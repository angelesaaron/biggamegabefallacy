#!/usr/bin/env python3
"""
Manually update data readiness for a specific week.
Useful when the automatic update fails or needs to be re-run.

This script ONLY counts existing data in the database and creates/updates the DataReadiness record.
It does NOT fetch new data from APIs or create new predictions.

Usage:
    DATABASE_URL="..." python debug_tools/update_data_readiness_manual.py --week 18 --year 2025
    DATABASE_URL="..." python debug_tools/update_data_readiness_manual.py --all  # Update all weeks 1-18
"""
import asyncio
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal
from app.services.batch_tracking import update_data_readiness


async def update_week(week: int, year: int, season_type: str = 'reg'):
    """Update data readiness for a specific week"""
    async with AsyncSessionLocal() as db:
        print(f"Updating data readiness for {year} Week {week} ({season_type})...", end=" ", flush=True)
        try:
            await update_data_readiness(db, year, week, season_type)
            print("✓ Done")
        except Exception as e:
            print(f"✗ Error: {str(e)}")
            import traceback
            traceback.print_exc()
            raise


async def main():
    parser = argparse.ArgumentParser(description='Manually update data readiness')
    parser.add_argument('--week', type=int, help='Specific week to update')
    parser.add_argument('--year', type=int, default=2025, help='Season year (default: 2025)')
    parser.add_argument('--season-type', default='reg', choices=['reg', 'pre', 'post'], help='Season type')
    parser.add_argument('--all', action='store_true', help='Update all weeks 1-18')
    args = parser.parse_args()

    print("=" * 60)
    print("Manual Data Readiness Update")
    print("=" * 60)
    print()
    print("NOTE: This script counts existing data in the database.")
    print("      It does NOT fetch new data or create new records.")
    print()

    if args.all:
        print(f"Updating all weeks for {args.year} season")
        print()
        for week in range(1, 19):
            await update_week(week, args.year, args.season_type)
    elif args.week:
        await update_week(args.week, args.year, args.season_type)
    else:
        print("Error: Must specify --week or --all")
        parser.print_help()
        sys.exit(1)

    print()
    print("=" * 60)
    print("✓ Data readiness update complete")
    print("=" * 60)
    print()
    print("You can now check the Data Readiness page in your UI.")


if __name__ == "__main__":
    asyncio.run(main())
