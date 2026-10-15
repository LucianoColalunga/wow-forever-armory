"""Registro de fuentes con su estado verificado al 14/10/2026 (detalle en docs/RESEARCH.md)."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings
from app.sources.base import SourceInfo, SourceUnavailable


class CombatLogFileSource:
    info = SourceInfo(
        key="combat_log_file",
        label="Combat logs (archivo WoWCombatLog*.txt)",
        status="active",
        verified=True,
        provides=(
            "encuentros",
            "jugadores",
            "daño",
            "curación",
            "absorciones",
            "muertes",
            "interrupciones",
            "dispels",
            "campos de batalla",
        ),
        description="Importador propio del archivo que escribe el cliente con /combatlog. Formato v22 "
        "verificado con una cabecera real de la beta de Forever (PROJECT_ID 18, build 1.60.1).",
        limits="Los datos dependen de quién registra el log: en mundo abierto/campos de batalla el cliente sólo "
        "registra eventos cercanos (rango limitado). Sin Advanced Combat Logging no hay dueño de mascotas "
        "por bloque avanzado ni vida del jefe.",
        references=("https://warcraft.wiki.gg/wiki/COMBAT_LOG_EVENT", "https://github.com/Emyrk/chronicle/issues/693"),
    )

    def describe(self) -> dict[str, Any]:
        return self.info.as_dict()


class UserSubmissionSource:
    info = SourceInfo(
        key="user_submissions",
        label="Aportes de usuarios (moderados)",
        status="active",
        verified=False,
        provides=("pertenencia a hermandad", "corrección de clase/spec", "notas"),
        description="Los usuarios envían correcciones; nada se aplica sin aprobación de un admin y cada "
        "aprobación queda auditada.",
        limits="Datos autodeclarados: se marcan como tales en la interfaz.",
    )

    def describe(self) -> dict[str, Any]:
        return self.info.as_dict()


class BlizzardApiSource:
    """Cliente genérico de la API de Battle.net (OAuth client credentials).

    No hay namespace publicado para Forever ni respuesta oficial en el foro de API
    (us.forums.blizzard.com/en/blizzard/t/when-will-we-gain-api-access-to-forever-apis/59595).
    Queda desactivado; si Blizzard publica endpoints, se configura BLIZZARD_FOREVER_NAMESPACE.
    """

    TOKEN_URL = "https://oauth.battle.net/token"  # noqa: S105 - URL pública, no es un secreto

    info = SourceInfo(
        key="blizzard_api",
        label="API oficial de Blizzard (Battle.net)",
        status="unavailable",
        verified=False,
        provides=("perfiles", "hermandades", "temporadas"),
        description="Blizzard no publicó endpoints ni namespace para WoW: Forever y nunca ofreció API para "
        "beta/PTR. El adaptador existe pero no hace llamadas mientras no haya namespace verificado.",
        limits="Cuando exista: OAuth client credentials y cuota por cliente (36.000 solicitudes/hora según el "
        "foro de la API, sin confirmación oficial).",
        references=(
            "https://us.forums.blizzard.com/en/blizzard/t/when-will-we-gain-api-access-to-forever-apis/59595",
            "https://community.developer.battle.net/documentation",
        ),
    )

    def describe(self) -> dict[str, Any]:
        s = get_settings()
        d = self.info.as_dict()
        d["configured"] = bool(s.blizzard_client_id and s.blizzard_client_secret and s.blizzard_forever_namespace)
        return d

    def _token(self) -> str:
        s = get_settings()
        if not (s.blizzard_client_id and s.blizzard_client_secret and s.blizzard_forever_namespace):
            raise SourceUnavailable("API de Blizzard no configurada: no hay namespace verificado para Forever.")
        resp = httpx.post(
            self.TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(s.blizzard_client_id, s.blizzard_client_secret),
            timeout=10,
        )
        resp.raise_for_status()
        return str(resp.json()["access_token"])

    def get(self, region: str, path: str) -> dict[str, Any]:
        s = get_settings()
        token = self._token()
        resp = httpx.get(
            f"https://{region}.api.blizzard.com{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "Battlenet-Namespace": f"{s.blizzard_forever_namespace}-{region}",
            },
            timeout=10,
        )
        resp.raise_for_status()
        return dict(resp.json())


class ForeverLogsSource:
    info = SourceInfo(
        key="foreverlogs",
        label="Forever Logs (foreverlogs.gg, terceros)",
        status="disabled",
        verified=False,
        provides=("reportes de terceros", "rankings de mazmorras"),
        description="Sitio comunitario de logs de Forever. Su portada enlaza una 'Developer API', pero no se "
        "pudo leer la documentación ni los términos; un tercero informa que requiere clave del dueño.",
        limits="Sin documentación verificada: no se integra hasta contar con términos y autorización.",
        references=("https://foreverlogs.gg/",),
    )

    def describe(self) -> dict[str, Any]:
        return self.info.as_dict()


class AddonExportSource:
    info = SourceInfo(
        key="addon_export",
        label="Exportación por addon (SavedVariables)",
        status="planned",
        verified=False,
        provides=("roster de hermandad", "datos del propio personaje"),
        description="Forever restringe la API de addons (jugadores reportan límites al combat log sin filtrar). "
        "Los addons sí pueden activar /combatlog (LoggingCombat), que es el camino soportado hoy.",
        limits="Pendiente de verificar qué API de addons expone Forever en el cliente final.",
        references=(
            "https://github.com/FangYuanWoW/forever-logs-companion",
            "https://eu.forums.blizzard.com/en/wow/t/please-reconsider-the-addon-api-restrictions-in-forever/633555",
        ),
    )

    def describe(self) -> dict[str, Any]:
        return self.info.as_dict()


_SOURCES = (
    CombatLogFileSource(),
    UserSubmissionSource(),
    BlizzardApiSource(),
    ForeverLogsSource(),
    AddonExportSource(),
)


def all_sources() -> list[dict[str, Any]]:
    return [s.describe() for s in _SOURCES]
