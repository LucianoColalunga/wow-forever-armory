FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --system wfa && useradd --system --gid wfa --home /app wfa

COPY pyproject.toml ./
RUN pip install --upgrade pip && python - <<'EOF' > /tmp/req.txt
import tomllib
print("\n".join(tomllib.load(open("pyproject.toml", "rb"))["project"]["dependencies"]))
EOF
RUN pip install -r /tmp/req.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY scripts/start.sh ./scripts/start.sh

RUN mkdir -p /data/storage && chown -R wfa:wfa /data /app
USER wfa

ENV STORAGE_DIR=/data/storage
EXPOSE 8000
# Migraciones + catálogo + servidor en $PORT (ver scripts/start.sh).
CMD ["sh", "scripts/start.sh"]
