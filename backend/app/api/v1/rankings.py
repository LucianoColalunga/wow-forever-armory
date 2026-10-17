from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from app.api.deps import DB, Dataset, Page, SettingsDep
from app.catalog.forever import PVP_MODES
from app.core import ratelimit
from app.models import Encounter, Instance, RankingEntry
from app.rankings import methods
from app.rankings.cache import current_version, response_cache
from app.services.queries import data_meta, encounter_dict, instance_dict

router = APIRouter(prefix="/rankings", tags=["rankings"], dependencies=[Depends(ratelimit.public_limit)])

Method = Literal["peak", "consistency", "percentile"]
Role = Literal["dps", "healer", "tank"]


def _resolve_instance(db: DB, ref: str | None, kinds: tuple[str, ...]) -> Instance | None:
    if not ref:
        return None
    inst = db.get(Instance, int(ref)) if ref.isdigit() else db.scalar(select(Instance).where(Instance.slug == ref))
    if inst is None or inst.kind not in kinds:
        raise HTTPException(404, "Instancia inexistente para este ranking.")
    return inst


def _period(season_id: int | None, date_from: datetime | None, date_to: datetime | None) -> dict[str, Any]:
    return {"season_id": season_id, "date_from": date_from, "date_to": date_to}


def _cached(db: DB, settings: SettingsDep, dataset: str, key: tuple[Any, ...], build: Any) -> dict[str, Any]:
    version = current_version(db, dataset)
    hit = response_cache.get(key, version, settings.ranking_cache_seconds)
    if hit is not None:
        return {**hit, "cache": "hit"}
    value = build()
    response_cache.set(key, version, value)
    return {**value, "cache": "miss"}


@router.get("/pve", summary="Ranking general PvE (métodos A/B/C normalizados)")
def ranking_pve(
    db: DB,
    settings: SettingsDep,
    page: Page,
    dataset: Dataset = "real",
    metric: Literal[
        "dps",
        "hps",
        "aps",
        "damage_done",
        "healing_effective",
        "absorbs_provided",
        "interrupts",
        "dispels",
        "survival_pct",
    ] = "dps",
    method: Method = "percentile",
    instance: Annotated[str | None, Query(description="id o slug de banda/mazmorra")] = None,
    difficulty_id: int | None = None,
    group_size: int | None = None,
    class_slug: Annotated[str | None, Query(alias="class", max_length=16)] = None,
    spec: Annotated[str | None, Query(max_length=24)] = None,
    role: Role | None = None,
    season_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[str, Any]:
    pg, size = page
    inst = _resolve_instance(db, instance, ("raid", "dungeon"))
    f = methods.Filters(
        dataset=dataset,
        kind="pve",
        instance_id=inst.id if inst else None,
        difficulty_id=difficulty_id,
        group_size=group_size,
        class_slug=class_slug,
        spec=spec,
        role=role,
        season_id=season_id,
        date_from=date_from,
        date_to=date_to,
    )
    key = (
        "pve",
        dataset,
        metric,
        method,
        f.instance_id,
        difficulty_id,
        group_size,
        class_slug,
        spec,
        role,
        season_id,
        date_from,
        date_to,
        pg,
        size,
    )

    def build() -> dict[str, Any]:
        res = methods.general_ranking(
            db,
            f,
            metric,
            method,
            page=pg,
            page_size=size,
            min_bucket=settings.min_bucket_size,
            min_kills=settings.consistency_min_kills,
        )
        res["meta"].update(
            {
                "method": method,
                "method_label": methods.METHODS[method]["label"],
                "method_description": methods.METHODS[method]["general"],
                "metric": metric,
                "metric_label": methods.METRICS[metric]["label"],
                "scale": "índice" if method != "percentile" else "percentil (0–100)",
                "min_bucket_size": settings.min_bucket_size,
                "consistency_min_kills": settings.consistency_min_kills,
                "instance": instance_dict(inst),
                **_period(season_id, date_from, date_to),
            }
        )
        return {**res, "page": pg, "page_size": size, "data": data_meta(db, dataset)}

    return _cached(db, settings, dataset, key, build)


@router.get("/pve/bosses/{boss_id}", summary="Ranking por jefe (una dificultad y tamaño de grupo)")
def ranking_boss(
    boss_id: int,
    db: DB,
    settings: SettingsDep,
    page: Page,
    dataset: Dataset = "real",
    metric: Literal[
        "dps",
        "hps",
        "aps",
        "damage_done",
        "healing_effective",
        "absorbs_provided",
        "damage_taken",
        "dtps",
        "deaths",
        "survival_pct",
        "interrupts",
        "dispels",
    ] = "dps",
    method: Method = "peak",
    difficulty_id: int | None = None,
    group_size: int | None = None,
    class_slug: Annotated[str | None, Query(alias="class", max_length=16)] = None,
    spec: Annotated[str | None, Query(max_length=24)] = None,
    role: Role | None = None,
    season_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[str, Any]:
    pg, size = page
    enc = db.get(Encounter, boss_id)
    if enc is None or enc.dataset != dataset:
        raise HTTPException(404, "Jefe inexistente en este conjunto de datos.")
    parts = db.execute(
        select(
            RankingEntry.difficulty_id,
            RankingEntry.group_size,
            func.count(),
            func.count(func.distinct(RankingEntry.fight_id)),
        )
        .where(RankingEntry.encounter_id == enc.id, RankingEntry.kind == "pve")
        .group_by(RankingEntry.difficulty_id, RankingEntry.group_size)
        .order_by(func.count().desc())
    ).all()
    partitions = [{"difficulty_id": d, "group_size": g, "entries": n, "kills": k} for d, g, n, k in parts]
    if (difficulty_id is None or group_size is None) and partitions:
        difficulty_id = difficulty_id if difficulty_id is not None else partitions[0]["difficulty_id"]
        group_size = group_size if group_size is not None else partitions[0]["group_size"]
    f = methods.Filters(
        dataset=dataset,
        kind="pve",
        encounter_id=enc.id,
        difficulty_id=difficulty_id,
        group_size=group_size,
        class_slug=class_slug,
        spec=spec,
        role=role,
        season_id=season_id,
        date_from=date_from,
        date_to=date_to,
    )
    key = (
        "boss",
        dataset,
        enc.id,
        metric,
        method,
        difficulty_id,
        group_size,
        class_slug,
        spec,
        role,
        season_id,
        date_from,
        date_to,
        pg,
        size,
    )

    def build() -> dict[str, Any]:
        res = methods.partition_ranking(
            db,
            f,
            metric,
            method,
            page=pg,
            page_size=size,
            min_bucket=settings.min_bucket_size,
            min_kills=settings.consistency_min_kills,
            last_n=settings.consistency_last_n,
        )
        # Distribución de valores (histograma) para el gráfico, sobre todos los kills de la partición.
        col = methods.METRICS[metric]["column"]
        values = [v for (v,) in db.execute(select(col).where(*methods._where(f))).all() if v is not None]
        res["meta"].update(
            {
                "method": method,
                "method_label": methods.METHODS[method]["label"],
                "method_description": methods.METHODS[method]["partition"],
                "metric": metric,
                "metric_label": methods.METRICS[metric]["label"],
                "difficulty_id": difficulty_id,
                "group_size": group_size,
                "min_bucket_size": settings.min_bucket_size,
                "consistency_min_kills": settings.consistency_min_kills,
                "consistency_last_n": settings.consistency_last_n,
                **_period(season_id, date_from, date_to),
            }
        )
        return {
            **res,
            "page": pg,
            "page_size": size,
            "encounter": encounter_dict(enc),
            "instance": instance_dict(enc.instance),
            "partitions": partitions,
            "distribution": _histogram(values),
            "data": data_meta(db, dataset),
        }

    return _cached(db, settings, dataset, key, build)


@router.get("/pvp", summary="Ranking PvP (sólo modalidades confirmadas en Forever)")
def ranking_pvp(
    db: DB,
    settings: SettingsDep,
    page: Page,
    dataset: Dataset = "real",
    metric: Literal[
        "dps", "damage_to_players", "hps", "healing_effective", "killing_blows", "deaths"
    ] = "damage_to_players",
    method: Literal["peak", "consistency"] = "peak",
    battleground: Annotated[str | None, Query(description="id o slug del campo de batalla")] = None,
    class_slug: Annotated[str | None, Query(alias="class", max_length=16)] = None,
    spec: Annotated[str | None, Query(max_length=24)] = None,
    faction: Literal["alliance", "horde"] | None = None,
    q: Annotated[
        str | None, Query(min_length=2, max_length=24, description="Buscar por nombre (conserva la posición real)")
    ] = None,
    season_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[str, Any]:
    pg, size = page
    name_query = q.strip() if q and q.strip() else None
    verified = db.scalars(
        select(Instance)
        .where(Instance.kind == "battleground", Instance.verification.in_(("official", "verified_by_admin")))
        .order_by(Instance.name)
    ).all()
    inst = (
        _resolve_instance(db, battleground, ("battleground",)) if battleground else (verified[0] if verified else None)
    )
    if inst is not None and inst.verification not in ("official", "verified_by_admin"):
        raise HTTPException(404, "Ese campo de batalla no está confirmado para Forever.")
    f = methods.Filters(
        dataset=dataset,
        kind="pvp",
        instance_id=inst.id if inst else -1,
        class_slug=class_slug,
        spec=spec,
        season_id=season_id,
        date_from=date_from,
        date_to=date_to,
        faction=faction,
        name_query=name_query,
    )
    key = (
        "pvp",
        dataset,
        metric,
        method,
        f.instance_id,
        class_slug,
        spec,
        faction,
        (name_query or "").lower(),
        season_id,
        date_from,
        date_to,
        pg,
        size,
    )

    def build() -> dict[str, Any]:
        res = methods.partition_ranking(
            db,
            f,
            metric,
            method,
            page=pg,
            page_size=size,
            min_bucket=settings.min_bucket_size,
            min_kills=settings.consistency_min_kills,
            last_n=settings.consistency_last_n,
        )
        res["meta"].update(
            {
                "method": method,
                "method_label": methods.METHODS[method]["label"],
                "method_description": methods.METHODS[method]["partition"],
                "metric": metric,
                "metric_label": methods.METRICS[metric]["label"],
                **_period(season_id, date_from, date_to),
                "partial_data_note": "Los combat logs en campos de batalla sólo registran eventos cercanos a quien "
                "graba: las cifras son parciales y no hay rating oficial.",
            }
        )
        return {
            **res,
            "page": pg,
            "page_size": size,
            "battleground": instance_dict(inst),
            "battlegrounds": [instance_dict(i) for i in verified],
            "summary": methods.spec_summary(db, f, metric),
            "modes": list(PVP_MODES),
            "data": data_meta(db, dataset),
        }

    return _cached(db, settings, dataset, key, build)


def _histogram(values: list[float], bins: int = 20) -> dict[str, Any]:
    if not values:
        return {"bins": [], "count": 0}
    lo, hi = min(values), max(values)
    if hi == lo:
        return {"bins": [{"from": lo, "to": hi, "count": len(values)}], "count": len(values)}
    width = (hi - lo) / bins
    counts = [0] * bins
    for v in values:
        counts[min(int((v - lo) / width), bins - 1)] += 1
    return {
        "bins": [{"from": lo + i * width, "to": lo + (i + 1) * width, "count": c} for i, c in enumerate(counts)],
        "count": len(values),
    }
