"""
SeasonStateService — writes end-of-season carry-forward state to player_season_state.

Run once after all game logs for a season are ingested and features are computed.
Produces the rows that feed into the early-season feature pipeline (weeks 1-3)
for the FOLLOWING season (join_season = season + 1).

What gets stored: the player's end-of-season feature values computed from ALL
their game logs for the season — equivalent to prior_season_final_state.csv
from the notebook pipeline.

Feature math is shared with FeatureComputeService via app.ml.feature_math.
Safe to re-run (upserts). Only covers WR/TE who appeared in at least one game.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.feature_math import compute_features_from_logs
from app.ml.model_bundle import get_eb_params
from app.models.player import Player
from app.models.player_game_log import PlayerGameLog
from app.models.player_season_state import PlayerSeasonState
from app.services.sync_result import SyncResult

logger = logging.getLogger(__name__)


class SeasonStateService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def run(self, season: int) -> SyncResult:
        result = SyncResult()

        try:
            eb = get_eb_params()
        except FileNotFoundError as exc:
            result.n_failed += 1
            result.add_event(f"model_bundle_not_found: {exc}")
            logger.error("SeasonState aborted: %s", exc)
            return result

        # Include inactive players — a player may have retired but still needs
        # a prior-season state row for historical completeness.
        player_rows = await self._db.execute(
            select(Player).where(Player.position.in_(["WR", "TE"]))
        )
        players = {p.player_id: p for p in player_rows.scalars().all()}

        log_rows = await self._db.execute(
            select(PlayerGameLog)
            .where(PlayerGameLog.season == season)
            .order_by(PlayerGameLog.player_id, PlayerGameLog.week)
        )
        all_logs = list(log_rows.scalars().all())

        player_logs: dict[str, list[PlayerGameLog]] = defaultdict(list)
        for log in all_logs:
            if log.player_id in players:
                player_logs[log.player_id].append(log)

        if not player_logs:
            result.add_event(f"no_game_logs_found_for_season_{season}")
            return result

        # Build team cumulative totals from log.team — not player.team.
        team_cum_targets: dict[str, int] = defaultdict(int)
        team_cum_rz_targets: dict[str, int] = defaultdict(int)
        for log in all_logs:
            if log.team and log.player_id in players:
                team_cum_targets[log.team] += log.targets
                team_cum_rz_targets[log.team] += (log.rz_targets or 0)

        for pid, plogs in player_logs.items():
            player = players[pid]
            # Use the player's last recorded team from their game logs
            current_team = plogs[-1].team

            try:
                feat = compute_features_from_logs(
                    logs=plogs,
                    is_te=player.is_te,
                    team_cum_targets=team_cum_targets.get(current_team, 0),
                    team_cum_rz_targets=team_cum_rz_targets.get(current_team, 0),
                    eb=eb,
                )
                await self._upsert_state(pid, season, feat, player, current_team)
                result.n_written += 1
            except Exception as exc:
                logger.error("SeasonState failed %s S%d: %s", pid, season, exc)
                result.n_failed += 1
                result.add_event(f"state_error:{pid}:{exc}")

        await self._db.commit()
        logger.info(
            "SeasonState S%d: written=%d skipped=%d failed=%d",
            season, result.n_written, result.n_skipped, result.n_failed,
        )
        return result

    async def _upsert_state(
        self, player_id: str, season: int, feat: dict, player: Player, last_team: str | None
    ) -> None:
        values = {
            "player_id": player_id,
            "season": season,
            "join_season": season + 1,
            "team": last_team,  # from plogs[-1].team — unambiguous regardless of when roster sync ran
            "draft_round": player.draft_round,
            # Carry-forward feature values
            "targets_pg": feat.get("targets_pg"),
            "yards_pg": feat.get("yards_pg"),
            "receptions_pg": feat.get("receptions_pg"),
            "roll3_targets": feat.get("roll3_targets"),
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
            "lag_snap_pct": feat.get("lag_snap_pct"),
            "roll3_snap_pct": feat.get("roll3_snap_pct"),
            "roll3_rz_targets": feat.get("roll3_rz_targets"),
            "rz_target_share": feat.get("rz_target_share"),
            "rz_td_rate_eb": feat.get("rz_td_rate_eb"),
        }
        update_cols = {k: v for k, v in values.items() if k not in ("player_id", "season")}
        stmt = (
            pg_insert(PlayerSeasonState)
            .values(**values)
            .on_conflict_do_update(constraint="uq_player_season_state", set_=update_cols)
        )
        await self._db.execute(stmt)
