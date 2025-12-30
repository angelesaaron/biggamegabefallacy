#!/usr/bin/env python3
"""
Sync NFL Schedule to Database

Fetches full season schedule from Tank01 and stores in database.
This is a one-time operation (or run once per season).

Usage:
    python sync_schedule.py
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import AsyncSessionLocal
from app.models.schedule import Schedule
from app.utils.tank01_client import Tank01Client
from app.config import settings
from sqlalchemy import select


async def sync_schedule():
    """Sync NFL schedule for current and previous seasons"""
    print("="*60)
    print("Syncing NFL Schedule")
    print("="*60)
    print()

    current_season = settings.NFL_SEASON_YEAR
    seasons_to_sync = [current_season - 1, current_season]  # e.g., 2024, 2025

    print(f"Seasons to sync: {seasons_to_sync}")
    print(f"Weeks per season: 1-18 (regular season)")
    print(f"Total API calls: {len(seasons_to_sync) * 18}")
    print()

    response = input("Continue? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("\nCancelled.")
        return

    print()
    print("Starting schedule sync...")
    print()

    client = Tank01Client()
    total_games = 0

    try:
        async with AsyncSessionLocal() as db:
            for season in seasons_to_sync:
                print(f"\n📅 Syncing {season} season...")

                for week in range(1, 19):  # Weeks 1-18
                    try:
                        # Fetch schedule from Tank01
                        games = await client.get_schedule(
                            season=season,
                            week=week,
                            season_type="reg"
                        )

                        if not games:
                            print(f"  Week {week:2d}: No games found")
                            continue

                        # Store in database
                        for game in games:
                            # Check if exists
                            result = await db.execute(
                                select(Schedule).where(Schedule.game_id == game.get("gameID"))
                            )
                            existing = result.scalar_one_or_none()

                            if existing:
                                # Update
                                existing.week = week
                                existing.game_status = game.get("gameStatus")
                            else:
                                # Create new
                                schedule_entry = Schedule(
                                    game_id=game.get("gameID"),
                                    season_year=season,
                                    week=week,
                                    season_type=game.get("seasonType", "Regular Season"),
                                    home_team=game.get("home"),
                                    away_team=game.get("away"),
                                    home_team_id=game.get("teamIDHome"),
                                    away_team_id=game.get("teamIDAway"),
                                    game_date=game.get("gameDate"),
                                    game_status=game.get("gameStatus"),
                                    neutral_site=game.get("neutralSite") == "True"
                                )
                                db.add(schedule_entry)

                        await db.commit()
                        total_games += len(games)
                        print(f"  Week {week:2d}: ✅ {len(games)} games")

                    except Exception as e:
                        print(f"  Week {week:2d}: ❌ Error: {str(e)}")
                        await db.rollback()
                        continue

        print()
        print("="*60)
        print(f"✅ Schedule Sync Complete!")
        print("="*60)
        print()
        print(f"Total games synced: {total_games}")
        print()
        print("Next step:")
        print("  python sync_game_logs.py")
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
    asyncio.run(sync_schedule())
