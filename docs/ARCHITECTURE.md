# Arquitectura

## Visión general

```
 Navegador ──► Next.js (web, :3000) ──/api/* proxy──► FastAPI (api, :8000) ──► PostgreSQL
                  │  Server Components                   │  rutas /api/v1          ▲
                  └──── fetch interno (API_INTERNAL_URL)─┘                         │
                                                          worker (python -m app.worker)
                                                          └── cola import_jobs (SKIP LOCKED)
                                                          └── almacenamiento de logs (volumen)
```

**Monolito modular**: un backend Python con módulos bien separados y una web Next.js. Dos procesos
del mismo código backend: la API y el worker de importación.

## Decisiones y justificación

| Decisión | Motivo |
|---|---|
| **FastAPI + SQLAlchemy 2 + Alembic** | Tipado, OpenAPI automático, migraciones versionadas. |
| **PostgreSQL** como única dependencia de infraestructura | Window functions (`percent_rank`, `percentile_cont`) para rankings, `pg_trgm` para búsqueda difusa, `JSONB` para series y metadatos, `SKIP LOCKED` para la cola. |
| **Cola en PostgreSQL** en lugar de Redis/Celery | Un servicio menos. `SELECT … FOR UPDATE SKIP LOCKED` permite varios workers sin duplicar trabajo; reintentos con backoff exponencial y recuperación de locks vencidos. Redis sólo aportaría si el volumen lo justifica. |
| **Rate limiting en memoria** | Simple y sin dependencias; por proceso (documentado). La interfaz permite cambiar el backend por Redis sin tocar las rutas. |
| **Caché de rankings en tabla** (`ranking_entries`) + caché de respuestas por versión | Actualización **incremental**: al procesar o corregir un reporte sólo se reconstruyen sus filas; cada cambio sube `ranking_versions.version` del dataset y eso invalida las respuestas cacheadas. |
| **Parser puro y versionado** | No toca la base: se testea con logs y valores esperados escritos a mano. `PARSER_VERSION` queda en cada reporte y combate; reprocesar reconstruye todo desde el archivo guardado. |
| **Archivos guardados por SHA-256** | Deduplicación exacta y trazabilidad: reporte → archivo → líneas del combate. Nunca se usa el nombre del usuario como ruta. |
| **Proxy `/api/*` en Next.js** | Mismo origen para cookies `HttpOnly` + `SameSite` y CSRF sin CORS; la URL de la API se lee en tiempo de ejecución. |
| **Datasets `real` y `demo`** | Los fixtures sintéticos viven en otro conjunto (columna `dataset` en todas las tablas de datos); un archivo con `BUILD_VERSION …-DEMO` siempre se clasifica como demo. |

## Módulos del backend (`backend/app`)

| Módulo | Responsabilidad |
|---|---|
| `parser/` | Tokenizador (timestamps, comillas, listas anidadas), dialectos (`COMBAT_LOG_VERSION`/`PROJECT_ID`), segmentación (encuentros, mazmorras, campos de batalla), métricas, inferencia de clase/spec. |
| `importer/` | Validación de archivos (tamaño, firmas binarias, UTF-8, zip), almacenamiento, alta del reporte, procesamiento y deduplicación. |
| `worker/` | Cola de trabajos, reintentos, latido del worker. |
| `rankings/` | `cache.py` (filas rankeables y versión) y `methods.py` (métodos A/B/C en SQL). |
| `sources/` | Adaptadores de fuentes intercambiables con su estado verificado. |
| `catalog/` | Instancias de Forever con estado de verificación y fuente. |
| `services/` | Auditoría, sincronización de catálogo/fases y serializadores compartidos. |
| `api/` | Rutas públicas (`v1/*`), autenticación, admin y health. |
| `demo/` | Constructor de líneas de log y generador determinista de datos DEMO. |
| `cli.py` | Operación: admin, catálogo, demo, reprocesar, reconstruir rankings, exportar OpenAPI. |

## Flujo de importación

1. `POST /api/v1/reports/import`: autenticación (sesión o API key), rate limit y límite de
   `Content-Length`.
2. Copia en streaming con corte por tamaño → validación (firmas, zip, UTF-8, primera línea) →
   SHA-256. Si el archivo ya existe se devuelve el reporte existente (no se reprocesa).
3. Se crea `reports` + `import_jobs` (estado `queued`) y se responde `202`.
4. El worker toma el trabajo, parsea el archivo, guarda combates, participantes, avisos y filas de
   ranking en una transacción, detecta duplicados entre reportes y outliers, y sube la versión.
5. Ante un error: reintento con backoff; al agotar intentos el trabajo queda `dead` y el reporte
   `failed` con el detalle.

## Modelo de datos (resumen)

`users`, `sessions`, `api_keys`, `audit_log` · `instances`, `encounters`, `seasons` ·
`guilds`, `characters` · `source_files`, `reports`, `import_jobs`, `report_issues`,
`worker_heartbeats` · `fights`, `fight_participants`, `ranking_entries`, `ranking_versions` ·
`submissions`. Índices principales: partición de rankings
(`dataset, kind, encounter, dificultad, tamaño`), cubeta clase/spec, tiempo, `fight_key` y GIN
trigram sobre nombres.

## Frontend (`frontend/src`)

- `app/`: páginas (App Router). Server Components consultan la API; las vistas interactivas
  (tablas ordenables/filtrables, gráficos Recharts, filtros en la URL, admin, importador) son
  Client Components.
- `components/`: UI propia (tabla accesible, gráficos con vista de tabla, estados vacío/error/carga/
  desactualizado, banners de demo).
- `lib/`: cliente de API (servidor y navegador con CSRF), formatos es-AR, clases y opciones.
- `middleware.ts`: redirige a `/login` las rutas con sesión requerida (la autorización real la hace la API).

## Estructura del repositorio

```
wow-forever-armory/
├── backend/
│   ├── app/            (api, parser, importer, worker, rankings, sources, catalog, services, demo)
│   ├── alembic/        (migraciones)
│   ├── scripts/        (servidor para e2e)
│   ├── tests/          (unit, integration, fixtures/logs con resultados esperados)
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── src/            (app, components, lib)
│   ├── e2e/            (Playwright)
│   ├── Dockerfile
│   └── package.json
├── docs/               (investigación, arquitectura, metodología, seguridad, operación, deploy, openapi.json)
├── .github/workflows/ci.yml
├── docker-compose.yml
└── .env.example
```
