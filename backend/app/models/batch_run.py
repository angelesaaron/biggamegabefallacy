"""
Batch Run Model - Tracks batch process executions
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime

from app.database import Base


class BatchRun(Base):
    """
    Audit log for batch process executions.

    Tracks weekly updates, prediction generation, and roster refresh jobs
    with detailed metrics and status information.
    """
    __tablename__ = "batch_runs"

    id = Column(Integer, primary_key=True, index=True)

    # Batch identification
    batch_type = Column(String(50), nullable=False, index=True)  # weekly_update, prediction_generation, roster_refresh
    batch_mode = Column(String(50))  # full, odds_only, ingest_only, schedule_only
    season_year = Column(Integer, nullable=False, index=True)
    week = Column(Integer, nullable=False, index=True)
    season_type = Column(String(10))  # reg, post

    # Execution tracking
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime)
    duration_seconds = Column(Integer)
    status = Column(String(20), nullable=False, index=True)  # running, success, partial, failed

    # Batch metrics
    api_calls_made = Column(Integer, default=0)
    games_processed = Column(Integer, default=0)
    game_logs_added = Column(Integer, default=0)
    predictions_generated = Column(Integer, default=0)
    predictions_skipped = Column(Integer, default=0)  # Already existed (immutability)
    odds_synced = Column(Integer, default=0)
    errors_encountered = Column(Integer, default=0)

    # Diagnostics
    warnings = Column(JSONB)  # Array of warning objects
    error_message = Column(Text)
    extra_data = Column(JSONB)  # Flexible additional data (renamed from metadata to avoid SQLAlchemy conflict)

    # Audit
    triggered_by = Column(String(100))  # github_actions, manual, api
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<BatchRun {self.batch_type} {self.season_year}W{self.week} {self.status}>"


class DataReadiness(Base):
    """
    Data availability status per NFL week.

    Tracks which data is available for each week to support
    the System Status page and data validation.
    """
    __tablename__ = "data_readiness"

    id = Column(Integer, primary_key=True, index=True)
    season_year = Column(Integer, nullable=False, index=True)
    week = Column(Integer, nullable=False, index=True)
    season_type = Column(String(10), nullable=False, default='reg')

    # Availability flags
    schedule_complete = Column(Boolean, default=False)
    game_logs_available = Column(Boolean, default=False)
    predictions_available = Column(Boolean, default=False)
    draftkings_odds_available = Column(Boolean, default=False)
    fanduel_odds_available = Column(Boolean, default=False)

    # Counts
    games_count = Column(Integer, default=0)
    game_logs_count = Column(Integer, default=0)
    predictions_count = Column(Integer, default=0)
    draftkings_odds_count = Column(Integer, default=0)
    fanduel_odds_count = Column(Integer, default=0)

    # Freshness
    last_updated = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<DataReadiness {self.season_year}W{self.week} ({self.season_type})>"
