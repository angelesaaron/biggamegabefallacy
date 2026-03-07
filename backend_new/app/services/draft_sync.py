"""
DraftSyncService — populates players.draft_round from nflreadpy.

Tank01's getNFLTeamRoster does not include draft data. nflreadpy's load_players()
does — and nflverse's espn_id is the same numeric ID as Tank01's playerID, so
matching is exact (no name fuzzing required).

draft_round values:
  1-7  — drafted round
  0    — undrafted free agent (UDFA); nflverse returns NaN for these
  NULL — not found in nflverse (rare; feature_compute treats as 0 / UDFA bucket)

Run after roster sync. Safe to re-run at any time — idempotent.
Re-run after the annual draft to populate draft_round for incoming rookies.
"""

import asyncio
import logging
import os

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.player import Player
from app.services.sync_result import SyncResult

logger = logging.getLogger(__name__)


class DraftSyncService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def run(self, force_update: bool = False) -> SyncResult:
        """
        Fetch nflverse player registry and populate draft_round for WR/TE players.

        Args:
            force_update: If True, overwrite existing draft_round values.
                          If False (default), only update players where draft_round is NULL.
        """
        result = SyncResult()

        rows = await self._db.execute(
            select(Player).where(Player.position.in_(["WR", "TE"]))
        )
        players = list(rows.scalars().all())

        if not force_update:
            players = [p for p in players if p.draft_round is None]

        if not players:
            logger.info(
                "DraftSync: no players need draft_round update (use force_update=True to refresh all)"
            )
            return result

        logger.info(
            "DraftSync: %d players to update (force_update=%s)", len(players), force_update
        )

        try:
            draft_map: dict[str, int] = await asyncio.to_thread(_load_draft_rounds)
        except Exception as exc:
            logger.error("DraftSync: nflreadpy fetch failed: %s", exc)
            raise

        logger.info(
            "DraftSync: loaded draft data for %d players from nflverse", len(draft_map)
        )

        for player in players:
            if player.player_id not in draft_map:
                logger.debug(
                    "DraftSync: %s (%s) not found in nflverse",
                    player.full_name, player.player_id,
                )
                result.n_skipped += 1
                result.add_event(
                    f"draft_round_not_found: {player.full_name} ({player.player_id})"
                )
                continue

            new_round = draft_map[player.player_id]

            if player.draft_round == new_round:
                result.n_skipped += 1
                continue

            try:
                await self._db.execute(
                    update(Player)
                    .where(Player.player_id == player.player_id)
                    .values(draft_round=new_round)
                )
                result.n_updated += 1
            except Exception as exc:
                logger.error(
                    "DraftSync: update failed for %s: %s", player.player_id, exc
                )
                result.n_failed += 1

        await self._db.commit()

        logger.info(
            "DraftSync complete: %d updated, %d skipped, %d failed",
            result.n_updated, result.n_skipped, result.n_failed,
        )
        return result


# ── nflreadpy fetch (sync, runs in thread pool) ───────────────────────────────

def _load_draft_rounds() -> dict[str, int]:
    """
    Fetch nflverse player registry and return espn_id → draft_round map.

    espn_id in nflverse == playerID in Tank01 (both are ESPN numeric IDs).
    Players with no draft entry (NaN draft_round) are treated as UDFA → 0.
    """
    import nflreadpy as nfl
    from pathlib import Path
    from nflreadpy.config import update_config

    cache_dir = settings.NFLVERSE_CACHE_DIR
    os.makedirs(cache_dir, exist_ok=True)
    update_config(cache_mode="filesystem", cache_dir=Path(cache_dir))

    logger.info("DraftSync: fetching nflreadpy player data (cache: %s)", cache_dir)
    df = nfl.load_players().to_pandas()

    df = df[df["espn_id"].notna()].copy()
    df["espn_id"] = df["espn_id"].astype(float).astype(int).astype(str)

    # NaN draft_round → 0 (UDFA)
    df["draft_round"] = df["draft_round"].fillna(0).astype(int)

    # Deduplicate: if a player appears multiple times keep the highest round
    # (0 = UDFA and should only stay if no other entry exists)
    deduped = (
        df.sort_values("draft_round", ascending=False)
        .drop_duplicates(subset=["espn_id"], keep="first")
    )

    return dict(zip(deduped["espn_id"], deduped["draft_round"]))
