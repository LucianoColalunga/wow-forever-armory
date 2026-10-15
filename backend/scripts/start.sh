#!/bin/sh
# Arranque de la API (Docker Compose, Render u otro host de contenedores).
#  1. migraciones y catálogo
#  2. primer admin si están ADMIN_BOOTSTRAP_EMAIL / ADMIN_BOOTSTRAP_PASSWORD (no pisa uno existente)
#  3. datos DEMO en segundo plano si SEED_DEMO=true (no duplica si ya existen)
#  4. servidor en $PORT (8000 por defecto)
set -e

alembic upgrade head
python -m app.cli sync-catalog

if [ -n "$ADMIN_BOOTSTRAP_EMAIL" ] && [ -n "$ADMIN_BOOTSTRAP_PASSWORD" ]; then
    python -m app.cli create-admin --from-env || echo "No se pudo crear el admin inicial (revisá la contraseña)."
fi

if [ "$SEED_DEMO" = "true" ]; then
    python -m app.cli seed-demo --weeks "${SEED_DEMO_WEEKS:-4}" &
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
