"""Hash de contraseñas (Argon2id), tokens de sesión y API keys.

- Las contraseñas se guardan sólo como hash Argon2id.
- Los tokens de sesión y las API keys se guardan como SHA-256 (nunca en claro).
- Las comparaciones usan ``hmac.compare_digest``.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()

API_KEY_PREFIX = "wfa_"
MIN_PASSWORD_LENGTH = 12


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def validate_password_strength(password: str) -> str | None:
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres."
    if password.lower() == password or password.upper() == password or not any(c.isdigit() for c in password):
        return "La contraseña debe combinar mayúsculas, minúsculas y números."
    return None


def new_token() -> str:
    return secrets.token_urlsafe(32)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def new_api_key() -> tuple[str, str, str]:
    """Devuelve (clave completa para mostrar una sola vez, prefijo visible, hash a guardar)."""
    raw = API_KEY_PREFIX + secrets.token_urlsafe(32)
    return raw, raw[:12], sha256_hex(raw)


# Hash de referencia para igualar tiempos cuando el usuario no existe (evita enumeración por timing).
DUMMY_HASH = _hasher.hash("timing-equalizer-not-a-real-password")
