"""
InferenceService — runs XGBoost inference + calibration and writes to predictions.

Pipeline per call:
  1. Bulk-fetch all player_features rows for (season, week, feature_version='v2')
  2. Build numpy matrix in bundle['features'] order — None → np.nan
  3. XGBoost raw_probs = model.predict_proba(X)[:, 1]
  4. Calibrate: beta calibration (default) or temperature scaling
  5. Apply early-season week scalar
  6. Bulk-upsert to predictions — safe to re-run after a model retrain

model_odds and favor are NOT stored — they are computed at query time from final_prob.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import numpy as np
from scipy.special import expit, logit
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.ml.model_bundle import load_bundle
from app.models.player_features import PlayerFeatures
from app.models.prediction import Prediction
from app.services.sync_result import SyncResult

logger = logging.getLogger(__name__)

# Snap features are expected to be NaN for some players — not an error.
_SNAP_FEATURES = frozenset({"lag_snap_pct", "roll3_snap_pct"})


class InferenceService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def run(self, season: int, week: int) -> SyncResult:
        result = SyncResult()

        try:
            bundle = load_bundle()
        except FileNotFoundError as exc:
            result.n_failed += 1
            result.add_event(f"model_bundle_not_found: {exc}")
            logger.error("InferenceService aborted: %s", exc)
            return result

        # ── Fetch feature rows ────────────────────────────────────────────────
        rows = await self._db.execute(
            select(PlayerFeatures)
            .where(PlayerFeatures.season == season)
            .where(PlayerFeatures.week == week)
            .where(PlayerFeatures.feature_version == "v2")
        )
        feature_rows: list[PlayerFeatures] = list(rows.scalars().all())

        if not feature_rows:
            result.add_event(
                f"no_feature_rows S{season}W{week} v2 — run compute/features first"
            )
            return result

        # ── Extract bundle components (single load) ───────────────────────────
        model = bundle["model"]
        feature_names: list[str] = bundle["features"]
        best_cal: str = bundle.get("best_calibration", "beta")
        tau: float = float(bundle.get("tau", 1.0))
        beta_cal = bundle.get("beta_calibrator") if best_cal == "beta" else None
        scalars: dict = bundle.get(
            "early_season_scalars", {"wk1": 1.0, "wk2_3": 1.0, "wk4_plus": 1.0}
        )

        scalar_key = "wk1" if week == 1 else ("wk2_3" if week <= 3 else "wk4_plus")
        week_scalar = float(scalars.get(scalar_key, 1.0))

        # ── Build feature matrix ──────────────────────────────────────────────
        n_rows = len(feature_rows)
        n_features = len(feature_names)
        X = np.full((n_rows, n_features), np.nan, dtype=np.float64)

        n_snap_nan = 0
        n_unexpected_nan = 0

        for i, row in enumerate(feature_rows):
            for j, fname in enumerate(feature_names):
                val = getattr(row, fname, None)
                if val is None:
                    if fname in _SNAP_FEATURES:
                        n_snap_nan += 1
                    else:
                        n_unexpected_nan += 1
                    # Leave as np.nan — XGBoost handles missing values natively
                else:
                    X[i, j] = float(val)

        if n_snap_nan > 0:
            logger.warning(
                "S%d W%d: %d snap feature NaN values (nflverse match failures) — OK",
                season, week, n_snap_nan,
            )
        if n_unexpected_nan > 0:
            logger.error(
                "S%d W%d: %d unexpected NaN values in non-snap features — "
                "check feature compute completeness",
                season, week, n_unexpected_nan,
            )

        # ── XGBoost inference (thread to avoid blocking async loop) ──────────
        raw_probs: np.ndarray = await asyncio.to_thread(_predict_proba, model, X)

        # ── Calibration ───────────────────────────────────────────────────────
        if best_cal == "beta" and beta_cal is not None:
            calibrated_probs: np.ndarray = await asyncio.to_thread(
                _apply_beta_cal, beta_cal, raw_probs
            )
        else:
            calibrated_probs = _apply_temperature_scaling(raw_probs, tau)

        # ── Week scalar ───────────────────────────────────────────────────────
        final_probs: np.ndarray = np.clip(calibrated_probs * week_scalar, 0.0, 1.0)

        # ── Bulk upsert predictions ───────────────────────────────────────────
        for i, feat_row in enumerate(feature_rows):
            completeness = (
                float(feat_row.completeness_score)
                if feat_row.completeness_score is not None
                else None
            )
            values = {
                "player_id": feat_row.player_id,
                "season": season,
                "week": week,
                "model_version": settings.MODEL_VERSION,
                "feature_row_id": feat_row.id,
                "raw_prob": float(raw_probs[i]),
                "calibrated_prob": float(calibrated_probs[i]),
                "week_scalar": week_scalar,
                "final_prob": float(final_probs[i]),
                "completeness_score": completeness,
                "is_low_confidence": (completeness or 1.0) < 0.75,
            }
            update_cols = {
                k: v for k, v in values.items()
                if k not in ("player_id", "season", "week", "model_version")
            }
            try:
                stmt = (
                    pg_insert(Prediction)
                    .values(**values)
                    .on_conflict_do_update(
                        constraint="uq_prediction", set_=update_cols
                    )
                )
                await self._db.execute(stmt)
                result.n_written += 1
            except Exception as exc:
                logger.error(
                    "Prediction upsert failed %s S%d W%d: %s",
                    feat_row.player_id, season, week, exc,
                )
                result.n_failed += 1
                result.add_event(f"prediction_error:{feat_row.player_id}:{exc}")

        await self._db.commit()
        logger.info(
            "InferenceService S%d W%d: written=%d failed=%d "
            "scalar=%.4f cal=%s n_players=%d",
            season, week, result.n_written, result.n_failed,
            week_scalar, best_cal, n_rows,
        )
        result.add_event(
            f"week_scalar={week_scalar:.4f} calibration={best_cal} "
            f"n_players={n_rows} snap_nan={n_snap_nan}"
        )
        return result


# ── Synchronous inference helpers (called via asyncio.to_thread) ──────────────

def _predict_proba(model, X: np.ndarray) -> np.ndarray:
    return model.predict_proba(X)[:, 1]


def _apply_beta_cal(bc, raw_probs: np.ndarray) -> np.ndarray:
    return bc.predict(raw_probs.reshape(-1, 1))


def _apply_temperature_scaling(raw_probs: np.ndarray, tau: float) -> np.ndarray:
    clipped = np.clip(raw_probs, 1e-6, 1.0 - 1e-6)
    return expit(logit(clipped) / tau)
