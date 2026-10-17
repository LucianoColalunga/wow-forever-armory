"""Importación de punta a punta: API → cola → parser → base → rankings."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime

import pytest

from app.demo.logbuilder import LogBuilder, creature, player
from app.parser.parser import PARSER_VERSION
from tests.conftest import LOGS

pytestmark = pytest.mark.integration
EXPECTED = json.loads((LOGS / "expected.json").read_text(encoding="utf-8"))


def _import(upload, drain, name: str, headers: dict, **form: str) -> str:  # type: ignore[no-untyped-def]
    r = upload(name, (LOGS / name).read_bytes(), headers, **form)
    assert r.status_code == 202, r.text
    assert drain() >= 1
    return r.json()["report_id"]


def test_import_basic_kill_end_to_end(client, make_user, upload, drain) -> None:  # type: ignore[no-untyped-def]
    u = make_user()
    rid = _import(upload, drain, "basic_kill.txt", u["headers"], guild_name="Prueba", guild_realm="Testrealm")
    rep = client.get(f"/api/v1/reports/{rid}").json()
    assert rep["status"] == "processed"
    assert rep["parser_version"] == PARSER_VERSION
    assert rep["dialect"]["key"] == "forever"
    assert rep["source_file"]["original_name"] == "basic_kill.txt"
    assert len(rep["source_file"]["sha256"]) == 64
    fights = [f for f in rep["fights"] if f["kind"] == "encounter"]
    assert len(fights) == 1 and fights[0]["first_line"] == 3

    detail = client.get(f"/api/v1/encounters/{fights[0]['id']}").json()
    by_name = {p["name"]: p for p in detail["participants"]}
    exp = EXPECTED["basic_kill.txt"]["fights"][0]["players"]
    assert by_name["Brakka"]["damage_done"] == exp["Player-5000-00000001"]["damage_done"]
    assert by_name["Brakka"]["overkill"] == 1500
    assert by_name["Lumen"]["healing_effective"] == 3500
    assert by_name["Lumen"]["absorbs_provided"] == 1700
    assert by_name["Lumen"]["overhealing"] == 1500
    assert by_name["Ignis"]["deaths"] == 1
    assert by_name["Arrowyn"]["deaths"] == 0
    assert detail["source"]["file_sha256"] == rep["source_file"]["sha256"]
    assert sum(detail["timeline"]["raid_damage"]) == 11000

    # Ranking por jefe: 4 jugadores en la partición (dificultad 3, 20 jugadores)
    boss_id = detail["encounter"]["id"]
    rk = client.get(f"/api/v1/rankings/pve/bosses/{boss_id}", params={"metric": "dps"}).json()
    assert rk["meta"]["records_used"] == 4
    assert rk["rows"][0]["name"] == "Brakka" and rk["rows"][0]["value"] == pytest.approx(91.67, abs=0.01)
    # Perfil de jugador y guild inferida del reporte
    pid = by_name["Brakka"]["character_id"]
    prof = client.get(f"/api/v1/players/{pid}").json()
    assert prof["character"]["class_slug"] == "warrior" and prof["character"]["spec"] == "arms"
    assert prof["character"]["guild"]["name"] == "Prueba"
    assert prof["summary"]["kills"] == 1


def test_same_file_twice_is_not_reprocessed(client, make_user, upload, drain) -> None:  # type: ignore[no-untyped-def]
    u = make_user()
    rid = _import(upload, drain, "basic_kill.txt", u["headers"])
    again = upload("otro-nombre.txt", (LOGS / "basic_kill.txt").read_bytes(), u["headers"])
    assert again.status_code == 200
    body = again.json()
    assert body["duplicate"] is True and body["report_id"] == rid and body["job_id"] is None
    assert drain() == 0
    ov = client.get("/api/v1/stats/overview").json()
    assert ov["counts"]["reports"] == 1 and ov["counts"]["kills"] == 1


def _shifted_copy(seconds: int) -> str:
    """El mismo combate registrado por otra persona: reloj distinto y un evento menos."""
    text = (LOGS / "wipe_then_kill.txt").read_text(encoding="utf-8").splitlines()
    out = []
    from datetime import timedelta

    for line in text:
        ts, rest = line.split("  ", 1)
        date, time_ = ts.split(" ")
        dt = datetime.strptime(f"{date} {time_[:12]}", "%m/%d/%Y %H:%M:%S.%f") + timedelta(seconds=seconds)
        off = time_[12:]
        out.append(
            f"{dt.month}/{dt.day}/{dt.year} {dt.hour}:{dt.minute:02d}:{dt.second:02d}."
            f"{dt.microsecond // 1000:03d}{off}  {rest}"
        )
    return "\n".join(out) + "\n"


def test_duplicate_fights_from_other_logger_do_not_inflate(client, make_user, upload, drain) -> None:  # type: ignore[no-untyped-def]
    u = make_user()
    _import(upload, drain, "wipe_then_kill.txt", u["headers"])
    boss = client.get("/api/v1/encounters", params={"kind": "encounter"}).json()["items"][0]["encounter"]["id"]
    before = client.get(f"/api/v1/rankings/pve/bosses/{boss}").json()["meta"]["records_used"]
    r = upload("otro-logger.txt", _shifted_copy(7), u["headers"])
    assert r.status_code == 202
    drain()
    rep = client.get(f"/api/v1/reports/{r.json()['report_id']}").json()
    assert all(f["duplicate_of_id"] is not None for f in rep["fights"])
    assert {i["code"] for i in rep["issues"]} >= {"duplicate_fight"}
    after = client.get(f"/api/v1/rankings/pve/bosses/{boss}").json()["meta"]["records_used"]
    assert after == before
    hist = client.get("/api/v1/encounters", params={"kind": "encounter"}).json()
    assert hist["total"] == 2  # wipe + kill, sin duplicados
    hist_all = client.get("/api/v1/encounters", params={"kind": "encounter", "include_duplicates": True}).json()
    assert hist_all["total"] == 4


def test_truncated_log_is_flagged_and_not_ranked(client, make_user, upload, drain) -> None:  # type: ignore[no-untyped-def]
    u = make_user()
    rid = _import(upload, drain, "truncated.txt", u["headers"])
    rep = client.get(f"/api/v1/reports/{rid}").json()
    assert rep["fights"][0]["rankable"] is False
    assert rep["fights"][0]["unrankable_reason"] == "incompleto"
    assert any(i["code"] == "incomplete_fight" and i["severity"] == "error" for i in rep["issues"])
    rk = client.get("/api/v1/rankings/pve", params={"method": "peak"}).json()
    assert rk["total"] == 0


def test_zip_upload_is_equivalent_to_text(client, make_user, upload, drain) -> None:  # type: ignore[no-untyped-def]
    u = make_user()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("WoWCombatLog-101426_210000.txt", (LOGS / "basic_kill.txt").read_text(encoding="utf-8"))
    r = upload("logs.zip", buf.getvalue(), u["headers"])
    assert r.status_code == 202, r.text
    drain()
    same = upload("basic_kill.txt", (LOGS / "basic_kill.txt").read_bytes(), u["headers"])
    assert same.status_code == 200 and same.json()["duplicate"] is True


def test_demo_file_never_enters_as_real(client, make_user, upload, drain) -> None:  # type: ignore[no-untyped-def]
    u = make_user()
    b = LogBuilder(datetime(2026, 10, 1, 20, 0), build="1.60.1-DEMO")
    a, boss = player(77, "Demonio"), creature(990001, 1, "Demo Boss (demo)")
    b.wait(1000).encounter_start(990001, "Demo Boss (demo)", 3, 20, 1)
    b.wait(1000).spell_damage(a, boss, 116, "Frostbolt", 1000)
    b.wait(20000).encounter_end(990001, "Demo Boss (demo)", 3, 20, True, 21000)
    r = upload("demo.txt", b.text(), u["headers"])
    assert r.status_code == 202 and r.json()["dataset"] == "demo"
    drain()
    assert client.get("/api/v1/players", params={"q": "Demonio"}).json()["total"] == 0
    demo = client.get("/api/v1/players", params={"q": "Demonio", "dataset": "demo"}).json()
    assert demo["total"] == 1 and demo["meta"]["is_demo"] is True
    # Un nombre con "Demo" en un log real NO lo convierte en demo
    b2 = LogBuilder(datetime(2026, 10, 2, 20, 0))
    b2.wait(1000).encounter_start(1, "Real Boss", 3, 20, 1)
    b2.wait(1000).spell_damage(player(78, "Demoledor"), creature(1, 1, "Real Boss"), 116, "Frostbolt", 1000)
    b2.wait(20000).encounter_end(1, "Real Boss", 3, 20, True, 21000)
    r2 = upload("real.txt", b2.text(), u["headers"])
    assert r2.json()["dataset"] == "real"


def test_private_report_is_hidden_from_public(client, make_user, upload, drain) -> None:  # type: ignore[no-untyped-def]
    u = make_user()
    rid = _import(upload, drain, "basic_kill.txt", u["headers"], visibility="private")
    assert client.get(f"/api/v1/reports/{rid}").status_code == 404
    assert client.get(f"/api/v1/reports/{rid}", headers=u["headers"]).status_code == 200
    assert client.get("/api/v1/stats/overview").json()["counts"]["kills"] == 0
    assert client.get("/api/v1/rankings/pve", params={"method": "peak"}).json()["total"] == 0


def test_worker_retries_then_marks_dead(client, make_user, upload, drain, db) -> None:  # type: ignore[no-untyped-def]
    from app.core.config import get_settings
    from app.models import ImportJob, Report, SourceFile

    u = make_user()
    r = upload("basic_kill.txt", (LOGS / "basic_kill.txt").read_bytes(), u["headers"])
    rid = r.json()["report_id"]
    # Simula pérdida del archivo de origen: cada intento falla.
    sf = db.query(SourceFile).one()
    (get_settings().storage_dir / sf.stored_path).unlink()
    for _ in range(4):
        drain()
    db.expire_all()
    job = db.query(ImportJob).one()
    rep = db.query(Report).filter_by(public_id=rid).one()
    assert job.status == "dead" and job.attempts == job.max_attempts
    assert "FileNotFoundError" in (job.last_error or "")
    assert rep.status == "failed"


def test_battleground_counts_only_confirmed_modes(client, make_user, upload, drain) -> None:  # type: ignore[no-untyped-def]
    u = make_user()
    _import(upload, drain, "battleground.txt", u["headers"])
    rk = client.get("/api/v1/rankings/pvp", params={"metric": "damage_to_players"}).json()
    assert rk["battleground"]["slug"] == "darkspear-islands"
    assert rk["rows"][0]["name"] == "Aldren" and rk["rows"][0]["value"] == 2700
    assert "rated" in {m["key"] for m in rk["modes"]}
    assert client.get("/api/v1/rankings/pvp", params={"battleground": "warsong-gulch"}).status_code == 404


def test_pvp_search_keeps_real_rank_and_faction_filter(client, make_user, upload, drain, db) -> None:  # type: ignore[no-untyped-def]
    from app.models import Character

    u = make_user()
    _import(upload, drain, "battleground.txt", u["headers"])
    full = client.get("/api/v1/rankings/pvp", params={"metric": "damage_to_players"}).json()
    rows = full["rows"]
    assert len(rows) >= 2
    target = rows[-1]
    found = client.get(
        "/api/v1/rankings/pvp", params={"metric": "damage_to_players", "q": target["name"][1:4].upper()}
    ).json()
    assert target["character_id"] in {r["character_id"] for r in found["rows"]}
    assert next(r for r in found["rows"] if r["character_id"] == target["character_id"])["rank"] == target["rank"]
    # Caracteres comodín de LIKE se buscan literalmente.
    assert client.get("/api/v1/rankings/pvp", params={"q": "%%"}).json()["total"] == 0

    # El log de prueba no trae COMBATANT_INFO: se asignan facciones a mano.
    horde_id = rows[1]["character_id"]
    for c in db.query(Character).all():
        c.faction = "horde" if c.id == horde_id else "alliance"
    db.commit()
    horde = client.get("/api/v1/rankings/pvp", params={"metric": "damage_to_players", "faction": "horde"}).json()
    assert [(r["character_id"], r["rank"], r["faction"]) for r in horde["rows"]] == [(horde_id, 1, "horde")]
    alliance = client.get("/api/v1/rankings/pvp", params={"metric": "damage_to_players", "faction": "alliance"}).json()
    assert alliance["total"] == len(rows) - 1
    assert alliance["summary"]["players"] == len(rows) - 1

    summary = full["summary"]
    assert summary["matches"] == 1
    assert summary["players"] == full["meta"]["characters"]
    assert sum(s["players"] for s in summary["specs"]) <= summary["players"]
    assert all(s["low_sample"] == (s["players"] < summary["min_players"]) for s in summary["specs"])


def test_profile_shows_pvp_block_and_ranking_positions(client, make_user, upload, drain) -> None:  # type: ignore[no-untyped-def]
    u = make_user()
    _import(upload, drain, "battleground.txt", u["headers"])
    _import(upload, drain, "basic_kill.txt", u["headers"])
    pvp = client.get("/api/v1/rankings/pvp", params={"metric": "damage_to_players"}).json()
    for row in pvp["rows"][:2]:
        prof = client.get(f"/api/v1/players/{row['character_id']}").json()
        block = prof["pvp"][0]
        assert block["battleground"]["slug"] == "darkspear-islands"
        assert block["damage_position"] == {"position": row["rank"], "of": pvp["total"]}

    boss = client.get("/api/v1/rankings/pve", params={"metric": "dps"}).json()
    top = boss["rows"][0] if boss["rows"] else None
    if top is not None:
        prof = client.get(f"/api/v1/players/{top['character_id']}").json()
        assert any(b["dps_position"] and b["dps_position"]["position"] == 1 for b in prof["best_by_encounter"])
