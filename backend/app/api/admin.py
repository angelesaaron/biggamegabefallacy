"""
Admin API Endpoints

System status, batch run history, and data readiness indicators.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.database import get_db
from app.models.batch_run import BatchRun, DataReadiness
from app.utils.nfl_calendar import get_current_nfl_week

router = APIRouter()


@router.get("/batch-runs/latest")
async def get_latest_batch_run(
    batch_type: Optional[str] = Query(None, description="Filter by batch type"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the most recent batch run.

    Optionally filter by batch_type: 'weekly_update', 'prediction_generation', 'roster_refresh'
    """
    query = select(BatchRun).order_by(BatchRun.started_at.desc()).limit(1)

    if batch_type:
        query = query.where(BatchRun.batch_type == batch_type)

    result = await db.execute(query)
    latest = result.scalar_one_or_none()

    if not latest:
        return {"batch_run": None}

    return {
        "batch_run": {
            "id": latest.id,
            "batch_type": latest.batch_type,
            "batch_mode": latest.batch_mode,
            "season_year": latest.season_year,
            "week": latest.week,
            "season_type": latest.season_type,
            "started_at": latest.started_at.isoformat() if latest.started_at else None,
            "completed_at": latest.completed_at.isoformat() if latest.completed_at else None,
            "duration_seconds": latest.duration_seconds,
            "status": latest.status,
            "api_calls_made": latest.api_calls_made,
            "games_processed": latest.games_processed,
            "game_logs_added": latest.game_logs_added,
            "predictions_generated": latest.predictions_generated,
            "predictions_skipped": latest.predictions_skipped,
            "odds_synced": latest.odds_synced,
            "errors_encountered": latest.errors_encountered,
            "warnings": latest.warnings,
            "error_message": latest.error_message,
            "triggered_by": latest.triggered_by
        }
    }


@router.get("/batch-runs/history")
async def get_batch_run_history(
    limit: int = Query(10, description="Number of recent runs to return"),
    batch_type: Optional[str] = Query(None, description="Filter by batch type"),
    db: AsyncSession = Depends(get_db)
):
    """Get recent batch run history"""
    query = select(BatchRun).order_by(BatchRun.started_at.desc()).limit(limit)

    if batch_type:
        query = query.where(BatchRun.batch_type == batch_type)

    result = await db.execute(query)
    runs = result.scalars().all()

    return {
        "batch_runs": [
            {
                "id": run.id,
                "batch_type": run.batch_type,
                "batch_mode": run.batch_mode,
                "season_year": run.season_year,
                "week": run.week,
                "season_type": run.season_type,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "duration_seconds": run.duration_seconds,
                "status": run.status,
                "api_calls_made": run.api_calls_made,
                "games_processed": run.games_processed,
                "game_logs_added": run.game_logs_added,
                "predictions_generated": run.predictions_generated,
                "predictions_skipped": run.predictions_skipped,
                "odds_synced": run.odds_synced,
                "errors_encountered": run.errors_encountered,
                "warnings": run.warnings,
                "triggered_by": run.triggered_by
            }
            for run in runs
        ],
        "total": len(runs)
    }


@router.get("/data-readiness/current")
async def get_current_data_readiness(
    db: AsyncSession = Depends(get_db)
):
    """Get data readiness for current NFL week"""
    year, week, season_type = get_current_nfl_week()

    result = await db.execute(
        select(DataReadiness)
        .where(
            DataReadiness.season_year == year,
            DataReadiness.week == week,
            DataReadiness.season_type == season_type
        )
    )
    readiness = result.scalar_one_or_none()

    if not readiness:
        return {
            "data_readiness": None,
            "current_week": {"year": year, "week": week, "season_type": season_type}
        }

    return {
        "data_readiness": {
            "season_year": readiness.season_year,
            "week": readiness.week,
            "season_type": readiness.season_type,
            "schedule_complete": readiness.schedule_complete,
            "game_logs_available": readiness.game_logs_available,
            "predictions_available": readiness.predictions_available,
            "draftkings_odds_available": readiness.draftkings_odds_available,
            "fanduel_odds_available": readiness.fanduel_odds_available,
            "games_count": readiness.games_count,
            "game_logs_count": readiness.game_logs_count,
            "predictions_count": readiness.predictions_count,
            "draftkings_odds_count": readiness.draftkings_odds_count,
            "fanduel_odds_count": readiness.fanduel_odds_count,
            "last_updated": readiness.last_updated.isoformat() if readiness.last_updated else None
        },
        "current_week": {"year": year, "week": week, "season_type": season_type}
    }


@router.get("/data-readiness/{year}/{week}")
async def get_week_data_readiness(
    year: int,
    week: int,
    season_type: str = Query('reg', description="Season type: reg or post"),
    db: AsyncSession = Depends(get_db)
):
    """Get data readiness for a specific week"""
    result = await db.execute(
        select(DataReadiness)
        .where(
            DataReadiness.season_year == year,
            DataReadiness.week == week,
            DataReadiness.season_type == season_type
        )
    )
    readiness = result.scalar_one_or_none()

    if not readiness:
        return {"data_readiness": None}

    return {
        "data_readiness": {
            "season_year": readiness.season_year,
            "week": readiness.week,
            "season_type": readiness.season_type,
            "schedule_complete": readiness.schedule_complete,
            "game_logs_available": readiness.game_logs_available,
            "predictions_available": readiness.predictions_available,
            "draftkings_odds_available": readiness.draftkings_odds_available,
            "fanduel_odds_available": readiness.fanduel_odds_available,
            "games_count": readiness.games_count,
            "game_logs_count": readiness.game_logs_count,
            "predictions_count": readiness.predictions_count,
            "draftkings_odds_count": readiness.draftkings_odds_count,
            "fanduel_odds_count": readiness.fanduel_odds_count,
            "last_updated": readiness.last_updated.isoformat() if readiness.last_updated else None
        }
    }


@router.get("/health/summary")
async def get_system_health_summary(
    db: AsyncSession = Depends(get_db)
):
    """
    Get overall system health summary.

    Combines latest batch run status with current week data readiness.
    """
    year, week, season_type = get_current_nfl_week()

    # Get latest batch run
    latest_run_result = await db.execute(
        select(BatchRun).order_by(BatchRun.started_at.desc()).limit(1)
    )
    latest_run = latest_run_result.scalar_one_or_none()

    # Get current week readiness
    readiness_result = await db.execute(
        select(DataReadiness)
        .where(
            DataReadiness.season_year == year,
            DataReadiness.week == week,
            DataReadiness.season_type == season_type
        )
    )
    readiness = readiness_result.scalar_one_or_none()

    # Calculate health score
    health_score = "unknown"
    if readiness:
        core_data_ready = (
            readiness.schedule_complete and
            readiness.predictions_available
        )
        odds_ready = (
            readiness.draftkings_odds_available or
            readiness.fanduel_odds_available
        )

        if core_data_ready and odds_ready:
            health_score = "healthy"
        elif core_data_ready:
            health_score = "partial"
        else:
            health_score = "incomplete"

    return {
        "current_week": {
            "year": year,
            "week": week,
            "season_type": season_type
        },
        "health_score": health_score,
        "latest_batch": {
            "type": latest_run.batch_type if latest_run else None,
            "status": latest_run.status if latest_run else None,
            "started_at": latest_run.started_at.isoformat() if latest_run and latest_run.started_at else None,
            "duration_seconds": latest_run.duration_seconds if latest_run else None
        } if latest_run else None,
        "data_readiness": {
            "schedule": readiness.schedule_complete if readiness else False,
            "predictions": readiness.predictions_available if readiness else False,
            "odds": (readiness.draftkings_odds_available or readiness.fanduel_odds_available) if readiness else False,
            "games_count": readiness.games_count if readiness else 0,
            "predictions_count": readiness.predictions_count if readiness else 0
        } if readiness else None
    }
