"""Constantes del formato de combat log.

Fuentes (ver docs/RESEARCH.md):
- warcraft.wiki.gg/wiki/COMBAT_LOG_EVENT (parámetros base, prefijos, sufijos, bloque avanzado)
- wowcoach.gg/docs/combat-log/line-format (máscaras de flags de unidad, formato de timestamp)
"""

from __future__ import annotations

# --- Flags de unidad (sourceFlags / destFlags) ---------------------------------
AFFILIATION_MASK = 0x0000000F
AFFILIATION_MINE = 0x1
AFFILIATION_PARTY = 0x2
AFFILIATION_RAID = 0x4
AFFILIATION_OUTSIDER = 0x8

REACTION_MASK = 0x000000F0
REACTION_FRIENDLY = 0x10
REACTION_NEUTRAL = 0x20
REACTION_HOSTILE = 0x40

CONTROL_MASK = 0x00000300
CONTROL_PLAYER = 0x100
CONTROL_NPC = 0x200

TYPE_MASK = 0x0000FC00
TYPE_PLAYER = 0x400
TYPE_NPC = 0x800
TYPE_PET = 0x1000
TYPE_GUARDIAN = 0x2000
TYPE_OBJECT = 0x4000

NIL_GUID = "0000000000000000"

GUID_PREFIXES = ("Player-", "Creature-", "Pet-", "Vehicle-", "GameObject-", "Vignette-", "Item-")

# Eventos especiales (sin prefijo/sufijo estándar)
SPECIAL_EVENTS = {
    "ENCOUNTER_START",
    "ENCOUNTER_END",
    "ZONE_CHANGE",
    "MAP_CHANGE",
    "COMBATANT_INFO",
    "UNIT_DIED",
    "UNIT_DESTROYED",
    "UNIT_DISSIPATES",
    "PARTY_KILL",
    "CHALLENGE_MODE_START",
    "CHALLENGE_MODE_END",
    "ARENA_MATCH_START",
    "ARENA_MATCH_END",
    "EMOTE",
    "WORLD_MARKER_PLACED",
    "WORLD_MARKER_REMOVED",
    "ENCHANT_APPLIED",
    "ENCHANT_REMOVED",
    "COMBAT_LOG_VERSION",
}

# Prefijos con información de hechizo (spellId, spellName, spellSchool)
SPELL_PREFIXES = ("SPELL_BUILDING_", "SPELL_PERIODIC_", "SPELL_", "RANGE_")

# Sufijos que llevan el bloque de "Advanced Combat Logging" antes del sufijo.
ADVANCED_SUFFIXES = {
    "_DAMAGE",
    "_DAMAGE_LANDED",
    "_HEAL",
    "_CAST_SUCCESS",
    "_ENERGIZE",
    "_DRAIN",
    "_LEECH",
}

# Cantidad de parámetros del bloque avanzado según la wiki (infoGUID ... level).
# Se recalibra por archivo usando eventos *_CAST_SUCCESS (ver parser.py).
DEFAULT_ADVANCED_BLOCK = 17

# Hechizos que generan UNIT_DIED sin ser una muerte real (Fingir muerte del cazador).
FEIGN_DEATH_SPELL_IDS = {5384}
FEIGN_DEATH_SPELL_NAMES = {"feign death", "fingir muerte"}
