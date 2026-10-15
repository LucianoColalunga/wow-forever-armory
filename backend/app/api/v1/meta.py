from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select

from app.api.deps import DB, Dataset, OptionalAuth, SettingsDep
from app.catalog.forever import PVP_MODES
from app.core import ratelimit
from app.models import Character, Encounter, Fight, FightParticipant, Guild, Instance, Report, Season, Submission
from app.parser import PARSER_VERSION
from app.parser.classes import CLASSES, SPEC_LABELS
from app.rankings.methods import GENERAL_METRICS, METHODS, METRICS, PVP_METRICS
from app.schemas import SubmissionIn
from app.services.queries import data_meta, encounter_dict, instance_dict, visible_report
from app.sources import all_sources

router = APIRouter(tags=["meta"], dependencies=[Depends(ratelimit.public_limit)])


@router.get("/meta/catalog", summary="Instancias, modalidades PvP y su estado de verificación")
def catalog(db: DB) -> dict[str, Any]:
    instances = db.scalars(select(Instance).order_by(Instance.kind, Instance.name)).all()
    return {
        "instances": [instance_dict(i) for i in instances],
        "pvp_modes": list(PVP_MODES),
        "classes": [
            {"slug": k, "label": v["label"], "specs": [{"slug": s, "label": SPEC_LABELS[s]} for s in v["specs"]]}  # type: ignore[attr-defined]
            for k, v in CLASSES.items()
        ],
        "mythic_plus": {
            "available": False,
            "detail": "Ningún anuncio de Forever menciona Mythic+ ni afijos: no se implementa.",
        },
    }


@router.get("/meta/seasons", summary="Temporadas / fases")
def seasons(db: DB) -> list[dict[str, Any]]:
    rows = db.scalars(select(Season).order_by(Season.starts_at)).all()
    return [
        {
            "id": s.id,
            "slug": s.slug,
            "name": s.name,
            "kind": s.kind,
            "starts_at": s.starts_at,
            "ends_at": s.ends_at,
            "is_official": s.is_official,
            "source_note": s.source_note,
        }
        for s in rows
    ]


@router.get("/meta/methodology", summary="Definición de métricas y métodos de ranking")
def methodology(settings: SettingsDep) -> dict[str, Any]:
    return {
        "parser_version": PARSER_VERSION,
        "metrics": {
            k: {
                "label": v["label"],
                "higher_better": v["higher_better"],
                "unit": v["unit"],
                "pvp_only": v.get("pvp_only", False),
            }
            for k, v in METRICS.items()
        },
        "general_metrics": list(GENERAL_METRICS),
        "pvp_metrics": list(PVP_METRICS),
        "methods": METHODS,
        "thresholds": {
            "min_bucket_size": settings.min_bucket_size,
            "consistency_min_kills": settings.consistency_min_kills,
            "consistency_last_n": settings.consistency_last_n,
            "min_partition_size": 3,
            "min_rankable_duration_ms": 15000,
        },
        "definitions": {
            "damage_done": "Daño realizado = vida quitada + overkill + daño absorbido por escudos del objetivo.",
            "effective_damage": "Daño efectivo = vida realmente quitada (amount − overkill).",
            "overkill": "Daño que sobró en el golpe que mató al objetivo.",
            "healing_effective": "Curación efectiva = curación − overhealing.",
            "overhealing": "Curación desperdiciada sobre vida llena.",
            "absorbs_provided": "Daño absorbido por escudos del jugador (SPELL_ABSORBED). Nunca se suma a la curación.",
            "damage_taken": "Vida perdida por el jugador (sin contar lo absorbido, que se informa aparte).",
            "survival_pct": "Porcentaje del combate que el jugador estuvo con vida hasta su primera muerte.",
            "partitions": "Los rankings nunca mezclan encuentros, dificultades ni tamaños de grupo distintos.",
            "duplicates": "El mismo combate subido por varias personas cuenta una sola vez.",
            "estimated": "No existe rating oficial de Forever: ningún número de este sitio es un rating de Blizzard.",
        },
    }


@router.get("/meta/sources", summary="Fuentes de datos y estado de cada integración")
def sources() -> list[dict[str, Any]]:
    return all_sources()


@router.get("/stats/overview", summary="Resumen para el dashboard")
def overview(db: DB, dataset: Dataset = "real") -> dict[str, Any]:
    vis = [Fight.dataset == dataset, Fight.duplicate_of_id.is_(None), *visible_report()]
    counts = {
        "reports": db.scalar(
            select(func.count()).select_from(Report).where(Report.dataset == dataset, *visible_report())
        )
        or 0,
        "fights": db.scalar(select(func.count()).select_from(Fight).join(Report).where(*vis)) or 0,
        "kills": db.scalar(
            select(func.count())
            .select_from(Fight)
            .join(Report)
            .where(*vis, Fight.kind == "encounter", Fight.success.is_(True))
        )
        or 0,
        "characters": db.scalar(
            select(func.count()).select_from(Character).where(Character.dataset == dataset, Character.hidden.is_(False))
        )
        or 0,
        "guilds": db.scalar(
            select(func.count()).select_from(Guild).where(Guild.dataset == dataset, Guild.hidden.is_(False))
        )
        or 0,
        "bosses": db.scalar(select(func.count()).select_from(Encounter).where(Encounter.dataset == dataset)) or 0,
    }
    latest = db.scalars(
        select(Fight)
        .join(Report)
        .where(*vis, Fight.kind == "encounter", Fight.success.is_(True))
        .order_by(Fight.start_at.desc())
        .limit(8)
    ).all()
    latest_kills = [
        {
            "fight_id": f.id,
            "encounter": encounter_dict(f.encounter),
            "instance": instance_dict(f.instance),
            "difficulty_id": f.difficulty_id,
            "group_size": f.group_size,
            "start_at": f.start_at,
            "duration_ms": f.duration_ms,
            "report_public_id": f.report.public_id,
        }
        for f in latest
    ]

    # Mejores actuaciones de la última semana con datos (por métrica y rol), por encuentro.
    last_at = db.scalar(select(func.max(Fight.start_at)).join(Report).where(*vis))
    highlights: list[dict[str, Any]] = []
    if last_at is not None:
        since = last_at - timedelta(days=7)
        for metric, role in (("dps", "dps"), ("hps", "healer"), ("aps", None)):
            col = getattr(FightParticipant, metric)
            q = (
                select(FightParticipant, Character, Fight)
                .join(Fight, Fight.id == FightParticipant.fight_id)
                .join(Report, Report.id == Fight.report_id)
                .join(Character, Character.id == FightParticipant.character_id)
                .where(
                    *vis,
                    Fight.kind == "encounter",
                    Fight.success.is_(True),
                    Fight.rankable.is_(True),
                    Fight.excluded_by_admin.is_(False),
                    Fight.start_at >= since,
                    Character.hidden.is_(False),
                    col > 0,
                )
                .order_by(col.desc())
                .limit(1)
            )
            if role:
                q = q.where(FightParticipant.role == role)
            row = db.execute(q).first()
            if row:
                p, c, f = row
                highlights.append(
                    {
                        "metric": metric,
                        "value": getattr(p, metric),
                        "character_id": c.id,
                        "name": c.name,
                        "class_slug": p.class_slug,
                        "spec": p.spec,
                        "fight_id": f.id,
                        "encounter": encounter_dict(f.encounter),
                        "difficulty_id": f.difficulty_id,
                        "group_size": f.group_size,
                    }
                )
    # Kills por día (últimos 30 días con datos) para el gráfico del dashboard.
    activity: list[dict[str, Any]] = []
    if last_at is not None:
        day = func.date_trunc("day", Fight.start_at)
        rows = db.execute(
            select(day.label("day"), func.count())
            .join(Report)
            .where(*vis, Fight.kind == "encounter", Fight.start_at >= last_at - timedelta(days=30))
            .group_by(day)
            .order_by(day)
        ).all()
        activity = [{"day": d, "fights": n} for d, n in rows]
    return {
        "counts": counts,
        "latest_kills": latest_kills,
        "highlights": highlights,
        "activity": activity,
        "meta": data_meta(db, dataset),
        "now": datetime.now(UTC),
    }


@router.post("/submissions", status_code=202, summary="Enviar un aporte (queda pendiente de moderación)")
def submit(body: SubmissionIn, request: Request, db: DB, ctx: OptionalAuth) -> dict[str, Any]:
    ratelimit.enforce(request, "submission", 10, 3600)
    payload = {
        k: (str(v)[:500] if not isinstance(v, int | float | bool) else v) for k, v in list(body.payload.items())[:10]
    }
    sub = Submission(
        kind=body.kind,
        payload=payload,
        status="pending",
        submitted_by=ctx.user.id if ctx else None,
        contact=body.contact,
    )
    db.add(sub)
    db.commit()
    return {"id": sub.id, "status": "pending", "message": "Gracias: un admin lo va a revisar antes de aplicarlo."}
