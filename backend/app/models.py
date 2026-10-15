"""Modelos ORM (PostgreSQL). Las migraciones viven en alembic/versions."""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[Any, Any]] = {dict[str, Any]: JSONB, list[Any]: JSONB}


def _now() -> Any:
    return func.now()


# ---------------------------------------------------------------------------
# Usuarios, sesiones, API keys y auditoría
# ---------------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    display_name: Mapped[str] = mapped_column(String(64))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16))  # admin | uploader
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    user: Mapped[User] = relationship()


class ApiKey(Base):
    __tablename__ = "api_keys"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    prefix: Mapped[str] = mapped_column(String(12))
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user: Mapped[User] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    actor_label: Mapped[str] = mapped_column(String(254))
    action: Mapped[str] = mapped_column(String(64))
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[str] = mapped_column(String(64))
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    reason: Mapped[str] = mapped_column(Text)
    ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now(), index=True)

    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id"),)


# ---------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------


class Instance(Base):
    __tablename__ = "instances"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    kind: Mapped[str] = mapped_column(String(16))  # raid | dungeon | battleground
    max_players: Mapped[int | None] = mapped_column(Integer)
    verification: Mapped[str] = mapped_column(String(16))  # official | reported | verified_by_admin
    source_url: Mapped[str] = mapped_column(String(512))
    is_new: Mapped[bool] = mapped_column(Boolean, default=False)
    level_range: Mapped[str | None] = mapped_column(String(16))
    notes: Mapped[str] = mapped_column(Text, default="")
    game_instance_ids: Mapped[list[Any]] = mapped_column(JSONB, default=list)


class Encounter(Base):
    __tablename__ = "encounters"
    id: Mapped[int] = mapped_column(primary_key=True)
    game_encounter_id: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(128))
    instance_id: Mapped[int | None] = mapped_column(ForeignKey("instances.id", ondelete="SET NULL"), index=True)
    dataset: Mapped[str] = mapped_column(String(8))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now())
    instance: Mapped[Instance | None] = relationship()

    __table_args__ = (UniqueConstraint("game_encounter_id", "dataset", name="uq_encounter_game_dataset"),)


class Season(Base):
    __tablename__ = "seasons"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    kind: Mapped[str] = mapped_column(String(8))  # pve | pvp | all
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_official: Mapped[bool] = mapped_column(Boolean, default=False)
    source_note: Mapped[str] = mapped_column(Text, default="")


# ---------------------------------------------------------------------------
# Personajes y hermandades
# ---------------------------------------------------------------------------


class Guild(Base):
    __tablename__ = "guilds"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    realm: Mapped[str] = mapped_column(String(64), default="")
    region: Mapped[str] = mapped_column(String(8), default="")
    faction: Mapped[str | None] = mapped_column(String(16))
    dataset: Mapped[str] = mapped_column(String(8))
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now())

    __table_args__ = (
        UniqueConstraint("name", "realm", "region", "dataset", name="uq_guild_identity"),
        Index("ix_guilds_name_trgm", "name", postgresql_using="gin", postgresql_ops={"name": "gin_trgm_ops"}),
    )


class Character(Base):
    __tablename__ = "characters"
    id: Mapped[int] = mapped_column(primary_key=True)
    guid: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(64))
    realm: Mapped[str] = mapped_column(String(64), default="")
    region: Mapped[str] = mapped_column(String(8), default="")
    class_slug: Mapped[str | None] = mapped_column(String(16))
    spec: Mapped[str | None] = mapped_column(String(24))
    class_source: Mapped[str] = mapped_column(String(16), default="unknown")
    class_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    class_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    faction: Mapped[str | None] = mapped_column(String(16))
    guild_id: Mapped[int | None] = mapped_column(ForeignKey("guilds.id", ondelete="SET NULL"), index=True)
    guild_source: Mapped[str | None] = mapped_column(String(16))
    dataset: Mapped[str] = mapped_column(String(8))
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now())
    guild: Mapped[Guild | None] = relationship()

    __table_args__ = (
        UniqueConstraint("guid", "dataset", name="uq_character_guid_dataset"),
        Index("ix_characters_name_trgm", "name", postgresql_using="gin", postgresql_ops={"name": "gin_trgm_ops"}),
        Index("ix_characters_dataset_class", "dataset", "class_slug", "spec"),
    )


# ---------------------------------------------------------------------------
# Importación
# ---------------------------------------------------------------------------


class SourceFile(Base):
    __tablename__ = "source_files"
    id: Mapped[int] = mapped_column(primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    original_name: Mapped[str] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    stored_path: Mapped[str] = mapped_column(String(512))
    content_kind: Mapped[str] = mapped_column(String(8))  # text | zip
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now())


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(16), unique=True)
    title: Mapped[str] = mapped_column(String(128))
    dataset: Mapped[str] = mapped_column(String(8))  # real | demo
    visibility: Mapped[str] = mapped_column(String(8), default="public")  # public | private
    status: Mapped[str] = mapped_column(String(16), index=True)  # queued|processing|processed|failed|duplicate
    source_file_id: Mapped[int] = mapped_column(ForeignKey("source_files.id", ondelete="RESTRICT"), index=True)
    guild_id: Mapped[int | None] = mapped_column(ForeignKey("guilds.id", ondelete="SET NULL"), index=True)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    region: Mapped[str] = mapped_column(String(8), default="")
    fallback_utc_offset: Mapped[int | None] = mapped_column(Integer)
    default_year: Mapped[int | None] = mapped_column(Integer)
    parser_version: Mapped[str | None] = mapped_column(String(16))
    dialect: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    stats: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    log_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    log_ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now(), index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_file: Mapped[SourceFile] = relationship()
    guild: Mapped[Guild | None] = relationship()


class ImportJob(Base):
    __tablename__ = "import_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # process | reprocess
    status: Mapped[str] = mapped_column(String(16))  # queued | running | succeeded | failed | dead
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=4)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now())
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[str | None] = mapped_column(String(64))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_jobs_status_run_after", "status", "run_after"),)


class ReportIssue(Base):
    __tablename__ = "report_issues"
    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    fight_id: Mapped[int | None] = mapped_column(ForeignKey("fights.id", ondelete="CASCADE"))
    severity: Mapped[str] = mapped_column(String(8))
    code: Mapped[str] = mapped_column(String(48))
    message: Mapped[str] = mapped_column(Text)
    line_no: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now())


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"
    worker_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now())
    processed: Mapped[int] = mapped_column(Integer, default=0)


# ---------------------------------------------------------------------------
# Combates y estadísticas
# ---------------------------------------------------------------------------


class Fight(Base):
    __tablename__ = "fights"
    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    encounter_id: Mapped[int | None] = mapped_column(ForeignKey("encounters.id", ondelete="SET NULL"))
    instance_id: Mapped[int | None] = mapped_column(ForeignKey("instances.id", ondelete="SET NULL"), index=True)
    season_id: Mapped[int | None] = mapped_column(ForeignKey("seasons.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(16))  # encounter | dungeon_run | battleground
    dataset: Mapped[str] = mapped_column(String(8))
    difficulty_id: Mapped[int | None] = mapped_column(Integer)
    group_size: Mapped[int | None] = mapped_column(Integer)
    success: Mapped[bool | None] = mapped_column(Boolean)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int] = mapped_column(Integer)
    zone_name: Mapped[str | None] = mapped_column(String(128))
    game_instance_id: Mapped[int | None] = mapped_column(Integer)
    first_line: Mapped[int] = mapped_column(Integer)
    last_line: Mapped[int | None] = mapped_column(Integer)
    fight_key: Mapped[str] = mapped_column(String(64), index=True)
    duplicate_of_id: Mapped[int | None] = mapped_column(ForeignKey("fights.id", ondelete="SET NULL"))
    rankable: Mapped[bool] = mapped_column(Boolean, default=True)
    unrankable_reason: Mapped[str | None] = mapped_column(String(64))
    excluded_by_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    boss_min_hp_pct: Mapped[float | None] = mapped_column(Float)
    player_count: Mapped[int] = mapped_column(Integer, default=0)
    parser_version: Mapped[str] = mapped_column(String(16))
    timeline: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now())
    report: Mapped[Report] = relationship()
    encounter: Mapped[Encounter | None] = relationship()
    instance: Mapped[Instance | None] = relationship()

    __table_args__ = (
        Index("ix_fights_partition", "dataset", "encounter_id", "difficulty_id", "group_size", "success"),
    )


class FightParticipant(Base):
    __tablename__ = "fight_participants"
    id: Mapped[int] = mapped_column(primary_key=True)
    fight_id: Mapped[int] = mapped_column(ForeignKey("fights.id", ondelete="CASCADE"))
    character_id: Mapped[int] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"), index=True)
    class_slug: Mapped[str | None] = mapped_column(String(16))
    spec: Mapped[str | None] = mapped_column(String(24))
    role: Mapped[str] = mapped_column(String(8))
    damage_done: Mapped[int] = mapped_column(BigInteger, default=0)
    effective_damage: Mapped[int] = mapped_column(BigInteger, default=0)
    overkill: Mapped[int] = mapped_column(BigInteger, default=0)
    damage_absorbed_by_target: Mapped[int] = mapped_column(BigInteger, default=0)
    damage_to_players: Mapped[int] = mapped_column(BigInteger, default=0)
    healing_gross: Mapped[int] = mapped_column(BigInteger, default=0)
    healing_effective: Mapped[int] = mapped_column(BigInteger, default=0)
    overhealing: Mapped[int] = mapped_column(BigInteger, default=0)
    heal_absorbed: Mapped[int] = mapped_column(BigInteger, default=0)
    absorbs_provided: Mapped[int] = mapped_column(BigInteger, default=0)
    damage_taken: Mapped[int] = mapped_column(BigInteger, default=0)
    damage_taken_absorbed: Mapped[int] = mapped_column(BigInteger, default=0)
    deaths: Mapped[int] = mapped_column(Integer, default=0)
    interrupts: Mapped[int] = mapped_column(Integer, default=0)
    dispels: Mapped[int] = mapped_column(Integer, default=0)
    killing_blows: Mapped[int] = mapped_column(Integer, default=0)
    time_alive_ms: Mapped[int] = mapped_column(Integer, default=0)
    dps: Mapped[float] = mapped_column(Float, default=0.0)
    hps: Mapped[float] = mapped_column(Float, default=0.0)
    aps: Mapped[float] = mapped_column(Float, default=0.0)
    dtps: Mapped[float] = mapped_column(Float, default=0.0)
    survival_pct: Mapped[float] = mapped_column(Float, default=100.0)
    abilities: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    death_log: Mapped[list[Any] | None] = mapped_column(JSONB)
    gear: Mapped[list[Any] | None] = mapped_column(JSONB)  # objetos equipados (COMBATANT_INFO)
    casts: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # línea de tiempo de lanzamientos
    fight: Mapped[Fight] = relationship()
    character: Mapped[Character] = relationship()

    __table_args__ = (UniqueConstraint("fight_id", "character_id", name="uq_participant_fight_character"),)


class RankingEntry(Base):
    """Caché desnormalizada de rankings: una fila por (combate rankeable, personaje).

    Se actualiza de forma incremental al procesar/reprocesar/excluir un reporte.
    """

    __tablename__ = "ranking_entries"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    kind: Mapped[str] = mapped_column(String(8))  # pve | pvp
    dataset: Mapped[str] = mapped_column(String(8))
    fight_id: Mapped[int] = mapped_column(ForeignKey("fights.id", ondelete="CASCADE"))
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"), index=True)
    encounter_id: Mapped[int | None] = mapped_column(ForeignKey("encounters.id", ondelete="CASCADE"))
    instance_id: Mapped[int | None] = mapped_column(ForeignKey("instances.id", ondelete="SET NULL"))
    season_id: Mapped[int | None] = mapped_column(ForeignKey("seasons.id", ondelete="SET NULL"))
    difficulty_id: Mapped[int | None] = mapped_column(Integer)
    group_size: Mapped[int | None] = mapped_column(Integer)
    class_slug: Mapped[str | None] = mapped_column(String(16))
    spec: Mapped[str | None] = mapped_column(String(24))
    role: Mapped[str] = mapped_column(String(8))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int] = mapped_column(Integer)
    dps: Mapped[float] = mapped_column(Float)
    hps: Mapped[float] = mapped_column(Float)
    aps: Mapped[float] = mapped_column(Float)
    dtps: Mapped[float] = mapped_column(Float)
    damage_done: Mapped[int] = mapped_column(BigInteger)
    healing_effective: Mapped[int] = mapped_column(BigInteger)
    absorbs_provided: Mapped[int] = mapped_column(BigInteger)
    damage_taken: Mapped[int] = mapped_column(BigInteger)
    damage_to_players: Mapped[int] = mapped_column(BigInteger, default=0)
    killing_blows: Mapped[int] = mapped_column(Integer, default=0)
    deaths: Mapped[int] = mapped_column(Integer)
    interrupts: Mapped[int] = mapped_column(Integer)
    dispels: Mapped[int] = mapped_column(Integer)
    survival_pct: Mapped[float] = mapped_column(Float)

    __table_args__ = (
        UniqueConstraint("fight_id", "character_id", name="uq_ranking_fight_character"),
        Index("ix_ranking_partition", "dataset", "kind", "encounter_id", "difficulty_id", "group_size"),
        Index("ix_ranking_bucket", "dataset", "encounter_id", "difficulty_id", "group_size", "class_slug", "spec"),
        Index("ix_ranking_time", "dataset", "kind", "occurred_at"),
    )


class RankingVersion(Base):
    __tablename__ = "ranking_versions"
    dataset: Mapped[str] = mapped_column(String(8), primary_key=True)
    version: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now())


class Submission(Base):
    """Aportes de usuarios (pendientes de moderación). Nunca se aplican sin aprobación admin."""

    __tablename__ = "submissions"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))  # character_guild | class_spec | note
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)  # pending|approved|rejected
    submitted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    contact: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_now())
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)
