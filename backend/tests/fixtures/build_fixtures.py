"""Genera los logs de prueba de tests/fixtures/logs.

Uso:  python -m tests.fixtures.build_fixtures   (desde backend/)

Los resultados esperados NO se calculan con el parser: están escritos a mano en
tests/fixtures/logs/expected.json y documentados en tests/fixtures/logs/README.md.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.demo.logbuilder import LogBuilder, Unit, creature, player

OUT = Path(__file__).parent / "logs"

WARRIOR = player(1, "Brakka", flags="0x511")
PRIEST = player(2, "Lumen")
MAGE = player(3, "Ignis")
HUNTER = player(4, "Arrowyn")
PET = Unit("Pet-0-5000-1-100-42-0100000001", "Wolfie", "0x1114")
ELEMENTAL = creature(510, 99, "Water Elemental", flags="0x2114")
BOSS = creature(90001, 1, "Test Guardian")
ADD = creature(90002, 2, "Test Add")


def basic_kill() -> str:
    b = LogBuilder(datetime(2026, 10, 14, 21, 0, 0))
    b.wait(1000).zone(9999, "Hyjal Summit", 3)
    b.wait(4000).encounter_start(99001, "Test Guardian", 3, 20, 9999)  # 21:00:05.000
    b.combatant_info(WARRIOR, 1, 71)
    b.combatant_info(PRIEST, 1, 0)
    # 21:00:06 guerrero
    b.wait(1000).cast(WARRIOR, BOSS, 12294, "Mortal Strike")
    b.spell_damage(WARRIOR, BOSS, 12294, "Mortal Strike", 1000, hp=999000, max_hp=1000000)
    b.wait(1000).swing(WARRIOR, BOSS, 500)
    b.swing_landed(WARRIOR, BOSS, 500)  # duplicado del mismo golpe: no debe contarse
    # 21:00:08 mago: escudo del jefe absorbe 300
    b.wait(1000).cast(MAGE, BOSS, 116, "Frostbolt", "0x10")
    b.spell_damage(MAGE, BOSS, 116, "Frostbolt", 2000, absorbed=300, school="0x10", hp=995000, max_hp=1000000)
    b.absorbed_spell(MAGE, BOSS, 116, "Frostbolt", BOSS, 90100, "Guardian Ward", 300)
    # 21:00:09 Fire Blast totalmente absorbido
    b.wait(1000).cast(MAGE, BOSS, 2136, "Fire Blast", "0x4")
    b.spell_missed(MAGE, BOSS, 2136, "Fire Blast", "ABSORB", 400, school="0x4")
    b.absorbed_spell(MAGE, BOSS, 2136, "Fire Blast", BOSS, 90100, "Guardian Ward", 400)
    b.cast(MAGE, None, 11426, "Ice Barrier", "0x10")
    # 21:00:10 mascota del cazador (dueño por bloque avanzado) y elemental (dueño por SPELL_SUMMON)
    b.wait(1000).swing(PET, BOSS, 300, owner=HUNTER)
    b.summon(MAGE, ELEMENTAL, 31687, "Summon Water Elemental")
    b.spell_damage(ELEMENTAL, BOSS, 31707, "Waterbolt", 600, school="0x10", hp=990000, max_hp=1000000)
    # 21:00:12 el jefe golpea al tanque; Power Word: Shield absorbe
    b.wait(2000).cast(PRIEST, WARRIOR, 17, "Power Word: Shield", "0x2")
    b.spell_damage(BOSS, WARRIOR, 90200, "Crushing Blow", 3000, absorbed=1000, info=WARRIOR)
    b.absorbed_spell(BOSS, WARRIOR, 90200, "Crushing Blow", PRIEST, 17, "Power Word: Shield", 1000)
    b.wait(1000).swing(BOSS, WARRIOR, 800, absorbed=200)
    b.absorbed_melee(BOSS, WARRIOR, PRIEST, 17, "Power Word: Shield", 200)
    b.swing_missed(BOSS, WARRIOR, "ABSORB", 500)
    b.absorbed_melee(BOSS, WARRIOR, PRIEST, 17, "Power Word: Shield", 500)
    # 21:00:15 curaciones
    b.wait(2000).cast(PRIEST, WARRIOR, 2061, "Flash Heal", "0x2")
    b.heal(PRIEST, WARRIOR, 2061, "Flash Heal", 2500, overheal=500)
    b.wait(1000).heal(PRIEST, WARRIOR, 139, "Renew", 1000, overheal=1000, periodic=True)
    b.wait(1000).heal(PRIEST, MAGE, 2061, "Flash Heal", 1500, heal_absorbed=200)
    # 21:00:20 interrupción y dispel
    b.wait(3000).interrupt(WARRIOR, BOSS, 6552, "Pummel", 90300, "Shadow Bolt Volley")
    b.wait(1000).dispel(PRIEST, MAGE, 527, "Dispel Magic", 122, "Frost Nova")
    # 21:00:22 daño propio: no es daño realizado, sí daño recibido
    b.wait(1000).spell_damage(WARRIOR, WARRIOR, 2687, "Bloodrage", 100, info=WARRIOR)
    # 21:00:25 cazador
    b.wait(3000).cast(HUNTER, BOSS, 19434, "Aimed Shot")
    b.spell_damage(HUNTER, BOSS, 19434, "Aimed Shot", 1500, hp=900000, max_hp=1000000)
    b.range_damage(HUNTER, BOSS, 400)
    b.cast(HUNTER, None, 19506, "Trueshot Aura")
    # 21:00:30 Fingir muerte: UNIT_DIED que no es muerte
    b.wait(5000).cast(HUNTER, None, 5384, "Feign Death")
    b.wait(500).died(HUNTER)
    # 21:00:40 muere el mago
    b.wait(9500).spell_damage(BOSS, MAGE, 90400, "Shadow Bolt", 5000, overkill=1200, school="0x20", info=MAGE)
    b.wait(100).died(MAGE)
    # 21:01:00 golpe final con overkill
    b.wait(19900).spell_damage(WARRIOR, BOSS, 20662, "Execute", 4000, overkill=1500, hp=0, max_hp=1000000)
    b.wait(100).died(BOSS)
    b.wait(4900).encounter_end(99001, "Test Guardian", 3, 20, True, 60000)  # 21:01:05.000
    # Después del ENCOUNTER_END: no debe contarse
    b.wait(1000).spell_damage(WARRIOR, ADD, 12294, "Mortal Strike", 999)
    return b.text()


def wipe_then_kill() -> str:
    b = LogBuilder(datetime(2026, 10, 15, 22, 0, 0))
    b.wait(1000).zone(9999, "Hyjal Summit", 3)
    # Intento 1: wipe al 40 %
    b.wait(1000).encounter_start(99001, "Test Guardian", 3, 20, 9999)
    b.wait(1000).spell_damage(WARRIOR, BOSS, 12294, "Mortal Strike", 1000, hp=400000, max_hp=1000000)
    b.wait(29000).encounter_end(99001, "Test Guardian", 3, 20, False, 30000)
    # Intento 2: kill de 40 s
    b.wait(60000).encounter_start(99001, "Test Guardian", 3, 20, 9999)
    b.wait(1000).spell_damage(WARRIOR, BOSS, 12294, "Mortal Strike", 2000)
    b.wait(1000).spell_damage(MAGE, BOSS, 116, "Frostbolt", 2000, school="0x10")
    b.wait(38000).encounter_end(99001, "Test Guardian", 3, 20, True, 40000)
    return b.text()


def truncated() -> str:
    b = LogBuilder(datetime(2026, 10, 16, 20, 0, 0))
    b.wait(1000).encounter_start(99001, "Test Guardian", 3, 20, 9999)
    b.wait(1000).spell_damage(WARRIOR, BOSS, 12294, "Mortal Strike", 1000)
    b.wait(1000).spell_damage(WARRIOR, BOSS, 12294, "Mortal Strike", 1000)
    return b.text()


def legacy_no_year() -> str:
    """Formato viejo: sin año, sin huso horario y sin log avanzado; cruza fin de año."""
    b = LogBuilder(
        datetime(2026, 12, 31, 23, 59, 50),
        utc_offset=None,
        with_year=False,
        advanced=False,
        build="1.15.7",
        project_id=2,
    )
    b.encounter_start(99001, "Test Guardian", 3, 20, 9999)
    b.wait(5000).spell_damage(WARRIOR, BOSS, 12294, "Mortal Strike", 1000)
    b.wait(5000).spell_damage(WARRIOR, BOSS, 12294, "Mortal Strike", 1000)  # 00:00:00 del 1/1
    b.wait(1000).heal(PRIEST, WARRIOR, 2061, "Flash Heal", 900, overheal=100)
    b.wait(9000).encounter_end(99001, "Test Guardian", 3, 20, True, 20000)
    return b.text()


def battleground() -> str:
    ally = [player(10, "Aldren", flags="0x511"), player(11, "Marisol")]
    horde = [player(20, "Grosh", flags="0x548"), player(21, "Zul'kah", flags="0x548")]
    b = LogBuilder(datetime(2026, 11, 20, 19, 0, 0))
    b.wait(1000).zone(8888, "Darkspear Islands", 0)
    b.wait(1000).spell_damage(ally[0], horde[0], 12294, "Mortal Strike", 1500)
    b.wait(1000).spell_damage(horde[1], ally[1], 116, "Frostbolt", 800, school="0x10")
    b.wait(1000).heal(ally[1], ally[0], 2061, "Flash Heal", 700, overheal=100)
    b.wait(1000).spell_damage(ally[0], horde[0], 20662, "Execute", 1200, overkill=300)
    b.wait(100).died(horde[0])
    b.wait(60000).zone(1, "Durotar", 0)
    return b.text()


def quoted_names() -> str:
    odd = Unit("Player-5000-0000000A", "Ca,ma-Testrealm", "0x514")
    target = creature(90003, 3, "Dummy, Grand")
    b = LogBuilder(datetime(2026, 10, 17, 18, 0, 0))
    b.wait(1000).encounter_start(99002, "Training, the Dummy", 3, 20, 9999)
    b.wait(1000).spell_damage(odd, target, 116, "Frostbolt", 700, school="0x10")
    b.wait(19000).encounter_end(99002, "Training, the Dummy", 3, 20, True, 20000)
    return b.text()


def write_all() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    files = {
        "basic_kill.txt": basic_kill(),
        "wipe_then_kill.txt": wipe_then_kill(),
        "truncated.txt": truncated(),
        "legacy_no_year.txt": legacy_no_year(),
        "battleground.txt": battleground(),
        "quoted_names.txt": quoted_names(),
    }
    for name, text in files.items():
        (OUT / name).write_text(text, encoding="utf-8", newline="\n")
    print(f"{len(files)} fixtures escritos en {OUT}")


if __name__ == "__main__":
    write_all()
