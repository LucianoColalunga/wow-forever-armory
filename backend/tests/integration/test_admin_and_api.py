"""Correcciones admin auditadas, reprocesamiento, búsqueda, comparador, OpenAPI y health."""

from __future__ import annotations

import pytest

from tests.conftest import LOGS

pytestmark = pytest.mark.integration


def _seed(upload, drain, headers) -> str:  # type: ignore[no-untyped-def]
    r = upload("basic_kill.txt", (LOGS / "basic_kill.txt").read_bytes(), headers, guild_name="Prueba")
    drain()
    return r.json()["report_id"]


def _char(client, name: str) -> dict:  # type: ignore[no-untyped-def]
    return client.get("/api/v1/players", params={"q": name}).json()["items"][0]


def test_admin_class_correction_is_audited_and_propagated(client, make_user, upload, drain) -> None:  # type: ignore[no-untyped-def]
    adm = make_user("admin")
    _seed(upload, drain, adm["headers"])
    priest = _char(client, "Lumen")
    assert (priest["class_slug"], priest["spec"], priest["class_source"]) == ("priest", "holy", "role")
    no_reason = client.patch(
        f"/api/v1/admin/characters/{priest['id']}", json={"spec": "discipline"}, headers=adm["headers"]
    )
    assert no_reason.status_code == 422  # el motivo es obligatorio
    r = client.patch(
        f"/api/v1/admin/characters/{priest['id']}",
        json={"class_slug": "priest", "spec": "Disciplina", "reason": "Confirmado por la hermandad"},
        headers=adm["headers"],
    )
    assert r.status_code == 200 and r.json()["spec"] == "discipline" and r.json()["class_locked"] is True
    audit = client.get("/api/v1/admin/audit", params={"entity_type": "character"}, headers=adm["headers"]).json()
    entry = audit["items"][0]
    assert entry["action"] == "character.update" and entry["actor"] == adm["email"]
    assert entry["before"]["spec"] == "holy" and entry["after"]["spec"] == "discipline"
    assert entry["reason"] == "Confirmado por la hermandad"
    # La corrección se propaga a rankings
    boss = client.get("/api/v1/encounters").json()["items"][0]["encounter"]["id"]
    rk = client.get(f"/api/v1/rankings/pve/bosses/{boss}", params={"metric": "hps"}).json()
    assert rk["rows"][0]["spec"] == "discipline"
    # Reprocesar no pisa la corrección manual
    rid = client.get("/api/v1/reports").json()["items"][0]["public_id"]
    rp = client.post(
        f"/api/v1/admin/reports/{rid}/reprocess", json={"reason": "nueva versión del parser"}, headers=adm["headers"]
    )
    assert rp.status_code == 200
    drain()
    assert _char(client, "Lumen")["spec"] == "discipline"


def test_reprocess_is_idempotent(client, make_user, upload, drain) -> None:  # type: ignore[no-untyped-def]
    adm = make_user("admin")
    rid = _seed(upload, drain, adm["headers"])
    boss = client.get("/api/v1/encounters").json()["items"][0]["encounter"]["id"]
    before = client.get(f"/api/v1/rankings/pve/bosses/{boss}").json()["meta"]["records_used"]
    for _ in range(2):
        client.post(f"/api/v1/admin/reports/{rid}/reprocess", json={"reason": "idempotencia"}, headers=adm["headers"])
        drain()
    rep = client.get(f"/api/v1/reports/{rid}").json()
    assert rep["status"] == "processed" and len([f for f in rep["fights"] if f["kind"] == "encounter"]) == 1
    assert client.get(f"/api/v1/rankings/pve/bosses/{boss}").json()["meta"]["records_used"] == before


def test_exclude_fight_and_delete_report(client, make_user, upload, drain) -> None:  # type: ignore[no-untyped-def]
    adm = make_user("admin")
    rid = _seed(upload, drain, adm["headers"])
    fight = client.get("/api/v1/encounters").json()["items"][0]
    r = client.patch(
        f"/api/v1/admin/fights/{fight['id']}",
        json={"excluded": True, "reason": "log manipulado"},
        headers=adm["headers"],
    )
    assert r.status_code == 200 and r.json()["rankable"] is False
    assert client.get("/api/v1/rankings/pve", params={"method": "peak"}).json()["total"] == 0
    d = client.post(f"/api/v1/admin/reports/{rid}/delete", json={"reason": "pedido del autor"}, headers=adm["headers"])
    assert d.status_code == 200
    assert client.get(f"/api/v1/reports/{rid}").status_code == 404
    actions = {a["action"] for a in client.get("/api/v1/admin/audit", headers=adm["headers"]).json()["items"]}
    assert {"fight.update", "report.delete"} <= actions


def test_hidden_character_privacy(client, make_user, upload, drain) -> None:  # type: ignore[no-untyped-def]
    adm = make_user("admin")
    _seed(upload, drain, adm["headers"])
    mage = _char(client, "Ignis")
    client.patch(
        f"/api/v1/admin/characters/{mage['id']}",
        json={"hidden": True, "reason": "pedido de privacidad"},
        headers=adm["headers"],
    )
    assert client.get(f"/api/v1/players/{mage['id']}").status_code == 404
    assert client.get("/api/v1/players", params={"q": "Ignis"}).json()["total"] == 0
    fight = client.get("/api/v1/encounters").json()["items"][0]
    detail = client.get(f"/api/v1/encounters/{fight['id']}").json()
    assert "Ignis" not in {p["name"] for p in detail["participants"]}
    assert str(mage["id"]) not in detail["timeline"]["players_damage"]


def test_submission_moderation(client, make_user, upload, drain) -> None:  # type: ignore[no-untyped-def]
    adm = make_user("admin")
    _seed(upload, drain, adm["headers"])
    mage = _char(client, "Ignis")
    r = client.post(
        "/api/v1/submissions",
        json={"kind": "class_spec", "payload": {"character_id": mage["id"], "class_slug": "mage", "spec": "fire"}},
    )
    assert r.status_code == 202
    assert _char(client, "Ignis")["spec"] == "frost"  # no se aplica sin moderación
    sid = client.get("/api/v1/admin/submissions", headers=adm["headers"]).json()["items"][0]["id"]
    ok = client.post(
        f"/api/v1/admin/submissions/{sid}/review",
        json={"approve": True, "reason": "verificado"},
        headers=adm["headers"],
    )
    assert ok.status_code == 200 and ok.json()["applied"]["spec"] == "fire"
    assert _char(client, "Ignis")["spec"] == "fire"


def test_search_compare_guild_and_history(client, make_user, upload, drain) -> None:  # type: ignore[no-untyped-def]
    u = make_user()
    _seed(upload, drain, u["headers"])
    res = client.get("/api/v1/search", params={"q": "brak"}).json()
    assert res["players"][0]["name"] == "Brakka"
    fuzzy = client.get("/api/v1/search", params={"q": "Brakk"}).json()
    assert fuzzy["players"]
    assert client.get("/api/v1/search", params={"q": "hyjal"}).json()["instances"][0]["slug"] == "hyjal-summit"
    a, b = _char(client, "Brakka")["id"], _char(client, "Ignis")["id"]
    cmp_ = client.get("/api/v1/compare", params={"ids": f"{a},{b}"}).json()
    assert len(cmp_["players"]) == 2 and cmp_["partitions"][0]["shared_by_all"] is True
    assert client.get("/api/v1/compare", params={"ids": f"{a}"}).status_code == 422
    gid = client.get("/api/v1/guilds").json()["items"][0]["id"]
    g = client.get(f"/api/v1/guilds/{gid}").json()
    assert g["guild"]["name"] == "Prueba" and len(g["members"]) == 4
    assert g["members"][0]["membership"] == "inferida por reportes"
    assert g["progression"][0]["kills"] == 1
    raid = client.get("/api/v1/raids/hyjal-summit").json()
    assert raid["bosses"][0]["kills"] == 1
    hist = client.get(f"/api/v1/players/{a}/fights").json()
    assert hist["total"] == 1 and hist["items"][0]["performance"]["damage_done"] == 5500
    assert client.get("/api/v1/dungeons/blackmaw-hold").status_code == 200
    assert client.get("/api/v1/raids/no-existe").status_code == 404


def test_meta_endpoints(client) -> None:  # type: ignore[no-untyped-def]
    cat = client.get("/api/v1/meta/catalog").json()
    assert cat["mythic_plus"]["available"] is False
    keys = {m["key"]: m["status"] for m in cat["pvp_modes"]}
    assert keys["battlegrounds"] == "official" and keys["arenas"] == "unconfirmed"
    srcs = {s["key"]: s["status"] for s in client.get("/api/v1/meta/sources").json()}
    assert srcs["combat_log_file"] == "active" and srcs["blizzard_api"] == "unavailable"
    meth = client.get("/api/v1/meta/methodology").json()
    assert set(meth["methods"]) == {"peak", "consistency", "percentile"}
    assert client.get("/api/v1/meta/seasons").json()[0]["slug"] == "beta-2026"


def test_health_and_openapi(client) -> None:  # type: ignore[no-untyped-def]
    assert client.get("/api/health/live").json() == {"status": "ok"}
    ready = client.get("/api/health/ready")
    assert ready.status_code == 200 and ready.json()["checks"]["database"] == "ok"
    spec = client.get("/api/openapi.json").json()
    required = [
        "/api/v1/players",
        "/api/v1/players/{player_id}",
        "/api/v1/guilds/{guild_id}",
        "/api/v1/rankings/pvp",
        "/api/v1/rankings/pve",
        "/api/v1/rankings/pve/bosses/{boss_id}",
        "/api/v1/raids/{raid_id}",
        "/api/v1/dungeons/{dungeon_id}",
        "/api/v1/encounters/{fight_id}",
        "/api/v1/reports/{report_id}",
        "/api/v1/reports/import",
    ]
    for path in required:
        assert path in spec["paths"], path
    assert "post" in spec["paths"]["/api/v1/reports/import"]


def test_stale_and_empty_states(client) -> None:  # type: ignore[no-untyped-def]
    ov = client.get("/api/v1/stats/overview").json()
    assert ov["counts"]["reports"] == 0 and ov["meta"]["last_processed_at"] is None and ov["meta"]["stale"] is False
    rk = client.get("/api/v1/rankings/pve").json()
    assert rk["total"] == 0 and rk["rows"] == []
