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
from app.services.batch_tracking import BatchTracker
from app.ml.model_service import get_model_service
from app.ml.feature_engineering import extract_prediction_features
from app.utils.nfl_calendar import get_current_nfl_week
from sqlalchemy import select, delete
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def generate_predictions_for_week(season_year: int, week: int, force_regenerate: bool = False):
    """
    Generate predictions for all WR/TE players for a specific week.

    IMMUTABILITY GUARANTEE:
    - By default, skips players who already have predictions
    - Only generates predictions for NEW players or NEW weeks
    - force_regenerate=True is DANGEROUS and requires explicit confirmation

    Args:
        season_year: Season year
        week: Week number
        force_regenerate: If True, DELETE existing predictions (REQUIRES CONFIRMATION)
    """
    print(f"\n🎯 Generating Predictions for {season_year} Week {week}")
    print("=" * 60)

    model_service = get_model_service()

    import os
    triggered_by = 'github_actions' if os.environ.get('CI') else 'manual'

    async with AsyncSessionLocal() as db:
        # SAFETY CHECK: Check if predictions already exist
        from sqlalchemy import func
        existing_count = await db.scalar(
            select(func.count(Prediction.id))
            .where(Prediction.season_year == season_year, Prediction.week == week)
        )

        if existing_count > 0 and not force_regenerate:
            print(f"⚠️  WARNING: {existing_count} predictions already exist for Week {week}")
            print(f"   Predictions are IMMUTABLE. Will only generate for new players.")
            print(f"   To regenerate (DANGEROUS), use --force flag")
            print()

        if existing_count > 0 and force_regenerate:
            print(f"⚠️  DANGER: Deleting {existing_count} existing predictions")
            print(f"   This violates prediction immutability!")
            import os
            if not os.environ.get('CI'):
                response = input("Are you ABSOLUTELY SURE? Type 'DELETE' to confirm: ")
                if response != "DELETE":
                    print("\nCancelled.")
                    return
            await db.execute(
                delete(Prediction)
                .where(Prediction.season_year == season_year, Prediction.week == week)
            )
            await db.commit()
            print(f"Deleted {existing_count} existing predictions\n")

        # Get all active WR/TE players
        result = await db.execute(
            select(Player).where(
                Player.active_status == True,
                Player.position.in_(['WR', 'TE'])
            )
        )
        players = result.scalars().all()

        print(f"Found {len(players)} active WR/TE players")

        # Get existing predictions for this week to skip them
        existing_predictions_result = await db.execute(
            select(Prediction.player_id)
            .where(Prediction.season_year == season_year, Prediction.week == week)
        )
        existing_player_ids = {row[0] for row in existing_predictions_result.all()}

        if existing_player_ids:
            print(f"Skipping {len(existing_player_ids)} players with existing predictions")

        # Filter to only players WITHOUT predictions
        players_to_predict = [p for p in players if p.player_id not in existing_player_ids]

        if not players_to_predict:
            print("\n✅ All players already have predictions. Nothing to do.")
            print()
            return

        print(f"Generating predictions for {len(players_to_predict)} new players\n")

        data_service = get_data_service(db)

        successful = 0
        failed = 0
        week1_baseline = 0
        skipped = len(existing_player_ids)

        # Track batch execution
        async with BatchTracker(
            db=db,
            batch_type='prediction_generation',
            season_year=season_year,
            week=week,
            batch_mode='incremental' if not force_regenerate else 'full',
            season_type='reg',
            triggered_by=triggered_by
        ) as tracker:
            for i, player in enumerate(players_to_predict, 1):
                try:
                    # Get player data
                    _, game_logs, _ = await data_service.get_player_data_for_prediction(
                        player_id=player.player_id,
                        next_week=week
                    )

                    # Generate prediction
                    if not game_logs:
                        # Week 1 baseline
                        td_prob, _, odds_val, favor = model_service.predict_week_1(week=week)
                        week1_baseline += 1
                    else:
                        # Extract features and predict
                        features = extract_prediction_features(game_logs, next_week=week)

                        if features is None:
                            logger.warning(f"Could not extract features for {player.full_name}")
                            failed += 1
                            tracker.increment_metric('errors_encountered')
                            continue

                        td_prob, _, odds_val, favor = model_service.predict_td_with_odds(features)

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
                        try:
                            await db.commit()
                            print(f"[{i}/{len(players_to_predict)}] Generated {successful} predictions...")
                        except Exception as commit_error:
                            # Handle race condition - another process may have created prediction
                            await db.rollback()
                            logger.warning(f"Commit error (likely race condition): {commit_error}")

                except Exception as e:
                    logger.error(f"Failed to generate prediction for {player.full_name}: {str(e)}")
                    await db.rollback()
                    failed += 1
                    tracker.increment_metric('errors_encountered')
                    continue

            # Final commit with error handling
            try:
                await db.commit()
            except Exception as e:
                await db.rollback()
                logger.warning(f"Final commit error: {e}")

            # Update tracker metrics
            tracker.increment_metric('predictions_generated', successful)
            tracker.increment_metric('predictions_skipped', skipped)

            if failed > 0:
                tracker.add_warning('prediction_generation', f'{failed} predictions failed to generate')

        print()
        print("=" * 60)
        print("✅ Prediction Generation Complete!")
        print("=" * 60)
        print()
        print(f"New predictions generated: {successful}")
        print(f"Skipped (already exist): {len(existing_player_ids)}")
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
    parser.add_argument('--force', action='store_true',
                        help='DANGEROUS: Delete existing predictions and regenerate')
    args = parser.parse_args()

    # Get week/year
    if args.week and args.year:
        season_year = args.year
        week = args.week
        season_type = 'reg'  # Assume regular season when manually specified
    else:
        season_year, week, season_type = get_current_nfl_week()

    print("=" * 60)
    print("Batch Prediction Generation")
    print("=" * 60)
    print()
    print(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Target: {season_year} Week {week}")
    print(f"Season Type: {season_type.upper()}")
    print()

    # PLAYOFF PROTECTION: Model is trained on regular season only
    if season_type == 'post':
        print("=" * 60)
        print("⚠️  ERROR: Cannot generate predictions for playoff games")
        print("=" * 60)
        print()
        print("The model is trained on regular season data only.")
        print("Playoff predictions are not supported.")
        print()
        print("Playoffs use different game dynamics:")
        print("  - Elimination pressure")
        print("  - Weather conditions (outdoor stadiums)")
        print("  - Home field advantage shifts")
        print("  - Different usage patterns")
        print()
        sys.exit(1)

    if args.force:
        print("⚠️  FORCE MODE ENABLED - Will delete existing predictions!")
        print()

    print("This will:")
    print(f"  1. Check for existing predictions (immutable)")
    print(f"  2. Generate predictions ONLY for new players")
    print(f"  3. Use game logs from database (0 API calls)")
    print(f"  4. Store predictions in database for fast retrieval")
    if args.force:
        print(f"  5. DELETE existing predictions first (FORCE mode)")
    print()

    # Skip confirmation in CI/CD environments
    import os
    if not os.environ.get('CI'):
        response = input("Continue? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("\nCancelled.")
            return
        print()
    else:
        print("Running in CI/CD mode - auto-confirming...")
        print()

    try:
        await generate_predictions_for_week(season_year, week, force_regenerate=args.force)
    except Exception as e:
        print()
        print(f"❌ ERROR: {str(e)}")
        print()
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
