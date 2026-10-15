"""Worker de importación:  python -m app.worker"""

from __future__ import annotations

import logging
import signal
import time

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import get_sessionmaker
from app.worker.queue import claim_next, heartbeat, requeue_stale, run_job

_running = True


def _stop(*_: object) -> None:
    global _running
    _running = False


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    log = logging.getLogger("wfa.worker")
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    session_factory = get_sessionmaker()
    log.info("worker iniciado")
    last_maintenance = 0.0
    while _running:
        with session_factory() as db:
            now = time.monotonic()
            if now - last_maintenance > 30:
                requeue_stale(db, settings)
                heartbeat(db)
                last_maintenance = now
            job = claim_next(db)
            if job is None:
                time.sleep(settings.worker_poll_seconds)
                continue
            ok = run_job(db, settings, job)
            heartbeat(db, processed=1 if ok else 0)
    log.info("worker detenido")


if __name__ == "__main__":
    main()
