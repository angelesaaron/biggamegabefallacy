"""team_game_stats: add team_rz_targets_all_pos column.

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-06

Changes:
  - Add team_rz_targets_all_pos (nullable Integer) to team_game_stats.
    This stores total RZ pass targets for ALL positions (WR+TE+RB+QB),
    sourced from nflverse PBP. Used as the correct denominator for
    rz_target_share in feature_compute — matching how the model was trained.

    team_rz_targets (existing) = WR/TE-only cumulative (kept for auditing).
    team_rz_targets_all_pos    = all-position cumulative (used in features).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "team_game_stats",
        sa.Column("team_rz_targets_all_pos", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("team_game_stats", "team_rz_targets_all_pos")
