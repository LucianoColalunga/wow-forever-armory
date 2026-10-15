"""Métodos de ranking con datos controlados (valores conocidos de antemano)."""

from __future__ import annotations

import statistics
from datetime import datetime

import pytest

from app.demo.logbuilder import LogBuilder, creature, player

pytestmark = pytest.mark.integration

# DPS de cada mago (frost) en cada uno de los 4 kills de 60 s del jefe 7001 (dificultad 3, 20 jugadores).
MAGE_A = [100, 300, 200, 250]
MAGE_B = [150, 160, 170, 180]
WARRIOR = [400, 100, 120, 130]
# Segundo jefe (7002): A y el guerrero, con valores 10x para verificar la normalización entre encuentros.
BOSS2_A = [2000, 2200]
BOSS2_W = [1000, 1100]


def _kill(day: int, boss_id: int, boss_name: str, dps_by_player: dict[int, tuple[str, str, int]]) -> str:
    b = LogBuilder(datetime(2026, 10, 1 + day, 21, 0))
    boss = creature(boss_id, day + 1, boss_name)
    b.wait(1000).encounter_start(boss_id, boss_name, 3, 20, 1)
    for pid, (name, spell, _dps) in dps_by_player.items():
        sig = {"Frostbolt": (11426, "Ice Barrier"), "Bloodthirst": (23881, "Bloodthirst")}[spell]
        b.cast(player(pid, name), None, sig[0], sig[1])
    for pid, (name, spell, dps) in dps_by_player.items():
        b.spell_damage(player(pid, name), boss, 116 if spell == "Frostbolt" else 23881, spell, dps * 60)
    b.wait(59000).encounter_end(boss_id, boss_name, 3, 20, True, 60000)
    return b.text()


@pytest.fixture
def ranked_data(make_user, upload, drain):  # type: ignore[no-untyped-def]
    u = make_user()
    for i in range(4):
        text = _kill(
            i,
            7001,
            "Jefe Uno",
            {
                1: ("Alfa", "Frostbolt", MAGE_A[i]),
                2: ("Beta", "Frostbolt", MAGE_B[i]),
                3: ("Gamma", "Bloodthirst", WARRIOR[i]),
            },
        )
        assert upload(f"k{i}.txt", text, u["headers"]).status_code == 202
    for i in range(2):
        text = _kill(
            10 + i, 7002, "Jefe Dos", {1: ("Alfa", "Frostbolt", BOSS2_A[i]), 3: ("Gamma", "Bloodthirst", BOSS2_W[i])}
        )
        assert upload(f"j{i}.txt", text, u["headers"]).status_code == 202
    drain()
    return u


def _boss(client, name: str) -> int:  # type: ignore[no-untyped-def]
    res = client.get("/api/v1/search", params={"q": name}).json()
    return int(res["bosses"][0]["id"])


def test_peak_method(client, ranked_data) -> None:  # type: ignore[no-untyped-def]
    boss = _boss(client, "Jefe Uno")
    rk = client.get(f"/api/v1/rankings/pve/bosses/{boss}", params={"method": "peak"}).json()
    vals = {r["name"]: r["value"] for r in rk["rows"]}
    assert vals == {"Gamma": 400, "Alfa": 300, "Beta": 180}
    assert [r["rank"] for r in rk["rows"]] == [1, 2, 3]
    assert rk["meta"]["records_used"] == 12 and rk["meta"]["characters"] == 3
    assert rk["meta"]["difficulty_id"] == 3 and rk["meta"]["group_size"] == 20
    assert rk["meta"]["period_from"].startswith("2026-10-02")
    assert rk["rows"][0]["samples"] == 4


def test_consistency_method_uses_median_and_min_kills(client, ranked_data) -> None:  # type: ignore[no-untyped-def]
    boss = _boss(client, "Jefe Uno")
    rk = client.get(f"/api/v1/rankings/pve/bosses/{boss}", params={"method": "consistency"}).json()
    vals = {r["name"]: r["value"] for r in rk["rows"]}
    assert vals["Alfa"] == pytest.approx(statistics.median(MAGE_A))
    assert vals["Beta"] == pytest.approx(statistics.median(MAGE_B))
    assert vals["Gamma"] == pytest.approx(statistics.median(WARRIOR))
    # El orden cambia respecto del pico: la consistencia premia a Alfa sobre Gamma.
    assert [r["name"] for r in rk["rows"]] == ["Alfa", "Beta", "Gamma"]
    boss2 = _boss(client, "Jefe Dos")
    rk2 = client.get(f"/api/v1/rankings/pve/bosses/{boss2}", params={"method": "consistency"}).json()
    assert rk2["total"] == 0  # 2 kills < mínimo de 3
    assert rk2["meta"]["records_excluded"] == 2


def test_percentile_requires_min_sample(client, ranked_data) -> None:  # type: ignore[no-untyped-def]
    from app.core.config import get_settings

    boss = _boss(client, "Jefe Uno")
    rk = client.get(f"/api/v1/rankings/pve/bosses/{boss}", params={"method": "percentile"}).json()
    assert rk["total"] == 0 and rk["meta"]["records_excluded"] == 12  # cubetas de 8 y 4 < 10
    s = get_settings()
    s.min_bucket_size = 4
    try:
        from app.rankings.cache import response_cache

        response_cache.clear()
        rk = client.get(f"/api/v1/rankings/pve/bosses/{boss}", params={"method": "percentile"}).json()
        vals = {r["name"]: r["value"] for r in rk["rows"]}
        # Cubeta mago/frost: 8 valores; el mejor de Alfa (300) es el máximo → percentil 100.
        assert vals["Alfa"] == pytest.approx(100.0)
        # Beta: su mejor (180) es el 5.º de 8 → percent_rank = 4/7.
        assert vals["Beta"] == pytest.approx(100 * 4 / 7)
        # Guerrero solo en su cubeta (4 valores): su mejor es el máximo → 100.
        assert vals["Gamma"] == pytest.approx(100.0)
        assert rk["meta"]["records_excluded"] == 0
    finally:
        s.min_bucket_size = 10


def test_general_ranking_normalizes_across_encounters(client, ranked_data) -> None:  # type: ignore[no-untyped-def]
    rk = client.get("/api/v1/rankings/pve", params={"method": "peak", "metric": "dps"}).json()
    vals = {r["name"]: r for r in rk["rows"]}
    med1 = statistics.median(MAGE_A + MAGE_B + WARRIOR)
    # Jefe Dos tiene sólo 4 registros: mediana = promedio de los dos centrales
    med2 = statistics.median(BOSS2_A + BOSS2_W)
    exp_alfa = (100 * max(MAGE_A) / med1 + 100 * max(BOSS2_A) / med2) / 2
    exp_gamma = (100 * max(WARRIOR) / med1 + 100 * max(BOSS2_W) / med2) / 2
    exp_beta = 100 * max(MAGE_B) / med1
    assert vals["Alfa"]["value"] == pytest.approx(exp_alfa)
    assert vals["Gamma"]["value"] == pytest.approx(exp_gamma)
    assert vals["Beta"]["value"] == pytest.approx(exp_beta)
    assert vals["Alfa"]["partitions"] == 2 and vals["Beta"]["partitions"] == 1
    assert rk["meta"]["records_used"] == 16
    assert "mediana" in rk["meta"]["method_description"]


def test_ranking_cache_invalidates_on_new_data(client, ranked_data, upload, drain) -> None:  # type: ignore[no-untyped-def]
    boss = _boss(client, "Jefe Uno")
    first = client.get(f"/api/v1/rankings/pve/bosses/{boss}").json()
    second = client.get(f"/api/v1/rankings/pve/bosses/{boss}").json()
    assert second["cache"] == "hit"
    text = _kill(20, 7001, "Jefe Uno", {4: ("Delta", "Frostbolt", 999)})
    assert upload("nuevo.txt", text, ranked_data["headers"]).status_code == 202
    drain()
    third = client.get(f"/api/v1/rankings/pve/bosses/{boss}").json()
    assert third["cache"] == "miss" and third["rows"][0]["name"] == "Delta"
    assert third["meta"]["records_used"] == first["meta"]["records_used"] + 1


def test_filters_and_pagination(client, ranked_data) -> None:  # type: ignore[no-untyped-def]
    boss = _boss(client, "Jefe Uno")
    rk = client.get(f"/api/v1/rankings/pve/bosses/{boss}", params={"class": "mage", "page_size": 1, "page": 2}).json()
    assert rk["total"] == 2 and len(rk["rows"]) == 1 and rk["rows"][0]["name"] == "Beta" and rk["rows"][0]["rank"] == 2
    since = (datetime(2026, 10, 3, 0, 0)).isoformat()
    rk2 = client.get(f"/api/v1/rankings/pve/bosses/{boss}", params={"date_from": since}).json()
    assert rk2["meta"]["records_used"] == 9
