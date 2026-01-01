#!/usr/bin/env python3
"""
Add missing unique constraint to data_readiness table.

This constraint is required for the UPSERT operation in update_data_readiness().

Usage:
    DATABASE_URL="..." python debug_tools/add_data_readiness_constraint.py
"""
import asyncio
import sys
from pathlib import Path
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal


async def add_constraint():
    """Add unique constraint to data_readiness table"""
    async with AsyncSessionLocal() as db:
        print("Checking for existing constraint...")

        # Check if constraint already exists
        result = await db.execute(text("""
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name = 'data_readiness'
            AND constraint_type = 'UNIQUE'
        """))
        existing = result.fetchall()

        if existing:
            print(f"✓ Constraint already exists: {existing[0][0]}")
            return

        print("Adding unique constraint on (season_year, week, season_type)...")

        try:
            await db.execute(text("""
                ALTER TABLE data_readiness
                ADD CONSTRAINT uix_data_readiness_season_week
                UNIQUE (season_year, week, season_type)
            """))
            await db.commit()
            print("✓ Constraint added successfully!")
        except Exception as e:
            await db.rollback()
            print(f"✗ Error adding constraint: {str(e)}")
            raise


if __name__ == "__main__":
    print("=" * 60)
    print("Add Data Readiness Unique Constraint")
    print("=" * 60)
    print()
    asyncio.run(add_constraint())
    print()
    print("=" * 60)
    print("Done! You can now run update_data_readiness_manual.py")
    print("=" * 60)
