"""Compara la salida del parser con los resultados esperados escritos a mano."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.parser import parse_text

LOGS = Path(__file__).parents[1] / "fixtures" / "logs"
EXPECTED = json.loads((LOGS / "expected.json").read_text(encoding="utf-8"))
FILES = [k for k in EXPECTED if not k.startswith("_")]


def _parse(name: str):
    return parse_text((LOGS / name).read_text(encoding="utf-8"), default_year=2026)


@pytest.mark.parametrize("name", FILES)
def test_fixture_matches_expected(name: str) -> None:
    expected = EXPECTED[name]
    result = _parse(name)
    fights = [f for f in result.fights if f.kind in ("encounter", "battleground")]
    assert len(fights) == len(expected["fights"]), [f.kind for f in result.fights]
    for fight, exp in zip(fights, expected["fights"], strict=True):
        for key in (
            "kind",
            "encounter_id",
            "encounter_name",
            "difficulty_id",
            "group_size",
            "success",
            "complete",
            "rankable",
            "duration_ms",
            "zone_name",
            "boss_min_hp_pct",
            "unrankable_reason",
        ):
            if key in exp:
                assert getattr(fight, key) == exp[key], f"{name}: {key}"
        if "start_utc" in exp:
            assert fight.start.isoformat() == exp["start_utc"]
        if "end_utc" in exp:
            assert fight.end is not None and fight.end.isoformat() == exp["end_utc"]
        for guid, metrics in exp["players"].items():
            assert guid in fight.players, f"{name}: falta {guid}"
            ps = fight.players[guid]
            got = ps.as_metrics(fight.duration_ms)
            for metric, value in metrics.items():
                if metric == "name":
                    assert result.units[guid].name == value
                    continue
                assert got[metric] == pytest.approx(value, abs=0.01), f"{name}: {guid} {metric}"
    for code in expected.get("issue_codes", []):
        assert code in {i.code for i in result.issues}, f"{name}: falta issue {code}"
    if "dialect" in expected:
        d = result.dialect.as_dict()
        for key, value in expected["dialect"].items():
            assert d[key] == value, f"{name}: dialect.{key}"


def test_basic_kill_class_inference() -> None:
    result = _parse("basic_kill.txt")
    for guid, exp in EXPECTED["basic_kill.txt"]["classes"].items():
        guess = result.units[guid].guess
        assert guess is not None
        assert (guess.class_slug, guess.spec, guess.source) == (exp["class"], exp["spec"], exp["source"])


def test_basic_kill_totals_and_no_double_counting() -> None:
    result = _parse("basic_kill.txt")
    fight = result.fights[0]
    total = sum(p.damage_done for p in fight.players.values())
    assert total == EXPECTED["basic_kill.txt"]["raid_damage_total"]
    # absorciones no se suman a la curación
    priest = fight.players["Player-5000-00000002"]
    assert priest.healing_effective == 3500
    assert priest.absorbs_provided == 1700
    # el golpe posterior al ENCOUNTER_END (999) no aparece
    assert all(p.damage_done != 999 for p in fight.players.values())
    # las absorciones de golpes coinciden con SPELL_ABSORBED: sin aviso de inconsistencia
    assert "absorb_mismatch" not in {i.code for i in fight.issues}
    # la serie temporal suma lo mismo que el total
    tl = fight.timeline.export(fight.duration_ms)
    assert sum(tl["raid_damage"]) == total


def test_feign_death_is_not_a_death() -> None:
    result = _parse("basic_kill.txt")
    hunter = result.fights[0].players["Player-5000-00000004"]
    assert hunter.deaths == 0


def test_death_log_records_killing_ability() -> None:
    result = _parse("basic_kill.txt")
    mage = result.fights[0].players["Player-5000-00000003"]
    assert mage.death_log[0] == {"t_ms": 35100, "ability": "Shadow Bolt", "killer": "Test Guardian"}


def test_fight_key_is_deterministic() -> None:
    a = _parse("basic_kill.txt").fights[0].fight_key
    b = _parse("basic_kill.txt").fights[0].fight_key
    assert a == b and len(a) == 64
