"""
ModelBundle — loads and caches the XGBoost v2 pickle at module level.

The bundle is a dict produced by ml/train.py + ml/calibrate.py and contains:
  model                 — XGBClassifier
  features              — ordered list of 21 feature names (order matters for XGBoost)
  alpha_eb              — Beta-Binomial alpha for anytime TD rate  (flat top-level key)
  beta_eb               — Beta-Binomial beta  for anytime TD rate
  rz_alpha_eb           — Beta-Binomial alpha for RZ TD rate (may be None if not trained)
  rz_beta_eb            — Beta-Binomial beta  for RZ TD rate
  tau                   — float, temperature scaling parameter
  beta_calibrator       — BetaCalibration instance (betacal)
  best_calibration      — 'beta' or 'temperature'
  early_season_scalars  — {wk1, wk2_3, wk4_plus}

EB parameters are fit once on the training set and saved here.
They must NEVER be refit on live data.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import joblib

from app.config import settings

logger = logging.getLogger(__name__)

_bundle_cache: dict | None = None


@dataclass(frozen=True)
class EBParams:
    """Empirical Bayes Beta-Binomial parameters — loaded from pkl, never refit."""

    alpha: float    # anytime TD: posterior alpha
    beta: float     # anytime TD: posterior beta
    rz_alpha: float  # red zone TD: posterior alpha (0 if not trained)
    rz_beta: float   # red zone TD: posterior beta (0 if not trained)


def load_bundle() -> dict:
    """Load and return the model bundle, caching after the first call."""
    global _bundle_cache
    if _bundle_cache is None:
        path = settings.resolved_model_path()
        if not path.exists():
            raise FileNotFoundError(
                f"Model bundle not found at {path}. "
                "Set MODEL_PATH in .env or run ml/train.py + ml/calibrate.py."
            )
        _bundle_cache = joblib.load(path)
        logger.info("Model bundle loaded from %s (version=%s)", path, settings.MODEL_VERSION)
    return _bundle_cache


def get_eb_params() -> EBParams:
    """Extract EB parameters from the cached model bundle.

    Keys are flat top-level strings — alpha_eb, beta_eb, rz_alpha_eb, rz_beta_eb —
    as saved by ml/train.py. rz_* may be None if the model was trained without RZ
    features; they default to 0 so the EB formula degrades gracefully.
    """
    b = load_bundle()
    return EBParams(
        alpha=float(b["alpha_eb"]),
        beta=float(b["beta_eb"]),
        rz_alpha=float(b["rz_alpha_eb"] or 0),
        rz_beta=float(b["rz_beta_eb"] or 0),
    )


def get_model():
    """Return the XGBClassifier from the bundle."""
    return load_bundle()["model"]


def get_feature_names() -> list[str]:
    """Return the ordered feature name list — column order matters for XGBoost."""
    return load_bundle()["features"]


def get_calibrator():
    """Return the beta calibrator, or None if temperature scaling is preferred."""
    b = load_bundle()
    if b.get("best_calibration", "beta") == "beta":
        return b["beta_calibrator"]
    return None


def get_tau() -> float:
    """Return the temperature scaling parameter tau."""
    return float(load_bundle().get("tau", 1.0))


def get_week_scalars() -> dict:
    """Return the early-season week-group scalars from the bundle."""
    return load_bundle().get(
        "early_season_scalars",
        {"wk1": 1.0, "wk2_3": 1.0, "wk4_plus": 1.0},
    )
