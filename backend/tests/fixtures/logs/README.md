# Logs de prueba con resultados esperados

Generados con `python -m tests.fixtures.build_fixtures` (desde `backend/`) usando
`app/demo/logbuilder.py`. Formato v22 con Advanced Combat Logging (cabecera de Forever:
`PROJECT_ID 18`, `BUILD_VERSION 1.60.1`), salvo `legacy_no_year.txt`.

Los valores esperados están en [expected.json](expected.json) y se calcularon **a mano** a partir de
los eventos; `tests/unit/test_parser_fixtures.py` compara la salida del parser contra ese archivo.

## basic_kill.txt — un kill de 60 s con 4 jugadores

| Jugador | Eventos relevantes | Esperado |
|---|---|---|
| Brakka (guerrero, `specID 71`) | Mortal Strike 1000, golpe 500 (+ `SWING_DAMAGE_LANDED` duplicado que **no** cuenta), Execute 4000 con overkill 1500, daño propio 100, interrupción | daño 5500, efectivo 4000, overkill 1500, DPS 91,67, recibido 3900 (+1700 absorbido), 1 interrupción |
| Lumen (sacerdote) | Flash Heal 2500 (500 overheal), Renew 1000 (1000 overheal), Flash Heal 1500 (200 absorbido por debuff), Power Word: Shield absorbe 1000 + 200 + 500, 1 dispel | curación bruta 5000, efectiva 3500, overheal 1500, absorciones 1700 (**no** sumadas a la curación), HPS 58,33, APS 28,33 |
| Ignis (mago) | Frostbolt 2000 (+300 absorbido por el escudo del jefe), Fire Blast totalmente absorbido (400), elemental de agua (`SPELL_SUMMON`) 600, muere a los 35,1 s | daño 3300, efectivo 2600, absorbido por el objetivo 700, supervivencia 58,5 % |
| Arrowyn (cazador) | Aimed Shot 1500, Auto Shot 400, mascota 300 (dueño por `ownerGUID`), Fingir Muerte + `UNIT_DIED` | daño 2200, **0 muertes** |

Además: el golpe posterior a `ENCOUNTER_END` no cuenta; total del grupo 11000; absorciones de
golpes = `SPELL_ABSORBED` (sin aviso de inconsistencia).

## Otros

| Archivo | Qué prueba | Esperado |
|---|---|---|
| `wipe_then_kill.txt` | Wipe y kill del mismo jefe | wipe de 30 s con el jefe al 40 %; kill de 40 s |
| `truncated.txt` | `ENCOUNTER_START` sin fin | combate incompleto, no rankeable, aviso `incomplete_fight` |
| `legacy_no_year.txt` | Formato viejo: sin año, sin huso, sin log avanzado, cruce de año | 31/12 23:59:50 → 1/1 00:00:10 UTC; avisos `year_inferred`, `timezone_assumed`, `advanced_logging_off` |
| `battleground.txt` | Darkspear Islands | daño a jugadores 2700 y 1 golpe de gracia para Aldren; 64,1 s |
| `quoted_names.txt` | Nombres con comas entre comillas | jugador `Ca,ma`, encuentro `Training, the Dummy` |
