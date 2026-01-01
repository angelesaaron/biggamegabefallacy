#!/usr/bin/env python3
"""
Debug script to understand why backfill_predictions_for_week might not be generating predictions.
This simulates what happens when backfill runs for a specific player and week.

Usage:
    DATABASE_URL="postgresql://..." python debug_backfill_predictions.py 4426515 15
    (where 4426515 is Puka Nacua's player_id and 15 is week 15)
"""
import asyncio
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.database import AsyncSessionLocal
from app.models.player import Player
from app.models.game_log import GameLog
from app.models.prediction import Prediction
from app.services.data_service import get_data_service
from app.ml.model_service import get_model_service
from app.ml.feature_engineering import extract_prediction_features
from sqlalchemy import select


async def debug_prediction_generation(player_id: str, week: int, season_year: int = 2025):
    """Debug prediction generation for a specific player/week"""
    print("=" * 80)
    print(f"Debug Prediction Generation")
    print(f"Player ID: {player_id}")
    print(f"Week: {week}")
    print(f"Season Year: {season_year}")
    print("=" * 80)
    print()

    async with AsyncSessionLocal() as db:
        # Get player info
        player_result = await db.execute(
            select(Player).where(Player.player_id == player_id)
        )
        player = player_result.scalar_one_or_none()

        if not player:
            print(f"❌ Player {player_id} not found in database")
            return

        print(f"Player: {player.full_name}")
        print(f"Team: {player.team_name}")
        print(f"Position: {player.position}")
        print(f"Active: {player.active_status}")
        print()

        # Check if player would be included in backfill
        if not player.active_status:
            print(f"⚠️  Player is NOT active - would be skipped by backfill")
            return

        if player.position not in ['WR', 'TE']:
            print(f"⚠️  Player position is {player.position} - would be skipped by backfill")
            return

        print("✓ Player meets criteria for prediction generation")
        print()

        # Check if prediction already exists
        existing_pred = await db.execute(
            select(Prediction).where(
                Prediction.player_id == player_id,
                Prediction.season_year == season_year,
                Prediction.week == week
            )
        )
        existing = existing_pred.scalar_one_or_none()

        if existing:
            print(f"⚠️  Prediction already exists for week {week}:")
            print(f"    TD Likelihood: {existing.td_likelihood}")
            print(f"    Model Odds: {existing.model_odds}")
            print(f"    This player would be SKIPPED by backfill")
            print()
        else:
            print(f"✓ No existing prediction for week {week} - would attempt to generate")
            print()

        # Get game logs using the same method as backfill
        print(f"Fetching game logs for prediction...")
        data_service = get_data_service(db)

        _, game_logs, _ = await data_service.get_player_data_for_prediction(
            player_id=player_id,
            next_week=week
        )

        print(f"Game logs returned: {len(game_logs)} logs")
        if game_logs:
            weeks_in_logs = sorted([log['week'] for log in game_logs])
            print(f"Weeks: {weeks_in_logs}")
            print()
            print("Game log details:")
            for log in game_logs:
                print(f"  Week {log['week']}: "
                      f"{log.get('receptions', 0)} rec, "
                      f"{log.get('receiving_yards', 0)} yds, "
                      f"{log.get('receiving_touchdowns', 0)} TD, "
                      f"{log.get('targets', 0)} tgt")
        else:
            print("No game logs found - would use Week 1 baseline prediction")
        print()

        # Try to generate prediction
        model_service = get_model_service()

        try:
            if not game_logs:
                print("Generating Week 1 baseline prediction...")
                td_prob, _, odds_val, favor = model_service.predict_week_1(week=week)
                print(f"✓ Baseline prediction generated:")
                print(f"    TD Probability: {td_prob:.4f}")
                print(f"    Model Odds: {odds_val}")
                print(f"    Favor: {favor}")
            else:
                print("Extracting features from game logs...")
                features = extract_prediction_features(game_logs, next_week=week)

                if features is None:
                    print("❌ Feature extraction returned None")
                    print("   This would cause prediction to FAIL")
                    return

                print(f"✓ Features extracted: shape {features.shape}")
                print(f"   Features: {features}")
                print()

                print("Generating prediction from features...")
                td_prob, _, odds_val, favor = model_service.predict_td_with_odds(features)
                print(f"✓ Prediction generated:")
                print(f"    TD Probability: {td_prob:.4f}")
                print(f"    Model Odds: {odds_val}")
                print(f"    Favor: {favor}")

            print()
            print("=" * 80)
            print("CONCLUSION:")
            if existing:
                print(f"Prediction already exists - backfill would SKIP this player/week")
            else:
                print(f"Backfill SHOULD generate prediction for {player.full_name} week {week}")
                print(f"If it's not appearing in your database, check:")
                print(f"  1. Backfill logs for errors during commit")
                print(f"  2. Database constraints that might be failing")
                print(f"  3. Whether backfill actually ran for this week")
            print("=" * 80)

        except Exception as e:
            print(f"❌ ERROR during prediction generation: {str(e)}")
            print()
            import traceback
            traceback.print_exc()
            print()
            print("This error would cause backfill to skip this player")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: DATABASE_URL='...' python debug_backfill_predictions.py PLAYER_ID WEEK [YEAR]")
        print("Example: DATABASE_URL='postgresql://...' python debug_backfill_predictions.py 4426515 15 2025")
        print()
        print("To find player ID, run: python check_player_simple.py 'Player Name'")
        sys.exit(1)

    player_id = sys.argv[1]
    week = int(sys.argv[2])
    season_year = int(sys.argv[3]) if len(sys.argv) > 3 else 2025

    asyncio.run(debug_prediction_generation(player_id, week, season_year))
