from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text

from app import __version__
from app.api.deps import DB, SettingsDep
from app.models import ImportJob, WorkerHeartbeat
from app.parser import PARSER_VERSION

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", summary="Liveness: el proceso responde")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", summary="Readiness: base de datos y almacenamiento disponibles")
def ready(db: DB, settings: SettingsDep) -> JSONResponse:
    checks: dict[str, object] = {}
    healthy = True
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
        healthy = False
    try:
        settings.storage_dir.mkdir(parents=True, exist_ok=True)
        probe = settings.storage_dir / f".probe-{uuid.uuid4().hex}"
        probe.write_text("ok")
        probe.unlink()
        checks["storage"] = "ok"
    except OSError:
        checks["storage"] = "error"
        healthy = False
    if checks["database"] == "ok":
        last = db.scalar(select(func.max(WorkerHeartbeat.last_seen_at)))
        queued = db.scalar(select(func.count()).select_from(ImportJob).where(ImportJob.status == "queued"))
        checks["worker_last_seen"] = last
        checks["worker"] = (
            "ok"
            if last and datetime.now(UTC) - last < timedelta(minutes=2)
            else ("inline" if settings.inline_worker else "sin_latido")
        )
        checks["jobs_queued"] = queued
    body = {
        "status": "ok" if healthy else "error",
        "version": __version__,
        "parser_version": PARSER_VERSION,
        "checks": checks,
    }
    return JSONResponse(
        content=_jsonable(body), status_code=200 if healthy else 503, headers={"Cache-Control": "no-store"}
    )


def _jsonable(value: object) -> object:
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, datetime):
        return value.isoformat()
    return value
