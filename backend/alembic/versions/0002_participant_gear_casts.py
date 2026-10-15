"""Equipo y línea de tiempo de lanzamientos por participante.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("fight_participants", sa.Column("gear", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("fight_participants", sa.Column("casts", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("fight_participants", "casts")
    op.drop_column("fight_participants", "gear")
