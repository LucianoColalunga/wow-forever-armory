"""Lectura de líneas del combat log: timestamp + campos separados por comas.

Formato de línea (combat log v22, verificado en wowcoach.gg/docs/combat-log/line-format):

    M/D/YYYY H:MM:SS.mmm[offset]␠␠EVENTO,campo1,campo2,...

- La fecha no tiene ceros a la izquierda; los milisegundos siempre son 3 dígitos.
- ``offset`` es el huso horario en horas enteras: negativo con ``-`` y positivo SIN signo
  (``19:41:14.7042`` = 19:41:14.704 en UTC+2).
- Clientes viejos (Classic 1.13/1.14) escriben ``M/D H:MM:SS.mmm`` sin año ni huso.
- El separador entre timestamp y evento son dos espacios (en algunos clientes, un tab).
- Los nombres van entre comillas dobles y pueden contener comas.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone

_TS_RE = re.compile(
    r"^(?P<mon>\d{1,2})/(?P<day>\d{1,2})(?:/(?P<year>\d{4}))?\s(?P<h>\d{1,2}):(?P<m>\d{2}):(?P<s>\d{2})"
    r"\.(?P<ms>\d{3})(?P<off>-?\d{1,2})?(?:\s\s|\t)(?P<rest>.*)$"
)

_HEX_RE = re.compile(r"^0x[0-9a-fA-F]+$")
_INT_RE = re.compile(r"^-?\d+$")


@dataclass(slots=True)
class RawLine:
    line_no: int
    month: int
    day: int
    year: int | None
    hour: int
    minute: int
    second: int
    millis: int
    utc_offset_hours: int | None
    fields: list[str]

    @property
    def event(self) -> str:
        return self.fields[0] if self.fields else ""


class LineFormatError(ValueError):
    """La línea no respeta el formato del combat log."""


def split_fields(rest: str) -> list[str]:
    """Divide la parte posterior al timestamp respetando comillas."""
    if '"' not in rest:
        return rest.split(",")
    return next(csv.reader([rest], skipinitialspace=False))


def split_nested(rest: str) -> list[str]:
    """Divide por comas de primer nivel respetando comillas, corchetes y paréntesis.

    Se usa para COMBATANT_INFO, cuyos campos de talentos/equipo contienen listas
    anidadas como ``[(1,2,3),(4,5,6)]``.
    """
    out: list[str] = []
    depth = 0
    in_quotes = False
    buf: list[str] = []
    for ch in rest:
        if ch == '"':
            in_quotes = not in_quotes
            continue
        if not in_quotes:
            if ch in "[(":
                depth += 1
            elif ch in "])":
                depth = max(0, depth - 1)
            elif ch == "," and depth == 0:
                out.append("".join(buf))
                buf = []
                continue
        buf.append(ch)
    out.append("".join(buf))
    return out


def tokenize(line: str, line_no: int) -> RawLine:
    m = _TS_RE.match(line)
    if not m:
        raise LineFormatError("timestamp inválido o separador ausente")
    rest = m.group("rest")
    fields = split_nested(rest) if rest.startswith("COMBATANT_INFO") else split_fields(rest)
    off = m.group("off")
    return RawLine(
        line_no=line_no,
        month=int(m.group("mon")),
        day=int(m.group("day")),
        year=int(m.group("year")) if m.group("year") else None,
        hour=int(m.group("h")),
        minute=int(m.group("m")),
        second=int(m.group("s")),
        millis=int(m.group("ms")),
        utc_offset_hours=int(off) if off is not None else None,
        fields=fields,
    )


def to_utc(raw: RawLine, year: int, fallback_offset_hours: int | None) -> datetime:
    """Convierte el timestamp de la línea a UTC.

    Si la línea no trae huso horario se usa ``fallback_offset_hours`` (dato del
    importador); si tampoco existe se asume UTC y el parser lo reporta como aviso.
    """
    offset = raw.utc_offset_hours if raw.utc_offset_hours is not None else fallback_offset_hours
    tz = timezone(timedelta(hours=offset)) if offset is not None else UTC
    local = datetime(year, raw.month, raw.day, raw.hour, raw.minute, raw.second, raw.millis * 1000, tzinfo=tz)
    return local.astimezone(UTC)


def as_int(value: str | None, default: int = 0) -> int:
    if value is None:
        return default
    v = value.strip()
    if not v or v == "nil":
        return default
    if _HEX_RE.match(v):
        return int(v, 16)
    if _INT_RE.match(v):
        return int(v)
    try:
        return int(float(v))
    except ValueError:
        return default


def as_flag(value: str | None) -> int:
    return as_int(value, 0)


def as_bool(value: str | None) -> bool:
    if value is None:
        return False
    v = value.strip()
    return v not in ("", "nil", "0")


def as_str(value: str | None) -> str | None:
    if value is None:
        return None
    v = value.strip()
    if v == "nil" or v == "":
        return None
    return v


def looks_like_guid(value: str | None) -> bool:
    if not value:
        return False
    if value == "0000000000000000":
        return True
    return value.startswith(("Player-", "Creature-", "Pet-", "Vehicle-", "GameObject-", "Vignette-", "Item-"))
