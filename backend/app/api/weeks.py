"""
Weeks API - Get available weeks with complete data
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select, distinct, func
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any
from app.database import get_db
from app.models.prediction import Prediction
from app.models.odds import SportsbookOdds
from app.models.schedule import Schedule

router = APIRouter(prefix="/api/weeks", tags=["weeks"])


@router.get("/available")
async def get_available_weeks(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Get list of weeks that have complete data (predictions + odds).

    Returns weeks in descending order (most recent first).
    """
    # Get weeks that have predictions
    pred_weeks_result = await db.execute(
        select(
            Prediction.season_year,
            Prediction.week,
            func.count(Prediction.id).label('prediction_count')
        )
        .group_by(Prediction.season_year, Prediction.week)
        .order_by(Prediction.season_year.desc(), Prediction.week.desc())
    )
    pred_weeks = {(row.season_year, row.week): row.prediction_count for row in pred_weeks_result}

    # Get weeks that have odds
    odds_weeks_result = await db.execute(
        select(
            SportsbookOdds.season_year,
            SportsbookOdds.week,
            func.count(SportsbookOdds.id).label('odds_count')
        )
        .group_by(SportsbookOdds.season_year, SportsbookOdds.week)
        .order_by(SportsbookOdds.season_year.desc(), SportsbookOdds.week.desc())
    )
    odds_weeks = {(row.season_year, row.week): row.odds_count for row in odds_weeks_result}

    # Get all weeks from schedule (including future weeks without odds)
    schedule_weeks_result = await db.execute(
        select(
            Schedule.season_year,
            Schedule.week,
            func.count(Schedule.id).label('game_count')
        )
        .group_by(Schedule.season_year, Schedule.week)
        .order_by(Schedule.season_year.desc(), Schedule.week.desc())
    )
    schedule_weeks = {(row.season_year, row.week): row.game_count for row in schedule_weeks_result}

    # Build complete list - include all scheduled weeks
    weeks_list = []
    for (year, week), game_count in schedule_weeks.items():
        has_predictions = (year, week) in pred_weeks
        has_odds = (year, week) in odds_weeks

        weeks_list.append({
            "season_year": year,
            "week": week,
            "label": f"Week {week}",
            "has_odds": has_odds,
            "has_predictions": has_predictions,
            "is_complete": has_odds and has_predictions,  # Both odds and predictions
            "game_count": game_count,
            "odds_count": odds_weeks.get((year, week), 0),
            "prediction_count": pred_weeks.get((year, week), 0)
        })

    # Sort by season year and week (descending)
    weeks_list.sort(key=lambda x: (x['season_year'], x['week']), reverse=True)

    # Find current week (first complete week)
    current_week = next((w for w in weeks_list if w['is_complete']), None)

    return {
        "weeks": weeks_list,
        "current_week": current_week
    }
