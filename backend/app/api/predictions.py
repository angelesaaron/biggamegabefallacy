from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime
import logging

from app.database import get_db
from app.models.prediction import Prediction
from app.models.player import Player
from app.models.odds import SportsbookOdds
from app.schemas.prediction import PredictionResponse
from app.utils.nfl_calendar import get_current_nfl_week
from app.services.data_service import get_data_service, DataService
from app.services.prediction_service import get_prediction_service
from app.ml.model_service import get_model_service
from app.ml.feature_engineering import extract_prediction_features
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/current")
async def get_current_week_predictions(
    limit: int = Query(100, description="Max number of predictions to return"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all predictions for the current NFL week with player details.

    If no predictions exist for the current week, falls back to the most recent week
    with available predictions and includes metadata to inform the frontend.
    """
    current_year, current_week = get_current_nfl_week()

    result = await db.execute(
        select(
            Prediction.player_id,
            Prediction.season_year,
            Prediction.week,
            Prediction.td_likelihood,
            Prediction.model_odds,
            Prediction.favor,
            Prediction.created_at,
            Player.full_name,
            Player.team_name,
            Player.position,
            Player.jersey_number,
            Player.headshot_url
        )
        .join(Player, Prediction.player_id == Player.player_id)
        .where(Prediction.season_year == current_year)
        .where(Prediction.week == current_week)
        .order_by(Prediction.td_likelihood.desc())
        .limit(limit)
    )
    rows = result.all()

    is_fallback = False
    fallback_year = current_year
    fallback_week = current_week

    # If no predictions for current week, fall back to most recent week with data
    if not rows:
        logger.warning(f"No predictions found for {current_year} Week {current_week}, falling back to most recent week")
        is_fallback = True

        # Find most recent predictions
        fallback_result = await db.execute(
            select(
                Prediction.player_id,
                Prediction.season_year,
                Prediction.week,
                Prediction.td_likelihood,
                Prediction.model_odds,
                Prediction.favor,
                Prediction.created_at,
                Player.full_name,
                Player.team_name,
                Player.position,
                Player.jersey_number,
                Player.headshot_url
            )
            .join(Player, Prediction.player_id == Player.player_id)
            .order_by(Prediction.season_year.desc(), Prediction.week.desc(), Prediction.td_likelihood.desc())
            .limit(limit)
        )
        rows = fallback_result.all()

        if rows:
            fallback_year = rows[0].season_year
            fallback_week = rows[0].week

    # Convert to dict format
    predictions = []
    for row in rows:
        predictions.append({
            "player_id": row.player_id,
            "player_name": row.full_name,
            "team_name": row.team_name,
            "position": row.position,
            "jersey_number": row.jersey_number,
            "headshot_url": row.headshot_url,
            "season_year": row.season_year,
            "week": row.week,
            "td_likelihood": str(row.td_likelihood),
            "model_odds": str(row.model_odds),
            "favor": row.favor,
            "created_at": row.created_at.isoformat() if row.created_at else None
        })

    return {
        "predictions": predictions,
        "metadata": {
            "current_week": current_week,
            "current_year": current_year,
            "showing_week": fallback_week,
            "showing_year": fallback_year,
            "is_fallback": is_fallback
        }
    }


@router.get("/{player_id}", response_model=PredictionResponse | None)
async def get_player_prediction(
    player_id: str,
    week: int | None = Query(None, description="Week number (defaults to current week)"),
    year: int | None = Query(None, description="Season year (defaults to current year)"),
    db: AsyncSession = Depends(get_db)
):
    """Get prediction for a specific player"""
    if not year or not week:
        year, week = get_current_nfl_week()

    result = await db.execute(
        select(Prediction)
        .where(Prediction.player_id == player_id)
        .where(Prediction.season_year == year)
        .where(Prediction.week == week)
    )
    prediction = result.scalar_one_or_none()

    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found for this player/week")

    return prediction


@router.get("/history/{player_id}")
async def get_player_prediction_history(
    player_id: str,
    season: int | None = Query(None, description="Filter by season year"),
    weeks: int = Query(20, description="Number of recent weeks to return"),
    db: AsyncSession = Depends(get_db)
):
    """Get historical predictions for a player"""
    query = select(Prediction).where(Prediction.player_id == player_id)

    if season:
        query = query.where(Prediction.season_year == season)

    query = query.order_by(Prediction.season_year.desc(), Prediction.week.desc()).limit(weeks)

    result = await db.execute(query)
    predictions = result.scalars().all()

    return [
        {
            "player_id": p.player_id,
            "season_year": p.season_year,
            "week": p.week,
            "td_likelihood": float(p.td_likelihood),
            "model_odds": float(p.model_odds),
            "favor": p.favor
        }
        for p in predictions
    ]


@router.post("/generate/{player_id}")
async def generate_prediction(
    player_id: str,
    week: Optional[int] = Query(None, description="Week to predict (defaults to current week)"),
    year: Optional[int] = Query(None, description="Season year (defaults to current year)"),
    save_to_db: bool = Query(True, description="Save prediction to database"),
    update_existing: bool = Query(True, description="Update existing predictions"),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate a fresh TD prediction for a player using the unified prediction service.

    This endpoint uses the same prediction logic as batch generation scripts,
    ensuring consistency across all prediction sources.

    Returns:
        Dict with prediction details including model odds, sportsbook odds, and EV
    """
    if not year or not week:
        year, week = get_current_nfl_week()

    logger.info(f"Generating prediction for player {player_id}, {year} week {week}")

    try:
        # Get player and sportsbook data
        data_service = get_data_service(db)
        player, _, sportsbook_odds = await data_service.get_player_data_for_prediction(
            player_id=player_id,
            next_week=week
        )

        if not player:
            raise HTTPException(
                status_code=404,
                detail=f"Player {player_id} not found. Run roster sync first."
            )

        # Use unified prediction service
        prediction_service = get_prediction_service(db)
        td_prob, odds_val, favor = await prediction_service.generate_prediction(
            player_id=player_id,
            season_year=year,
            week=week,
            save_to_db=save_to_db,
            update_existing=update_existing
        )

        # Format odds string
        odds_str = f"+{int(odds_val)}" if odds_val > 0 else f"{int(odds_val)}"

        logger.info(f"Model prediction: {td_prob:.4f} probability, {odds_str} odds")

        # Calculate expected value if sportsbook odds available
        expected_value = None
        has_edge = False

        if sportsbook_odds:
            # Convert American odds to implied probability
            if sportsbook_odds > 0:
                implied_prob = 100 / (sportsbook_odds + 100)
            else:
                implied_prob = abs(sportsbook_odds) / (abs(sportsbook_odds) + 100)

            # EV = (model_prob * payout) - (1 - model_prob)
            if sportsbook_odds > 0:
                payout = sportsbook_odds / 100
            else:
                payout = 100 / abs(sportsbook_odds)

            expected_value = (td_prob * payout) - (1 - td_prob)
            has_edge = td_prob > implied_prob

            logger.info(f"Sportsbook odds: {sportsbook_odds}, EV: {expected_value:.4f}, Edge: {has_edge}")

        # Build response
        return {
            "player_id": player_id,
            "player_name": player.full_name if player else None,
            "position": player.position if player else None,
            "season_year": year,
            "week": week,
            "td_probability": round(td_prob, 4),
            "model_odds": {
                "american": odds_str,
                "value": odds_val,
                "favor": "underdog" if favor == 1 else "favorite"
            },
            "sportsbook_odds": sportsbook_odds,
            "expected_value": round(expected_value, 4) if expected_value else None,
            "has_edge": has_edge,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate prediction: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate prediction: {str(e)}"
        )
