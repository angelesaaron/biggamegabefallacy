#!/usr/bin/env python3
"""
Complete Historical Backfill

Efficiently backfills ALL data (game logs, predictions, odds) for specified weeks.
Designed to run after refreshing rosters to fill in historical data for new players.

Usage:
    # Backfill last 5 weeks (most common after roster refresh)
    python backfill_complete.py --weeks 5

    # Backfill specific week
    python backfill_complete.py --week 10 --year 2025

    # Backfill week range
    python backfill_complete.py --start-week 10 --end-week 15 --year 2025

Efficiency:
- Game logs: ~16 API calls per week (box score per game)
- Odds: ~16 API calls per week (odds per game)
- Predictions: 0 API calls (uses database)
- Total: ~32 API calls per week (vs 500+ with old method)
"""
import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime
import argparse

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import AsyncSessionLocal
from app.models.schedule import Schedule
from app.models.game_log import GameLog
from app.models.player import Player
from app.models.prediction import Prediction
from app.models.odds import SportsbookOdds
from app.utils.tank01_client import Tank01Client
from app.utils.nfl_calendar import get_current_nfl_week
from app.services.batch_tracking import BatchTracker
from app.ml.model_service import get_model_service
from app.ml.feature_engineering import extract_prediction_features
from app.services.data_service import get_data_service
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def backfill_game_logs_for_week(db, client: Tank01Client, season_year: int, week: int, tracker):
    """
    Backfill game logs for a week using box score method (efficient).
    Only adds logs that don't already exist.
    """
    tracker.log_output(f"[Game Logs] Week {week}: Fetching box scores...")

    # Get all games for this week
    result = await db.execute(
        select(Schedule)
        .where(Schedule.season_year == season_year, Schedule.week == week)
        .order_by(Schedule.game_date)
    )
    games = result.scalars().all()

    if not games:
        tracker.log_output(f"[Game Logs] Week {week}: No games found")
        return 0

    # Get all valid player IDs
    player_result = await db.execute(select(Player.player_id))
    valid_player_ids = {row[0] for row in player_result.all()}

    new_logs = 0
    skipped_existing = 0

    for game in games:
        try:
            # Fetch box score
            game_logs = await client.get_game_logs_from_box_score(
                game_id=game.game_id,
                season_year=season_year,
                week=week
            )

            if not game_logs:
                continue

            for log in game_logs:
                player_id = log["player_id"]

                # Skip if player not in database
                if player_id not in valid_player_ids:
                    continue

                # Check if log already exists
                existing = await db.scalar(
                    select(func.count(GameLog.id))
                    .where(
                        GameLog.player_id == player_id,
                        GameLog.game_id == game.game_id
                    )
                )

                if existing > 0:
                    skipped_existing += 1
                    continue

                # Add new game log
                game_log = GameLog(
                    player_id=log["player_id"],
                    game_id=log["game_id"],
                    season_year=log["season_year"],
                    week=log["week"],
                    team=log["team"],
                    team_id=log["team_id"],
                    receptions=log["receptions"],
                    receiving_yards=log["receiving_yards"],
                    receiving_touchdowns=log["receiving_touchdowns"],
                    targets=log["targets"],
                    long_reception=log["long_reception"],
                    yards_per_reception=log["yards_per_reception"]
                )
                db.add(game_log)
                new_logs += 1

            await db.commit()

        except Exception as e:
            tracker.log_output(f"[Game Logs] Week {week}: Error on game {game.game_id}: {str(e)}")
            await db.rollback()
            continue

    tracker.log_output(f"[Game Logs] Week {week}: Added {new_logs} logs, skipped {skipped_existing} existing")
    return new_logs


async def backfill_predictions_for_week(db, season_year: int, week: int, tracker):
    """
    Generate predictions for players who don't have predictions for this week.
    Uses database game logs (0 API calls).
    """
    tracker.log_output(f"[Predictions] Week {week}: Generating predictions...")

    model_service = get_model_service()
    data_service = get_data_service(db)

    # Get all active WR/TE players
    result = await db.execute(
        select(Player).where(
            Player.active_status == True,
            Player.position.in_(['WR', 'TE'])
        )
    )
    players = result.scalars().all()

    # Get existing predictions for this week
    existing_result = await db.execute(
        select(Prediction.player_id)
        .where(Prediction.season_year == season_year, Prediction.week == week)
    )
    existing_player_ids = {row[0] for row in existing_result.all()}

    # Filter to only players WITHOUT predictions
    players_to_predict = [p for p in players if p.player_id not in existing_player_ids]

    if not players_to_predict:
        tracker.log_output(f"[Predictions] Week {week}: All players already have predictions")
        return 0

    generated = 0
    failed = 0

    for player in players_to_predict:
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
            else:
                # Extract features and predict
                features = extract_prediction_features(game_logs, next_week=week)
                if features is None:
                    failed += 1
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

            if generated % 50 == 0:
                await db.commit()

        except Exception as e:
            logger.error(f"Failed to generate prediction for {player.full_name}: {str(e)}")
            await db.rollback()
            failed += 1
            continue

    # Final commit
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.warning(f"Final commit error: {e}")

    tracker.log_output(f"[Predictions] Week {week}: Generated {generated}, failed {failed}, skipped {len(existing_player_ids)} existing")
    return generated


async def backfill_odds_for_week(db, client: Tank01Client, season_year: int, week: int, tracker):
    """
    Backfill odds for a week.
    Uses UPSERT to update existing or insert new records.
    """
    tracker.log_output(f"[Odds] Week {week}: Fetching odds...")

    # Get all games for this week
    result = await db.execute(
        select(Schedule)
        .where(Schedule.season_year == season_year, Schedule.week == week)
        .order_by(Schedule.game_date)
    )
    games = result.scalars().all()

    if not games:
        tracker.log_output(f"[Odds] Week {week}: No games found")
        return 0

    # Get valid player IDs
    player_result = await db.execute(select(Player.player_id))
    valid_player_ids = {row[0] for row in player_result.all()}

    all_odds_values = []

    for game in games:
        try:
            # Fetch odds using gameID
            response = await client.get_betting_odds(game_id=game.game_id)

            if not response or 'body' not in response:
                continue

            body = response.get('body')
            if not body:
                continue

            if isinstance(body, dict):
                game_data = body if body.get('gameID') == game.game_id else None
            elif isinstance(body, list):
                game_data = next((g for g in body if g.get('gameID') == game.game_id), None)
            else:
                continue

            if not game_data:
                continue

            player_props = game_data.get('playerProps', [])

            for prop in player_props:
                player_id = prop.get('playerID')
                anytd = prop.get('propBets', {}).get('anytd')

                if not player_id or not anytd:
                    continue

                # Skip players not in database
                if player_id not in valid_player_ids:
                    continue

                # Parse odds
                try:
                    if anytd == "even":
                        odds_value = 100
                    elif isinstance(anytd, str) and (anytd.startswith('+') or anytd.startswith('-')):
                        odds_value = int(anytd)
                    else:
                        odds_value = int(anytd)
                except (ValueError, TypeError):
                    continue

                # Create odds records for both sportsbooks
                for sportsbook in ['draftkings', 'fanduel']:
                    all_odds_values.append({
                        'player_id': player_id,
                        'game_id': game.game_id,
                        'season_year': season_year,
                        'week': week,
                        'sportsbook': sportsbook,
                        'anytime_td_odds': odds_value
                    })

        except Exception as e:
            tracker.log_output(f"[Odds] Week {week}: Error on game {game.game_id}: {str(e)}")
            continue

    # UPSERT all odds at once
    if all_odds_values:
        try:
            stmt = insert(SportsbookOdds).values(all_odds_values)
            stmt = stmt.on_conflict_do_update(
                index_elements=['player_id', 'game_id', 'sportsbook'],
                set_={'anytime_td_odds': stmt.excluded.anytime_td_odds}
            )
            await db.execute(stmt)
            await db.commit()
            tracker.log_output(f"[Odds] Week {week}: Upserted {len(all_odds_values)} odds records")
            return len(all_odds_values)
        except Exception as e:
            tracker.log_output(f"[Odds] Week {week}: Failed to upsert: {str(e)}")
            await db.rollback()
            return 0
    else:
        tracker.log_output(f"[Odds] Week {week}: No odds found")
        return 0


async def main():
    """Run complete historical backfill"""
    parser = argparse.ArgumentParser(description='Complete historical backfill (logs, predictions, odds)')
    parser.add_argument('--weeks', type=int, help='Backfill last N weeks (e.g., --weeks 5)')
    parser.add_argument('--week', type=int, help='Specific week to backfill')
    parser.add_argument('--start-week', type=int, help='Start week for range')
    parser.add_argument('--end-week', type=int, help='End week for range')
    parser.add_argument('--year', type=int, help='Season year (default: current season)')
    args = parser.parse_args()

    # Check if running in CI mode
    skip_confirmation = os.environ.get('CI', '').lower() == 'true'

    # Determine season year
    if args.year:
        season_year = args.year
    else:
        season_year, _, _ = get_current_nfl_week()

    # Determine weeks to backfill
    if args.week:
        weeks_to_backfill = [args.week]
    elif args.weeks:
        # Last N weeks from current
        _, current_week, _ = get_current_nfl_week()
        start = max(1, current_week - args.weeks)
        weeks_to_backfill = list(range(start, current_week))
    elif args.start_week and args.end_week:
        weeks_to_backfill = list(range(args.start_week, args.end_week + 1))
    elif args.start_week:
        weeks_to_backfill = list(range(args.start_week, 19))
    else:
        # Default: last 5 weeks
        _, current_week, _ = get_current_nfl_week()
        start = max(1, current_week - 5)
        weeks_to_backfill = list(range(start, current_week))

    print("=" * 60)
    print("Complete Historical Backfill")
    print("=" * 60)
    print()
    print(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Season: {season_year}")
    print(f"Weeks to backfill: {weeks_to_backfill}")
    print()
    print("This will backfill:")
    print(f"  1. Game logs (box score method)")
    print(f"  2. Predictions (only missing players)")
    print(f"  3. Sportsbook odds (upsert existing)")
    print()
    print(f"Efficiency:")
    print(f"  - API calls: ~{len(weeks_to_backfill) * 32} ({len(weeks_to_backfill)} weeks × 32 calls/week)")
    print(f"  - Only adds/updates records that don't exist")
    print(f"  - Safe to run multiple times (idempotent)")
    print()

    if not skip_confirmation:
        response = input("Continue? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("\nCancelled.")
            return
        print()
    else:
        print("Running in CI/CD mode - auto-confirming...")
        print()

    client = Tank01Client()
    triggered_by = 'github_actions' if skip_confirmation else 'manual'

    total_logs = 0
    total_predictions = 0
    total_odds = 0

    try:
        async with AsyncSessionLocal() as db:
            primary_week = weeks_to_backfill[0] if weeks_to_backfill else 1

            async with BatchTracker(
                db=db,
                batch_type='complete_backfill',
                season_year=season_year,
                week=primary_week,
                batch_mode=f"{len(weeks_to_backfill)}_weeks",
                season_type='reg',
                triggered_by=triggered_by
            ) as tracker:
                # STEP 1: Game Logs
                await tracker.start_step('game_logs', step_order=1)
                tracker.log_output(f"Starting game logs backfill for {len(weeks_to_backfill)} weeks...")

                for week in weeks_to_backfill:
                    logs_added = await backfill_game_logs_for_week(db, client, season_year, week, tracker)
                    total_logs += logs_added

                tracker.increment_metric('game_logs_added', total_logs)
                await tracker.complete_step(status='success', records_processed=total_logs)

                # STEP 2: Predictions
                await tracker.start_step('predictions', step_order=2)
                tracker.log_output(f"Starting predictions backfill for {len(weeks_to_backfill)} weeks...")

                for week in weeks_to_backfill:
                    predictions_added = await backfill_predictions_for_week(db, season_year, week, tracker)
                    total_predictions += predictions_added

                tracker.increment_metric('predictions_generated', total_predictions)
                await tracker.complete_step(status='success', records_processed=total_predictions)

                # STEP 3: Odds
                await tracker.start_step('odds', step_order=3)
                tracker.log_output(f"Starting odds backfill for {len(weeks_to_backfill)} weeks...")

                for week in weeks_to_backfill:
                    odds_added = await backfill_odds_for_week(db, client, season_year, week, tracker)
                    total_odds += odds_added

                tracker.increment_metric('odds_synced', total_odds)
                await tracker.complete_step(status='success', records_processed=total_odds)

        print()
        print("=" * 60)
        print("✅ Complete Backfill Finished!")
        print("=" * 60)
        print()
        print(f"Weeks processed: {len(weeks_to_backfill)}")
        print(f"Game logs added: {total_logs}")
        print(f"Predictions generated: {total_predictions}")
        print(f"Odds records upserted: {total_odds}")
        print()

    except Exception as e:
        print()
        print(f"❌ ERROR: {str(e)}")
        print()
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
