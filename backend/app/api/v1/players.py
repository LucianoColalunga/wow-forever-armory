from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Float, cast, func, or_, select

from app.api.deps import DB, Dataset, Page, SettingsDep
from app.core import ratelimit
from app.models import Character, Encounter, Fight, FightParticipant, Guild, RankingEntry, Report
from app.services.queries import (
    character_dict,
    count_of,
    data_meta,
    encounter_dict,
    fight_summary,
    paged,
    participant_dict,
    visible_report,
)

router = APIRouter(tags=["players"], dependencies=[Depends(ratelimit.public_limit)])


def _get_character(db: DB, character_id: int, dataset: str) -> Character:
    c = db.get(Character, character_id)
    if c is None or c.hidden or c.dataset != dataset:
        raise HTTPException(404, "Personaje inexistente en este conjunto de datos.")
    return c


def name_filter(column: Any, q: str) -> Any:
    term = q.strip()[:64]
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return or_(column.ilike(f"{escaped}%", escape="\\"), func.similarity(column, term) > 0.3)


@router.get("/players", summary="Listado y búsqueda de personajes")
def list_players(
    db: DB,
    page: Page,
    dataset: Dataset = "real",
    q: Annotated[str | None, Query(max_length=64)] = None,
    class_slug: Annotated[str | None, Query(alias="class", max_length=16)] = None,
    spec: Annotated[str | None, Query(max_length=24)] = None,
    guild_id: int | None = None,
    sort: Literal["name", "last_seen", "fights"] = "last_seen",
) -> dict[str, Any]:
    pg, size = page
    fights_sq = (
        select(FightParticipant.character_id, func.count().label("fights"))
        .join(Fight, Fight.id == FightParticipant.fight_id)
        .join(Report, Report.id == Fight.report_id)
        .where(Fight.duplicate_of_id.is_(None), *visible_report())
        .group_by(FightParticipant.character_id)
        .subquery()
    )
    qry = (
        select(Character, func.coalesce(fights_sq.c.fights, 0).label("fights"))
        .outerjoin(fights_sq, fights_sq.c.character_id == Character.id)
        .where(Character.dataset == dataset, Character.hidden.is_(False))
    )
    if q:
        qry = qry.where(name_filter(Character.name, q))
    if class_slug:
        qry = qry.where(Character.class_slug == class_slug)
    if spec:
        qry = qry.where(Character.spec == spec)
    if guild_id:
        qry = qry.where(Character.guild_id == guild_id)
    total = count_of(db, qry)
    orders: dict[str, list[Any]] = {
        "name": [Character.name.asc()],
        "last_seen": [Character.last_seen_at.desc().nulls_last()],
        "fights": [func.coalesce(fights_sq.c.fights, 0).desc()],
    }
    order = orders[sort]
    rows = db.execute(qry.order_by(*order, Character.id).limit(size).offset((pg - 1) * size)).all()
    items = [{**character_dict(c), "fights": n} for c, n in rows]
    return paged(items, pg, size, total, data_meta(db, dataset))


@router.get("/players/{player_id}", summary="Perfil de personaje")
def get_player(player_id: int, db: DB, settings: SettingsDep, dataset: Dataset = "real") -> dict[str, Any]:
    c = _get_character(db, player_id, dataset)
    vis = [Fight.duplicate_of_id.is_(None), *visible_report()]
    base = (
        select(FightParticipant, Fight)
        .join(Fight, Fight.id == FightParticipant.fight_id)
        .join(Report, Report.id == Fight.report_id)
        .where(FightParticipant.character_id == c.id, *vis)
    )
    sub = base.subquery()
    summary_row = db.execute(
        select(
            func.count(),
            func.count().filter(sub.c.success.is_(True)),
            func.sum(sub.c.deaths),
            func.max(sub.c.dps),
            func.max(sub.c.hps),
            func.max(sub.c.aps),
            func.sum(sub.c.interrupts),
            func.sum(sub.c.dispels),
        ).where(sub.c.kind == "encounter")
    ).one()
    summary = {
        "encounters": int(summary_row[0] or 0),
        "kills": int(summary_row[1] or 0),
        "deaths": int(summary_row[2] or 0),
        "best_dps": summary_row[3],
        "best_hps": summary_row[4],
        "best_aps": summary_row[5],
        "interrupts": int(summary_row[6] or 0),
        "dispels": int(summary_row[7] or 0),
    }
    # Mejor marca por partición (encuentro × dificultad × tamaño) con su percentil por clase/spec.
    bucket = [
        RankingEntry.encounter_id,
        RankingEntry.difficulty_id,
        RankingEntry.group_size,
        RankingEntry.class_slug,
        RankingEntry.spec,
    ]
    pct = (
        select(
            RankingEntry.id,
            RankingEntry.character_id,
            RankingEntry.encounter_id,
            RankingEntry.difficulty_id,
            RankingEntry.group_size,
            RankingEntry.dps,
            RankingEntry.hps,
            RankingEntry.aps,
            RankingEntry.occurred_at,
            RankingEntry.fight_id,
            cast(func.percent_rank().over(partition_by=bucket, order_by=RankingEntry.dps.asc()) * 100, Float).label(
                "dps_pct"
            ),
            cast(func.percent_rank().over(partition_by=bucket, order_by=RankingEntry.hps.asc()) * 100, Float).label(
                "hps_pct"
            ),
            func.count().over(partition_by=bucket).label("bucket_n"),
        )
        .where(
            RankingEntry.dataset == dataset,
            RankingEntry.kind == "pve",
            RankingEntry.encounter_id.in_(select(RankingEntry.encounter_id).where(RankingEntry.character_id == c.id)),
        )
        .subquery()
    )
    mine = select(pct).where(pct.c.character_id == c.id).subquery()
    best_rows = db.execute(
        select(
            mine.c.encounter_id,
            mine.c.difficulty_id,
            mine.c.group_size,
            func.max(mine.c.dps),
            func.max(mine.c.hps),
            func.max(mine.c.aps),
            func.count(),
            func.max(mine.c.occurred_at),
            func.max(mine.c.dps_pct),
            func.max(mine.c.hps_pct),
            func.max(mine.c.bucket_n),
        ).group_by(mine.c.encounter_id, mine.c.difficulty_id, mine.c.group_size)
    ).all()
    enc_map = {
        e.id: e for e in db.scalars(select(Encounter).where(Encounter.id.in_([r[0] for r in best_rows] or [-1])))
    }
    best = [
        {
            "encounter": encounter_dict(enc_map.get(r[0] or -1)),
            "difficulty_id": r[1],
            "group_size": r[2],
            "best_dps": r[3],
            "best_hps": r[4],
            "best_aps": r[5],
            "kills": r[6],
            "last_kill_at": r[7],
            "best_dps_percentile": r[8] if (r[10] or 0) >= settings.min_bucket_size else None,
            "best_hps_percentile": r[9] if (r[10] or 0) >= settings.min_bucket_size else None,
            "bucket_size": r[10],
        }
        for r in best_rows
    ]
    best.sort(key=lambda b: (b["encounter"] or {}).get("name") or "")

    recent = db.execute(base.order_by(Fight.start_at.desc()).limit(10)).all()
    evolution = db.execute(
        select(
            RankingEntry.occurred_at,
            RankingEntry.encounter_id,
            RankingEntry.difficulty_id,
            RankingEntry.group_size,
            RankingEntry.dps,
            RankingEntry.hps,
            RankingEntry.aps,
            RankingEntry.fight_id,
        )
        .where(RankingEntry.character_id == c.id, RankingEntry.kind == "pve")
        .order_by(RankingEntry.occurred_at)
        .limit(500)
    ).all()
    return {
        "character": character_dict(c),
        "summary": summary,
        "best_by_encounter": best,
        "recent_fights": [
            {**fight_summary(f), "performance": participant_dict(p, c, include_details=False)} for p, f in recent
        ],
        "evolution": [
            {
                "at": r[0],
                "encounter_id": r[1],
                "difficulty_id": r[2],
                "group_size": r[3],
                "dps": r[4],
                "hps": r[5],
                "aps": r[6],
                "fight_id": r[7],
            }
            for r in evolution
        ],
        "meta": data_meta(db, dataset),
    }


@router.get("/players/{player_id}/fights", summary="Historial de combates del personaje")
def player_fights(
    player_id: int,
    db: DB,
    page: Page,
    dataset: Dataset = "real",
    kind: Literal["encounter", "battleground", "dungeon_run"] | None = None,
    success: bool | None = None,
) -> dict[str, Any]:
    pg, size = page
    c = _get_character(db, player_id, dataset)
    q = (
        select(FightParticipant, Fight)
        .join(Fight, Fight.id == FightParticipant.fight_id)
        .join(Report, Report.id == Fight.report_id)
        .where(FightParticipant.character_id == c.id, Fight.duplicate_of_id.is_(None), *visible_report())
    )
    if kind:
        q = q.where(Fight.kind == kind)
    if success is not None:
        q = q.where(Fight.success.is_(success))
    total = count_of(db, q)
    rows = db.execute(q.order_by(Fight.start_at.desc()).limit(size).offset((pg - 1) * size)).all()
    items = [{**fight_summary(f), "performance": participant_dict(p, c, include_details=False)} for p, f in rows]
    return paged(items, pg, size, total, data_meta(db, dataset))


@router.get("/compare", summary="Comparador de jugadores (2 a 4)", tags=["players"])
def compare(
    db: DB,
    ids: Annotated[str, Query(description="IDs separados por coma", max_length=64)],
    dataset: Dataset = "real",
) -> dict[str, Any]:
    try:
        id_list = list(dict.fromkeys(int(x) for x in ids.split(",") if x.strip()))
    except ValueError as exc:
        raise HTTPException(422, "ids inválidos") from exc
    if not 2 <= len(id_list) <= 4:
        raise HTTPException(422, "Elegí entre 2 y 4 personajes.")
    chars = [_get_character(db, i, dataset) for i in id_list]
    rows = db.execute(
        select(
            RankingEntry.character_id,
            RankingEntry.encounter_id,
            RankingEntry.difficulty_id,
            RankingEntry.group_size,
            func.max(RankingEntry.dps),
            func.percentile_cont(0.5).within_group(RankingEntry.dps),
            func.max(RankingEntry.hps),
            func.percentile_cont(0.5).within_group(RankingEntry.hps),
            func.max(RankingEntry.aps),
            func.count(),
            func.avg(RankingEntry.survival_pct),
        )
        .where(RankingEntry.character_id.in_(id_list), RankingEntry.kind == "pve", RankingEntry.dataset == dataset)
        .group_by(
            RankingEntry.character_id, RankingEntry.encounter_id, RankingEntry.difficulty_id, RankingEntry.group_size
        )
    ).all()
    partitions: dict[tuple[int, int | None, int | None], dict[str, Any]] = {}
    for r in rows:
        key = (r[1], r[2], r[3])
        part = partitions.setdefault(
            key, {"encounter_id": r[1], "difficulty_id": r[2], "group_size": r[3], "players": {}}
        )
        part["players"][str(r[0])] = {
            "best_dps": r[4],
            "median_dps": r[5],
            "best_hps": r[6],
            "median_hps": r[7],
            "best_aps": r[8],
            "kills": r[9],
            "avg_survival_pct": r[10],
        }
    enc_map = {
        e.id: e for e in db.scalars(select(Encounter).where(Encounter.id.in_([k[0] for k in partitions] or [-1])))
    }
    common = []
    for key, part in partitions.items():
        part["encounter"] = encounter_dict(enc_map.get(key[0]))
        part["shared_by_all"] = len(part["players"]) == len(id_list)
        common.append(part)
    common.sort(key=lambda p: (not p["shared_by_all"], (p["encounter"] or {}).get("name") or ""))
    series = db.execute(
        select(
            RankingEntry.character_id,
            RankingEntry.occurred_at,
            RankingEntry.dps,
            RankingEntry.hps,
            RankingEntry.encounter_id,
        )
        .where(RankingEntry.character_id.in_(id_list), RankingEntry.kind == "pve", RankingEntry.dataset == dataset)
        .order_by(RankingEntry.occurred_at)
        .limit(1000)
    ).all()
    return {
        "players": [character_dict(c) for c in chars],
        "partitions": common,
        "series": [{"character_id": s[0], "at": s[1], "dps": s[2], "hps": s[3], "encounter_id": s[4]} for s in series],
        "note": "Sólo se comparan valores dentro del mismo encuentro, dificultad y tamaño de grupo.",
        "meta": data_meta(db, dataset),
    }


@router.get("/guilds", summary="Listado y búsqueda de hermandades", tags=["guilds"])
def list_guilds(
    db: DB, page: Page, dataset: Dataset = "real", q: Annotated[str | None, Query(max_length=64)] = None
) -> dict[str, Any]:
    pg, size = page
    members = (
        select(Character.guild_id, func.count().label("members"))
        .where(Character.hidden.is_(False))
        .group_by(Character.guild_id)
        .subquery()
    )
    qry = (
        select(Guild, func.coalesce(members.c.members, 0))
        .outerjoin(members, members.c.guild_id == Guild.id)
        .where(Guild.dataset == dataset, Guild.hidden.is_(False))
    )
    if q:
        qry = qry.where(name_filter(Guild.name, q))
    total = count_of(db, qry)
    rows = db.execute(qry.order_by(Guild.name).limit(size).offset((pg - 1) * size)).all()
    items = [
        {"id": g.id, "name": g.name, "realm": g.realm, "region": g.region, "faction": g.faction, "members": n}
        for g, n in rows
    ]
    return paged(items, pg, size, total, data_meta(db, dataset))


@router.get("/guilds/{guild_id}", summary="Perfil de hermandad", tags=["guilds"])
def get_guild(guild_id: int, db: DB, dataset: Dataset = "real") -> dict[str, Any]:
    g = db.get(Guild, guild_id)
    if g is None or g.hidden or g.dataset != dataset:
        raise HTTPException(404, "Hermandad inexistente en este conjunto de datos.")
    members = db.scalars(
        select(Character).where(Character.guild_id == g.id, Character.hidden.is_(False)).order_by(Character.name)
    ).all()
    reports = db.scalars(
        select(Report).where(Report.guild_id == g.id, *visible_report()).order_by(Report.created_at.desc()).limit(20)
    ).all()
    vis = [Fight.duplicate_of_id.is_(None), *visible_report()]
    prog = db.execute(
        select(
            Fight.encounter_id,
            Fight.difficulty_id,
            Fight.group_size,
            func.min(Fight.start_at),
            func.count(),
            func.min(Fight.duration_ms),
        )
        .join(Report, Report.id == Fight.report_id)
        .where(Report.guild_id == g.id, Fight.kind == "encounter", Fight.success.is_(True), *vis)
        .group_by(Fight.encounter_id, Fight.difficulty_id, Fight.group_size)
    ).all()
    enc_map = {e.id: e for e in db.scalars(select(Encounter).where(Encounter.id.in_([p[0] for p in prog] or [-1])))}
    week = func.date_trunc("week", Fight.start_at)
    activity = db.execute(
        select(week, func.count(), func.count().filter(Fight.success.is_(True)))
        .join(Report, Report.id == Fight.report_id)
        .where(Report.guild_id == g.id, Fight.kind == "encounter", *vis)
        .group_by(week)
        .order_by(week)
    ).all()
    return {
        "guild": {
            "id": g.id,
            "name": g.name,
            "realm": g.realm,
            "region": g.region,
            "faction": g.faction,
            "dataset": g.dataset,
        },
        "members": [
            {
                **character_dict(m),
                "membership": "inferida por reportes"
                if m.guild_source == "report_tag"
                else ("asignada por admin" if m.guild_source == "admin" else "aporte aprobado"),
            }
            for m in members
        ],
        "reports": [
            {
                "public_id": r.public_id,
                "title": r.title,
                "created_at": r.created_at,
                "log_started_at": r.log_started_at,
                "stats": r.stats,
            }
            for r in reports
        ],
        "progression": sorted(
            [
                {
                    "encounter": encounter_dict(enc_map.get(p[0] or -1)),
                    "difficulty_id": p[1],
                    "group_size": p[2],
                    "first_kill_at": p[3],
                    "kills": p[4],
                    "fastest_kill_ms": p[5],
                }
                for p in prog
            ],
            key=lambda x: x["first_kill_at"],
        ),
        "activity": [{"week": w, "pulls": n, "kills": int(k or 0)} for w, n, k in activity],
        "meta": data_meta(db, dataset),
    }
