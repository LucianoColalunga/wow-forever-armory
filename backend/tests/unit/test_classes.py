from __future__ import annotations

from collections import Counter

import pytest

from app.parser.classes import infer_class_spec, normalize_class, normalize_spec, role_for


@pytest.mark.parametrize(
    ("raw", "slug"),
    [
        ("Warrior", "warrior"),
        ("GUERRERO", "warrior"),
        ("Pícaro", "rogue"),
        ("picara", "rogue"),
        ("Chamán", "shaman"),
        ("death knight", None),
        ("", None),
        (None, None),
    ],
)
def test_normalize_class(raw: str | None, slug: str | None) -> None:
    assert normalize_class(raw) == slug


def test_normalize_spec_aliases_and_labels() -> None:
    assert normalize_spec("hunter", "BM") == "beast-mastery"
    assert normalize_spec("druid", "Restauración") == "restoration"
    assert normalize_spec("mage", "holy") is None
    assert normalize_spec(None, "fire") is None


def test_spec_id_wins() -> None:
    g = infer_class_spec(Counter({"Frostbolt": 10}), spec_id=63, role_hint=None)
    assert (g.class_slug, g.spec, g.source) == ("mage", "fire", "combatant_info")


def test_ambiguous_signatures_return_unknown() -> None:
    g = infer_class_spec(Counter({"Frostbolt": 1, "Shadow Bolt": 1}), spec_id=None, role_hint=None)
    assert g.class_slug is None and g.source == "unknown"


def test_role_fallback_for_spec() -> None:
    g = infer_class_spec(Counter({"Flash Heal": 3}), spec_id=None, role_hint="healer")
    assert (g.class_slug, g.spec, g.source) == ("priest", "holy", "role")


def test_role_for() -> None:
    assert role_for("priest", "holy", 0.9, 0.0) == "healer"
    assert role_for("warrior", "protection", 0.0, 0.5) == "tank"
    assert role_for("mage", "fire", 0.0, 0.05) == "dps"
