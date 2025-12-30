#!/usr/bin/env python3
"""
Generate Batch Predictions

Generates TD predictions for all WR/TE players for a specific week.
Stores predictions in database for fast retrieval.

Usage:
    python generate_predictions.py [--week WEEK] [--year YEAR]
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
import argparse

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import AsyncSessionLocal
from app.models.player import Player
from app.models.prediction import Prediction
from app.services.data_service import get_data_service
from app.ml.model_service import get_model_service
from app.ml.feature_engineering import extract_prediction_features
from app.utils.nfl_calendar import get_current_nfl_week
from sqlalchemy import select, delete
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def generate_predictions_for_week(season_year: int, week: int):
    """
    Generate predictions for all WR/TE players for a specific week.

    Args:
        season_year: Season year
        week: Week number
    """
    print(f"\n🎯 Generating Predictions for {season_year} Week {week}")
    print("=" * 60)

    model_service = get_model_service()

    async with AsyncSessionLocal() as db:
        # Get all active WR/TE players
        result = await db.execute(
            select(Player).where(
                Player.active_status == True,
                Player.position.in_(['WR', 'TE'])
            )
        )
        players = result.scalars().all()

        print(f"Found {len(players)} active WR/TE players")

        # Delete existing predictions for this week (refresh)
        await db.execute(
            delete(Prediction)
            .where(Prediction.season_year == season_year, Prediction.week == week)
        )
        await db.commit()
        print(f"Cleared old predictions for Week {week}\n")

        data_service = get_data_service(db)

        successful = 0
        failed = 0
        week1_baseline = 0

        for i, player in enumerate(players, 1):
            try:
                # Get player data
                _, game_logs, sportsbook_odds = await data_service.get_player_data_for_prediction(
                    player_id=player.player_id,
                    next_week=week
                )

                # Generate prediction
                if not game_logs:
                    # Week 1 baseline
                    td_prob, odds_str, odds_val, favor = model_service.predict_week_1(week=week)
                    week1_baseline += 1
                else:
                    # Extract features and predict
                    features = extract_prediction_features(game_logs, next_week=week)

                    if features is None:
                        logger.warning(f"Could not extract features for {player.full_name}")
                        failed += 1
                        continue

                    td_prob, odds_str, odds_val, favor = model_service.predict_td_with_odds(features)

                # Save prediction to database
                prediction = Prediction(
                    player_id=player.player_id,
                    season_year=season_year,
                    week=week,
                    td_likelihood=td_prob,
                    model_odds=odds_val,
                    favor=favor,
                    created_at=datetime.utcnow()
                )
                db.add(prediction)

                successful += 1

                if i % 50 == 0:
                    await db.commit()
                    print(f"[{i}/{len(players)}] Generated {successful} predictions...")

            except Exception as e:
                logger.error(f"Failed to generate prediction for {player.full_name}: {str(e)}")
                failed += 1
                continue

        # Final commit
        await db.commit()

        print()
        print("=" * 60)
        print("✅ Prediction Generation Complete!")
        print("=" * 60)
        print()
        print(f"Successful predictions: {successful}")
        print(f"Week 1 baseline predictions: {week1_baseline}")
        print(f"Failed predictions: {failed}")
        print()
        print(f"Predictions ready for {season_year} Week {week}")
        print()


async def main():
    """Run batch prediction generation"""
    parser = argparse.ArgumentParser(description='Generate batch predictions for NFL players')
    parser.add_argument('--week', type=int, help='Week number (default: current week)')
    parser.add_argument('--year', type=int, help='Season year (default: current year)')
    args = parser.parse_args()

    # Get week/year
    if args.week and args.year:
        season_year = args.year
        week = args.week
    else:
        season_year, week = get_current_nfl_week()

    print("=" * 60)
    print("Batch Prediction Generation")
    print("=" * 60)
    print()
    print(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Target: {season_year} Week {week}")
    print()
    print("This will:")
    print(f"  1. Generate predictions for all WR/TE players")
    print(f"  2. Use game logs from database (0 API calls)")
    print(f"  3. Use sportsbook odds from database")
    print(f"  4. Store predictions in database for fast retrieval")
    print()

    response = input("Continue? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("\nCancelled.")
        return

    try:
        await generate_predictions_for_week(season_year, week)
    except Exception as e:
        print()
        print(f"❌ ERROR: {str(e)}")
        print()
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
