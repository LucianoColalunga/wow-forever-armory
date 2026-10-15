from __future__ import annotations

from pathlib import Path

import pytest

from app.parser import parse_text
from app.parser.gear import average_item_level, extract_items, parse_nested
from app.parser.tokenizer import split_nested

LOGS = Path(__file__).parents[1] / "fixtures" / "logs"


def test_parse_nested_lists_and_tuples() -> None:
    assert parse_nested("[(1,2,(3,4),(),(5)),(0,0,(),(),())]") == [(1, 2, (3, 4), (), (5,)), (0, 0, (), (), ())]
    assert parse_nested("[Player-1-ABC,123]") == ["Player-1-ABC", 123]
    with pytest.raises(ValueError):
        parse_nested("[(1,2")


def test_extract_items_full_slot_list() -> None:
    items = ",".join(
        f"({100 + i},{60 + (i % 3)},({2500 if i == 0 else 0},0,0),(),({7000 if i == 4 else 0}))"
        if i not in (3, 18)
        else "(0,0,(),(),())"
        for i in range(19)
    )
    line = f"COMBATANT_INFO,Player-1-AA,1,{','.join(['0'] * 21)},71,[(1,2,3)],(0,0,0,0),[{items}],[Player-1-AA,1234]"
    got = extract_items(split_nested(line))
    assert got is not None and len(got) == 17  # camisa (4) y tabardo (19) vacías
    head = got[0]
    assert (head["slot_name"], head["item_id"], head["item_level"], head["enchants"]) == ("Cabeza", 100, 60, [2500])
    chest = next(i for i in got if i["slot_name"] == "Pecho")
    assert chest["gems"] == [7000]
    assert got[-1]["slot_name"] == "A distancia"
    assert average_item_level(got) == pytest.approx(sum(i["item_level"] for i in got) / len(got), abs=0.05)


def test_extract_items_ignores_talent_lists() -> None:
    assert extract_items(["COMBATANT_INFO", "Player-1-AA", "1", "[(1,2,3)]", "(0,0,0,0)"]) is None


def test_fight_gear_and_cast_timeline_from_fixture() -> None:
    result = parse_text((LOGS / "basic_kill.txt").read_text(encoding="utf-8"), default_year=2026)
    fight = result.fights[0]
    warrior = fight.gear["Player-5000-00000001"]
    assert warrior[0]["item_id"] == 19019 and warrior[0]["item_level"] == 63
    # Lanzamientos con su momento relativo al inicio del encuentro (21:00:05)
    assert fight.casts["Player-5000-00000001"] == [(1000, "Mortal Strike")]
    assert fight.casts["Player-5000-00000004"] == [
        (20000, "Aimed Shot"),
        (20000, "Trueshot Aura"),
        (25000, "Feign Death"),
    ]
    assert [c[1] for c in fight.casts["Player-5000-00000003"]] == ["Frostbolt", "Fire Blast", "Ice Barrier"]
