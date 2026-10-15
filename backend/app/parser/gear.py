"""Equipo de cada jugador a partir de ``COMBATANT_INFO``.

El cliente escribe ``COMBATANT_INFO`` al empezar cada encuentro, con la lista de objetos equipados
como tuplas ``(itemID, nivelDeObjeto, (encantamientos), (bonusIDs), (gemas))``. La posición exacta del
campo en Forever no está documentada, así que se busca por forma: la primera lista de tuplas cuyo
tercer elemento es a su vez una tupla. El orden de ranuras es el estándar del cliente (no verificado
en Forever); si la lista no tiene el largo esperado se informan como "Ranura N".
"""

from __future__ import annotations

from typing import Any

SLOT_NAMES = (
    "Cabeza", "Cuello", "Hombros", "Camisa", "Pecho", "Cintura", "Piernas", "Pies", "Muñecas", "Manos",
    "Dedo 1", "Dedo 2", "Abalorio 1", "Abalorio 2", "Espalda", "Mano principal", "Mano secundaria",
    "A distancia", "Tabardo",
)  # fmt: skip


def parse_nested(text: str) -> Any:
    """Convierte ``[(1,2,(3)),...]`` en listas/tuplas de enteros o textos. Lanza ValueError si no puede."""
    pos = 0

    def value() -> Any:
        nonlocal pos
        if pos >= len(text):
            raise ValueError("fin inesperado")
        ch = text[pos]
        if ch in "[(":
            close = "]" if ch == "[" else ")"
            pos += 1
            items: list[Any] = []
            while pos < len(text) and text[pos] != close:
                items.append(value())
                if pos < len(text) and text[pos] == ",":
                    pos += 1
            if pos >= len(text):
                raise ValueError("falta cierre")
            pos += 1
            return items if close == "]" else tuple(items)
        start = pos
        while pos < len(text) and text[pos] not in ",)]":
            pos += 1
        token = text[start:pos].strip().strip('"')
        try:
            return int(token)
        except ValueError:
            return token

    result = value()
    if pos != len(text):
        raise ValueError("texto sobrante")
    return result


def _ints(value: Any) -> list[int]:
    return [v for v in value if isinstance(v, int) and v] if isinstance(value, tuple | list) else []


def extract_items(fields: list[str]) -> list[dict[str, Any]] | None:
    for raw in fields[3:]:
        raw = raw.strip()
        if not raw.startswith("[") or len(raw) > 20_000:
            continue
        try:
            val = parse_nested(raw)
        except (ValueError, RecursionError):
            continue
        if not isinstance(val, list) or not val:
            continue
        if not all(
            isinstance(t, tuple)
            and len(t) >= 3
            and isinstance(t[0], int)
            and isinstance(t[1], int)
            and isinstance(t[2], tuple)
            for t in val
        ):
            continue
        named = len(val) >= 16
        items = []
        for idx, t in enumerate(val):
            if t[0] <= 0:
                continue  # ranura vacía
            items.append(
                {
                    "slot": idx + 1,
                    "slot_name": SLOT_NAMES[idx] if named and idx < len(SLOT_NAMES) else f"Ranura {idx + 1}",
                    "item_id": t[0],
                    "item_level": t[1],
                    "enchants": _ints(t[2]),
                    "bonus_ids": _ints(t[3]) if len(t) > 3 else [],
                    "gems": _ints(t[4]) if len(t) > 4 else [],
                }
            )
        return items
    return None


def average_item_level(items: list[dict[str, Any]] | None) -> float | None:
    """Promedio sobre las ranuras que suman al nivel de objeto (excluye camisa y tabardo)."""
    if not items:
        return None
    levels = [i["item_level"] for i in items if i["slot_name"] not in ("Camisa", "Tabardo") and i["item_level"] > 0]
    return round(sum(levels) / len(levels), 1) if levels else None
