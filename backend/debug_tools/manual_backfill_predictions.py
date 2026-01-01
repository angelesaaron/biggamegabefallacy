#!/usr/bin/env python3
"""
Manual script to backfill missing predictions for specific players/weeks.
Useful when backfill_complete.py runs but doesn't generate predictions for some reason.

Usage:
    # Backfill all missing predictions for all players, weeks 1-17
    python manual_backfill_predictions.py --all

    # Backfill specific weeks
    python manual_backfill_predictions.py --start-week 6 --end-week 16

    # Dry run to see what would be backfilled
    python manual_backfill_predictions.py --all --dry-run
"""
import asyncio
import sys
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from app.database import AsyncSessionLocal
from app.models.player import Player
from app.models.game_log import GameLog
from app.models.prediction import Prediction
from app.services.data_service import get_data_service
from app.ml.model_service import get_model_service
from app.ml.feature_engineering import extract_prediction_features
from sqlalchemy import select
import logging

logging.basicConfig(level=logging.WARNING)  # Reduce SQL logging


async def backfill_missing_predictions(start_week: int, end_week: int, season_year: int, dry_run: bool = False):
    """Backfill missing predictions for all active WR/TE players"""

    async with AsyncSessionLocal() as db:
        # Get all active WR/TE players
        result = await db.execute(
            select(Player).where(
                Player.active_status == True,
                Player.position.in_(['WR', 'TE'])
            ).order_by(Player.full_name)
        )
        players = result.scalars().all()

        print(f"Found {len(players)} active WR/TE players")
        print(f"Checking weeks {start_week}-{end_week} for season {season_year}")
        print()

        model_service = get_model_service()
        data_service = get_data_service(db)

        total_missing = 0
        total_generated = 0
        total_errors = 0

        for week in range(start_week, end_week + 1):
            print(f"Week {week}:", end=" ", flush=True)

            # Get existing predictions for this week
            existing_result = await db.execute(
                select(Prediction.player_id).where(
                    Prediction.season_year == season_year,
                    Prediction.week == week
                )
            )
            existing_player_ids = {row[0] for row in existing_result.all()}

            # Find players without predictions
            players_missing = [p for p in players if p.player_id not in existing_player_ids]

            if not players_missing:
                print(f"✓ All {len(players)} players have predictions")
                continue

            print(f"{len(players_missing)} missing predictions", end="")

            if dry_run:
                print(" (dry run - not generating)")
                total_missing += len(players_missing)
                continue

            print(" - generating...", end="", flush=True)

            generated = 0
            errors = 0

            for player in players_missing:
                try:
                    # Get game logs
                    _, game_logs, _ = await data_service.get_player_data_for_prediction(
                        player_id=player.player_id,
                        next_week=week
                    )

                    # Generate prediction
                    if not game_logs:
                        td_prob, _, odds_val, favor = model_service.predict_week_1(week=week)
                    else:
                        features = extract_prediction_features(game_logs, next_week=week)
                        if features is None:
                            errors += 1
                            continue
                        td_prob, _, odds_val, favor = model_service.predict_td_with_odds(features)

                    # Save prediction
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
                    generated += 1

                    # Commit every 50 predictions
                    if generated % 50 == 0:
                        await db.commit()

                except Exception as e:
                    print(f"\n  ❌ Error for {player.full_name}: {str(e)}")
                    await db.rollback()
                    errors += 1

            # Final commit for this week
            try:
                await db.commit()
                print(f" ✓ Generated {generated}", end="")
                if errors > 0:
                    print(f", {errors} errors", end="")
                print()
            except Exception as e:
                await db.rollback()
                print(f" ❌ Commit failed: {str(e)}")

            total_generated += generated
            total_errors += errors
            total_missing += len(players_missing)

        print()
        print("=" * 60)
        print("Summary:")
        print(f"  Total missing predictions found: {total_missing}")
        if not dry_run:
            print(f"  Successfully generated: {total_generated}")
            if total_errors > 0:
                print(f"  Errors: {total_errors}")
        print("=" * 60)


async def main():
    parser = argparse.ArgumentParser(description='Manually backfill missing predictions')
    parser.add_argument('--all', action='store_true', help='Backfill all weeks (1-17)')
    parser.add_argument('--start-week', type=int, help='Start week')
    parser.add_argument('--end-week', type=int, help='End week')
    parser.add_argument('--year', type=int, default=2025, help='Season year (default: 2025)')
    parser.add_argument('--dry-run', action='store_true', help='Just show what would be backfilled')
    args = parser.parse_args()

    if args.all:
        start_week = 1
        end_week = 17
    elif args.start_week and args.end_week:
        start_week = args.start_week
        end_week = args.end_week
    elif args.start_week:
        start_week = args.start_week
        end_week = 17
    else:
        print("Error: Must specify --all or --start-week/--end-week")
        parser.print_help()
        sys.exit(1)

    print("=" * 60)
    print("Manual Prediction Backfill")
    print("=" * 60)
    print()

    if args.dry_run:
        print("DRY RUN MODE - No changes will be made")
        print()

    await backfill_missing_predictions(start_week, end_week, args.year, args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())
