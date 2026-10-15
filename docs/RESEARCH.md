# Investigación: WoW: Forever, fuentes de datos e integraciones

Relevamiento hecho el **14/10/2026** (beta abierta en curso; lanzamiento anunciado para el 4/11/2026).
Cada afirmación lleva su fuente. Lo que no se pudo verificar está marcado como tal y **no** se usa
como dato en la plataforma.

## 1. Qué es WoW: Forever

| Hecho | Estado | Fuente |
|---|---|---|
| Rama nueva de World of Warcraft que corre junto al WoW moderno y a WoW Classic; ambientada en el primer año de WoW, en una continuidad separada. | Oficial | [Blizzard: Carve a New Path](https://news.blizzard.com/en-us/article/24302093/carve-a-new-path-with-world-of-warcraft-forever), [Wikipedia](https://en.wikipedia.org/wiki/World_of_Warcraft:_Forever) |
| Nivel máximo 60, sin aumentos de nivel previstos. | Oficial | Blizzard (Carve a New Path) |
| Anunciado en BlizzCon el 12/09/2026; beta desde el 17/09; lanzamiento global el 4/11/2026 a las 15:00 PST. | Oficial | Blizzard (Carve a New Path) |
| Incluido en la suscripción / Game Time; paquetes opcionales (raza Skyborne). | Oficial | Blizzard (Carve a New Path) |
| Bandas: **Hyjal Summit** (20 jugadores) y **Barrow Deeps** (10 jugadores). | Oficial | [Blizzard: What's Next panel recap](https://news.blizzard.com/en-us/article/24303862/world-of-warcraft-forever-whats-next-panel-recap) |
| Desbloqueo de bandas el 9/12/2026, junto con Onyxia's Lair (40). | Hyjal/Barrow oficial; Onyxia según [warcraft.wiki.gg](https://warcraft.wiki.gg/wiki/World_of_Warcraft:_Forever) | — |
| Nueve mazmorras nuevas (Hall of Thanes, Ruins of Lordaeron, City of Dalaran, Drowned City, Krol'dok Stronghold, Alcaz Prison, Blackmaw Hold, Shaper's Terrace y una excavación en Wetlands). | Oficial (el nombre exacto de la excavación sale de la wiki) | Blizzard (What's Next), warcraft.wiki.gg |
| Campo de batalla **Darkspear Islands**, 15 vs 15. | Oficial | Blizzard (What's Next) |
| Reinos: un "mega-reino" por reglas (Normal, PvP, RP; Hardcore más adelante) por región. | Wiki (no verificado en Blizzard) | warcraft.wiki.gg |
| Honor con 14 rangos por temporada; sin PvP puntuado (citando la sesión de preguntas del 17/09). | Terceros (no verificado) | [wowclassicforever.info](https://wowclassicforever.info/pvp/), [lfcarry.com](https://lfcarry.com/guides/wow-forever-pvp) |
| Arenas, Mythic+ o afijos. | **Sin anuncio**. No se implementan. | Ningún artículo de Blizzard los menciona |

### Diferencias con retail, Classic y servidores privados

- **Retail (Midnight)**: expansiones con nivel creciente, Mythic+, PvP puntuado y API oficial
  completa. Forever no comparte esas temporadas ni (por ahora) la API.
- **Classic (Era/Anniversary)**: recrea el juego original; Forever lo **expande** con zonas,
  mazmorras, bandas, razas y combinaciones raza/clase nuevas, y cambia talentos y habilidades.
- **Servidores privados** (Turtle WoW, etc.): proyectos no oficiales con clientes 1.12 y logs con
  otro formato (sin `COMBAT_LOG_VERSION`); Forever es un producto oficial de Blizzard con cliente
  moderno (`COMBAT_LOG_VERSION 22`).

## 2. APIs oficiales

| Pregunta | Respuesta | Fuente |
|---|---|---|
| ¿Hay API oficial de Forever? | **No verificada.** Un hilo del foro de la API pregunta por ella sin respuesta de Blizzard; un usuario recuerda que Blizzard nunca ofreció API para beta/PTR. | [Foro API: When will we gain API access to Forever APIs?](https://us.forums.blizzard.com/en/blizzard/t/when-will-we-gain-api-access-to-forever-apis/59595) |
| ¿Sirven los endpoints de Classic? | Los namespaces conocidos de Classic son `*-classic1x-{región}` (Era) y `*-classic-{región}` (Progression); no hay namespace conocido para Forever. Un proyecto de terceros documenta que nada se sabe aún del namespace de Forever. | [npm @blizzard-api/classic-wow](https://www.npmjs.com/package/@blizzard-api/classic-wow), [cageymage/fuzion#101](https://github.com/cageymage/fuzion/issues/101) |
| Autenticación | OAuth 2.0 client credentials contra `oauth.battle.net` (host verificado en el portal de desarrolladores). | [Battle.net Developer Portal](https://community.developer.battle.net/documentation) |
| Rate limit | 36.000 solicitudes/hora por cliente según un hilo del foro (sin confirmar que sea personal de Blizzard). | [Foro: API Access - Clients - Rate Limits](https://us.forums.blizzard.com/en/blizzard/t/api-access-clients-rate-limits/5602) |

**Decisión**: el adaptador `BlizzardApiSource` existe (OAuth + cliente genérico) pero queda
**desactivado**; sólo se habilita configurando `BLIZZARD_FOREVER_NAMESPACE` cuando Blizzard publique
endpoints. No se inventan endpoints.

## 3. Combat logs

| Hecho | Fuente |
|---|---|
| Cabecera real de la beta de Forever: `COMBAT_LOG_VERSION,22,ADVANCED_LOG_ENABLED,1,BUILD_VERSION,1.60.1,PROJECT_ID,18`. | [Emyrk/chronicle#693](https://github.com/Emyrk/chronicle/issues/693) |
| Formato de línea `M/D/YYYY H:MM:SS.mmm[huso]␠␠EVENTO,...`; huso positivo sin signo. | [wowcoach.gg: line format](https://wowcoach.gg/docs/combat-log/line-format), [gotchas](https://wowcoach.gg/docs/combat-log/gotchas) |
| Parámetros base, prefijos, sufijos (`_DAMAGE`, `_HEAL`, `_ABSORBED`, …), eventos especiales y bloque avanzado. | [warcraft.wiki.gg: COMBAT_LOG_EVENT](https://warcraft.wiki.gg/wiki/COMBAT_LOG_EVENT) |
| `SWING_DAMAGE_LANDED` duplica `SWING_DAMAGE`; `SPELL_ABSORBED` tiene dos variantes; overkill `-1` = sin overkill. | wowcoach.gg (gotchas, damage-and-healing) |
| Rango del log limitado a 50 yardas en mundo abierto (no en mazmorras/bandas). | warcraft.wiki.gg (hotfixes de Classic 2019/2020) |
| En Forever el cliente ignora el pedido de log unos segundos al entrar a una mazmorra. | [forever-logs-companion](https://github.com/FangYuanWoW/forever-logs-companion) |

**No verificado para Forever**: la posición del `specID` en `COMBATANT_INFO`, los `difficultyID`
de cada banda y los IDs de instancia/encuentro. Por eso el parser acepta el `specID` sólo si
coincide con un ID conocido, guarda la dificultad tal cual la escribe el cliente y el admin puede
asociar IDs a instancias (auditado).

## 4. Plataformas de logs de terceros

| Plataforma | Estado | Fuente |
|---|---|---|
| Warcraft Logs | No se encontró soporte para Forever. Su API v2 es GraphQL con OAuth y cuota por puntos; el cliente público sólo ve reportes públicos. | [Warcraft Logs API docs](https://www.warcraftlogs.com/api/docs), [archon.gg API doc](https://www.archon.gg/wow/articles/help/api-documentation) |
| Forever Logs (foreverlogs.gg) | Sitio comunitario de logs de Forever con "Developer API" enlazada; no se pudo leer su documentación ni términos. Un tercero menciona que requiere clave del dueño. | [foreverlogs.gg](https://foreverlogs.gg/), [alsh0083/wowforever-helper#172](https://github.com/alsh0083/wowforever-helper/issues/172) |

**Decisión**: adaptador `ForeverLogsSource` desactivado hasta contar con documentación y
autorización. No se hace scraping.

## 5. Addons

- Jugadores reportan que Forever restringe la API de addons (combat log sin filtrar, valores de
  vida protegidos), afectando medidores de daño. Fuente: [foro EU](https://eu.forums.blizzard.com/en/wow/t/please-reconsider-the-addon-api-restrictions-in-forever/633555) (sin respuesta oficial visible).
- Los addons sí pueden activar el log a archivo (`/combatlog`); ejemplo: Forever Logs Companion.

**Decisión**: el adaptador de exportación por addon queda **planificado**; el camino soportado es el
archivo de combat log.

## 6. Privacidad

Hay debate en la comunidad sobre la publicación de logs ([foro US](https://us.forums.blizzard.com/en/wow/t/blizzard-should-seriously-consider-blocking-the-ability-to-upload-public-combat-logsparses-in-wow-forever/2348152)).
Medidas implementadas: reportes **privados** (no entran en rankings ni listados), **ocultar
personajes** a pedido (auditado), sin datos personales más allá de lo que trae el log, y el
nombre de archivo original se sanea.

## 7. Estado de cada integración

| Fuente | Estado en la plataforma |
|---|---|
| Combat log (archivo) | **Activa** — importador propio, v22 verificado |
| Aportes de usuarios | **Activa** — moderada por admin y auditada |
| API de Blizzard | **No disponible** — sin namespace verificado |
| Forever Logs | **Desactivada** — sin documentación ni autorización |
| Exportación por addon | **Planificada** — API de addons de Forever sin verificar |
