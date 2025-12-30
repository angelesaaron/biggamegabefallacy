from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.utils.nfl_calendar import get_current_nfl_week

router = APIRouter()


@router.get("/current")
async def get_current_value_picks(
    sportsbook: str | None = Query(None, description="Filter by sportsbook"),
    limit: int = Query(30, description="Max picks to return"),
    db: AsyncSession = Depends(get_db)
):
    """Get value picks for the current week"""
    year, week = get_current_nfl_week()

    # TODO: Implement value picks query
    return {
        "year": year,
        "week": week,
        "sportsbook": sportsbook,
        "picks": []
    }


@router.get("/best")
async def get_best_value_picks(
    limit: int = Query(30, description="Max picks to return"),
    db: AsyncSession = Depends(get_db)
):
    """Get best value picks across all sportsbooks"""
    year, week = get_current_nfl_week()

    # TODO: Implement best picks query
    return {
        "year": year,
        "week": week,
        "picks": []
    }
