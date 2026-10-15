# Despliegue

## Opción recomendada: un servidor con Docker Compose y HTTPS

1. Servidor Linux con Docker (2 vCPU / 4 GB alcanzan para empezar).
2. Clonar el repositorio y crear `.env` desde `.env.example` con:
   - `APP_ENV=production`, `COOKIE_SECURE=true`
   - `POSTGRES_PASSWORD` fuerte (y el mismo valor dentro de `DATABASE_URL` si se usa fuera de Compose)
   - `TRUSTED_PROXIES` con la red de Docker (`172.16.0.0/12`) y la IP del proxy HTTPS
3. Exponer **sólo la web** detrás de un proxy con HTTPS (por ejemplo Caddy). En `docker-compose.yml`
   conviene quitar la publicación de los puertos de `db` y `api` en producción: la web habla con la
   API por la red interna.

Ejemplo de Caddyfile:

```
armory.ejemplo.com {
    encode zstd gzip
    reverse_proxy 127.0.0.1:3000
}
```

4. Levantar y crear el admin:

```bash
docker compose up --build -d
```

```bash
docker compose exec api python -m app.cli create-admin --email tu-email@ejemplo.com --name "Tu nombre"
```

5. Programar backups (ver OPERATIONS.md).

## Opción gestionada

- **Base**: PostgreSQL gestionado con la extensión `pg_trgm` habilitada (Neon, Supabase, RDS…).
- **API + worker**: dos servicios desde `backend/Dockerfile` (Render, Fly.io, Railway…). Comandos:
  `alembic upgrade head && python -m app.cli sync-catalog && uvicorn app.main:app --host 0.0.0.0 --port 8000`
  para la API y `python -m app.worker` para el worker, con un **volumen persistente** en
  `STORAGE_DIR` compartido o, si la plataforma no lo permite, un único servicio con
  `INLINE_WORKER=true`.
- **Web**: `frontend/Dockerfile` con `API_INTERNAL_URL` apuntando a la API.

### Sobre Vercel

La web puede desplegarse en Vercel para navegación, pero las funciones serverless de Vercel limitan
el cuerpo de la solicitud (4,5 MB) y la importación pasa por el proxy `/api`. Para importar logs
reales (decenas o cientos de MB) desplegá la web como contenedor o usá la API directamente con una
API key (`curl … /api/v1/reports/import`).

## Checklist antes de publicar

- [ ] `.env` de producción sin valores de ejemplo.
- [ ] HTTPS y `COOKIE_SECURE=true`.
- [ ] Puertos de `db` y `api` no expuestos a Internet.
- [ ] Admin creado y la variable `ADMIN_BOOTSTRAP_PASSWORD` vacía.
- [ ] Backups programados y una restauración probada.
- [ ] `GET /api/health/ready` en 200 y worker con latido.
- [ ] Datos demo sólo si se quieren mostrar (siempre quedan marcados como DEMO).
