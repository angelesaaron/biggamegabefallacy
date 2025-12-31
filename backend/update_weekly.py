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
from app.utils.tank01_client import Tank01Client, parse_game_log
from app.utils.nfl_calendar import get_current_nfl_week
from app.services.batch_tracking import BatchTracker
from sqlalchemy import select, delete


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
    """
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

    # Delete existing odds for current week (refresh)
    await db.execute(
        delete(SportsbookOdds)
        .where(SportsbookOdds.season_year == current_season, SportsbookOdds.week == current_week)
    )
    await db.commit()

    total_saved = 0
    skipped_players = set()

    for i, game in enumerate(games, 1):
        game_id = game.game_id  # Store game_id before potential rollback

        # Create a list to batch insert odds for this game
        odds_to_add = []

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
                    odds_record = SportsbookOdds(
                        player_id=player_id,
                        game_id=game_id,
                        season_year=current_season,
                        week=current_week,
                        sportsbook=sportsbook,
                        anytime_td_odds=odds_value
                    )
                    odds_to_add.append(odds_record)

            # Only add and commit if we have valid odds to insert
            if odds_to_add:
                for odds_record in odds_to_add:
                    db.add(odds_record)
                await db.commit()
                total_saved += len(odds_to_add)

            if i % 5 == 0:
                print(f"   [{i}/{len(games)}] Synced {total_saved} odds records so far...")

        except Exception as e:
            print(f"   ⚠️  Error syncing odds for game {game_id}: {str(e)}")
            await db.rollback()
            continue

    if skipped_players:
        print(f"   ⚠️  Skipped {len(skipped_players)} players not in database (run roster sync to add them)")

    print(f"   ✅ Synced {total_saved} odds records for Week {current_week}")
    return total_saved


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
    mode_descriptions = {
        'full': [
            f"1. Update schedule for current/next week",
            f"2. Fetch box scores for Week {current_week - 1} (completed)" if use_box_scores else f"2. Fetch game logs for Week {current_week - 1} (completed)",
            f"3. Fetch odds for Week {current_week} (upcoming)",
            f"4. Then run: python generate_predictions.py (separate step)"
        ],
        'odds_only': [
            f"1. Fetch odds for Week {current_week} ONLY",
            f"2. Skip schedule and game logs",
            f"3. Safe to run mid-week to refresh odds",
            f"4. Does NOT regenerate predictions"
        ],
        'ingest_only': [
            f"1. Update schedule",
            f"2. Fetch box scores for Week {current_week - 1}" if use_box_scores else f"2. Fetch game logs for Week {current_week - 1}",
            f"3. Skip odds sync",
            f"4. Use for data corrections"
        ],
        'schedule_only': [
            f"1. Update schedule ONLY",
            f"2. Skip box scores and odds",
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

            # Track batch execution
            async with BatchTracker(
                db=db,
                batch_type='weekly_update',
                season_year=current_season,
                week=current_week,
                batch_mode=args.mode,
                season_type=season_type,
                triggered_by=triggered_by
            ) as tracker:
                # SCHEDULE SYNC
                if args.mode in ['full', 'ingest_only', 'schedule_only']:
                    games_added = await update_schedule(db, client, current_season, current_week)
                    tracker.increment_metric('games_processed', games_added)

                # GAME LOGS SYNC
                if args.mode in ['full', 'ingest_only']:
                    if season_type == 'reg':
                        # Update game logs - choose method based on flag
                        if use_box_scores:
                            logs_added = await update_game_logs_from_box_scores(db, client, current_season, current_week)
                            tracker.increment_metric('game_logs_added', logs_added)
                        else:
                            logs_added = await update_game_logs(db, client, current_season, current_week)
                            tracker.increment_metric('game_logs_added', logs_added)
                    else:
                        print("\n⚠️  Skipping game logs (playoffs - not supported for predictions)")
                        tracker.add_warning('game_logs', 'Skipped - playoffs not supported')

                # ODDS SYNC
                if args.mode in ['full', 'odds_only']:
                    print(f"\n📊 Syncing Odds for Week {current_week}...")
                    odds_synced = await sync_odds_for_next_week(db, client, current_season, current_week)
                    tracker.increment_metric('odds_synced', odds_synced)

        print()
        print("="*60)
        print(f"✅ Batch Complete ({args.mode.upper()})")
        print("="*60)

        # Next steps guidance
        if args.mode == 'full' and season_type == 'reg':
            print()
            print("Next steps:")
            print(f"  python generate_predictions.py --week {current_week} --year {current_season}")
            print(f"  (Will generate predictions ONLY for new players)")
            print()
        elif args.mode == 'full' and season_type == 'post':
            print()
            print("⚠️  Playoffs detected - predictions not supported")
            print("   Schedule and odds have been synced")
            print()
        elif args.mode == 'odds_only':
            print()
            print("✅ Odds refreshed successfully")
            print(f"   Predictions remain unchanged (immutable)")
            print()
        else:
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