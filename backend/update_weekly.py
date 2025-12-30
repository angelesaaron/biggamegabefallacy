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


async def update_game_logs(db, client, current_season, current_week):
    """Fetch game logs for recently completed games"""
    print("\n🏈 Updating Game Logs...")
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
    """Run weekly update"""
    print("="*60)
    print("Weekly Data Update")
    print("="*60)
    print()
    print(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Use automatic week detection
    current_season, current_week = get_current_nfl_week()

    print(f"Season: {current_season}")
    print(f"Week: {current_week} (auto-detected)")
    print()
    print("This will:")
    print(f"  1. Update schedule for weeks {current_week} and {current_week + 1}")
    print(f"  2. Fetch new game logs for Week {current_week - 1} (just completed)")
    print(f"  3. Fetch sportsbook odds for Week {current_week} (upcoming)")
    print(f"  4. API calls: ~2 for schedule + ~538 for game logs + ~16 for odds = ~556 calls")
    print()

    # Skip confirmation in CI/CD environments
    if not os.environ.get('CI'):
        response = input("Continue? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("\nCancelled.")
            return
        print()
    else:
        print("Running in CI/CD mode - auto-confirming...")
        print()

    client = Tank01Client()

    try:
        async with AsyncSessionLocal() as db:
            # Update schedule
            await update_schedule(db, client, current_season, current_week)

            # Update game logs
            await update_game_logs(db, client, current_season, current_week)

            # Sync odds for next week
            print("\n📊 Syncing Odds for Next Week...")
            await sync_odds_for_next_week(db, client, current_season, current_week)

        print()
        print("="*60)
        print("✅ Weekly Update Complete!")
        print("="*60)
        print()
        print("Next steps:")
        print(f"  1. Run: python generate_predictions.py")
        print(f"     (Will generate Week {current_week} predictions)")
        print(f"     - Uses Weeks 1-{current_week-1} historical game logs")
        print(f"     - Uses Week {current_week} sportsbook odds")
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