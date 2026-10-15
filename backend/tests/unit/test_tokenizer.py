from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.parser.dialects import from_header
from app.parser.tokenizer import LineFormatError, as_int, split_nested, to_utc, tokenize


def test_timestamp_negative_offset() -> None:
    raw = tokenize("10/7/2026 20:46:27.250-4  SPELL_DAMAGE,a,b", 1)
    assert (raw.month, raw.day, raw.year, raw.millis, raw.utc_offset_hours) == (10, 7, 2026, 250, -4)
    assert to_utc(raw, 2026, None) == datetime(2026, 10, 8, 0, 46, 27, 250000, tzinfo=UTC)


def test_timestamp_positive_offset_without_sign() -> None:
    # "19:41:14.7042" = 19:41:14.704 en UTC+2 (ejemplo de wowcoach.gg)
    raw = tokenize("8/30/2026 19:41:14.7042  SPELL_HEAL,x", 1)
    assert raw.millis == 704
    assert raw.utc_offset_hours == 2
    assert to_utc(raw, 2026, None) == datetime(2026, 8, 30, 17, 41, 14, 704000, tzinfo=UTC)


def test_timestamp_two_digit_offset() -> None:
    raw = tokenize("8/30/2026 15:35:07.16710  SPELL_HEAL,x", 1)
    assert (raw.millis, raw.utc_offset_hours) == (167, 10)


def test_legacy_timestamp_without_year_and_tab_separator() -> None:
    raw = tokenize("4/21 21:01:38.861\tSPELL_DAMAGE,x", 1)
    assert raw.year is None and raw.utc_offset_hours is None
    assert to_utc(raw, 2026, -3) == datetime(2026, 4, 22, 0, 1, 38, 861000, tzinfo=UTC)


@pytest.mark.parametrize("line", ["", "garbage", "10/7/2026 20:46:27  X", "MZ\x90\x00binary"])
def test_invalid_lines_raise(line: str) -> None:
    with pytest.raises(LineFormatError):
        tokenize(line, 1)


def test_quoted_fields_with_commas() -> None:
    raw = tokenize('1/1/2026 1:00:00.000  SPELL_DAMAGE,Player-1-A,"Ca,ma-Realm",0x511', 1)
    assert raw.fields == ["SPELL_DAMAGE", "Player-1-A", "Ca,ma-Realm", "0x511"]


def test_split_nested_keeps_brackets_together() -> None:
    assert split_nested('A,[(1,2),(3,4)],(5,6),"x,y",7') == ["A", "[(1,2),(3,4)]", "(5,6)", "x,y", "7"]


def test_as_int_variants() -> None:
    assert as_int("0x10a48") == 0x10A48
    assert as_int("nil") == 0
    assert as_int("-1") == -1
    assert as_int("12.7") == 12
    assert as_int("abc", 5) == 5


def test_dialect_forever_header() -> None:
    d = from_header(
        ["COMBAT_LOG_VERSION", "22", "ADVANCED_LOG_ENABLED", "1", "BUILD_VERSION", "1.60.1", "PROJECT_ID", "18"]
    )
    assert (d.key, d.verified, d.log_version, d.project_id, d.advanced_enabled) == ("forever", True, 22, 18, True)
    assert not d.is_demo


def test_dialect_demo_marker() -> None:
    d = from_header(
        ["COMBAT_LOG_VERSION", "22", "ADVANCED_LOG_ENABLED", "1", "BUILD_VERSION", "0.0.0-DEMO", "PROJECT_ID", "18"]
    )
    assert d.is_demo


def test_dialect_unknown_project_is_generic() -> None:
    d = from_header(
        ["COMBAT_LOG_VERSION", "20", "ADVANCED_LOG_ENABLED", "0", "BUILD_VERSION", "1.15.7", "PROJECT_ID", "2"]
    )
    assert d.key == "generic" and not d.verified and d.advanced_enabled is False
    assert d.notes
