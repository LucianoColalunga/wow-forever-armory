from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class SourceUnavailable(RuntimeError):
    """La fuente no está disponible (sin API verificada, sin credenciales o desactivada)."""


@dataclass(frozen=True, slots=True)
class SourceInfo:
    key: str
    label: str
    status: str  # active | unavailable | disabled | planned
    verified: bool
    provides: tuple[str, ...]
    description: str
    limits: str
    references: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "status": self.status,
            "verified": self.verified,
            "provides": list(self.provides),
            "description": self.description,
            "limits": self.limits,
            "references": list(self.references),
        }


class SourceAdapter(Protocol):
    info: SourceInfo

    def describe(self) -> dict[str, Any]: ...
