"""Configuración por variables de entorno (ver .env.example en la raíz del repo)."""

from __future__ import annotations

import ipaddress
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="development", description="development | test | production")
    database_url: str = "postgresql+psycopg://wfa:wfa@localhost:5432/wfa"
    db_pool_size: int = 10
    storage_dir: Path = Path("./storage")

    # Seguridad
    session_ttl_hours: int = 12
    cookie_secure: bool = False
    cookie_domain: str | None = None
    trusted_proxies: str = ""  # IPs o rangos CIDR separados por coma cuyo X-Forwarded-For se acepta
    # Secreto compartido con el proxy de Next.js (Vercel): permite confiar en la IP real del visitante
    # aunque el proxy no tenga IP fija. Vacío = desactivado.
    proxy_shared_secret: str | None = None
    # Cabecera con la IP del visitante que escribe (y sobrescribe) el borde de la plataforma, p. ej.
    # ``cf-connecting-ip`` en Render (Cloudflare). Sólo para plataformas donde el contenedor no es
    # accesible sin pasar por ese borde. Vacío = desactivado.
    client_ip_header: str = ""
    cors_origins: str = ""  # orígenes separados por coma (vacío = mismo origen vía proxy de Next.js)
    public_uploads: bool = False  # si es False, importar requiere usuario uploader/admin o API key

    # Límites del importador
    max_upload_mb: int = 200
    max_uncompressed_mb: int = 600
    max_compression_ratio: int = 40

    # Rate limiting (por IP, ventana de 60 s salvo indicación)
    rate_limit_public_per_min: int = 240
    rate_limit_search_per_min: int = 60
    rate_limit_login_per_15min: int = 10
    rate_limit_import_per_hour: int = 20

    # Worker
    worker_poll_seconds: float = 2.0
    job_max_attempts: int = 4
    job_backoff_base_seconds: int = 15
    job_stale_minutes: int = 30
    inline_worker: bool = False  # procesa trabajos dentro del proceso de la API (despliegues de 1 contenedor)

    # Rankings
    min_bucket_size: int = 10  # muestra mínima por (encuentro, dificultad, tamaño, clase, spec) para percentiles
    consistency_min_kills: int = 3
    consistency_last_n: int = 10
    stale_after_hours: int = 72
    ranking_cache_seconds: int = 120

    # Bootstrap del primer admin (sólo se usa con `python -m app.cli create-admin --from-env`)
    admin_bootstrap_email: str | None = None
    admin_bootstrap_password: str | None = None

    # Integraciones externas (desactivadas: no hay API verificada para Forever)
    blizzard_client_id: str | None = None
    blizzard_client_secret: str | None = None
    blizzard_forever_namespace: str | None = None

    log_level: str = "INFO"

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, v: str) -> str:
        """Acepta la URL tal como la entregan Neon, Render o Heroku (postgres:// o postgresql://)."""
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://") :]
        if v.startswith("postgresql://"):
            v = "postgresql+psycopg://" + v[len("postgresql://") :]
        return v

    @field_validator("storage_dir")
    @classmethod
    def _resolve_storage(cls, v: Path) -> Path:
        return v.expanduser().resolve()

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def trusted_proxy_networks(self) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
        nets = []
        for raw in self.trusted_proxies.split(","):
            raw = raw.strip()
            if raw:
                try:
                    nets.append(ipaddress.ip_network(raw, strict=False))
                except ValueError:
                    continue
        return nets

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
