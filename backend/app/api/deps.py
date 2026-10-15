"""Dependencias comunes: base de datos, autenticación, autorización y CSRF."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.core.config import Settings, get_settings
from app.core.security import constant_time_equals, sha256_hex
from app.db.session import get_db
from app.models import ApiKey, Session, User

SESSION_COOKIE = "wfa_session"
CSRF_COOKIE = "wfa_csrf"
CSRF_HEADER = "x-csrf-token"

DB = Annotated[DbSession, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
Dataset = Annotated[
    Literal["real", "demo"],
    Query(description="Conjunto de datos: `real` (por defecto) o `demo` (fixtures sintéticos). Nunca se mezclan."),
]


class AuthContext:
    def __init__(self, user: User, via: str, session: Session | None = None) -> None:
        self.user = user
        self.via = via  # session | api_key
        self.session = session


def _from_api_key(db: DbSession, raw: str) -> AuthContext | None:
    key = db.scalar(select(ApiKey).where(ApiKey.key_hash == sha256_hex(raw), ApiKey.revoked_at.is_(None)))
    if key is None or not key.user.is_active:
        return None
    key.last_used_at = datetime.now(UTC)
    db.commit()
    return AuthContext(key.user, "api_key")


def _from_session(db: DbSession, token: str) -> AuthContext | None:
    sess = db.scalar(select(Session).where(Session.token_hash == sha256_hex(token), Session.revoked_at.is_(None)))
    if sess is None or sess.expires_at <= datetime.now(UTC) or not sess.user.is_active:
        return None
    return AuthContext(sess.user, "session", sess)


def optional_auth(request: Request, db: DB) -> AuthContext | None:
    auth = request.headers.get("authorization", "")
    api_key = request.headers.get("x-api-key") or (auth[7:].strip() if auth.lower().startswith("bearer ") else "")
    if api_key:
        ctx = _from_api_key(db, api_key)
        if ctx is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API key inválida o revocada.")
        return ctx
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        ctx = _from_session(db, token)
        if ctx is not None and request.method not in ("GET", "HEAD", "OPTIONS"):
            _check_csrf(request, ctx)
        return ctx
    return None


def _check_csrf(request: Request, ctx: AuthContext) -> None:
    """Double submit: la cabecera debe coincidir con el token CSRF ligado a la sesión."""
    header = request.headers.get(CSRF_HEADER, "")
    if not header or ctx.session is None or not constant_time_equals(sha256_hex(header), ctx.session.csrf_hash):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Token CSRF inválido o ausente.")


OptionalAuth = Annotated[AuthContext | None, Depends(optional_auth)]


def require_user(ctx: OptionalAuth) -> AuthContext:
    if ctx is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Necesitás iniciar sesión.")
    return ctx


def require_uploader(ctx: Annotated[AuthContext, Depends(require_user)]) -> AuthContext:
    if ctx.user.role not in ("uploader", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Tu cuenta no tiene permiso para importar.")
    return ctx


def require_admin(ctx: Annotated[AuthContext, Depends(require_user)]) -> AuthContext:
    if ctx.user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Acceso restringido a administradores.")
    return ctx


UserAuth = Annotated[AuthContext, Depends(require_user)]
UploaderAuth = Annotated[AuthContext, Depends(require_uploader)]
AdminAuth = Annotated[AuthContext, Depends(require_admin)]


def pagination(
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> tuple[int, int]:
    return page, page_size


Page = Annotated[tuple[int, int], Depends(pagination)]
