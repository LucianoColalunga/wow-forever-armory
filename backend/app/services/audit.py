"""Auditoría de acciones administrativas. Toda corrección admin pasa por ``record``."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog, User


def record(
    db: Session,
    *,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: str | int,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    reason: str,
    ip: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor.id if actor else None,
        actor_label=actor.email if actor else "system",
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        before=before,
        after=after,
        reason=reason.strip()[:2000],
        ip=ip,
    )
    db.add(entry)
    return entry
