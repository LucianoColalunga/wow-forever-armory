"""Seguridad sin base de datos: IP del cliente detrás de proxies, redacción de logs, contraseñas y validación."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from starlette.requests import Request

from app.core.config import get_settings
from app.core.logging import redact
from app.core.ratelimit import SlidingWindowLimiter, client_ip
from app.core.security import hash_password, validate_password_strength, verify_password
from app.importer import validation


def _req(peer: str, xff: str | None = None) -> Request:
    headers = [(b"x-forwarded-for", xff.encode())] if xff else []
    return Request({"type": "http", "client": (peer, 1234), "headers": headers, "method": "GET", "path": "/"})


def test_client_ip_ignores_forwarded_header_from_untrusted_peer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "trusted_proxies", "")
    assert client_ip(_req("203.0.113.5", "1.2.3.4")) == "203.0.113.5"


def test_client_ip_uses_forwarded_header_from_trusted_cidr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "trusted_proxies", "172.16.0.0/12")
    # El cliente intenta falsificar el primer valor; cuenta el último no confiable.
    assert client_ip(_req("172.18.0.4", "6.6.6.6, 198.51.100.7")) == "198.51.100.7"
    assert client_ip(_req("172.18.0.4", "198.51.100.7, 172.18.0.9")) == "198.51.100.7"


def _req_secret(peer: str, secret: str, ip: str) -> Request:
    headers = [(b"x-wfa-proxy-secret", secret.encode()), (b"x-wfa-client-ip", ip.encode())]
    return Request({"type": "http", "client": (peer, 1234), "headers": headers, "method": "GET", "path": "/"})


def test_client_ip_from_proxy_with_shared_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "trusted_proxies", "")
    monkeypatch.setattr(get_settings(), "proxy_shared_secret", "secreto-de-prueba")
    assert client_ip(_req_secret("10.1.2.3", "secreto-de-prueba", "198.51.100.7")) == "198.51.100.7"
    # Sin el secreto correcto o con una IP inválida se usa el par inmediato.
    assert client_ip(_req_secret("10.1.2.3", "otro", "198.51.100.7")) == "10.1.2.3"
    assert client_ip(_req_secret("10.1.2.3", "secreto-de-prueba", "no-es-ip")) == "10.1.2.3"
    monkeypatch.setattr(get_settings(), "proxy_shared_secret", None)
    assert client_ip(_req_secret("10.1.2.3", "secreto-de-prueba", "198.51.100.7")) == "10.1.2.3"


def test_client_ip_from_platform_edge_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "trusted_proxies", "")
    monkeypatch.setattr(get_settings(), "client_ip_header", "cf-connecting-ip")
    req = Request(
        {
            "type": "http",
            "client": ("10.9.8.7", 1),
            "headers": [(b"cf-connecting-ip", b"198.51.100.7")],
            "method": "GET",
            "path": "/",
        }
    )
    assert client_ip(req) == "198.51.100.7"
    bad = Request(
        {
            "type": "http",
            "client": ("10.9.8.7", 1),
            "headers": [(b"cf-connecting-ip", b"x")],
            "method": "GET",
            "path": "/",
        }
    )
    assert client_ip(bad) == "10.9.8.7"
    monkeypatch.setattr(get_settings(), "client_ip_header", "")
    assert client_ip(req) == "10.9.8.7"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("postgres://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgresql://u:p@h/db?sslmode=require", "postgresql+psycopg://u:p@h/db?sslmode=require"),
        ("postgresql+psycopg://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
    ],
)
def test_database_url_is_normalized(raw: str, expected: str) -> None:
    from app.core.config import Settings

    assert Settings(database_url=raw).database_url == expected


def test_sliding_window_limiter() -> None:
    lim = SlidingWindowLimiter()
    assert [lim.hit("k", 2, 60)[0] for _ in range(3)] == [True, True, False]
    assert lim.hit("k", 2, 60)[1] >= 1


def test_logs_redact_secrets() -> None:
    line = (
        'password="hunter2" Authorization: Bearer abc.def token=xyz postgresql+psycopg://u:secreta@db/x wfa_' + "a" * 30
    )
    out = redact(line)
    for secret in ("hunter2", "abc.def", "xyz", "secreta", "a" * 30):
        assert secret not in out


def test_password_hashing_and_policy() -> None:
    h = hash_password("Correcta-Clave-2026")
    assert h.startswith("$argon2id$") and verify_password(h, "Correcta-Clave-2026")
    assert not verify_password(h, "otra")
    assert validate_password_strength("corta") is not None
    assert validate_password_strength("todominusculas123") is not None
    assert validate_password_strength("Correcta-Clave-2026") is None


def test_safe_filename() -> None:
    assert validation.safe_filename("../../etc/passwd") == "passwd"
    assert validation.safe_filename("C:\\Logs\\Wo<w>Log|.txt") == "WowLog.txt"
    assert validation.safe_filename("") == "combatlog.txt"


def test_zip_bomb_detected_before_extracting(tmp_path: Path) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("log.txt", b"A" * 3_000_000)
    src = tmp_path / "bomb.zip"
    src.write_bytes(buf.getvalue())
    saved = validation.SavedUpload(src, src.stat().st_size)
    with pytest.raises(validation.InvalidUpload, match="compresión"):
        validation.validate_saved(saved, "bomb.zip", tmp_path, max_uncompressed=10_000_000, max_ratio=40)
