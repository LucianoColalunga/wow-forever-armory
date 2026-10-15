"""Sincroniza el catálogo estático (app/catalog/forever.py) y las temporadas con la base."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalog.forever import CATALOG, find_by_zone_name
from app.models import Instance, Season

# Fases anunciadas por Blizzard (no son "temporadas" oficiales con nombre: se publican como fases).
DEFAULT_SEASONS = (
    {
        "slug": "beta-2026",
        "name": "Beta (17/09 – 22/10/2026)",
        "kind": "all",
        "starts_at": datetime(2026, 9, 17, tzinfo=UTC),
        "ends_at": datetime(2026, 10, 23, tzinfo=UTC),
        "is_official": True,
        "source_note": "Fechas de beta anunciadas por Blizzard (news.blizzard.com).",
    },
    {
        "slug": "lanzamiento-2026",
        "name": "Lanzamiento (desde 4/11/2026)",
        "kind": "all",
        "starts_at": datetime(2026, 11, 4, 23, 0, tzinfo=UTC),
        "ends_at": datetime(2026, 12, 9, tzinfo=UTC),
        "is_official": True,
        "source_note": "Lanzamiento global anunciado por Blizzard: 4/11/2026 15:00 PST.",
    },
    {
        "slug": "bandas-fase-1",
        "name": "Bandas fase 1 (desde 9/12/2026)",
        "kind": "all",
        "starts_at": datetime(2026, 12, 9, tzinfo=UTC),
        "ends_at": None,
        "is_official": True,
        "source_note": "Desbloqueo de Barrow Deeps, Hyjal Summit y Onyxia's Lair anunciado para el 9/12/2026.",
    },
)


def sync_catalog(db: Session) -> dict[str, int]:
    created = updated = 0
    existing = {i.slug: i for i in db.scalars(select(Instance))}
    for item in CATALOG:
        inst = existing.get(item.slug)
        if inst is None:
            db.add(
                Instance(
                    slug=item.slug,
                    name=item.name,
                    kind=item.kind,
                    max_players=item.max_players,
                    verification=item.verification,
                    source_url=item.source_url,
                    is_new=item.is_new_in_forever,
                    level_range=item.level_range,
                    notes=item.notes,
                    game_instance_ids=[],
                )
            )
            created += 1
        else:
            # No pisa decisiones del admin (verification = verified_by_admin, IDs asignados).
            inst.name, inst.kind, inst.max_players = item.name, item.kind, item.max_players
            inst.source_url, inst.is_new, inst.level_range, inst.notes = (
                item.source_url,
                item.is_new_in_forever,
                item.level_range,
                item.notes,
            )
            if inst.verification != "verified_by_admin":
                inst.verification = item.verification
            updated += 1
    seasons = {s.slug for s in db.scalars(select(Season))}
    for s in DEFAULT_SEASONS:
        if s["slug"] not in seasons:
            db.add(Season(**s))
    db.commit()
    return {"created": created, "updated": updated}


def instance_for(db: Session, zone_name: str | None, game_instance_id: int | None) -> Instance | None:
    if game_instance_id:
        for inst in db.scalars(select(Instance)):
            if game_instance_id in (inst.game_instance_ids or []):
                return inst
    item = find_by_zone_name(zone_name)
    if item is None:
        return None
    return db.scalar(select(Instance).where(Instance.slug == item.slug))


def season_for(db: Session, when: datetime, kind: str) -> Season | None:
    kinds = ("all", kind)
    q = (
        select(Season)
        .where(Season.kind.in_(kinds), Season.starts_at <= when)
        .where((Season.ends_at.is_(None)) | (Season.ends_at > when))
        .order_by(Season.starts_at.desc())
    )
    return db.scalars(q).first()
