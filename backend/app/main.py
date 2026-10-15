"""Aplicación FastAPI: monolito modular (API pública, importación, admin)."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.v1 import admin, auth, content, health, meta, players, rankings, reports, search
from app.core.config import get_settings
from app.core.logging import configure_logging

log = logging.getLogger("wfa.api")

DESCRIPTION = """
API REST de **WoW Forever Armory & Competitive Analytics**: estadísticas competitivas de
*World of Warcraft: Forever* construidas a partir de combat logs importados.

* Proyecto de la comunidad, **no afiliado a Blizzard Entertainment**. No hay API oficial de Forever.
* Todos los endpoints de lectura aceptan `dataset=real|demo`. Los datos `demo` son fixtures sintéticos
  y nunca se mezclan con datos reales.
* Ningún número es un rating oficial. Los métodos de ranking están en `GET /api/v1/meta/methodology`.
* Escritura: sesión (cookie + cabecera `X-CSRF-Token`) o API key (`Authorization: Bearer wfa_...`).
"""

TAGS = [
    {"name": "rankings", "description": "Rankings PvE (por jefe y general) y PvP (sólo modalidades confirmadas)."},
    {"name": "players", "description": "Personajes, perfiles, historial y comparador."},
    {"name": "guilds", "description": "Hermandades."},
    {"name": "content", "description": "Bandas, mazmorras, campos de batalla, jefes y combates."},
    {"name": "reports", "description": "Reportes importados e importación de combat logs."},
    {"name": "search", "description": "Buscador global."},
    {"name": "meta", "description": "Catálogo, temporadas, metodología, fuentes y resumen."},
    {"name": "auth", "description": "Sesión y API keys."},
    {"name": "admin", "description": "Panel admin (rol admin, acciones auditadas)."},
    {"name": "health", "description": "Health checks."},
]

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}
API_CSP = "default-src 'none'; frame-ancestors 'none'"
DOCS_CSP = (
    "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
    "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; img-src 'self' data: https://fastapi.tiangolo.com; "
    "frame-ancestors 'none'"
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    stop = threading.Event()
    if settings.inline_worker:
        threading.Thread(target=_inline_worker, args=(stop,), daemon=True, name="inline-worker").start()
    yield
    stop.set()


def _inline_worker(stop: threading.Event) -> None:
    """Worker dentro del proceso de la API (para despliegues de un solo contenedor)."""
    from app.db.session import get_sessionmaker
    from app.worker.queue import claim_next, heartbeat, run_job

    settings = get_settings()
    factory = get_sessionmaker()
    while not stop.is_set():
        try:
            with factory() as db:
                heartbeat(db)
                job = claim_next(db)
                if job is None:
                    stop.wait(settings.worker_poll_seconds)
                    continue
                run_job(db, settings, job)
        except Exception:
            log.exception("error en el worker interno")
            stop.wait(5)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="WoW Forever Armory API",
        version=__version__,
        description=DESCRIPTION,
        openapi_tags=TAGS,
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan,
    )
    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "DELETE"],
            allow_headers=["Content-Type", "X-CSRF-Token", "Authorization", "X-API-Key"],
        )

    max_body = settings.max_upload_mb * 1024 * 1024 + 1024 * 1024

    @app.middleware("http")
    async def guard_and_log(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        rid = request.headers.get("x-request-id", "")[:64] or uuid.uuid4().hex[:16]
        if request.method == "POST" and request.url.path.endswith("/reports/import"):
            length = request.headers.get("content-length")
            if length is None:
                return JSONResponse({"detail": "Falta Content-Length."}, status_code=411)
            if not length.isdigit() or int(length) > max_body:
                return JSONResponse({"detail": f"El archivo supera {settings.max_upload_mb} MB."}, status_code=413)
        start = time.perf_counter()
        response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        path = request.url.path
        response.headers.setdefault(
            "Content-Security-Policy", DOCS_CSP if path in ("/api/docs", "/api/redoc") else API_CSP
        )
        if settings.is_production:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        if request.method == "GET" and "cache-control" not in response.headers:
            response.headers["Cache-Control"] = (
                "no-store" if "/admin" in path or "/auth" in path else "public, max-age=30"
            )
        response.headers["X-Request-ID"] = rid
        log.info(
            "request",
            extra={
                "request_id": rid,
                "path": path,
                "method": request.method,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - start) * 1000, 1),
            },
        )
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"loc": list(e.get("loc", [])), "msg": e.get("msg", ""), "type": e.get("type", "")} for e in exc.errors()
        ]
        return JSONResponse({"detail": "Parámetros inválidos.", "errors": errors}, status_code=422)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("error no controlado", extra={"path": request.url.path})
        return JSONResponse({"detail": "Error interno. Probá de nuevo más tarde."}, status_code=500)

    app.include_router(health.router, prefix="/api")
    for r in (
        rankings.router,
        players.router,
        content.router,
        reports.router,
        search.router,
        meta.router,
        auth.router,
        admin.router,
    ):
        app.include_router(r, prefix="/api/v1")
    return app


app = create_app()
