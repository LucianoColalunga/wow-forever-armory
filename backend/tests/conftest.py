"""Configuración de tests.

Los tests de integración usan una base PostgreSQL aparte (TEST_DATABASE_URL, por defecto
``wfa_test`` en localhost). Si no hay base disponible se saltean con un aviso claro.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

TEST_DB = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://wfa:wfa@localhost:5432/wfa_test")
_STORAGE = Path(tempfile.mkdtemp(prefix="wfa-test-storage-"))

os.environ["DATABASE_URL"] = TEST_DB
os.environ["STORAGE_DIR"] = str(_STORAGE)
os.environ["APP_ENV"] = "test"
os.environ["RATE_LIMIT_PUBLIC_PER_MIN"] = "100000"
os.environ["RATE_LIMIT_SEARCH_PER_MIN"] = "100000"
os.environ["RATE_LIMIT_IMPORT_PER_HOUR"] = "100000"
os.environ["RATE_LIMIT_LOGIN_PER_15MIN"] = "5"
os.environ["JOB_BACKOFF_BASE_SECONDS"] = "0"
os.environ["MIN_BUCKET_SIZE"] = "10"
os.environ["LOG_LEVEL"] = "WARNING"

LOGS = Path(__file__).parent / "fixtures" / "logs"


def _db_available() -> bool:
    try:
        import psycopg

        url = TEST_DB.replace("postgresql+psycopg://", "postgresql://")
        with psycopg.connect(url, connect_timeout=3):
            return True
    except Exception:
        return False


DB_OK = _db_available()


@pytest.fixture(scope="session")
def migrated() -> Iterator[None]:
    if not DB_OK:
        pytest.skip(f"PostgreSQL de tests no disponible ({TEST_DB.split('@')[-1]})")
    from alembic.config import Config

    from alembic import command

    cfg = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).parents[1] / "alembic"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    from app.db.session import get_sessionmaker
    from app.services.catalog import sync_catalog

    with get_sessionmaker()() as db:
        sync_catalog(db)
    yield
    shutil.rmtree(_STORAGE, ignore_errors=True)


TABLES = (
    "audit_log",
    "submissions",
    "ranking_entries",
    "ranking_versions",
    "fight_participants",
    "report_issues",
    "fights",
    "import_jobs",
    "reports",
    "source_files",
    "characters",
    "guilds",
    "encounters",
    "api_keys",
    "sessions",
    "users",
    "worker_heartbeats",
)


@pytest.fixture
def db(migrated: None) -> Iterator[object]:
    from sqlalchemy import text

    from app.core.ratelimit import limiter
    from app.db.session import get_sessionmaker
    from app.rankings.cache import response_cache

    with get_sessionmaker()() as s:
        s.execute(text("TRUNCATE " + ", ".join(TABLES) + " RESTART IDENTITY CASCADE"))
        s.execute(
            text(
                "UPDATE instances SET verification = CASE WHEN slug IN ('onyxias-lair', "
                "'excavation-site-wetlands', 'ragefire-chasm', 'the-deadmines', 'wailing-caverns', "
                "'scholomance', 'stratholme', 'blackrock-depths', 'warsong-gulch', 'arathi-basin', "
                "'alterac-valley') THEN 'reported' ELSE 'official' END, game_instance_ids = '[]'"
            )
        )
        s.commit()
        limiter.reset()
        response_cache.clear()
        for p in _STORAGE.glob("**/*"):
            if p.is_file():
                p.unlink()
        yield s


@pytest.fixture
def client(db: object) -> Iterator[object]:
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def make_user(db: object):  # type: ignore[no-untyped-def]
    from app.core.security import hash_password, new_api_key
    from app.models import ApiKey, User

    def _make(role: str = "uploader", email: str | None = None, password: str = "Correcta-Clave-2026") -> dict:
        email = email or f"{role}@example.test"
        u = User(email=email, display_name=role.title(), role=role, password_hash=hash_password(password))
        db.add(u)  # type: ignore[attr-defined]
        db.flush()  # type: ignore[attr-defined]
        raw, prefix, digest = new_api_key()
        db.add(ApiKey(user_id=u.id, name="tests", prefix=prefix, key_hash=digest))  # type: ignore[attr-defined]
        db.commit()  # type: ignore[attr-defined]
        return {
            "user": u,
            "email": email,
            "password": password,
            "api_key": raw,
            "headers": {"Authorization": f"Bearer {raw}"},
        }

    return _make


@pytest.fixture
def drain(db: object):  # type: ignore[no-untyped-def]
    from app.core.config import get_settings
    from app.db.session import get_sessionmaker
    from app.worker.queue import drain as _drain

    def _run() -> int:
        with get_sessionmaker()() as s:
            return _drain(s, get_settings(), max_jobs=500)

    return _run


@pytest.fixture
def upload(client: object):  # type: ignore[no-untyped-def]
    def _up(name: str, content: bytes | str, headers: dict, **form: str):  # type: ignore[no-untyped-def]
        data = content.encode("utf-8") if isinstance(content, str) else content
        return client.post(
            "/api/v1/reports/import",
            files={"file": (name, data, "text/plain")},  # type: ignore[attr-defined]
            data=form,
            headers=headers,
        )

    return _up
