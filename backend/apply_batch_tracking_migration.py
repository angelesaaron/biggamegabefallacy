#!/usr/bin/env python3
"""
Apply Batch Tracking Migration

Creates batch_runs and data_readiness tables for observability.

Usage:
    python apply_batch_tracking_migration.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.database import AsyncSessionLocal
from sqlalchemy import text


async def apply_migration():
    """Apply batch tracking tables migration"""
    print("=" * 60)
    print("Applying Batch Tracking Migration")
    print("=" * 60)
    print()

    # Read SQL file
    sql_file = Path(__file__).parent / "create_batch_tracking_tables.sql"
    with open(sql_file, 'r') as f:
        sql_content = f.read()

    print("Creating tables:")
    print("  - batch_runs (audit log for batch processes)")
    print("  - data_readiness (data availability per week)")
    print()

    async with AsyncSessionLocal() as db:
        try:
            # Split SQL into individual statements and execute
            # Remove comments and split by semicolons
            statements = []
            current = []
            for line in sql_content.split('\n'):
                # Skip comment-only lines
                if line.strip().startswith('--'):
                    continue
                # Remove inline comments
                line = line.split('--')[0].strip()
                if line:
                    current.append(line)
                    if line.endswith(';'):
                        statements.append(' '.join(current))
                        current = []

            # Execute each statement
            for statement in statements:
                if statement.strip():
                    await db.execute(text(statement))

            await db.commit()

            print("✅ Migration applied successfully!")
            print()
            print("Tables created:")
            print("  ✓ batch_runs")
            print("  ✓ data_readiness")
            print()
            print("Indexes created:")
            print("  ✓ idx_batch_runs_type_week")
            print("  ✓ idx_batch_runs_status")
            print("  ✓ idx_batch_runs_started")
            print("  ✓ idx_data_readiness_week")
            print("  ✓ idx_data_readiness_type")
            print()

        except Exception as e:
            print(f"❌ Migration failed: {str(e)}")
            await db.rollback()
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(apply_migration())
