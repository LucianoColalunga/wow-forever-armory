"""Subida por partes de punta a punta: la web la usa para pasar el límite de 4,5 MB de Vercel."""

from __future__ import annotations

import pytest

from app.importer import chunked
from tests.conftest import LOGS

pytestmark = pytest.mark.integration

API = "/api/v1/reports/uploads"


def _send_all(client, upload_id: str, data: bytes, size: int, headers: dict) -> None:  # type: ignore[no-untyped-def]
    for i, start in enumerate(range(0, len(data), size)):
        r = client.post(
            f"{API}/{upload_id}/chunks/{i}",
            content=data[start : start + size],
            headers={**headers, "Content-Type": "application/octet-stream"},
        )
        assert r.status_code == 200, r.text


def test_chunked_upload_end_to_end(client, make_user, drain, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(chunked, "CHUNK_BYTES", 2048)
    u = make_user()
    data = (LOGS / "basic_kill.txt").read_bytes()
    assert len(data) > 2048  # obliga a usar varias partes

    r = client.post(API, json={"file_name": "basic_kill.txt", "size": len(data)}, headers=u["headers"])
    assert r.status_code == 201, r.text
    started = r.json()
    assert started["chunk_size"] == 2048

    up_id = started["upload_id"]
    r = client.post(f"{API}/{up_id}/complete", headers=u["headers"])
    assert r.status_code == 409  # todavía no llegó nada

    _send_all(client, up_id, data, 2048, u["headers"])
    r = client.post(f"{API}/{up_id}/complete", data={"guild_name": "Prueba"}, headers=u["headers"])
    assert r.status_code == 202, r.text
    report_id = r.json()["report_id"]
    assert drain() >= 1
    rep = client.get(f"/api/v1/reports/{report_id}").json()
    assert rep["status"] == "processed"
    assert rep["guild"]["name"] == "Prueba"
    assert rep["source_file"]["original_name"] == "basic_kill.txt"
    assert any(f["kind"] == "encounter" for f in rep["fights"])

    # La sesión se borra al completar.
    assert client.post(f"{API}/{up_id}/complete", headers=u["headers"]).status_code == 404

    # El mismo archivo subido por partes otra vez se detecta como duplicado.
    r = client.post(API, json={"file_name": "otra.txt", "size": len(data)}, headers=u["headers"])
    up2 = r.json()["upload_id"]
    _send_all(client, up2, data, 2048, u["headers"])
    r = client.post(f"{API}/{up2}/complete", headers=u["headers"])
    assert r.status_code == 200 and r.json()["duplicate"] is True


def test_chunked_upload_requires_auth_and_ownership(client, make_user, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(chunked, "CHUNK_BYTES", 16)
    assert client.post(API, json={"file_name": "log.txt", "size": 10}).status_code == 401
    owner = make_user(email="owner@example.test")
    other = make_user(email="other@example.test")
    up_id = client.post(API, json={"file_name": "log.txt", "size": 10}, headers=owner["headers"]).json()["upload_id"]

    r = client.post(f"{API}/{up_id}/chunks/0", content=b"12345", headers=other["headers"])
    assert r.status_code == 404
    r = client.post(f"{API}/{up_id}/chunks/1", content=b"12345", headers=owner["headers"])
    assert r.status_code == 409
    r = client.post(f"{API}/{up_id}/chunks/0", content=b"x" * 17, headers=owner["headers"])
    assert r.status_code == 400  # parte más grande que el máximo
    r = client.post(API, json={"file_name": "virus.exe", "size": 10}, headers=owner["headers"])
    assert r.status_code == 415
    assert client.delete(f"{API}/{up_id}", headers=other["headers"]).status_code == 404
    assert client.delete(f"{API}/{up_id}", headers=owner["headers"]).status_code == 204
