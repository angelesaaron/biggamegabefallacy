"""
Backfill sportsbook odds for all weeks that have game logs but no odds rows.

Run from backend_new/:
    python scripts/backfill_odds.py

Uses OddsSyncService directly (no running server needed).
Adds a 1s delay between weeks to avoid rate limiting.
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.config import settings
from app.services.odds_sync import OddsSyncService
from app.utils.tank01_client import Tank01Client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("backfill_odds")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


async def get_weeks_needing_odds(engine) -> list[tuple[int, int]]:
    query = sa.text("""
        SELECT
            g.season,
            g.week,
            COUNT(DISTINCT gg.game_id) AS num_games,
            COUNT(pgl.id)              AS num_logs,
            COALESCE(so.cnt, 0)        AS num_odds
        FROM (SELECT DISTINCT season, week FROM games) g
        JOIN games gg ON gg.season = g.season AND gg.week = g.week
        LEFT JOIN player_game_logs pgl
            ON pgl.season = g.season AND pgl.week = g.week
        LEFT JOIN (
            SELECT season, week, COUNT(*) AS cnt
            FROM sportsbook_odds
            GROUP BY season, week
        ) so ON so.season = g.season AND so.week = g.week
        GROUP BY g.season, g.week, so.cnt
        HAVING COUNT(pgl.id) > 0
           AND COALESCE(so.cnt, 0) = 0
        ORDER BY g.season, g.week
    """)
    async with engine.connect() as conn:
        rows = (await conn.execute(query)).fetchall()
    return [(row.season, row.week) for row in rows]


async def main() -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    weeks = await get_weeks_needing_odds(engine)
    if not weeks:
        logger.info("No weeks need odds backfill — all caught up.")
        await engine.dispose()
        return

    logger.info("Weeks to backfill: %d", len(weeks))

    total_written = 0
    total_updated = 0
    total_failed = 0
    errors: list[str] = []

    async with Tank01Client(api_key=settings.TANK01_API_KEY) as tank01:
        for i, (season, week) in enumerate(weeks):
            logger.info("[%d/%d] S%dW%d …", i + 1, len(weeks), season, week)
            try:
                async with Session() as db:
                    svc = OddsSyncService(db=db, tank01=tank01)
                    result = await svc.run(season=season, week=week)
                    await db.commit()

                total_written += result.n_written
                total_updated += result.n_updated
                total_failed += result.n_failed

                logger.info(
                    "  → written=%d updated=%d failed=%d | %s",
                    result.n_written, result.n_updated, result.n_failed, result.events,
                )
                if result.n_failed > 0:
                    errors.append(f"S{season}W{week}: {result.events}")

            except Exception as exc:
                logger.error("  S%dW%d ABORTED: %s", season, week, exc)
                total_failed += 1
                errors.append(f"S{season}W{week}: {exc}")

            if i < len(weeks) - 1:
                await asyncio.sleep(1.0)

    await engine.dispose()

    print("\n" + "=" * 60)
    print("BACKFILL COMPLETE")
    print(f"  Weeks processed : {len(weeks)}")
    print(f"  Total written   : {total_written}")
    print(f"  Total updated   : {total_updated}")
    print(f"  Total failed    : {total_failed}")
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
