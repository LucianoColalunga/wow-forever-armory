"""Acumuladores de métricas por jugador y por combate.

Definiciones (ver docs/METHODOLOGY.md):

- ``damage_done`` (daño realizado) = daño que quitó vida + overkill + daño absorbido por escudos
  del objetivo (campo ``absorbed`` del evento de daño + ``*_MISSED`` de tipo ABSORB).
- ``effective_damage`` (daño efectivo) = vida realmente quitada = amount − overkill.
- ``overkill`` = daño sobrante del golpe que mató (−1 en el log = sin overkill → 0).
- ``healing_effective`` = amount − overhealing.  ``overhealing`` se guarda aparte.
- ``heal_absorbed`` = curación consumida por efectos de "absorción de sanación" del objetivo;
  ya está dentro de ``amount`` y se informa por separado (no se resta del efectivo).
- ``absorbs_provided`` = daño evitado por escudos del jugador (eventos ``SPELL_ABSORBED``),
  atribuido al lanzador del escudo. NUNCA se suma a la curación.
- ``damage_taken`` = vida perdida por el jugador (amount); ``damage_taken_absorbed`` = lo que
  absorbieron sus escudos. No se mezclan.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class PlayerStats:
    guid: str
    name: str | None = None
    damage_done: int = 0
    effective_damage: int = 0
    overkill: int = 0
    damage_absorbed_by_target: int = 0
    damage_to_players: int = 0
    healing_gross: int = 0
    healing_effective: int = 0
    overhealing: int = 0
    heal_absorbed: int = 0
    absorbs_provided: int = 0
    damage_taken: int = 0
    damage_taken_absorbed: int = 0
    deaths: int = 0
    first_death_ms: int | None = None
    interrupts: int = 0
    dispels: int = 0
    killing_blows: int = 0
    events: int = 0
    damage_by_ability: Counter[str] = field(default_factory=Counter)
    healing_by_ability: Counter[str] = field(default_factory=Counter)
    death_log: list[dict[str, object]] = field(default_factory=list)

    def as_metrics(self, duration_ms: int) -> dict[str, float]:
        seconds = max(duration_ms, 1) / 1000.0
        time_alive = self.first_death_ms if self.first_death_ms is not None else duration_ms
        time_alive = max(0, min(time_alive, duration_ms))
        return {
            "damage_done": self.damage_done,
            "effective_damage": self.effective_damage,
            "overkill": self.overkill,
            "damage_absorbed_by_target": self.damage_absorbed_by_target,
            "damage_to_players": self.damage_to_players,
            "healing_gross": self.healing_gross,
            "healing_effective": self.healing_effective,
            "overhealing": self.overhealing,
            "heal_absorbed": self.heal_absorbed,
            "absorbs_provided": self.absorbs_provided,
            "damage_taken": self.damage_taken,
            "damage_taken_absorbed": self.damage_taken_absorbed,
            "deaths": self.deaths,
            "interrupts": self.interrupts,
            "dispels": self.dispels,
            "killing_blows": self.killing_blows,
            "time_alive_ms": time_alive,
            "dps": round(self.damage_done / seconds, 2),
            "hps": round(self.healing_effective / seconds, 2),
            "aps": round(self.absorbs_provided / seconds, 2),
            "dtps": round(self.damage_taken / seconds, 2),
            "survival_pct": round(100.0 * time_alive / max(duration_ms, 1), 2),
        }


@dataclass(slots=True)
class Timeline:
    """Series agregadas en baldes de tiempo para los gráficos."""

    bucket_ms: int
    damage: dict[str, Counter[int]] = field(default_factory=dict)
    healing: dict[str, Counter[int]] = field(default_factory=dict)

    def add(self, series: dict[str, Counter[int]], guid: str, t_rel_ms: int, amount: int) -> None:
        if amount <= 0 or t_rel_ms < 0:
            return
        series.setdefault(guid, Counter())[t_rel_ms // self.bucket_ms] += amount

    def export(self, duration_ms: int, max_buckets: int = 240) -> dict[str, Any]:
        raw_n = max(1, -(-duration_ms // self.bucket_ms))
        factor = max(1, -(-raw_n // max_buckets))
        n = max(1, -(-raw_n // factor))

        def dense(c: Counter[int]) -> list[int]:
            out = [0] * n
            for i, v in c.items():
                j = i // factor
                if 0 <= j < n:
                    out[j] += int(v)
            return out

        total_d: Counter[int] = Counter()
        total_h: Counter[int] = Counter()
        for c in self.damage.values():
            total_d.update(c)
        for c in self.healing.values():
            total_h.update(c)
        return {
            "bucket_ms": self.bucket_ms * factor,
            "buckets": n,
            "raid_damage": dense(total_d),
            "raid_healing": dense(total_h),
            "players_damage": {g: dense(c) for g, c in self.damage.items()},
            "players_healing": {g: dense(c) for g, c in self.healing.items()},
        }
