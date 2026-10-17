# Metodología

Todo lo que se publica se calcula a partir de combat logs. **Ningún valor es un rating oficial.**
Esta página también se expone en la API (`GET /api/v1/meta/methodology`) y en la web (`/methodology`).

## Métricas por jugador y combate

| Métrica | Definición |
|---|---|
| Daño realizado (`damage_done`) | Vida quitada + overkill + daño que frenaron escudos del objetivo (campo `absorbed` del golpe y `*_MISSED` de tipo `ABSORB`). Sólo contra unidades enemigas; el fuego amigo y el daño propio no cuentan. |
| Daño efectivo (`effective_damage`) | Vida realmente quitada: `amount − overkill`. |
| Overkill | Daño sobrante del golpe mortal (`-1` en el log = 0). |
| DPS | `damage_done / duración del encuentro`. |
| Curación efectiva (`healing_effective`) | `amount − overhealing`. HPS = curación efectiva / duración. |
| Overhealing | Curación desperdiciada (se informa aparte y como %). |
| Curación absorbida (`heal_absorbed`) | Curación consumida por efectos que absorben sanación; ya está dentro de `amount` y se muestra aparte. |
| Absorciones (`absorbs_provided`) | Daño evitado por escudos del jugador, atribuido al lanzador del escudo (`SPELL_ABSORBED`). **Nunca se suma a la curación.** Por segundo (`aps`) y total. |
| Daño recibido (`damage_taken`) | Vida perdida. Lo absorbido por escudos se informa en `damage_taken_absorbed`. |
| Muertes | `UNIT_DIED` de jugadores, excepto Fingir Muerte (lanzado ≤2,5 s antes) o `unconsciousOnDeath`. |
| Supervivencia | % del combate con vida hasta la primera muerte. |
| Interrupciones / Dispels | `SPELL_INTERRUPT` contra enemigos; `SPELL_DISPEL` y `SPELL_STOLEN`. |
| Golpes de gracia (PvP) | Muerte de un jugador cuyo último golpe (≤3 s) vino del jugador o su mascota. |

**Anti doble conteo**: se ignoran `SWING_DAMAGE_LANDED` (repite `SWING_DAMAGE`), `DAMAGE_SPLIT` y
`*_SUPPORT`. El campo `absorbed` de un golpe sólo suma al daño del atacante; `SPELL_ABSORBED` sólo
suma al lanzador del escudo. Se verifica la consistencia entre ambos (aviso `absorb_mismatch`).
Los eventos posteriores a `ENCOUNTER_END` se descartan. Mascotas y guardianes se atribuyen al dueño
(`SPELL_SUMMON` u `ownerGUID` del bloque avanzado).

## Particiones

Un ranking **nunca** mezcla encuentros distintos, ni dificultades (`difficultyID` del log), ni
tamaños de grupo. Partición = (jefe, dificultad, tamaño). Sólo cuentan kills rankeables: completos,
de al menos 15 s, no duplicados, no excluidos por un admin, de reportes públicos.

## Métodos de ranking

### Por jefe (una partición)

- **A · Pico**: mejor valor de cada personaje en el período.
- **B · Consistencia**: mediana de sus últimos N kills (por defecto 10), con un mínimo de kills
  (por defecto 3). Se muestra el desvío estándar.
- **C · Percentil**: `percent_rank()` × 100 dentro de la cubeta (jefe, dificultad, tamaño, clase,
  spec), sólo en cubetas con al menos `MIN_BUCKET_SIZE` registros (por defecto 10). Se toma el mejor
  percentil del personaje. Registros en cubetas chicas se excluyen y se cuentan.

### General (varios jefes)

Nunca compara DPS bruto entre encuentros. Índice normalizado de cada registro:
`100 × valor / mediana(valores de la partición)` (100 = rendimiento mediano del encuentro). Las
particiones con menos de 3 registros no se normalizan.

- **A · Pico normalizado**: promedio, sobre los encuentros jugados, del mejor índice.
- **B · Consistencia normalizada**: mediana del índice sobre todos sus kills (mínimo de kills).
- **C · Percentil normalizado**: promedio, sobre los encuentros, del mejor percentil por clase/spec.

Cada respuesta informa: registros usados, excluidos, personajes, período (desde/hasta), método y
umbrales.

## PvP

**Rendimiento por especialización** (página PvP): por cada personaje se toma su mejor valor en el
campo de batalla y período elegidos; por clase y spec se informa la **mediana** de esos mejores
valores y el máximo. Cada jugador cuenta una vez, así un jugador con muchas partidas no inclina el
resultado. Specs con menos de 3 jugadores se marcan como «muestra chica».

**Puesto** (perfil): posición en el ranking de pico de la partición = 1 + cantidad de personajes con
un mejor valor estrictamente superior (los empates comparten puesto).

Sólo modalidades confirmadas (Darkspear Islands). Métricas: daño a jugadores, DPS, HPS, golpes de
gracia y muertes, con métodos A y B. Los logs en campos de batalla son **parciales** (el cliente
registra eventos cercanos a quien graba) y se aclara en la interfaz. No hay rating ni puntuación
propia.

## Clase y spec

1. `COMBATANT_INFO` con un `specID` conocido (confianza alta).
2. Hechizos característicos lanzados por el propio jugador (confianza media).
3. Rol observado para elegir la spec por defecto (confianza baja).

El origen y la confianza se muestran en el perfil; un admin puede corregir (queda fijo y auditado).
Forever cambia talentos y habilidades, por lo que la heurística es revisable.

## Deduplicación

- **Archivo**: SHA-256 del contenido normalizado (un `.zip` y su `.txt` dan el mismo hash).
- **Combate**: mismo jefe, dificultad, tamaño y resultado, inicio dentro de ±120 s y ≥60 % de
  jugadores en común (coeficiente de solapamiento). El duplicado se guarda (trazabilidad) pero no
  suma a rankings, historial ni estadísticas. Si el original se reprocesa o borra, los duplicados
  se liberan y se recalculan.

## Inconsistencias detectadas

Combate sin cierre (`incomplete_fight`), duración informada vs medida, timestamps que retroceden,
porcentaje de líneas ilegibles, log sin huso horario o sin año (se infiere con cruce de año), log
sin Advanced Combat Logging, overhealing mayor que la curación, absorciones inconsistentes y
**outliers** (DPS > 3× el máximo histórico del jefe con ≥10 registros → queda en revisión admin).

## Equipo y línea de tiempo

- **Equipo**: se toma del `COMBATANT_INFO` que el cliente escribe al empezar cada jefe con Advanced
  Combat Logging. Se guarda por ranura el ID de objeto, el nivel de objeto, encantamientos, bonus y
  gemas. El nivel promedio excluye camisa y tabardo. El log no trae nombres ni apariencia: la
  interfaz muestra una silueta propia y enlaza cada objeto a Wowhead (en datos reales).
- **Línea de tiempo**: cada `SPELL_CAST_SUCCESS` del jugador dentro del combate, con el momento
  relativo al inicio (máximo 1500 por jugador y pelea). Los hechizos que se lanzan sin
  `SPELL_CAST_SUCCESS` (por ejemplo, ataques automáticos) no aparecen.

## Parser versionado

`PARSER_VERSION` (hoy `1.1.0`) se guarda en cada reporte y combate. Cambiar reglas implica subir la
versión y reprocesar (`python -m app.cli reprocess-all`). El tamaño del bloque avanzado se calibra
por archivo con `SPELL_CAST_SUCCESS`, así el parser tolera cambios de formato entre clientes.
