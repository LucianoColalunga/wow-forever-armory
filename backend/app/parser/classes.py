"""Normalización e inferencia de clase y especialización.

El combat log no trae la clase de los jugadores en cada evento. Se usa, en orden:

1. ``COMBATANT_INFO`` con un ``specID`` conocido (confianza alta). La posición del campo en
   Forever no está documentada; sólo se acepta si el valor coincide con un specID conocido.
2. Hechizos característicos de cada clase/spec (confianza media). Forever modifica talentos y
   habilidades, así que es una heurística: puede corregirse desde el panel admin (auditado).
3. Rol observado (curación vs daño) para elegir la spec por defecto (confianza baja).
"""

from __future__ import annotations

import unicodedata
from collections import Counter
from dataclasses import dataclass

CLASSES: dict[str, dict[str, object]] = {
    "warrior": {"label": "Guerrero", "specs": ["arms", "fury", "protection"]},
    "paladin": {"label": "Paladín", "specs": ["holy", "protection", "retribution"]},
    "hunter": {"label": "Cazador", "specs": ["beast-mastery", "marksmanship", "survival"]},
    "rogue": {"label": "Pícaro", "specs": ["assassination", "combat", "subtlety"]},
    "priest": {"label": "Sacerdote", "specs": ["discipline", "holy", "shadow"]},
    "shaman": {"label": "Chamán", "specs": ["elemental", "enhancement", "restoration"]},
    "mage": {"label": "Mago", "specs": ["arcane", "fire", "frost"]},
    "warlock": {"label": "Brujo", "specs": ["affliction", "demonology", "destruction"]},
    "druid": {"label": "Druida", "specs": ["balance", "feral", "restoration"]},
}

SPEC_LABELS: dict[str, str] = {
    "arms": "Armas",
    "fury": "Furia",
    "protection": "Protección",
    "holy": "Sagrado",
    "retribution": "Reprensión",
    "beast-mastery": "Bestias",
    "marksmanship": "Puntería",
    "survival": "Supervivencia",
    "assassination": "Asesinato",
    "combat": "Combate",
    "subtlety": "Sutileza",
    "discipline": "Disciplina",
    "shadow": "Sombra",
    "elemental": "Elemental",
    "enhancement": "Mejora",
    "restoration": "Restauración",
    "arcane": "Arcano",
    "fire": "Fuego",
    "frost": "Escarcha",
    "affliction": "Aflicción",
    "demonology": "Demonología",
    "destruction": "Destrucción",
    "balance": "Equilibrio",
    "feral": "Feral",
}

HEALER_SPECS = {
    ("priest", "holy"),
    ("priest", "discipline"),
    ("paladin", "holy"),
    ("shaman", "restoration"),
    ("druid", "restoration"),
}
TANK_SPECS = {("warrior", "protection"), ("paladin", "protection"), ("druid", "feral")}

# specID de retail (estables desde Mists of Pandaria). Se aceptan sólo si aparecen en COMBATANT_INFO.
SPEC_IDS: dict[int, tuple[str, str]] = {
    71: ("warrior", "arms"), 72: ("warrior", "fury"), 73: ("warrior", "protection"),
    65: ("paladin", "holy"), 66: ("paladin", "protection"), 70: ("paladin", "retribution"),
    253: ("hunter", "beast-mastery"), 254: ("hunter", "marksmanship"), 255: ("hunter", "survival"),
    259: ("rogue", "assassination"), 260: ("rogue", "combat"), 261: ("rogue", "subtlety"),
    256: ("priest", "discipline"), 257: ("priest", "holy"), 258: ("priest", "shadow"),
    262: ("shaman", "elemental"), 263: ("shaman", "enhancement"), 264: ("shaman", "restoration"),
    62: ("mage", "arcane"), 63: ("mage", "fire"), 64: ("mage", "frost"),
    265: ("warlock", "affliction"), 266: ("warlock", "demonology"), 267: ("warlock", "destruction"),
    102: ("druid", "balance"), 103: ("druid", "feral"), 104: ("druid", "feral"), 105: ("druid", "restoration"),
}  # fmt: skip

_CLASS_ALIASES = {
    "warrior": "warrior", "guerrero": "warrior", "guerrera": "warrior",
    "paladin": "paladin", "paladín": "paladin",
    "hunter": "hunter", "cazador": "hunter", "cazadora": "hunter",
    "rogue": "rogue", "picaro": "rogue", "pícaro": "rogue", "picara": "rogue", "pícara": "rogue",
    "priest": "priest", "sacerdote": "priest", "sacerdotisa": "priest",
    "shaman": "shaman", "chaman": "shaman", "chamán": "shaman",
    "mage": "mage", "mago": "mage", "maga": "mage",
    "warlock": "warlock", "brujo": "warlock", "bruja": "warlock",
    "druid": "druid", "druida": "druid",
}  # fmt: skip


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.strip().lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def normalize_class(value: str | None) -> str | None:
    if not value:
        return None
    key = _fold(value).replace(" ", "").replace("_", "")
    for alias, slug in _CLASS_ALIASES.items():
        if _fold(alias) == key:
            return slug
    return None


def normalize_spec(class_slug: str | None, value: str | None) -> str | None:
    if not class_slug or not value:
        return None
    folded = _fold(value).replace(" ", "-").replace("_", "-")
    specs = CLASSES.get(class_slug, {}).get("specs", [])
    assert isinstance(specs, list)
    if folded in specs:
        return folded
    for spec, label in SPEC_LABELS.items():
        if spec in specs and _fold(label).replace(" ", "-") == folded:
            return spec
    aliases = {
        "bm": "beast-mastery",
        "mm": "marksmanship",
        "sv": "survival",
        "ret": "retribution",
        "prot": "protection",
        "resto": "restoration",
        "enh": "enhancement",
        "ele": "elemental",
        "disc": "discipline",
        "outlaw": "combat",
        "guardian": "feral",
        "bestias": "beast-mastery",
    }
    mapped = aliases.get(folded)
    return mapped if mapped in specs else None


# Hechizos característicos por clase (nombres en inglés del cliente).
CLASS_SIGNATURES: dict[str, set[str]] = {
    "warrior": {"heroic strike", "mortal strike", "bloodthirst", "shield slam", "sunder armor", "execute",
                "cleave", "revenge", "overpower", "battle shout", "hamstring", "rend", "thunder clap",
                "shield block", "bloodrage", "slam", "pummel", "shield bash", "whirlwind", "devastate",
                "recklessness", "death wish", "demoralizing shout", "intercept", "charge"},
    "paladin": {"holy light", "flash of light", "judgement", "judgement of righteousness",
                "seal of righteousness", "seal of command", "seal of the crusader", "seal of light",
                "seal of wisdom", "holy shock", "consecration", "blessing of might", "blessing of kings",
                "blessing of wisdom", "hammer of justice", "divine shield", "lay on hands", "holy shield",
                "exorcism", "hammer of wrath", "cleanse", "righteous fury", "crusader strike"},
    "hunter": {"aimed shot", "multi-shot", "arcane shot", "serpent sting", "auto shot", "steady shot",
               "hunter's mark", "raptor strike", "mongoose bite", "wing clip", "feign death",
               "bestial wrath", "trueshot aura", "rapid fire", "volley", "wyvern sting", "kill command",
               "tranquilizing shot", "concussive shot", "scatter shot", "explosive trap effect"},
    "rogue": {"sinister strike", "backstab", "eviscerate", "slice and dice", "rupture", "ambush", "garrote",
              "kick", "hemorrhage", "blade flurry", "adrenaline rush", "cold blood", "expose armor",
              "kidney shot", "cheap shot", "gouge", "instant poison", "deadly poison", "mutilate",
              "vanish", "evasion", "sprint", "ghostly strike"},
    "priest": {"flash heal", "greater heal", "renew", "power word: shield", "prayer of healing", "mind blast",
               "shadow word: pain", "mind flay", "holy fire", "smite", "shadowform", "vampiric embrace",
               "power word: fortitude", "inner fire", "psychic scream", "dispel magic", "abolish disease",
               "holy nova", "lightwell", "power infusion", "inner focus", "desperate prayer", "fade",
               "prayer of mending", "circle of healing"},
    "shaman": {"lightning bolt", "chain lightning", "earth shock", "flame shock", "frost shock",
               "healing wave", "lesser healing wave", "chain heal", "stormstrike", "windfury attack",
               "windfury weapon", "searing totem", "windfury totem", "mana tide totem", "grace of air totem",
               "strength of earth totem", "purge", "lightning shield", "elemental mastery",
               "flametongue weapon", "ghost wolf", "tremor totem", "earth shield"},
    "mage": {"frostbolt", "fireball", "arcane missiles", "arcane explosion", "blizzard", "scorch", "pyroblast",
             "fire blast", "cone of cold", "frost nova", "ice block", "ice barrier", "arcane intellect",
             "arcane power", "combustion", "polymorph", "counterspell", "blast wave", "presence of mind",
             "flamestrike", "ice lance", "evocation", "mana shield", "remove lesser curse", "ignite",
             "arcane blast"},
    "warlock": {"shadow bolt", "corruption", "curse of agony", "immolate", "searing pain", "life tap",
                "drain life", "drain soul", "curse of the elements", "curse of shadow",
                "curse of recklessness", "curse of doom", "siphon life", "conflagrate", "shadowburn",
                "hellfire", "rain of fire", "fear", "death coil", "soul fire", "demon armor",
                "health funnel", "spell lock", "unstable affliction"},
    "druid": {"wrath", "starfire", "moonfire", "insect swarm", "rejuvenation", "regrowth", "healing touch",
              "swiftmend", "tranquility", "maul", "swipe", "shred", "claw", "rake", "ferocious bite", "rip",
              "bear form", "dire bear form", "cat form", "moonkin form", "mark of the wild", "gift of the wild",
              "thorns", "innervate", "faerie fire", "faerie fire (feral)", "entangling roots", "hurricane",
              "remove curse", "abolish poison", "barkskin", "rebirth", "growl", "demoralizing roar", "bash",
              "lifebloom", "mangle (bear)", "mangle (cat)"},
}  # fmt: skip

SPEC_SIGNATURES: dict[tuple[str, str], set[str]] = {
    ("warrior", "arms"): {"mortal strike", "sweeping strikes"},
    ("warrior", "fury"): {"bloodthirst", "rampage", "death wish"},
    ("warrior", "protection"): {"shield slam", "concussion blow", "last stand", "devastate"},
    ("paladin", "holy"): {"holy shock", "divine favor"},
    ("paladin", "protection"): {"holy shield", "avenger's shield"},
    ("paladin", "retribution"): {"seal of command", "repentance", "crusader strike"},
    ("hunter", "beast-mastery"): {"bestial wrath", "intimidation"},
    ("hunter", "marksmanship"): {"trueshot aura", "scatter shot", "aimed shot"},
    ("hunter", "survival"): {"wyvern sting", "counterattack", "deterrence"},
    ("rogue", "assassination"): {"cold blood", "mutilate"},
    ("rogue", "combat"): {"blade flurry", "adrenaline rush", "riposte"},
    ("rogue", "subtlety"): {"hemorrhage", "premeditation", "preparation", "ghostly strike"},
    ("priest", "discipline"): {"power infusion", "divine spirit", "pain suppression"},
    ("priest", "holy"): {"lightwell", "circle of healing"},
    ("priest", "shadow"): {"shadowform", "mind flay", "vampiric embrace", "silence"},
    ("shaman", "elemental"): {"elemental mastery", "totem of wrath"},
    ("shaman", "enhancement"): {"stormstrike", "shamanistic rage"},
    ("shaman", "restoration"): {"mana tide totem", "earth shield"},
    ("mage", "arcane"): {"arcane power", "presence of mind", "slow"},
    ("mage", "fire"): {"combustion", "pyroblast", "blast wave", "dragon's breath"},
    ("mage", "frost"): {"ice barrier", "cold snap", "summon water elemental"},
    ("warlock", "affliction"): {"siphon life", "curse of exhaustion", "unstable affliction", "dark pact"},
    ("warlock", "demonology"): {"soul link", "summon felguard"},
    ("warlock", "destruction"): {"conflagrate", "shadowburn", "shadowfury"},
    ("druid", "balance"): {"moonkin form", "insect swarm", "force of nature"},
    ("druid", "feral"): {"faerie fire (feral)", "mangle (bear)", "mangle (cat)", "leader of the pack"},
    ("druid", "restoration"): {"swiftmend", "tree of life", "lifebloom"},
}

_DEFAULT_SPEC_BY_ROLE: dict[tuple[str, str], str] = {
    ("priest", "healer"): "holy", ("priest", "dps"): "shadow",
    ("paladin", "healer"): "holy", ("paladin", "tank"): "protection", ("paladin", "dps"): "retribution",
    ("shaman", "healer"): "restoration", ("druid", "healer"): "restoration", ("druid", "tank"): "feral",
    ("warrior", "tank"): "protection",
}  # fmt: skip


@dataclass(slots=True)
class ClassGuess:
    class_slug: str | None
    spec: str | None
    source: str  # combatant_info | signature | role | unknown
    confidence: float


def infer_class_spec(
    spell_names: Counter[str],
    spec_id: int | None,
    role_hint: str | None,
) -> ClassGuess:
    """Infiere clase y spec de un jugador a partir de lo observado en el log."""
    if spec_id is not None and spec_id in SPEC_IDS:
        cls, spec = SPEC_IDS[spec_id]
        return ClassGuess(cls, spec, "combatant_info", 0.95)

    names = Counter({_fold(k): v for k, v in spell_names.items()})
    class_scores: Counter[str] = Counter()
    for cls, sigs in CLASS_SIGNATURES.items():
        for name, count in names.items():
            if name in sigs:
                class_scores[cls] += count
    if not class_scores:
        return ClassGuess(None, None, "unknown", 0.0)
    (best_cls, best), *rest = class_scores.most_common()
    runner_up = rest[0][1] if rest else 0
    if best <= runner_up:
        return ClassGuess(None, None, "unknown", 0.0)
    cls_conf = round(min(0.9, 0.5 + 0.4 * (best - runner_up) / best), 2)

    spec_scores: Counter[str] = Counter()
    for (cls, spec), sigs in SPEC_SIGNATURES.items():
        if cls != best_cls:
            continue
        for name, count in names.items():
            if name in sigs:
                spec_scores[spec] += count
    if spec_scores:
        top = spec_scores.most_common(2)
        if len(top) == 1 or top[0][1] > top[1][1]:
            return ClassGuess(best_cls, top[0][0], "signature", cls_conf)
    if role_hint:
        role_spec = _DEFAULT_SPEC_BY_ROLE.get((best_cls, role_hint))
        if role_spec:
            return ClassGuess(best_cls, role_spec, "role", min(cls_conf, 0.4))
    return ClassGuess(best_cls, None, "signature", cls_conf)


def role_for(class_slug: str | None, spec: str | None, healing_share: float, damage_taken_share: float) -> str:
    if class_slug and spec:
        if (class_slug, spec) in HEALER_SPECS and healing_share >= 0.3:
            return "healer"
        if (class_slug, spec) in TANK_SPECS and damage_taken_share >= 0.25:
            return "tank"
    if healing_share >= 0.6:
        return "healer"
    if damage_taken_share >= 0.35:
        return "tank"
    return "dps"
