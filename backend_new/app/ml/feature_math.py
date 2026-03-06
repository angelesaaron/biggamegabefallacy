"""
feature_math.py — Shared feature computation from player game logs.

Used by both FeatureComputeService (regular season, week >= 4) and
SeasonStateService (end-of-season state). The only difference between the two
callers is WHICH logs are passed in — everything else is identical.
"""

from __future__ import annotations

import math
from typing import Optional

from app.ml.model_bundle import EBParams
from app.models.player_game_log import PlayerGameLog


def compute_features_from_logs(
    logs: list[PlayerGameLog],
    is_te: bool,
    team_cum_targets: int,
    team_cum_rz_targets: int,
    eb: EBParams,
) -> dict:
    """
    Compute all 21 model features from a player's game logs.

    logs must be sorted ascending by week and non-empty.
    team_cum_* are WR/TE-only cumulative totals for the player's team,
    keyed by log.team — passed in from the caller after aggregating all logs.

    NaN rules (matching feature_prep.py):
      roll3_target_std → 0.0 when fewer than 2 games (no meaningful variance)
      roll3_rz_targets → SUM not mean (matches notebook 05_new_features.ipynb)
      rz_target_share, rz_td_rate_eb → 0.0 when team has no RZ data
      lag_snap_pct, roll3_snap_pct → None (NaN) when nflverse match failed
      lag_targets, lag_yards → always non-null (at least one game exists)
    """
    n = len(logs)

    # ── Cumulative season totals ──────────────────────────────────────────────
    cum_targets = sum(l.targets for l in logs)
    cum_yards = sum(l.rec_yards for l in logs)
    cum_recs = sum(l.receptions for l in logs)
    cum_tds = sum(l.rec_tds for l in logs)
    cum_rz_targets = sum(l.rz_targets or 0 for l in logs)
    cum_rz_tds = sum(l.rz_rec_tds or 0 for l in logs)

    # ── Per-game averages ─────────────────────────────────────────────────────
    targets_pg = cum_targets / n
    yards_pg = cum_yards / n
    receptions_pg = cum_recs / n

    # ── Rolling 3-game stats ──────────────────────────────────────────────────
    last3 = logs[-3:]
    n3 = len(last3)

    roll3_targets = sum(l.targets for l in last3) / n3
    roll3_yards = sum(l.rec_yards for l in last3) / n3
    roll3_receptions = sum(l.receptions for l in last3) / n3
    roll3_rz_targets = float(sum(l.rz_targets or 0 for l in last3))  # SUM not mean

    long_recs = [l.long_rec for l in last3 if l.long_rec is not None]
    roll3_long_rec: Optional[float] = (
        float(sum(long_recs)) / len(long_recs) if long_recs else 0.0
    )

    if n3 >= 2:
        t3 = [l.targets for l in last3]
        mean_t3 = sum(t3) / n3
        roll3_target_std: float = math.sqrt(
            sum((t - mean_t3) ** 2 for t in t3) / (n3 - 1)
        )
    else:
        roll3_target_std = 0.0

    # ── Lag features (most recent game) ──────────────────────────────────────
    last = logs[-1]
    lag_targets = float(last.targets)
    lag_yards = float(last.rec_yards)
    lag_snap_pct: Optional[float] = (
        float(last.snap_pct) if last.snap_pct is not None else None
    )

    snap_vals = [float(l.snap_pct) for l in last3 if l.snap_pct is not None]
    roll3_snap_pct: Optional[float] = (
        sum(snap_vals) / len(snap_vals) if snap_vals else None
    )

    # ── Streak / momentum ─────────────────────────────────────────────────────
    tds_last3 = float(sum(l.rec_tds for l in last3))
    td_streak = 0
    for log in reversed(logs):
        if log.rec_tds > 0:
            td_streak += 1
        else:
            break

    # ── Empirical Bayes TD rates (params from model bundle — never refit) ─────
    a_post = cum_tds + eb.alpha
    b_post = max(0, cum_targets - cum_tds) + eb.beta
    ab_post = a_post + b_post
    td_rate_eb = a_post / ab_post
    td_rate_eb_std = math.sqrt((a_post * b_post) / (ab_post ** 2 * (ab_post + 1)))

    rz_a = cum_rz_tds + eb.rz_alpha
    rz_b = max(0, cum_rz_targets - cum_rz_tds) + eb.rz_beta
    rz_ab = rz_a + rz_b
    rz_td_rate_eb = rz_a / rz_ab

    # ── Target share (WR/TE only — matches add_target_share() in feature_prep.py)
    target_share: Optional[float] = (
        cum_targets / team_cum_targets if team_cum_targets > 0 else None
    )
    rz_target_share: float = (
        float(cum_rz_targets) / team_cum_rz_targets
        if team_cum_rz_targets > 0
        else 0.0
    )

    return {
        "targets_pg": targets_pg,
        "roll3_targets": roll3_targets,
        "yards_pg": yards_pg,
        "receptions_pg": receptions_pg,
        "roll3_yards": roll3_yards,
        "roll3_receptions": roll3_receptions,
        "lag_targets": lag_targets,
        "lag_yards": lag_yards,
        "target_share": target_share,
        "roll3_long_rec": roll3_long_rec,
        "roll3_target_std": roll3_target_std,
        "tds_last3": tds_last3,
        "td_streak": float(td_streak),
        "td_rate_eb": td_rate_eb,
        "td_rate_eb_std": td_rate_eb_std,
        "is_te": is_te,
        "lag_snap_pct": lag_snap_pct,
        "roll3_snap_pct": roll3_snap_pct,
        "roll3_rz_targets": roll3_rz_targets,
        "rz_target_share": rz_target_share,
        "rz_td_rate_eb": rz_td_rate_eb,
    }
