from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.utils.nfl_calendar import get_current_nfl_week

router = APIRouter()


@router.get("/last-week")
async def get_last_week_performance(
    db: AsyncSession = Depends(get_db)
):
    """Get performance metrics for last week"""
    year, week = get_current_nfl_week()
    last_week = week - 1 if week > 1 else 1

    # TODO: Implement performance calculation
    return {
        "year": year,
        "week": last_week,
        "win_rate": None,
        "net_balance": None,
        "results": []
    }


@router.get("/{player_id}")
async def get_player_performance(
    player_id: str,
    weeks: int = Query(10, description="Number of recent weeks"),
    db: AsyncSession = Depends(get_db)
):
    """Get historical performance for a specific player"""
    # TODO: Implement player performance history
    return {
        "player_id": player_id,
        "performance": []
    }
