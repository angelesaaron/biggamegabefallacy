"""
OddsSyncService — Tank01 → sportsbook_odds table.

Fetches player props (anytime TD) for every game on each game date in a week,
computes implied_prob on write, upserts into sportsbook_odds.

Tank01 returns a single consensus line, stored as sportsbook='consensus'.
Idempotent: safe to re-run to refresh stale odds.
"""

import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import Game
from app.models.sportsbook_odds import SportsbookOdds
from app.services.sync_result import SyncResult
from app.utils.db_utils import execute_upsert
from app.utils.odds_utils import implied_prob_from_american
from app.utils.tank01_client import Tank01Client, parse_anytime_td_odds

logger = logging.getLogger(__name__)

_SPORTSBOOK = "consensus"


class OddsSyncService:
    def __init__(self, db: AsyncSession, tank01: Tank01Client) -> None:
        self._db = db
        self._tank01 = tank01

    async def run(self, season: int, week: int) -> SyncResult:
        result = SyncResult()

        # Get all games for this week to know which dates to query
        games = await self._get_games(season, week)
        if not games:
            result.add_event(f"no_games_found: S{season}W{week} — sync schedule first")
            return result

        # Tank01 odds API is per game-date. Get unique dates.
        game_dates = sorted({g.game_date.strftime("%Y%m%d") for g in games if g.game_date})
        # Build game_id lookup: game_id → (season, week)
        game_meta = {g.game_id: (g.season, g.week) for g in games}

        for game_date in game_dates:
            try:
                raw_games = await self._tank01.get_player_props(game_date)
            except Exception as exc:
                logger.error("Odds fetch failed %s: %s", game_date, exc)
                result.n_failed += 1
                result.add_event(f"odds_fetch_failed: {game_date} — {exc}")
                continue

            props = parse_anytime_td_odds(raw_games)
            for prop in props:
                game_id = prop["game_id"]
                if game_id not in game_meta:
                    result.n_skipped += 1
                    continue

                s, w = game_meta[game_id]
                try:
                    implied = implied_prob_from_american(prop["odds"])
                    data = {
                        "player_id": prop["player_id"],
                        "game_id": game_id,
                        "season": s,
                        "week": w,
                        "sportsbook": _SPORTSBOOK,
                        "odds": prop["odds"],
                        "implied_prob": round(implied, 5),
                    }
                    stmt = (
                        pg_insert(SportsbookOdds)
                        .values(**data)
                        .on_conflict_do_update(
                            constraint="uq_sportsbook_odds",
                            set_={
                                "odds": data["odds"],
                                "implied_prob": data["implied_prob"],
                            },
                        )
                    )
                    n_w, n_u = await execute_upsert(self._db, stmt)
                    result.n_written += n_w
                    result.n_updated += n_u
                except Exception as exc:
                    logger.error("OddsUpsert failed %s %s: %s", prop["player_id"], game_id, exc)
                    result.n_failed += 1

        logger.info(
            "OddsSync S%dW%d: %d written, %d updated, %d failed",
            season, week, result.n_written, result.n_updated, result.n_failed,
        )
        return result

    async def _get_games(self, season: int, week: int) -> list[Game]:
        rows = await self._db.execute(
            select(Game)
            .where(Game.season == season)
            .where(Game.week == week)
        )
        return list(rows.scalars().all())
