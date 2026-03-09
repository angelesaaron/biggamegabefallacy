"""Drop player_aliases table.

Revision ID: c39879e4a4d4
Revises: 0003
Create Date: 2026-03-07

player_aliases was used for nflverse name→player_id resolution.
Replaced by the ID bridge (nflreadpy.load_players() cross-reference:
espn_id == Tank01 playerID). No name matching needed anymore.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "c39879e4a4d4"
down_revision: str | None = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_player_aliases_player_id")
    op.execute("DROP TABLE IF EXISTS player_aliases")


def downgrade() -> None:
    op.create_table(
        "player_aliases",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "player_id", sa.String(50),
            sa.ForeignKey("players.player_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("alias_name", sa.String(150), nullable=False),
        sa.Column("match_type", sa.String(20), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("player_id", "source", name="uq_player_alias_player_source"),
    )
    op.create_index("ix_player_aliases_player_id", "player_aliases", ["player_id"])
