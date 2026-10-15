"""Constructor de líneas de combat log (formato v22 con Advanced Combat Logging).

Se usa para escribir los logs de prueba (tests/fixtures/logs) y los datos de demostración.
No produce datos "reales": todo lo que genera es sintético.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

NIL = "0000000000000000"
NIL_UNIT = (NIL, "nil", "0x80000000", "0x80000000")


@dataclass(frozen=True)
class Unit:
    guid: str
    name: str
    flags: str
    raid_flags: str = "0x0"

    def fields(self) -> tuple[str, str, str, str]:
        name = self.name if self.name == "nil" else f'"{self.name}"'
        return (self.guid, name, self.flags, self.raid_flags)


def player(n: int, name: str, realm: str = "Testrealm", flags: str = "0x514") -> Unit:
    return Unit(f"Player-5000-{n:08X}", f"{name}-{realm}", flags)


def creature(entry: int, spawn: int, name: str, flags: str = "0xa48") -> Unit:
    return Unit(f"Creature-0-5000-1-100-{entry}-{spawn:010X}", name, flags)


class LogBuilder:
    def __init__(
        self,
        start: datetime,
        utc_offset: int | None = -3,
        with_year: bool = True,
        build: str = "1.60.1",
        project_id: int = 18,
        advanced: bool = True,
    ) -> None:
        self.t = start
        self.offset = utc_offset
        self.with_year = with_year
        self.advanced = advanced
        self.lines: list[str] = []
        self.header(build, project_id)

    # -- tiempo -----------------------------------------------------------------
    def at(self, t: datetime) -> LogBuilder:
        self.t = t
        return self

    def wait(self, ms: int) -> LogBuilder:
        self.t = self.t + timedelta(milliseconds=ms)
        return self

    def _ts(self) -> str:
        t = self.t
        date = f"{t.month}/{t.day}/{t.year}" if self.with_year else f"{t.month}/{t.day}"
        off = ""
        if self.offset is not None and self.with_year:
            off = str(self.offset) if self.offset < 0 else str(self.offset) if self.offset > 0 else "0"
        return f"{date} {t.hour}:{t.minute:02d}:{t.second:02d}.{t.microsecond // 1000:03d}{off}"

    def raw(self, body: str) -> LogBuilder:
        self.lines.append(f"{self._ts()}  {body}")
        return self

    def emit(self, *fields: object) -> LogBuilder:
        return self.raw(",".join(str(f) for f in fields))

    # -- bloque avanzado ----------------------------------------------------------
    def adv(self, info: Unit | None, owner: Unit | None = None, hp: int = 100000, max_hp: int = 100000) -> tuple:
        if not self.advanced:
            return ()
        return (
            info.guid if info else NIL,
            owner.guid if owner else NIL,
            hp,
            max_hp,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            "100.00",
            "200.00",
            1,
            "1.5708",
            60,
        )

    # -- eventos ------------------------------------------------------------------
    def header(self, build: str, project_id: int) -> LogBuilder:
        return self.emit(
            "COMBAT_LOG_VERSION",
            22,
            "ADVANCED_LOG_ENABLED",
            1 if self.advanced else 0,
            "BUILD_VERSION",
            build,
            "PROJECT_ID",
            project_id,
        )

    def zone(self, instance_id: int, name: str, difficulty: int = 0) -> LogBuilder:
        return self.emit("ZONE_CHANGE", instance_id, f'"{name}"', difficulty)

    def encounter_start(self, enc_id: int, name: str, difficulty: int, size: int, instance_id: int) -> LogBuilder:
        return self.emit("ENCOUNTER_START", enc_id, f'"{name}"', difficulty, size, instance_id)

    def encounter_end(
        self, enc_id: int, name: str, difficulty: int, size: int, success: bool, fight_ms: int
    ) -> LogBuilder:
        return self.emit("ENCOUNTER_END", enc_id, f'"{name}"', difficulty, size, 1 if success else 0, fight_ms)

    def combatant_info(self, p: Unit, faction: int, spec_id: int) -> LogBuilder:
        stats = ["300", "100", "400", "50"] + ["0"] * 16 + ["3000"]
        return self.emit(
            "COMBATANT_INFO", p.guid, faction, *stats, spec_id, "[(1,2,3)]", "(0,0,0,0)", "[(19019,63,(),(),())]", "[]"
        )

    def cast(self, src: Unit, dst: Unit | None, spell_id: int, spell: str, school: str = "0x1") -> LogBuilder:
        d = dst.fields() if dst else NIL_UNIT
        return self.emit("SPELL_CAST_SUCCESS", *src.fields(), *d, spell_id, f'"{spell}"', school, *self.adv(src, None))

    def spell_damage(
        self,
        src: Unit,
        dst: Unit,
        spell_id: int,
        spell: str,
        amount: int,
        overkill: int = -1,
        absorbed: int = 0,
        school: str = "0x1",
        periodic: bool = False,
        info: Unit | None = None,
        owner: Unit | None = None,
        hp: int = 100000,
        max_hp: int = 100000,
    ) -> LogBuilder:
        ev = "SPELL_PERIODIC_DAMAGE" if periodic else "SPELL_DAMAGE"
        base = (amount, amount) if self.advanced else (amount,)
        return self.emit(
            ev,
            *src.fields(),
            *dst.fields(),
            spell_id,
            f'"{spell}"',
            school,
            *self.adv(info or dst, owner, hp, max_hp),
            *base,
            overkill,
            school,
            0,
            0,
            absorbed,
            "nil",
            "nil",
            "nil",
        )

    def range_damage(self, src: Unit, dst: Unit, amount: int, overkill: int = -1) -> LogBuilder:
        base = (amount, amount) if self.advanced else (amount,)
        return self.emit(
            "RANGE_DAMAGE",
            *src.fields(),
            *dst.fields(),
            75,
            '"Auto Shot"',
            "0x1",
            *self.adv(dst),
            *base,
            overkill,
            "0x1",
            0,
            0,
            0,
            "nil",
            "nil",
            "nil",
        )

    def swing(
        self, src: Unit, dst: Unit, amount: int, overkill: int = -1, absorbed: int = 0, owner: Unit | None = None
    ) -> LogBuilder:
        base = (amount, amount) if self.advanced else (amount,)
        return self.emit(
            "SWING_DAMAGE",
            *src.fields(),
            *dst.fields(),
            *self.adv(src, owner),
            *base,
            overkill,
            "0x1",
            0,
            0,
            absorbed,
            "nil",
            "nil",
            "nil",
            "nil",
        )

    def swing_landed(self, src: Unit, dst: Unit, amount: int) -> LogBuilder:
        base = (amount, amount) if self.advanced else (amount,)
        return self.emit(
            "SWING_DAMAGE_LANDED",
            *src.fields(),
            *dst.fields(),
            *self.adv(dst),
            *base,
            -1,
            "0x1",
            0,
            0,
            0,
            "nil",
            "nil",
            "nil",
            "nil",
        )

    def spell_missed(
        self, src: Unit, dst: Unit, spell_id: int, spell: str, miss_type: str, amount: int, school: str = "0x1"
    ) -> LogBuilder:
        return self.emit(
            "SPELL_MISSED",
            *src.fields(),
            *dst.fields(),
            spell_id,
            f'"{spell}"',
            school,
            miss_type,
            "nil",
            amount,
            amount,
            "nil",
        )

    def swing_missed(self, src: Unit, dst: Unit, miss_type: str, amount: int) -> LogBuilder:
        return self.emit("SWING_MISSED", *src.fields(), *dst.fields(), miss_type, "nil", amount, amount, "nil")

    def heal(
        self,
        src: Unit,
        dst: Unit,
        spell_id: int,
        spell: str,
        amount: int,
        overheal: int = 0,
        heal_absorbed: int = 0,
        periodic: bool = False,
    ) -> LogBuilder:
        ev = "SPELL_PERIODIC_HEAL" if periodic else "SPELL_HEAL"
        base = (amount, amount) if self.advanced else (amount,)
        return self.emit(
            ev,
            *src.fields(),
            *dst.fields(),
            spell_id,
            f'"{spell}"',
            "0x2",
            *self.adv(dst),
            *base,
            overheal,
            heal_absorbed,
            "nil",
        )

    def absorbed_spell(
        self,
        attacker: Unit,
        defender: Unit,
        spell_id: int,
        spell: str,
        caster: Unit,
        absorb_id: int,
        absorb_name: str,
        amount: int,
    ) -> LogBuilder:
        return self.emit(
            "SPELL_ABSORBED",
            *attacker.fields(),
            *defender.fields(),
            spell_id,
            f'"{spell}"',
            "0x20",
            *caster.fields(),
            absorb_id,
            f'"{absorb_name}"',
            "0x2",
            amount,
            amount,
            "nil",
        )

    def absorbed_melee(
        self, attacker: Unit, defender: Unit, caster: Unit, absorb_id: int, absorb_name: str, amount: int
    ) -> LogBuilder:
        return self.emit(
            "SPELL_ABSORBED",
            *attacker.fields(),
            *defender.fields(),
            *caster.fields(),
            absorb_id,
            f'"{absorb_name}"',
            "0x2",
            amount,
            amount,
            "nil",
        )

    def interrupt(self, src: Unit, dst: Unit, spell_id: int, spell: str, extra_id: int, extra: str) -> LogBuilder:
        return self.emit(
            "SPELL_INTERRUPT",
            *src.fields(),
            *dst.fields(),
            spell_id,
            f'"{spell}"',
            "0x1",
            extra_id,
            f'"{extra}"',
            "0x20",
        )

    def dispel(self, src: Unit, dst: Unit, spell_id: int, spell: str, extra_id: int, extra: str) -> LogBuilder:
        return self.emit(
            "SPELL_DISPEL",
            *src.fields(),
            *dst.fields(),
            spell_id,
            f'"{spell}"',
            "0x2",
            extra_id,
            f'"{extra}"',
            "0x10",
            "DEBUFF",
        )

    def summon(self, src: Unit, dst: Unit, spell_id: int, spell: str) -> LogBuilder:
        return self.emit("SPELL_SUMMON", *src.fields(), *dst.fields(), spell_id, f'"{spell}"', "0x10")

    def died(self, unit: Unit, unconscious: int = 0) -> LogBuilder:
        return self.emit("UNIT_DIED", *NIL_UNIT, *unit.fields(), 0, unconscious)

    def text(self) -> str:
        return "\n".join(self.lines) + "\n"
