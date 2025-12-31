import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import AsyncSessionLocal
from app.models.batch_run import BatchRun
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(BatchRun).order_by(BatchRun.started_at.desc()).limit(10)
        )
        batches = result.scalars().all()
        
        if not batches:
            print("No batch runs found in database")
        else:
            print(f"Found {len(batches)} recent batch runs:\n")
            for b in batches:
                print(f"ID: {b.id}")
                print(f"  Type: {b.batch_type}")
                print(f"  Status: {b.status}")
                print(f"  Started: {b.started_at}")
                print(f"  Completed: {b.completed_at}")
                print(f"  Triggered by: {b.triggered_by}")
                print()

asyncio.run(check())
