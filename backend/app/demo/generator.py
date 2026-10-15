"""Generador de datos de DEMOSTRACIÓN (sintéticos y deterministas).

Todo lo que produce este módulo es ficticio:
- La cabecera usa ``BUILD_VERSION,1.60.1-DEMO`` → el importador lo clasifica siempre como dataset ``demo``.
- Los jefes tienen IDs 990001+ y nombres inventados con el sufijo "(demo)".
- Personajes, hermandades y reinos son inventados.
Las zonas usan nombres del catálogo (Hyjal Summit, Barrow Deeps, Blackmaw Hold, Darkspear Islands)
sólo para poder navegar las páginas de instancia con datos de ejemplo.
"""

from __future__ import annotations

import random
import zlib
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.demo.logbuilder import LogBuilder, Unit, creature, player
from app.parser.classes import SPEC_IDS

DEMO_BUILD = "1.60.1-DEMO"

# (clase, spec, rol, hechizo principal, id, escuela, dps/hps base)
ARCHETYPES: list[tuple[str, str, str, str, int, str, int]] = [
    ("warrior", "protection", "tank", "Shield Slam", 23922, "0x1", 260),
    ("warrior", "fury", "dps", "Bloodthirst", 23881, "0x1", 520),
    ("warrior", "arms", "dps", "Mortal Strike", 12294, "0x1", 500),
    ("rogue", "combat", "dps", "Sinister Strike", 1752, "0x1", 540),
    ("rogue", "assassination", "dps", "Mutilate", 1329, "0x1", 530),
    ("mage", "fire", "dps", "Fireball", 133, "0x4", 560),
    ("mage", "frost", "dps", "Frostbolt", 116, "0x10", 520),
    ("warlock", "destruction", "dps", "Shadow Bolt", 686, "0x20", 550),
    ("warlock", "affliction", "dps", "Corruption", 172, "0x20", 510),
    ("hunter", "marksmanship", "dps", "Aimed Shot", 19434, "0x1", 530),
    ("hunter", "beast-mastery", "dps", "Arcane Shot", 3044, "0x40", 500),
    ("priest", "shadow", "dps", "Mind Flay", 15407, "0x20", 470),
    ("druid", "balance", "dps", "Starfire", 2912, "0x40", 480),
    ("shaman", "enhancement", "dps", "Stormstrike", 17364, "0x1", 500),
    ("priest", "holy", "healer", "Greater Heal", 2060, "0x2", 430),
    ("priest", "discipline", "healer", "Power Word: Shield", 17, "0x2", 300),
    ("paladin", "holy", "healer", "Holy Light", 635, "0x2", 450),
    ("druid", "restoration", "healer", "Rejuvenation", 774, "0x8", 420),
    ("shaman", "restoration", "healer", "Chain Heal", 1064, "0x8", 440),
    ("paladin", "protection", "tank", "Holy Shield", 20925, "0x2", 240),
]
SIGNATURE: dict[tuple[str, str], tuple[str, int]] = {
    ("warrior", "protection"): ("Shield Slam", 23922), ("warrior", "fury"): ("Bloodthirst", 23881),
    ("warrior", "arms"): ("Mortal Strike", 12294), ("rogue", "combat"): ("Blade Flurry", 13877),
    ("rogue", "assassination"): ("Mutilate", 1329), ("mage", "fire"): ("Pyroblast", 11366),
    ("mage", "frost"): ("Ice Barrier", 11426), ("warlock", "destruction"): ("Conflagrate", 17962),
    ("warlock", "affliction"): ("Siphon Life", 18265), ("hunter", "marksmanship"): ("Trueshot Aura", 19506),
    ("hunter", "beast-mastery"): ("Bestial Wrath", 19574), ("priest", "shadow"): ("Shadowform", 15473),
    ("druid", "balance"): ("Moonkin Form", 24858), ("shaman", "enhancement"): ("Stormstrike", 17364),
    ("priest", "holy"): ("Circle of Healing", 34861), ("priest", "discipline"): ("Power Infusion", 10060),
    ("paladin", "holy"): ("Holy Shock", 20473), ("druid", "restoration"): ("Swiftmend", 18562),
    ("shaman", "restoration"): ("Mana Tide Totem", 16190), ("paladin", "protection"): ("Holy Shield", 20925),
}  # fmt: skip

SYLLABLES_A = [
    "Ae",
    "Bra",
    "Cor",
    "Dal",
    "El",
    "Fen",
    "Gor",
    "Hal",
    "Ith",
    "Jor",
    "Kael",
    "Lor",
    "Mor",
    "Nyl",
    "Or",
    "Pel",
    "Quel",
    "Ryn",
    "Syl",
    "Thal",
    "Ul",
    "Vor",
    "Wyn",
    "Xan",
    "Yse",
    "Zar",
]
SYLLABLES_B = [
    "adan",
    "bris",
    "cor",
    "dris",
    "eth",
    "fyn",
    "gar",
    "hild",
    "ion",
    "jas",
    "kith",
    "lia",
    "mir",
    "nor",
    "oth",
    "rak",
    "sha",
    "thas",
    "uin",
    "vash",
    "wen",
    "xis",
    "yra",
    "zul",
]


@dataclass
class DemoPlayer:
    unit: Unit
    class_slug: str
    spec: str
    role: str
    spell: str
    spell_id: int
    school: str
    base: int
    skill: float


@dataclass
class DemoBoss:
    encounter_id: int
    name: str
    hp: int


RAIDS = {
    "Hyjal Summit": {
        "size": 20,
        "difficulty": 148,
        "instance": 990100,
        "bosses": [
            DemoBoss(990001, "Centinela de Ceniza (demo)", 3_200_000),
            DemoBoss(990002, "Archidruida Marchito (demo)", 3_800_000),
            DemoBoss(990003, "Tejedora de Tormentas (demo)", 4_400_000),
        ],
    },
    "Barrow Deeps": {
        "size": 10,
        "difficulty": 3,
        "instance": 990200,
        "bosses": [
            DemoBoss(990011, "Guardián del Túmulo (demo)", 1_500_000),
            DemoBoss(990012, "Reina Sepulcral (demo)", 1_900_000),
        ],
    },
}
DUNGEON = {
    "name": "Blackmaw Hold",
    "instance": 990300,
    "bosses": [
        DemoBoss(990021, "Capataz Fauceoscura (demo)", 240_000),
        DemoBoss(990022, "Vidente de las Mareas (demo)", 300_000),
    ],
}

GUILDS = [("Vigilia Eterna", "Alianza Demo"), ("Brasas del Alba", "Alianza Demo"), ("Colmillo Rúnico", "Horda Demo")]


class DemoWorld:
    def __init__(self, seed: int = 2026) -> None:
        self.rng = random.Random(seed)
        self.counter = 1
        self.used: set[str] = set()
        self.rosters: dict[str, list[DemoPlayer]] = {}
        for gname, realm in GUILDS:
            flags_logger = "0x511"
            roster: list[DemoPlayer] = []
            for i in range(22):
                arche = ARCHETYPES[i % len(ARCHETYPES)] if i < len(ARCHETYPES) else self.rng.choice(ARCHETYPES)
                roster.append(self._player(arche, realm.replace(" ", ""), flags_logger if i == 0 else "0x514"))
            self.rosters[gname] = roster

    def _name(self) -> str:
        while True:
            n = self.rng.choice(SYLLABLES_A) + self.rng.choice(SYLLABLES_B)
            if n not in self.used:
                self.used.add(n)
                return n

    def _player(self, arche: tuple[str, str, str, str, int, str, int], realm: str, flags: str) -> DemoPlayer:
        cls, spec, role, spell, sid, school, base = arche
        u = player(0x9000 + self.counter, self._name(), realm=realm, flags=flags)
        self.counter += 1
        return DemoPlayer(u, cls, spec, role, spell, sid, school, base, skill=self.rng.uniform(0.78, 1.18))


# specID de cada arquetipo (los mismos que usa COMBATANT_INFO).
_SPEC_ID = {cs: sid for sid, cs in sorted(SPEC_IDS.items(), reverse=True)}
_INTERRUPTS = {
    "warrior": (6552, "Pummel"),
    "rogue": (1766, "Kick"),
    "mage": (2139, "Counterspell"),
    "shaman": (8042, "Earth Shock"),
}
_EMPTY_SLOTS = {3, 18}  # camisa y tabardo vacíos
# Hechizos secundarios por clase (para que la línea de tiempo de la demo tenga variedad).
_SECONDARY: dict[str, list[tuple[str, int, str]]] = {
    "warrior": [("Heroic Strike", 78, "0x1"), ("Whirlwind", 1680, "0x1")],
    "rogue": [("Eviscerate", 2098, "0x1"), ("Rupture", 1943, "0x1")],
    "mage": [("Fire Blast", 2136, "0x4"), ("Arcane Missiles", 5143, "0x40")],
    "warlock": [("Immolate", 348, "0x4"), ("Curse of Agony", 980, "0x20")],
    "hunter": [("Multi-Shot", 2643, "0x1"), ("Serpent Sting", 1978, "0x8")],
    "priest": [("Mind Blast", 8092, "0x20"), ("Shadow Word: Pain", 589, "0x20")],
    "druid": [("Moonfire", 8921, "0x40"), ("Wrath", 5176, "0x8")],
    "shaman": [("Earth Shock", 8042, "0x8"), ("Lightning Bolt", 403, "0x8")],
    "paladin": [("Judgement", 20271, "0x2"), ("Consecration", 26573, "0x2")],
}
_HEAL_SECONDARY: dict[str, list[tuple[str, int]]] = {
    "priest": [("Renew", 139), ("Flash Heal", 2061)],
    "paladin": [("Flash of Light", 19750)],
    "druid": [("Regrowth", 8936), ("Healing Touch", 5185)],
    "shaman": [("Healing Wave", 331), ("Lesser Healing Wave", 8004)],
}


def _demo_gear(p: DemoPlayer, week: int) -> str:
    """19 ranuras con IDs de objeto ficticios (rango 9.100.000+) que mejoran semana a semana."""
    base = 9_100_000 + (zlib.crc32(p.unit.guid.encode()) % 400) * 100  # estable entre ejecuciones
    out = []
    for slot in range(19):
        if slot in _EMPTY_SLOTS:
            out.append("(0,0,(),(),())")
            continue
        ilvl = 58 + 2 * week + (slot % 3)
        enchant = 990_000 + slot if slot in (0, 2, 4, 6, 8, 9, 14, 15) else 0
        gem = 991_000 + slot if slot in (0, 4) else 0
        out.append(f"({base + slot * 10 + week},{ilvl},({enchant},0,0),(),({gem}))")
    return "[" + ",".join(out) + "]"


def _boss_fight(
    b: LogBuilder,
    rng: random.Random,
    raid: list[DemoPlayer],
    boss: DemoBoss,
    difficulty: int,
    size: int,
    instance: int,
    kill: bool,
    week_factor: float,
    week: int = 0,
) -> None:
    boss_unit = creature(boss.encounter_id, rng.randint(1, 9999), boss.name)
    duration = rng.randint(150, 240) if kill else rng.randint(60, 140)
    b.encounter_start(boss.encounter_id, boss.name, difficulty, size, instance)
    for p in raid:
        faction = 0 if "HordaDemo" in p.unit.name else 1
        b.combatant_info(p.unit, faction, _SPEC_ID.get((p.class_slug, p.spec), 0), _demo_gear(p, week))
    hp = boss.hp
    tanks = [p for p in raid if p.role == "tank"] or raid[:1]
    healers = [p for p in raid if p.role == "healer"]
    dead: set[str] = set()
    for p in raid:
        sig = SIGNATURE.get((p.class_slug, p.spec))
        if sig:
            b.cast(p.unit, None, sig[1], sig[0])
    step_ms = 2500  # divide el balde de 5 s: evita un patrón de serrucho en la línea de tiempo
    midway = (duration * 1000 // 2 // step_ms) * step_ms
    for t in range(0, duration * 1000, step_ms):
        b.wait(step_ms)
        if t == midway:  # segundo uso del cooldown característico
            for p in raid:
                sig = SIGNATURE.get((p.class_slug, p.spec))
                if sig and p.unit.guid not in dead:
                    b.cast(p.unit, None, sig[1], sig[0])
        # el jefe golpea a un tanque y a veces a un jugador al azar
        tank = rng.choice(tanks)
        dmg = int(rng.uniform(1800, 3200))
        shield = 0
        disc = [h for h in healers if h.spec == "discipline"]
        if disc and rng.random() < 0.35:
            shield = int(dmg * rng.uniform(0.2, 0.5))
        b.swing(boss_unit, tank.unit, dmg - shield, absorbed=shield)
        if shield:
            b.absorbed_melee(boss_unit, tank.unit, disc[0].unit, 17, "Power Word: Shield", shield)
        if rng.random() < 0.25:
            victim = rng.choice(raid)
            if victim.unit.guid not in dead:
                big = int(rng.uniform(2000, 4500))
                lethal = rng.random() < (0.012 if kill else 0.05)
                b.spell_damage(
                    boss_unit,
                    victim.unit,
                    990900,
                    "Golpe Sombrío (demo)",
                    big,
                    overkill=int(big * 0.3) if lethal else -1,
                    school="0x20",
                    info=victim.unit,
                )
                if lethal:
                    b.died(victim.unit)
                    dead.add(victim.unit.guid)
        for p in raid:
            if p.unit.guid in dead:
                continue
            per_tick = p.base * p.skill * week_factor * step_ms / 1000 * rng.uniform(0.75, 1.25)
            if p.role in ("dps", "tank"):
                amount = int(per_tick)
                spell, spell_id, school = (p.spell, p.spell_id, p.school)
                if rng.random() > 0.6 and p.class_slug in _SECONDARY:
                    spell, spell_id, school = rng.choice(_SECONDARY[p.class_slug])
                b.cast(p.unit, boss_unit, spell_id, spell, school)
                if hp - amount <= 0 and kill and t >= (duration - 6) * 1000:
                    b.spell_damage(
                        p.unit,
                        boss_unit,
                        spell_id,
                        spell,
                        amount,
                        overkill=amount - max(hp, 0),
                        school=school,
                        hp=0,
                        max_hp=boss.hp,
                    )
                    hp = 0
                else:
                    hp = max(1, hp - amount)
                    b.spell_damage(p.unit, boss_unit, spell_id, spell, amount, school=school, hp=hp, max_hp=boss.hp)
                if p.class_slug in _INTERRUPTS and rng.random() < 0.04:
                    kick_id, kick = _INTERRUPTS[p.class_slug]
                    b.cast(p.unit, boss_unit, kick_id, kick)
                    b.interrupt(p.unit, boss_unit, kick_id, kick, 990901, "Cántico Prohibido (demo)")
            else:
                target = rng.choice(raid)
                amount = int(per_tick * 1.2)
                over = int(amount * rng.uniform(0.05, 0.45))
                if p.spec == "discipline" and rng.random() < 0.5:
                    b.cast(p.unit, target.unit, 17, "Power Word: Shield", "0x2")
                heal, heal_id = (p.spell, p.spell_id)
                if rng.random() > 0.6 and p.class_slug in _HEAL_SECONDARY:
                    heal, heal_id = rng.choice(_HEAL_SECONDARY[p.class_slug])
                b.cast(p.unit, target.unit, heal_id, heal, "0x2")
                b.heal(p.unit, target.unit, heal_id, heal, amount, overheal=over)
                if p.class_slug in ("priest", "paladin") and rng.random() < 0.05:
                    b.dispel(
                        p.unit,
                        target.unit,
                        527 if p.class_slug == "priest" else 4987,
                        "Dispel Magic" if p.class_slug == "priest" else "Cleanse",
                        990902,
                        "Maldición Ígnea (demo)",
                    )
        if kill and hp <= 0:
            break
    if kill:
        b.wait(200).died(boss_unit)
    b.wait(500).encounter_end(boss.encounter_id, boss.name, difficulty, size, kill, duration * 1000)


def raid_night(world: DemoWorld, guild: str, raid_name: str, start: datetime, week: int) -> str:
    rng = random.Random(f"{guild}-{raid_name}-{week}")
    cfg = RAIDS[raid_name]
    roster = world.rosters[guild]
    size: int = cfg["size"]  # type: ignore[assignment]
    tanks = [p for p in roster if p.role == "tank"][:2]
    healers = [p for p in roster if p.role == "healer"][: max(2, size // 5)]
    dps = [p for p in roster if p.role == "dps"]
    rng.shuffle(dps)
    raid = (tanks + healers + dps)[:size]
    b = LogBuilder(start, utc_offset=-3, build=DEMO_BUILD)
    b.wait(1000).zone(cfg["instance"], raid_name, cfg["difficulty"])  # type: ignore[arg-type]
    week_factor = 1.0 + 0.03 * week  # mejora de equipo semana a semana
    for boss in cfg["bosses"]:  # type: ignore[attr-defined]
        wipes = rng.choice([0, 0, 1, 2]) if week < 3 else rng.choice([0, 0, 0, 1])
        for _ in range(wipes):
            b.wait(rng.randint(60_000, 180_000))
            _boss_fight(b, rng, raid, boss, cfg["difficulty"], size, cfg["instance"], False, week_factor, week)  # type: ignore[arg-type]
        b.wait(rng.randint(60_000, 240_000))
        _boss_fight(b, rng, raid, boss, cfg["difficulty"], size, cfg["instance"], True, week_factor, week)  # type: ignore[arg-type]
    return b.text()


def dungeon_run(world: DemoWorld, guild: str, start: datetime, seed: int) -> str:
    rng = random.Random(f"dungeon-{guild}-{seed}")
    roster = world.rosters[guild]
    party = [next(p for p in roster if p.role == "tank"), next(p for p in roster if p.role == "healer")]
    party += rng.sample([p for p in roster if p.role == "dps"], 3)
    b = LogBuilder(start, utc_offset=-3, build=DEMO_BUILD)
    b.wait(1000).zone(DUNGEON["instance"], DUNGEON["name"], 1)  # type: ignore[arg-type]
    for boss in DUNGEON["bosses"]:  # type: ignore[attr-defined]
        b.wait(rng.randint(120_000, 300_000))
        _boss_fight(b, rng, party, boss, 1, 5, DUNGEON["instance"], True, 1.0)  # type: ignore[arg-type]
    b.wait(30_000).zone(1, "Azshara", 0)
    return b.text()


def battleground(world: DemoWorld, start: datetime, seed: int) -> str:
    rng = random.Random(f"bg-{seed}")
    ally_pool = world.rosters["Vigilia Eterna"] + world.rosters["Brasas del Alba"]
    horde_pool = world.rosters["Colmillo Rúnico"]
    ally = rng.sample(ally_pool, 15)
    horde = rng.sample(horde_pool, 15)
    logger = ally[0]
    b = LogBuilder(start, utc_offset=-3, build=DEMO_BUILD)
    b.wait(1000).zone(990400, "Darkspear Islands", 0)

    def as_enemy(p: DemoPlayer) -> Unit:
        return Unit(p.unit.guid, p.unit.name, "0x548")

    def as_friend(p: DemoPlayer) -> Unit:
        return Unit(p.unit.guid, p.unit.name, "0x511" if p is logger else "0x514")

    dead_until: dict[str, int] = {}
    for t in range(0, rng.randint(600, 900)):
        b.wait(1000)
        if rng.random() > 0.5:
            continue
        side_ally = rng.random() < 0.5
        attackers, defenders = (ally, horde) if side_ally else (horde, ally)
        a, d = rng.choice(attackers), rng.choice(defenders)
        if dead_until.get(a.unit.guid, -1) > t or dead_until.get(d.unit.guid, -1) > t:
            continue
        au = as_friend(a) if side_ally else as_enemy(a)
        du = as_enemy(d) if side_ally else as_friend(d)
        if a.role == "healer":
            friends = ally if side_ally else horde
            f = rng.choice(friends)
            fu = as_friend(f) if side_ally else as_enemy(f)
            amt = int(a.base * a.skill * rng.uniform(1.5, 3.0))
            b.heal(au, fu, a.spell_id, a.spell, amt, overheal=int(amt * rng.uniform(0, 0.3)))
            continue
        amt = int(a.base * a.skill * rng.uniform(1.5, 3.5))
        lethal = rng.random() < 0.08
        b.spell_damage(
            au, du, a.spell_id, a.spell, amt, overkill=int(amt * 0.2) if lethal else -1, school=a.school, info=du
        )
        if lethal:
            b.wait(50).died(du)
            dead_until[d.unit.guid] = t + 30
    b.wait(5000).zone(1, "Dustwallow Marsh", 0)
    return b.text()


def generate(start: datetime | None = None, weeks: int = 6) -> list[tuple[str, str, dict[str, str]]]:
    """Devuelve [(nombre_archivo, texto, metadatos_de_importación)]."""
    world = DemoWorld()
    if start is None:
        # Termina cerca de hoy para que la demo luzca "fresca"; el contenido es determinista.
        today = datetime.now().replace(hour=21, minute=0, second=0, microsecond=0)
        start = today - timedelta(days=7 * weeks + 1)
    base = start
    files: list[tuple[str, str, dict[str, str]]] = []
    for week in range(weeks):
        for gi, (guild, realm) in enumerate(GUILDS):
            night = base + timedelta(days=7 * week + gi)
            meta = {
                "guild_name": guild,
                "guild_realm": realm,
                "region": "us",
                "faction": "horde" if "Horda" in realm else "alliance",
            }
            files.append(
                (
                    f"demo-{guild.replace(' ', '_')}-hyjal-w{week + 1}.txt",
                    raid_night(world, guild, "Hyjal Summit", night, week),
                    meta,
                )
            )
            files.append(
                (
                    f"demo-{guild.replace(' ', '_')}-barrow-w{week + 1}.txt",
                    raid_night(world, guild, "Barrow Deeps", night + timedelta(days=1), week),
                    meta,
                )
            )
            if week % 2 == 0:
                files.append(
                    (
                        f"demo-{guild.replace(' ', '_')}-blackmaw-w{week + 1}.txt",
                        dungeon_run(world, guild, night + timedelta(days=2), week),
                        meta,
                    )
                )
        files.append(
            (
                f"demo-darkspear-w{week + 1}.txt",
                battleground(world, base + timedelta(days=7 * week + 3), week),
                {"region": "us"},
            )
        )
    # Mismo raid registrado por otro integrante: debe detectarse como duplicado y no inflar estadísticas.
    dup_text = raid_night(world, GUILDS[0][0], "Barrow Deeps", base + timedelta(days=1, seconds=7), 0)
    files.append(
        (
            "demo-duplicado-otro-logger.txt",
            dup_text,
            {"guild_name": GUILDS[0][0], "guild_realm": GUILDS[0][1], "region": "us"},
        )
    )
    return files
