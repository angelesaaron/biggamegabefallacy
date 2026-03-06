"""
ScheduleSyncService — Tank01 → games table.

Fetches the regular-season schedule for a given season (all 18 weeks)
and upserts into the games table. Idempotent.

Call this once per season at the start of the year, then re-run weekly
to pick up status changes (scheduled → final).
"""

import logging
from datetime import date

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import Game
from app.services.sync_result import SyncResult
from app.utils.tank01_client import Tank01Client, parse_game_from_schedule

logger = logging.getLogger(__name__)

_REG_SEASON_WEEKS = 18


class ScheduleSyncService:
    def __init__(self, db: AsyncSession, tank01: Tank01Client) -> None:
        self._db = db
        self._tank01 = tank01

    async def run(self, season: int) -> SyncResult:
        result = SyncResult()

        for week in range(1, _REG_SEASON_WEEKS + 1):
            try:
                games = await self._tank01.get_schedule_week(season, week)
            except Exception as exc:
                logger.error("Schedule fetch failed S%dW%d: %s", season, week, exc)
                result.n_failed += 1
                result.add_event(f"schedule_fetch_failed: S{season}W{week} — {exc}")
                continue

            for raw in games:
                data = parse_game_from_schedule(raw, season, week)
                if not data.get("game_id"):
                    result.n_skipped += 1
                    continue

                # Parse game_date string "YYYYMMDD" → date object
                date_str = data.get("game_date")
                if date_str and isinstance(date_str, str) and len(date_str) == 8:
                    try:
                        data["game_date"] = date(
                            int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8])
                        )
                    except ValueError:
                        data["game_date"] = None

                try:
                    stmt = (
                        pg_insert(Game)
                        .values(**data)
                        .on_conflict_do_update(
                            index_elements=["game_id"],
                            set_={
                                "status": data["status"],
                                "home_team": data["home_team"],
                                "away_team": data["away_team"],
                                "game_date": data["game_date"],
                                "updated_at": func.now(),
                            },
                        )
                    )
                    await self._db.execute(stmt)
                    result.n_written += 1
                except Exception as exc:
                    logger.error("Game upsert failed %s: %s", data.get("game_id"), exc)
                    result.n_failed += 1

        await self._db.commit()
        logger.info(
            "ScheduleSync S%d complete: %d written, %d failed",
            season, result.n_written, result.n_failed,
        )
        return result
