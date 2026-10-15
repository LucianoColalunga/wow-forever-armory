from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.api.deps import DB, Dataset, OptionalAuth, Page, SettingsDep
from app.core import ratelimit
from app.importer.pipeline import ImportMeta, create_import
from app.importer.validation import InvalidUpload
from app.models import Fight, ImportJob, Report, ReportIssue, SourceFile
from app.schemas import ImportAccepted
from app.services.queries import count_of, data_meta, fight_summary, paged, visible_report

router = APIRouter(prefix="/reports", tags=["reports"])


def _report_dict(r: Report, source: SourceFile | None) -> dict[str, Any]:
    return {
        "public_id": r.public_id,
        "title": r.title,
        "dataset": r.dataset,
        "visibility": r.visibility,
        "status": r.status,
        "guild": {"id": r.guild.id, "name": r.guild.name, "realm": r.guild.realm} if r.guild else None,
        "region": r.region,
        "parser_version": r.parser_version,
        "dialect": r.dialect,
        "stats": r.stats,
        "log_started_at": r.log_started_at,
        "log_ended_at": r.log_ended_at,
        "created_at": r.created_at,
        "processed_at": r.processed_at,
        "error": r.error,
        "source_file": {
            "sha256": source.sha256,
            "original_name": source.original_name,
            "size_bytes": source.size_bytes,
            "content_kind": source.content_kind,
        }
        if source
        else None,
    }


@router.get("", summary="Reportes públicos procesados", dependencies=[Depends(ratelimit.public_limit)])
def list_reports(db: DB, page: Page, dataset: Dataset = "real", guild_id: int | None = None) -> dict[str, Any]:
    pg, size = page
    q = select(Report).where(Report.dataset == dataset, *visible_report())
    if guild_id:
        q = q.where(Report.guild_id == guild_id)
    total = count_of(db, q)
    rows = db.scalars(q.order_by(Report.created_at.desc()).limit(size).offset((pg - 1) * size)).all()
    items = [_report_dict(r, None) for r in rows]
    return paged(items, pg, size, total, data_meta(db, dataset))


def _get_report(db: DB, public_id: str, ctx: OptionalAuth) -> Report:
    r = db.scalar(select(Report).where(Report.public_id == public_id[:16]))
    if r is None or r.deleted_at is not None:
        raise HTTPException(404, "Reporte inexistente.")
    is_owner = ctx is not None and (ctx.user.role == "admin" or ctx.user.id == r.uploaded_by)
    if r.visibility == "private" and not is_owner:
        raise HTTPException(404, "Reporte inexistente.")
    return r


@router.get(
    "/{report_id}",
    summary="Detalle de reporte con trazabilidad al archivo de origen",
    dependencies=[Depends(ratelimit.public_limit)],
)
def get_report(report_id: str, db: DB, ctx: OptionalAuth) -> dict[str, Any]:
    r = _get_report(db, report_id, ctx)
    source = db.get(SourceFile, r.source_file_id)
    fights = db.scalars(select(Fight).where(Fight.report_id == r.id).order_by(Fight.start_at, Fight.id)).all()
    issues = db.scalars(select(ReportIssue).where(ReportIssue.report_id == r.id).order_by(ReportIssue.id)).all()
    job = db.scalar(select(ImportJob).where(ImportJob.report_id == r.id).order_by(ImportJob.id.desc()))
    return {
        **_report_dict(r, source),
        "fights": [fight_summary(f) | {"first_line": f.first_line, "last_line": f.last_line} for f in fights],
        "issues": [
            {"severity": i.severity, "code": i.code, "message": i.message, "line_no": i.line_no, "fight_id": i.fight_id}
            for i in issues
        ],
        "job": {
            "id": job.id,
            "status": job.status,
            "attempts": job.attempts,
            "max_attempts": job.max_attempts,
            "last_error": job.last_error,
            "run_after": job.run_after,
        }
        if job
        else None,
        "meta": data_meta(db, r.dataset),
    }


@router.get(
    "/{report_id}/status",
    summary="Estado del procesamiento (para polling)",
    dependencies=[Depends(ratelimit.public_limit)],
)
def report_status(report_id: str, db: DB, ctx: OptionalAuth) -> dict[str, Any]:
    r = _get_report(db, report_id, ctx)
    job = db.scalar(select(ImportJob).where(ImportJob.report_id == r.id).order_by(ImportJob.id.desc()))
    return {
        "public_id": r.public_id,
        "status": r.status,
        "error": r.error,
        "stats": r.stats,
        "job_status": job.status if job else None,
        "attempts": job.attempts if job else 0,
    }


@router.post(
    "/import",
    status_code=202,
    response_model=ImportAccepted,
    summary="Importar un combat log (.txt, .log o .zip con un único archivo)",
    responses={
        200: {"description": "El archivo ya estaba importado"},
        413: {"description": "Archivo muy grande"},
        415: {"description": "Formato rechazado"},
        401: {"description": "Requiere autenticación"},
    },
)
def import_report(
    request: Request,
    db: DB,
    settings: SettingsDep,
    ctx: OptionalAuth,
    file: Annotated[UploadFile, File(description="WoWCombatLog*.txt o .zip")],
    title: Annotated[str | None, Form(max_length=128)] = None,
    guild_name: Annotated[str | None, Form(max_length=64)] = None,
    guild_realm: Annotated[str | None, Form(max_length=64)] = None,
    region: Annotated[Literal["", "us", "eu", "kr", "tw", "cn"], Form()] = "",
    faction: Annotated[Literal["alliance", "horde"] | None, Form()] = None,
    visibility: Annotated[Literal["public", "private"], Form()] = "public",
    utc_offset: Annotated[int | None, Form(ge=-12, le=14, description="Huso del cliente si el log no lo trae")] = None,
    default_year: Annotated[int | None, Form(ge=2004, le=2100)] = None,
) -> Any:
    if ctx is None and not settings.public_uploads:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Iniciá sesión con una cuenta uploader o usá una API key.")
    if ctx is not None and ctx.user.role not in ("uploader", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Tu cuenta no tiene permiso para importar.")
    who = str(ctx.user.id) if ctx else "anon"
    ratelimit.enforce(request, "import", settings.rate_limit_import_per_hour, 3600, key_suffix=who)
    meta = ImportMeta(
        title=title,
        guild_name=guild_name or None,
        guild_realm=guild_realm,
        region=region,
        faction=faction,
        visibility=visibility,
        utc_offset=utc_offset,
        default_year=default_year,
    )
    try:
        outcome = create_import(db, settings, file.file, file.filename, meta, ctx.user if ctx else None)
    except InvalidUpload as exc:
        code = status.HTTP_413_CONTENT_TOO_LARGE if "máximo" in str(exc) else status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
        raise HTTPException(code, str(exc)) from exc
    body = ImportAccepted(
        report_id=outcome.report.public_id,
        status=outcome.report.status,
        duplicate=outcome.duplicate,
        job_id=outcome.job.id if outcome.job else None,
        dataset=outcome.report.dataset,
        message="El archivo ya estaba importado: no se vuelve a procesar."
        if outcome.duplicate
        else "Archivo recibido: se procesa en segundo plano.",
    )
    if outcome.duplicate:
        return JSONResponse(body.model_dump(), status_code=200)
    return body
