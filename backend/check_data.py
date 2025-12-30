#!/usr/bin/env python3
"""
Quick diagnostic script to check what data is in the database
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import AsyncSessionLocal
from app.models.prediction import Prediction
from app.models.odds import SportsbookOdds
from app.utils.nfl_calendar import get_current_nfl_week
from sqlalchemy import select, func


async def check_data():
    print("="*60)
    print("DATABASE DIAGNOSTIC CHECK")
    print("="*60)
    print()

    # Get current week
    current_year, current_week = get_current_nfl_week()
    print(f"Current NFL Week (from detection): {current_year} Week {current_week}")
    print()

    async with AsyncSessionLocal() as db:
        # Check predictions
        print("PREDICTIONS:")
        print("-" * 60)

        # Get all unique week/year combinations
        result = await db.execute(
            select(
                Prediction.season_year,
                Prediction.week,
                func.count(Prediction.player_id).label('count')
            )
            .group_by(Prediction.season_year, Prediction.week)
            .order_by(Prediction.season_year.desc(), Prediction.week.desc())
        )
        predictions_summary = result.all()

        if predictions_summary:
            for row in predictions_summary:
                marker = " <- CURRENT WEEK" if row.season_year == current_year and row.week == current_week else ""
                print(f"  {row.season_year} Week {row.week}: {row.count} predictions{marker}")
        else:
            print("  No predictions found in database!")

        print()

        # Check odds
        print("SPORTSBOOK ODDS:")
        print("-" * 60)

        result = await db.execute(
            select(
                SportsbookOdds.season_year,
                SportsbookOdds.week,
                func.count(func.distinct(SportsbookOdds.player_id)).label('players'),
                func.count(SportsbookOdds.id).label('total_records')
            )
            .group_by(SportsbookOdds.season_year, SportsbookOdds.week)
            .order_by(SportsbookOdds.season_year.desc(), SportsbookOdds.week.desc())
        )
        odds_summary = result.all()

        if odds_summary:
            for row in odds_summary:
                marker = " <- CURRENT WEEK" if row.season_year == current_year and row.week == current_week else ""
                print(f"  {row.season_year} Week {row.week}: {row.players} players, {row.total_records} records{marker}")
        else:
            print("  No odds found in database!")

        print()
        print("="*60)
        print("SUMMARY:")
        print("="*60)

        # Check if current week has data
        has_current_predictions = any(
            row.season_year == current_year and row.week == current_week
            for row in predictions_summary
        )
        has_current_odds = any(
            row.season_year == current_year and row.week == current_week
            for row in odds_summary
        )

        if has_current_predictions and has_current_odds:
            print(f"✅ Week {current_week} predictions and odds are available")
        elif has_current_predictions and not has_current_odds:
            print(f"⚠️  Week {current_week} predictions exist but NO ODDS")
        elif not has_current_predictions and has_current_odds:
            print(f"⚠️  Week {current_week} odds exist but NO PREDICTIONS")
        else:
            print(f"❌ Week {current_week} has NO DATA")
            if predictions_summary:
                latest = predictions_summary[0]
                print(f"   Latest available: {latest.season_year} Week {latest.week}")


if __name__ == "__main__":
    asyncio.run(check_data())
