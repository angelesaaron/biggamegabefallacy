#!/usr/bin/env python3
"""
Diagnostic script to check game logs and predictions for a specific player.
Helps identify missing predictions that should exist based on available game logs.

Usage:
    python check_player_data.py "Ricky Pearsall"
    python check_player_data.py "Puka Nacua"
"""
import asyncio
import sys
from pathlib import Path
from sqlalchemy import select

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import AsyncSessionLocal
from app.models.player import Player
from app.models.game_log import GameLog
from app.models.prediction import Prediction


async def check_player(player_name: str):
    """Check game logs and predictions for a player"""
    async with AsyncSessionLocal() as db:
        # Find player
        result = await db.execute(
            select(Player).where(Player.full_name.ilike(f"%{player_name}%"))
        )
        players = result.scalars().all()

        if not players:
            print(f"❌ No player found matching '{player_name}'")
            return

        if len(players) > 1:
            print(f"⚠️  Multiple players found:")
            for p in players:
                print(f"   - {p.full_name} ({p.player_id}) - {p.team} {p.position}")
            print("\nPlease be more specific.")
            return

        player = players[0]
        print("=" * 80)
        print(f"Player: {player.full_name}")
        print(f"ID: {player.player_id}")
        print(f"Team: {player.team} | Position: {player.position}")
        print(f"Active: {player.active_status}")
        print("=" * 80)
        print()

        # Get game logs for 2025
        game_logs_result = await db.execute(
            select(GameLog)
            .where(GameLog.player_id == player.player_id, GameLog.season_year == 2025)
            .order_by(GameLog.week)
        )
        game_logs = game_logs_result.scalars().all()

        # Get predictions for 2025
        predictions_result = await db.execute(
            select(Prediction)
            .where(Prediction.player_id == player.player_id, Prediction.season_year == 2025)
            .order_by(Prediction.week)
        )
        predictions = predictions_result.scalars().all()

        # Create week-indexed dictionaries
        game_log_weeks = {log.week: log for log in game_logs}
        prediction_weeks = {pred.week: pred for pred in predictions}

        # Find all weeks (1-18)
        all_weeks = range(1, 19)

        print("Week-by-Week Breakdown (2025 Season):")
        print("-" * 80)
        print(f"{'Week':<6} {'Game Log':<15} {'Prediction':<15} {'Status':<30}")
        print("-" * 80)

        missing_predictions = []

        for week in all_weeks:
            has_game_log = week in game_log_weeks
            has_prediction = week in prediction_weeks

            # Determine status
            if has_game_log and has_prediction:
                status = "✓ Complete"
                game_log_str = f"✓ ({game_log_weeks[week].receiving_touchdowns} TD)"
                pred_str = f"✓ ({prediction_weeks[week].td_likelihood:.3f})"
            elif has_game_log and not has_prediction:
                status = "⚠️  MISSING PREDICTION"
                game_log_str = f"✓ ({game_log_weeks[week].receiving_touchdowns} TD)"
                pred_str = "❌ None"
                missing_predictions.append(week)
            elif not has_game_log and has_prediction:
                status = "ℹ️  Prediction only"
                game_log_str = "❌ None"
                pred_str = f"✓ ({prediction_weeks[week].td_likelihood:.3f})"
            else:
                status = ""
                game_log_str = ""
                pred_str = ""
                continue  # Skip weeks with no data

            print(f"{week:<6} {game_log_str:<15} {pred_str:<15} {status:<30}")

        print("-" * 80)
        print()
        print("Summary:")
        print(f"  Total game logs: {len(game_logs)}")
        print(f"  Total predictions: {len(predictions)}")
        print(f"  Weeks with game logs: {sorted(game_log_weeks.keys())}")
        print(f"  Weeks with predictions: {sorted(prediction_weeks.keys())}")

        if missing_predictions:
            print()
            print(f"⚠️  MISSING PREDICTIONS for weeks: {missing_predictions}")
            print()
            print("To generate missing predictions, you can:")
            print(f"  1. Run backfill for specific weeks:")
            for wk in missing_predictions[:3]:  # Show first 3 as examples
                print(f"     python backfill_complete.py --week {wk} --year 2025")
            if len(missing_predictions) > 3:
                print(f"     ... and {len(missing_predictions) - 3} more weeks")
            print()
            print(f"  2. Or backfill a range:")
            if missing_predictions:
                min_week = min(missing_predictions)
                max_week = max(missing_predictions)
                print(f"     python backfill_complete.py --start-week {min_week} --end-week {max_week} --year 2025")
        else:
            print()
            print("✓ All weeks with game logs have predictions!")

        print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_player_data.py 'Player Name'")
        print("Example: python check_player_data.py 'Ricky Pearsall'")
        sys.exit(1)

    player_name = sys.argv[1]
    asyncio.run(check_player(player_name))
