"""Panel admin: todas las rutas exigen rol admin; cada corrección queda en audit_log con motivo."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import Field
from sqlalchemy import func, select

from app.api.deps import DB, AdminAuth, Page, SettingsDep
from app.core.ratelimit import client_ip
from app.core.security import hash_password, validate_password_strength
from app.importer.pipeline import enqueue_reprocess
from app.models import (
    AuditLog,
    Character,
    Encounter,
    Fight,
    Guild,
    ImportJob,
    Instance,
    Report,
    ReportIssue,
    Season,
    Submission,
    User,
    WorkerHeartbeat,
)
from app.parser.classes import CLASSES, normalize_class, normalize_spec
from app.rankings import cache
from app.schemas import Email, ReasonIn, UserOut
from app.services import audit
from app.services.queries import character_dict, count_of, fight_summary, instance_dict, paged

router = APIRouter(prefix="/admin", tags=["admin"])


def _snap(obj: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    out = {}
    for f in fields:
        v = getattr(obj, f)
        out[f] = v.isoformat() if isinstance(v, datetime) else v
    return out


@router.get("/overview", summary="Resumen operativo")
def overview(ctx: AdminAuth, db: DB) -> dict[str, Any]:
    jobs = dict(db.execute(select(ImportJob.status, func.count()).group_by(ImportJob.status)).all())
    reports = dict(db.execute(select(Report.status, func.count()).group_by(Report.status)).all())
    datasets = dict(db.execute(select(Report.dataset, func.count()).group_by(Report.dataset)).all())
    workers = db.scalars(select(WorkerHeartbeat).order_by(WorkerHeartbeat.last_seen_at.desc()).limit(5)).all()
    issues = db.execute(
        select(ReportIssue, Report.public_id)
        .join(Report, Report.id == ReportIssue.report_id)
        .where(ReportIssue.severity.in_(("error", "warning")))
        .order_by(ReportIssue.id.desc())
        .limit(15)
    ).all()
    pending = db.scalar(select(func.count()).select_from(Submission).where(Submission.status == "pending"))
    outliers = db.scalar(select(func.count()).select_from(Fight).where(Fight.unrankable_reason == "revision_outlier"))
    return {
        "jobs": jobs,
        "reports": reports,
        "datasets": datasets,
        "pending_submissions": pending,
        "outliers_pending": outliers,
        "workers": [
            {"worker_id": w.worker_id, "last_seen_at": w.last_seen_at, "processed": w.processed} for w in workers
        ],
        "recent_issues": [
            {
                "report_public_id": pid,
                "severity": i.severity,
                "code": i.code,
                "message": i.message,
                "fight_id": i.fight_id,
            }
            for i, pid in issues
        ],
        "versions": {d: cache.current_version(db, d) for d in ("real", "demo")},
        "admin": ctx.user.email,
    }


# ---------------------------------------------------------------------------
# Trabajos y reportes
# ---------------------------------------------------------------------------


@router.get("/jobs", summary="Trabajos de importación")
def jobs(
    ctx: AdminAuth,
    db: DB,
    page: Page,
    status: Literal["queued", "running", "succeeded", "failed", "dead"] | None = None,
) -> dict[str, Any]:
    pg, size = page
    q = select(ImportJob, Report.public_id, Report.title).join(Report, Report.id == ImportJob.report_id)
    if status:
        q = q.where(ImportJob.status == status)
    total = count_of(db, q)
    rows = db.execute(q.order_by(ImportJob.id.desc()).limit(size).offset((pg - 1) * size)).all()
    items = [
        {
            "id": j.id,
            "report_public_id": pid,
            "report_title": title,
            "kind": j.kind,
            "status": j.status,
            "attempts": j.attempts,
            "max_attempts": j.max_attempts,
            "last_error": j.last_error,
            "run_after": j.run_after,
            "created_at": j.created_at,
            "finished_at": j.finished_at,
        }
        for j, pid, title in rows
    ]
    return paged(items, pg, size, total)


@router.post("/jobs/{job_id}/retry", summary="Reintentar un trabajo fallido")
def retry_job(job_id: int, body: ReasonIn, request: Request, ctx: AdminAuth, db: DB) -> dict[str, Any]:
    job = db.get(ImportJob, job_id)
    if job is None:
        raise HTTPException(404, "Trabajo inexistente.")
    if job.status not in ("dead", "failed"):
        raise HTTPException(409, "Sólo se reintentan trabajos fallidos.")
    before = _snap(job, ("status", "attempts"))
    job.status, job.attempts, job.run_after, job.last_error = "queued", 0, datetime.now(UTC), None
    report = db.get(Report, job.report_id)
    if report:
        report.status = "queued"
    audit.record(
        db,
        actor=ctx.user,
        action="job.retry",
        entity_type="import_job",
        entity_id=job.id,
        before=before,
        after=_snap(job, ("status", "attempts")),
        reason=body.reason,
        ip=client_ip(request),
    )
    db.commit()
    return {"id": job.id, "status": job.status}


@router.get("/reports", summary="Todos los reportes (incluye privados y eliminados)")
def reports(
    ctx: AdminAuth,
    db: DB,
    page: Page,
    dataset: Literal["real", "demo"] | None = None,
    status: str | None = None,
    include_deleted: bool = False,
) -> dict[str, Any]:
    pg, size = page
    q = select(Report)
    if dataset:
        q = q.where(Report.dataset == dataset)
    if status:
        q = q.where(Report.status == status)
    if not include_deleted:
        q = q.where(Report.deleted_at.is_(None))
    total = count_of(db, q)
    rows = db.scalars(q.order_by(Report.id.desc()).limit(size).offset((pg - 1) * size)).all()
    items = [
        {
            "id": r.id,
            "public_id": r.public_id,
            "title": r.title,
            "dataset": r.dataset,
            "status": r.status,
            "visibility": r.visibility,
            "parser_version": r.parser_version,
            "created_at": r.created_at,
            "processed_at": r.processed_at,
            "deleted_at": r.deleted_at,
            "error": r.error,
            "stats": r.stats,
        }
        for r in rows
    ]
    return paged(items, pg, size, total)


@router.post("/reports/{public_id}/reprocess", summary="Reprocesar con la versión actual del parser")
def reprocess(
    public_id: str, body: ReasonIn, request: Request, ctx: AdminAuth, db: DB, settings: SettingsDep
) -> dict[str, Any]:
    r = db.scalar(select(Report).where(Report.public_id == public_id))
    if r is None or r.deleted_at is not None:
        raise HTTPException(404, "Reporte inexistente.")
    job = enqueue_reprocess(db, r, settings)
    db.flush()
    audit.record(
        db,
        actor=ctx.user,
        action="report.reprocess",
        entity_type="report",
        entity_id=r.public_id,
        before={"parser_version": r.parser_version},
        after={"job_id": job.id},
        reason=body.reason,
        ip=client_ip(request),
    )
    db.commit()
    return {"report_id": r.public_id, "job_id": job.id, "status": "queued"}


class ReportPatch(ReasonIn):
    visibility: Literal["public", "private"] | None = None
    title: str | None = Field(default=None, max_length=128)
    guild_id: int | None = None


@router.patch("/reports/{public_id}", summary="Editar visibilidad, título o hermandad de un reporte")
def patch_report(public_id: str, body: ReportPatch, request: Request, ctx: AdminAuth, db: DB) -> dict[str, Any]:
    r = db.scalar(select(Report).where(Report.public_id == public_id))
    if r is None:
        raise HTTPException(404, "Reporte inexistente.")
    fields = ("visibility", "title", "guild_id")
    before = _snap(r, fields)
    if body.visibility:
        r.visibility = body.visibility
    if body.title:
        r.title = body.title
    if body.guild_id is not None:
        g = db.get(Guild, body.guild_id)
        if g is None or g.dataset != r.dataset:
            raise HTTPException(422, "Hermandad inválida para este dataset.")
        r.guild_id = g.id
    audit.record(
        db,
        actor=ctx.user,
        action="report.update",
        entity_type="report",
        entity_id=r.public_id,
        before=before,
        after=_snap(r, fields),
        reason=body.reason,
        ip=client_ip(request),
    )
    db.flush()
    cache.rebuild_for_report(db, r)
    db.commit()
    return {"public_id": r.public_id, **_snap(r, fields)}


@router.post("/reports/{public_id}/delete", summary="Eliminar (baja lógica) un reporte")
def delete_report(public_id: str, body: ReasonIn, request: Request, ctx: AdminAuth, db: DB) -> dict[str, Any]:
    r = db.scalar(select(Report).where(Report.public_id == public_id))
    if r is None or r.deleted_at is not None:
        raise HTTPException(404, "Reporte inexistente.")
    r.deleted_at = datetime.now(UTC)
    audit.record(
        db,
        actor=ctx.user,
        action="report.delete",
        entity_type="report",
        entity_id=r.public_id,
        before={"deleted_at": None},
        after={"deleted_at": r.deleted_at.isoformat()},
        reason=body.reason,
        ip=client_ip(request),
    )
    db.flush()
    cache.rebuild_for_report(db, r)
    db.commit()
    return {"public_id": r.public_id, "deleted": True}


# ---------------------------------------------------------------------------
# Correcciones de datos
# ---------------------------------------------------------------------------


class CharacterPatch(ReasonIn):
    class_slug: str | None = None
    spec: str | None = None
    guild_id: int | None = Field(default=None, description="0 para quitar la hermandad")
    hidden: bool | None = Field(default=None, description="Ocultar por pedido de privacidad")


@router.get("/characters", summary="Buscar personajes (incluye ocultos)")
def characters(
    ctx: AdminAuth,
    db: DB,
    page: Page,
    q: Annotated[str | None, Query(max_length=64)] = None,
    dataset: Literal["real", "demo"] = "real",
) -> dict[str, Any]:
    pg, size = page
    qry = select(Character).where(Character.dataset == dataset)
    if q:
        qry = qry.where(Character.name.ilike(f"%{q.replace('%', '').replace('_', '')}%"))
    total = count_of(db, qry)
    rows = db.scalars(qry.order_by(Character.name).limit(size).offset((pg - 1) * size)).all()
    return paged(
        [{**character_dict(c), "hidden": c.hidden, "class_locked": c.class_locked} for c in rows], pg, size, total
    )


@router.patch("/characters/{character_id}", summary="Corregir clase/spec, hermandad o visibilidad")
def patch_character(
    character_id: int, body: CharacterPatch, request: Request, ctx: AdminAuth, db: DB
) -> dict[str, Any]:
    c = db.get(Character, character_id)
    if c is None:
        raise HTTPException(404, "Personaje inexistente.")
    fields = ("class_slug", "spec", "class_source", "class_locked", "guild_id", "guild_source", "hidden")
    before = _snap(c, fields)
    if body.class_slug is not None or body.spec is not None:
        cls = normalize_class(body.class_slug) if body.class_slug else c.class_slug
        if cls is None or cls not in CLASSES:
            raise HTTPException(422, "Clase inválida.")
        spec = normalize_spec(cls, body.spec) if body.spec else (c.spec if cls == c.class_slug else None)
        if body.spec and spec is None:
            raise HTTPException(422, "Spec inválida para esa clase.")
        c.class_slug, c.spec, c.class_source, c.class_confidence, c.class_locked = cls, spec, "admin", 1.0, True
        cache.sync_participant_classes(db, c)
    if body.guild_id is not None:
        if body.guild_id == 0:
            c.guild_id, c.guild_source = None, "admin"
        else:
            g = db.get(Guild, body.guild_id)
            if g is None or g.dataset != c.dataset:
                raise HTTPException(422, "Hermandad inválida para este dataset.")
            c.guild_id, c.guild_source = g.id, "admin"
    if body.hidden is not None:
        c.hidden = body.hidden
    audit.record(
        db,
        actor=ctx.user,
        action="character.update",
        entity_type="character",
        entity_id=c.id,
        before=before,
        after=_snap(c, fields),
        reason=body.reason,
        ip=client_ip(request),
    )
    db.flush()
    cache.rebuild_for_character(db, c)
    db.commit()
    return {**character_dict(c), "hidden": c.hidden, "class_locked": c.class_locked}


class FightPatch(ReasonIn):
    excluded: bool | None = Field(default=None, description="Excluir/incluir en rankings")
    approve_outlier: bool | None = Field(default=None, description="Aprobar un combate marcado como outlier")


@router.get("/fights/review", summary="Combates pendientes de revisión (outliers)")
def fights_review(ctx: AdminAuth, db: DB, page: Page) -> dict[str, Any]:
    pg, size = page
    q = select(Fight).where((Fight.unrankable_reason == "revision_outlier") | Fight.excluded_by_admin.is_(True))
    total = count_of(db, q)
    rows = db.scalars(q.order_by(Fight.id.desc()).limit(size).offset((pg - 1) * size)).all()
    return paged([fight_summary(f) | {"excluded_by_admin": f.excluded_by_admin} for f in rows], pg, size, total)


@router.patch("/fights/{fight_id}", summary="Excluir/incluir un combate o aprobar un outlier")
def patch_fight(fight_id: int, body: FightPatch, request: Request, ctx: AdminAuth, db: DB) -> dict[str, Any]:
    f = db.get(Fight, fight_id)
    if f is None:
        raise HTTPException(404, "Combate inexistente.")
    fields = ("rankable", "unrankable_reason", "excluded_by_admin")
    before = _snap(f, fields)
    if body.excluded is not None:
        f.excluded_by_admin = body.excluded
    if body.approve_outlier:
        if f.unrankable_reason != "revision_outlier":
            raise HTTPException(409, "El combate no está pendiente de revisión.")
        f.rankable, f.unrankable_reason = True, None
    audit.record(
        db,
        actor=ctx.user,
        action="fight.update",
        entity_type="fight",
        entity_id=f.id,
        before=before,
        after=_snap(f, fields),
        reason=body.reason,
        ip=client_ip(request),
    )
    db.flush()
    cache.rebuild_for_fight(db, f)
    db.commit()
    return fight_summary(f) | {"excluded_by_admin": f.excluded_by_admin}


class InstancePatch(ReasonIn):
    verification: Literal["official", "reported", "verified_by_admin"] | None = None
    game_instance_ids: list[int] | None = Field(default=None, max_length=10)


@router.patch("/instances/{instance_id}", summary="Verificar una instancia o asignarle IDs del juego")
def patch_instance(instance_id: int, body: InstancePatch, request: Request, ctx: AdminAuth, db: DB) -> dict[str, Any]:
    inst = db.get(Instance, instance_id)
    if inst is None:
        raise HTTPException(404, "Instancia inexistente.")
    fields = ("verification", "game_instance_ids")
    before = _snap(inst, fields)
    if body.verification:
        inst.verification = body.verification
    if body.game_instance_ids is not None:
        inst.game_instance_ids = sorted(set(body.game_instance_ids))
    audit.record(
        db,
        actor=ctx.user,
        action="instance.update",
        entity_type="instance",
        entity_id=inst.id,
        before=before,
        after=_snap(inst, fields),
        reason=body.reason,
        ip=client_ip(request),
    )
    db.flush()
    for ds in ("real", "demo"):
        cache.rebuild_all(db, ds)
    db.commit()
    return instance_dict(inst) | {"game_instance_ids": inst.game_instance_ids}  # type: ignore[operator]


class EncounterPatch(ReasonIn):
    instance_id: int | None = None
    name: str | None = Field(default=None, max_length=128)


@router.patch("/encounters/{encounter_id}", summary="Asociar un jefe a su instancia o corregir su nombre")
def patch_encounter(
    encounter_id: int, body: EncounterPatch, request: Request, ctx: AdminAuth, db: DB
) -> dict[str, Any]:
    enc = db.get(Encounter, encounter_id)
    if enc is None:
        raise HTTPException(404, "Jefe inexistente.")
    before = _snap(enc, ("instance_id", "name"))
    if body.instance_id is not None:
        if db.get(Instance, body.instance_id) is None:
            raise HTTPException(422, "Instancia inválida.")
        enc.instance_id = body.instance_id
        from sqlalchemy import update

        db.execute(update(Fight).where(Fight.encounter_id == enc.id).values(instance_id=body.instance_id))
    if body.name:
        enc.name = body.name
    audit.record(
        db,
        actor=ctx.user,
        action="encounter.update",
        entity_type="encounter",
        entity_id=enc.id,
        before=before,
        after=_snap(enc, ("instance_id", "name")),
        reason=body.reason,
        ip=client_ip(request),
    )
    db.flush()
    cache.rebuild_all(db, enc.dataset)
    db.commit()
    return {"id": enc.id, "name": enc.name, "instance_id": enc.instance_id}


class SeasonIn(ReasonIn):
    slug: str = Field(pattern=r"^[a-z0-9-]{3,64}$")
    name: str = Field(min_length=3, max_length=128)
    kind: Literal["pve", "pvp", "all"] = "all"
    starts_at: datetime
    ends_at: datetime | None = None
    is_official: bool = False
    source_note: str = Field(default="", max_length=500)


@router.post("/seasons", status_code=201, summary="Crear temporada/fase")
def create_season(body: SeasonIn, request: Request, ctx: AdminAuth, db: DB) -> dict[str, Any]:
    if db.scalar(select(Season).where(Season.slug == body.slug)):
        raise HTTPException(409, "Ya existe una temporada con ese slug.")
    s = Season(**body.model_dump(exclude={"reason"}))
    db.add(s)
    db.flush()
    audit.record(
        db,
        actor=ctx.user,
        action="season.create",
        entity_type="season",
        entity_id=s.id,
        before=None,
        after=body.model_dump(mode="json", exclude={"reason"}),
        reason=body.reason,
        ip=client_ip(request),
    )
    db.commit()
    return {"id": s.id, "slug": s.slug}


@router.post("/rankings/rebuild", summary="Reconstruir la caché de rankings de un dataset")
def rebuild(
    body: ReasonIn, request: Request, ctx: AdminAuth, db: DB, dataset: Literal["real", "demo"] = "real"
) -> dict[str, Any]:
    n = cache.rebuild_all(db, dataset)
    audit.record(
        db,
        actor=ctx.user,
        action="rankings.rebuild",
        entity_type="dataset",
        entity_id=dataset,
        before=None,
        after={"entries": n},
        reason=body.reason,
        ip=client_ip(request),
    )
    db.commit()
    return {"dataset": dataset, "entries": n}


# ---------------------------------------------------------------------------
# Aportes de usuarios
# ---------------------------------------------------------------------------


@router.get("/submissions", summary="Aportes pendientes de moderación")
def submissions(
    ctx: AdminAuth, db: DB, page: Page, status: Literal["pending", "approved", "rejected"] = "pending"
) -> dict[str, Any]:
    pg, size = page
    q = select(Submission).where(Submission.status == status)
    total = count_of(db, q)
    rows = db.scalars(q.order_by(Submission.id.desc()).limit(size).offset((pg - 1) * size)).all()
    return paged(
        [
            {
                "id": s.id,
                "kind": s.kind,
                "payload": s.payload,
                "status": s.status,
                "contact": s.contact,
                "created_at": s.created_at,
                "review_note": s.review_note,
            }
            for s in rows
        ],
        pg,
        size,
        total,
    )


class ReviewIn(ReasonIn):
    approve: bool


@router.post("/submissions/{submission_id}/review", summary="Aprobar (y aplicar) o rechazar un aporte")
def review_submission(submission_id: int, body: ReviewIn, request: Request, ctx: AdminAuth, db: DB) -> dict[str, Any]:
    s = db.get(Submission, submission_id)
    if s is None or s.status != "pending":
        raise HTTPException(404, "Aporte inexistente o ya revisado.")
    applied: dict[str, Any] | None = None
    if body.approve:
        applied = _apply_submission(db, s)
    s.status = "approved" if body.approve else "rejected"
    s.reviewed_by, s.reviewed_at, s.review_note = ctx.user.id, datetime.now(UTC), body.reason
    audit.record(
        db,
        actor=ctx.user,
        action=f"submission.{s.status}",
        entity_type="submission",
        entity_id=s.id,
        before={"status": "pending", "payload": s.payload},
        after={"status": s.status, "applied": applied},
        reason=body.reason,
        ip=client_ip(request),
    )
    db.commit()
    return {"id": s.id, "status": s.status, "applied": applied}


def _apply_submission(db: DB, s: Submission) -> dict[str, Any] | None:
    p = s.payload
    if s.kind == "character_guild":
        c = db.get(Character, int(p.get("character_id", 0)))
        g = db.get(Guild, int(p.get("guild_id", 0)))
        if c is None or g is None or c.dataset != g.dataset:
            raise HTTPException(422, "El aporte referencia un personaje o hermandad inválidos.")
        c.guild_id, c.guild_source = g.id, "submission"
        return {"character_id": c.id, "guild_id": g.id}
    if s.kind == "class_spec":
        c = db.get(Character, int(p.get("character_id", 0)))
        cls = normalize_class(str(p.get("class_slug", "")))
        if c is None or cls is None:
            raise HTTPException(422, "El aporte referencia un personaje o clase inválidos.")
        c.class_slug, c.spec = cls, normalize_spec(cls, str(p.get("spec", "")))
        c.class_source, c.class_confidence, c.class_locked = "admin", 1.0, True
        cache.sync_participant_classes(db, c)
        db.flush()
        cache.rebuild_for_character(db, c)
        return {"character_id": c.id, "class_slug": c.class_slug, "spec": c.spec}
    return None


# ---------------------------------------------------------------------------
# Usuarios y auditoría
# ---------------------------------------------------------------------------


class UserIn(ReasonIn):
    email: Email
    display_name: str = Field(min_length=2, max_length=64)
    role: Literal["admin", "uploader"]
    password: str = Field(min_length=12, max_length=256)


class UserPatch(ReasonIn):
    role: Literal["admin", "uploader"] | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=12, max_length=256)


@router.get("/users", response_model=list[UserOut], summary="Usuarios")
def users(ctx: AdminAuth, db: DB) -> list[User]:
    return list(db.scalars(select(User).order_by(User.id)).all())


@router.post("/users", status_code=201, response_model=UserOut, summary="Crear usuario")
def create_user(body: UserIn, request: Request, ctx: AdminAuth, db: DB) -> User:
    if (err := validate_password_strength(body.password)) is not None:
        raise HTTPException(422, err)
    if db.scalar(select(User).where(func.lower(User.email) == body.email.lower())):
        raise HTTPException(409, "Ya existe un usuario con ese email.")
    u = User(
        email=body.email.lower(),
        display_name=body.display_name,
        role=body.role,
        password_hash=hash_password(body.password),
        is_active=True,
    )
    db.add(u)
    db.flush()
    audit.record(
        db,
        actor=ctx.user,
        action="user.create",
        entity_type="user",
        entity_id=u.id,
        before=None,
        after={"email": u.email, "role": u.role},
        reason=body.reason,
        ip=client_ip(request),
    )
    db.commit()
    return u


@router.patch("/users/{user_id}", response_model=UserOut, summary="Cambiar rol, estado o contraseña")
def patch_user(user_id: int, body: UserPatch, request: Request, ctx: AdminAuth, db: DB) -> User:
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "Usuario inexistente.")
    if u.id == ctx.user.id and (body.role == "uploader" or body.is_active is False):
        raise HTTPException(409, "No podés quitarte el rol admin ni desactivarte a vos mismo.")
    before = {"role": u.role, "is_active": u.is_active}
    if body.role:
        u.role = body.role
    if body.is_active is not None:
        u.is_active = body.is_active
    if body.password:
        if (err := validate_password_strength(body.password)) is not None:
            raise HTTPException(422, err)
        u.password_hash = hash_password(body.password)
    after = {"role": u.role, "is_active": u.is_active, "password_changed": bool(body.password)}
    audit.record(
        db,
        actor=ctx.user,
        action="user.update",
        entity_type="user",
        entity_id=u.id,
        before=before,
        after=after,
        reason=body.reason,
        ip=client_ip(request),
    )
    db.commit()
    return u


@router.get("/audit", summary="Registro de auditoría")
def audit_log(
    ctx: AdminAuth, db: DB, page: Page, entity_type: str | None = None, entity_id: str | None = None
) -> dict[str, Any]:
    pg, size = page
    q = select(AuditLog)
    if entity_type:
        q = q.where(AuditLog.entity_type == entity_type)
    if entity_id:
        q = q.where(AuditLog.entity_id == entity_id)
    total = count_of(db, q)
    rows = db.scalars(q.order_by(AuditLog.id.desc()).limit(size).offset((pg - 1) * size)).all()
    return paged(
        [
            {
                "id": a.id,
                "actor": a.actor_label,
                "action": a.action,
                "entity_type": a.entity_type,
                "entity_id": a.entity_id,
                "before": a.before,
                "after": a.after,
                "reason": a.reason,
                "ip": a.ip,
                "created_at": a.created_at,
            }
            for a in rows
        ],
        pg,
        size,
        total,
    )
