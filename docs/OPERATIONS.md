# Operación

## Health checks

| Endpoint | Uso |
|---|---|
| `GET /api/health/live` | Liveness: el proceso responde. |
| `GET /api/health/ready` | Readiness: base de datos y almacenamiento escribible (503 si fallan); informa el último latido del worker y los trabajos en cola. |

En Docker Compose la API tiene `healthcheck` sobre `/api/health/ready`; el worker y la web esperan
a que esté sana.

## Logs

JSON por línea en stdout (`docker compose logs -f api worker`), con `request_id`, ruta, estado y
duración. Los secretos se redactan automáticamente. Cada respuesta lleva `X-Request-ID`.

## Tareas frecuentes

```bash
docker compose exec api python -m app.cli create-admin --email admin@ejemplo.com --name "Admin"
```

```bash
docker compose exec api python -m app.cli process-pending
```

```bash
docker compose exec api python -m app.cli reprocess-all --dataset real
```

```bash
docker compose exec api python -m app.cli rebuild-rankings --dataset real
```

```bash
docker compose exec api python -m app.cli seed-demo --force
```

```bash
docker compose exec api python -m app.cli reset-demo
```

Escalar workers (la cola soporta varios en paralelo):

```bash
docker compose up -d --scale worker=3
```

## Backups

Hay dos cosas que respaldar: **la base** y **el volumen de logs** (`storage`), porque los combates
se pueden reconstruir desde los archivos originales.

Base (formato custom, comprimido):

```bash
docker compose exec -T db pg_dump -U wfa -d wfa -Fc > backups/wfa-$(date +%F).dump
```

Logs originales:

```bash
docker run --rm -v wfa_storage:/data -v "$PWD/backups":/backup alpine tar czf /backup/storage-$(date +%F).tgz -C /data .
```

Recomendado: diario, con retención de 7 diarios y 4 semanales, copiado fuera del servidor.
Probá la restauración periódicamente en un entorno aparte.

## Restauración

1. Detené la API y el worker: `docker compose stop api worker`.
2. Base:

```bash
docker compose exec -T db pg_restore -U wfa -d wfa --clean --if-exists < backups/wfa-AAAA-MM-DD.dump
```

3. Logs:

```bash
docker run --rm -v wfa_storage:/data -v "$PWD/backups":/backup alpine sh -c "rm -rf /data/* && tar xzf /backup/storage-AAAA-MM-DD.tgz -C /data"
```

4. `docker compose start api worker` y verificá `GET /api/health/ready`.
5. Si sólo se recuperaron los archivos de log (sin base), reimportarlos reconstruye todo; si la
   base es de otra versión del parser, `reprocess-all` la actualiza.

## Migraciones

Se aplican solas al iniciar la API (`alembic upgrade head`). Para revisar o revertir:

```bash
docker compose exec api alembic current
```

```bash
docker compose exec api alembic downgrade -1
```

## Mantenimiento de datos

- Trabajos fallidos: panel admin → Trabajos → Reintentar (auditado).
- Outliers y exclusiones: panel admin → Revisión.
- Privacidad: panel admin → Personajes → Ocultar; Reportes → Hacer privado / Eliminar.
