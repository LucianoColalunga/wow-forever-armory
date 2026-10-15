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
- **API + worker**: dos servicios desde `backend/Dockerfile` (Render, Fly.io, Railway…). La imagen
  arranca con `scripts/start.sh` (migraciones, catálogo y servidor en `$PORT`) y el worker con
  `python -m app.worker`, con un **volumen persistente** en
  `STORAGE_DIR` compartido o, si la plataforma no lo permite, un único servicio con
  `INLINE_WORKER=true`.
- **Web**: `frontend/Dockerfile` con `API_INTERNAL_URL` apuntando a la API.

## Despliegue gratis: Vercel + Neon + Render

Todo con planes gratuitos (relevado en octubre de 2026). Es ideal para mostrar el proyecto con los
datos DEMO; para uso real intenso conviene un servidor pago chico.

| Parte | Servicio gratis | Límites a tener en cuenta |
|---|---|---|
| Web (Next.js) | Vercel Hobby | Cada pedido a una función admite como máximo **4,5 MB** de cuerpo y 300 s. |
| Base de datos | Neon Free | 0,5 GB por proyecto y 100 CU-hora/mes; se suspende tras 5 min sin actividad. Soporta `pg_trgm`. |
| API + procesamiento | Render Free (`render.yaml`) | Se duerme tras 15 min sin visitas (tarda ~1 min en despertar), 750 h/mes, 512 MB de RAM, **sin worker aparte ni disco persistente**. |

Consecuencias del plan gratis:
- El procesamiento corre dentro de la API (`INLINE_WORKER=true`); se despierta al importar y sondea
  la base cada 15 minutos para que Neon pueda dormir.
- Los archivos de log originales viven en el disco efímero de Render: los datos procesados quedan en
  Neon, pero tras un reinicio no se puede **reprocesar** un reporte viejo.
- Logs de más de 4,5 MB no pasan por la web en Vercel: subilos directo a la API de Render con una
  API key (ver más abajo).
- No configures "pingers" para mantener despierta la API: Neon gastaría su cuota mensual de cómputo.

### Pasos

1. **Neon** (neon.com, se puede entrar con GitHub): crear un proyecto en la región
   *AWS US East (N. Virginia)* y copiar la cadena de conexión **directa** (sin `-pooler`).
2. **Render** (render.com, entrar con GitHub): *New → Blueprint*, elegir este repositorio. Render lee
   `render.yaml` y pide:
   - `DATABASE_URL`: la cadena de Neon (se acepta tal cual, con `postgresql://`).
   - `ADMIN_BOOTSTRAP_EMAIL`: el email del primer admin.
   - `ADMIN_BOOTSTRAP_PASSWORD` y `PROXY_SHARED_SECRET` se generan solos. La contraseña del admin se
     ve en Render → servicio → *Environment*; usala para el primer ingreso.
   Al arrancar, `scripts/start.sh` aplica migraciones, sincroniza el catálogo, crea el admin y carga
   los datos DEMO. Verificá `https://<servicio>.onrender.com/api/health/ready`.
3. **Vercel**: importar el repositorio con **Root Directory = `frontend`** (Framework: Next.js) y
   definir las variables:
   - `API_INTERNAL_URL` = `https://<servicio>.onrender.com`
   - `PROXY_SHARED_SECRET` = el mismo valor que generó Render (Render → servicio → Environment).
4. Opcional: dominio propio. En Vercel → Settings → Domains agregá `tudominio` y `www.tudominio`;
   en el registrador (por ejemplo NIC Argentina → Delegar) cargá `ns1.vercel-dns.com` y
   `ns2.vercel-dns.com`. Cuando el dominio responda, definí `CANONICAL_HOST` = `tudominio` (sin
   `https://`) en las variables de Vercel y volvé a desplegar: `www` y la dirección `*.vercel.app`
   redirigen al dominio principal.

Importar un log grande directo a la API (sin el límite de Vercel), con una API key creada desde la
web:

```bash
curl -H "Authorization: Bearer wfa_TU_API_KEY" -F "file=@WoWCombatLog.txt" https://<servicio>.onrender.com/api/v1/reports/import
```

## Checklist antes de publicar

- [ ] `.env` de producción sin valores de ejemplo.
- [ ] HTTPS y `COOKIE_SECURE=true`.
- [ ] Puertos de `db` y `api` no expuestos a Internet.
- [ ] Admin creado y la variable `ADMIN_BOOTSTRAP_PASSWORD` vacía.
- [ ] Backups programados y una restauración probada.
- [ ] `GET /api/health/ready` en 200 y worker con latido.
- [ ] Datos demo sólo si se quieren mostrar (siempre quedan marcados como DEMO).
