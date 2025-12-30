"""
Unified Prediction Service

This service provides a single source of truth for generating and storing
TD predictions, used by both the API endpoints and batch generation scripts.
"""
import logging
from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.prediction import Prediction
from app.models.game_log import GameLog
from app.ml.model_service import get_model_service

logger = logging.getLogger(__name__)


class PredictionService:
    """Service for generating and managing TD predictions"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.model_service = get_model_service()

    async def generate_prediction(
        self,
        player_id: str,
        season_year: int,
        week: int,
        save_to_db: bool = True,
        update_existing: bool = True
    ) -> Tuple[float, float, int]:
        """
        Generate a TD prediction for a specific player/week.

        This is the unified prediction generation method used by:
        - API endpoints (/api/predictions/generate/{player_id})
        - Batch generation scripts (generate_historical_predictions.py)
        - Any other prediction generation needs

        Args:
            player_id: Player ID
            season_year: Season year (e.g., 2025)
            week: Week number (1-18)
            save_to_db: Whether to save prediction to database
            update_existing: If True, update existing predictions. If False, skip existing.

        Returns:
            Tuple of (probability, odds_value, favor)

        Raises:
            ValueError: If unable to generate prediction
        """
        logger.info(f"Generating prediction for {player_id}, {season_year} Week {week}")

        try:
            # Get game logs for this player/season up to (but not including) this week
            game_logs = await self._get_game_logs(player_id, season_year, week)

            # Generate prediction using model
            if week == 1 or not game_logs:
                # Week 1 or no historical data: use baseline prediction
                probability, odds_str, odds_value, favor = self.model_service.predict_week_1(week=week)
                logger.info(f"Week 1 baseline prediction: {probability:.4f}")
            else:
                # Week 2+: use trailing data from same season
                result = self.model_service.predict_from_game_logs(
                    game_logs,
                    next_week=week,
                    season_year=season_year
                )

                if result is None:
                    raise ValueError(f"Could not generate prediction from game logs")

                probability, odds_str, odds_value, favor = result
                logger.info(f"Prediction from {len(game_logs)} game logs: {probability:.4f}")

            # Save to database if requested
            if save_to_db:
                await self._save_prediction(
                    player_id=player_id,
                    season_year=season_year,
                    week=week,
                    probability=probability,
                    odds_value=odds_value,
                    favor=favor,
                    update_existing=update_existing
                )

            return probability, odds_value, favor

        except Exception as e:
            logger.error(f"Failed to generate prediction: {e}", exc_info=True)
            raise

    async def _get_game_logs(
        self,
        player_id: str,
        season_year: int,
        week: int
    ) -> List[Dict[str, Any]]:
        """
        Get game logs for a player/season up to (but not including) the target week.

        Args:
            player_id: Player ID
            season_year: Season year
            week: Target week (will fetch weeks 1 through week-1)

        Returns:
            List of game log dicts with required fields for feature extraction
        """
        result = await self.db.execute(
            select(GameLog)
            .where(GameLog.player_id == player_id)
            .where(GameLog.season_year == season_year)
            .where(GameLog.week < week)
            .order_by(GameLog.week)
        )
        logs = result.scalars().all()

        # Convert to dict format for model
        return [
            {
                'season_year': log.season_year,
                'week': log.week,
                'receptions': log.receptions or 0,
                'receiving_yards': log.receiving_yards or 0,
                'receiving_touchdowns': log.receiving_touchdowns or 0,
                'targets': log.targets or 0,
            }
            for log in logs
        ]

    async def _save_prediction(
        self,
        player_id: str,
        season_year: int,
        week: int,
        probability: float,
        odds_value: float,
        favor: int,
        update_existing: bool
    ) -> None:
        """
        Save or update a prediction in the database.

        Args:
            player_id: Player ID
            season_year: Season year
            week: Week number
            probability: TD probability (0-1)
            odds_value: American odds value
            favor: 1 for underdog, -1 for favorite
            update_existing: If True, update existing. If False, skip existing.
        """
        # Check if prediction already exists
        result = await self.db.execute(
            select(Prediction)
            .where(Prediction.player_id == player_id)
            .where(Prediction.season_year == season_year)
            .where(Prediction.week == week)
        )
        existing = result.scalar_one_or_none()

        if existing:
            if update_existing:
                # Update existing prediction
                existing.td_likelihood = probability
                existing.model_odds = odds_value
                existing.favor = favor
                existing.created_at = datetime.utcnow()
                logger.info(f"Updated existing prediction for {player_id} {season_year} W{week}")
            else:
                # Skip existing prediction
                logger.debug(f"Skipped existing prediction for {player_id} {season_year} W{week}")
        else:
            # Create new prediction
            prediction = Prediction(
                player_id=player_id,
                season_year=season_year,
                week=week,
                td_likelihood=probability,
                model_odds=odds_value,
                favor=favor
            )
            self.db.add(prediction)
            logger.info(f"Created new prediction for {player_id} {season_year} W{week}")

    async def generate_current_week_predictions(
        self,
        season_year: int,
        week: int,
        update_existing: bool = True
    ) -> int:
        """
        Generate predictions for all players for a specific week.

        This is used by batch generation scripts to generate predictions
        for the current week across all players.

        Args:
            season_year: Season year
            week: Week number
            update_existing: Whether to update existing predictions

        Returns:
            Number of predictions generated
        """
        logger.info(f"Generating predictions for all players, {season_year} Week {week}")

        # Get all unique players with game logs in this season
        result = await self.db.execute(
            select(GameLog.player_id)
            .where(GameLog.season_year == season_year)
            .distinct()
        )
        player_ids = [row[0] for row in result.all()]

        predictions_generated = 0
        predictions_skipped = 0
        predictions_failed = 0

        for player_id in player_ids:
            try:
                await self.generate_prediction(
                    player_id=player_id,
                    season_year=season_year,
                    week=week,
                    save_to_db=True,
                    update_existing=update_existing
                )
                predictions_generated += 1

            except ValueError as e:
                logger.warning(f"Skipped {player_id}: {str(e)}")
                predictions_skipped += 1

            except Exception as e:
                logger.error(f"Failed to generate prediction for {player_id}: {str(e)}")
                predictions_failed += 1

        await self.db.commit()

        logger.info(
            f"Batch complete: {predictions_generated} generated, "
            f"{predictions_skipped} skipped, {predictions_failed} failed"
        )

        return predictions_generated


def get_prediction_service(db: AsyncSession) -> PredictionService:
    """
    Get a prediction service instance.

    Args:
        db: Database session

    Returns:
        PredictionService instance
    """
    return PredictionService(db)
