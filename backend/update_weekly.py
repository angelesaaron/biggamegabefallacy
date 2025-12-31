#!/usr/bin/env python3
"""
Weekly Update Script

Run this every Monday after games finish to:
1. Update schedule with any new games
2. Fetch new game logs from the past week
3. Keep data fresh for predictions

Usage:
    python update_weekly.py
"""
import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import AsyncSessionLocal
from app.models.player import Player
from app.models.game_log import GameLog
from app.models.schedule import Schedule
from app.models.odds import SportsbookOdds
from app.models.prediction import Prediction
from app.models.batch_run import BatchRun
from app.utils.tank01_client import Tank01Client, parse_game_log
from app.utils.nfl_calendar import get_current_nfl_week
from app.services.batch_tracking import BatchTracker
from app.services.data_service import get_data_service
from app.ml.model_service import get_model_service
from app.ml.feature_engineering import extract_prediction_features
from sqlalchemy import select, delete, func
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def update_schedule(db, client, current_season, current_week):
    """Update schedule with current and next week's games"""
    print("\n📅 Updating Schedule...")
    print(f"   Season: {current_season}, Current Week: {current_week}")

    games_added = 0

    # Regular season: update current and next week
    if current_week <= 18:
        weeks_to_update = [current_week, current_week + 1] if current_week < 18 else [current_week]

        for week in weeks_to_update:
            try:
                games = await client.get_schedule(
                    season=current_season,
                    week=week,
                    season_type="reg"
                )

                if not games:
                    print(f"   Week {week}: No games found")
                    continue

                for game in games:
                    # Check if exists
                    result = await db.execute(
                        select(Schedule).where(Schedule.game_id == game.get("gameID"))
                    )
                    existing = result.scalar_one_or_none()

                    if existing:
                        # Update game status
                        existing.game_status = game.get("gameStatus")
                    else:
                        # Add new game
                        schedule_entry = Schedule(
                            game_id=game.get("gameID"),
                            season_year=current_season,
                            week=week,
                            season_type="reg",
                            home_team=game.get("home"),
                            away_team=game.get("away"),
                            home_team_id=game.get("teamIDHome"),
                            away_team_id=game.get("teamIDAway"),
                            game_date=game.get("gameDate"),
                            game_status=game.get("gameStatus"),
                            neutral_site=game.get("neutralSite") == "True"
                        )
                        db.add(schedule_entry)
                        games_added += 1

                await db.commit()
                print(f"   Week {week}: ✅ Updated")

            except Exception as e:
                print(f"   Week {week}: ❌ Error: {str(e)}")
                await db.rollback()

        # If Week 18, also fetch playoff schedule (4 rounds)
        if current_week == 18:
            print("   Note: Week 18 - syncing playoff schedule...")
            for playoff_week in range(1, 5):  # Wildcard, Divisional, Conference, Super Bowl
                try:
                    games = await client.get_schedule(
                        season=current_season,
                        week=playoff_week,
                        season_type="post"
                    )

                    if not games:
                        continue

                    for game in games:
                        result = await db.execute(
                            select(Schedule).where(Schedule.game_id == game.get("gameID"))
                        )
                        existing = result.scalar_one_or_none()

                        if not existing:
                            schedule_entry = Schedule(
                                game_id=game.get("gameID"),
                                season_year=current_season,
                                week=playoff_week,
                                season_type="post",
                                home_team=game.get("home"),
                                away_team=game.get("away"),
                                home_team_id=game.get("teamIDHome"),
                                away_team_id=game.get("teamIDAway"),
                                game_date=game.get("gameDate"),
                                game_status=game.get("gameStatus"),
                                neutral_site=game.get("neutralSite") == "True"
                            )
                            db.add(schedule_entry)
                            games_added += 1

                    await db.commit()
                    print(f"   Playoff Week {playoff_week}: ✅ Updated")

                except Exception as e:
                    print(f"   Playoff Week {playoff_week}: ⚠️  {str(e)}")
                    await db.rollback()

    print(f"   Added {games_added} new games")
    return games_added


async def update_game_logs_from_box_scores(db, client, current_season, current_week):
    """
    Fetch game logs using box score endpoint (OPTIMIZED).

    Instead of making 538 API calls (one per player), this makes ~16 API calls
    (one per game) and extracts all player stats from each box score.

    Reduction: 538 calls → 16 calls (97% reduction)
    """
    print("\n🏈 Updating Game Logs (Box Score Method)...")
    completed_week = current_week - 1
    print(f"   Fetching box scores for week {completed_week} (last completed week)")

    # Get all games for completed week
    result = await db.execute(
        select(Schedule)
        .where(Schedule.season_year == current_season, Schedule.week == completed_week)
    )
    games = result.scalars().all()

    if not games:
        print(f"   No games found for Week {completed_week}")
        return 0

    print(f"   Found {len(games)} games to process")

    # Get all valid player IDs to validate foreign keys
    player_result = await db.execute(select(Player.player_id))
    valid_player_ids = {row[0] for row in player_result.all()}

    new_logs = 0
    skipped_players = set()
    games_processed = 0

    for i, game in enumerate(games, 1):
        try:
            print(f"   [{i}/{len(games)}] {game.game_id}...", end=" ", flush=True)

            # Fetch box score and extract all player game logs
            game_logs = await client.get_game_logs_from_box_score(
                game_id=game.game_id,
                season_year=current_season,
                week=completed_week
            )

            if not game_logs:
                print("No stats")
                continue

            logs_added = 0

            for log in game_logs:
                player_id = log["player_id"]

                # Skip if player not in our database (avoid foreign key errors)
                if player_id not in valid_player_ids:
                    skipped_players.add(player_id)
                    continue

                # Check if this log already exists
                existing_result = await db.execute(
                    select(GameLog).where(
                        GameLog.player_id == player_id,
                        GameLog.game_id == game.game_id
                    )
                )
                existing = existing_result.scalar_one_or_none()

                if not existing:
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
                    logs_added += 1

            if logs_added > 0:
                await db.commit()
                new_logs += logs_added
                print(f"✅ {logs_added} logs")
            else:
                print("Already synced")

            games_processed += 1

        except Exception as e:
            print(f"❌ Error: {str(e)}")
            await db.rollback()
            continue

    if skipped_players:
        print(f"   ⚠️  Skipped {len(skipped_players)} players not in database (run roster sync to add them)")

    print(f"   ✅ Complete: {games_processed} games processed, {new_logs} new game logs added")
    return new_logs


async def update_game_logs(db, client, current_season, current_week):
    """Fetch game logs for recently completed games (PER-PLAYER METHOD - LEGACY)"""
    print("\n🏈 Updating Game Logs (Per-Player Method - DEPRECATED)...")
    print(f"   Fetching logs for week {current_week - 1} (last completed week)")

    # Get all active WR/TE players
    result = await db.execute(
        select(Player).where(
            Player.active_status == True,
            Player.position.in_(["WR", "TE"])
        )
    )
    players = result.scalars().all()

    # Get schedule for mapping
    schedule_result = await db.execute(select(Schedule))
    all_schedules = schedule_result.scalars().all()
    game_id_to_week = {s.game_id: (s.season_year, s.week) for s in all_schedules}

    print(f"   Processing {len(players)} players...")

    new_logs = 0
    updated_players = 0

    for i, player in enumerate(players, 1):
        try:
            # Fetch all game logs from Tank01 (it returns recent games)
            raw_logs = await client.get_games_for_player(
                player_id=player.player_id,
                limit=10  # Only get last 10 games for efficiency
            )

            if not raw_logs:
                continue

            player_new_logs = 0

            for raw_log in raw_logs:
                parsed = parse_game_log(raw_log)
                game_id = parsed.get("game_id")

                # Get week info from schedule
                if game_id and game_id in game_id_to_week:
                    season_year, week = game_id_to_week[game_id]
                    parsed["week"] = week
                    parsed["season_year"] = season_year
                else:
                    continue

                # Check if this log already exists
                existing_result = await db.execute(
                    select(GameLog).where(
                        GameLog.player_id == player.player_id,
                        GameLog.game_id == game_id
                    )
                )
                existing = existing_result.scalar_one_or_none()

                if not existing:
                    # Add new game log
                    game_log = GameLog(
                        player_id=parsed["player_id"],
                        game_id=parsed["game_id"],
                        season_year=parsed["season_year"],
                        week=parsed["week"],
                        team=parsed["team"],
                        team_id=parsed["team_id"],
                        receptions=parsed["receptions"],
                        receiving_yards=parsed["receiving_yards"],
                        receiving_touchdowns=parsed["receiving_touchdowns"],
                        targets=parsed["targets"],
                        long_reception=parsed["long_reception"],
                        yards_per_reception=parsed["yards_per_reception"]
                    )
                    db.add(game_log)
                    player_new_logs += 1
                    new_logs += 1

            if player_new_logs > 0:
                await db.commit()
                updated_players += 1
                if i % 50 == 0:
                    print(f"   [{i}/{len(players)}] {updated_players} players updated, {new_logs} new logs")

        except Exception as e:
            await db.rollback()
            if i % 50 == 0:
                print(f"   [{i}/{len(players)}] Progress update")
            continue

    print(f"   ✅ Complete: {updated_players} players updated, {new_logs} new game logs added")
    return new_logs


async def sync_odds_for_next_week(db, client, current_season, current_week):
    """
    Sync sportsbook odds for upcoming week's games.

    Note: current_week from get_current_nfl_week() is already the next upcoming week,
    so we fetch odds for current_week (not current_week + 1).

    Uses UPSERT pattern (insert or update on conflict) to prevent data loss
    if fetch fails mid-process. Old odds remain until successfully replaced.
    """
    from sqlalchemy.dialects.postgresql import insert

    if current_week > 18:
        print(f"   Skipping odds sync - Week {current_week} is beyond regular season")
        return 0

    print(f"   Fetching odds for Week {current_week}...")

    # Get all games for current week (upcoming)
    result = await db.execute(
        select(Schedule)
        .where(Schedule.season_year == current_season, Schedule.week == current_week)
    )
    games = result.scalars().all()

    if not games:
        print(f"   No games found for Week {current_week}")
        return 0

    # Get all valid player IDs to check foreign key constraints
    player_result = await db.execute(select(Player.player_id))
    valid_player_ids = {row[0] for row in player_result.all()}
    print(f"   Found {len(valid_player_ids)} valid players in database")

    total_saved = 0
    skipped_players = set()
    all_odds_values = []  # Collect all odds for batch upsert

    for i, game in enumerate(games, 1):
        game_id = game.game_id

        try:
            # Fetch odds using gameID
            response = await client.get_betting_odds(game_id=game_id)

            if not response or 'body' not in response:
                continue

            # Handle both dict and list response formats
            body = response.get('body')
            if not body:
                continue

            if isinstance(body, dict):
                game_data = body if body.get('gameID') == game_id else None
            elif isinstance(body, list):
                game_data = next((g for g in body if g.get('gameID') == game_id), None)
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

                # Skip players not in our database to avoid foreign key violations
                if player_id not in valid_player_ids:
                    skipped_players.add(player_id)
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

                # Create odds records for both DraftKings and FanDuel
                for sportsbook in ['draftkings', 'fanduel']:
                    all_odds_values.append({
                        'player_id': player_id,
                        'game_id': game_id,
                        'season_year': current_season,
                        'week': current_week,
                        'sportsbook': sportsbook,
                        'anytime_td_odds': odds_value
                    })

            if i % 5 == 0:
                print(f"   [{i}/{len(games)}] Fetched odds for {len(all_odds_values)} player-sportsbook combinations so far...")

        except Exception as e:
            print(f"   ⚠️  Error fetching odds for game {game_id}: {str(e)}")
            continue

    # ATOMIC UPSERT: Insert all odds at once, or update if already exists
    if all_odds_values:
        try:
            stmt = insert(SportsbookOdds).values(all_odds_values)
            stmt = stmt.on_conflict_do_update(
                index_elements=['player_id', 'game_id', 'sportsbook'],
                set_={'anytime_td_odds': stmt.excluded.anytime_td_odds}
            )
            await db.execute(stmt)
            await db.commit()
            total_saved = len(all_odds_values)
            print(f"   ✅ Successfully upserted {total_saved} odds records for Week {current_week}")
        except Exception as e:
            print(f"   ❌ CRITICAL: Failed to upsert odds: {str(e)}")
            await db.rollback()
            raise
    else:
        print(f"   ⚠️  No valid odds found for Week {current_week}")

    if skipped_players:
        print(f"   ⚠️  Skipped {len(skipped_players)} players not in database (run roster sync to add them)")

    return total_saved


async def generate_predictions_for_week(db, current_season, current_week):
    """
    Generate predictions for all WR/TE players for the current week.
    Only generates predictions for players who don't already have them (immutable).
    Uses historical game logs from database (0 API calls).
    """
    print(f"\n🎯 Generating Predictions for Week {current_week}...")

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

    # Get existing predictions for this week to skip them
    existing_predictions_result = await db.execute(
        select(Prediction.player_id)
        .where(Prediction.season_year == current_season, Prediction.week == current_week)
    )
    existing_player_ids = {row[0] for row in existing_predictions_result.all()}

    if existing_player_ids:
        print(f"   Found {len(existing_player_ids)} players with existing predictions (skipping)")

    # Filter to only players WITHOUT predictions
    players_to_predict = [p for p in players if p.player_id not in existing_player_ids]

    if not players_to_predict:
        print(f"   ✅ All {len(players)} players already have predictions. Nothing to do.")
        return 0

    print(f"   Generating predictions for {len(players_to_predict)} new players...")

    successful = 0
    failed = 0
    week1_baseline = 0

    for i, player in enumerate(players_to_predict, 1):
        try:
            # Get player data
            _, game_logs, _ = await data_service.get_player_data_for_prediction(
                player_id=player.player_id,
                next_week=current_week
            )

            # Generate prediction
            if not game_logs:
                # Week 1 baseline
                td_prob, _, odds_val, favor = model_service.predict_week_1(week=current_week)
                week1_baseline += 1
            else:
                # Extract features and predict
                features = extract_prediction_features(game_logs, next_week=current_week)

                if features is None:
                    logger.warning(f"Could not extract features for {player.full_name}")
                    failed += 1
                    continue

                td_prob, _, odds_val, favor = model_service.predict_td_with_odds(features)

            # Save prediction to database
            prediction = Prediction(
                player_id=player.player_id,
                season_year=current_season,
                week=current_week,
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
                    print(f"   [{i}/{len(players_to_predict)}] Generated {successful} predictions...")
                except Exception as commit_error:
                    await db.rollback()
                    logger.warning(f"Commit error (likely race condition): {commit_error}")

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

    print(f"   ✅ Generated {successful} predictions ({week1_baseline} Week 1 baselines)")
    if failed > 0:
        print(f"   ⚠️  {failed} predictions failed")

    return successful


async def main():
    """Run weekly update with configurable batch modes"""
    import argparse

    parser = argparse.ArgumentParser(description='Weekly NFL data update')
    parser.add_argument(
        '--mode',
        choices=['full', 'odds_only', 'ingest_only', 'schedule_only'],
        default='full',
        help='Batch execution mode'
    )
    parser.add_argument('--week', type=int, help='Override week (required for odds_only)')
    parser.add_argument('--year', type=int, help='Override year (required for odds_only)')
    parser.add_argument('--season-type', choices=['reg', 'post'], help='Season type override')
    args = parser.parse_args()

    print("="*60)
    print("Weekly Data Update")
    print("="*60)
    print()
    print(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Mode validation
    if args.mode == 'odds_only' and (not args.week or not args.year):
        print("❌ ERROR: --mode odds_only requires --week and --year")
        print()
        print("Usage: python update_weekly.py --mode odds_only --week 17 --year 2025")
        sys.exit(1)

    # Check for box score optimization flag
    use_box_scores = os.environ.get('USE_BOX_SCORES', 'true').lower() == 'true'

    # Detect or use provided week/year
    if args.week and args.year:
        current_season = args.year
        current_week = args.week
        season_type = args.season_type or 'reg'
        print(f"Using provided: {current_season} Week {current_week} ({season_type.upper()})")
    else:
        current_season, current_week, season_type = get_current_nfl_week()
        print(f"Auto-detected: {current_season} Week {current_week} ({season_type.upper()})")

    print(f"Batch Mode: {args.mode.upper()}")
    print()

    # Mode descriptions
    schedule_desc = f"1. Update schedule for Week {current_week}" + (f" and {current_week + 1}" if current_week < 18 else " (+ playoff schedule)" if current_week == 18 else "")
    mode_descriptions = {
        'full': [
            schedule_desc,
            f"2. Fetch box scores for Week {current_week - 1} (completed)" if use_box_scores else f"2. Fetch game logs for Week {current_week - 1} (completed)",
            f"3. Generate predictions for Week {current_week} (using Week {current_week - 1} data)",
            f"4. Fetch odds for Week {current_week} (upcoming)"
        ],
        'odds_only': [
            f"1. Fetch odds for Week {current_week} ONLY",
            f"2. Skip schedule, game logs, and predictions",
            f"3. Safe to run mid-week to refresh odds",
            f"4. Does NOT regenerate predictions"
        ],
        'ingest_only': [
            f"1. Update schedule",
            f"2. Fetch box scores for Week {current_week - 1}" if use_box_scores else f"2. Fetch game logs for Week {current_week - 1}",
            f"3. Skip predictions and odds sync",
            f"4. Use for data corrections"
        ],
        'schedule_only': [
            f"1. Update schedule ONLY",
            f"2. Skip box scores, predictions, and odds",
            f"3. Use for schedule fixes"
        ]
    }

    print("This will:")
    for step in mode_descriptions[args.mode]:
        print(f"  {step}")
    print()

    if use_box_scores and args.mode in ['full', 'ingest_only']:
        print("Game Log Method: BOX SCORES (Optimized - 97% fewer API calls)")
    print()

    # Skip confirmation in CI/CD environments or when running odds_only
    if not os.environ.get('CI') and args.mode != 'odds_only':
        response = input("Continue? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("\nCancelled.")
            return
        print()
    elif os.environ.get('CI'):
        print("Running in CI/CD mode - auto-confirming...")
        print()

    client = Tank01Client()

    try:
        async with AsyncSessionLocal() as db:
            # Determine who triggered this batch
            triggered_by = 'github_actions' if os.environ.get('CI') else 'manual'

            # Check if batch ID was provided by API endpoint
            existing_batch_id = os.environ.get('BATCH_RUN_ID')

            # If batch ID provided, fetch and reuse existing batch
            if existing_batch_id:
                result = await db.execute(
                    select(BatchRun).where(BatchRun.id == int(existing_batch_id))
                )
                batch_run = result.scalar_one_or_none()

                if not batch_run:
                    raise ValueError(f"Batch run {existing_batch_id} not found")

                # Use season info from the existing batch (don't re-detect)
                current_season = batch_run.season_year
                current_week = batch_run.week
                season_type = batch_run.season_type

                # Use existing batch with manual tracker management
                tracker = BatchTracker(
                    db=db,
                    batch_type='weekly_update',
                    season_year=current_season,
                    week=current_week,
                    batch_mode=args.mode,
                    season_type=season_type,
                    triggered_by='ui'
                )
                # Override with existing batch
                tracker.batch_run = batch_run
                async with tracker:
                    await _execute_batch_steps(
                        db, tracker, client, current_season, current_week,
                        season_type, args.mode, use_box_scores
                    )
            else:
                # Create new batch via context manager
                async with BatchTracker(
                    db=db,
                    batch_type='weekly_update',
                    season_year=current_season,
                    week=current_week,
                    batch_mode=args.mode,
                    season_type=season_type,
                    triggered_by=triggered_by
                ) as tracker:
                    await _execute_batch_steps(
                        db, tracker, client, current_season, current_week,
                        season_type, args.mode, use_box_scores
                    )

    except Exception as e:
        print()
        print(f"❌ ERROR: {str(e)}")
        print()
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        await client.close()


async def _execute_batch_steps(
        db, tracker, client, current_season, current_week,
        season_type, mode, use_box_scores
):
    """Execute the batch update steps (extracted for reuse)"""
    # STEP 1: SCHEDULE SYNC
    if mode in ['full', 'ingest_only', 'schedule_only']:
        await tracker.start_step('schedule', step_order=1)
        try:
            tracker.log_output("Starting schedule update...")
            games_added = await update_schedule(db, client, current_season, current_week)
            tracker.increment_metric('games_processed', games_added)
            tracker.log_output(f"Schedule update complete: {games_added} games processed")
            await tracker.complete_step(status='success', records_processed=games_added)
        except Exception as e:
            tracker.log_output(f"Schedule update failed: {str(e)}")
            await tracker.fail_step(error_message=str(e))
            raise

    # STEP 2: GAME LOGS SYNC
    if mode in ['full', 'ingest_only']:
        if season_type == 'reg':
            await tracker.start_step('game_logs', step_order=2)
            try:
                # Update game logs - choose method based on flag
                if use_box_scores:
                    tracker.log_output("Fetching game logs from box scores (optimized)...")
                    logs_added = await update_game_logs_from_box_scores(db, client, current_season, current_week)
                else:
                    tracker.log_output("Fetching game logs from player endpoint...")
                    logs_added = await update_game_logs(db, client, current_season, current_week)

                tracker.increment_metric('game_logs_added', logs_added)
                tracker.log_output(f"Game logs sync complete: {logs_added} logs added")
                await tracker.complete_step(status='success', records_processed=logs_added)
            except Exception as e:
                tracker.log_output(f"Game logs sync failed: {str(e)}")
                await tracker.fail_step(error_message=str(e))
                raise
        else:
            await tracker.start_step('game_logs', step_order=2)
            print("\n⚠️  Skipping game logs (playoffs - not supported for predictions)")
            tracker.add_warning('game_logs', 'Skipped - playoffs not supported')
            await tracker.skip_step(reason="Playoffs not supported for predictions")

    # STEP 3: PREDICTIONS (FULL MODE ONLY)
    if mode == 'full' and season_type == 'reg':
        await tracker.start_step('predictions', step_order=3)
        try:
            tracker.log_output(f"Generating predictions for Week {current_week}...")
            predictions_generated = await generate_predictions_for_week(db, current_season, current_week)
            tracker.increment_metric('predictions_generated', predictions_generated)
            tracker.log_output(f"Prediction generation complete: {predictions_generated} predictions generated")
            await tracker.complete_step(status='success', records_processed=predictions_generated)
        except Exception as e:
            tracker.log_output(f"Prediction generation failed: {str(e)}")
            await tracker.fail_step(error_message=str(e))
            raise

    # STEP 4: ODDS SYNC
    if mode in ['full', 'odds_only']:
        step_order = 4 if mode == 'full' else 3
        await tracker.start_step('odds', step_order=step_order)
        try:
            tracker.log_output(f"Syncing odds for Week {current_week}...")
            print(f"\n📊 Syncing Odds for Week {current_week}...")
            odds_synced = await sync_odds_for_next_week(db, client, current_season, current_week)
            tracker.increment_metric('odds_synced', odds_synced)
            tracker.log_output(f"Odds sync complete: {odds_synced} odds records synced")
            await tracker.complete_step(status='success', records_processed=odds_synced)
        except Exception as e:
            tracker.log_output(f"Odds sync failed: {str(e)}")
            await tracker.fail_step(error_message=str(e))
            raise

    print()
    print("="*60)
    print(f"✅ Batch Complete ({mode.upper()})")
    print("="*60)

    # Next steps guidance
    if mode == 'full' and season_type == 'reg':
        print()
        print("✅ Full batch complete!")
        print(f"   Schedule, game logs, predictions, and odds are ready for Week {current_week}")
        print()
    elif mode == 'full' and season_type == 'post':
        print()
        print("⚠️  Playoffs detected - predictions not supported")
        print("   Schedule and odds have been synced")
        print()
    elif mode == 'odds_only':
        print()
        print("✅ Odds refreshed successfully")
        print(f"   Predictions remain unchanged (immutable)")
        print()
    else:
        print()


if __name__ == "__main__":
    asyncio.run(main())