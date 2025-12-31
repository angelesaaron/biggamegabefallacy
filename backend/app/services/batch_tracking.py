"""
Batch Tracking Service

Utilities for tracking batch process execution and updating data readiness.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert

from app.models.batch_run import BatchRun, DataReadiness
from app.models.schedule import Schedule
from app.models.game_log import GameLog
from app.models.prediction import Prediction
from app.models.odds import SportsbookOdds


class BatchTracker:
    """Context manager for tracking batch process execution"""

    def __init__(
        self,
        db: AsyncSession,
        batch_type: str,
        season_year: int,
        week: int,
        batch_mode: Optional[str] = None,
        season_type: str = 'reg',
        triggered_by: str = 'manual'
    ):
        self.db = db
        self.batch_run = BatchRun(
            batch_type=batch_type,
            batch_mode=batch_mode,
            season_year=season_year,
            week=week,
            season_type=season_type,
            started_at=datetime.utcnow(),
            status='running',
            triggered_by=triggered_by
        )
        self.warnings: List[Dict[str, str]] = []

    async def __aenter__(self):
        """Start tracking batch run"""
        self.db.add(self.batch_run)
        await self.db.commit()
        await self.db.refresh(self.batch_run)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Complete tracking batch run"""
        self.batch_run.completed_at = datetime.utcnow()
        self.batch_run.duration_seconds = int(
            (self.batch_run.completed_at - self.batch_run.started_at).total_seconds()
        )

        if exc_type is not None:
            # Exception occurred
            self.batch_run.status = 'failed'
            self.batch_run.error_message = str(exc_val)
            self.batch_run.errors_encountered = 1
        elif self.warnings:
            # Completed with warnings
            self.batch_run.status = 'partial'
            self.batch_run.warnings = self.warnings
        else:
            # Clean success
            self.batch_run.status = 'success'

        await self.db.commit()

        # Update data readiness after batch completes
        if self.batch_run.status in ['success', 'partial']:
            await update_data_readiness(
                self.db,
                self.batch_run.season_year,
                self.batch_run.week,
                self.batch_run.season_type
            )

        return False  # Don't suppress exceptions

    def add_warning(self, step: str, message: str):
        """Add a warning to the batch run"""
        self.warnings.append({"step": step, "message": message})

    def increment_metric(self, metric: str, count: int = 1):
        """Increment a batch metric"""
        current = getattr(self.batch_run, metric, 0) or 0
        setattr(self.batch_run, metric, current + count)


async def update_data_readiness(
    db: AsyncSession,
    season_year: int,
    week: int,
    season_type: str = 'reg'
):
    """
    Update data readiness indicators for a given week.

    Queries all relevant tables to determine what data is available.
    """
    # Count available data
    games_count = await db.scalar(
        select(func.count(Schedule.id))
        .where(
            Schedule.season_year == season_year,
            Schedule.week == week,
            Schedule.season_type == season_type
        )
    ) or 0

    game_logs_count = await db.scalar(
        select(func.count(GameLog.id))
        .where(
            GameLog.season_year == season_year,
            GameLog.week == week
        )
    ) or 0

    predictions_count = await db.scalar(
        select(func.count(Prediction.id))
        .where(
            Prediction.season_year == season_year,
            Prediction.week == week
        )
    ) or 0

    draftkings_odds_count = await db.scalar(
        select(func.count(SportsbookOdds.id))
        .where(
            SportsbookOdds.season_year == season_year,
            SportsbookOdds.week == week,
            SportsbookOdds.sportsbook == 'draftkings'
        )
    ) or 0

    fanduel_odds_count = await db.scalar(
        select(func.count(SportsbookOdds.id))
        .where(
            SportsbookOdds.season_year == season_year,
            SportsbookOdds.week == week,
            SportsbookOdds.sportsbook == 'fanduel'
        )
    ) or 0

    # Determine completeness thresholds
    # Regular season: 14-16 games, Playoffs: varies
    expected_games = 14 if season_type == 'reg' else 1
    schedule_complete = games_count >= expected_games

    # Upsert data readiness record
    stmt = insert(DataReadiness).values(
        season_year=season_year,
        week=week,
        season_type=season_type,
        schedule_complete=schedule_complete,
        game_logs_available=game_logs_count > 0,
        predictions_available=predictions_count > 0,
        draftkings_odds_available=draftkings_odds_count > 0,
        fanduel_odds_available=fanduel_odds_count > 0,
        games_count=games_count,
        game_logs_count=game_logs_count,
        predictions_count=predictions_count,
        draftkings_odds_count=draftkings_odds_count,
        fanduel_odds_count=fanduel_odds_count,
        last_updated=datetime.utcnow()
    ).on_conflict_do_update(
        index_elements=['season_year', 'week', 'season_type'],
        set_={
            'schedule_complete': schedule_complete,
            'game_logs_available': game_logs_count > 0,
            'predictions_available': predictions_count > 0,
            'draftkings_odds_available': draftkings_odds_count > 0,
            'fanduel_odds_available': fanduel_odds_count > 0,
            'games_count': games_count,
            'game_logs_count': game_logs_count,
            'predictions_count': predictions_count,
            'draftkings_odds_count': draftkings_odds_count,
            'fanduel_odds_count': fanduel_odds_count,
            'last_updated': datetime.utcnow()
        }
    )

    await db.execute(stmt)
    await db.commit()
