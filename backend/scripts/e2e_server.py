"""Servidor de la API para los tests end-to-end (Playwright).

Prepara una base aislada desde cero y luego sirve la API con el worker interno:
  1. migraciones (downgrade base + upgrade head)
  2. catálogo y fases
  3. datos DEMO sintéticos
  4. fixtures de tests/fixtures/logs importados como datos reales
  5. admin de prueba con E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD (nunca credenciales reales)

Uso:  python scripts/e2e_server.py   (variables: DATABASE_URL, E2E_ADMIN_EMAIL, E2E_ADMIN_PASSWORD, E2E_PORT)
"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("INLINE_WORKER", "true")
os.environ.setdefault("JOB_BACKOFF_BASE_SECONDS", "1")
os.environ.setdefault("RATE_LIMIT_PUBLIC_PER_MIN", "100000")
os.environ.setdefault("RATE_LIMIT_SEARCH_PER_MIN", "100000")
os.environ.setdefault("RATE_LIMIT_IMPORT_PER_HOUR", "1000")
os.environ.setdefault("RATE_LIMIT_LOGIN_PER_15MIN", "50")
os.environ.setdefault("STORAGE_DIR", str(ROOT / "storage-e2e"))


def prepare() -> None:
    from alembic.config import Config
    from sqlalchemy import select

    from alembic import command
    from app.cli import _seed_demo
    from app.core.config import get_settings
    from app.core.security import hash_password
    from app.db.session import get_sessionmaker
    from app.importer.pipeline import ImportMeta, create_import
    from app.models import User
    from app.services.catalog import sync_catalog
    from app.worker.queue import drain

    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    settings = get_settings()
    for f in settings.storage_dir.glob("**/*"):
        if f.is_file():
            f.unlink()
    with get_sessionmaker()() as db:
        sync_catalog(db)

    class Args:
        force = True
        weeks = 3

    _seed_demo(Args())  # type: ignore[arg-type]

    logs = ROOT / "tests" / "fixtures" / "logs"
    with get_sessionmaker()() as db:
        for name in ("basic_kill.txt", "wipe_then_kill.txt", "battleground.txt"):
            meta = ImportMeta(title=f"Fixture {name}", guild_name="Prueba E2E", guild_realm="Testrealm", region="us")
            create_import(db, settings, io.BytesIO((logs / name).read_bytes()), name, meta, None)
        drain(db, settings)

        email = os.environ.get("E2E_ADMIN_EMAIL")
        password = os.environ.get("E2E_ADMIN_PASSWORD")
        if email and password and not db.scalar(select(User).where(User.email == email.lower())):
            db.add(
                User(email=email.lower(), display_name="Admin E2E", role="admin", password_hash=hash_password(password))
            )
            db.commit()


def main() -> None:
    prepare()
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=int(os.environ.get("E2E_PORT", "8100")), log_level="warning")


if __name__ == "__main__":
    main()
