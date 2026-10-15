from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.deps import CSRF_COOKIE, DB, SESSION_COOKIE, SettingsDep, UserAuth
from app.core import ratelimit
from app.core.security import (
    DUMMY_HASH,
    hash_password,
    needs_rehash,
    new_api_key,
    new_token,
    sha256_hex,
    verify_password,
)
from app.models import ApiKey, Session, User
from app.schemas import LoginIn, LoginOut, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_cookies(response: Response, settings: SettingsDep, token: str, csrf: str, max_age: int) -> None:
    common = {"secure": settings.cookie_secure, "samesite": "lax", "path": "/", "max_age": max_age}
    if settings.cookie_domain:
        common["domain"] = settings.cookie_domain
    response.set_cookie(SESSION_COOKIE, token, httponly=True, **common)  # type: ignore[arg-type]
    response.set_cookie(CSRF_COOKIE, csrf, httponly=False, **common)  # type: ignore[arg-type]


@router.post("/login", response_model=LoginOut, summary="Iniciar sesión (cookie HttpOnly + token CSRF)")
def login(body: LoginIn, request: Request, response: Response, db: DB, settings: SettingsDep) -> LoginOut:
    email = body.email.lower()
    ratelimit.enforce(request, "login", settings.rate_limit_login_per_15min, 15 * 60, key_suffix=email)
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    # Siempre se verifica un hash para no revelar por tiempo si el usuario existe.
    ok = verify_password(user.password_hash if user else DUMMY_HASH, body.password)
    if not user or not ok or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email o contraseña incorrectos.")
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    token, csrf = new_token(), new_token()
    ttl = timedelta(hours=settings.session_ttl_hours)
    db.add(
        Session(
            user_id=user.id,
            token_hash=sha256_hex(token),
            csrf_hash=sha256_hex(csrf),
            expires_at=datetime.now(UTC) + ttl,
            ip=ratelimit.client_ip(request),
            user_agent=(request.headers.get("user-agent") or "")[:255],
        )
    )
    user.last_login_at = datetime.now(UTC)
    db.commit()
    _set_cookies(response, settings, token, csrf, int(ttl.total_seconds()))
    return LoginOut(user=UserOut.model_validate(user), csrf_token=csrf)


@router.post("/logout", status_code=204, summary="Cerrar sesión")
def logout(ctx: UserAuth, response: Response, db: DB) -> Response:
    if ctx.session is not None:
        ctx.session.revoked_at = datetime.now(UTC)
        db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    response.status_code = 204
    return response


@router.get("/me", response_model=UserOut, summary="Usuario actual")
def me(ctx: UserAuth) -> UserOut:
    return UserOut.model_validate(ctx.user)


class ApiKeyIn(BaseModel):
    name: str = Field(min_length=2, max_length=64)


@router.get("/api-keys", summary="Mis API keys (sin la clave)")
def list_keys(ctx: UserAuth, db: DB) -> list[dict[str, object]]:
    keys = db.scalars(select(ApiKey).where(ApiKey.user_id == ctx.user.id).order_by(ApiKey.id.desc())).all()
    return [
        {
            "id": k.id,
            "name": k.name,
            "prefix": k.prefix,
            "created_at": k.created_at,
            "last_used_at": k.last_used_at,
            "revoked": k.revoked_at is not None,
        }
        for k in keys
    ]


@router.post("/api-keys", status_code=201, summary="Crear API key (se muestra una sola vez)")
def create_key(body: ApiKeyIn, ctx: UserAuth, db: DB) -> dict[str, object]:
    if ctx.user.role not in ("uploader", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Sólo cuentas uploader o admin pueden crear API keys.")
    raw, prefix, digest = new_api_key()
    key = ApiKey(user_id=ctx.user.id, name=body.name, prefix=prefix, key_hash=digest)
    db.add(key)
    db.commit()
    return {
        "id": key.id,
        "name": key.name,
        "prefix": prefix,
        "api_key": raw,
        "warning": "Guardala ahora: no se puede volver a mostrar.",
    }


@router.delete("/api-keys/{key_id}", status_code=204, summary="Revocar API key propia")
def revoke_key(key_id: int, ctx: UserAuth, db: DB) -> Response:
    key = db.get(ApiKey, key_id)
    if key is None or key.user_id != ctx.user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API key inexistente.")
    key.revoked_at = datetime.now(UTC)
    db.commit()
    return Response(status_code=204)
