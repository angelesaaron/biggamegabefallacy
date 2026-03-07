"""
seed_draft_rounds.py — Populate players.draft_round from nflreadpy.

Tank01's getNFLTeamRoster does not include draft data. nflreadpy's
load_players() does — and nflverse uses espn_id which is the same
numeric ID as Tank01's playerID, so matching is exact (no name fuzzing).

Usage (from backend_new/):
    python scripts/seed_draft_rounds.py [--dry-run]

Run once after initial roster sync. Re-run each year after the draft
to populate draft_round for incoming rookies.

draft_round values:
  1-7  — drafted round
  0    — undrafted free agent (UDFA)
  NULL — player exists in nflverse but draft info unavailable (rare)
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Allow running from backend_new/ or project root
sys.path.insert(0, str(Path(__file__).parent.parent))

import nflreadpy as nfl
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.player import Player

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def _load_draft_rounds() -> dict[str, int]:
    """
    Fetch player data from nflverse and build espn_id → draft_round map.

    espn_id in nflverse == playerID in Tank01 (both are ESPN numeric IDs).
    Players with no draft entry are treated as UDFA (draft_round=0).
    """
    logger.info("Fetching nflreadpy player data...")
    df = nfl.load_players().to_pandas()

    # Keep rows with a valid ESPN id
    df = df[df["espn_id"].notna()].copy()
    df["espn_id"] = df["espn_id"].astype(float).astype(int).astype(str)

    # draft_round: NaN → 0 (UDFA), otherwise int
    df["draft_round"] = df["draft_round"].fillna(0).astype(int)

    # If a player appears multiple times (rare), keep the highest round number
    # (higher round = more specific; 0 means UDFA and should only stay if no other entry)
    deduped = (
        df.sort_values("draft_round", ascending=False)
        .drop_duplicates(subset=["espn_id"], keep="first")
    )

    return dict(zip(deduped["espn_id"], deduped["draft_round"]))


async def run(dry_run: bool) -> None:
    draft_map = _load_draft_rounds()
    logger.info("Loaded draft data for %d players from nflverse", len(draft_map))

    async with AsyncSessionLocal() as session:
        rows = await session.execute(
            select(Player).where(Player.position.in_(["WR", "TE"]))
        )
        players = rows.scalars().all()

        n_updated = 0
        n_already_set = 0
        n_not_found = 0

        for player in players:
            if player.player_id not in draft_map:
                n_not_found += 1
                continue

            new_round = draft_map[player.player_id]

            if player.draft_round == new_round:
                n_already_set += 1
                continue

            if not dry_run:
                player.draft_round = new_round
            n_updated += 1

        if not dry_run:
            await session.commit()

        mode = "[DRY RUN] " if dry_run else ""
        logger.info(
            "%sResults: %d updated, %d already correct, %d not in nflverse",
            mode, n_updated, n_already_set, n_not_found,
        )
        if dry_run and n_updated > 0:
            logger.info("Re-run without --dry-run to apply changes.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would change without writing to DB",
    )
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
