#!/usr/bin/env python3
"""
Add jersey_number column to players table

This migration adds the jersey_number column that was added to the Player model.
Run this once to update your existing database.

Usage:
    python add_jersey_number_column.py
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import text
from app.database import engine


async def add_jersey_number_column():
    """Add jersey_number column to players table"""
    print("="*60)
    print("Adding jersey_number Column to Players Table")
    print("="*60)
    print()

    async with engine.begin() as conn:
        # Check if column already exists
        result = await conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='players' AND column_name='jersey_number'
        """))

        if result.fetchone():
            print("✓ Column 'jersey_number' already exists. No migration needed.")
            return

        # Add the column
        print("Adding jersey_number column...")
        await conn.execute(text("""
            ALTER TABLE players
            ADD COLUMN jersey_number VARCHAR(10)
        """))

        print()
        print("="*60)
        print("✅ Migration Complete!")
        print("="*60)
        print()
        print("Next steps:")
        print("  1. Re-sync rosters to populate jersey numbers: python sync_rosters.py")
        print("  2. Restart your backend server")
        print()


if __name__ == "__main__":
    asyncio.run(add_jersey_number_column())
