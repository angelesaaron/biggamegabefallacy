"""
FeatureComputeService — production translation of feature_prep.py + early_season.py.

For weeks 4+: compute all 21 features from in-season game_logs for weeks 1..week-1.
For weeks 1-3: resolve via three paths (matching early_season.py exactly):
  1. carry_forward  — player has prior-season state + same team → use all CARRY_FEATURES
  2. team_changer   — player has prior-season state + different team → zero VOLUME_FEATURES
  3. rookie         — no prior-season state → draft-round/pos bucket values

EB parameters come from the model bundle (never refit on live data).
Feature math is in app.ml.feature_math (shared with SeasonStateService).
Writes to player_features with feature_version='v2'.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.feature_math import compute_features_from_logs
from app.ml.model_bundle import EBParams, get_eb_params
from app.models.player import Player
from app.models.player_features import PlayerFeatures
from app.models.player_game_log import PlayerGameLog
from app.models.player_season_state import PlayerSeasonState
from app.models.rookie_bucket import RookieBucket
from app.models.team_game_stats import TeamGameStats
from app.services.sync_result import SyncResult

logger = logging.getLogger(__name__)

FEATURE_VERSION = "v2"

# Volume features zeroed (NaN) for team-changers — new system, unknown role.
# Skill / rate features are kept — ability travels with the player.
VOLUME_FEATURES: frozenset[str] = frozenset({
    "targets_pg", "yards_pg", "receptions_pg",
    "roll3_targets", "roll3_yards", "roll3_receptions",
    "lag_targets", "lag_yards",
    "target_share",
    "roll3_rz_targets", "rz_target_share",
    "lag_snap_pct", "roll3_snap_pct",
})

# 21 model features — ordering matches FEATURES in feature_prep.py.
ALL_FEATURES: list[str] = [
    "targets_pg", "roll3_targets",
    "yards_pg", "receptions_pg",
    "roll3_yards", "roll3_receptions",
    "lag_targets", "lag_yards",
    "target_share",
    "roll3_long_rec", "roll3_target_std",
    "tds_last3", "td_streak",
    "td_rate_eb", "td_rate_eb_std",
    "is_te",
    "lag_snap_pct", "roll3_snap_pct",
    "roll3_rz_targets", "rz_target_share", "rz_td_rate_eb",
]


def _completeness_score(feat: dict) -> float:
    non_null = sum(1 for f in ALL_FEATURES if feat.get(f) is not None)
    return round(non_null / len(ALL_FEATURES), 2)


def _to_float(val) -> Optional[float]:
    return float(val) if val is not None else None


class FeatureComputeService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def run(self, season: int, week: int) -> SyncResult:
        result = SyncResult()

        try:
            eb = get_eb_params()
        except FileNotFoundError as exc:
            result.n_failed += 1
            result.add_event(f"model_bundle_not_found: {exc}")
            logger.error("FeatureCompute aborted: %s", exc)
            return result

        players = await self._get_players()
        if not players:
            result.add_event("no_active_wr_te_players")
            return result

        if week <= 3:
            await self._compute_early_season(players, season, week, eb, result)
        else:
            await self._compute_regular_season(players, season, week, eb, result)

        await self._db.commit()
        logger.info(
            "FeatureCompute S%d W%d: written=%d skipped=%d failed=%d",
            season, week, result.n_written, result.n_skipped, result.n_failed,
        )
        return result

    # ── Queries ───────────────────────────────────────────────────────────────

    async def _get_players(self) -> list[Player]:
        rows = await self._db.execute(
            select(Player)
            .where(Player.position.in_(["WR", "TE"]))
            .where(Player.active.is_(True))
        )
        return list(rows.scalars().all())

    async def _get_team_rz_all_pos_before(
        self, season: int, week: int
    ) -> dict[str, int]:
        """Cumulative all-position RZ targets per team for weeks < week."""
        rows = await self._db.execute(
            select(TeamGameStats.team, TeamGameStats.team_rz_targets_all_pos)
            .where(TeamGameStats.season == season)
            .where(TeamGameStats.week < week)
            .where(TeamGameStats.team_rz_targets_all_pos.isnot(None))
        )
        totals: dict[str, int] = defaultdict(int)
        for row in rows:
            totals[row.team] += row.team_rz_targets_all_pos
        return totals

    async def _get_season_logs_before(
        self, season: int, week: int
    ) -> list[PlayerGameLog]:
        rows = await self._db.execute(
            select(PlayerGameLog)
            .where(PlayerGameLog.season == season)
            .where(PlayerGameLog.week < week)
            .order_by(PlayerGameLog.player_id, PlayerGameLog.week)
        )
        return list(rows.scalars().all())

    async def _get_prior_states(self, season: int) -> dict[str, PlayerSeasonState]:
        rows = await self._db.execute(
            select(PlayerSeasonState).where(PlayerSeasonState.join_season == season)
        )
        return {s.player_id: s for s in rows.scalars().all()}

    async def _get_rookie_buckets(self) -> dict[tuple[int, str], RookieBucket]:
        rows = await self._db.execute(select(RookieBucket))
        return {(b.draft_round, b.pos): b for b in rows.scalars().all()}

    # ── Regular season (week >= 4) ────────────────────────────────────────────

    async def _compute_regular_season(
        self,
        players: list[Player],
        season: int,
        week: int,
        eb: EBParams,
        result: SyncResult,
    ) -> None:
        logs = await self._get_season_logs_before(season, week)
        # All-position team RZ totals — correct denominator for rz_target_share
        team_cum_rz_all_pos = await self._get_team_rz_all_pos_before(season, week)

        # Group logs by player_id (sorted by week via query ORDER BY)
        player_logs: dict[str, list[PlayerGameLog]] = defaultdict(list)
        for log in logs:
            player_logs[log.player_id].append(log)

        # Build team cumulative totals from log.team — NOT player.team.
        # A mid-season trade means old-team logs must count toward the old
        # team's denominator so target_share is correct for each team.
        team_cum_targets: dict[str, int] = defaultdict(int)
        for log in logs:
            if log.team:
                team_cum_targets[log.team] += log.targets

        for player in players:
            pid = player.player_id
            plogs = player_logs.get(pid)

            if not plogs:
                result.n_skipped += 1
                continue

            # Use the player's most recent team from their logs as the
            # denominator key (matches training: team column on that row).
            current_team = plogs[-1].team

            try:
                feat = compute_features_from_logs(
                    logs=plogs,
                    is_te=player.is_te,
                    team_cum_targets=team_cum_targets.get(current_team, 0),
                    team_cum_rz_targets=team_cum_rz_all_pos.get(current_team, 0),
                    eb=eb,
                )
                score = _completeness_score(feat)
                await self._upsert_features(
                    player_id=pid,
                    season=season,
                    week=week,
                    feat=feat,
                    completeness_score=score,
                    is_early_season=False,
                    carry_forward_used=False,
                )
                result.n_written += 1
            except Exception as exc:
                logger.error(
                    "Feature compute failed %s S%d W%d: %s", pid, season, week, exc
                )
                result.n_failed += 1
                result.add_event(f"compute_error:{pid}:{exc}")

    # ── Early season (weeks 1-3) ──────────────────────────────────────────────

    async def _compute_early_season(
        self,
        players: list[Player],
        season: int,
        week: int,
        eb: EBParams,
        result: SyncResult,
    ) -> None:
        prior_states = await self._get_prior_states(season)
        buckets = await self._get_rookie_buckets()

        counts: dict[str, int] = {
            "carry_forward": 0, "team_changer": 0, "rookie": 0, "skipped": 0,
        }

        for player in players:
            pid = player.player_id
            prior = prior_states.get(pid)

            # ── Determine resolution path (mirrors early_season.py) ────────────
            if prior is not None:
                team_changed = (
                    prior.team is not None
                    and player.team is not None
                    and player.team != prior.team
                )
                resolution = "team_changer" if team_changed else "carry_forward"
            else:
                resolution = "rookie"

            # ── Build feature dict from carry-forward source ───────────────────
            if resolution in ("carry_forward", "team_changer"):
                feat = self._features_from_prior(prior, player.is_te)  # type: ignore[arg-type]
                if resolution == "team_changer":
                    for col in VOLUME_FEATURES:
                        feat[col] = None  # NaN — XGBoost handles natively
                carry_used = True
                counts[resolution] += 1

            else:  # rookie / new entrant
                draft_round = player.draft_round if player.draft_round is not None else 0
                pos = "TE" if player.is_te else "WR"
                bucket = buckets.get((draft_round, pos)) or buckets.get((0, pos))
                if bucket is None:
                    logger.warning(
                        "No rookie bucket for round=%d pos=%s player=%s — skipping",
                        draft_round, pos, pid,
                    )
                    result.n_skipped += 1
                    counts["skipped"] += 1
                    continue
                feat = self._features_from_bucket(bucket, player.is_te)
                carry_used = False
                counts["rookie"] += 1

            try:
                score = _completeness_score(feat)
                await self._upsert_features(
                    player_id=pid,
                    season=season,
                    week=week,
                    feat=feat,
                    completeness_score=score,
                    is_early_season=True,
                    carry_forward_used=carry_used,
                )
                result.n_written += 1
            except Exception as exc:
                logger.error(
                    "Early-season feature upsert failed %s S%d W%d: %s",
                    pid, season, week, exc,
                )
                result.n_failed += 1
                result.add_event(f"early_season_error:{pid}:{exc}")

        logger.info(
            "Early-season W%d: carry=%d changer=%d rookie=%d skipped=%d",
            week, counts["carry_forward"], counts["team_changer"],
            counts["rookie"], counts["skipped"],
        )
        result.add_event(
            f"W{week} carry={counts['carry_forward']} "
            f"changer={counts['team_changer']} "
            f"rookie={counts['rookie']} skipped={counts['skipped']}"
        )

    # ── Feature-dict builders (early season only) ─────────────────────────────

    def _features_from_prior(self, prior: PlayerSeasonState, is_te: bool) -> dict:
        return {
            "targets_pg": _to_float(prior.targets_pg),
            "roll3_targets": _to_float(prior.roll3_targets),
            "yards_pg": _to_float(prior.yards_pg),
            "receptions_pg": _to_float(prior.receptions_pg),
            "roll3_yards": _to_float(prior.roll3_yards),
            "roll3_receptions": _to_float(prior.roll3_receptions),
            "lag_targets": _to_float(prior.lag_targets),
            "lag_yards": _to_float(prior.lag_yards),
            "target_share": _to_float(prior.target_share),
            "roll3_long_rec": _to_float(prior.roll3_long_rec),
            "roll3_target_std": _to_float(prior.roll3_target_std),
            "tds_last3": _to_float(prior.tds_last3),
            "td_streak": _to_float(prior.td_streak),
            "td_rate_eb": _to_float(prior.td_rate_eb),
            "td_rate_eb_std": _to_float(prior.td_rate_eb_std),
            "is_te": is_te,
            "lag_snap_pct": _to_float(prior.lag_snap_pct),
            "roll3_snap_pct": _to_float(prior.roll3_snap_pct),
            "roll3_rz_targets": _to_float(prior.roll3_rz_targets),
            "rz_target_share": _to_float(prior.rz_target_share),
            "rz_td_rate_eb": _to_float(prior.rz_td_rate_eb),
        }

    def _features_from_bucket(self, bucket: RookieBucket, is_te: bool) -> dict:
        return {
            "targets_pg": _to_float(bucket.targets_pg),
            "roll3_targets": _to_float(bucket.roll3_targets),
            "yards_pg": _to_float(bucket.yards_pg),
            "receptions_pg": _to_float(bucket.receptions_pg),
            "roll3_yards": _to_float(bucket.roll3_yards),
            "roll3_receptions": _to_float(bucket.roll3_receptions),
            "lag_targets": _to_float(bucket.lag_targets),
            "lag_yards": _to_float(bucket.lag_yards),
            "target_share": _to_float(bucket.target_share),
            "roll3_long_rec": _to_float(bucket.roll3_long_rec),
            "roll3_target_std": _to_float(bucket.roll3_target_std),
            "tds_last3": _to_float(bucket.tds_last3),
            "td_streak": _to_float(bucket.td_streak),
            "td_rate_eb": _to_float(bucket.td_rate_eb),
            "td_rate_eb_std": _to_float(bucket.td_rate_eb_std),
            "is_te": is_te,
            "lag_snap_pct": _to_float(bucket.lag_snap_pct),
            "roll3_snap_pct": _to_float(bucket.roll3_snap_pct),
            "roll3_rz_targets": _to_float(bucket.roll3_rz_targets),
            "rz_target_share": _to_float(bucket.rz_target_share),
            "rz_td_rate_eb": _to_float(bucket.rz_td_rate_eb),
        }

    # ── Upsert ────────────────────────────────────────────────────────────────

    async def _upsert_features(
        self,
        player_id: str,
        season: int,
        week: int,
        feat: dict,
        completeness_score: float,
        is_early_season: bool,
        carry_forward_used: bool,
    ) -> None:
        values = {
            "player_id": player_id,
            "season": season,
            "week": week,
            "feature_version": FEATURE_VERSION,
            "targets_pg": feat.get("targets_pg"),
            "roll3_targets": feat.get("roll3_targets"),
            "yards_pg": feat.get("yards_pg"),
            "receptions_pg": feat.get("receptions_pg"),
            "roll3_yards": feat.get("roll3_yards"),
            "roll3_receptions": feat.get("roll3_receptions"),
            "lag_targets": feat.get("lag_targets"),
            "lag_yards": feat.get("lag_yards"),
            "target_share": feat.get("target_share"),
            "roll3_long_rec": feat.get("roll3_long_rec"),
            "roll3_target_std": feat.get("roll3_target_std"),
            "tds_last3": feat.get("tds_last3"),
            "td_streak": feat.get("td_streak"),
            "td_rate_eb": feat.get("td_rate_eb"),
            "td_rate_eb_std": feat.get("td_rate_eb_std"),
            "is_te": bool(feat.get("is_te", False)),
            "lag_snap_pct": feat.get("lag_snap_pct"),
            "roll3_snap_pct": feat.get("roll3_snap_pct"),
            "roll3_rz_targets": feat.get("roll3_rz_targets"),
            "rz_target_share": feat.get("rz_target_share"),
            "rz_td_rate_eb": feat.get("rz_td_rate_eb"),
            "completeness_score": completeness_score,
            "is_early_season": is_early_season,
            "carry_forward_used": carry_forward_used,
        }
        update_cols = {
            k: v for k, v in values.items()
            if k not in ("player_id", "season", "week", "feature_version")
        }
        stmt = (
            pg_insert(PlayerFeatures)
            .values(**values)
            .on_conflict_do_update(constraint="uq_player_features", set_=update_cols)
        )
        await self._db.execute(stmt)
