"""Cola de trabajos sobre PostgreSQL (``SELECT ... FOR UPDATE SKIP LOCKED``).

- Varios workers pueden correr en paralelo sin tomar el mismo trabajo.
- Reintentos con backoff exponencial (``JOB_BACKOFF_BASE_SECONDS * 2^(intento-1)``).
- Al agotar ``max_attempts`` el trabajo queda ``dead`` y el reporte ``failed`` con el error.
- Trabajos ``running`` con lock vencido (worker caído) vuelven a la cola.
"""

from __future__ import annotations

import logging
import os
import socket
import threading
import traceback
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.importer.pipeline import process_report
from app.models import ImportJob, Report, WorkerHeartbeat

log = logging.getLogger("wfa.worker")

WORKER_ID = f"{socket.gethostname()}-{os.getpid()}"[:64]

# Con INLINE_WORKER el worker corre dentro de la API: se lo despierta al encolar un trabajo para
# poder sondear la base con poca frecuencia (en planes gratis, una base que nunca duerme agota la cuota).
inline_wakeup = threading.Event()


def notify_new_job() -> None:
    inline_wakeup.set()


def _now() -> datetime:
    return datetime.now(UTC)


def heartbeat(db: Session, processed: int = 0) -> None:
    stmt = pg_insert(WorkerHeartbeat).values(worker_id=WORKER_ID, last_seen_at=_now(), processed=processed)
    stmt = stmt.on_conflict_do_update(
        index_elements=[WorkerHeartbeat.worker_id],
        set_={"last_seen_at": _now(), "processed": WorkerHeartbeat.processed + processed},
    )
    db.execute(stmt)
    db.commit()


def requeue_stale(db: Session, settings: Settings) -> int:
    limit = _now() - timedelta(minutes=settings.job_stale_minutes)
    res = db.execute(
        update(ImportJob)
        .where(ImportJob.status == "running", ImportJob.locked_at < limit)
        .values(status="queued", locked_at=None, locked_by=None, last_error="Lock vencido: se reencola.")
    )
    db.commit()
    return res.rowcount or 0  # type: ignore[attr-defined]


def claim_next(db: Session) -> ImportJob | None:
    job = db.scalars(
        select(ImportJob)
        .where(ImportJob.status == "queued", ImportJob.run_after <= _now())
        .order_by(ImportJob.run_after, ImportJob.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    ).first()
    if job is None:
        db.rollback()
        return None
    job.status = "running"
    job.locked_at = _now()
    job.locked_by = WORKER_ID
    job.started_at = job.started_at or _now()
    job.attempts += 1
    db.commit()
    return job


def run_job(db: Session, settings: Settings, job: ImportJob) -> bool:
    """Ejecuta un trabajo ya reclamado. Devuelve True si terminó bien."""
    try:
        process_report(db, settings, job.report_id)
        job = db.get(ImportJob, job.id)  # type: ignore[assignment]
        job.status = "succeeded"
        job.finished_at = _now()
        job.last_error = None
        job.locked_at = None
        db.commit()
        return True
    except Exception as exc:
        db.rollback()
        detail = f"{type(exc).__name__}: {exc}"[:1500]
        log.warning("fallo procesando reporte", extra={"job_id": job.id, "report_id": job.report_id})
        log.debug(traceback.format_exc())
        job = db.get(ImportJob, job.id)  # type: ignore[assignment]
        report = db.get(Report, job.report_id)
        job.last_error = detail
        job.locked_at = None
        if job.attempts >= job.max_attempts:
            job.status = "dead"
            job.finished_at = _now()
            if report is not None:
                report.status = "failed"
                report.error = f"Falló tras {job.attempts} intentos: {detail}"
        else:
            delay = settings.job_backoff_base_seconds * (2 ** (job.attempts - 1))
            job.status = "queued"
            job.run_after = _now() + timedelta(seconds=delay)
            if report is not None:
                report.status = "queued"
        db.commit()
        return False


def drain(db: Session, settings: Settings, max_jobs: int = 100) -> int:
    """Procesa trabajos pendientes en el proceso actual (tests, CLI e INLINE_WORKER)."""
    done = 0
    while done < max_jobs:
        job = claim_next(db)
        if job is None:
            break
        run_job(db, settings, job)
        done += 1
    return done
