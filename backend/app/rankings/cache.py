"""Caché de rankings (tabla ``ranking_entries``) con actualización incremental.

Sólo se reconstruyen las filas del reporte o personaje afectado; cada cambio incrementa
``ranking_versions.version`` del dataset, que invalida la caché de respuestas en memoria.
"""

from __future__ import annotations

import threading
import time
from typing import Any

from sqlalchemy import and_, delete, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import Character, Fight, FightParticipant, Instance, RankingEntry, RankingVersion, Report

PVP_VERIFIED = ("official", "verified_by_admin")


def bump_version(db: Session, dataset: str) -> None:
    stmt = pg_insert(RankingVersion).values(dataset=dataset, version=1)
    stmt = stmt.on_conflict_do_update(
        index_elements=[RankingVersion.dataset],
        set_={"version": RankingVersion.version + 1, "updated_at": func.now()},
    )
    db.execute(stmt)


def current_version(db: Session, dataset: str) -> int:
    return int(db.scalar(select(RankingVersion.version).where(RankingVersion.dataset == dataset)) or 0)


def _eligible_select(extra_where: Any) -> Any:
    """SELECT de las filas rankeables con las columnas en el orden de ``_COLUMNS``."""
    return (
        select(
            Fight.kind,
            Fight.dataset,
            Fight.id,
            Fight.report_id,
            FightParticipant.character_id,
            Fight.encounter_id,
            Fight.instance_id,
            Fight.season_id,
            Fight.difficulty_id,
            Fight.group_size,
            FightParticipant.class_slug,
            FightParticipant.spec,
            FightParticipant.role,
            Fight.start_at,
            Fight.duration_ms,
            FightParticipant.dps,
            FightParticipant.hps,
            FightParticipant.aps,
            FightParticipant.dtps,
            FightParticipant.damage_done,
            FightParticipant.healing_effective,
            FightParticipant.absorbs_provided,
            FightParticipant.damage_taken,
            FightParticipant.damage_to_players,
            FightParticipant.killing_blows,
            FightParticipant.deaths,
            FightParticipant.interrupts,
            FightParticipant.dispels,
            FightParticipant.survival_pct,
        )
        .join(FightParticipant, FightParticipant.fight_id == Fight.id)
        .join(Report, Report.id == Fight.report_id)
        .join(Character, Character.id == FightParticipant.character_id)
        .outerjoin(Instance, Instance.id == Fight.instance_id)
        .where(
            Fight.rankable.is_(True),
            Fight.excluded_by_admin.is_(False),
            Fight.duplicate_of_id.is_(None),
            Report.status == "processed",
            Report.visibility == "public",
            Report.deleted_at.is_(None),
            Character.hidden.is_(False),
            (
                and_(Fight.kind == "encounter", Fight.success.is_(True))
                | and_(Fight.kind == "battleground", Instance.verification.in_(PVP_VERIFIED))
            ),
            extra_where,
        )
    )


_COLUMNS = [
    "kind", "dataset", "fight_id", "report_id", "character_id", "encounter_id", "instance_id", "season_id",
    "difficulty_id", "group_size", "class_slug", "spec", "role", "occurred_at", "duration_ms", "dps", "hps", "aps",
    "dtps", "damage_done", "healing_effective", "absorbs_provided", "damage_taken", "damage_to_players",
    "killing_blows", "deaths", "interrupts", "dispels", "survival_pct",
]  # fmt: skip


def _insert_from(db: Session, extra_where: Any) -> int:
    rows = db.execute(_eligible_select(extra_where)).all()
    if not rows:
        return 0
    payload = []
    for r in rows:
        values = dict(zip(_COLUMNS, r, strict=True))
        values["kind"] = "pvp" if values["kind"] == "battleground" else "pve"  # Fight.kind → tipo de ranking
        payload.append(values)
    db.execute(insert(RankingEntry), payload)
    return len(payload)


def rebuild_for_report(db: Session, report: Report) -> int:
    db.execute(delete(RankingEntry).where(RankingEntry.report_id == report.id))
    n = _insert_from(db, Fight.report_id == report.id)
    bump_version(db, report.dataset)
    return n


def rebuild_for_character(db: Session, character: Character) -> int:
    db.execute(delete(RankingEntry).where(RankingEntry.character_id == character.id))
    n = _insert_from(db, FightParticipant.character_id == character.id)
    bump_version(db, character.dataset)
    return n


def rebuild_for_fight(db: Session, fight: Fight) -> int:
    db.execute(delete(RankingEntry).where(RankingEntry.fight_id == fight.id))
    n = _insert_from(db, Fight.id == fight.id)
    bump_version(db, fight.dataset)
    return n


def rebuild_all(db: Session, dataset: str) -> int:
    db.execute(delete(RankingEntry).where(RankingEntry.dataset == dataset))
    n = _insert_from(db, Fight.dataset == dataset)
    bump_version(db, dataset)
    return n


def sync_participant_classes(db: Session, character: Character) -> None:
    """Propaga una corrección de clase/spec del personaje a sus participaciones."""
    db.execute(
        update(FightParticipant)
        .where(FightParticipant.character_id == character.id)
        .values(class_slug=character.class_slug, spec=character.spec)
    )


# ---------------------------------------------------------------------------
# Caché de respuestas en memoria, invalidada por versión
# ---------------------------------------------------------------------------


class ResponseCache:
    def __init__(self, max_items: int = 512) -> None:
        self._data: dict[tuple[Any, ...], tuple[float, int, Any]] = {}
        self._lock = threading.Lock()
        self.max_items = max_items

    def get(self, key: tuple[Any, ...], version: int, ttl: float) -> Any | None:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            created, ver, value = item
            if ver != version or time.monotonic() - created > ttl:
                self._data.pop(key, None)
                return None
            return value

    def set(self, key: tuple[Any, ...], version: int, value: Any) -> None:
        with self._lock:
            if len(self._data) >= self.max_items:
                oldest = min(self._data.items(), key=lambda kv: kv[1][0])[0]
                self._data.pop(oldest, None)
            self._data[key] = (time.monotonic(), version, value)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


response_cache = ResponseCache()
