"""player_season_state: index join_season + tds_last3 Numeric.

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-05

Changes:
  - Add ix_player_season_state_join_season index on join_season.
    _get_prior_states() in feature_compute.py filters WHERE join_season = :season
    on every feature compute run — without this index it's a full table scan.
  - Change tds_last3 from INTEGER to NUMERIC to match player_features.tds_last3
    and the float returned by feature_math.compute_features_from_logs().
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_player_season_state_join_season",
        "player_season_state",
        ["join_season"],
    )
    op.alter_column(
        "player_season_state",
        "tds_last3",
        existing_type=sa.Integer(),
        type_=sa.Numeric(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "player_season_state",
        "tds_last3",
        existing_type=sa.Numeric(),
        type_=sa.Integer(),
        existing_nullable=True,
    )
    op.drop_index("ix_player_season_state_join_season", table_name="player_season_state")
