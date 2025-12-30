#!/usr/bin/env python3
"""
Sync NFL Team Rosters to Database

Fetches all WR and TE players from Tank01 API and stores them in the database.
This is a one-time operation that makes 32 API calls (one per NFL team).

Usage:
    python sync_rosters.py
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import AsyncSessionLocal
from app.services.data_service import get_data_service


async def sync_rosters():
    """Sync all NFL team rosters for WR and TE positions"""
    print("="*60)
    print("Syncing NFL Rosters (WR & TE)")
    print("="*60)
    print()
    print("⚠️  This will make 32 Tank01 API calls (one per NFL team)")
    print()

    # Ask for confirmation
    response = input("Continue? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("\nCancelled.")
        return

    print()
    print("Starting roster sync...")
    print()

    async with AsyncSessionLocal() as db:
        service = get_data_service(db)

        try:
            # Sync only WR and TE positions
            count = await service.sync_rosters(positions=["WR", "TE"])

            print()
            print("="*60)
            print(f"✅ Roster Sync Complete!")
            print("="*60)
            print()
            print(f"Synced {count} players (WR & TE)")
            print()
            print("API calls used: 32")
            print()
            print("Next steps:")
            print("  1. Test player list: http://localhost:8000/api/players")
            print("  2. Generate a prediction: POST /api/predictions/generate/{player_id}")
            print("  3. View API docs: http://localhost:8000/docs")
            print()

        except Exception as e:
            print()
            print(f"❌ ERROR: {str(e)}")
            print()
            import traceback
            traceback.print_exc()
            sys.exit(1)

        finally:
            await service.close()


if __name__ == "__main__":
    asyncio.run(sync_rosters())
