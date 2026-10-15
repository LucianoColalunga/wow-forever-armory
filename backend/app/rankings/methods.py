"""Métodos de ranking (documentados en docs/METHODOLOGY.md).

Ranking por partición (un jefe, una dificultad y un tamaño de grupo):
  A · pico          mejor valor de cada personaje.
  B · consistencia  mediana de sus últimos N kills (mínimo ``consistency_min_kills``).
  C · percentil     percent_rank dentro de (encuentro, dificultad, tamaño, clase, spec);
                     sólo cubetas con ``min_bucket_size`` registros o más. Se toma el mejor.

Ranking general (varios jefes): nunca compara DPS bruto entre encuentros.
  A · pico normalizado         promedio, por encuentro, del mejor índice 100·valor/mediana del encuentro.
  B · consistencia normalizada mediana del índice sobre todos sus kills (mínimo de kills).
  C · percentil normalizado    promedio, por encuentro, del mejor percentil por clase/spec.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Float, and_, cast, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import ColumnElement

from app.models import Character, Guild, RankingEntry

METRICS: dict[str, dict[str, Any]] = {
    "dps": {"label": "DPS", "column": RankingEntry.dps, "higher_better": True, "unit": "por segundo"},
    "hps": {"label": "HPS efectivo", "column": RankingEntry.hps, "higher_better": True, "unit": "por segundo"},
    "aps": {
        "label": "Absorciones por segundo",
        "column": RankingEntry.aps,
        "higher_better": True,
        "unit": "por segundo",
    },
    "damage_done": {"label": "Daño total", "column": RankingEntry.damage_done, "higher_better": True, "unit": "total"},
    "healing_effective": {
        "label": "Curación efectiva total",
        "column": RankingEntry.healing_effective,
        "higher_better": True,
        "unit": "total",
    },
    "absorbs_provided": {
        "label": "Absorciones totales",
        "column": RankingEntry.absorbs_provided,
        "higher_better": True,
        "unit": "total",
    },
    "damage_taken": {
        "label": "Daño recibido",
        "column": RankingEntry.damage_taken,
        "higher_better": False,
        "unit": "total",
    },
    "dtps": {
        "label": "Daño recibido por segundo",
        "column": RankingEntry.dtps,
        "higher_better": False,
        "unit": "por segundo",
    },
    "deaths": {"label": "Muertes", "column": RankingEntry.deaths, "higher_better": False, "unit": "cantidad"},
    "survival_pct": {
        "label": "Supervivencia",
        "column": RankingEntry.survival_pct,
        "higher_better": True,
        "unit": "% del combate con vida",
    },
    "interrupts": {
        "label": "Interrupciones",
        "column": RankingEntry.interrupts,
        "higher_better": True,
        "unit": "cantidad",
    },
    "dispels": {"label": "Dispels", "column": RankingEntry.dispels, "higher_better": True, "unit": "cantidad"},
    "damage_to_players": {
        "label": "Daño a jugadores",
        "column": RankingEntry.damage_to_players,
        "higher_better": True,
        "unit": "total",
        "pvp_only": True,
    },
    "killing_blows": {
        "label": "Golpes de gracia",
        "column": RankingEntry.killing_blows,
        "higher_better": True,
        "unit": "cantidad",
        "pvp_only": True,
    },
}

GENERAL_METRICS = (
    "dps",
    "hps",
    "aps",
    "damage_done",
    "healing_effective",
    "absorbs_provided",
    "interrupts",
    "dispels",
    "survival_pct",
)
PVP_METRICS = ("dps", "damage_to_players", "hps", "healing_effective", "killing_blows", "deaths")

METHODS = {
    "peak": {
        "label": "A · Pico",
        "partition": "Mejor valor de cada personaje en el período.",
        "general": "Promedio, sobre los encuentros jugados, del mejor índice normalizado "
        "(100 × valor / mediana del encuentro, dificultad y tamaño).",
    },
    "consistency": {
        "label": "B · Consistencia",
        "partition": "Mediana de los últimos N kills del personaje (mínimo configurable).",
        "general": "Mediana del índice normalizado (100 × valor / mediana del encuentro) sobre todos sus kills.",
    },
    "percentile": {
        "label": "C · Percentil",
        "partition": "Mejor percentil dentro de la misma clase y spec en el mismo encuentro, dificultad y "
        "tamaño; sólo cubetas con la muestra mínima.",
        "general": "Promedio, sobre los encuentros jugados, del mejor percentil por clase y spec "
        "(cubetas con muestra mínima).",
    },
}


@dataclass(slots=True)
class Filters:
    dataset: str
    kind: str = "pve"
    encounter_id: int | None = None
    instance_id: int | None = None
    encounter_ids: list[int] | None = None
    difficulty_id: int | None = None
    group_size: int | None = None
    class_slug: str | None = None
    spec: str | None = None
    role: str | None = None
    season_id: int | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


def _where(f: Filters, include_class: bool = True) -> list[ColumnElement[bool]]:
    w: list[ColumnElement[bool]] = [RankingEntry.dataset == f.dataset, RankingEntry.kind == f.kind]
    if f.encounter_id is not None:
        w.append(RankingEntry.encounter_id == f.encounter_id)
    if f.encounter_ids is not None:
        w.append(RankingEntry.encounter_id.in_(f.encounter_ids or [-1]))
    if f.instance_id is not None:
        w.append(RankingEntry.instance_id == f.instance_id)
    if f.difficulty_id is not None:
        w.append(RankingEntry.difficulty_id == f.difficulty_id)
    if f.group_size is not None:
        w.append(RankingEntry.group_size == f.group_size)
    if f.season_id is not None:
        w.append(RankingEntry.season_id == f.season_id)
    if f.date_from is not None:
        w.append(RankingEntry.occurred_at >= f.date_from)
    if f.date_to is not None:
        w.append(RankingEntry.occurred_at < f.date_to)
    if include_class:
        if f.class_slug:
            w.append(RankingEntry.class_slug == f.class_slug)
        if f.spec:
            w.append(RankingEntry.spec == f.spec)
        if f.role:
            w.append(RankingEntry.role == f.role)
    return w


def _class_filters(cte: Any, f: Filters) -> list[ColumnElement[bool]]:
    w: list[ColumnElement[bool]] = []
    if f.class_slug:
        w.append(cte.c.class_slug == f.class_slug)
    if f.spec:
        w.append(cte.c.spec == f.spec)
    if f.role:
        w.append(cte.c.role == f.role)
    return w


def _character_cols() -> list[Any]:
    return [
        Character.id.label("character_id"),
        Character.name,
        Character.realm,
        Character.region,
        Character.class_slug.label("character_class"),
        Character.spec.label("character_spec"),
        Character.dataset,
        Guild.id.label("guild_id"),
        Guild.name.label("guild_name"),
    ]


def _meta(db: Session, used_q: Any) -> dict[str, Any]:
    sub = used_q.subquery()
    row = db.execute(
        select(
            func.count(),
            func.min(sub.c.occurred_at),
            func.max(sub.c.occurred_at),
            func.count(func.distinct(sub.c.character_id)),
        )
    ).one()
    return {"records_used": int(row[0]), "period_from": row[1], "period_to": row[2], "characters": int(row[3])}


# ---------------------------------------------------------------------------
# Ranking por partición
# ---------------------------------------------------------------------------


def partition_ranking(
    db: Session,
    f: Filters,
    metric: str,
    method: str,
    *,
    page: int,
    page_size: int,
    min_bucket: int,
    min_kills: int,
    last_n: int,
) -> dict[str, Any]:
    spec = METRICS[metric]
    col = spec["column"]
    hb: bool = spec["higher_better"]

    base = select(RankingEntry, cast(col, Float).label("value")).where(*_where(f, include_class=method != "percentile"))
    base_cte = base.cte("base")
    excluded = 0

    if method == "peak":
        ranked = select(
            base_cte,
            func.row_number()
            .over(
                partition_by=base_cte.c.character_id,
                order_by=[(base_cte.c.value.desc() if hb else base_cte.c.value.asc()), base_cte.c.occurred_at.asc()],
            )
            .label("rn"),
            func.count().over(partition_by=base_cte.c.character_id).label("samples"),
        ).cte("ranked")
        best = select(ranked).where(ranked.c.rn == 1).cte("best")
        q = (
            select(
                best.c.value,
                best.c.samples,
                best.c.fight_id,
                best.c.report_id,
                best.c.occurred_at,
                best.c.class_slug,
                best.c.spec,
                best.c.role,
                best.c.duration_ms,
                *_character_cols(),
            )
            .join(Character, Character.id == best.c.character_id)
            .outerjoin(Guild, Guild.id == Character.guild_id)
        )
        used_q = select(base_cte.c.occurred_at, base_cte.c.character_id)
    elif method == "consistency":
        recent = select(
            base_cte,
            func.row_number()
            .over(partition_by=base_cte.c.character_id, order_by=base_cte.c.occurred_at.desc())
            .label("recent"),
        ).cte("recent")
        window = select(recent).where(recent.c.recent <= last_n).cte("window")
        agg = (
            select(
                window.c.character_id,
                func.percentile_cont(0.5).within_group(window.c.value).label("value"),
                func.count().label("samples"),
                func.coalesce(func.stddev_samp(window.c.value), 0).label("stddev"),
                func.max(window.c.occurred_at).label("occurred_at"),
                func.max(window.c.fight_id).label("fight_id"),
                func.max(window.c.report_id).label("report_id"),
                func.max(window.c.class_slug).label("class_slug"),
                func.max(window.c.spec).label("spec"),
                func.max(window.c.role).label("role"),
            )
            .group_by(window.c.character_id)
            .having(func.count() >= min_kills)
            .cte("agg")
        )
        q = (
            select(
                agg.c.value,
                agg.c.samples,
                agg.c.stddev,
                agg.c.fight_id,
                agg.c.report_id,
                agg.c.occurred_at,
                agg.c.class_slug,
                agg.c.spec,
                agg.c.role,
                *_character_cols(),
            )
            .join(Character, Character.id == agg.c.character_id)
            .outerjoin(Guild, Guild.id == Character.guild_id)
        )
        used_q = select(window.c.occurred_at, window.c.character_id).where(
            window.c.character_id.in_(select(agg.c.character_id))
        )
        excluded = int(
            db.scalar(
                select(func.count()).select_from(
                    select(window.c.character_id)
                    .group_by(window.c.character_id)
                    .having(func.count() < min_kills)
                    .subquery()
                )
            )
            or 0
        )
    elif method == "percentile":
        bucket_cols = [
            base_cte.c.encounter_id,
            base_cte.c.instance_id,
            base_cte.c.difficulty_id,
            base_cte.c.group_size,
            base_cte.c.class_slug,
            base_cte.c.spec,
        ]
        pct = (
            select(
                base_cte,
                cast(
                    func.percent_rank().over(
                        partition_by=bucket_cols, order_by=base_cte.c.value.asc() if hb else base_cte.c.value.desc()
                    )
                    * 100,
                    Float,
                ).label("pct"),
                func.count().over(partition_by=bucket_cols).label("bucket_n"),
            )
            .where(base_cte.c.class_slug.is_not(None), base_cte.c.spec.is_not(None))
            .cte("pct")
        )
        eligible = select(pct).where(pct.c.bucket_n >= min_bucket, *_class_filters(pct, f)).cte("eligible")
        ranked = select(
            eligible,
            func.row_number()
            .over(partition_by=eligible.c.character_id, order_by=[eligible.c.pct.desc(), eligible.c.occurred_at.asc()])
            .label("rn"),
            func.count().over(partition_by=eligible.c.character_id).label("samples"),
        ).cte("ranked")
        best = select(ranked).where(ranked.c.rn == 1).cte("best")
        q = (
            select(
                best.c.pct.label("value"),
                best.c.value.label("raw_value"),
                best.c.samples,
                best.c.bucket_n,
                best.c.fight_id,
                best.c.report_id,
                best.c.occurred_at,
                best.c.class_slug,
                best.c.spec,
                best.c.role,
                *_character_cols(),
            )
            .join(Character, Character.id == best.c.character_id)
            .outerjoin(Guild, Guild.id == Character.guild_id)
        )
        used_q = select(eligible.c.occurred_at, eligible.c.character_id)
        excluded = int(
            db.scalar(select(func.count()).select_from(pct).where(pct.c.bucket_n < min_bucket, *_class_filters(pct, f)))
            or 0
        )
        excluded += int(
            db.scalar(
                select(func.count())
                .select_from(base_cte)
                .where((base_cte.c.class_slug.is_(None)) | (base_cte.c.spec.is_(None)), *_class_filters(base_cte, f))
            )
            or 0
        )
        hb = True  # el percentil siempre es "más alto es mejor"
    else:
        raise ValueError("método inválido")

    sub = q.subquery()
    total = int(db.scalar(select(func.count()).select_from(sub)) or 0)
    ordered = select(sub).order_by(sub.c.value.desc() if hb else sub.c.value.asc(), sub.c.occurred_at.asc())
    rows = [dict(r) for r in db.execute(ordered.limit(page_size).offset((page - 1) * page_size)).mappings()]
    offset = (page - 1) * page_size
    for i, r in enumerate(rows):
        r["rank"] = offset + i + 1
    meta = _meta(db, used_q)
    meta.update({"records_excluded": excluded, "higher_better": hb})
    return {"rows": rows, "total": total, "meta": meta}


# ---------------------------------------------------------------------------
# Ranking general (varios encuentros normalizados)
# ---------------------------------------------------------------------------


def general_ranking(
    db: Session,
    f: Filters,
    metric: str,
    method: str,
    *,
    page: int,
    page_size: int,
    min_bucket: int,
    min_kills: int,
    min_partition: int = 3,
) -> dict[str, Any]:
    if metric not in GENERAL_METRICS:
        raise ValueError("métrica no disponible para el ranking general")
    col = METRICS[metric]["column"]

    base = select(RankingEntry, cast(col, Float).label("value")).where(*_where(f, include_class=False)).cte("base")
    pkeys = [base.c.encounter_id, base.c.difficulty_id, base.c.group_size]
    excluded = 0

    if method in ("peak", "consistency"):
        med = (
            select(*pkeys, func.percentile_cont(0.5).within_group(base.c.value).label("med"), func.count().label("pn"))
            .group_by(*pkeys)
            .cte("med")
        )
        norm = (
            select(base, (100.0 * base.c.value / func.nullif(med.c.med, 0)).label("s"))
            .join(
                med,
                and_(
                    med.c.encounter_id == base.c.encounter_id,
                    med.c.difficulty_id == base.c.difficulty_id,
                    med.c.group_size == base.c.group_size,
                ),
            )
            .where(med.c.pn >= min_partition, med.c.med > 0)
            .cte("norm")
        )
        filt = select(norm).where(*_class_filters(norm, f)).cte("filt")
        excluded = int(
            db.scalar(
                select(func.count())
                .select_from(base)
                .join(
                    med,
                    and_(
                        med.c.encounter_id == base.c.encounter_id,
                        med.c.difficulty_id == base.c.difficulty_id,
                        med.c.group_size == base.c.group_size,
                    ),
                )
                .where((med.c.pn < min_partition) | (med.c.med <= 0), *_class_filters(base, f))
            )
            or 0
        )
        if method == "peak":
            per_part = (
                select(
                    filt.c.character_id,
                    func.max(filt.c.s).label("best"),
                    func.count().label("n"),
                    func.max(filt.c.occurred_at).label("last_at"),
                )
                .group_by(filt.c.character_id, filt.c.encounter_id, filt.c.difficulty_id, filt.c.group_size)
                .cte("per_part")
            )
            agg = (
                select(
                    per_part.c.character_id,
                    cast(func.avg(per_part.c.best), Float).label("value"),
                    func.count().label("partitions"),
                    func.sum(per_part.c.n).label("samples"),
                    func.max(per_part.c.last_at).label("occurred_at"),
                )
                .group_by(per_part.c.character_id)
                .cte("agg")
            )
            used_q = select(filt.c.occurred_at, filt.c.character_id)
        else:
            agg = (
                select(
                    filt.c.character_id,
                    func.percentile_cont(0.5).within_group(filt.c.s).label("value"),
                    func.count(
                        func.distinct(
                            func.concat(filt.c.encounter_id, "-", filt.c.difficulty_id, "-", filt.c.group_size)
                        )
                    ).label("partitions"),
                    func.count().label("samples"),
                    func.max(filt.c.occurred_at).label("occurred_at"),
                )
                .group_by(filt.c.character_id)
                .having(func.count() >= min_kills)
                .cte("agg")
            )
            used_q = select(filt.c.occurred_at, filt.c.character_id).where(
                filt.c.character_id.in_(select(agg.c.character_id))
            )
    elif method == "percentile":
        bucket = [*pkeys, base.c.class_slug, base.c.spec]
        pct = (
            select(
                base,
                cast(func.percent_rank().over(partition_by=bucket, order_by=base.c.value.asc()) * 100, Float).label(
                    "pct"
                ),
                func.count().over(partition_by=bucket).label("bucket_n"),
            )
            .where(base.c.class_slug.is_not(None), base.c.spec.is_not(None))
            .cte("pct")
        )
        eligible = select(pct).where(pct.c.bucket_n >= min_bucket, *_class_filters(pct, f)).cte("eligible")
        excluded = int(
            db.scalar(select(func.count()).select_from(pct).where(pct.c.bucket_n < min_bucket, *_class_filters(pct, f)))
            or 0
        )
        per_part = (
            select(
                eligible.c.character_id,
                func.max(eligible.c.pct).label("best"),
                func.count().label("n"),
                func.max(eligible.c.occurred_at).label("last_at"),
            )
            .group_by(eligible.c.character_id, eligible.c.encounter_id, eligible.c.difficulty_id, eligible.c.group_size)
            .cte("per_part")
        )
        agg = (
            select(
                per_part.c.character_id,
                cast(func.avg(per_part.c.best), Float).label("value"),
                func.count().label("partitions"),
                func.sum(per_part.c.n).label("samples"),
                func.max(per_part.c.last_at).label("occurred_at"),
            )
            .group_by(per_part.c.character_id)
            .cte("agg")
        )
        used_q = select(eligible.c.occurred_at, eligible.c.character_id)
    else:
        raise ValueError("método inválido")

    q = (
        select(agg.c.value, agg.c.partitions, agg.c.samples, agg.c.occurred_at, *_character_cols())
        .join(Character, Character.id == agg.c.character_id)
        .outerjoin(Guild, Guild.id == Character.guild_id)
    )
    sub = q.subquery()
    total = int(db.scalar(select(func.count()).select_from(sub)) or 0)
    ordered = select(sub).order_by(sub.c.value.desc(), sub.c.samples.desc(), sub.c.character_id.asc())
    rows = [dict(r) for r in db.execute(ordered.limit(page_size).offset((page - 1) * page_size)).mappings()]
    offset = (page - 1) * page_size
    for i, r in enumerate(rows):
        r["rank"] = offset + i + 1
    meta = _meta(db, used_q)
    meta.update({"records_excluded": excluded, "higher_better": True, "min_partition_size": min_partition})
    return {"rows": rows, "total": total, "meta": meta}
