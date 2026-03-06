"""
AliasSeedService — seeds player_aliases with known name mismatches.

The NAME_OVERRIDES dict is directly derived from 05_new_features.ipynb.
Keys are Tank01 full_name (lowercased), values are nflverse_snap alias_name.

Run once after initial roster sync. Safe to re-run (upserts).

Known unresolved names from the notebook (need nflverse lookup to complete):
  Gabe Davis, Drew Ogletree, Harold Fannin Jr., Tre' Harris, Oronde Gadsden,
  Luther Burden III, Donald Parham Jr., Scotty Miller, Dont'e Thornton Jr.,
  Mecole Hardman Jr.
These will appear in DataQualityEvents until their aliases are added here.
"""

import logging

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.player import Player
from app.models.player_alias import PlayerAlias
from app.services.sync_result import SyncResult

logger = logging.getLogger(__name__)

# Keys: Tank01 full_name (lowercase)
# Values: exact alias_name as it appears in nflverse snap data (lowercase)
_SNAP_OVERRIDES: dict[str, str] = {
    "kyle pitts sr.": "kyle pitts",
    "dk metcalf": "d.k. metcalf",
    "marvin mims jr.": "marvin mims",
    "brian thomas jr.": "brian thomas",
    "john metchie iii": "john metchie",
    "chig okonkwo": "chigoziem okonkwo",
    "joshua palmer": "josh palmer",
    "hollywood brown": "marquise brown",
    "chris godwin jr.": "chris godwin",
}

# PBP overrides: Tank01 full_name (lowercase) → nflverse_pbp short name (lowercase)
# Most PBP names are auto-derived "F.Last" — only add here when that fails.
_PBP_OVERRIDES: dict[str, str] = {
    # Example: "dk metcalf": "d.metcalf"  — but auto-derive "D.Metcalf" works, so not needed.
    # Add entries here as DataQualityEvents surface nflverse_pbp failures.
}


class AliasSeedService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def run(self) -> SyncResult:
        result = SyncResult()

        # Build full_name_lower → player_id map from DB
        rows = await self._db.execute(
            select(Player.player_id, Player.full_name)
            .where(Player.position.in_(["WR", "TE"]))
        )
        name_to_id = {row.full_name.lower(): row.player_id for row in rows}

        for overrides, source in [
            (_SNAP_OVERRIDES, "nflverse_snap"),
            (_PBP_OVERRIDES, "nflverse_pbp"),
        ]:
            for tank01_name_lower, alias_name in overrides.items():
                player_id = name_to_id.get(tank01_name_lower)
                if not player_id:
                    logger.warning(
                        "AliasSeed: Tank01 name '%s' not found in players table "
                        "(sync rosters first, or check spelling)",
                        tank01_name_lower,
                    )
                    result.n_failed += 1
                    result.add_event(f"alias_seed_no_player: {tank01_name_lower}")
                    continue

                try:
                    stmt = (
                        pg_insert(PlayerAlias)
                        .values(
                            player_id=player_id,
                            source=source,
                            alias_name=alias_name,
                            match_type="manual",
                            active=True,
                        )
                        .on_conflict_do_update(
                            constraint="uq_player_alias_player_source",
                            set_={"alias_name": alias_name, "active": True},
                        )
                    )
                    await self._db.execute(stmt)
                    result.n_written += 1
                    logger.debug("Seeded alias: %s → %s (%s)", tank01_name_lower, alias_name, source)
                except Exception as exc:
                    logger.error("Alias seed failed %s/%s: %s", tank01_name_lower, source, exc)
                    result.n_failed += 1

        await self._db.commit()
        logger.info(
            "AliasSeed complete: %d written, %d failed",
            result.n_written, result.n_failed,
        )
        return result
