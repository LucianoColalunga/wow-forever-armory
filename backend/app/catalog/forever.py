"""Catálogo de contenido de WoW: Forever con su estado de verificación.

Reglas:
- ``official``: aparece en una publicación de Blizzard (news.blizzard.com).
- ``reported``: lo publican wikis o guías de terceros; no se muestra en rankings hasta que
  un admin lo marque como verificado.
- No se inventan IDs de instancia ni de encuentro: Blizzard no los publicó. Las instancias se
  asocian por nombre de zona del combat log (``ZONE_CHANGE``) y el admin puede fijar IDs.
- Los nombres de jefes salen de los propios logs (``ENCOUNTER_START``), no de este archivo.

Fecha de relevamiento: 14/10/2026. Ver docs/RESEARCH.md para el detalle de fuentes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

BLIZZ_CARVE = "https://news.blizzard.com/en-us/article/24302093/carve-a-new-path-with-world-of-warcraft-forever"
BLIZZ_NEXT = "https://news.blizzard.com/en-us/article/24303862/world-of-warcraft-forever-whats-next-panel-recap"
WIKI_FOREVER = "https://warcraft.wiki.gg/wiki/World_of_Warcraft:_Forever"


@dataclass(frozen=True, slots=True)
class CatalogInstance:
    slug: str
    name: str
    kind: str  # raid | dungeon | battleground
    max_players: int | None
    verification: str  # official | reported
    source_url: str
    is_new_in_forever: bool
    level_range: str | None = None
    notes: str = ""
    aliases: tuple[str, ...] = field(default_factory=tuple)


CATALOG: tuple[CatalogInstance, ...] = (
    # --- Bandas (Blizzard: "Hyjal Summit" 20 jugadores, "Barrow Deeps" 10 jugadores) ---
    CatalogInstance("barrow-deeps", "Barrow Deeps", "raid", 10, "official", BLIZZ_NEXT, True, "60",
                    "Desafío de nivel máximo para 10 jugadores. Desbloqueo anunciado: 9/12/2026."),
    CatalogInstance("hyjal-summit", "Hyjal Summit", "raid", 20, "official", BLIZZ_NEXT, True, "60",
                    "Banda de 20 jugadores. Desbloqueo anunciado: 9/12/2026."),
    CatalogInstance("onyxias-lair", "Onyxia's Lair", "raid", 40, "reported", WIKI_FOREVER, False, "60",
                    "Listada por warcraft.wiki.gg como banda de lanzamiento (40). Pendiente de confirmación oficial."),
    # --- Mazmorras nuevas (nombradas por Blizzard en el panel "What's Next") ---
    CatalogInstance("hall-of-thanes", "The Hall of Thanes", "dungeon", 5, "official", BLIZZ_NEXT, True, "13-18",
                    aliases=("Hall of Thanes",)),
    CatalogInstance("ruins-of-lordaeron", "Ruins of Lordaeron", "dungeon", 5, "official", BLIZZ_NEXT, True, "15-20"),
    CatalogInstance("excavation-site-wetlands", "Excavation Site: Wetlands", "dungeon", 5, "reported", WIKI_FOREVER,
                    True, "24-29", "Blizzard la menciona sin nombre exacto; el nombre sale de la wiki."),
    CatalogInstance("city-of-dalaran", "City of Dalaran", "dungeon", 5, "official", BLIZZ_NEXT, True, "28-33"),
    CatalogInstance("the-drowned-city", "The Drowned City", "dungeon", 5, "official", BLIZZ_NEXT, True, "35-40",
                    aliases=("Drowned City",)),
    CatalogInstance("kroldok-stronghold", "Krol'dok Stronghold", "dungeon", 5, "official", BLIZZ_NEXT, True, "40-45"),
    CatalogInstance("alcaz-prison", "Alcaz Prison", "dungeon", 5, "official", BLIZZ_NEXT, True, "48-53"),
    CatalogInstance("blackmaw-hold", "Blackmaw Hold", "dungeon", 5, "official", BLIZZ_NEXT, True, "55-60"),
    CatalogInstance("shapers-terrace", "Shaper's Terrace", "dungeon", 5, "official", BLIZZ_NEXT, True, "58-60"),
    # --- Mazmorras clásicas que la wiki lista como presentes ---
    CatalogInstance("ragefire-chasm", "Ragefire Chasm", "dungeon", 5, "reported", WIKI_FOREVER, False),
    CatalogInstance("the-deadmines", "The Deadmines", "dungeon", 5, "reported", WIKI_FOREVER, False,
                    aliases=("Deadmines",)),
    CatalogInstance("wailing-caverns", "Wailing Caverns", "dungeon", 5, "reported", WIKI_FOREVER, False),
    CatalogInstance("scholomance", "Scholomance", "dungeon", 5, "reported", WIKI_FOREVER, False),
    CatalogInstance("stratholme", "Stratholme", "dungeon", 5, "reported", WIKI_FOREVER, False),
    CatalogInstance("blackrock-depths", "Blackrock Depths", "dungeon", 5, "reported", WIKI_FOREVER, False),
    # --- Campos de batalla ---
    CatalogInstance("darkspear-islands", "Darkspear Islands", "battleground", 15, "official", BLIZZ_NEXT, True,
                    notes="Campo de batalla 15 vs 15 anunciado por Blizzard."),
    CatalogInstance("warsong-gulch", "Warsong Gulch", "battleground", 10, "reported", WIKI_FOREVER, False,
                    notes="Guías de terceros lo dan por presente; Blizzard no lo confirmó."),
    CatalogInstance("arathi-basin", "Arathi Basin", "battleground", 15, "reported", WIKI_FOREVER, False,
                    notes="Guías de terceros lo dan por presente; Blizzard no lo confirmó."),
    CatalogInstance("alterac-valley", "Alterac Valley", "battleground", 40, "reported", WIKI_FOREVER, False,
                    notes="Guías de terceros lo dan por presente; Blizzard no lo confirmó."),
)  # fmt: skip

# Modalidades PvP: sólo se ofrecen rankings de las confirmadas.
PVP_MODES: tuple[dict[str, str], ...] = (
    {"key": "battlegrounds", "label": "Campos de batalla", "status": "official",
     "detail": "Darkspear Islands (15 vs 15) anunciado por Blizzard."},
    {"key": "rated", "label": "PvP puntuado", "status": "not_available",
     "detail": "Guías de terceros citan la sesión de preguntas del 17/09 diciendo que no habrá PvP puntuado. "
               "No hay rating oficial: este sitio no publica ratings."},
    {"key": "arenas", "label": "Arenas", "status": "unconfirmed",
     "detail": "Ningún anuncio de Blizzard menciona arenas para Forever."},
    {"key": "honor", "label": "Honor y rangos", "status": "reported",
     "detail": "Guías de terceros describen 14 rangos de honor por temporada. Sin fuente oficial "
               "ni API: no se publica ranking de honor."},
)  # fmt: skip

_BY_NAME: dict[str, CatalogInstance] = {}
for _inst in CATALOG:
    _BY_NAME[_inst.name.lower()] = _inst
    for _alias in _inst.aliases:
        _BY_NAME[_alias.lower()] = _inst


def find_by_zone_name(zone_name: str | None) -> CatalogInstance | None:
    if not zone_name:
        return None
    return _BY_NAME.get(zone_name.strip().lower())


def find_by_slug(slug: str) -> CatalogInstance | None:
    for inst in CATALOG:
        if inst.slug == slug:
            return inst
    return None


def classify_zone(zone_name: str | None) -> str | None:
    """Devuelve ``raid``, ``dungeon`` o ``battleground`` si la zona está en el catálogo."""
    inst = find_by_zone_name(zone_name)
    return inst.kind if inst else None
