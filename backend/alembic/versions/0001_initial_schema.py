"""Esquema inicial: usuarios, auditoría, catálogo, importación, combates y caché de rankings.

Revision ID: 0001
Revises: 
Create Date: 2026-10-14 20:55:31.869603

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # pg_trgm habilita la búsqueda difusa por nombre (índices GIN más abajo).
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table('guilds',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('realm', sa.String(length=64), nullable=False),
    sa.Column('region', sa.String(length=8), nullable=False),
    sa.Column('faction', sa.String(length=16), nullable=True),
    sa.Column('dataset', sa.String(length=8), nullable=False),
    sa.Column('hidden', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name', 'realm', 'region', 'dataset', name='uq_guild_identity')
    )
    op.create_index('ix_guilds_name_trgm', 'guilds', ['name'], unique=False, postgresql_using='gin', postgresql_ops={'name': 'gin_trgm_ops'})
    op.create_table('instances',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('slug', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('max_players', sa.Integer(), nullable=True),
    sa.Column('verification', sa.String(length=16), nullable=False),
    sa.Column('source_url', sa.String(length=512), nullable=False),
    sa.Column('is_new', sa.Boolean(), nullable=False),
    sa.Column('level_range', sa.String(length=16), nullable=True),
    sa.Column('notes', sa.Text(), nullable=False),
    sa.Column('game_instance_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )
    op.create_table('ranking_versions',
    sa.Column('dataset', sa.String(length=8), nullable=False),
    sa.Column('version', sa.BigInteger(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('dataset')
    )
    op.create_table('seasons',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('slug', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('kind', sa.String(length=8), nullable=False),
    sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('ends_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('is_official', sa.Boolean(), nullable=False),
    sa.Column('source_note', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('display_name', sa.String(length=64), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )
    op.create_table('worker_heartbeats',
    sa.Column('worker_id', sa.String(length=64), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('processed', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('worker_id')
    )
    op.create_table('api_keys',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('prefix', sa.String(length=12), nullable=False),
    sa.Column('key_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('key_hash')
    )
    op.create_index(op.f('ix_api_keys_user_id'), 'api_keys', ['user_id'], unique=False)
    op.create_table('audit_log',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('actor_id', sa.Integer(), nullable=True),
    sa.Column('actor_label', sa.String(length=254), nullable=False),
    sa.Column('action', sa.String(length=64), nullable=False),
    sa.Column('entity_type', sa.String(length=32), nullable=False),
    sa.Column('entity_id', sa.String(length=64), nullable=False),
    sa.Column('before', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('after', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('ip', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_audit_entity', 'audit_log', ['entity_type', 'entity_id'], unique=False)
    op.create_index(op.f('ix_audit_log_created_at'), 'audit_log', ['created_at'], unique=False)
    op.create_table('characters',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('guid', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('realm', sa.String(length=64), nullable=False),
    sa.Column('region', sa.String(length=8), nullable=False),
    sa.Column('class_slug', sa.String(length=16), nullable=True),
    sa.Column('spec', sa.String(length=24), nullable=True),
    sa.Column('class_source', sa.String(length=16), nullable=False),
    sa.Column('class_confidence', sa.Float(), nullable=False),
    sa.Column('class_locked', sa.Boolean(), nullable=False),
    sa.Column('faction', sa.String(length=16), nullable=True),
    sa.Column('guild_id', sa.Integer(), nullable=True),
    sa.Column('guild_source', sa.String(length=16), nullable=True),
    sa.Column('dataset', sa.String(length=8), nullable=False),
    sa.Column('hidden', sa.Boolean(), nullable=False),
    sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['guild_id'], ['guilds.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('guid', 'dataset', name='uq_character_guid_dataset')
    )
    op.create_index('ix_characters_dataset_class', 'characters', ['dataset', 'class_slug', 'spec'], unique=False)
    op.create_index(op.f('ix_characters_guild_id'), 'characters', ['guild_id'], unique=False)
    op.create_index('ix_characters_name_trgm', 'characters', ['name'], unique=False, postgresql_using='gin', postgresql_ops={'name': 'gin_trgm_ops'})
    op.create_table('encounters',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('game_encounter_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('instance_id', sa.Integer(), nullable=True),
    sa.Column('dataset', sa.String(length=8), nullable=False),
    sa.Column('first_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['instance_id'], ['instances.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('game_encounter_id', 'dataset', name='uq_encounter_game_dataset')
    )
    op.create_index(op.f('ix_encounters_instance_id'), 'encounters', ['instance_id'], unique=False)
    op.create_table('sessions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('csrf_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('ip', sa.String(length=64), nullable=True),
    sa.Column('user_agent', sa.String(length=255), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_index(op.f('ix_sessions_user_id'), 'sessions', ['user_id'], unique=False)
    op.create_table('source_files',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('original_name', sa.String(length=255), nullable=False),
    sa.Column('size_bytes', sa.BigInteger(), nullable=False),
    sa.Column('stored_path', sa.String(length=512), nullable=False),
    sa.Column('content_kind', sa.String(length=8), nullable=False),
    sa.Column('uploaded_by', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('sha256')
    )
    op.create_table('submissions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('submitted_by', sa.Integer(), nullable=True),
    sa.Column('contact', sa.String(length=128), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('reviewed_by', sa.Integer(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('review_note', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['submitted_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_submissions_status'), 'submissions', ['status'], unique=False)
    op.create_table('reports',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('public_id', sa.String(length=16), nullable=False),
    sa.Column('title', sa.String(length=128), nullable=False),
    sa.Column('dataset', sa.String(length=8), nullable=False),
    sa.Column('visibility', sa.String(length=8), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('source_file_id', sa.Integer(), nullable=False),
    sa.Column('guild_id', sa.Integer(), nullable=True),
    sa.Column('uploaded_by', sa.Integer(), nullable=True),
    sa.Column('region', sa.String(length=8), nullable=False),
    sa.Column('fallback_utc_offset', sa.Integer(), nullable=True),
    sa.Column('default_year', sa.Integer(), nullable=True),
    sa.Column('parser_version', sa.String(length=16), nullable=True),
    sa.Column('dialect', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('stats', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('log_started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('log_ended_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['guild_id'], ['guilds.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['source_file_id'], ['source_files.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('public_id')
    )
    op.create_index(op.f('ix_reports_created_at'), 'reports', ['created_at'], unique=False)
    op.create_index(op.f('ix_reports_guild_id'), 'reports', ['guild_id'], unique=False)
    op.create_index(op.f('ix_reports_source_file_id'), 'reports', ['source_file_id'], unique=False)
    op.create_index(op.f('ix_reports_status'), 'reports', ['status'], unique=False)
    op.create_table('fights',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('report_id', sa.Integer(), nullable=False),
    sa.Column('encounter_id', sa.Integer(), nullable=True),
    sa.Column('instance_id', sa.Integer(), nullable=True),
    sa.Column('season_id', sa.Integer(), nullable=True),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('dataset', sa.String(length=8), nullable=False),
    sa.Column('difficulty_id', sa.Integer(), nullable=True),
    sa.Column('group_size', sa.Integer(), nullable=True),
    sa.Column('success', sa.Boolean(), nullable=True),
    sa.Column('start_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('end_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('duration_ms', sa.Integer(), nullable=False),
    sa.Column('zone_name', sa.String(length=128), nullable=True),
    sa.Column('game_instance_id', sa.Integer(), nullable=True),
    sa.Column('first_line', sa.Integer(), nullable=False),
    sa.Column('last_line', sa.Integer(), nullable=True),
    sa.Column('fight_key', sa.String(length=64), nullable=False),
    sa.Column('duplicate_of_id', sa.Integer(), nullable=True),
    sa.Column('rankable', sa.Boolean(), nullable=False),
    sa.Column('unrankable_reason', sa.String(length=64), nullable=True),
    sa.Column('excluded_by_admin', sa.Boolean(), nullable=False),
    sa.Column('boss_min_hp_pct', sa.Float(), nullable=True),
    sa.Column('player_count', sa.Integer(), nullable=False),
    sa.Column('parser_version', sa.String(length=16), nullable=False),
    sa.Column('timeline', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['duplicate_of_id'], ['fights.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['encounter_id'], ['encounters.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['instance_id'], ['instances.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['report_id'], ['reports.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['season_id'], ['seasons.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_fights_fight_key'), 'fights', ['fight_key'], unique=False)
    op.create_index(op.f('ix_fights_instance_id'), 'fights', ['instance_id'], unique=False)
    op.create_index('ix_fights_partition', 'fights', ['dataset', 'encounter_id', 'difficulty_id', 'group_size', 'success'], unique=False)
    op.create_index(op.f('ix_fights_report_id'), 'fights', ['report_id'], unique=False)
    op.create_index(op.f('ix_fights_start_at'), 'fights', ['start_at'], unique=False)
    op.create_table('import_jobs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('report_id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('max_attempts', sa.Integer(), nullable=False),
    sa.Column('run_after', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('locked_by', sa.String(length=64), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['report_id'], ['reports.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_import_jobs_report_id'), 'import_jobs', ['report_id'], unique=False)
    op.create_index('ix_jobs_status_run_after', 'import_jobs', ['status', 'run_after'], unique=False)
    op.create_table('fight_participants',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('fight_id', sa.Integer(), nullable=False),
    sa.Column('character_id', sa.Integer(), nullable=False),
    sa.Column('class_slug', sa.String(length=16), nullable=True),
    sa.Column('spec', sa.String(length=24), nullable=True),
    sa.Column('role', sa.String(length=8), nullable=False),
    sa.Column('damage_done', sa.BigInteger(), nullable=False),
    sa.Column('effective_damage', sa.BigInteger(), nullable=False),
    sa.Column('overkill', sa.BigInteger(), nullable=False),
    sa.Column('damage_absorbed_by_target', sa.BigInteger(), nullable=False),
    sa.Column('damage_to_players', sa.BigInteger(), nullable=False),
    sa.Column('healing_gross', sa.BigInteger(), nullable=False),
    sa.Column('healing_effective', sa.BigInteger(), nullable=False),
    sa.Column('overhealing', sa.BigInteger(), nullable=False),
    sa.Column('heal_absorbed', sa.BigInteger(), nullable=False),
    sa.Column('absorbs_provided', sa.BigInteger(), nullable=False),
    sa.Column('damage_taken', sa.BigInteger(), nullable=False),
    sa.Column('damage_taken_absorbed', sa.BigInteger(), nullable=False),
    sa.Column('deaths', sa.Integer(), nullable=False),
    sa.Column('interrupts', sa.Integer(), nullable=False),
    sa.Column('dispels', sa.Integer(), nullable=False),
    sa.Column('killing_blows', sa.Integer(), nullable=False),
    sa.Column('time_alive_ms', sa.Integer(), nullable=False),
    sa.Column('dps', sa.Float(), nullable=False),
    sa.Column('hps', sa.Float(), nullable=False),
    sa.Column('aps', sa.Float(), nullable=False),
    sa.Column('dtps', sa.Float(), nullable=False),
    sa.Column('survival_pct', sa.Float(), nullable=False),
    sa.Column('abilities', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('death_log', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['fight_id'], ['fights.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('fight_id', 'character_id', name='uq_participant_fight_character')
    )
    op.create_index(op.f('ix_fight_participants_character_id'), 'fight_participants', ['character_id'], unique=False)
    op.create_table('ranking_entries',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('kind', sa.String(length=8), nullable=False),
    sa.Column('dataset', sa.String(length=8), nullable=False),
    sa.Column('fight_id', sa.Integer(), nullable=False),
    sa.Column('report_id', sa.Integer(), nullable=False),
    sa.Column('character_id', sa.Integer(), nullable=False),
    sa.Column('encounter_id', sa.Integer(), nullable=True),
    sa.Column('instance_id', sa.Integer(), nullable=True),
    sa.Column('season_id', sa.Integer(), nullable=True),
    sa.Column('difficulty_id', sa.Integer(), nullable=True),
    sa.Column('group_size', sa.Integer(), nullable=True),
    sa.Column('class_slug', sa.String(length=16), nullable=True),
    sa.Column('spec', sa.String(length=24), nullable=True),
    sa.Column('role', sa.String(length=8), nullable=False),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('duration_ms', sa.Integer(), nullable=False),
    sa.Column('dps', sa.Float(), nullable=False),
    sa.Column('hps', sa.Float(), nullable=False),
    sa.Column('aps', sa.Float(), nullable=False),
    sa.Column('dtps', sa.Float(), nullable=False),
    sa.Column('damage_done', sa.BigInteger(), nullable=False),
    sa.Column('healing_effective', sa.BigInteger(), nullable=False),
    sa.Column('absorbs_provided', sa.BigInteger(), nullable=False),
    sa.Column('damage_taken', sa.BigInteger(), nullable=False),
    sa.Column('damage_to_players', sa.BigInteger(), nullable=False),
    sa.Column('killing_blows', sa.Integer(), nullable=False),
    sa.Column('deaths', sa.Integer(), nullable=False),
    sa.Column('interrupts', sa.Integer(), nullable=False),
    sa.Column('dispels', sa.Integer(), nullable=False),
    sa.Column('survival_pct', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['character_id'], ['characters.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['encounter_id'], ['encounters.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['fight_id'], ['fights.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['instance_id'], ['instances.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['report_id'], ['reports.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['season_id'], ['seasons.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('fight_id', 'character_id', name='uq_ranking_fight_character')
    )
    op.create_index('ix_ranking_bucket', 'ranking_entries', ['dataset', 'encounter_id', 'difficulty_id', 'group_size', 'class_slug', 'spec'], unique=False)
    op.create_index(op.f('ix_ranking_entries_character_id'), 'ranking_entries', ['character_id'], unique=False)
    op.create_index(op.f('ix_ranking_entries_report_id'), 'ranking_entries', ['report_id'], unique=False)
    op.create_index('ix_ranking_partition', 'ranking_entries', ['dataset', 'kind', 'encounter_id', 'difficulty_id', 'group_size'], unique=False)
    op.create_index('ix_ranking_time', 'ranking_entries', ['dataset', 'kind', 'occurred_at'], unique=False)
    op.create_table('report_issues',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('report_id', sa.Integer(), nullable=False),
    sa.Column('fight_id', sa.Integer(), nullable=True),
    sa.Column('severity', sa.String(length=8), nullable=False),
    sa.Column('code', sa.String(length=48), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('line_no', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['fight_id'], ['fights.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['report_id'], ['reports.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_report_issues_report_id'), 'report_issues', ['report_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_report_issues_report_id'), table_name='report_issues')
    op.drop_table('report_issues')
    op.drop_index('ix_ranking_time', table_name='ranking_entries')
    op.drop_index('ix_ranking_partition', table_name='ranking_entries')
    op.drop_index(op.f('ix_ranking_entries_report_id'), table_name='ranking_entries')
    op.drop_index(op.f('ix_ranking_entries_character_id'), table_name='ranking_entries')
    op.drop_index('ix_ranking_bucket', table_name='ranking_entries')
    op.drop_table('ranking_entries')
    op.drop_index(op.f('ix_fight_participants_character_id'), table_name='fight_participants')
    op.drop_table('fight_participants')
    op.drop_index('ix_jobs_status_run_after', table_name='import_jobs')
    op.drop_index(op.f('ix_import_jobs_report_id'), table_name='import_jobs')
    op.drop_table('import_jobs')
    op.drop_index(op.f('ix_fights_start_at'), table_name='fights')
    op.drop_index(op.f('ix_fights_report_id'), table_name='fights')
    op.drop_index('ix_fights_partition', table_name='fights')
    op.drop_index(op.f('ix_fights_instance_id'), table_name='fights')
    op.drop_index(op.f('ix_fights_fight_key'), table_name='fights')
    op.drop_table('fights')
    op.drop_index(op.f('ix_reports_status'), table_name='reports')
    op.drop_index(op.f('ix_reports_source_file_id'), table_name='reports')
    op.drop_index(op.f('ix_reports_guild_id'), table_name='reports')
    op.drop_index(op.f('ix_reports_created_at'), table_name='reports')
    op.drop_table('reports')
    op.drop_index(op.f('ix_submissions_status'), table_name='submissions')
    op.drop_table('submissions')
    op.drop_table('source_files')
    op.drop_index(op.f('ix_sessions_user_id'), table_name='sessions')
    op.drop_table('sessions')
    op.drop_index(op.f('ix_encounters_instance_id'), table_name='encounters')
    op.drop_table('encounters')
    op.drop_index('ix_characters_name_trgm', table_name='characters', postgresql_using='gin', postgresql_ops={'name': 'gin_trgm_ops'})
    op.drop_index(op.f('ix_characters_guild_id'), table_name='characters')
    op.drop_index('ix_characters_dataset_class', table_name='characters')
    op.drop_table('characters')
    op.drop_index(op.f('ix_audit_log_created_at'), table_name='audit_log')
    op.drop_index('ix_audit_entity', table_name='audit_log')
    op.drop_table('audit_log')
    op.drop_index(op.f('ix_api_keys_user_id'), table_name='api_keys')
    op.drop_table('api_keys')
    op.drop_table('worker_heartbeats')
    op.drop_table('users')
    op.drop_table('seasons')
    op.drop_table('ranking_versions')
    op.drop_table('instances')
    op.drop_index('ix_guilds_name_trgm', table_name='guilds', postgresql_using='gin', postgresql_ops={'name': 'gin_trgm_ops'})
    op.drop_table('guilds')
