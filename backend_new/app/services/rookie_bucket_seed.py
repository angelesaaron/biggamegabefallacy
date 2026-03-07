"""
RookieBucketSeedService — populates the rookie_buckets table.

Values are hard-coded from ml/data/rookie_buckets.csv (a static training artifact).
They only change if the model is retrained, at which point this file is updated too.

Safe to re-run — upserts on (draft_round, pos).
"""

from __future__ import annotations

import logging

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rookie_bucket import RookieBucket
from app.services.sync_result import SyncResult
from app.utils.db_utils import execute_upsert

logger = logging.getLogger(__name__)

# Derived from ml/data/rookie_buckets.csv — do not edit by hand.
# Columns match CARRY_FEATURES in ml/early_season.py.
# draft_round 0 = UDFA. Note: no round-7 TE row in training data.
_BUCKETS: list[dict] = [
    {"draft_round": 0, "pos": "TE", "targets_pg": 3.0, "yards_pg": 18.25, "receptions_pg": 2.0, "roll3_targets": 3.0, "roll3_yards": 18.25, "roll3_receptions": 2.0, "lag_targets": 3.0, "lag_yards": 16.5, "target_share": 0.15, "roll3_long_rec": 12.0, "roll3_target_std": 0.7071067811865476, "tds_last3": 0.0, "td_streak": 0.0, "td_rate_eb": 0.04840741917943441, "td_rate_eb_std": 0.011290766982585217, "lag_snap_pct": 0.59, "roll3_snap_pct": 0.59, "roll3_rz_targets": 0.0, "rz_target_share": 0.0, "rz_td_rate_eb": 0.2476481750478776},
    {"draft_round": 0, "pos": "WR", "targets_pg": 4.0, "yards_pg": 33.0, "receptions_pg": 3.0, "roll3_targets": 4.0, "roll3_yards": 33.0, "roll3_receptions": 3.0, "lag_targets": 4.0, "lag_yards": 32.0, "target_share": 0.15, "roll3_long_rec": 17.0, "roll3_target_std": 1.4142135623730951, "tds_last3": 0.0, "td_streak": 0.0, "td_rate_eb": 0.048542131190093214, "td_rate_eb_std": 0.011321342789816072, "lag_snap_pct": 0.475, "roll3_snap_pct": 0.4875, "roll3_rz_targets": 0.0, "rz_target_share": 0.0, "rz_td_rate_eb": 0.2476481750478776},
    {"draft_round": 1, "pos": "TE", "targets_pg": 4.0, "yards_pg": 32.0, "receptions_pg": 4.0, "roll3_targets": 4.0, "roll3_yards": 32.0, "roll3_receptions": 4.0, "lag_targets": 4.0, "lag_yards": 33.0, "target_share": 0.203125, "roll3_long_rec": 13.0, "roll3_target_std": 1.4142135623730951, "tds_last3": 0.0, "td_streak": 0.0, "td_rate_eb": 0.04800773226936553, "td_rate_eb_std": 0.011200021492496704, "lag_snap_pct": 0.75, "roll3_snap_pct": 0.74, "roll3_rz_targets": 0.0, "rz_target_share": 0.0, "rz_td_rate_eb": 0.2476481750478776},
    {"draft_round": 1, "pos": "WR", "targets_pg": 6.0, "yards_pg": 52.25, "receptions_pg": 4.0, "roll3_targets": 6.0, "roll3_yards": 52.25, "roll3_receptions": 4.0, "lag_targets": 6.0, "lag_yards": 54.5, "target_share": 0.2954963235294118, "roll3_long_rec": 22.5, "roll3_target_std": 1.4142135623730951, "tds_last3": 0.0, "td_streak": 0.0, "td_rate_eb": 0.04840741917943441, "td_rate_eb_std": 0.011244551074074023, "lag_snap_pct": 0.795, "roll3_snap_pct": 0.795, "roll3_rz_targets": 0.0, "rz_target_share": 0.0, "rz_td_rate_eb": 0.2476481750478776},
    {"draft_round": 2, "pos": "TE", "targets_pg": 4.0, "yards_pg": 27.5, "receptions_pg": 3.0, "roll3_targets": 4.0, "roll3_yards": 27.5, "roll3_receptions": 3.0, "lag_targets": 4.0, "lag_yards": 27.0, "target_share": 0.140625, "roll3_long_rec": 11.5, "roll3_target_std": 1.4142135623730951, "tds_last3": 0.0, "td_streak": 0.0, "td_rate_eb": 0.04827345279337337, "td_rate_eb_std": 0.011260355710293303, "lag_snap_pct": 0.72, "roll3_snap_pct": 0.71, "roll3_rz_targets": 0.0, "rz_target_share": 0.0, "rz_td_rate_eb": 0.2476481750478776},
    {"draft_round": 2, "pos": "WR", "targets_pg": 5.5, "yards_pg": 38.5, "receptions_pg": 4.0, "roll3_targets": 5.5, "roll3_yards": 38.5, "roll3_receptions": 4.0, "lag_targets": 5.0, "lag_yards": 34.5, "target_share": 0.21052631578947367, "roll3_long_rec": 18.0, "roll3_target_std": 2.1213203435596424, "tds_last3": 0.0, "td_streak": 0.0, "td_rate_eb": 0.04827345279337337, "td_rate_eb_std": 0.01123010764990045, "lag_snap_pct": 0.79, "roll3_snap_pct": 0.78, "roll3_rz_targets": 0.0, "rz_target_share": 0.0, "rz_td_rate_eb": 0.2476481750478776},
    {"draft_round": 3, "pos": "TE", "targets_pg": 3.0, "yards_pg": 23.0, "receptions_pg": 2.0, "roll3_targets": 3.0, "roll3_yards": 23.0, "roll3_receptions": 2.0, "lag_targets": 3.0, "lag_yards": 23.0, "target_share": 0.13513513513513514, "roll3_long_rec": 14.0, "roll3_target_std": 2.1213203435596424, "tds_last3": 0.0, "td_streak": 0.0, "td_rate_eb": 0.04840741917943441, "td_rate_eb_std": 0.011290766982585217, "lag_snap_pct": 0.64, "roll3_snap_pct": 0.67, "roll3_rz_targets": 0.0, "rz_target_share": 0.0, "rz_td_rate_eb": 0.2476481750478776},
    {"draft_round": 3, "pos": "WR", "targets_pg": 4.0, "yards_pg": 30.0, "receptions_pg": 3.0, "roll3_targets": 4.0, "roll3_yards": 30.0, "roll3_receptions": 3.0, "lag_targets": 4.0, "lag_yards": 30.0, "target_share": 0.16666666666666666, "roll3_long_rec": 17.0, "roll3_target_std": 1.4142135623730951, "tds_last3": 0.0, "td_streak": 0.0, "td_rate_eb": 0.04840741917943441, "td_rate_eb_std": 0.011260355710293303, "lag_snap_pct": 0.75, "roll3_snap_pct": 0.75, "roll3_rz_targets": 0.0, "rz_target_share": 0.0, "rz_td_rate_eb": 0.2476481750478776},
    {"draft_round": 4, "pos": "TE", "targets_pg": 3.0, "yards_pg": 18.0, "receptions_pg": 2.0, "roll3_targets": 3.0, "roll3_yards": 18.0, "roll3_receptions": 2.0, "lag_targets": 3.0, "lag_yards": 15.0, "target_share": 0.1333570412517781, "roll3_long_rec": 10.5, "roll3_target_std": 1.4142135623730951, "tds_last3": 0.0, "td_streak": 0.0, "td_rate_eb": 0.04834043598640389, "td_rate_eb_std": 0.011260355710293303, "lag_snap_pct": 0.615, "roll3_snap_pct": 0.625, "roll3_rz_targets": 0.0, "rz_target_share": 0.0, "rz_td_rate_eb": 0.2476481750478776},
    {"draft_round": 4, "pos": "WR", "targets_pg": 4.0, "yards_pg": 31.0, "receptions_pg": 3.0, "roll3_targets": 4.0, "roll3_yards": 31.0, "roll3_receptions": 3.0, "lag_targets": 4.0, "lag_yards": 31.0, "target_share": 0.16666666666666666, "roll3_long_rec": 14.0, "roll3_target_std": 1.4142135623730951, "tds_last3": 0.0, "td_streak": 0.0, "td_rate_eb": 0.04840741917943441, "td_rate_eb_std": 0.011260355710293303, "lag_snap_pct": 0.7, "roll3_snap_pct": 0.645, "roll3_rz_targets": 0.0, "rz_target_share": 0.0, "rz_td_rate_eb": 0.2476481750478776},
    {"draft_round": 5, "pos": "TE", "targets_pg": 2.0, "yards_pg": 13.0, "receptions_pg": 1.75, "roll3_targets": 2.0, "roll3_yards": 13.0, "roll3_receptions": 1.75, "lag_targets": 2.0, "lag_yards": 14.5, "target_share": 0.07334525939177103, "roll3_long_rec": 9.75, "roll3_target_std": 1.0606601717798214, "tds_last3": 0.0, "td_streak": 0.0, "td_rate_eb": 0.048542131190093214, "td_rate_eb_std": 0.011321342789816072, "lag_snap_pct": 0.585, "roll3_snap_pct": 0.5774999999999999, "roll3_rz_targets": 0.0, "rz_target_share": 0.0, "rz_td_rate_eb": 0.2476481750478776},
    {"draft_round": 5, "pos": "WR", "targets_pg": 3.0, "yards_pg": 26.0, "receptions_pg": 2.0, "roll3_targets": 3.0, "roll3_yards": 26.0, "roll3_receptions": 2.0, "lag_targets": 3.0, "lag_yards": 26.0, "target_share": 0.14545454545454545, "roll3_long_rec": 18.5, "roll3_target_std": 0.7071067811865476, "tds_last3": 0.0, "td_streak": 0.0, "td_rate_eb": 0.04840741917943441, "td_rate_eb_std": 0.011290766982585217, "lag_snap_pct": 0.63, "roll3_snap_pct": 0.62, "roll3_rz_targets": 0.0, "rz_target_share": 0.0, "rz_td_rate_eb": 0.2476481750478776},
    {"draft_round": 6, "pos": "TE", "targets_pg": 4.5, "yards_pg": 27.5, "receptions_pg": 2.5, "roll3_targets": 4.5, "roll3_yards": 27.5, "roll3_receptions": 2.5, "lag_targets": 4.5, "lag_yards": 27.5, "target_share": 0.1039426523297491, "roll3_long_rec": 17.25, "roll3_target_std": 1.4142135623730951, "tds_last3": 0.0, "td_streak": 0.0, "td_rate_eb": 0.04840779199173329, "td_rate_eb_std": 0.011259675104270448, "lag_snap_pct": 0.545, "roll3_snap_pct": 0.51, "roll3_rz_targets": 0.0, "rz_target_share": 0.0, "rz_td_rate_eb": 0.2476481750478776},
    {"draft_round": 6, "pos": "WR", "targets_pg": 2.5, "yards_pg": 19.0, "receptions_pg": 2.0, "roll3_targets": 2.5, "roll3_yards": 19.0, "roll3_receptions": 2.0, "lag_targets": 2.0, "lag_yards": 19.0, "target_share": 0.10204081632653061, "roll3_long_rec": 13.0, "roll3_target_std": 1.0606601717798214, "tds_last3": 0.0, "td_streak": 0.0, "td_rate_eb": 0.048542131190093214, "td_rate_eb_std": 0.011321342789816072, "lag_snap_pct": 0.39, "roll3_snap_pct": 0.39, "roll3_rz_targets": 0.0, "rz_target_share": 0.0, "rz_td_rate_eb": 0.2476481750478776},
    {"draft_round": 7, "pos": "WR", "targets_pg": 3.0, "yards_pg": 22.75, "receptions_pg": 2.25, "roll3_targets": 3.0, "roll3_yards": 22.75, "roll3_receptions": 2.25, "lag_targets": 3.0, "lag_yards": 18.0, "target_share": 0.13597560975609757, "roll3_long_rec": 15.75, "roll3_target_std": 1.4142135623730951, "tds_last3": 0.0, "td_streak": 0.0, "td_rate_eb": 0.04827345279337337, "td_rate_eb_std": 0.011259675104270448, "lag_snap_pct": 0.46, "roll3_snap_pct": 0.4, "roll3_rz_targets": 0.0, "rz_target_share": 0.0, "rz_td_rate_eb": 0.2476481750478776},
]


class RookieBucketSeedService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def run(self) -> SyncResult:
        result = SyncResult()

        for bucket in _BUCKETS:
            stmt = (
                pg_insert(RookieBucket)
                .values(**bucket)
                .on_conflict_do_update(
                    constraint="uq_rookie_bucket",
                    set_={k: v for k, v in bucket.items() if k not in ("draft_round", "pos")},
                )
            )
            try:
                w, u = await execute_upsert(self._db, stmt)
                result.n_written += w
                result.n_updated += u
            except Exception as exc:
                logger.error(
                    "RookieBucketSeed failed round=%s pos=%s: %s",
                    bucket["draft_round"], bucket["pos"], exc,
                )
                result.n_failed += 1

        logger.info(
            "RookieBucketSeed: %d written, %d updated, %d failed",
            result.n_written, result.n_updated, result.n_failed,
        )
        return result
