#!/usr/bin/env python3
"""
Normalize season_type values in the schedule table.

Converts 'Regular Season', 'Post Season', 'Pre Season' to 'reg', 'post', 'pre'
to ensure consistency across all database tables.

This is safe because all code that reads season_type has normalization maps
that handle both formats.

Usage:
    DATABASE_URL="..." python debug_tools/normalize_schedule_season_types.py
"""
import asyncio
import sys
from pathlib import Path
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal


async def normalize_season_types():
    """Normalize season_type values in schedule table"""
    async with AsyncSessionLocal() as db:
        print("Checking current season_type values...")

        # Check current values
        result = await db.execute(text("""
            SELECT season_type, COUNT(*)
            FROM schedule
            GROUP BY season_type
            ORDER BY season_type
        """))

        print("\nCurrent season_type distribution:")
        rows = result.fetchall()
        needs_update = False
        for row in rows:
            print(f"  '{row[0]}': {row[1]} games")
            if row[0] not in ['reg', 'post', 'pre']:
                needs_update = True

        if not needs_update:
            print("\n✓ All season_type values are already normalized!")
            return

        print("\n" + "=" * 60)
        print("This will update the schedule table:")
        print("  'Regular Season' → 'reg'")
        print("  'Post Season' → 'post'")
        print("  'Pre Season' → 'pre'")
        print("=" * 60)
        print()

        # Update Regular Season -> reg
        result = await db.execute(text("""
            UPDATE schedule
            SET season_type = 'reg'
            WHERE season_type = 'Regular Season'
        """))
        reg_count = result.rowcount

        # Update Post Season -> post
        result = await db.execute(text("""
            UPDATE schedule
            SET season_type = 'post'
            WHERE season_type = 'Post Season'
        """))
        post_count = result.rowcount

        # Update Pre Season -> pre
        result = await db.execute(text("""
            UPDATE schedule
            SET season_type = 'pre'
            WHERE season_type = 'Pre Season'
        """))
        pre_count = result.rowcount

        await db.commit()

        total_updated = reg_count + post_count + pre_count
        print(f"✓ Updated {reg_count} 'Regular Season' → 'reg'")
        print(f"✓ Updated {post_count} 'Post Season' → 'post'")
        print(f"✓ Updated {pre_count} 'Pre Season' → 'pre'")
        print(f"\nTotal games updated: {total_updated}")

        # Verify
        result = await db.execute(text("""
            SELECT season_type, COUNT(*)
            FROM schedule
            GROUP BY season_type
            ORDER BY season_type
        """))

        print("\nFinal season_type distribution:")
        for row in result.fetchall():
            print(f"  '{row[0]}': {row[1]} games")


if __name__ == "__main__":
    print("=" * 60)
    print("Normalize Schedule Season Types")
    print("=" * 60)
    print()
    asyncio.run(normalize_season_types())
    print()
    print("=" * 60)
    print("✓ Complete - Schedule table is now consistent")
    print("=" * 60)
