# WoW Forever Armory & Competitive Analytics

Plataforma web de estadísticas competitivas para **World of Warcraft: Forever**: rankings PvE y PvP,
perfiles de personajes y hermandades, historial de combates, comparador y un importador de
combat logs con parser propio.

> Proyecto independiente de la comunidad, **no afiliado ni avalado por Blizzard Entertainment**.
> World of Warcraft y Warcraft son marcas de Blizzard Entertainment, Inc. Ningún número de este
> sitio es un rating oficial.

Autor: **Luciano Colalunga**.

## Por qué funciona sin API oficial

Al 14/10/2026 Blizzard no publicó ninguna API para Forever (ver [docs/RESEARCH.md](docs/RESEARCH.md)).
La fuente principal es el archivo `WoWCombatLog*.txt` que escribe el propio cliente con `/combatlog`:
el formato v22 se verificó con una cabecera real de la beta de Forever (`PROJECT_ID 18`,
`BUILD_VERSION 1.60.1`). Las demás fuentes (API de Blizzard, sitios de terceros, addons) están
implementadas como adaptadores desactivados con su motivo documentado.

## Funcionalidades

| Área | Qué incluye |
|---|---|
| Dashboard | Totales, últimos kills, destacados de la semana, actividad diaria, estado de las fuentes |
| Rankings PvE | General (varios jefes, normalizado) y por jefe; métodos **A · Pico**, **B · Consistencia** y **C · Percentil** por clase/spec con muestra mínima; DPS, daño total, HPS efectivo, curación efectiva, absorciones/s y totales, daño recibido, muertes, supervivencia, interrupciones y dispels |
| Rankings PvP | Sólo modalidades confirmadas (campo de batalla Darkspear Islands); sin ratings inventados |
| Contenido | Bandas, mazmorras y campos de batalla con estado de verificación y fuente |
| Perfiles | Personaje (mejores marcas, percentiles, evolución, historial) y hermandad (progreso, miembros, actividad) |
| Buscador | Global, tolerante a errores de tipeo (PostgreSQL `pg_trgm`) |
| Comparador | 2 a 4 personajes, sólo dentro del mismo jefe, dificultad y tamaño |
| Historial | Kills, wipes (con % de vida del jefe), recorridos de mazmorra y partidas PvP |
| Importador | Validación segura, deduplicación, cola con reintentos, parser versionado y reprocesable, trazabilidad hasta la línea del archivo |
| Admin | Correcciones auditadas (clase/spec, hermandad, privacidad, exclusiones, outliers, verificación de instancias), usuarios, trabajos, aportes de usuarios |
| API REST | `/api/v1/...` con OpenAPI en `/api/docs` (también [docs/openapi.json](docs/openapi.json)) |

Los datos de **demostración** son sintéticos, viven en un conjunto separado (`dataset=demo`) y la
interfaz los marca en todas las páginas: nunca se mezclan con datos reales.

## Inicio rápido (Docker)

Requisitos: Docker con Compose v2.

```bash
cp .env.example .env
```

```bash
docker compose up --build -d
```

Esto levanta PostgreSQL, la API (aplica migraciones y sincroniza el catálogo al arrancar), el worker
de importación y la web. Abrí <http://localhost:3000> (API en <http://localhost:8000/api/docs>).

Crear el primer administrador (pide la contraseña por consola, no queda en ningún archivo):

```bash
docker compose exec api python -m app.cli create-admin --email tu-email@ejemplo.com --name "Tu nombre"
```

Cargar datos de demostración (opcional, marcados como DEMO):

```bash
docker compose exec api python -m app.cli seed-demo
```

En la web, el selector **Datos reales / Demo** (arriba a la derecha) cambia de conjunto.

## Desarrollo local sin Docker para la app

Sólo PostgreSQL en Docker; API, worker y web corren localmente.

```bash
docker compose up -d db
```

Backend (Python 3.12+):

```bash
cd backend && python -m venv .venv && .venv/bin/pip install -e ".[dev]"
```

```bash
cd backend && .venv/bin/alembic upgrade head && .venv/bin/python -m app.cli sync-catalog
```

```bash
cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000
```

```bash
cd backend && .venv/bin/python -m app.worker
```

En Windows usá `.venv\Scripts\` en lugar de `.venv/bin/`. Frontend (Node 22):

```bash
cd frontend && npm install && npm run dev
```

## Tests y calidad

| Comando (desde la carpeta indicada) | Qué verifica |
|---|---|
| `backend`: `pytest` | Parser contra resultados escritos a mano, importación de punta a punta, duplicados, archivos inválidos, seguridad, rankings, admin auditado (requiere PostgreSQL; base `wfa_test`) |
| `backend`: `ruff check app tests scripts` y `mypy app` | Lint y tipos |
| `backend`: `alembic upgrade head` / `alembic downgrade base` | Migraciones ida y vuelta |
| `frontend`: `npm run lint`, `npm run typecheck`, `npm test` | ESLint, TypeScript y tests de componentes |
| `frontend`: `npm run build` | Build de producción |
| `frontend`: `npx playwright test` | E2E con API real y base aislada `wfa_e2e` |

Para los tests de integración creá la base una vez:

```bash
docker compose exec db psql -U wfa -c "CREATE DATABASE wfa_test;"
```

Para los e2e (además de `npx playwright install chromium`):

```bash
docker compose exec db psql -U wfa -c "CREATE DATABASE wfa_e2e;"
```

El pipeline de CI (`.github/workflows/ci.yml`) corre todo lo anterior más el build de las imágenes.

## Importar logs

1. En el juego: *Opciones → Red → Advanced Combat Logging*.
2. `/combatlog` antes del primer pull.
3. Subí `Logs/WoWCombatLog-*.txt` (o un `.zip` con ese único archivo) desde **Importar** con una
   cuenta `uploader` o `admin`, o por API con una API key:

```bash
curl -H "Authorization: Bearer wfa_TU_API_KEY" -F "file=@WoWCombatLog.txt" -F "guild_name=Mi Hermandad" http://localhost:8000/api/v1/reports/import
```

## Documentación

- [docs/RESEARCH.md](docs/RESEARCH.md) — qué es Forever, fuentes verificadas y estado de cada integración.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — arquitectura, decisiones y estructura del proyecto.
- [docs/METHODOLOGY.md](docs/METHODOLOGY.md) — métricas, métodos de ranking, deduplicación y parser.
- [docs/SECURITY.md](docs/SECURITY.md) — autenticación, autorización, validación de archivos y privacidad.
- [docs/OPERATIONS.md](docs/OPERATIONS.md) — health checks, logs, backups, restauración y mantenimiento.
- [docs/DEPLOY.md](docs/DEPLOY.md) — despliegue a producción.
- [backend/tests/fixtures/logs/README.md](backend/tests/fixtures/logs/README.md) — logs de prueba y resultados esperados.

## Variables de entorno

Todas están en [.env.example](.env.example) con valores seguros para desarrollo. En producción:
`APP_ENV=production`, `COOKIE_SECURE=true`, una contraseña fuerte en `POSTGRES_PASSWORD` y
`TRUSTED_PROXIES` con la IP/rango del proxy que termina HTTPS.
