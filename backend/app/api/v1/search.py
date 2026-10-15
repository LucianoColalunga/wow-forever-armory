from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.api.deps import DB, Dataset
from app.api.v1.players import name_filter
from app.core import ratelimit
from app.models import Character, Encounter, Guild, Instance, Report
from app.services.queries import encounter_dict, instance_dict, visible_report

router = APIRouter(tags=["search"], dependencies=[Depends(ratelimit.search_limit)])


@router.get("/search", summary="Buscador global: personajes, hermandades, jefes, instancias y reportes")
def search(
    db: DB,
    q: Annotated[str, Query(min_length=2, max_length=64)],
    dataset: Dataset = "real",
    limit: Annotated[int, Query(ge=1, le=20)] = 8,
) -> dict[str, Any]:
    term = q.strip()
    sim = func.similarity
    chars = db.scalars(
        select(Character)
        .where(Character.dataset == dataset, Character.hidden.is_(False), name_filter(Character.name, term))
        .order_by(sim(Character.name, term).desc(), Character.name)
        .limit(limit)
    ).all()
    guilds = db.scalars(
        select(Guild)
        .where(Guild.dataset == dataset, Guild.hidden.is_(False), name_filter(Guild.name, term))
        .order_by(sim(Guild.name, term).desc())
        .limit(limit)
    ).all()
    bosses = db.scalars(
        select(Encounter)
        .where(Encounter.dataset == dataset, name_filter(Encounter.name, term))
        .order_by(sim(Encounter.name, term).desc())
        .limit(limit)
    ).all()
    instances = db.scalars(
        select(Instance).where(name_filter(Instance.name, term)).order_by(sim(Instance.name, term).desc()).limit(limit)
    ).all()
    reports = db.scalars(
        select(Report)
        .where(
            Report.dataset == dataset,
            *visible_report(),
            (Report.public_id == term.lower()) | name_filter(Report.title, term),
        )
        .order_by(Report.created_at.desc())
        .limit(limit)
    ).all()
    return {
        "query": term,
        "dataset": dataset,
        "players": [
            {
                "id": c.id,
                "name": c.name,
                "realm": c.realm,
                "class_slug": c.class_slug,
                "spec": c.spec,
                "guild": c.guild.name if c.guild and not c.guild.hidden else None,
            }
            for c in chars
        ],
        "guilds": [{"id": g.id, "name": g.name, "realm": g.realm} for g in guilds],
        "bosses": [encounter_dict(b) for b in bosses],
        "instances": [instance_dict(i) for i in instances],
        "reports": [{"public_id": r.public_id, "title": r.title, "created_at": r.created_at} for r in reports],
    }
