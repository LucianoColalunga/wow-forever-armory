"""Consultas y serializadores compartidos por las rutas públicas."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import ColumnElement

from app.core.config import get_settings
from app.models import Character, Encounter, Fight, FightParticipant, Guild, Instance, Report, ReportIssue, SourceFile
from app.rankings.cache import current_version


def visible_report() -> list[ColumnElement[bool]]:
    return [Report.status == "processed", Report.visibility == "public", Report.deleted_at.is_(None)]


def visible_fight_query(dataset: str, include_duplicates: bool = False) -> Select[Fight]:
    q = select(Fight).join(Report, Report.id == Fight.report_id).where(Fight.dataset == dataset, *visible_report())
    if not include_duplicates:
        q = q.where(Fight.duplicate_of_id.is_(None))
    return q


def data_meta(db: Session, dataset: str) -> dict[str, Any]:
    settings = get_settings()
    last = db.scalar(select(func.max(Report.processed_at)).where(Report.dataset == dataset, *visible_report()))
    now = datetime.now(UTC)
    stale = last is not None and now - last > timedelta(hours=settings.stale_after_hours)
    return {
        "dataset": dataset,
        "is_demo": dataset == "demo",
        "data_version": current_version(db, dataset),
        "last_processed_at": last,
        "stale": bool(stale),
        "generated_at": now,
    }


def guild_dict(g: Guild | None) -> dict[str, Any] | None:
    if g is None or g.hidden:
        return None
    return {"id": g.id, "name": g.name, "realm": g.realm, "region": g.region, "faction": g.faction}


def character_dict(c: Character) -> dict[str, Any]:
    return {
        "id": c.id,
        "name": c.name,
        "realm": c.realm,
        "region": c.region,
        "class_slug": c.class_slug,
        "spec": c.spec,
        "class_source": c.class_source,
        "class_confidence": c.class_confidence,
        "faction": c.faction,
        "guild": guild_dict(c.guild),
        "guild_source": c.guild_source,
        "first_seen_at": c.first_seen_at,
        "last_seen_at": c.last_seen_at,
        "dataset": c.dataset,
    }


def instance_dict(i: Instance | None) -> dict[str, Any] | None:
    if i is None:
        return None
    return {
        "id": i.id,
        "slug": i.slug,
        "name": i.name,
        "kind": i.kind,
        "max_players": i.max_players,
        "verification": i.verification,
        "source_url": i.source_url,
        "is_new": i.is_new,
        "level_range": i.level_range,
        "notes": i.notes,
    }


def encounter_dict(e: Encounter | None) -> dict[str, Any] | None:
    if e is None:
        return None
    return {
        "id": e.id,
        "game_encounter_id": e.game_encounter_id,
        "name": e.name,
        "instance_id": e.instance_id,
        "dataset": e.dataset,
    }


def fight_summary(f: Fight) -> dict[str, Any]:
    return {
        "id": f.id,
        "kind": f.kind,
        "encounter": encounter_dict(f.encounter),
        "instance": instance_dict(f.instance),
        "difficulty_id": f.difficulty_id,
        "group_size": f.group_size,
        "success": f.success,
        "start_at": f.start_at,
        "duration_ms": f.duration_ms,
        "zone_name": f.zone_name,
        "rankable": f.rankable and not f.excluded_by_admin,
        "unrankable_reason": "excluido_por_admin" if f.excluded_by_admin else f.unrankable_reason,
        "duplicate_of_id": f.duplicate_of_id,
        "boss_min_hp_pct": f.boss_min_hp_pct,
        "player_count": f.player_count,
        "report_public_id": f.report.public_id,
        "dataset": f.dataset,
    }


PARTICIPANT_FIELDS = (
    "damage_done", "effective_damage", "overkill", "damage_absorbed_by_target", "damage_to_players",
    "healing_gross", "healing_effective", "overhealing", "heal_absorbed", "absorbs_provided", "damage_taken",
    "damage_taken_absorbed", "deaths", "interrupts", "dispels", "killing_blows", "time_alive_ms", "dps", "hps",
    "aps", "dtps", "survival_pct",
)  # fmt: skip


def participant_dict(p: FightParticipant, c: Character, include_details: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {
        "character_id": c.id,
        "name": c.name,
        "realm": c.realm,
        "class_slug": p.class_slug,
        "spec": p.spec,
        "role": p.role,
    }
    for k in PARTICIPANT_FIELDS:
        out[k] = getattr(p, k)
    if include_details:
        out["abilities"] = p.abilities
        out["death_log"] = p.death_log
    return out


def fight_detail(db: Session, f: Fight) -> dict[str, Any]:
    rows = db.execute(
        select(FightParticipant, Character)
        .join(Character, Character.id == FightParticipant.character_id)
        .where(FightParticipant.fight_id == f.id, Character.hidden.is_(False))
        .order_by(FightParticipant.damage_done.desc())
    ).all()
    issues = db.scalars(select(ReportIssue).where(ReportIssue.fight_id == f.id).order_by(ReportIssue.id)).all()
    source = db.get(SourceFile, f.report.source_file_id)
    hidden_ids = {
        str(c.id)
        for c in db.scalars(
            select(Character)
            .join(FightParticipant, FightParticipant.character_id == Character.id)
            .where(FightParticipant.fight_id == f.id, Character.hidden.is_(True))
        )
    }
    timeline = dict(f.timeline) if f.timeline else None
    if timeline and hidden_ids:
        for key in ("players_damage", "players_healing"):
            timeline[key] = {k: v for k, v in (timeline.get(key) or {}).items() if k not in hidden_ids}
    return {
        **fight_summary(f),
        "participants": [participant_dict(p, c) for p, c in rows],
        "timeline": timeline,
        "issues": [
            {"severity": i.severity, "code": i.code, "message": i.message, "line_no": i.line_no} for i in issues
        ],
        "source": {
            "report_public_id": f.report.public_id,
            "report_title": f.report.title,
            "file_sha256": source.sha256 if source else None,
            "file_name": source.original_name if source else None,
            "first_line": f.first_line,
            "last_line": f.last_line,
            "parser_version": f.parser_version,
        },
    }


def paged(
    items: list[Any], page: int, page_size: int, total: int, meta: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {"items": items, "page": page, "page_size": page_size, "total": total, "meta": meta}


def count_of(db: Session, q: Any) -> int:
    return int(db.scalar(select(func.count()).select_from(q.order_by(None).subquery())) or 0)
