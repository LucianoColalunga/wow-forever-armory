"""Esquemas Pydantic de la API pública (se publican en OpenAPI)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

T = TypeVar("T")

# Validación simple a propósito: acepta dominios internos (p. ej. admin@wfa.local).
Email = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_lower=True, max_length=254, pattern=r"^[^@\s]{1,64}@[^@\s]{1,189}$"),
]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DataMeta(BaseModel):
    dataset: Literal["real", "demo"]
    is_demo: bool = Field(description="True si los datos son fixtures sintéticos de demostración.")
    data_version: int = Field(description="Versión de la caché de rankings del dataset.")
    last_processed_at: datetime | None = Field(description="Último reporte procesado del dataset.")
    stale: bool = Field(description="True si no entraron datos nuevos en STALE_AFTER_HOURS.")
    generated_at: datetime


class PageOf(BaseModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int
    meta: DataMeta | None = None


class GuildRef(ORM):
    id: int
    name: str
    realm: str
    region: str
    faction: str | None = None


class CharacterOut(ORM):
    id: int
    name: str
    realm: str
    region: str
    class_slug: str | None
    spec: str | None
    class_source: str = Field(description="combatant_info | signature | role | admin | unknown")
    class_confidence: float
    faction: str | None
    guild: GuildRef | None = None
    guild_source: str | None = Field(default=None, description="report_tag (inferido) | admin | submission")
    first_seen_at: datetime | None
    last_seen_at: datetime | None
    dataset: str


class InstanceOut(ORM):
    id: int
    slug: str
    name: str
    kind: str
    max_players: int | None
    verification: str
    source_url: str
    is_new: bool
    level_range: str | None
    notes: str


class EncounterOut(ORM):
    id: int
    game_encounter_id: int
    name: str
    instance_id: int | None
    dataset: str


class ParticipantOut(BaseModel):
    character_id: int
    name: str
    realm: str
    class_slug: str | None
    spec: str | None
    role: str
    damage_done: int
    effective_damage: int
    overkill: int
    damage_absorbed_by_target: int
    damage_to_players: int
    healing_gross: int
    healing_effective: int
    overhealing: int
    heal_absorbed: int
    absorbs_provided: int
    damage_taken: int
    damage_taken_absorbed: int
    deaths: int
    interrupts: int
    dispels: int
    killing_blows: int
    time_alive_ms: int
    dps: float
    hps: float
    aps: float
    dtps: float
    survival_pct: float
    abilities: dict[str, Any] | None = None
    death_log: list[Any] | None = None


class FightSummary(BaseModel):
    id: int
    kind: str
    encounter: EncounterOut | None
    instance: InstanceOut | None
    difficulty_id: int | None
    group_size: int | None
    success: bool | None
    start_at: datetime
    duration_ms: int
    zone_name: str | None
    rankable: bool
    unrankable_reason: str | None
    duplicate_of_id: int | None
    boss_min_hp_pct: float | None
    player_count: int
    report_public_id: str
    dataset: str


class FightDetail(FightSummary):
    participants: list[ParticipantOut]
    timeline: dict[str, Any] | None
    issues: list[dict[str, Any]]
    source: dict[str, Any] = Field(description="Trazabilidad: archivo de origen, líneas y versión del parser.")


class ImportAccepted(BaseModel):
    report_id: str
    status: str
    duplicate: bool = Field(description="True si el mismo archivo ya estaba importado (no se procesa de nuevo).")
    job_id: int | None
    dataset: str
    message: str


class LoginIn(BaseModel):
    email: Email
    password: str = Field(min_length=1, max_length=256)


class UserOut(ORM):
    id: int
    email: str
    display_name: str
    role: str
    is_active: bool


class LoginOut(BaseModel):
    user: UserOut
    csrf_token: str


class ReasonIn(BaseModel):
    reason: str = Field(min_length=5, max_length=2000, description="Motivo obligatorio (queda en la auditoría).")


class SubmissionIn(BaseModel):
    kind: Literal["character_guild", "class_spec", "note"]
    payload: dict[str, Any]
    contact: str | None = Field(default=None, max_length=128)
