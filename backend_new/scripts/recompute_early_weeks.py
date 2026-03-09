"""
Recompute features + predictions for weeks 1-3 across all seasons.

Fixes: features were computed before draft sync ran, so all rookies defaulted
to the rd0 (UDFA) bucket. Now that draft_round is populated, re-running
feature compute will assign the correct bucket per draft round.

Run from backend_new/:
    python scripts/recompute_early_weeks.py [--seasons 2022 2023 2024 2025]
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal
from app.services.feature_compute import FeatureComputeService
from app.services.inference_service import InferenceService

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

EARLY_WEEKS = [1, 2, 3]


async def run(seasons: list[int]) -> None:
    print(f"Recomputing early-season features + predictions for weeks {EARLY_WEEKS}")
    print(f"Seasons: {seasons}\n")

    for season in seasons:
        for week in EARLY_WEEKS:
            async with AsyncSessionLocal() as db:
                feat_result = await FeatureComputeService(db).run(season, week)
                await db.commit()

            async with AsyncSessionLocal() as db:
                pred_result = await InferenceService(db).run(season, week)
                await db.commit()

            print(
                f"S{season}W{week}  "
                f"features={feat_result.n_written:3d} updated={feat_result.n_updated:3d} failed={feat_result.n_failed}"
                f"  preds={pred_result.n_written:3d} updated={pred_result.n_updated:3d} failed={pred_result.n_failed}"
            )

    print("\nDone.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seasons", nargs="+", type=int, default=[2022, 2023, 2024, 2025])
    args = parser.parse_args()
    asyncio.run(run(args.seasons))
