#!/usr/bin/env python3
"""
Sync Sportsbook Odds

Fetches DraftKings and FanDuel anytime TD odds for upcoming games.
Uses gameID parameter to ensure correct player-game matching.

Usage:
    python sync_odds.py [--week WEEK] [--year YEAR]
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import AsyncSessionLocal
from app.models.schedule import Schedule
from app.models.odds import SportsbookOdds
from app.models.player import Player
from app.utils.tank01_client import Tank01Client
from app.utils.nfl_calendar import get_current_nfl_week
from sqlalchemy import select, delete
import argparse


async def fetch_odds_for_game(client: Tank01Client, game_id: str) -> Optional[dict]:
    """
    Fetch betting odds for a specific game using gameID parameter.

    Args:
        client: Tank01 API client
        game_id: Game ID (format: YYYYMMDD_AWAY@HOME)

    Returns:
        Dict with playerProps data or None if error
    """
    try:
        # Call getNFLBettingOdds with gameID parameter
        # Note: The actual endpoint might need gameID or gameDate, adjust based on API docs
        response = await client.get_betting_odds(game_id=game_id)

        if not response or 'body' not in response:
            print(f"  No odds data for {game_id}")
            return None

        # Response format can be either:
        # {"statusCode": 200, "body": {"gameID": "...", "playerProps": [...]}}  <- dict
        # OR
        # {"statusCode": 200, "body": [{"gameID": "...", "playerProps": [...]}]}  <- list
        body = response.get('body')
        if not body:
            return None

        # Handle both formats
        if isinstance(body, dict):
            # Single game response
            if body.get('gameID') == game_id:
                return body
            else:
                print(f"  Game ID mismatch: expected {game_id}, got {body.get('gameID')}")
                return None
        elif isinstance(body, list):
            # Multiple games response
            game_data = next((g for g in body if g.get('gameID') == game_id), None)
            return game_data
        else:
            print(f"  Unexpected body type: {type(body)}")
            return None

    except Exception as e:
        print(f"  ❌ Error fetching odds for {game_id}: {str(e)}")
        return None


async def sync_odds_for_week(db, client: Tank01Client, season_year: int, week: int):
    """
    Sync odds for all games in a given week.

    Args:
        db: Database session
        client: Tank01 API client
        season_year: Season year
        week: Week number
    """
    print(f"\n📊 Syncing Odds for {season_year} Week {week}...")

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
    player_result = await db.execute(select(Player.player_id))
    known_player_ids = set(row[0] for row in player_result)
    print(f"  Database has {len(known_player_ids)} players")

    # Delete existing odds for this week (refresh)
    await db.execute(
        delete(SportsbookOdds)
        .where(SportsbookOdds.season_year == season_year, SportsbookOdds.week == week)
    )
    await db.commit()
    print(f"  Cleared old odds")

    total_odds_saved = 0
    skipped_unknown_players = 0

    for i, game in enumerate(games, 1):
        game_id = game.game_id
        print(f"\n  [{i}/{len(games)}] {game.away_team} @ {game.home_team} ({game_id})")

        # Fetch odds for this game
        game_data = await fetch_odds_for_game(client, game_id)

        if not game_data:
            continue

        player_props = game_data.get('playerProps', [])
        if not player_props:
            print(f"    No player props found")
            continue

        # Extract DraftKings and FanDuel odds
        sportsbooks = game_data.get('sportsBooks', [])
        draftkings_data = next((s for s in sportsbooks if s.get('sportsBook') == 'draftkings'), None)
        fanduel_data = next((s for s in sportsbooks if s.get('sportsBook') == 'fanduel'), None)

        odds_count = 0

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

            # Save DraftKings odds (using consensus from playerProps)
            # Note: The playerProps odds appear to be consensus/aggregate
            draftkings_odds = SportsbookOdds(
                player_id=player_id,
                game_id=game_id,
                season_year=season_year,
                week=week,
                sportsbook='draftkings',
                anytime_td_odds=odds_value
            )
            db.add(draftkings_odds)

            # Save FanDuel odds (same for now, can differentiate if API provides)
            fanduel_odds = SportsbookOdds(
                player_id=player_id,
                game_id=game_id,
                season_year=season_year,
                week=week,
                sportsbook='fanduel',
                anytime_td_odds=odds_value
            )
            db.add(fanduel_odds)

            odds_count += 2

        await db.commit()
        total_odds_saved += odds_count
        print(f"    ✅ Saved {odds_count // 2} player odds (DK + FD)")

    if skipped_unknown_players > 0:
        print(f"\n  ⚠️  Skipped {skipped_unknown_players} player odds (not in database)")

    return total_odds_saved


async def main():
    """Run odds sync"""
    parser = argparse.ArgumentParser(description='Sync sportsbook odds for NFL games')
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
    print("Sportsbook Odds Sync")
    print("=" * 60)
    print()
    print(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Target: {season_year} Week {week}")
    print()
    print("This will:")
    print(f"  1. Fetch odds for all Week {week} games")
    print(f"  2. Store DraftKings and FanDuel anytime TD odds")
    print(f"  3. Replace any existing odds for this week")
    print()

    response = input("Continue? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("\nCancelled.")
        return

    client = Tank01Client()

    try:
        async with AsyncSessionLocal() as db:
            total_odds = await sync_odds_for_week(db, client, season_year, week)

        print()
        print("=" * 60)
        print(f"✅ Odds Sync Complete!")
        print("=" * 60)
        print()
        print(f"Total odds records saved: {total_odds}")
        print(f"(DraftKings + FanDuel for {total_odds // 2} players)")
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
