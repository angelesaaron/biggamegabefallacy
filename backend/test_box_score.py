#!/usr/bin/env python3
"""
Test Box Score Game Log Extraction

This script tests the new box score approach for fetching game logs.
Tests against Week 17 2025 data to validate:
1. API call works
2. Parser extracts all player stats correctly
3. Data matches expected format
4. Edge cases are handled
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.utils.tank01_client import Tank01Client
from app.database import AsyncSessionLocal
from app.models.schedule import Schedule
from sqlalchemy import select


async def test_box_score_extraction():
    """Test box score extraction for a single game"""
    print("="*60)
    print("Testing Box Score Game Log Extraction")
    print("="*60)
    print()

    client = Tank01Client()

    try:
        async with AsyncSessionLocal() as db:
            # Get one game from Week 17 2025
            result = await db.execute(
                select(Schedule)
                .where(Schedule.season_year == 2025, Schedule.week == 17)
                .limit(1)
            )
            game = result.scalar_one_or_none()

            if not game:
                print("❌ No Week 17 2025 games found in database")
                return

            print(f"Testing with game: {game.game_id}")
            print(f"  {game.away_team} @ {game.home_team}")
            print()

            # Test 1: Fetch box score
            print("Test 1: Fetching box score...")
            box_score = await client.get_box_score(game.game_id, play_by_play=False)

            if not box_score:
                print("❌ Failed to fetch box score")
                return

            player_stats = box_score.get("playerStats", {})
            print(f"✅ Box score fetched: {len(player_stats)} players found")
            print()

            # Test 2: Extract game logs
            print("Test 2: Extracting game logs from box score...")
            game_logs = await client.get_game_logs_from_box_score(
                game_id=game.game_id,
                season_year=2025,
                week=17
            )

            if not game_logs:
                print("❌ No game logs extracted")
                return

            print(f"✅ Extracted {len(game_logs)} game logs with receiving stats")
            print()

            # Test 3: Validate data format
            print("Test 3: Validating data format...")
            required_fields = [
                "player_id", "game_id", "season_year", "week", "team", "team_id",
                "receptions", "receiving_yards", "receiving_touchdowns", "targets"
            ]

            sample_log = game_logs[0]
            missing_fields = [f for f in required_fields if f not in sample_log]

            if missing_fields:
                print(f"❌ Missing fields: {missing_fields}")
                return

            print("✅ All required fields present")
            print()

            # Test 4: Display sample data
            print("Test 4: Sample game logs")
            print("-" * 60)
            for i, log in enumerate(game_logs[:5], 1):
                print(f"{i}. Player {log['player_id']} ({log['team']})")
                print(f"   Rec: {log['receptions']}, Yards: {log['receiving_yards']}, "
                      f"TD: {log['receiving_touchdowns']}, Targets: {log['targets']}")

            if len(game_logs) > 5:
                print(f"   ... and {len(game_logs) - 5} more players")
            print()

            # Test 5: Check for TD scorers
            print("Test 5: Players with receiving TDs")
            print("-" * 60)
            td_scorers = [log for log in game_logs if log['receiving_touchdowns'] > 0]

            if td_scorers:
                for log in td_scorers:
                    print(f"  ✅ Player {log['player_id']} ({log['team']}): {log['receiving_touchdowns']} TD(s)")
            else:
                print("  No receiving TDs in this game")
            print()

            # Test 6: Edge case - zero stat players
            print("Test 6: Players with zero stats (but played)")
            print("-" * 60)
            zero_stat_players = [
                log for log in game_logs
                if log['receptions'] == 0 and log['receiving_yards'] == 0 and log['targets'] > 0
            ]

            if zero_stat_players:
                for log in zero_stat_players[:3]:
                    print(f"  Player {log['player_id']} ({log['team']}): "
                          f"{log['targets']} targets, 0 catches (correctly included)")
            else:
                print("  No players with zero catches found")
            print()

            print("="*60)
            print("✅ All Tests Passed!")
            print("="*60)
            print()
            print("Summary:")
            print(f"  • Box score fetched successfully")
            print(f"  • {len(game_logs)} player game logs extracted")
            print(f"  • {len(td_scorers)} receiving TDs found")
            print(f"  • Data format validated")
            print()

    except Exception as e:
        print()
        print(f"❌ TEST FAILED: {str(e)}")
        print()
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        await client.close()


async def test_all_week_17_games():
    """Test box score extraction for all Week 17 games"""
    print("="*60)
    print("Testing All Week 17 2025 Games")
    print("="*60)
    print()

    client = Tank01Client()

    try:
        async with AsyncSessionLocal() as db:
            # Get all Week 17 games
            result = await db.execute(
                select(Schedule)
                .where(Schedule.season_year == 2025, Schedule.week == 17)
            )
            games = result.scalars().all()

            if not games:
                print("❌ No Week 17 2025 games found")
                return

            print(f"Found {len(games)} games for Week 17 2025")
            print()

            total_logs = 0
            total_tds = 0
            failed_games = []

            for i, game in enumerate(games, 1):
                try:
                    print(f"[{i}/{len(games)}] {game.game_id}...", end=" ", flush=True)

                    game_logs = await client.get_game_logs_from_box_score(
                        game_id=game.game_id,
                        season_year=2025,
                        week=17
                    )

                    if not game_logs:
                        print("No stats")
                        continue

                    tds = sum(log['receiving_touchdowns'] for log in game_logs)
                    total_logs += len(game_logs)
                    total_tds += tds

                    print(f"✅ {len(game_logs)} logs, {tds} TDs")

                except Exception as e:
                    print(f"❌ Error: {str(e)}")
                    failed_games.append(game.game_id)
                    continue

            print()
            print("="*60)
            print("Test Summary")
            print("="*60)
            print(f"  Games processed: {len(games) - len(failed_games)}/{len(games)}")
            print(f"  Total game logs: {total_logs}")
            print(f"  Total receiving TDs: {total_tds}")

            if failed_games:
                print(f"  Failed games: {len(failed_games)}")
                for game_id in failed_games:
                    print(f"    - {game_id}")
            else:
                print(f"  ✅ All games successful!")
            print()

    except Exception as e:
        print()
        print(f"❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        await client.close()


async def main():
    """Run all tests"""
    print("\nWhich test would you like to run?")
    print("  1. Single game test (detailed)")
    print("  2. All Week 17 games test (summary)")
    print()

    choice = input("Enter choice (1 or 2): ").strip()
    print()

    if choice == "1":
        await test_box_score_extraction()
    elif choice == "2":
        await test_all_week_17_games()
    else:
        print("Invalid choice. Run with '1' or '2'")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
