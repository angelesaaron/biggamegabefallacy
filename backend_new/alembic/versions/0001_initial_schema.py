"""Initial schema — all 10 tables.

Revision ID: 0001
Revises:
Create Date: 2026-03-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Tables are created in FK dependency order.
    # players and games have no dependencies and come first.

    # ── players ───────────────────────────────────────────────────────────────
    op.create_table(
        "players",
        sa.Column("player_id", sa.String(50), primary_key=True),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("position", sa.String(10), nullable=False),
        sa.Column("team", sa.String(10), nullable=True),
        sa.Column("is_te", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("draft_round", sa.Integer, nullable=True),
        sa.Column("experience", sa.Integer, nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("headshot_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_players_full_name", "players", ["full_name"])
    op.create_index("ix_players_active", "players", ["active"])

    # ── games ─────────────────────────────────────────────────────────────────
    op.create_table(
        "games",
        sa.Column("game_id", sa.String(30), primary_key=True),
        sa.Column("season", sa.Integer, nullable=False),
        sa.Column("week", sa.Integer, nullable=False),
        sa.Column("season_type", sa.String(10), nullable=False),
        sa.Column("home_team", sa.String(10), nullable=False),
        sa.Column("away_team", sa.String(10), nullable=False),
        sa.Column("game_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="scheduled"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_games_season", "games", ["season"])
    op.create_index("ix_games_week", "games", ["week"])

    # ── rookie_buckets ────────────────────────────────────────────────────────
    # No FK dependencies. Seeded separately via POST /admin/seed/rookie-buckets.
    op.create_table(
        "rookie_buckets",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("draft_round", sa.Integer, nullable=False),
        sa.Column("pos", sa.String(5), nullable=False),
        sa.Column("targets_pg", sa.Float, nullable=True),
        sa.Column("yards_pg", sa.Float, nullable=True),
        sa.Column("receptions_pg", sa.Float, nullable=True),
        sa.Column("roll3_targets", sa.Float, nullable=True),
        sa.Column("roll3_yards", sa.Float, nullable=True),
        sa.Column("roll3_receptions", sa.Float, nullable=True),
        sa.Column("lag_targets", sa.Float, nullable=True),
        sa.Column("lag_yards", sa.Float, nullable=True),
        sa.Column("target_share", sa.Float, nullable=True),
        sa.Column("roll3_long_rec", sa.Float, nullable=True),
        sa.Column("roll3_target_std", sa.Float, nullable=True),
        sa.Column("tds_last3", sa.Float, nullable=True),
        sa.Column("td_streak", sa.Float, nullable=True),
        sa.Column("td_rate_eb", sa.Float, nullable=True),
        sa.Column("td_rate_eb_std", sa.Float, nullable=True),
        sa.Column("lag_snap_pct", sa.Float, nullable=True),
        sa.Column("roll3_snap_pct", sa.Float, nullable=True),
        sa.Column("roll3_rz_targets", sa.Float, nullable=True),
        sa.Column("rz_target_share", sa.Float, nullable=True),
        sa.Column("rz_td_rate_eb", sa.Float, nullable=True),
        sa.UniqueConstraint("draft_round", "pos", name="uq_rookie_bucket"),
    )

    # ── player_game_logs ──────────────────────────────────────────────────────
    op.create_table(
        "player_game_logs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "player_id", sa.String(50),
            sa.ForeignKey("players.player_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "game_id", sa.String(30),
            sa.ForeignKey("games.game_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("season", sa.Integer, nullable=False),
        sa.Column("week", sa.Integer, nullable=False),
        sa.Column("team", sa.String(10), nullable=False),
        sa.Column("is_home", sa.Boolean, nullable=False),
        sa.Column("targets", sa.Integer, nullable=False, server_default="0"),
        sa.Column("receptions", sa.Integer, nullable=False, server_default="0"),
        sa.Column("rec_yards", sa.Integer, nullable=False, server_default="0"),
        sa.Column("rec_tds", sa.Integer, nullable=False, server_default="0"),
        sa.Column("long_rec", sa.Integer, nullable=True),
        sa.Column("snap_count", sa.Integer, nullable=True),
        sa.Column("snap_pct", sa.Numeric(4, 3), nullable=True),
        sa.Column("rz_targets", sa.Integer, nullable=True),
        sa.Column("rz_rec_tds", sa.Integer, nullable=True),
        sa.Column("data_source_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("player_id", "game_id", name="uq_player_game_log"),
    )
    op.create_index("ix_player_game_logs_player_id", "player_game_logs", ["player_id"])
    op.create_index("ix_player_game_logs_game_id", "player_game_logs", ["game_id"])
    op.create_index(
        "ix_player_game_logs_player_season_week",
        "player_game_logs", ["player_id", "season", "week"],
    )

    # ── team_game_stats ───────────────────────────────────────────────────────
    op.create_table(
        "team_game_stats",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "game_id", sa.String(30),
            sa.ForeignKey("games.game_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("team", sa.String(10), nullable=False),
        sa.Column("season", sa.Integer, nullable=False),
        sa.Column("week", sa.Integer, nullable=False),
        sa.Column("team_targets", sa.Integer, nullable=False),
        sa.Column("team_rec_tds", sa.Integer, nullable=False),
        sa.Column("team_rz_targets", sa.Integer, nullable=True),
        sa.Column("team_rz_tds", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("game_id", "team", name="uq_team_game_stats"),
    )
    op.create_index("ix_team_game_stats_game_id", "team_game_stats", ["game_id"])
    op.create_index("ix_team_game_stats_team", "team_game_stats", ["team"])

    # ── player_season_state ───────────────────────────────────────────────────
    op.create_table(
        "player_season_state",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "player_id", sa.String(50),
            sa.ForeignKey("players.player_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("season", sa.Integer, nullable=False),
        sa.Column("join_season", sa.Integer, nullable=False),
        sa.Column("team", sa.String(10), nullable=True),
        sa.Column("draft_round", sa.Integer, nullable=True),
        sa.Column("targets_pg", sa.Numeric, nullable=True),
        sa.Column("yards_pg", sa.Numeric, nullable=True),
        sa.Column("receptions_pg", sa.Numeric, nullable=True),
        sa.Column("roll3_targets", sa.Numeric, nullable=True),
        sa.Column("roll3_yards", sa.Numeric, nullable=True),
        sa.Column("roll3_receptions", sa.Numeric, nullable=True),
        sa.Column("lag_targets", sa.Numeric, nullable=True),
        sa.Column("lag_yards", sa.Numeric, nullable=True),
        sa.Column("target_share", sa.Numeric, nullable=True),
        sa.Column("roll3_long_rec", sa.Numeric, nullable=True),
        sa.Column("roll3_target_std", sa.Numeric, nullable=True),
        sa.Column("tds_last3", sa.Integer, nullable=True),
        sa.Column("td_streak", sa.Integer, nullable=True),
        sa.Column("td_rate_eb", sa.Numeric, nullable=True),
        sa.Column("td_rate_eb_std", sa.Numeric, nullable=True),
        sa.Column("lag_snap_pct", sa.Numeric, nullable=True),
        sa.Column("roll3_snap_pct", sa.Numeric, nullable=True),
        sa.Column("roll3_rz_targets", sa.Numeric, nullable=True),
        sa.Column("rz_target_share", sa.Numeric, nullable=True),
        sa.Column("rz_td_rate_eb", sa.Numeric, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("player_id", "season", name="uq_player_season_state"),
    )
    op.create_index("ix_player_season_state_player_id", "player_season_state", ["player_id"])

    # ── player_features ───────────────────────────────────────────────────────
    op.create_table(
        "player_features",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "player_id", sa.String(50),
            sa.ForeignKey("players.player_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("season", sa.Integer, nullable=False),
        sa.Column("week", sa.Integer, nullable=False),
        sa.Column("feature_version", sa.String(20), nullable=False),
        sa.Column("targets_pg", sa.Numeric, nullable=True),
        sa.Column("roll3_targets", sa.Numeric, nullable=True),
        sa.Column("yards_pg", sa.Numeric, nullable=True),
        sa.Column("receptions_pg", sa.Numeric, nullable=True),
        sa.Column("roll3_yards", sa.Numeric, nullable=True),
        sa.Column("roll3_receptions", sa.Numeric, nullable=True),
        sa.Column("lag_targets", sa.Numeric, nullable=True),
        sa.Column("lag_yards", sa.Numeric, nullable=True),
        sa.Column("target_share", sa.Numeric, nullable=True),
        sa.Column("roll3_long_rec", sa.Numeric, nullable=True),
        sa.Column("roll3_target_std", sa.Numeric, nullable=True),
        sa.Column("tds_last3", sa.Numeric, nullable=True),
        sa.Column("td_streak", sa.Integer, nullable=True),
        sa.Column("td_rate_eb", sa.Numeric, nullable=True),
        sa.Column("td_rate_eb_std", sa.Numeric, nullable=True),
        sa.Column("is_te", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("lag_snap_pct", sa.Numeric, nullable=True),
        sa.Column("roll3_snap_pct", sa.Numeric, nullable=True),
        sa.Column("roll3_rz_targets", sa.Numeric, nullable=True),
        sa.Column("rz_target_share", sa.Numeric, nullable=True),
        sa.Column("rz_td_rate_eb", sa.Numeric, nullable=True),
        sa.Column("is_early_season", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("carry_forward_used", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("completeness_score", sa.Numeric(3, 2), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint(
            "player_id", "season", "week", "feature_version",
            name="uq_player_features",
        ),
    )
    op.create_index("ix_player_features_player_id", "player_features", ["player_id"])
    op.create_index(
        "ix_player_features_lookup",
        "player_features", ["player_id", "season", "week"],
    )

    # ── predictions ───────────────────────────────────────────────────────────
    op.create_table(
        "predictions",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "player_id", sa.String(50),
            sa.ForeignKey("players.player_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("season", sa.Integer, nullable=False),
        sa.Column("week", sa.Integer, nullable=False),
        sa.Column("model_version", sa.String(30), nullable=False),
        sa.Column(
            "feature_row_id", sa.BigInteger,
            sa.ForeignKey("player_features.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("raw_prob", sa.Numeric(6, 5), nullable=False),
        sa.Column("calibrated_prob", sa.Numeric(6, 5), nullable=False),
        sa.Column("week_scalar", sa.Numeric(5, 4), nullable=False, server_default="1.0"),
        sa.Column("final_prob", sa.Numeric(6, 5), nullable=False),
        sa.Column("completeness_score", sa.Numeric(3, 2), nullable=True),
        sa.Column("is_low_confidence", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint(
            "player_id", "season", "week", "model_version",
            name="uq_prediction",
        ),
    )
    op.create_index("ix_predictions_player_id", "predictions", ["player_id"])
    op.create_index("ix_predictions_season_week", "predictions", ["season", "week"])

    # ── sportsbook_odds ───────────────────────────────────────────────────────
    op.create_table(
        "sportsbook_odds",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "player_id", sa.String(50),
            sa.ForeignKey("players.player_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "game_id", sa.String(30),
            sa.ForeignKey("games.game_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("season", sa.Integer, nullable=False),
        sa.Column("week", sa.Integer, nullable=False),
        sa.Column("sportsbook", sa.String(30), nullable=False),
        sa.Column("odds", sa.Integer, nullable=False),
        sa.Column("implied_prob", sa.Numeric(6, 5), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("player_id", "game_id", "sportsbook", name="uq_sportsbook_odds"),
    )
    op.create_index("ix_sportsbook_odds_player_id", "sportsbook_odds", ["player_id"])
    op.create_index("ix_sportsbook_odds_game_id", "sportsbook_odds", ["game_id"])
    op.create_index("ix_sportsbook_odds_season_week", "sportsbook_odds", ["season", "week"])

    # ── data_quality_events ───────────────────────────────────────────────────
    op.create_table(
        "data_quality_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column(
            "player_id", sa.String(50),
            sa.ForeignKey("players.player_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "game_id", sa.String(30),
            sa.ForeignKey("games.game_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("season", sa.Integer, nullable=False),
        sa.Column("week", sa.Integer, nullable=False),
        sa.Column("detail", sa.Text, nullable=True),
        sa.Column("auto_resolvable", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_data_quality_events_event_type", "data_quality_events", ["event_type"])
    op.create_index("ix_data_quality_events_player_id", "data_quality_events", ["player_id"])
    op.create_index("ix_dq_events_season_week", "data_quality_events", ["season", "week"])
    op.create_index("ix_dq_events_unresolved", "data_quality_events", ["resolved_at"])


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table("data_quality_events")
    op.drop_table("sportsbook_odds")
    op.drop_table("predictions")
    op.drop_table("player_features")
    op.drop_table("player_season_state")
    op.drop_table("team_game_stats")
    op.drop_table("player_game_logs")
    op.drop_table("rookie_buckets")
    op.drop_table("games")
    op.drop_table("players")
