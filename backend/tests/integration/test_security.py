"""Archivos inválidos, autenticación, autorización, CSRF, rate limiting e inyecciones."""

from __future__ import annotations

import io
import zipfile
from datetime import datetime

import pytest

from app.demo.logbuilder import LogBuilder, Unit, creature
from tests.conftest import LOGS

pytestmark = pytest.mark.integration

VALID = (LOGS / "basic_kill.txt").read_bytes()


def _zip(entries: dict[str, bytes], compression: int = zipfile.ZIP_DEFLATED) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


@pytest.mark.parametrize(
    ("name", "content", "fragment"),
    [
        ("log.txt", b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 64, "ejecutable"),
        ("log.txt", b"\x7fELF\x02\x01\x01" + b"\x00" * 64, "ELF"),
        ("log.txt", b"#!/bin/sh\nrm -rf /\n", "shebang"),
        ("log.exe", VALID, "Extensión"),
        ("log.txt", b"10/14/2026 21:00:00.000-3  A\x00B\n", "binarios"),
        ("log.txt", b"hola, esto no es un combat log\n", "combat log"),
        ("log.txt", b"<!DOCTYPE html><script>alert(1)</script>", "HTML"),
        ("log.txt", b"\xff\xfe\xfa\xfb invalid utf8 line\n", "UTF-8"),
        ("log.zip", b"PK\x03\x04garbage", "zip"),
        ("log.zip", VALID, "no es un zip"),
    ],
)
def test_invalid_files_are_rejected(make_user, upload, name, content, fragment) -> None:  # type: ignore[no-untyped-def]
    u = make_user()
    r = upload(name, content, u["headers"])
    assert r.status_code == 415, r.text
    assert fragment.lower() in r.json()["detail"].lower()


def test_empty_file_rejected(make_user, upload) -> None:  # type: ignore[no-untyped-def]
    r = upload("log.txt", b"", make_user()["headers"])
    assert r.status_code == 415 and "vacío" in r.json()["detail"]


@pytest.mark.parametrize(
    ("entries", "fragment"),
    [
        ({"a.txt": VALID, "b.txt": VALID}, "exactamente un"),
        ({"virus.exe": b"MZ" + b"\x00" * 100}, ".txt o .log"),
        ({"../../etc/passwd.txt": VALID}, "rutas"),
        ({"bomb.txt": VALID[:200] + b"A" * 5_000_000}, "compresión"),
    ],
)
def test_malicious_zips_rejected(make_user, upload, entries, fragment) -> None:  # type: ignore[no-untyped-def]
    r = upload("logs.zip", _zip(entries), make_user()["headers"])
    assert r.status_code in (413, 415), r.text
    assert fragment.lower() in r.json()["detail"].lower()


def test_upload_too_large(make_user, upload) -> None:  # type: ignore[no-untyped-def]
    from app.core.config import get_settings

    s = get_settings()
    old = s.max_upload_mb
    s.max_upload_mb = 1
    try:
        big = VALID + b"10/14/2026 21:02:00.000-3  SPELL_CAST_SUCCESS," + b"x" * (1024 * 1024 + 10) + b"\n"
        r = upload("big.txt", big, make_user()["headers"])
        assert r.status_code == 413
    finally:
        s.max_upload_mb = old


def test_import_requires_auth_and_role(client, make_user, upload) -> None:  # type: ignore[no-untyped-def]
    assert upload("log.txt", VALID, {}).status_code == 401
    assert upload("log.txt", VALID, {"Authorization": "Bearer wfa_falsa_falsa_falsa_falsa"}).status_code == 401


def test_admin_requires_admin_role(client, make_user) -> None:  # type: ignore[no-untyped-def]
    assert client.get("/api/v1/admin/overview").status_code == 401
    up = make_user("uploader")
    assert client.get("/api/v1/admin/overview", headers=up["headers"]).status_code == 403
    adm = make_user("admin")
    assert client.get("/api/v1/admin/overview", headers=adm["headers"]).status_code == 200


def test_session_login_csrf_and_logout(client, make_user) -> None:  # type: ignore[no-untyped-def]
    adm = make_user("admin")
    bad = client.post("/api/v1/auth/login", json={"email": adm["email"], "password": "incorrecta"})
    assert bad.status_code == 401
    ok = client.post("/api/v1/auth/login", json={"email": adm["email"], "password": adm["password"]})
    assert ok.status_code == 200
    set_cookie = ok.headers.get("set-cookie", "")
    assert "wfa_session=" in set_cookie and "HttpOnly" in set_cookie and "SameSite=lax" in set_cookie
    csrf = ok.json()["csrf_token"]
    assert client.get("/api/v1/auth/me").json()["role"] == "admin"
    # Escritura con cookie pero sin token CSRF → 403
    body = {"reason": "prueba de csrf"}
    assert client.post("/api/v1/admin/rankings/rebuild", json=body).status_code == 403
    assert client.post("/api/v1/admin/rankings/rebuild", json=body, headers={"X-CSRF-Token": "otro"}).status_code == 403
    assert client.post("/api/v1/admin/rankings/rebuild", json=body, headers={"X-CSRF-Token": csrf}).status_code == 200
    assert client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_login_is_rate_limited(client, make_user) -> None:  # type: ignore[no-untyped-def]
    adm = make_user("admin")
    codes = [
        client.post("/api/v1/auth/login", json={"email": adm["email"], "password": "x"}).status_code for _ in range(7)
    ]
    assert codes[:5] == [401] * 5 and codes[-1] == 429


def test_hostile_names_are_stored_as_text(client, make_user, upload, drain) -> None:  # type: ignore[no-untyped-def]
    evil = Unit("Player-5000-0000BEEF", "<script>alert(1)</script>-Realm", "0x514")
    sqli = Unit("Player-5000-0000CAFE", "x' OR 1=1; DROP TABLE users;---Realm", "0x514")
    boss = creature(5, 5, "Boss")
    b = LogBuilder(datetime(2026, 10, 3, 20, 0))
    b.wait(1000).encounter_start(5, "Boss", 3, 20, 1)
    b.wait(1000).spell_damage(evil, boss, 116, "Frostbolt", 1000)
    b.wait(1000).spell_damage(sqli, boss, 116, "Frostbolt", 900)
    b.wait(20000).encounter_end(5, "Boss", 3, 20, True, 22000)
    assert upload("evil.txt", b.text(), make_user()["headers"]).status_code == 202
    drain()
    res = client.get("/api/v1/search", params={"q": "<script>"})
    assert res.status_code == 200 and res.headers["content-type"].startswith("application/json")
    names = {p["name"] for p in client.get("/api/v1/players").json()["items"]}
    assert "<script>alert(1)</script>" in names and "x' OR 1=1; DROP TABLE users;" in names
    assert client.get("/api/v1/search", params={"q": "' OR '1'='1"}).status_code == 200
    assert client.get("/api/v1/players", params={"q": "%_%"}).json()["total"] == 0
    assert (
        client.get("/api/v1/admin/users", headers=make_user("admin", email="a2@x.test")["headers"]).status_code == 200
    )


def test_security_headers(client) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/api/health/live")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in r.headers["content-security-policy"]
    assert r.headers.get("x-request-id")


def test_invalid_query_params(client) -> None:  # type: ignore[no-untyped-def]
    assert client.get("/api/v1/rankings/pve", params={"metric": "nada"}).status_code == 422
    assert client.get("/api/v1/players", params={"page_size": 1000}).status_code == 422
    assert client.get("/api/v1/players", params={"dataset": "todo"}).status_code == 422
