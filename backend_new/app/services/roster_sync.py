"""
RosterSyncService — Tank01 → players table.

Fetches all 32 team rosters, filters to WR/TE, upserts into players.
Idempotent: safe to re-run at any time. Existing rows are updated in-place.

draft_round is NOT available from Tank01; it stays NULL until populated
via a separate source (e.g. nfl_data_py import_ids()).
"""

import logging

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.player import Player
from app.services.sync_result import SyncResult
from app.utils.tank01_client import Tank01Client, NFL_TEAMS, parse_player_from_roster

logger = logging.getLogger(__name__)

_TARGET_POSITIONS = {"WR", "TE"}


class RosterSyncService:
    def __init__(self, db: AsyncSession, tank01: Tank01Client) -> None:
        self._db = db
        self._tank01 = tank01

    async def run(self) -> SyncResult:
        result = SyncResult()

        for team_abv in NFL_TEAMS:
            try:
                body = await self._tank01.get_team_roster(team_abv)
                roster = body.get("roster", [])
            except Exception as exc:
                logger.error("Roster fetch failed for %s: %s", team_abv, exc)
                result.n_failed += 1
                result.add_event(f"roster_fetch_failed: {team_abv} — {exc}")
                continue

            for raw in roster:
                if raw.get("pos") not in _TARGET_POSITIONS:
                    continue

                data = parse_player_from_roster(raw)
                if not data.get("player_id") or not data.get("full_name"):
                    result.n_skipped += 1
                    continue

                try:
                    stmt = (
                        pg_insert(Player)
                        .values(**data)
                        .on_conflict_do_update(
                            index_elements=["player_id"],
                            set_={
                                "full_name": data["full_name"],
                                "position": data["position"],
                                "team": data["team"],
                                "is_te": data["is_te"],
                                "experience": data["experience"],
                                "active": data["active"],
                                "headshot_url": data["headshot_url"],
                            },
                        )
                    )
                    await self._db.execute(stmt)
                    result.n_written += 1
                except Exception as exc:
                    logger.error("Player upsert failed %s: %s", data.get("player_id"), exc)
                    result.n_failed += 1

        await self._db.commit()
        logger.info(
            "RosterSync complete: %d written, %d failed, %d skipped",
            result.n_written, result.n_failed, result.n_skipped,
        )
        return result
