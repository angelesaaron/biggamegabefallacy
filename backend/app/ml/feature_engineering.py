"""
Feature Engineering for TD Prediction Model

Based on the Jupyter notebook (3-TouchdownModel.ipynb), this module
extracts the 11 features required by the Random Forest model.

Features (in order):
1. week
2. lag_yds (previous game receiving yards)
3. cumulative_yards_per_game
4. cumulative_receptions_per_game
5. cumulative_targets_per_game
6. avg_receiving_yards_last_3
7. avg_receptions_last_3
8. avg_targets_last_3
9. yards_per_reception
10. td_rate_per_target
11. is_first_week
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def calculate_lagged_features(game_logs: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate lagged and rolling features for TD prediction.

    This function expects a DataFrame with game logs sorted by season and week.

    Args:
        game_logs: DataFrame with columns:
            - season_year
            - week
            - receptions
            - receiving_yards
            - receiving_touchdowns
            - targets

    Returns:
        DataFrame with added feature columns
    """
    # Ensure data is sorted
    df = game_logs.sort_values(by=['season_year', 'week']).reset_index(drop=True)

    # Calculate weeks played in current season
    df['weeks_played'] = df.groupby('season_year').cumcount() + 1

    # ============================================================================
    # CUMULATIVE FEATURES (Lagged by 1 week)
    # ============================================================================

    # Cumulative receiving yards
    df['cumulative_receiving_yards'] = (
        df.groupby('season_year')['receiving_yards']
        .cumsum()
        .shift(1)
    )
    df['cumulative_yards_per_game'] = (
        df['cumulative_receiving_yards'] / (df['weeks_played'] - 1)
    )

    # Cumulative receptions
    df['cumulative_receptions'] = (
        df.groupby('season_year')['receptions']
        .cumsum()
        .shift(1)
    )
    df['cumulative_receptions_per_game'] = (
        df['cumulative_receptions'] / (df['weeks_played'] - 1)
    )

    # Cumulative touchdowns
    df['cumulative_receiving_touchdowns'] = (
        df.groupby('season_year')['receiving_touchdowns']
        .cumsum()
        .shift(1)
    )
    df['cumulative_tds_per_game'] = (
        df['cumulative_receiving_touchdowns'] / (df['weeks_played'] - 1)
    )

    # Cumulative targets
    df['cumulative_targets'] = (
        df.groupby('season_year')['targets']
        .cumsum()
        .shift(1)
    )
    df['cumulative_targets_per_game'] = (
        df['cumulative_targets'] / (df['weeks_played'] - 1)
    )

    # ============================================================================
    # ROLLING 3-GAME AVERAGES (Lagged by 1 week)
    # ============================================================================

    df['avg_receiving_yards_last_3'] = (
        df.groupby('season_year')['receiving_yards']
        .rolling(window=3, min_periods=1)
        .mean()
        .shift(1)
        .reset_index(level=0, drop=True)
    )

    df['avg_receptions_last_3'] = (
        df.groupby('season_year')['receptions']
        .rolling(window=3, min_periods=1)
        .mean()
        .shift(1)
        .reset_index(level=0, drop=True)
    )

    df['avg_targets_last_3'] = (
        df.groupby('season_year')['targets']
        .rolling(window=3, min_periods=1)
        .mean()
        .shift(1)
        .reset_index(level=0, drop=True)
    )

    # ============================================================================
    # EFFICIENCY METRICS (Lagged by 1 week)
    # ============================================================================

    # Yards per reception
    df['yards_per_reception'] = (
        (df['receiving_yards'] / df['receptions'])
        .shift(1)
        .replace([np.inf, -np.inf], 0)
    )

    # TD rate per target
    df['td_rate_per_target'] = (
        (df['cumulative_receiving_touchdowns'] / df['cumulative_targets'])
        .shift(1)
        .replace([np.inf, -np.inf], 0)
    )

    # ============================================================================
    # BINARY FLAGS
    # ============================================================================

    # Is this the first week of the season?
    df['is_first_week'] = (df['weeks_played'] == 1).astype(int)

    # Lag yards (previous game yards)
    df['lag_yds'] = df['receiving_yards'].shift(1)

    # Fill NaN values with 0 (for first games)
    df = df.fillna(0)

    return df


def extract_prediction_features(
    game_logs: List[Dict[str, Any]],
    next_week: int
) -> Optional[np.ndarray]:
    """
    Extract features for next week prediction from historical game logs.

    Args:
        game_logs: List of game log dicts (must be sorted by date)
        next_week: The week number to predict

    Returns:
        Numpy array with 11 features, or None if insufficient data
    """
    if not game_logs:
        logger.warning("No game logs provided for feature extraction")
        return None

    # Convert to DataFrame
    df = pd.DataFrame(game_logs)

    # Validate required columns
    required_cols = ['season_year', 'week', 'receptions', 'receiving_yards', 'receiving_touchdowns', 'targets']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        logger.error(f"Missing required columns: {missing_cols}")
        return None

    # Calculate lagged features
    df = calculate_lagged_features(df)

    # Get the most recent game's features (these become the inputs for next week)
    latest_game = df.iloc[-1]

    # Check if we have the first week of a new season
    is_first_week = 1 if latest_game['weeks_played'] == 0 or pd.isna(latest_game['lag_yds']) else 0

    # Extract the 11 features in the correct order
    features = [
        next_week,                                              # 1. week
        float(latest_game.get('lag_yds', 0)),                  # 2. lag_yds
        float(latest_game.get('cumulative_yards_per_game', 0)), # 3. cumulative_yards_per_game
        float(latest_game.get('cumulative_receptions_per_game', 0)), # 4. cumulative_receptions_per_game
        float(latest_game.get('cumulative_targets_per_game', 0)), # 5. cumulative_targets_per_game
        float(latest_game.get('avg_receiving_yards_last_3', 0)), # 6. avg_receiving_yards_last_3
        float(latest_game.get('avg_receptions_last_3', 0)),     # 7. avg_receptions_last_3
        float(latest_game.get('avg_targets_last_3', 0)),        # 8. avg_targets_last_3
        float(latest_game.get('yards_per_reception', 0)),       # 9. yards_per_reception
        float(latest_game.get('td_rate_per_target', 0)),        # 10. td_rate_per_target
        is_first_week,                                          # 11. is_first_week
    ]

    # Convert to numpy array with shape (1, 11) for sklearn
    return np.array([features])


def extract_features_for_current_season(
    game_logs: List[Dict[str, Any]],
    current_year: int,
    next_week: int
) -> Optional[np.ndarray]:
    """
    Extract features for prediction, filtering to current season only.

    Args:
        game_logs: List of all game logs for player (multi-season)
        current_year: Current NFL season year
        next_week: Week to predict

    Returns:
        Feature array or None
    """
    # Filter to current season
    current_season_logs = [
        log for log in game_logs
        if log.get('season_year') == current_year and log.get('week', 0) < next_week
    ]

    if not current_season_logs:
        logger.warning(f"No game logs found for season {current_year}")
        # If it's week 1, return default features
        if next_week == 1:
            return create_week_1_features(next_week)
        return None

    return extract_prediction_features(current_season_logs, next_week)


def create_week_1_features(week: int = 1) -> np.ndarray:
    """
    Create feature array for Week 1 (no historical data).

    Args:
        week: Week number (usually 1)

    Returns:
        Feature array with all zeros except week and is_first_week flag
    """
    features = [
        week,   # 1. week
        0.0,    # 2. lag_yds
        0.0,    # 3. cumulative_yards_per_game
        0.0,    # 4. cumulative_receptions_per_game
        0.0,    # 5. cumulative_targets_per_game
        0.0,    # 6. avg_receiving_yards_last_3
        0.0,    # 7. avg_receptions_last_3
        0.0,    # 8. avg_targets_last_3
        0.0,    # 9. yards_per_reception
        0.0,    # 10. td_rate_per_target
        1,      # 11. is_first_week
    ]

    return np.array([features])


# ============================================================================
# VALIDATION
# ============================================================================

def validate_features(features: np.ndarray) -> bool:
    """
    Validate that feature array has correct shape and no NaN/Inf values.

    Args:
        features: Feature array

    Returns:
        True if valid, False otherwise
    """
    if features is None:
        return False

    if features.shape != (1, 11):
        logger.error(f"Invalid feature shape: {features.shape}, expected (1, 11)")
        return False

    if np.isnan(features).any():
        logger.error("Features contain NaN values")
        return False

    if np.isinf(features).any():
        logger.error("Features contain Inf values")
        return False

    return True
