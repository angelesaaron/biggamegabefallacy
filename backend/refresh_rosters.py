#!/usr/bin/env python3
"""
Roster Refresh - Manual Player Onboarding

Fetches latest rosters from Tank01 and adds new players.
For new players only, optionally backfills historical game logs.

IMMUTABILITY GUARANTEE:
- Only adds NEW players (skips existing)
- Historical backfill is OPTIONAL (--backfill flag)
- Safe to run multiple times (idempotent)

Usage:
    # Preview new players only (DRY RUN)
    python refresh_rosters.py --dry-run

    # Add new players WITHOUT historical backfill
    python refresh_rosters.py

    # Add new players WITH historical backfill
    python refresh_rosters.py --backfill

    # Custom backfill limit (default: 52 weeks)
    python refresh_rosters.py --backfill --max-weeks 20
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import List
import argparse
import logging

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import AsyncSessionLocal
from app.models.player import Player
from app.models.game_log import GameLog
from app.models.schedule import Schedule
from app.utils.tank01_client import Tank01Client, parse_player_from_roster, parse_game_log
from sqlalchemy import select, func

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def refresh_rosters(
    dry_run: bool = False,
    backfill_history: bool = False,
    positions: List[str] = None,
    max_backfill_weeks: int = 52
):
    """
    Fetch all rosters and onboard new players.

    Args:
        dry_run: If True, preview changes without committing
        backfill_history: If True, backfill historical game logs for new players
        positions: List of positions to sync (default: ["WR", "TE"])
        max_backfill_weeks: Maximum weeks to backfill per player
    """
    if positions is None:
        positions = ["WR", "TE"]

    print("=" * 60)
    print("Roster Refresh - Player Onboarding")
    print("=" * 60)
    print(f"Mode: {'DRY RUN (preview only)' if dry_run else 'LIVE'}")
    print(f"Positions: {', '.join(positions)}")
    print(f"Backfill: {'YES (up to ' + str(max_backfill_weeks) + ' weeks)' if backfill_history else 'NO'}")
    print()

    client = Tank01Client()
    start_time = datetime.utcnow()

    try:
        async with AsyncSessionLocal() as db:
            # Fetch all rosters from Tank01 (32 teams)
            print("Fetching rosters from Tank01 (32 teams)...")
            all_roster_players = await client.get_all_rosters(positions=positions)
            print(f"Found {len(all_roster_players)} {'/'.join(positions)} players from API\n")

            # Get existing players from database
            result = await db.execute(select(Player.player_id))
            existing_player_ids = {row[0] for row in result.all()}
            print(f"Database has {len(existing_player_ids)} existing players\n")

            # Find new players
            new_players = [
                p for p in all_roster_players
                if p.get("playerID") not in existing_player_ids
            ]

            if not new_players:
                print("✅ No new players detected. Roster is up to date.")
                print()
                return

            print(f"🆕 Detected {len(new_players)} NEW players:")
            for i, p in enumerate(new_players[:10], 1):  # Show first 10
                print(f"   {i}. {p.get('longName')} ({p.get('pos')}, {p.get('team')})")
            if len(new_players) > 10:
                print(f"   ... and {len(new_players) - 10} more")
            print()

            # Estimate API calls
            api_calls = 32  # Rosters already fetched
            if backfill_history:
                api_calls += len(new_players)  # 1 per player for game logs

            print(f"Estimated API calls: {api_calls}")
            if backfill_history:
                print(f"  - 32 roster calls (already made)")
                print(f"  - {len(new_players)} game log calls (1 per new player)")
            print()

            # DRY RUN - exit without changes
            if dry_run:
                print("=" * 60)
                print("DRY RUN - No changes will be made")
                print("=" * 60)
                print()
                print("To apply changes, run without --dry-run:")
                print(f"  python refresh_rosters.py")
                if backfill_history:
                    print(f"  python refresh_rosters.py --backfill")
                print()
                return

            # Confirm if high API usage
            if len(new_players) > 20 and backfill_history:
                print("⚠️  WARNING: Large number of new players with backfill enabled")
                response = input(f"Add {len(new_players)} players with historical backfill? (yes/no): ")
                if response.lower() not in ['yes', 'y']:
                    print("\nCancelled.")
                    return
                print()

            # PHASE 1: Insert new players
            print("Adding new players to database...")
            players_added = 0

            for player_data in new_players:
                try:
                    parsed = parse_player_from_roster(player_data)

                    new_player = Player(**parsed)
                    db.add(new_player)
                    players_added += 1
                except Exception as e:
                    logger.error(f"Failed to add player {player_data.get('longName')}: {e}")
                    continue

            await db.commit()
            print(f"✅ Added {players_added} new players\n")

            # PHASE 2: Historical backfill (OPTIONAL)
            backfilled_logs = 0

            if backfill_history:
                print(f"Starting historical backfill for {players_added} players...")
                print(f"(Limited to {max_backfill_weeks} most recent weeks)")
                print()

                # Get schedule for week mapping
                schedule_result = await db.execute(select(Schedule))
                all_schedules = schedule_result.scalars().all()
                game_id_to_week = {
                    s.game_id: (s.season_year, s.week)
                    for s in all_schedules
                }

                for i, player_data in enumerate(new_players, 1):
                    player_id = player_data.get("playerID")
                    player_name = player_data.get("longName")

                    try:
                        # Fetch game logs from API
                        raw_logs = await client.get_games_for_player(
                            player_id=player_id,
                            limit=max_backfill_weeks
                        )

                        if not raw_logs:
                            if i % 10 == 0:
                                print(f"[{i}/{players_added}] Backfilled {backfilled_logs} logs so far...")
                            continue

                        player_logs = 0

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

                            # Check if log already exists
                            existing_log = await db.execute(
                                select(GameLog).where(
                                    GameLog.player_id == player_id,
                                    GameLog.game_id == game_id
                                )
                            )
                            if existing_log.scalar_one_or_none():
                                continue

                            # Insert game log
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
                            player_logs += 1
                            backfilled_logs += 1

                        if player_logs > 0:
                            await db.commit()

                        if i % 10 == 0:
                            print(f"[{i}/{players_added}] Backfilled {backfilled_logs} logs so far...")

                        # Rate limiting - 500ms delay between players
                        await asyncio.sleep(0.5)

                    except Exception as e:
                        logger.error(f"Failed to backfill {player_name}: {e}")
                        await db.rollback()
                        continue

                print(f"✅ Backfilled {backfilled_logs} historical game logs\n")

            # Calculate duration
            end_time = datetime.utcnow()
            duration_seconds = int((end_time - start_time).total_seconds())

            # Summary
            print("=" * 60)
            print("✅ Roster Refresh Complete")
            print("=" * 60)
            print()
            print(f"Players scanned: {len(all_roster_players)}")
            print(f"Players added: {players_added}")
            if backfill_history:
                print(f"Game logs backfilled: {backfilled_logs}")
            print(f"Duration: {duration_seconds}s")
            print()

            if players_added > 0:
                print("Next steps:")
                print("  1. Run weekly batch to generate predictions for new players:")
                print("     python generate_predictions.py")
                print()

    finally:
        await client.close()


async def main():
    """Run roster refresh"""
    parser = argparse.ArgumentParser(
        description='Refresh NFL rosters and onboard new players',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview new players without making changes
  python refresh_rosters.py --dry-run

  # Add new players (no historical data)
  python refresh_rosters.py

  # Add new players with full historical backfill
  python refresh_rosters.py --backfill

  # Add new players with limited backfill (20 weeks)
  python refresh_rosters.py --backfill --max-weeks 20
        """
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without committing to database'
    )
    parser.add_argument(
        '--backfill',
        action='store_true',
        help='Backfill historical game logs for new players (uses API calls)'
    )
    parser.add_argument(
        '--max-weeks',
        type=int,
        default=52,
        help='Maximum weeks to backfill per player (default: 52)'
    )
    parser.add_argument(
        '--positions',
        nargs='+',
        default=['WR', 'TE'],
        help='Positions to sync (default: WR TE)'
    )
    args = parser.parse_args()

    try:
        await refresh_rosters(
            dry_run=args.dry_run,
            backfill_history=args.backfill,
            positions=args.positions,
            max_backfill_weeks=args.max_weeks
        )
    except Exception as e:
        print()
        print(f"❌ ERROR: {str(e)}")
        print()
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
