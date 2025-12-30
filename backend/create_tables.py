#!/usr/bin/env python3
"""
Create all database tables for BGGTDM

Run this after PostgreSQL is set up and running.
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import engine, Base
from app.models import player, prediction, odds, result, value_pick, job


async def create_tables():
    """Create all database tables"""
    print("="*60)
    print("Creating Database Tables")
    print("="*60)
    print()

    try:
        print("Connecting to database...")
        async with engine.begin() as conn:
            print("Creating tables...")
            await conn.run_sync(Base.metadata.create_all)

        print()
        print("✅ Tables created successfully!")
        print()
        print("Tables created:")
        print("  - players")
        print("  - predictions")
        print("  - sportsbook_odds")
        print("  - game_results")
        print("  - value_picks")
        print("  - job_runs")
        print()
        print("="*60)
        print("✅ Database is ready!")
        print("="*60)
        print()
        print("Next steps:")
        print("  1. Sync rosters: python sync_rosters.py")
        print("  2. Start API: uvicorn app.main:app --reload")
        print()

    except Exception as e:
        print()
        print(f"❌ ERROR: Failed to create tables")
        print(f"   {str(e)}")
        print()
        print("Make sure PostgreSQL is running:")
        print("  pg_ctl -D ~/pgdata status")
        print()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(create_tables())
