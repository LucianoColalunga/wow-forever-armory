"""Pipeline de importación: alta del reporte (síncrona) y procesamiento (asíncrono, en el worker).

Trazabilidad: reporte → archivo (sha256, nombre original, tamaño) → combate (líneas first/last
del archivo) → participación → fila de ranking. Reprocesar reconstruye todo desde el archivo
guardado con la versión actual del parser.
"""

from __future__ import annotations

import logging
import re
import secrets
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, BinaryIO

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.importer import validation
from app.models import (
    Character,
    Encounter,
    Fight,
    FightParticipant,
    Guild,
    ImportJob,
    RankingEntry,
    Report,
    ReportIssue,
    SourceFile,
    User,
)
from app.parser import PARSER_VERSION, ParseResult, parse_lines
from app.parser.classes import role_for
from app.parser.parser import FightResult
from app.rankings import cache
from app.services.catalog import instance_for, season_for

log = logging.getLogger("wfa.importer")

DEDUPE_WINDOW_S = 120
DEDUPE_MIN_OVERLAP = 0.6
OUTLIER_MIN_SAMPLE = 10
OUTLIER_FACTOR = 3.0


@dataclass(slots=True)
class ImportMeta:
    title: str | None = None
    guild_name: str | None = None
    guild_realm: str | None = None
    region: str = ""
    faction: str | None = None
    visibility: str = "public"
    dataset: str = "real"
    utc_offset: int | None = None
    default_year: int | None = None


@dataclass(slots=True)
class ImportOutcome:
    report: Report
    duplicate: bool
    job: ImportJob | None


def _public_id() -> str:
    return secrets.token_hex(6)


def _get_or_create_guild(db: Session, name: str, realm: str, region: str, faction: str | None, dataset: str) -> Guild:
    guild = db.scalar(
        select(Guild).where(
            func.lower(Guild.name) == name.lower(),
            func.lower(Guild.realm) == realm.lower(),
            Guild.region == region,
            Guild.dataset == dataset,
        )
    )
    if guild is None:
        guild = Guild(name=name, realm=realm, region=region, faction=faction, dataset=dataset)
        db.add(guild)
        db.flush()
    return guild


def create_import(
    db: Session, settings: Settings, stream: BinaryIO, original_name: str | None, meta: ImportMeta, user: User | None
) -> ImportOutcome:
    """Valida, guarda y encola. Lanza ``validation.InvalidUpload`` con un mensaje mostrable."""
    tmp_dir = settings.storage_dir / "tmp"
    name = validation.safe_filename(original_name)
    saved = validation.save_stream(stream, tmp_dir, settings.max_upload_mb * 1024 * 1024)
    validated: validation.ValidatedLog | None = None
    stored = False
    try:
        validated = validation.validate_saved(
            saved,
            name,
            tmp_dir,
            max_uncompressed=settings.max_uncompressed_mb * 1024 * 1024,
            max_ratio=settings.max_compression_ratio,
        )
        # Los archivos de demo (BUILD_VERSION con "DEMO") nunca entran como datos reales.
        dataset = "demo" if _header_is_demo(validated.header) else meta.dataset

        existing = db.scalar(select(SourceFile).where(SourceFile.sha256 == validated.sha256))
        if existing is not None:
            report = db.scalar(
                select(Report)
                .where(Report.source_file_id == existing.id, Report.deleted_at.is_(None))
                .order_by(Report.id)
            )
            if report is not None:
                return ImportOutcome(report=report, duplicate=True, job=None)
            source = existing
        else:
            stored_path = validation.store_validated(validated, settings.storage_dir)
            stored = True
            source = SourceFile(
                sha256=validated.sha256,
                original_name=name,
                size_bytes=validated.size,
                stored_path=stored_path.relative_to(settings.storage_dir).as_posix(),
                content_kind=validated.content_kind,
                uploaded_by=user.id if user else None,
            )
            db.add(source)
            db.flush()

        guild = None
        if meta.guild_name:
            guild = _get_or_create_guild(
                db,
                meta.guild_name.strip()[:64],
                (meta.guild_realm or "").strip()[:64],
                meta.region,
                meta.faction,
                dataset,
            )
        report = Report(
            public_id=_public_id(),
            title=(meta.title or name).strip()[:128] or name,
            dataset=dataset,
            visibility=meta.visibility if meta.visibility in ("public", "private") else "public",
            status="queued",
            source_file_id=source.id,
            guild_id=guild.id if guild else None,
            uploaded_by=user.id if user else None,
            region=meta.region,
            fallback_utc_offset=meta.utc_offset,
            default_year=meta.default_year,
        )
        db.add(report)
        db.flush()
        job = ImportJob(report_id=report.id, kind="process", status="queued", max_attempts=settings.job_max_attempts)
        db.add(job)
        db.commit()
        return ImportOutcome(report=report, duplicate=False, job=job)
    finally:
        # Limpia temporales: el zip original y, si no se guardó, el texto extraído.
        saved.path.unlink(missing_ok=True)
        if validated is not None and not stored and validated.text_path.parent == tmp_dir:
            validated.text_path.unlink(missing_ok=True)


_BUILD_RE = re.compile(r"BUILD_VERSION,([^,\s]+)")


def _header_is_demo(header: str | None) -> bool:
    if not header or "COMBAT_LOG_VERSION" not in header:
        return False
    m = _BUILD_RE.search(header)
    return bool(m and "DEMO" in m.group(1).upper())


def enqueue_reprocess(db: Session, report: Report, settings: Settings) -> ImportJob:
    job = ImportJob(report_id=report.id, kind="reprocess", status="queued", max_attempts=settings.job_max_attempts)
    report.status = "queued"
    db.add(job)
    return job


# ---------------------------------------------------------------------------
# Procesamiento
# ---------------------------------------------------------------------------


def _read_lines(path: Path) -> Iterator[str]:
    with path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
        first = True
        for line in fh:
            if first:
                line = line.lstrip("﻿")
                first = False
            yield line


def parse_report_file(settings: Settings, report: Report, source: SourceFile) -> ParseResult:
    path = settings.storage_dir / source.stored_path
    if not path.exists():
        raise FileNotFoundError(f"Archivo de origen no encontrado para el reporte {report.public_id}")
    default_year = report.default_year or (report.created_at or datetime.now(UTC)).year
    return parse_lines(_read_lines(path), default_year=default_year, fallback_utc_offset=report.fallback_utc_offset)


def _clear_report(db: Session, report: Report) -> set[int]:
    """Borra lo derivado del reporte. Devuelve los reportes cuyos duplicados quedaron liberados."""
    db.execute(delete(ReportIssue).where(ReportIssue.report_id == report.id))
    fight_ids = select(Fight.id).where(Fight.report_id == report.id).scalar_subquery()
    # Los combates de otros reportes que eran duplicados de éstos vuelven a ser canónicos.
    freed = set(db.scalars(select(Fight.report_id).where(Fight.duplicate_of_id.in_(fight_ids))))
    db.execute(
        update(Fight)
        .where(Fight.duplicate_of_id.in_(fight_ids), Fight.unrankable_reason == "duplicado")
        .values(duplicate_of_id=None, rankable=True, unrankable_reason=None)
    )
    db.execute(update(Fight).where(Fight.duplicate_of_id.in_(fight_ids)).values(duplicate_of_id=None))
    db.execute(delete(Fight).where(Fight.report_id == report.id))
    freed.discard(report.id)
    return freed


def _upsert_character(
    db: Session, report: Report, result: ParseResult, guid: str, cache_map: dict[str, Character], seen_at: datetime
) -> Character:
    if guid in cache_map:
        return cache_map[guid]
    unit = result.units.get(guid)
    char = db.scalar(select(Character).where(Character.guid == guid, Character.dataset == report.dataset))
    name = (unit.name if unit and unit.name else guid)[:64]
    realm = (unit.realm if unit and unit.realm else "")[:64]
    region = (unit.region if unit and unit.region else report.region or "")[:8]
    if char is None:
        char = Character(
            guid=guid,
            name=name,
            realm=realm,
            region=region,
            dataset=report.dataset,
            first_seen_at=seen_at,
            last_seen_at=seen_at,
            class_source="unknown",
            class_confidence=0.0,
        )
        db.add(char)
    else:
        if unit and unit.name:
            char.name = name
            char.realm = realm or char.realm
        char.first_seen_at = min(filter(None, [char.first_seen_at, seen_at]))
        char.last_seen_at = max(filter(None, [char.last_seen_at, seen_at]))
    if unit is not None:
        if unit.faction:
            char.faction = unit.faction
        g = unit.guess
        if (
            g is not None
            and g.class_slug
            and not char.class_locked
            and (g.confidence >= (char.class_confidence or 0.0) or char.class_slug is None)
        ):
            char.class_slug, char.class_source, char.class_confidence = g.class_slug, g.source, g.confidence
            if g.spec:
                char.spec = g.spec
    if (
        report.guild_id
        and (char.guild_id is None or char.guild_source == "report_tag")
        and char.guild_source != "admin"
    ):
        char.guild_id = report.guild_id
        char.guild_source = "report_tag"
    db.flush()
    cache_map[guid] = char
    return char


def _find_duplicate(db: Session, report: Report, fight: Fight, guids: set[str]) -> Fight | None:
    window = timedelta(seconds=DEDUPE_WINDOW_S)
    q = (
        select(Fight)
        .join(Report, Report.id == Fight.report_id)
        .where(
            Fight.dataset == fight.dataset,
            Fight.kind == fight.kind,
            Fight.duplicate_of_id.is_(None),
            Fight.start_at.between(fight.start_at - window, fight.start_at + window),
            Report.deleted_at.is_(None),
            Fight.id != fight.id,
        )
    )
    if fight.kind == "encounter":
        q = q.where(
            Fight.encounter_id == fight.encounter_id,
            Fight.difficulty_id == fight.difficulty_id,
            Fight.group_size == fight.group_size,
            Fight.success == fight.success,
        )
    else:
        q = q.where(Fight.zone_name == fight.zone_name)
    for cand in db.scalars(q.order_by(Fight.id)):
        if cand.report_id == report.id and cand.start_at != fight.start_at:
            continue
        other = set(
            db.scalars(
                select(Character.guid)
                .join(FightParticipant, FightParticipant.character_id == Character.id)
                .where(FightParticipant.fight_id == cand.id)
            )
        )
        if not other or not guids:
            continue
        overlap = len(other & guids) / min(len(other), len(guids))
        if overlap >= DEDUPE_MIN_OVERLAP:
            return cand
    return None


def _is_outlier(db: Session, fight: Fight, dps_values: list[float]) -> bool:
    """Marca para revisión si algún DPS supera 3× el máximo histórico de la misma partición."""
    if fight.kind != "encounter" or not fight.success or not dps_values:
        return False
    stats = db.execute(
        select(func.count(), func.max(RankingEntry.dps)).where(
            RankingEntry.dataset == fight.dataset,
            RankingEntry.kind == "pve",
            RankingEntry.encounter_id == fight.encounter_id,
            RankingEntry.difficulty_id == fight.difficulty_id,
            RankingEntry.group_size == fight.group_size,
        )
    ).one()
    count, max_dps = stats
    return bool(count >= OUTLIER_MIN_SAMPLE and max_dps and max(dps_values) > OUTLIER_FACTOR * max_dps)


def _compact_casts(casts: list[tuple[int, str]] | None) -> dict[str, Any] | None:
    """Línea de tiempo compacta: lista de hechizos y, por lanzamiento, (ms, índice del hechizo)."""
    if not casts:
        return None
    spells: list[str] = []
    index: dict[str, int] = {}
    t: list[int] = []
    s: list[int] = []
    for ms, name in casts:
        if name not in index:
            index[name] = len(spells)
            spells.append(name)
        t.append(ms)
        s.append(index[name])
    return {"spells": spells, "t": t, "s": s}


def _abilities(counter: Any, limit: int = 12) -> list[dict[str, Any]]:
    return [{"name": k, "amount": int(v)} for k, v in counter.most_common(limit) if v > 0]


def apply_parse_result(db: Session, report: Report, result: ParseResult) -> dict[str, Any]:
    freed = _clear_report(db, report)
    if result.is_demo and report.dataset != "demo":
        report.dataset = "demo"
        db.add(
            ReportIssue(
                report_id=report.id,
                severity="info",
                code="demo_file",
                message="El archivo es un fixture de demostración: se clasificó como dato DEMO.",
            )
        )
    chars: dict[str, Character] = {}
    summary = {"fights": 0, "encounters": 0, "kills": 0, "duplicates": 0, "unrankable": 0, "players": 0}

    for issue in result.issues:
        if issue.fight_index is None:
            db.add(
                ReportIssue(
                    report_id=report.id,
                    severity=issue.severity,
                    code=issue.code,
                    message=issue.message[:2000],
                    line_no=issue.line_no,
                )
            )

    for fr in result.fights:
        if not fr.players:
            continue
        fight = _store_fight(db, report, result, fr, chars, summary)
        for issue in fr.issues:
            db.add(
                ReportIssue(
                    report_id=report.id,
                    fight_id=fight.id,
                    severity=issue.severity,
                    code=issue.code,
                    message=issue.message[:2000],
                    line_no=issue.line_no,
                )
            )

    summary["players"] = len(chars)
    report.parser_version = PARSER_VERSION
    report.dialect = result.dialect.as_dict()
    report.stats = {**result.stats.as_dict(), **summary, "timezone_assumed": result.timezone_assumed}
    report.log_started_at = result.started_at
    report.log_ended_at = result.ended_at
    report.status = "processed"
    report.error = None
    report.processed_at = datetime.now(UTC)
    db.flush()
    cache.rebuild_for_report(db, report)
    for other_id in freed:
        other = db.get(Report, other_id)
        if other is not None:
            cache.rebuild_for_report(db, other)
    return summary


def _store_fight(
    db: Session,
    report: Report,
    result: ParseResult,
    fr: FightResult,
    chars: dict[str, Character],
    summary: dict[str, int],
) -> Fight:
    encounter = None
    if fr.kind == "encounter" and fr.encounter_id:
        encounter = db.scalar(
            select(Encounter).where(Encounter.game_encounter_id == fr.encounter_id, Encounter.dataset == report.dataset)
        )
        inst = instance_for(db, fr.zone_name, fr.instance_id)
        if encounter is None:
            encounter = Encounter(
                game_encounter_id=fr.encounter_id,
                name=(fr.encounter_name or "?")[:128],
                instance_id=inst.id if inst else None,
                dataset=report.dataset,
            )
            db.add(encounter)
            db.flush()
        elif encounter.instance_id is None and inst is not None:
            encounter.instance_id = inst.id
        instance = inst
    else:
        instance = instance_for(db, fr.zone_name, fr.instance_id)
    season = season_for(db, fr.start, "pvp" if fr.kind == "battleground" else "pve")
    timeline = fr.timeline.export(fr.duration_ms) if fr.kind in ("encounter", "battleground") else None
    fight = Fight(
        report_id=report.id,
        encounter_id=encounter.id if encounter else None,
        instance_id=instance.id if instance else (encounter.instance_id if encounter else None),
        season_id=season.id if season else None,
        kind=fr.kind,
        dataset=report.dataset,
        difficulty_id=fr.difficulty_id,
        group_size=fr.group_size,
        success=fr.success,
        start_at=fr.start,
        end_at=fr.end,
        duration_ms=fr.duration_ms,
        zone_name=(fr.zone_name or None),
        game_instance_id=fr.instance_id,
        first_line=fr.first_line,
        last_line=fr.last_line,
        fight_key=fr.fight_key,
        rankable=fr.rankable,
        unrankable_reason=fr.unrankable_reason,
        boss_min_hp_pct=fr.boss_min_hp_pct,
        player_count=len(fr.players),
        parser_version=PARSER_VERSION,
        timeline=None,
    )
    if fight.kind == "dungeon_run":
        fight.rankable = False
        fight.unrankable_reason = fight.unrankable_reason or "no_rankeable"
    db.add(fight)
    db.flush()

    # Participantes
    total_taken = sum(p.damage_taken for p in fr.players.values()) or 0
    guids = {g for g in fr.players if g.startswith("Player-")}
    dps_values: list[float] = []
    guid_to_char: dict[str, int] = {}
    for guid in sorted(guids):
        ps = fr.players[guid]
        char = _upsert_character(db, report, result, guid, chars, fr.start)
        guid_to_char[guid] = char.id
        m = ps.as_metrics(fr.duration_ms)
        heal_share = (ps.healing_effective + ps.absorbs_provided) / max(
            1, ps.damage_done + ps.healing_effective + ps.absorbs_provided
        )
        taken_share = ps.damage_taken / total_taken if total_taken else 0.0
        role = role_for(char.class_slug, char.spec, heal_share, taken_share)
        if role == "dps":
            dps_values.append(m["dps"])
        db.add(
            FightParticipant(
                fight_id=fight.id,
                character_id=char.id,
                class_slug=char.class_slug,
                spec=char.spec,
                role=role,
                damage_done=ps.damage_done,
                effective_damage=ps.effective_damage,
                overkill=ps.overkill,
                damage_absorbed_by_target=ps.damage_absorbed_by_target,
                damage_to_players=ps.damage_to_players,
                healing_gross=ps.healing_gross,
                healing_effective=ps.healing_effective,
                overhealing=ps.overhealing,
                heal_absorbed=ps.heal_absorbed,
                absorbs_provided=ps.absorbs_provided,
                damage_taken=ps.damage_taken,
                damage_taken_absorbed=ps.damage_taken_absorbed,
                deaths=ps.deaths,
                interrupts=ps.interrupts,
                dispels=ps.dispels,
                killing_blows=ps.killing_blows,
                time_alive_ms=int(m["time_alive_ms"]),
                dps=m["dps"],
                hps=m["hps"],
                aps=m["aps"],
                dtps=m["dtps"],
                survival_pct=m["survival_pct"],
                abilities={"damage": _abilities(ps.damage_by_ability), "healing": _abilities(ps.healing_by_ability)},
                death_log=ps.death_log or None,
                gear=fr.gear.get(guid),
                casts=_compact_casts(fr.casts.get(guid)),
            )
        )
    if timeline is not None:
        # Las series por jugador se indexan por id de personaje (no por GUID) para la API pública.
        timeline["players_damage"] = {
            str(guid_to_char[g]): v for g, v in timeline["players_damage"].items() if g in guid_to_char
        }
        timeline["players_healing"] = {
            str(guid_to_char[g]): v for g, v in timeline["players_healing"].items() if g in guid_to_char
        }
        fight.timeline = timeline
    db.flush()

    summary["fights"] += 1
    if fight.kind == "encounter":
        summary["encounters"] += 1
        if fight.success:
            summary["kills"] += 1

    if fight.kind in ("encounter", "battleground"):
        dup = _find_duplicate(db, report, fight, guids)
        if dup is not None:
            fight.duplicate_of_id = dup.id
            if fight.rankable:
                fight.rankable = False
                fight.unrankable_reason = "duplicado"
            summary["duplicates"] += 1
            db.add(
                ReportIssue(
                    report_id=report.id,
                    fight_id=fight.id,
                    severity="info",
                    code="duplicate_fight",
                    message=f"Combate ya importado en el reporte {dup.report.public_id} "
                    f"(combate #{dup.id}); no suma a rankings ni estadísticas.",
                )
            )
        elif fight.rankable and _is_outlier(db, fight, dps_values):
            fight.rankable = False
            fight.unrankable_reason = "revision_outlier"
            db.add(
                ReportIssue(
                    report_id=report.id,
                    fight_id=fight.id,
                    severity="warning",
                    code="outlier_dps",
                    message="DPS muy por encima del máximo histórico de este encuentro: queda fuera de "
                    "rankings hasta que un admin lo revise.",
                )
            )
    if not fight.rankable:
        summary["unrankable"] += 1
    return fight


def process_report(db: Session, settings: Settings, report_id: int) -> dict[str, Any]:
    report = db.get(Report, report_id)
    if report is None:
        raise LookupError(f"Reporte {report_id} inexistente")
    source = db.get(SourceFile, report.source_file_id)
    assert source is not None
    report.status = "processing"
    db.commit()
    result = parse_report_file(settings, report, source)
    fatal = [i for i in result.issues if i.severity == "error" and i.code == "parse_error_ratio"]
    if result.stats.parsed_lines == 0 or fatal:
        report.status = "failed"
        report.error = "No se pudo interpretar el archivo: " + (fatal[0].message if fatal else "sin eventos válidos.")
        report.parser_version = PARSER_VERSION
        report.stats = result.stats.as_dict()
        db.commit()
        return {"status": "failed"}
    summary = apply_parse_result(db, report, result)
    db.commit()
    log.info("reporte procesado", extra={"report_id": report.id})
    return summary
