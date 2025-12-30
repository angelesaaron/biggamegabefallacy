#!/usr/bin/env python3
"""
Sync Player Game Logs to Database

Fetches all game logs for all WR/TE players and stores in database.
This is a one-time bulk operation (or run periodically to update).

Usage:
    python sync_game_logs.py
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import AsyncSessionLocal
from app.models.player import Player
from app.models.game_log import GameLog
from app.models.schedule import Schedule
from app.utils.tank01_client import Tank01Client, parse_game_log
from sqlalchemy import select


async def sync_game_logs():
    """Sync game logs for all WR/TE players"""
    print("="*60)
    print("Syncing Player Game Logs")
    print("="*60)
    print()

    async with AsyncSessionLocal() as db:
        # Get all active WR/TE players
        result = await db.execute(
            select(Player).where(
                Player.active_status == True,
                Player.position.in_(["WR", "TE"])
            )
        )
        players = result.scalars().all()

        print(f"Found {len(players)} active WR/TE players")
        print(f"This will make {len(players)} API calls")
        print()

        response = input("Continue? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("\nCancelled.")
            return

        print()
        print("Starting game log sync...")
        print()

        # Get schedule mapping for week enrichment
        schedule_result = await db.execute(select(Schedule))
        all_schedules = schedule_result.scalars().all()
        game_id_to_week = {s.game_id: (s.season_year, s.week) for s in all_schedules}

        print(f"Loaded {len(game_id_to_week)} games from schedule")
        print()

        client = Tank01Client()
        total_logs = 0
        players_processed = 0
        players_failed = 0

        try:
            for i, player in enumerate(players, 1):
                try:
                    print(f"[{i}/{len(players)}] {player.full_name}...", end=" ", flush=True)

                    # Fetch game logs from Tank01
                    raw_logs = await client.get_games_for_player(player_id=player.player_id)

                    if not raw_logs:
                        print("No games")
                        continue

                    # Parse and store each game log
                    logs_added = 0
                    for raw_log in raw_logs:
                        parsed = parse_game_log(raw_log)

                        # Get week number from schedule
                        game_id = parsed.get("game_id")
                        if game_id and game_id in game_id_to_week:
                            season_year, week = game_id_to_week[game_id]
                            parsed["week"] = week
                            parsed["season_year"] = season_year
                        else:
                            # Skip games without week mapping
                            continue

                        # Check if already exists
                        existing_result = await db.execute(
                            select(GameLog).where(
                                GameLog.player_id == player.player_id,
                                GameLog.game_id == game_id
                            )
                        )
                        existing = existing_result.scalar_one_or_none()

                        if not existing:
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
                            logs_added += 1

                    await db.commit()
                    total_logs += logs_added
                    players_processed += 1
                    print(f"✅ {logs_added} games")

                except Exception as e:
                    print(f"❌ Error: {str(e)}")
                    players_failed += 1
                    await db.rollback()
                    continue

        finally:
            await client.close()

        print()
        print("="*60)
        print(f"✅ Game Log Sync Complete!")
        print("="*60)
        print()
        print(f"Players processed: {players_processed}")
        print(f"Players failed: {players_failed}")
        print(f"Total game logs: {total_logs}")
        print()
        print("Next step:")
        print("  Generate predictions for all players")
        print()


if __name__ == "__main__":
    asyncio.run(sync_game_logs())
