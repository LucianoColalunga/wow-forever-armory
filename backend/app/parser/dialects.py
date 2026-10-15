"""Dialectos de combat log según la cabecera ``COMBAT_LOG_VERSION``.

Cabecera (v22): ``COMBAT_LOG_VERSION,22,ADVANCED_LOG_ENABLED,1,BUILD_VERSION,1.60.1,PROJECT_ID,18``

- ``PROJECT_ID,18`` + ``BUILD_VERSION,1.60.1``: muestra real de la beta de WoW: Forever
  (20/09/2026) publicada en github.com/Emyrk/chronicle/issues/693.
- ``PROJECT_ID,1``: retail (ejemplo en wowcoach.gg/docs/combat-log/line-format).
- Otros PROJECT_ID se aceptan con el dialecto genérico y quedan marcados como no verificados.

El bloque avanzado no se asume fijo: se calibra por archivo (ver ``Dialect.advanced_block``).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.parser.constants import DEFAULT_ADVANCED_BLOCK


@dataclass(slots=True)
class Dialect:
    key: str
    label: str
    verified: bool
    log_version: int | None = None
    build_version: str | None = None
    project_id: int | None = None
    advanced_enabled: bool | None = None
    advanced_block: int = DEFAULT_ADVANCED_BLOCK
    advanced_block_calibrated: bool = False
    is_demo: bool = False
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "label": self.label,
            "verified": self.verified,
            "log_version": self.log_version,
            "build_version": self.build_version,
            "project_id": self.project_id,
            "advanced_enabled": self.advanced_enabled,
            "advanced_block": self.advanced_block,
            "advanced_block_calibrated": self.advanced_block_calibrated,
            "is_demo": self.is_demo,
        }


KNOWN_PROJECTS: dict[int, tuple[str, str, bool]] = {
    18: ("forever", "WoW: Forever", True),
    1: ("retail", "WoW (retail)", True),
}


def from_header(fields: list[str]) -> Dialect:
    """Construye el dialecto a partir de los campos de la cabecera."""
    values: dict[str, str] = {}
    # La cabecera alterna clave,valor: COMBAT_LOG_VERSION,22,ADVANCED_LOG_ENABLED,1,...
    for i in range(0, len(fields) - 1, 2):
        values[fields[i].strip().upper()] = fields[i + 1].strip()

    def _int(name: str) -> int | None:
        raw = values.get(name)
        if raw is None:
            return None
        try:
            return int(raw)
        except ValueError:
            return None

    project_id = _int("PROJECT_ID")
    build = values.get("BUILD_VERSION")
    adv = values.get("ADVANCED_LOG_ENABLED")
    key, label, verified = KNOWN_PROJECTS.get(project_id or -1, ("generic", "Genérico (no verificado)", False))
    dialect = Dialect(
        key=key,
        label=label,
        verified=verified,
        log_version=_int("COMBAT_LOG_VERSION"),
        build_version=build,
        project_id=project_id,
        advanced_enabled=(adv == "1") if adv is not None else None,
    )
    # Los fixtures sintéticos del proyecto usan un BUILD_VERSION con sufijo -DEMO.
    # Así un archivo de demo nunca puede entrar como dato real (ver importer/pipeline.py).
    if build and "DEMO" in build.upper():
        dialect.is_demo = True
    if dialect.log_version is not None and dialect.log_version != 22:
        dialect.notes.append(
            f"COMBAT_LOG_VERSION {dialect.log_version}: sólo la versión 22 fue verificada; "
            "el resto se procesa con el mismo esquema y puede tener diferencias."
        )
    return dialect


def legacy() -> Dialect:
    """Archivo sin cabecera (clientes viejos o recortes manuales)."""
    return Dialect(
        key="legacy",
        label="Sin cabecera COMBAT_LOG_VERSION",
        verified=False,
        notes=["El archivo no tiene cabecera COMBAT_LOG_VERSION; se detectó el formato por contenido."],
    )
