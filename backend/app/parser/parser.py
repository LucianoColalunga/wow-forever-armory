"""Parser en streaming del combat log.

Un solo recorrido del archivo: cada línea se tokeniza, se normaliza y se aplica a los
segmentos abiertos (encuentro de jefe, mazmorra o campo de batalla).

Reglas de atribución y anti-doble conteo (con tests en tests/unit/test_parser*.py):
- ``SWING_DAMAGE_LANDED`` repite el mismo golpe que ``SWING_DAMAGE``: se ignora.
- ``DAMAGE_SPLIT`` no es daño realizado (redistribución): se ignora para daño hecho.
- ``*_SUPPORT`` repite golpes ya contados: se ignora.
- El campo ``absorbed`` de los eventos de daño se usa sólo para ``damage_done`` del atacante;
  ``SPELL_ABSORBED`` se usa sólo para ``absorbs_provided`` del lanzador del escudo.
- Mascotas/guardianes se atribuyen al dueño (``SPELL_SUMMON`` y ``ownerGUID`` del bloque avanzado).
- ``UNIT_DIED`` por Fingir Muerte o con ``unconsciousOnDeath`` no cuenta como muerte.
- Los eventos posteriores a ``ENCOUNTER_END`` no se cuentan (ventana fija del encuentro).
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.catalog.forever import classify_zone
from app.parser import dialects
from app.parser.classes import SPEC_IDS, ClassGuess, infer_class_spec, role_for
from app.parser.constants import (
    FEIGN_DEATH_SPELL_IDS,
    FEIGN_DEATH_SPELL_NAMES,
    NIL_GUID,
    REACTION_FRIENDLY,
    REACTION_HOSTILE,
    REACTION_MASK,
    REACTION_NEUTRAL,
    TYPE_MASK,
    TYPE_PLAYER,
)
from app.parser.gear import extract_items
from app.parser.metrics import PlayerStats, Timeline
from app.parser.tokenizer import (
    LineFormatError,
    RawLine,
    as_bool,
    as_flag,
    as_int,
    as_str,
    looks_like_guid,
    to_utc,
    tokenize,
)

PARSER_VERSION = "1.1.0"  # 1.1: equipo por encuentro y línea de tiempo de lanzamientos

TIMELINE_BUCKET_MS = 5000
MIN_RANKABLE_DURATION_MS = 15_000
MAX_LINE_LENGTH = 65_536
MAX_STORED_ISSUES = 200
MAX_CASTS_PER_PLAYER = 1500


@dataclass(slots=True)
class Issue:
    severity: str  # info | warning | error
    code: str
    message: str
    line_no: int | None = None
    fight_index: int | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "line_no": self.line_no,
            "fight_index": self.fight_index,
        }


@dataclass(slots=True)
class UnitInfo:
    guid: str
    name: str | None = None
    realm: str | None = None
    region: str | None = None
    faction: str | None = None
    spec_id: int | None = None
    spell_casts: Counter[str] = field(default_factory=Counter)
    guess: ClassGuess | None = None
    gear: list[dict[str, Any]] | None = None


@dataclass(slots=True)
class FightResult:
    index: int
    kind: str  # encounter | dungeon_run | battleground
    start: datetime
    first_line: int
    encounter_id: int | None = None
    encounter_name: str | None = None
    difficulty_id: int | None = None
    group_size: int | None = None
    instance_id: int | None = None
    zone_name: str | None = None
    success: bool | None = None
    end: datetime | None = None
    last_line: int | None = None
    reported_duration_ms: int | None = None
    complete: bool = False
    players: dict[str, PlayerStats] = field(default_factory=dict)
    roster: set[str] = field(default_factory=set)
    timeline: Timeline = field(default_factory=lambda: Timeline(TIMELINE_BUCKET_MS))
    boss_guid: str | None = None
    boss_max_hp: int = 0
    boss_min_hp_pct: float | None = None
    creature_hp: dict[str, tuple[int, float]] = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)
    absorbed_on_hits: int = 0
    absorbed_events_total: int = 0
    rankable: bool = True
    unrankable_reason: str | None = None
    # campos derivados al cerrar
    duration_ms: int = 0
    fight_key: str = ""
    # equipo informado por COMBATANT_INFO y lanzamientos (ms relativo, hechizo) por jugador
    gear: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    casts: dict[str, list[tuple[int, str]]] = field(default_factory=dict)

    def stats_for(self, guid: str, name: str | None) -> PlayerStats:
        ps = self.players.get(guid)
        if ps is None:
            ps = PlayerStats(guid=guid, name=name)
            self.players[guid] = ps
        elif name and not ps.name:
            ps.name = name
        return ps

    def rel_ms(self, t: datetime) -> int:
        d = t - self.start
        return d.days * 86_400_000 + d.seconds * 1000 + d.microseconds // 1000


@dataclass(slots=True)
class ParseStats:
    total_lines: int = 0
    parsed_lines: int = 0
    error_lines: int = 0
    blank_lines: int = 0
    unknown_events: Counter[str] = field(default_factory=Counter)
    event_counts: Counter[str] = field(default_factory=Counter)
    non_monotonic: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "total_lines": self.total_lines,
            "parsed_lines": self.parsed_lines,
            "error_lines": self.error_lines,
            "blank_lines": self.blank_lines,
            "non_monotonic": self.non_monotonic,
            "unknown_events": dict(self.unknown_events.most_common(20)),
            "top_events": dict(self.event_counts.most_common(25)),
        }


@dataclass(slots=True)
class ParseResult:
    parser_version: str
    dialect: dialects.Dialect
    stats: ParseStats
    issues: list[Issue]
    fights: list[FightResult]
    units: dict[str, UnitInfo]
    started_at: datetime | None
    ended_at: datetime | None
    timezone_assumed: bool

    @property
    def is_demo(self) -> bool:
        return self.dialect.is_demo


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _is_player_guid(guid: str | None) -> bool:
    return bool(guid) and guid.startswith("Player-")  # type: ignore[union-attr]


def _reaction(flags: int) -> int:
    return flags & REACTION_MASK


def _is_enemy(src_flags: int, dst_flags: int) -> bool:
    s, d = _reaction(src_flags), _reaction(dst_flags)
    if s == REACTION_FRIENDLY:
        return d in (REACTION_HOSTILE, REACTION_NEUTRAL)
    if s == REACTION_HOSTILE:
        return d == REACTION_FRIENDLY
    return False


def _same_side(src_flags: int, dst_flags: int) -> bool:
    s, d = _reaction(src_flags), _reaction(dst_flags)
    return s == d and s in (REACTION_FRIENDLY, REACTION_HOSTILE)


def _split_name(full: str | None) -> tuple[str | None, str | None, str | None]:
    """``Nombre-Reino-Región`` → (nombre, reino, región). Los campos faltantes quedan en None."""
    if not full:
        return None, None, None
    parts = full.split("-")
    name = parts[0] or None
    realm = parts[1] if len(parts) > 1 and parts[1] else None
    region = parts[2] if len(parts) > 2 and parts[2] else None
    return name, realm, region


def _suffix_of(event: str) -> tuple[str, str]:
    """Separa prefijo y sufijo (``SPELL_PERIODIC_DAMAGE`` → (``SPELL_PERIODIC_``, ``_DAMAGE``))."""
    for prefix in ("SPELL_BUILDING_", "SPELL_PERIODIC_", "SPELL_", "RANGE_", "SWING_", "ENVIRONMENTAL_"):
        if event.startswith(prefix):
            return prefix, "_" + event[len(prefix) :]
    if event.startswith("DAMAGE_SHIELD_MISSED"):
        return "SPELL_", "_MISSED"
    if event.startswith("DAMAGE_SHIELD") or event.startswith("DAMAGE_SPLIT"):
        return "SPELL_", "_DAMAGE"
    return "", event


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class CombatLogParser:
    def __init__(
        self,
        *,
        default_year: int,
        fallback_utc_offset: int | None = None,
        zone_classifier: Callable[[str | None], str | None] = classify_zone,
    ) -> None:
        self.default_year = default_year
        self.fallback_utc_offset = fallback_utc_offset
        self.zone_classifier = zone_classifier
        self.stats = ParseStats()
        self.issues: list[Issue] = []
        self.fights: list[FightResult] = []
        self.units: dict[str, UnitInfo] = {}
        self.dialect: dialects.Dialect | None = None
        self.pet_owner: dict[str, str] = {}
        self.encounter: FightResult | None = None
        self.zone_seg: FightResult | None = None
        self.year = default_year
        self.last_month: int | None = None
        self.last_ts: datetime | None = None
        self.first_ts: datetime | None = None
        self.timezone_assumed = False
        self.saw_year = False
        self.advanced_samples: Counter[int] = Counter()
        self.last_hit: dict[str, tuple[datetime, str | None, str | None, str | None]] = {}
        self.feign_cast: dict[str, datetime] = {}
        self.current_zone: str | None = None

    # -- issues -----------------------------------------------------------------
    def _issue(
        self, severity: str, code: str, message: str, line_no: int | None = None, fight: FightResult | None = None
    ) -> None:
        issue = Issue(severity, code, message, line_no, fight.index if fight else None)
        if fight is not None:
            fight.issues.append(issue)
        if len(self.issues) < MAX_STORED_ISSUES:
            self.issues.append(issue)

    # -- unidades ---------------------------------------------------------------
    def _unit(self, guid: str, name: str | None) -> UnitInfo:
        u = self.units.get(guid)
        if u is None:
            n, realm, region = _split_name(name)
            u = UnitInfo(guid=guid, name=n, realm=realm, region=region)
            self.units[guid] = u
        elif name and not u.name:
            u.name, u.realm, u.region = _split_name(name)
        return u

    def _pname(self, guid: str) -> str | None:
        u = self.units.get(guid)
        if u is None:
            u = self._unit(guid, None)
        return u.name

    def _owner(self, guid: str | None) -> str | None:
        """Jugador responsable de una unidad (él mismo, o el dueño de su mascota)."""
        seen = 0
        while guid and seen < 4:
            if _is_player_guid(guid):
                return guid
            guid = self.pet_owner.get(guid)
            seen += 1
        return None

    # -- segmentos --------------------------------------------------------------
    def _active(self) -> list[FightResult]:
        segs = []
        if self.encounter is not None:
            segs.append(self.encounter)
        if self.zone_seg is not None:
            segs.append(self.zone_seg)
        return segs

    def _open(self, kind: str, ts: datetime, line_no: int, **kw: object) -> FightResult:
        fight = FightResult(index=len(self.fights), kind=kind, start=ts, first_line=line_no)
        for k, v in kw.items():
            setattr(fight, k, v)
        self.fights.append(fight)
        return fight

    def _close(self, fight: FightResult, ts: datetime, line_no: int, complete: bool) -> None:
        fight.end = ts
        fight.last_line = line_no
        fight.complete = complete
        measured = max(0, fight.rel_ms(ts))
        if fight.kind == "encounter" and fight.reported_duration_ms:
            fight.duration_ms = fight.reported_duration_ms
            if abs(fight.reported_duration_ms - measured) > max(3000, 0.1 * measured):
                self._issue(
                    "warning",
                    "duration_mismatch",
                    f"Duración informada por ENCOUNTER_END ({fight.reported_duration_ms} ms) difiere de la "
                    f"medida por timestamps ({measured} ms).",
                    line_no,
                    fight,
                )
        else:
            fight.duration_ms = measured
        if not complete:
            fight.rankable = False
            fight.unrankable_reason = "incompleto"
            self._issue(
                "error",
                "incomplete_fight",
                f"Segmento '{fight.encounter_name or fight.zone_name}' sin cierre (archivo cortado o /reload).",
                line_no,
                fight,
            )
        elif fight.kind == "encounter" and fight.success and fight.duration_ms < MIN_RANKABLE_DURATION_MS:
            fight.rankable = False
            fight.unrankable_reason = "duracion_minima"
            self._issue(
                "warning",
                "too_short",
                f"Combate de {fight.duration_ms} ms: menor al mínimo rankeable ({MIN_RANKABLE_DURATION_MS} ms).",
                line_no,
                fight,
            )
        if fight.kind == "encounter":
            # Consistencia de absorciones: lo absorbido en golpes debe coincidir con SPELL_ABSORBED.
            a, b = fight.absorbed_on_hits, fight.absorbed_events_total
            if max(a, b) > 1000 and abs(a - b) > 0.1 * max(a, b):
                self._issue(
                    "warning",
                    "absorb_mismatch",
                    f"Absorciones inconsistentes: golpes={a}, SPELL_ABSORBED={b}.",
                    line_no,
                    fight,
                )
            if fight.boss_guid is not None and fight.success:
                fight.boss_min_hp_pct = 0.0
        roster = fight.roster or set(fight.players)
        fight.fight_key = hashlib.sha256(
            (
                f"{fight.kind}:{fight.encounter_id}:{fight.difficulty_id}:{fight.group_size}:"
                f"{fight.zone_name}:" + ",".join(sorted(roster))
            ).encode()
        ).hexdigest()

    def _close_all(self, ts: datetime, line_no: int, complete: bool) -> None:
        if self.encounter is not None:
            self._close(self.encounter, ts, line_no, complete)
            self.encounter = None
        if self.zone_seg is not None:
            # Salir de la zona por fin de archivo no es un error para mazmorras/BG.
            self._close(self.zone_seg, ts, line_no, True)
            self.zone_seg = None

    # -- timestamps -------------------------------------------------------------
    def _timestamp(self, raw: RawLine) -> datetime:
        if raw.year is not None:
            self.year = raw.year
            self.saw_year = True
        elif self.last_month is not None and raw.month < self.last_month:
            self.year += 1  # cruce de año en logs sin año (diciembre → enero)
        self.last_month = raw.month
        if raw.utc_offset_hours is None and self.fallback_utc_offset is None:
            self.timezone_assumed = True
        ts = to_utc(raw, self.year, self.fallback_utc_offset)
        if self.last_ts is not None and (self.last_ts - ts).total_seconds() > 2:
            self.stats.non_monotonic += 1
        self.last_ts = ts
        if self.first_ts is None:
            self.first_ts = ts
        return ts

    # -- entrada principal ------------------------------------------------------
    def feed(self, lines: Iterable[str]) -> ParseResult:
        line_no = 0
        last_ts: datetime | None = None
        for line_no, line in enumerate(lines, start=1):
            self.stats.total_lines += 1
            line = line.rstrip("\r\n")
            if not line.strip():
                self.stats.blank_lines += 1
                continue
            if len(line) > MAX_LINE_LENGTH:
                self.stats.error_lines += 1
                self._issue("warning", "line_too_long", "Línea demasiado larga; se ignoró.", line_no)
                continue
            try:
                raw = tokenize(line, line_no)
            except (LineFormatError, ValueError):
                self.stats.error_lines += 1
                if self.stats.error_lines <= 20:
                    self._issue("warning", "malformed_line", "Línea con formato inválido; se ignoró.", line_no)
                continue
            try:
                ts = self._timestamp(raw)
                last_ts = ts
                self._dispatch(raw, ts)
                self.stats.parsed_lines += 1
            except (IndexError, ValueError, OverflowError) as exc:
                self.stats.error_lines += 1
                if self.stats.error_lines <= 20:
                    self._issue(
                        "warning", "event_error", f"Evento con campos inválidos: {type(exc).__name__}.", line_no
                    )
        if last_ts is not None:
            if self.encounter is not None:
                self._close(self.encounter, last_ts, line_no, complete=False)
                self.encounter = None
            if self.zone_seg is not None:
                self._close(self.zone_seg, last_ts, line_no, complete=True)
                self.zone_seg = None
        return self._finish()

    # -- despacho por evento ----------------------------------------------------
    def _dispatch(self, raw: RawLine, ts: datetime) -> None:
        f = raw.fields
        event = f[0]
        self.stats.event_counts[event] += 1

        if event == "COMBAT_LOG_VERSION":
            if self.dialect is not None:
                # Nueva cabecera a mitad de archivo = el cliente reinició el log (/reload).
                self._issue("info", "log_restarted", "El log se reinició (nueva cabecera).", raw.line_no)
                if self.encounter is not None:
                    self._close(self.encounter, ts, raw.line_no, complete=False)
                    self.encounter = None
            new = dialects.from_header(f)
            if self.dialect is not None:
                new.advanced_block = self.dialect.advanced_block
                new.advanced_block_calibrated = self.dialect.advanced_block_calibrated
                new.is_demo = new.is_demo or self.dialect.is_demo
            self.dialect = new
            for note in new.notes:
                self._issue("info", "dialect_note", note, raw.line_no)
            return
        if self.dialect is None:
            self.dialect = dialects.legacy()
            self._issue("info", "no_header", self.dialect.notes[0], raw.line_no)

        if event == "ENCOUNTER_START":
            self._encounter_start(raw, ts)
            return
        if event == "ENCOUNTER_END":
            self._encounter_end(raw, ts)
            return
        if event == "ZONE_CHANGE":
            self._zone_change(raw, ts)
            return
        if event == "COMBATANT_INFO":
            self._combatant_info(raw)
            return
        if event in (
            "MAP_CHANGE",
            "EMOTE",
            "WORLD_MARKER_PLACED",
            "WORLD_MARKER_REMOVED",
            "ENCHANT_APPLIED",
            "ENCHANT_REMOVED",
            "PARTY_KILL",
            "UNIT_DESTROYED",
            "UNIT_DISSIPATES",
            "CHALLENGE_MODE_START",
            "CHALLENGE_MODE_END",
            "ARENA_MATCH_START",
            "ARENA_MATCH_END",
        ):
            # Se registran pero no generan métricas (Forever no tiene Mythic+ ni arenas confirmadas).
            return
        if len(f) < 9:
            self.stats.unknown_events[event] += 1
            return

        src_guid, src_name, src_flags = f[1], as_str(f[2]), as_flag(f[3])
        dst_guid, dst_name, dst_flags = f[5], as_str(f[6]), as_flag(f[7])
        if src_flags & TYPE_MASK == TYPE_PLAYER or _is_player_guid(src_guid):
            self._unit(src_guid, src_name)
        if dst_flags & TYPE_MASK == TYPE_PLAYER or _is_player_guid(dst_guid):
            self._unit(dst_guid, dst_name)

        if event == "UNIT_DIED":
            self._unit_died(raw, ts, dst_guid, dst_name)
            return
        if event.endswith("_SUPPORT") or event == "SWING_DAMAGE_LANDED" or event.startswith("DAMAGE_SPLIT"):
            return
        if event == "SPELL_ABSORBED":
            self._absorbed(raw, ts)
            return

        prefix, suffix = _suffix_of(event)
        if not prefix:
            self.stats.unknown_events[event] += 1
            return
        idx = 9
        spell_id: int | None = None
        spell_name: str | None = None
        env_type: str | None = None
        if prefix in ("SPELL_", "SPELL_PERIODIC_", "SPELL_BUILDING_", "RANGE_"):
            spell_id, spell_name = as_int(f[9]), as_str(f[10])
            idx = 12
        elif prefix == "ENVIRONMENTAL_" and not self._has_advanced(f, 9):
            env_type = as_str(f[9])
            idx = 10

        adv = suffix in ("_DAMAGE", "_HEAL", "_CAST_SUCCESS", "_ENERGIZE", "_DRAIN", "_LEECH") and self._has_advanced(
            f, idx
        )
        if adv:
            if suffix == "_CAST_SUCCESS":
                self.advanced_samples[len(f) - idx] += 1
            block = self._advanced_block_size()
            info_guid, owner_guid = f[idx], f[idx + 1]
            if owner_guid and owner_guid != NIL_GUID and owner_guid != info_guid and _is_player_guid(owner_guid):
                self.pet_owner.setdefault(info_guid, owner_guid)
            self._track_hp(f, idx, info_guid)
            idx += block
            if prefix == "ENVIRONMENTAL_":
                env_type = as_str(f[idx])
                idx += 1

        if suffix == "_SUMMON":
            owner = self._owner(src_guid)
            if owner and dst_guid and not _is_player_guid(dst_guid):
                self.pet_owner[dst_guid] = owner
            return
        if suffix in ("_CAST_SUCCESS", "_CAST_START"):
            if _is_player_guid(src_guid) and spell_name:
                self.units[src_guid].spell_casts[spell_name] += 1
                if suffix == "_CAST_SUCCESS" and (
                    (spell_id in FEIGN_DEATH_SPELL_IDS) or spell_name.lower() in FEIGN_DEATH_SPELL_NAMES
                ):
                    self.feign_cast[src_guid] = ts
                if self.encounter is not None and _reaction(src_flags) == REACTION_FRIENDLY:
                    self.encounter.roster.add(src_guid)
                if suffix == "_CAST_SUCCESS":
                    for seg in self._active():
                        timeline = seg.casts.setdefault(src_guid, [])
                        if len(timeline) < MAX_CASTS_PER_PLAYER:
                            timeline.append((seg.rel_ms(ts), spell_name))
            return

        segs = self._active()
        if not segs:
            return
        if suffix == "_DAMAGE":
            self._damage(
                f,
                idx,
                adv,
                ts,
                segs,
                src_guid,
                src_name,
                src_flags,
                dst_guid,
                dst_name,
                dst_flags,
                spell_name or ("Melee" if prefix == "SWING_" else env_type or "?"),
                env=prefix == "ENVIRONMENTAL_",
            )
        elif suffix == "_MISSED":
            self._missed(f, idx, segs, src_guid, src_name, src_flags, dst_guid, dst_name, dst_flags)
        elif suffix == "_HEAL":
            self._heal(f, idx, adv, ts, segs, src_guid, src_name, src_flags, dst_guid, dst_flags, spell_name or "?")
        elif suffix == "_INTERRUPT":
            owner = self._owner(src_guid)
            if owner and _is_enemy(src_flags, dst_flags):
                for seg in segs:
                    seg.stats_for(owner, self._pname(owner)).interrupts += 1
        elif suffix in ("_DISPEL", "_STOLEN"):
            owner = self._owner(src_guid)
            if owner:
                for seg in segs:
                    seg.stats_for(owner, self._pname(owner)).dispels += 1
        elif suffix in (
            "_AURA_APPLIED",
            "_AURA_REMOVED",
            "_AURA_APPLIED_DOSE",
            "_AURA_REMOVED_DOSE",
            "_AURA_REFRESH",
            "_AURA_BROKEN",
            "_AURA_BROKEN_SPELL",
            "_ENERGIZE",
            "_DRAIN",
            "_LEECH",
            "_CAST_FAILED",
            "_CREATE",
            "_RESURRECT",
            "_INSTAKILL",
            "_DURABILITY_DAMAGE",
            "_DURABILITY_DAMAGE_ALL",
            "_EXTRA_ATTACKS",
            "_HEAL_ABSORBED",
            "_EMPOWER_START",
            "_EMPOWER_END",
            "_EMPOWER_INTERRUPT",
            "_DISPEL_FAILED",
        ):
            return
        else:
            self.stats.unknown_events[event] += 1

    # -- bloque avanzado --------------------------------------------------------
    def _has_advanced(self, f: list[str], idx: int) -> bool:
        if self.dialect is not None and self.dialect.advanced_enabled is False:
            return False
        return len(f) > idx + 1 and looks_like_guid(f[idx]) and looks_like_guid(f[idx + 1])

    def _advanced_block_size(self) -> int:
        assert self.dialect is not None
        if not self.dialect.advanced_block_calibrated and sum(self.advanced_samples.values()) >= 1:
            size, _ = self.advanced_samples.most_common(1)[0]
            if 10 <= size <= 30:
                self.dialect.advanced_block = size
                self.dialect.advanced_block_calibrated = True
        return self.dialect.advanced_block

    def _track_hp(self, f: list[str], idx: int, info_guid: str) -> None:
        enc = self.encounter
        if enc is None or not info_guid.startswith("Creature-"):
            return
        cur, mx = as_int(f[idx + 2]), as_int(f[idx + 3])
        if mx <= 0:
            return
        pct = round(100.0 * max(cur, 0) / mx, 2)
        prev = enc.creature_hp.get(info_guid)
        enc.creature_hp[info_guid] = (mx, pct if prev is None else min(prev[1], pct))
        if mx >= enc.boss_max_hp:
            enc.boss_max_hp = mx
            enc.boss_guid = info_guid
        if enc.boss_guid is not None:
            enc.boss_min_hp_pct = enc.creature_hp[enc.boss_guid][1]

    # -- eventos especiales -----------------------------------------------------
    def _encounter_start(self, raw: RawLine, ts: datetime) -> None:
        f = raw.fields
        if self.encounter is not None:
            self._close(self.encounter, ts, raw.line_no, complete=False)
            self.encounter = None
        self.encounter = self._open(
            "encounter",
            ts,
            raw.line_no,
            encounter_id=as_int(f[1]),
            encounter_name=as_str(f[2]),
            difficulty_id=as_int(f[3]),
            group_size=as_int(f[4]),
            instance_id=as_int(f[5]) if len(f) > 5 else None,
            zone_name=self.current_zone,
        )

    def _encounter_end(self, raw: RawLine, ts: datetime) -> None:
        f = raw.fields
        enc = self.encounter
        enc_id = as_int(f[1])
        if enc is None or enc.encounter_id != enc_id:
            self._issue("warning", "orphan_end", f"ENCOUNTER_END sin ENCOUNTER_START (id {enc_id}).", raw.line_no)
            return
        enc.success = as_int(f[5]) == 1 if len(f) > 5 else None
        if len(f) > 6:
            enc.reported_duration_ms = as_int(f[6]) or None
        self._close(enc, ts, raw.line_no, complete=True)
        self.encounter = None

    def _zone_change(self, raw: RawLine, ts: datetime) -> None:
        f = raw.fields
        instance_id = as_int(f[1]) if len(f) > 1 else None
        zone_name = as_str(f[2]) if len(f) > 2 else None
        difficulty = as_int(f[3]) if len(f) > 3 else None
        self.current_zone = zone_name
        if self.zone_seg is not None:
            if self.zone_seg.zone_name == zone_name:
                return
            self._close(self.zone_seg, ts, raw.line_no, complete=True)
            self.zone_seg = None
        kind = self.zone_classifier(zone_name)
        if kind == "dungeon":
            self.zone_seg = self._open(
                "dungeon_run", ts, raw.line_no, instance_id=instance_id, zone_name=zone_name, difficulty_id=difficulty
            )
        elif kind == "battleground":
            self.zone_seg = self._open(
                "battleground", ts, raw.line_no, instance_id=instance_id, zone_name=zone_name, difficulty_id=difficulty
            )

    def _combatant_info(self, raw: RawLine) -> None:
        f = raw.fields
        if len(f) < 3 or not _is_player_guid(f[1]):
            return
        unit = self._unit(f[1], None)
        faction = as_int(f[2], -1)
        unit.faction = {0: "horde", 1: "alliance"}.get(faction)
        for idx in (24, 25):
            if len(f) > idx:
                sid = as_int(f[idx], -1)
                if sid in SPEC_IDS:
                    unit.spec_id = sid
                    break
        items = extract_items(f)
        if items is not None:
            unit.gear = items
        if self.encounter is not None:
            self.encounter.roster.add(f[1])
            if items is not None:
                self.encounter.gear[f[1]] = items

    def _unit_died(self, raw: RawLine, ts: datetime, dst_guid: str, dst_name: str | None) -> None:
        f = raw.fields
        if not _is_player_guid(dst_guid):
            return
        unconscious = as_bool(f[10]) if len(f) > 10 else False
        feign = self.feign_cast.get(dst_guid)
        if unconscious or (feign is not None and 0 <= (ts - feign).total_seconds() <= 2.5):
            return
        hit = self.last_hit.get(dst_guid)
        killer_owner = hit[1] if hit and (ts - hit[0]).total_seconds() <= 3 else None
        for seg in self._active():
            ps = seg.stats_for(dst_guid, self._pname(dst_guid) if dst_guid in self.units else dst_name)
            ps.deaths += 1
            rel = seg.rel_ms(ts)
            if ps.first_death_ms is None:
                ps.first_death_ms = rel
            if len(ps.death_log) < 10:
                ps.death_log.append(
                    {
                        "t_ms": rel,
                        "ability": hit[2] if hit else None,
                        "killer": hit[3] if hit else None,
                    }
                )
            if killer_owner and killer_owner != dst_guid:
                seg.stats_for(killer_owner, self._pname(killer_owner)).killing_blows += 1

    # -- daño -------------------------------------------------------------------
    def _damage(
        self,
        f: list[str],
        idx: int,
        adv: bool,
        ts: datetime,
        segs: list[FightResult],
        src_guid: str,
        src_name: str | None,
        src_flags: int,
        dst_guid: str,
        dst_name: str | None,
        dst_flags: int,
        ability: str,
        env: bool = False,
    ) -> None:
        amount = max(0, as_int(f[idx]))
        k = idx + (2 if adv else 1)  # con log avanzado hay baseAmount después de amount
        overkill_raw = as_int(f[k])
        overkill = max(0, overkill_raw)
        absorbed = max(0, as_int(f[k + 4])) if len(f) > k + 4 else 0
        if overkill > amount:
            overkill = amount
        owner = None if env else self._owner(src_guid)
        for seg in segs:
            if seg.kind == "encounter":
                seg.absorbed_on_hits += absorbed

        # Daño recibido por un jugador
        if _is_player_guid(dst_guid):
            self.last_hit[dst_guid] = (ts, owner, ability, src_name)
            for seg in segs:
                ps = seg.stats_for(dst_guid, self._pname(dst_guid))
                ps.damage_taken += amount
                ps.damage_taken_absorbed += absorbed

        if owner is None:
            return
        if not _is_enemy(src_flags, dst_flags):
            return  # fuego amigo o daño a sí mismo: no es daño realizado
        total = amount + absorbed
        if owner == src_guid:  # hechizos lanzados por el propio jugador (no mascotas) ayudan a inferir la clase
            self.units[owner].spell_casts[ability] += 1
        effective = amount - overkill
        to_player = _is_player_guid(dst_guid)
        for seg in segs:
            ps = seg.stats_for(owner, self._pname(owner))
            ps.events += 1
            ps.damage_done += total
            ps.effective_damage += effective
            ps.overkill += overkill
            ps.damage_absorbed_by_target += absorbed
            if to_player:
                ps.damage_to_players += total
            ps.damage_by_ability[ability if owner == src_guid else f"{ability} (mascota)"] += total
            seg.timeline.add(seg.timeline.damage, owner, seg.rel_ms(ts), total)
            if seg.kind == "encounter":
                seg.roster.add(owner)

    def _missed(
        self,
        f: list[str],
        idx: int,
        segs: list[FightResult],
        src_guid: str,
        src_name: str | None,
        src_flags: int,
        dst_guid: str,
        dst_name: str | None,
        dst_flags: int,
    ) -> None:
        miss_type = as_str(f[idx]) if len(f) > idx else None
        if miss_type != "ABSORB":
            return
        amount = max(0, as_int(f[idx + 2])) if len(f) > idx + 2 else 0
        if amount <= 0:
            return
        for seg in segs:
            if seg.kind == "encounter":
                seg.absorbed_on_hits += amount
        if _is_player_guid(dst_guid):
            for seg in segs:
                seg.stats_for(dst_guid, self._pname(dst_guid)).damage_taken_absorbed += amount
        owner = self._owner(src_guid)
        if owner is None or not _is_enemy(src_flags, dst_flags):
            return
        for seg in segs:
            ps = seg.stats_for(owner, self._pname(owner))
            ps.damage_done += amount
            ps.damage_absorbed_by_target += amount
            seg.timeline.add(seg.timeline.damage, owner, seg.rel_ms(self.last_ts or seg.start), amount)

    # -- curación ---------------------------------------------------------------
    def _heal(
        self,
        f: list[str],
        idx: int,
        adv: bool,
        ts: datetime,
        segs: list[FightResult],
        src_guid: str,
        src_name: str | None,
        src_flags: int,
        dst_guid: str,
        dst_flags: int,
        ability: str,
    ) -> None:
        owner = self._owner(src_guid)
        if owner is None or not _same_side(src_flags, dst_flags):
            return
        amount = max(0, as_int(f[idx]))
        k = idx + (2 if adv else 1)
        overheal = max(0, as_int(f[k]))
        heal_absorbed = max(0, as_int(f[k + 1])) if len(f) > k + 1 else 0
        if overheal > amount:
            for seg in segs:
                self._issue(
                    "warning", "overheal_gt_amount", "Overhealing mayor que la curación; se recortó.", None, seg
                )
            overheal = amount
        effective = amount - overheal
        if owner == src_guid:
            self.units[owner].spell_casts[ability] += 1
        for seg in segs:
            ps = seg.stats_for(owner, self._pname(owner))
            ps.events += 1
            ps.healing_gross += amount
            ps.healing_effective += effective
            ps.overhealing += overheal
            ps.heal_absorbed += heal_absorbed
            ps.healing_by_ability[ability if owner == src_guid else f"{ability} (mascota)"] += effective
            seg.timeline.add(seg.timeline.healing, owner, seg.rel_ms(ts), effective)
            if seg.kind == "encounter":
                seg.roster.add(owner)

    # -- absorciones ------------------------------------------------------------
    def _absorbed(self, raw: RawLine, ts: datetime) -> None:
        """SPELL_ABSORBED tiene dos variantes según el golpe absorbido tenga hechizo o sea melee.

        - golpe con hechizo: base(1-8), spellId/nombre/escuela (9-11), lanzador del escudo (12-15),
          hechizo del escudo (16-18), amount (19) [, totalAmount, critical]
        - golpe melee:      base(1-8), lanzador del escudo (9-12), hechizo del escudo (13-15),
          amount (16) [, totalAmount, critical]
        La variante se detecta por el campo 9: GUID → melee; número → hechizo.
        """
        f = raw.fields
        segs = self._active()
        if not segs:
            return
        base = 9 if looks_like_guid(f[9]) else 12
        caster_guid, caster_flags = f[base], as_flag(f[base + 2])
        amount = max(0, as_int(f[base + 7])) if len(f) > base + 7 else 0
        if amount <= 0:
            return
        dst_flags = as_flag(f[7])
        for seg in segs:
            if seg.kind == "encounter":
                seg.absorbed_events_total += amount
        owner = self._owner(caster_guid)
        if owner is None or not _same_side(caster_flags, dst_flags):
            return
        for seg in segs:
            ps = seg.stats_for(owner, self._pname(owner))
            ps.absorbs_provided += amount
            if seg.kind == "encounter":
                seg.roster.add(owner)

    # -- cierre -----------------------------------------------------------------
    def _finish(self) -> ParseResult:
        dialect = self.dialect or dialects.legacy()
        if not self.saw_year and self.stats.parsed_lines:
            self._issue(
                "info", "year_inferred", f"Los timestamps no traen año; se usó {self.default_year} (con cruce de año)."
            )
        if self.timezone_assumed and self.stats.parsed_lines:
            self._issue("warning", "timezone_assumed", "Los timestamps no traen huso horario; se asumió UTC.")
        if dialect.advanced_enabled is False:
            self._issue(
                "warning",
                "advanced_logging_off",
                "Advanced Combat Logging desactivado: sin dueño de mascotas por bloque avanzado ni vida del jefe.",
            )
        if self.stats.non_monotonic:
            self._issue(
                "warning",
                "non_monotonic",
                f"{self.stats.non_monotonic} líneas con timestamps que retroceden más de 2 s.",
            )
        total = max(1, self.stats.total_lines - self.stats.blank_lines)
        ratio = self.stats.error_lines / total
        if ratio > 0.01:
            self._issue(
                "error" if ratio > 0.2 else "warning",
                "parse_error_ratio",
                f"{self.stats.error_lines} de {total} líneas no se pudieron interpretar ({ratio:.1%}).",
            )

        # Clase/spec por jugador con rol estimado sobre todos los encuentros.
        totals: dict[str, list[int]] = {}
        raid_taken = 0
        for fight in self.fights:
            for guid, ps in fight.players.items():
                t = totals.setdefault(guid, [0, 0, 0])
                t[0] += ps.damage_done
                t[1] += ps.healing_effective + ps.absorbs_provided
                t[2] += ps.damage_taken
                raid_taken += ps.damage_taken
        for guid, unit in self.units.items():
            if not _is_player_guid(guid):
                continue
            dmg, heal, taken = totals.get(guid, [0, 0, 0])
            healing_share = heal / (dmg + heal) if (dmg + heal) else 0.0
            taken_share = taken / raid_taken if raid_taken else 0.0
            role_hint = role_for(None, None, healing_share, taken_share)
            unit.guess = infer_class_spec(unit.spell_casts, unit.spec_id, role_hint)

        return ParseResult(
            parser_version=PARSER_VERSION,
            dialect=dialect,
            stats=self.stats,
            issues=self.issues,
            fights=self.fights,
            units=self.units,
            started_at=self.first_ts,
            ended_at=self.last_ts,
            timezone_assumed=self.timezone_assumed,
        )


def parse_lines(
    lines: Iterable[str],
    *,
    default_year: int | None = None,
    fallback_utc_offset: int | None = None,
    zone_classifier: Callable[[str | None], str | None] = classify_zone,
) -> ParseResult:
    parser = CombatLogParser(
        default_year=default_year or datetime.now(UTC).year,
        fallback_utc_offset=fallback_utc_offset,
        zone_classifier=zone_classifier,
    )
    return parser.feed(lines)


def parse_text(text: str, **kwargs: object) -> ParseResult:
    return parse_lines(text.splitlines(), **kwargs)  # type: ignore[arg-type]
