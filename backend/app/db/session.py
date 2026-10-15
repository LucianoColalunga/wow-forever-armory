from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def _force_utc(dbapi_connection: Any, _record: Any) -> None:
    """Sesiones siempre en UTC: fechas de la API y filtros sin huso no dependen del servidor."""
    dbapi_connection.execute("SET TIME ZONE 'UTC'")
    dbapi_connection.commit()


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    connect_args: dict[str, object] = {}
    if "-pooler." in settings.database_url:
        # Detrás de PgBouncer en modo transacción no se pueden usar sentencias preparadas.
        connect_args["prepare_threshold"] = None
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_pool_size,
        connect_args=connect_args,
    )
    event.listen(engine, "connect", _force_utc)
    return engine


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = get_sessionmaker()()
    try:
        yield db
    finally:
        db.close()
