#!/usr/bin/env python3
"""
Backfill Historical Sportsbook Odds

Fetches historical betting odds for completed games using gameID parameter.
Useful for:
1. Testing model predictions against historical sportsbook lines
2. Analyzing historical edge detection accuracy
3. Building a database of historical odds for future analysis

Note: Tank01 API may not have odds for very old games, but should have
recent weeks from current season.

Usage:
    # Backfill specific week
    python backfill_historical_odds.py --week 10 --year 2025

    # Backfill entire season
    python backfill_historical_odds.py --year 2025

    # Backfill week range
    python backfill_historical_odds.py --start-week 1 --end-week 16 --year 2025
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
from app.models.odds import SportsbookOdds
from app.utils.tank01_client import Tank01Client
from app.utils.nfl_calendar import get_current_nfl_week
from app.services.batch_tracking import BatchTracker
from sqlalchemy import select, delete


async def backfill_odds_for_week(db, client: Tank01Client, season_year: int, week: int, skip_confirmation: bool = False):
    """
    Backfill odds for all games in a specific week.

    Args:
        db: Database session
        client: Tank01 API client
        season_year: Season year
        week: Week number
        skip_confirmation: Skip overwrite confirmation (for CI mode)

    Returns:
        Number of odds records saved
    """
    print(f"\n📊 Backfilling Odds for {season_year} Week {week}...")

    # Get all games for this week
    result = await db.execute(
        select(Schedule)
        .where(Schedule.season_year == season_year, Schedule.week == week)
        .order_by(Schedule.game_date)
    )
    games = result.scalars().all()

    if not games:
        print(f"  No games found for Week {week}")
        return 0

    print(f"  Found {len(games)} games")

    # Get all player IDs from our database to check against
    from app.models.player import Player
    player_result = await db.execute(select(Player.player_id))
    known_player_ids = set(row[0] for row in player_result)
    print(f"  Database has {len(known_player_ids)} players")

    # Check if odds already exist
    existing_result = await db.execute(
        select(SportsbookOdds)
        .where(SportsbookOdds.season_year == season_year, SportsbookOdds.week == week)
    )
    existing_odds = existing_result.scalars().all()

    if existing_odds:
        print(f"  ⚠️  Found {len(existing_odds)} existing odds records")
        if not skip_confirmation:
            response = input("  Overwrite existing odds? (yes/no): ")
            if response.lower() not in ['yes', 'y']:
                print(f"  Skipped Week {week}")
                return 0
        else:
            print(f"  Auto-confirming overwrite (CI mode)")

        # Delete existing odds
        await db.execute(
            delete(SportsbookOdds)
            .where(SportsbookOdds.season_year == season_year, SportsbookOdds.week == week)
        )
        await db.commit()
        print(f"  Deleted {len(existing_odds)} existing records")

    total_saved = 0
    games_with_odds = 0
    games_without_odds = 0
    skipped_unknown_players = 0

    for i, game in enumerate(games, 1):
        game_id = game.game_id
        print(f"\n  [{i}/{len(games)}] {game.away_team} @ {game.home_team} ({game_id})")

        try:
            # Fetch odds using gameID
            response = await client.get_betting_odds(game_id=game_id)

            if not response or 'body' not in response:
                print(f"    ❌ No response from API")
                games_without_odds += 1
                continue

            # Handle both dict and list response formats
            body = response.get('body')
            if not body:
                print(f"    ⚠️  Empty response body")
                games_without_odds += 1
                continue

            if isinstance(body, dict):
                game_data = body if body.get('gameID') == game_id else None
            elif isinstance(body, list):
                game_data = next((g for g in body if g.get('gameID') == game_id), None)
            else:
                print(f"    ⚠️  Unexpected body type: {type(body)}")
                games_without_odds += 1
                continue

            if not game_data:
                print(f"    ⚠️  No odds data for this game")
                games_without_odds += 1
                continue

            player_props = game_data.get('playerProps', [])
            if not player_props:
                print(f"    ⚠️  No player props found")
                games_without_odds += 1
                continue

            game_odds_count = 0

            for prop in player_props:
                player_id = prop.get('playerID')
                if not player_id:
                    continue

                # Skip players not in our database
                if player_id not in known_player_ids:
                    skipped_unknown_players += 1
                    continue

                prop_bets = prop.get('propBets', {})
                anytd = prop_bets.get('anytd')

                if not anytd:
                    continue

                # Parse American odds (can be "+175", "-140", or "even")
                try:
                    if anytd == "even":
                        odds_value = 100
                    elif isinstance(anytd, str) and (anytd.startswith('+') or anytd.startswith('-')):
                        odds_value = int(anytd)
                    else:
                        odds_value = int(anytd)
                except (ValueError, AttributeError, TypeError):
                    continue

                # Save DraftKings odds
                draftkings_odds = SportsbookOdds(
                    player_id=player_id,
                    game_id=game_id,
                    season_year=season_year,
                    week=week,
                    sportsbook='draftkings',
                    anytime_td_odds=odds_value
                )
                db.add(draftkings_odds)

                # Save FanDuel odds (same value for now)
                fanduel_odds = SportsbookOdds(
                    player_id=player_id,
                    game_id=game_id,
                    season_year=season_year,
                    week=week,
                    sportsbook='fanduel',
                    anytime_td_odds=odds_value
                )
                db.add(fanduel_odds)

                game_odds_count += 2

            await db.commit()
            total_saved += game_odds_count

            if game_odds_count > 0:
                games_with_odds += 1
                print(f"    ✅ Saved {game_odds_count // 2} player odds (DK + FD)")
            else:
                games_without_odds += 1
                print(f"    ⚠️  No player odds available")

        except Exception as e:
            print(f"    ❌ Error: {str(e)}")
            await db.rollback()
            games_without_odds += 1
            continue

    print(f"\n  Summary for Week {week}:")
    print(f"    Games with odds: {games_with_odds}")
    print(f"    Games without odds: {games_without_odds}")
    print(f"    Total odds records: {total_saved}")
    if skipped_unknown_players > 0:
        print(f"    Skipped {skipped_unknown_players} player odds (not in database)")

    return total_saved


async def main():
    """Run historical odds backfill"""
    parser = argparse.ArgumentParser(description='Backfill historical sportsbook odds')
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
    elif args.start_week and args.end_week:
        weeks_to_backfill = list(range(args.start_week, args.end_week + 1))
    elif args.start_week:
        weeks_to_backfill = list(range(args.start_week, 19))
    else:
        # Default: backfill all weeks from 1 to current week - 1
        _, current_week, _ = get_current_nfl_week()
        weeks_to_backfill = list(range(1, current_week))

    print("=" * 60)
    print("Historical Odds Backfill")
    print("=" * 60)
    print()
    print(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Season: {season_year}")
    print(f"Weeks to backfill: {weeks_to_backfill}")
    print()
    print("This will:")
    print(f"  1. Fetch odds for {len(weeks_to_backfill)} weeks")
    print(f"  2. API calls: ~{len(weeks_to_backfill) * 16} (1 per game)")
    print(f"  3. Overwrite existing odds if present")
    print()
    print("⚠️  Note: Historical odds may not be available for all games")
    print("   Tank01 API likely only has odds for recent weeks")
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
    total_odds = 0
    successful_weeks = 0
    triggered_by = 'github_actions' if skip_confirmation else 'manual'

    try:
        async with AsyncSessionLocal() as db:
            # Use batch tracking for the first week (or single week if only one)
            # This allows tracking in the UI
            primary_week = weeks_to_backfill[0] if weeks_to_backfill else 1

            async with BatchTracker(
                db=db,
                batch_type='odds_backfill',
                season_year=season_year,
                week=primary_week,
                batch_mode=f"{len(weeks_to_backfill)}_weeks",
                season_type='reg',
                triggered_by=triggered_by
            ) as tracker:
                await tracker.start_step('backfill_odds', step_order=1)
                tracker.log_output(f"Backfilling odds for {len(weeks_to_backfill)} weeks: {weeks_to_backfill}")

                for week in weeks_to_backfill:
                    tracker.log_output(f"Processing week {week}...")
                    odds_count = await backfill_odds_for_week(db, client, season_year, week, skip_confirmation)
                    total_odds += odds_count
                    if odds_count > 0:
                        successful_weeks += 1
                    tracker.log_output(f"Week {week}: {odds_count} odds records saved")

                tracker.increment_metric('odds_synced', total_odds)
                tracker.log_output(f"Backfill complete: {successful_weeks}/{len(weeks_to_backfill)} weeks with odds, {total_odds} total records")
                await tracker.complete_step(status='success', records_processed=total_odds)

        print()
        print("=" * 60)
        print("✅ Historical Odds Backfill Complete!")
        print("=" * 60)
        print()
        print(f"Weeks processed: {len(weeks_to_backfill)}")
        print(f"Weeks with odds: {successful_weeks}")
        print(f"Total odds records saved: {total_odds}")
        print()
        print("Next steps:")
        print("  1. Test historical predictions with odds comparison:")
        print(f"     GET /api/predictions/{{player_id}}?week=10&year={season_year}")
        print()
        print("  2. Analyze model accuracy against historical lines")
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
