from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.utils.nfl_calendar import get_current_nfl_week

router = APIRouter()


@router.post("/fetch-odds")
async def trigger_odds_fetch(
    db: AsyncSession = Depends(get_db)
):
    """Manually trigger sportsbook odds fetch"""
    year, week = get_current_nfl_week()

    # TODO: Implement odds fetch job
    return {
        "status": "triggered",
        "job_type": "odds_fetch",
        "year": year,
        "week": week
    }


@router.post("/run-model")
async def trigger_model_run(
    db: AsyncSession = Depends(get_db)
):
    """Manually trigger model predictions"""
    year, week = get_current_nfl_week()

    # TODO: Implement model run job
    return {
        "status": "triggered",
        "job_type": "model_run",
        "year": year,
        "week": week
    }


@router.post("/sync-results")
async def trigger_results_sync(
    week: int | None = None,
    db: AsyncSession = Depends(get_db)
):
    """Manually trigger game results sync"""
    year, current_week = get_current_nfl_week()
    target_week = week or (current_week - 1)

    # TODO: Implement results sync job
    return {
        "status": "triggered",
        "job_type": "results_sync",
        "year": year,
        "week": target_week
    }


@router.get("/jobs")
async def get_job_history(
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """View recent job execution history"""
    # TODO: Query job_runs table
    return {
        "jobs": []
    }
