"""
TD Model Service

Loads the trained Random Forest model and provides inference functionality.
"""

import joblib
import numpy as np
from pathlib import Path
from typing import Tuple, Optional
import logging

from app.config import settings
from app.ml.feature_engineering import (
    extract_prediction_features,
    extract_features_for_current_season,
    validate_features,
    create_week_1_features
)
from app.utils.odds_conversion import decimal_to_american_odds

logger = logging.getLogger(__name__)


class TDModelService:
    """
    Service for TD prediction model inference.

    Loads the trained scikit-learn Random Forest model and provides
    methods for predicting touchdown probabilities.
    """

    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize model service.

        Args:
            model_path: Path to the pickled model file
        """
        self.model_path = model_path or settings.MODEL_PATH
        self.model = None
        self._load_model()

    def _load_model(self):
        """Load the pickled model from disk"""
        try:
            model_file = Path(self.model_path)
            if not model_file.exists():
                raise FileNotFoundError(f"Model file not found: {self.model_path}")

            self.model = joblib.load(model_file)
            logger.info(f"Successfully loaded model from {self.model_path}")

        except Exception as e:
            logger.error(f"Failed to load model: {str(e)}")
            raise

    def predict_td_probability(self, features: np.ndarray) -> float:
        """
        Predict touchdown probability for a given feature set.

        Args:
            features: Numpy array of shape (1, 11) with model features

        Returns:
            Probability of scoring a TD (float between 0 and 1)

        Raises:
            ValueError: If features are invalid
        """
        if not validate_features(features):
            raise ValueError("Invalid features provided")

        if self.model is None:
            raise RuntimeError("Model not loaded")

        try:
            # Get probability of positive class (TD = 1)
            probability = self.model.predict_proba(features)[:, 1][0]
            return float(probability)

        except Exception as e:
            logger.error(f"Prediction failed: {str(e)}")
            raise

    def predict_td_with_odds(
        self,
        features: np.ndarray
    ) -> Tuple[float, str, float, int]:
        """
        Predict TD probability and convert to American odds.

        Args:
            features: Numpy array of shape (1, 11) with model features

        Returns:
            Tuple of (probability, odds_string, odds_value, favor)
            - probability: float (0-1)
            - odds_string: str (e.g., "+250" or "-150")
            - odds_value: float (e.g., 250.0 or -150.0)
            - favor: int (1 for underdog, -1 for favorite)
        """
        probability = self.predict_td_probability(features)
        odds_string, odds_value, favor = decimal_to_american_odds(probability)

        return probability, odds_string, odds_value, favor

    def predict_from_game_logs(
        self,
        game_logs: list,
        next_week: int,
        season_year: Optional[int] = None
    ) -> Optional[Tuple[float, str, float, int]]:
        """
        Predict TD probability from player's game logs.

        Args:
            game_logs: List of game log dicts
            next_week: Week number to predict
            season_year: Optional season year filter

        Returns:
            Tuple of (probability, odds_string, odds_value, favor) or None if insufficient data
        """
        try:
            # Extract features from game logs
            if season_year:
                features = extract_features_for_current_season(game_logs, season_year, next_week)
            else:
                features = extract_prediction_features(game_logs, next_week)

            if features is None:
                logger.warning("Could not extract features from game logs")
                return None

            # Make prediction
            return self.predict_td_with_odds(features)

        except Exception as e:
            logger.error(f"Prediction from game logs failed: {str(e)}")
            return None

    def predict_week_1(self, week: int = 1) -> Tuple[float, str, float, int]:
        """
        Predict for Week 1 when no historical data exists.

        Uses default features (all zeros except week and is_first_week flag).

        Args:
            week: Week number (usually 1)

        Returns:
            Tuple of (probability, odds_string, odds_value, favor)
        """
        features = create_week_1_features(week)
        return self.predict_td_with_odds(features)


# ============================================================================
# GLOBAL MODEL INSTANCE
# ============================================================================

# Create a singleton instance to avoid reloading model on every request
_model_service: Optional[TDModelService] = None


def get_model_service() -> TDModelService:
    """
    Get the global model service instance.

    Returns:
        TDModelService instance
    """
    global _model_service

    if _model_service is None:
        _model_service = TDModelService()

    return _model_service


def reload_model():
    """
    Force reload of the model from disk.

    Useful if model file is updated during runtime.
    """
    global _model_service
    _model_service = None
    return get_model_service()
