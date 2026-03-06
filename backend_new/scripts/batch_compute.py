"""
Batch Feature Compute + Predictions
-------------------------------------
Runs feature compute and predictions for all season/week combinations
that have game log data but no features yet.

Run from backend_new/:
    python scripts/batch_compute.py [--seasons 2022 2023 2024 2025]

Also runs season_state_service after each completed season so prior-season
carry-forward is available for the next season's feature compute.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, func

from app.database import AsyncSessionLocal
from app.models.player_game_log import PlayerGameLog
from app.models.player_features import PlayerFeatures
from app.services.feature_compute import FeatureComputeService
from app.services.inference_service import InferenceService
from app.services.season_state_service import SeasonStateService

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def run(seasons: list[int]) -> None:
    async with AsyncSessionLocal() as db:
        # Get all (season, week) combos that have logs
        result = await db.execute(
            select(PlayerGameLog.season, PlayerGameLog.week)
            .distinct()
            .order_by(PlayerGameLog.season, PlayerGameLog.week)
            .where(PlayerGameLog.season.in_(seasons))
        )
        combos = result.all()
        print(f"Season/week combos with game logs: {len(combos)}")

        # Get already-computed (season, week) combos
        result2 = await db.execute(
            select(PlayerFeatures.season, PlayerFeatures.week).distinct()
        )
        already_done = {(r.season, r.week) for r in result2}
        print(f"Already computed: {len(already_done)}")

        to_compute = [(s, w) for s, w in combos if (s, w) not in already_done]
        print(f"To compute: {len(to_compute)}\n")

    total_features = 0
    total_preds = 0

    prev_season = None
    for season, week in to_compute:
        # When moving into a new season (not the first), run season_state for the prior season
        if prev_season is not None and season != prev_season:
            print(f"  → Running season_state for {prev_season}...")
            async with AsyncSessionLocal() as db:
                svc = SeasonStateService(db)
                r = await svc.run(prev_season)
                print(f"    season_state {prev_season}: {r.n_written} written, {r.n_failed} failed")

        async with AsyncSessionLocal() as db:
            feat_svc = FeatureComputeService(db)
            feat_result = await feat_svc.run(season, week)

        async with AsyncSessionLocal() as db:
            pred_svc = InferenceService(db)
            pred_result = await pred_svc.run(season, week)

        total_features += feat_result.n_written
        total_preds += pred_result.n_written

        print(
            f"S{season}W{week:02d}  features={feat_result.n_written:3d} ({feat_result.n_failed} failed)"
            f"  preds={pred_result.n_written:3d} ({pred_result.n_failed} failed)"
            + (f"  [{pred_result.events[0]}]" if pred_result.events else "")
        )
        prev_season = season

    # Run season_state for the last season processed
    if prev_season is not None and prev_season != seasons[-1]:
        print(f"\n  → Running season_state for {prev_season}...")
        async with AsyncSessionLocal() as db:
            svc = SeasonStateService(db)
            r = await svc.run(prev_season)
            print(f"    season_state {prev_season}: {r.n_written} written, {r.n_failed} failed")

    # Run season_state for all completed seasons (except the current one — 2025 is done too)
    for s in seasons:
        print(f"\n  → Running season_state for {s}...")
        async with AsyncSessionLocal() as db:
            svc = SeasonStateService(db)
            r = await svc.run(s)
            print(f"    season_state {s}: {r.n_written} written, {r.n_updated} updated, {r.n_failed} failed")

    print(f"\n=== Done ===")
    print(f"Total features computed : {total_features}")
    print(f"Total predictions written: {total_preds}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seasons", nargs="+", type=int, default=[2022, 2023, 2024, 2025])
    args = parser.parse_args()
    asyncio.run(run(args.seasons))
