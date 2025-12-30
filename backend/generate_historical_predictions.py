#!/usr/bin/env python3
"""
Generate Historical Predictions

This script generates model predictions for all historical weeks where we have game log data.
For each player and week, it uses the trailing game data to make a prediction, just as the
model would have done in real-time.

This allows us to show historical model probabilities in the UI alongside actual game results.

Usage:
    python generate_historical_predictions.py [--season YEAR] [--dry-run]
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime
import argparse

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import select, delete, func
from sqlalchemy.exc import IntegrityError
from app.database import engine, AsyncSessionLocal
from app.models.game_log import GameLog
from app.models.player import Player
from app.models.prediction import Prediction
from app.services.prediction_service import get_prediction_service


async def get_all_player_seasons(session):
    """Get all unique player/season combinations from game logs."""
    result = await session.execute(
        select(
            GameLog.player_id,
            GameLog.season_year,
            func.max(GameLog.week).label('max_week')
        )
        .group_by(GameLog.player_id, GameLog.season_year)
        .order_by(GameLog.season_year, GameLog.player_id)
    )
    return result.all()


async def get_game_logs_for_player_season(session, player_id: str, season: int):
    """Get all game logs for a player in a specific season, sorted by week."""
    result = await session.execute(
        select(GameLog)
        .where(GameLog.player_id == player_id)
        .where(GameLog.season_year == season)
        .order_by(GameLog.week)
    )
    return result.scalars().all()


async def generate_historical_predictions(season_filter: int = None, dry_run: bool = False):
    """
    Generate historical predictions for all players and weeks.

    For each week, we use only the game logs from PRIOR weeks in the SAME season
    to generate the prediction. The feature engineering handles all the lagging
    and averaging correctly.

    Args:
        season_filter: Optional season year to filter to
        dry_run: If True, don't save predictions to database
    """
    print("=" * 80)
    print("HISTORICAL PREDICTION GENERATION")
    print("=" * 80)
    print()

    if dry_run:
        print("🔍 DRY RUN MODE - No predictions will be saved")
        print()

    async with AsyncSessionLocal() as session:
        # Initialize unified prediction service
        prediction_service = get_prediction_service(session)

        # Get all player/season combinations
        print("Fetching player seasons from game logs...")
        player_seasons = await get_all_player_seasons(session)

        if season_filter:
            player_seasons = [ps for ps in player_seasons if ps.season_year == season_filter]
            print(f"Filtered to season {season_filter}")

        print(f"Found {len(player_seasons)} player/season combinations")
        print()

        total_predictions = 0
        total_skipped = 0
        total_errors = 0

        # Process each player/season
        for idx, (player_id, season_year, max_week) in enumerate(player_seasons, 1):
            # Get player name for logging
            player_result = await session.execute(
                select(Player.full_name).where(Player.player_id == player_id)
            )
            player_name = player_result.scalar_one_or_none() or player_id

            print(f"[{idx}/{len(player_seasons)}] {player_name} ({season_year})...")

            # Get all game logs for this player/season (for displaying actual results)
            game_logs = await get_game_logs_for_player_season(session, player_id, season_year)

            if not game_logs:
                print(f"  ⚠️  No game logs found")
                total_skipped += 1
                continue

            predictions_made = 0

            # Generate prediction for each week using unified service
            for week_num in range(1, int(max_week) + 1):
                try:
                    # Use unified prediction service
                    probability, odds_value, favor = await prediction_service.generate_prediction(
                        player_id=player_id,
                        season_year=season_year,
                        week=week_num,
                        save_to_db=not dry_run,  # Don't save in dry-run mode
                        update_existing=False  # Skip existing predictions in batch mode
                    )

                    predictions_made += 1
                    total_predictions += 1

                    # Get actual result for logging
                    actual_game = next((g for g in game_logs if g.week == week_num), None)
                    actual_td = actual_game.receiving_touchdowns if actual_game else 0
                    td_marker = "✓" if actual_td > 0 else "✗"

                    # Format odds string
                    odds_str = f"+{int(odds_value)}" if odds_value > 0 else f"{int(odds_value)}"

                    print(f"  {td_marker}  Week {week_num}: {probability:.1%} ({odds_str}) [Actual: {actual_td} TD]")

                except ValueError as e:
                    # Prediction skipped (e.g., already exists)
                    total_skipped += 1

                except Exception as e:
                    print(f"  ❌ Week {week_num}: Error - {str(e)}")
                    total_errors += 1

            # Commit after each player
            if not dry_run and predictions_made > 0:
                await session.commit()
                print(f"  ✓ Saved {predictions_made} predictions")

            print()

        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Total predictions generated: {total_predictions}")
        print(f"Total skipped (existing/no data): {total_skipped}")
        print(f"Total errors: {total_errors}")
        print()

        if dry_run:
            print("🔍 DRY RUN - No changes were saved to the database")
        else:
            print("✅ Historical predictions saved successfully!")
        print()


async def main():
    parser = argparse.ArgumentParser(description="Generate historical predictions from game logs")
    parser.add_argument(
        '--season',
        type=int,
        help='Filter to specific season year (e.g., 2025)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run without saving to database'
    )

    args = parser.parse_args()

    await generate_historical_predictions(
        season_filter=args.season,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    asyncio.run(main())
