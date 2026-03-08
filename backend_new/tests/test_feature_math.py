"""
Unit tests for feature_math.compute_features_from_logs.

Uses SimpleNamespace to create lightweight log objects — avoiding SQLAlchemy
instrumentation overhead while testing the pure math logic.
"""

import math
from types import SimpleNamespace

import pytest

from app.ml.model_bundle import EBParams
from app.ml.feature_math import compute_features_from_logs

# ── Shared EB params (realistic values from the pkl) ─────────────────────────

EB = EBParams(alpha=5.0, beta=95.0, rz_alpha=2.0, rz_beta=18.0)


def make_log(
    targets=5,
    receptions=4,
    rec_yards=50,
    rec_tds=0,
    long_rec=20,
    snap_pct=0.80,
    rz_targets=1,
    rz_rec_tds=0,
    team="MIN",
    week=1,
) -> SimpleNamespace:
    """Build a minimal game log stub usable by compute_features_from_logs."""
    return SimpleNamespace(
        targets=targets,
        receptions=receptions,
        rec_yards=rec_yards,
        rec_tds=rec_tds,
        long_rec=long_rec,
        snap_pct=snap_pct,
        rz_targets=rz_targets,
        rz_rec_tds=rz_rec_tds,
        team=team,
        week=week,
    )


class TestBasicCompute:
    def setup_method(self):
        self.logs = [
            make_log(targets=6, receptions=5, rec_yards=70, rec_tds=1, week=1),
            make_log(targets=4, receptions=3, rec_yards=40, rec_tds=0, week=2),
            make_log(targets=8, receptions=6, rec_yards=90, rec_tds=1, week=3),
            make_log(targets=5, receptions=4, rec_yards=60, rec_tds=0, week=4),
        ]
        self.feat = compute_features_from_logs(
            logs=self.logs,
            is_te=False,
            team_cum_targets=100,
            team_cum_rz_targets=20,
            eb=EB,
        )

    def test_targets_pg(self):
        # (6 + 4 + 8 + 5) / 4 = 5.75
        assert self.feat["targets_pg"] == pytest.approx(5.75, rel=1e-4)

    def test_yards_pg(self):
        # (70 + 40 + 90 + 60) / 4 = 65.0
        assert self.feat["yards_pg"] == pytest.approx(65.0, rel=1e-4)

    def test_receptions_pg(self):
        # (5 + 3 + 6 + 4) / 4 = 4.5
        assert self.feat["receptions_pg"] == pytest.approx(4.5, rel=1e-4)

    def test_roll3_targets(self):
        # last 3 games: weeks 2,3,4 → (4+8+5)/3 ≈ 5.667
        assert self.feat["roll3_targets"] == pytest.approx((4 + 8 + 5) / 3, rel=1e-4)

    def test_lag_targets(self):
        # most recent log: week 4, targets=5
        assert self.feat["lag_targets"] == pytest.approx(5.0, rel=1e-4)

    def test_lag_yards(self):
        assert self.feat["lag_yards"] == pytest.approx(60.0, rel=1e-4)

    def test_is_te_flag(self):
        assert self.feat["is_te"] is False

    def test_target_share(self):
        # 23 targets / 100 team targets = 0.23
        assert self.feat["target_share"] == pytest.approx(23 / 100, rel=1e-4)

    def test_all_21_features_present(self):
        expected_keys = {
            "targets_pg", "roll3_targets", "yards_pg", "receptions_pg",
            "roll3_yards", "roll3_receptions", "lag_targets", "lag_yards",
            "target_share", "roll3_long_rec", "roll3_target_std",
            "tds_last3", "td_streak", "td_rate_eb", "td_rate_eb_std",
            "is_te", "lag_snap_pct", "roll3_snap_pct",
            "roll3_rz_targets", "rz_target_share", "rz_td_rate_eb",
        }
        assert set(self.feat.keys()) == expected_keys


class TestTdFeatures:
    def test_tds_last3_counts_recent(self):
        logs = [
            make_log(rec_tds=1, week=1),
            make_log(rec_tds=0, week=2),
            make_log(rec_tds=1, week=3),
            make_log(rec_tds=1, week=4),
        ]
        feat = compute_features_from_logs(logs, is_te=False, team_cum_targets=80, team_cum_rz_targets=10, eb=EB)
        # last 3 = weeks 2,3,4: 0+1+1 = 2
        assert feat["tds_last3"] == 2.0

    def test_td_streak_consecutive_from_end(self):
        logs = [
            make_log(rec_tds=0, week=1),
            make_log(rec_tds=1, week=2),
            make_log(rec_tds=1, week=3),
        ]
        feat = compute_features_from_logs(logs, is_te=False, team_cum_targets=60, team_cum_rz_targets=10, eb=EB)
        assert feat["td_streak"] == 2.0

    def test_td_streak_broken_by_zero(self):
        logs = [
            make_log(rec_tds=1, week=1),
            make_log(rec_tds=0, week=2),
            make_log(rec_tds=1, week=3),
        ]
        feat = compute_features_from_logs(logs, is_te=False, team_cum_targets=60, team_cum_rz_targets=10, eb=EB)
        # Streak starts from end: week 3 has TD, but week 2 breaks it → streak=1
        assert feat["td_streak"] == 1.0

    def test_td_streak_no_tds(self):
        logs = [make_log(rec_tds=0, week=w) for w in range(1, 5)]
        feat = compute_features_from_logs(logs, is_te=False, team_cum_targets=80, team_cum_rz_targets=10, eb=EB)
        assert feat["td_streak"] == 0.0


class TestEmpiricalBayesRates:
    def test_td_rate_eb_uses_priors(self):
        # 1 TD across 10 targets + EB priors: alpha=5, beta=95
        # a_post = 1 + 5 = 6, b_post = 9 + 95 = 104
        logs = [make_log(targets=10, rec_tds=1, week=1)]
        feat = compute_features_from_logs(logs, is_te=False, team_cum_targets=50, team_cum_rz_targets=5, eb=EB)
        a_post = 1 + EB.alpha
        b_post = (10 - 1) + EB.beta
        expected = a_post / (a_post + b_post)
        assert feat["td_rate_eb"] == pytest.approx(expected, rel=1e-6)

    def test_td_rate_eb_std_positive(self):
        logs = [make_log(targets=8, rec_tds=0, week=1)]
        feat = compute_features_from_logs(logs, is_te=False, team_cum_targets=50, team_cum_rz_targets=5, eb=EB)
        assert feat["td_rate_eb_std"] > 0

    def test_rz_td_rate_eb_with_rz_data(self):
        # 2 rz_tds, 5 rz_targets; rz_alpha=2, rz_beta=18
        logs = [make_log(rz_targets=5, rz_rec_tds=2, week=1)]
        feat = compute_features_from_logs(logs, is_te=True, team_cum_targets=50, team_cum_rz_targets=20, eb=EB)
        rz_a = 2 + EB.rz_alpha
        rz_b = (5 - 2) + EB.rz_beta
        expected = rz_a / (rz_a + rz_b)
        assert feat["rz_td_rate_eb"] == pytest.approx(expected, rel=1e-6)


class TestSnapFeatures:
    def test_lag_snap_pct_from_last_game(self):
        logs = [
            make_log(snap_pct=0.70, week=1),
            make_log(snap_pct=0.85, week=2),
        ]
        feat = compute_features_from_logs(logs, is_te=False, team_cum_targets=40, team_cum_rz_targets=5, eb=EB)
        assert feat["lag_snap_pct"] == pytest.approx(0.85, rel=1e-4)

    def test_lag_snap_pct_none_when_missing(self):
        logs = [make_log(snap_pct=None, week=1)]
        feat = compute_features_from_logs(logs, is_te=False, team_cum_targets=20, team_cum_rz_targets=5, eb=EB)
        assert feat["lag_snap_pct"] is None

    def test_roll3_snap_pct_averages_available(self):
        logs = [
            make_log(snap_pct=0.6, week=1),
            make_log(snap_pct=None, week=2),  # missing — excluded from average
            make_log(snap_pct=0.8, week=3),
        ]
        feat = compute_features_from_logs(logs, is_te=False, team_cum_targets=50, team_cum_rz_targets=5, eb=EB)
        # Only weeks 1 and 3 contribute (week 2 is None)
        assert feat["roll3_snap_pct"] == pytest.approx((0.6 + 0.8) / 2, rel=1e-4)

    def test_roll3_snap_pct_none_when_all_missing(self):
        logs = [make_log(snap_pct=None, week=w) for w in range(1, 4)]
        feat = compute_features_from_logs(logs, is_te=False, team_cum_targets=40, team_cum_rz_targets=5, eb=EB)
        assert feat["roll3_snap_pct"] is None


class TestTargetShare:
    def test_target_share_none_when_no_team_targets(self):
        logs = [make_log(targets=5, week=1)]
        feat = compute_features_from_logs(logs, is_te=False, team_cum_targets=0, team_cum_rz_targets=5, eb=EB)
        assert feat["target_share"] is None

    def test_rz_target_share_zero_when_no_team_rz(self):
        logs = [make_log(rz_targets=3, week=1)]
        feat = compute_features_from_logs(logs, is_te=False, team_cum_targets=50, team_cum_rz_targets=0, eb=EB)
        assert feat["rz_target_share"] == 0.0


class TestRolling3Features:
    def test_roll3_uses_only_last_3_games(self):
        logs = [
            make_log(targets=10, week=1),  # should be excluded
            make_log(targets=10, week=2),  # should be excluded
            make_log(targets=2, week=3),
            make_log(targets=2, week=4),
            make_log(targets=2, week=5),
        ]
        feat = compute_features_from_logs(logs, is_te=False, team_cum_targets=100, team_cum_rz_targets=10, eb=EB)
        assert feat["roll3_targets"] == pytest.approx(2.0, rel=1e-4)

    def test_roll3_target_std_zero_with_single_game(self):
        # Only 1 game in last3 → std defaults to 0.0
        logs = [make_log(targets=5, week=1)]
        feat = compute_features_from_logs(logs, is_te=False, team_cum_targets=30, team_cum_rz_targets=5, eb=EB)
        assert feat["roll3_target_std"] == 0.0

    def test_roll3_rz_targets_is_sum_not_mean(self):
        # SUM of last 3 rz_targets — matches training (not average)
        logs = [
            make_log(rz_targets=2, week=1),
            make_log(rz_targets=3, week=2),
            make_log(rz_targets=1, week=3),
        ]
        feat = compute_features_from_logs(logs, is_te=False, team_cum_targets=60, team_cum_rz_targets=20, eb=EB)
        assert feat["roll3_rz_targets"] == 6.0  # SUM: 2+3+1

    def test_single_game_still_produces_all_features(self):
        """Edge case: exactly 1 game — lag features equal season totals."""
        logs = [make_log(targets=5, receptions=4, rec_yards=50, week=1)]
        feat = compute_features_from_logs(logs, is_te=True, team_cum_targets=40, team_cum_rz_targets=10, eb=EB)
        assert feat["lag_targets"] == 5.0
        assert feat["targets_pg"] == 5.0
        assert feat["is_te"] is True
