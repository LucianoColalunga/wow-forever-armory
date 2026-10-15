"""Bandas, mazmorras, campos de batalla, jefes e historial de combates."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from app.api.deps import DB, Dataset, Page
from app.core import ratelimit
from app.models import Encounter, Fight, Instance, Report
from app.schemas import FightDetail
from app.services.queries import (
    count_of,
    data_meta,
    encounter_dict,
    fight_detail,
    fight_summary,
    instance_dict,
    paged,
    visible_fight_query,
    visible_report,
)

router = APIRouter(tags=["content"], dependencies=[Depends(ratelimit.public_limit)])


def _instance(db: DB, ref: str, kind: str) -> Instance:
    inst = db.get(Instance, int(ref)) if ref.isdigit() else db.scalar(select(Instance).where(Instance.slug == ref))
    if inst is None or inst.kind != kind:
        raise HTTPException(404, "Instancia inexistente.")
    return inst


def _instance_payload(db: DB, inst: Instance, dataset: str) -> dict[str, Any]:
    vis = [Fight.dataset == dataset, Fight.duplicate_of_id.is_(None), *visible_report()]
    encounters = db.scalars(
        select(Encounter)
        .where(Encounter.instance_id == inst.id, Encounter.dataset == dataset)
        .order_by(Encounter.game_encounter_id)
    ).all()
    stats = {
        r[0]: r
        for r in db.execute(
            select(
                Fight.encounter_id,
                func.count(),
                func.count().filter(Fight.success.is_(True)),
                func.min(Fight.duration_ms),
                func.max(Fight.start_at),
            )
            .join(Report, Report.id == Fight.report_id)
            .where(*vis, Fight.kind == "encounter", Fight.encounter_id.in_([e.id for e in encounters] or [-1]))
            .group_by(Fight.encounter_id)
        ).all()
    }
    fastest = {
        r[0]: r[1]
        for r in db.execute(
            select(Fight.encounter_id, func.min(Fight.duration_ms))
            .join(Report, Report.id == Fight.report_id)
            .where(*vis, Fight.kind == "encounter", Fight.success.is_(True))
            .group_by(Fight.encounter_id)
        ).all()
    }
    bosses = []
    for e in encounters:
        s = stats.get(e.id)
        bosses.append(
            {
                **(encounter_dict(e) or {}),
                "pulls": int(s[1]) if s else 0,
                "kills": int(s[2] or 0) if s else 0,
                "fastest_kill_ms": fastest.get(e.id),
                "last_seen_at": s[4] if s else None,
            }
        )
    recent = db.scalars(
        visible_fight_query(dataset).where(Fight.instance_id == inst.id).order_by(Fight.start_at.desc()).limit(10)
    ).all()
    return {
        "instance": instance_dict(inst),
        "bosses": bosses,
        "recent_fights": [fight_summary(f) for f in recent],
        "meta": data_meta(db, dataset),
    }


@router.get("/raids", summary="Bandas del catálogo")
def raids(db: DB) -> list[dict[str, Any] | None]:
    return [
        instance_dict(i)
        for i in db.scalars(
            select(Instance).where(Instance.kind == "raid").order_by(Instance.max_players, Instance.name)
        )
    ]


@router.get("/raids/{raid_id}", summary="Detalle de banda: jefes, kills y combates recientes")
def raid(raid_id: str, db: DB, dataset: Dataset = "real") -> dict[str, Any]:
    return _instance_payload(db, _instance(db, raid_id, "raid"), dataset)


@router.get("/dungeons", summary="Mazmorras del catálogo")
def dungeons(db: DB) -> list[dict[str, Any] | None]:
    return [
        instance_dict(i)
        for i in db.scalars(
            select(Instance).where(Instance.kind == "dungeon").order_by(Instance.is_new.desc(), Instance.name)
        )
    ]


@router.get("/dungeons/{dungeon_id}", summary="Detalle de mazmorra: jefes y recorridos registrados")
def dungeon(dungeon_id: str, db: DB, dataset: Dataset = "real") -> dict[str, Any]:
    inst = _instance(db, dungeon_id, "dungeon")
    payload = _instance_payload(db, inst, dataset)
    runs = db.scalars(
        visible_fight_query(dataset)
        .where(Fight.instance_id == inst.id, Fight.kind == "dungeon_run")
        .order_by(Fight.start_at.desc())
        .limit(20)
    ).all()
    payload["runs"] = [fight_summary(f) for f in runs]
    payload["runs_note"] = (
        "Los recorridos se muestran como historial: no se rankean tiempos porque Blizzard no "
        "publicó criterios de finalización ni anunció Mythic+ para Forever."
    )
    return payload


@router.get("/battlegrounds", summary="Campos de batalla y su estado de verificación")
def battlegrounds(db: DB) -> list[dict[str, Any] | None]:
    return [
        instance_dict(i)
        for i in db.scalars(
            select(Instance).where(Instance.kind == "battleground").order_by(Instance.verification, Instance.name)
        )
    ]


@router.get("/bosses/{boss_id}", summary="Jefe: particiones (dificultad × tamaño) y estadísticas")
def boss(boss_id: int, db: DB, dataset: Dataset = "real") -> dict[str, Any]:
    enc = db.get(Encounter, boss_id)
    if enc is None or enc.dataset != dataset:
        raise HTTPException(404, "Jefe inexistente en este conjunto de datos.")
    vis = [Fight.dataset == dataset, Fight.duplicate_of_id.is_(None), *visible_report()]
    parts = db.execute(
        select(
            Fight.difficulty_id,
            Fight.group_size,
            func.count(),
            func.count().filter(Fight.success.is_(True)),
            func.min(Fight.duration_ms).filter(Fight.success.is_(True)),
            func.avg(Fight.duration_ms).filter(Fight.success.is_(True)),
            func.min(Fight.boss_min_hp_pct),
        )
        .join(Report, Report.id == Fight.report_id)
        .where(*vis, Fight.encounter_id == enc.id)
        .group_by(Fight.difficulty_id, Fight.group_size)
    ).all()
    return {
        "encounter": encounter_dict(enc),
        "instance": instance_dict(enc.instance),
        "partitions": [
            {
                "difficulty_id": d,
                "group_size": g,
                "pulls": n,
                "kills": int(k or 0),
                "fastest_kill_ms": fk,
                "avg_kill_ms": ak,
                "best_wipe_hp_pct": hp,
            }
            for d, g, n, k, fk, ak, hp in parts
        ],
        "meta": data_meta(db, dataset),
    }


@router.get("/encounters", summary="Historial de combates con filtros")
def encounters(
    db: DB,
    page: Page,
    dataset: Dataset = "real",
    kind: Literal["encounter", "battleground", "dungeon_run"] | None = None,
    instance: Annotated[str | None, Query(description="id o slug")] = None,
    boss_id: int | None = None,
    difficulty_id: int | None = None,
    group_size: int | None = None,
    success: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    include_duplicates: bool = False,
    sort: Literal["recent", "oldest", "duration"] = "recent",
) -> dict[str, Any]:
    pg, size = page
    q = visible_fight_query(dataset, include_duplicates=include_duplicates)
    if kind:
        q = q.where(Fight.kind == kind)
    if instance:
        inst = (
            db.get(Instance, int(instance))
            if instance.isdigit()
            else db.scalar(select(Instance).where(Instance.slug == instance))
        )
        q = q.where(Fight.instance_id == (inst.id if inst else -1))
    if boss_id:
        q = q.where(Fight.encounter_id == boss_id)
    if difficulty_id is not None:
        q = q.where(Fight.difficulty_id == difficulty_id)
    if group_size is not None:
        q = q.where(Fight.group_size == group_size)
    if success is not None:
        q = q.where(Fight.success.is_(success))
    if date_from:
        q = q.where(Fight.start_at >= date_from)
    if date_to:
        q = q.where(Fight.start_at < date_to)
    total = count_of(db, q)
    orders: dict[str, list[Any]] = {
        "recent": [Fight.start_at.desc()],
        "oldest": [Fight.start_at.asc()],
        "duration": [Fight.duration_ms.asc()],
    }
    order = orders[sort]
    rows = db.scalars(q.order_by(*order, Fight.id).limit(size).offset((pg - 1) * size)).all()
    return paged([fight_summary(f) for f in rows], pg, size, total, data_meta(db, dataset))


@router.get("/encounters/{fight_id}", response_model=FightDetail, summary="Detalle de un combate registrado")
def encounter_detail(fight_id: int, db: DB, dataset: Dataset = "real") -> dict[str, Any]:
    f = db.scalar(visible_fight_query(dataset, include_duplicates=True).where(Fight.id == fight_id))
    if f is None:
        raise HTTPException(404, "Combate inexistente en este conjunto de datos.")
    return fight_detail(db, f)
