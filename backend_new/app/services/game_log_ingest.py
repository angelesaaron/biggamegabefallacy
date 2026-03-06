"""
GameLogIngestService — writes player_game_logs and team_game_stats for a week.

Pipeline per game:
  1. Fetch box score from Tank01 (16 calls total for a full week)
  2. Parse receiving stats for all players
  3. Filter to WR/TE players in our DB
  4. Enrich with nflverse snap data (via NflverseAdapter)
  5. Enrich with nflverse RZ data (via NflverseAdapter)
  6. Upsert player_game_logs
  7. Aggregate and upsert team_game_stats
  8. Emit DataQualityEvent for every name that failed alias resolution

Idempotent: safe to re-run for any week. Existing rows are updated in-place.

Trigger:
  - Manually via admin endpoint after a week is complete
  - Re-run to backfill missing snap/RZ data after alias table updates
"""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.data_quality_event import DataQualityEvent
from app.models.game import Game
from app.models.player import Player
from app.models.player_game_log import PlayerGameLog
from app.models.team_game_stats import TeamGameStats
from app.services.sync_result import SyncResult
from app.utils.nflverse_adapter import NflverseAdapter, NflverseResult
from app.utils.tank01_client import Tank01Client, parse_game_logs_from_box_score

logger = logging.getLogger(__name__)


class GameLogIngestService:
    def __init__(self, db: AsyncSession, tank01: Tank01Client) -> None:
        self._db = db
        self._tank01 = tank01

    async def run(self, season: int, week: int) -> SyncResult:
        result = SyncResult()

        # Load all final games for this week
        games = await self._get_final_games(season, week)
        if not games:
            logger.warning("No final games found for S%dW%d — is schedule synced?", season, week)
            result.add_event(f"no_final_games: S{season}W{week}")
            return result

        # Load all known WR/TE player_ids into a set for fast lookup
        known_player_ids = await self._get_known_player_ids()

        # Download + resolve nflverse data for this season (covers all weeks)
        nflverse = await NflverseAdapter(self._db).load(seasons=[season])
        await self._emit_alias_events(nflverse, season, week, result)

        # Process each game
        for game in games:
            game_result = await self._ingest_game(
                game, season, week, known_player_ids, nflverse
            )
            result.merge(game_result)

        await self._db.commit()
        logger.info(
            "GameLogIngest S%dW%d: %d written, %d updated, %d skipped, %d failed",
            season, week, result.n_written, result.n_updated, result.n_skipped, result.n_failed,
        )
        return result

    # ── Private ───────────────────────────────────────────────────────────────

    async def _get_final_games(self, season: int, week: int) -> list[Game]:
        rows = await self._db.execute(
            select(Game)
            .where(Game.season == season)
            .where(Game.week == week)
            .where(Game.status == "final")
        )
        return list(rows.scalars().all())

    async def _get_known_player_ids(self) -> set[str]:
        rows = await self._db.execute(
            select(Player.player_id).where(Player.position.in_(["WR", "TE"]))
        )
        return {row[0] for row in rows}

    async def _ingest_game(
        self,
        game: Game,
        season: int,
        week: int,
        known_ids: set[str],
        nflverse: NflverseResult,
    ) -> SyncResult:
        result = SyncResult()

        try:
            box_score = await self._tank01.get_box_score(game.game_id)
        except Exception as exc:
            logger.error("Box score fetch failed %s: %s", game.game_id, exc)
            result.n_failed += 1
            result.add_event(f"box_score_failed: {game.game_id} — {exc}")
            return result

        raw_logs = parse_game_logs_from_box_score(box_score, game.game_id, season, week)

        for raw in raw_logs:
            player_id = raw["player_id"]
            if player_id not in known_ids:
                result.n_skipped += 1  # Non-WR/TE or player not in our DB — expected
                continue

            # Enrich with nflverse data
            snap = nflverse.snap.get((player_id, season, week))
            rz = nflverse.rz.get((player_id, season, week))

            log_data: dict[str, Any] = {
                **raw,
                # Snap (nullable)
                "snap_count": None,  # Tank01 box score doesn't give snap count
                "snap_pct": snap.snap_pct if snap else None,
                # Red zone (nullable)
                "rz_targets": rz.rz_targets if rz else None,
                "rz_rec_tds": rz.rz_tds if rz else None,
                # Audit flags
                "data_source_flags": {
                    "tank01": True,
                    "nflverse_snap": snap is not None,
                    "nflverse_rz": rz is not None,
                },
            }

            try:
                stmt = (
                    pg_insert(PlayerGameLog)
                    .values(**log_data)
                    .on_conflict_do_update(
                        constraint="uq_player_game_log",
                        set_={
                            "targets": log_data["targets"],
                            "receptions": log_data["receptions"],
                            "rec_yards": log_data["rec_yards"],
                            "rec_tds": log_data["rec_tds"],
                            "long_rec": log_data["long_rec"],
                            "snap_pct": log_data["snap_pct"],
                            "rz_targets": log_data["rz_targets"],
                            "rz_rec_tds": log_data["rz_rec_tds"],
                            "data_source_flags": log_data["data_source_flags"],
                        },
                    )
                )
                await self._db.execute(stmt)
                result.n_written += 1
            except Exception as exc:
                logger.error("PlayerGameLog upsert failed %s %s: %s", player_id, game.game_id, exc)
                result.n_failed += 1

        # Aggregate team totals and upsert team_game_stats
        await self._upsert_team_game_stats(game.game_id, season, week, result)

        return result

    async def _upsert_team_game_stats(
        self, game_id: str, season: int, week: int, result: SyncResult
    ) -> None:
        """
        Query the just-written player_game_logs for this game and aggregate
        team totals. This guarantees team_game_stats is always consistent
        with player_game_logs regardless of how many times ingest is re-run.
        """
        rows = await self._db.execute(
            select(
                PlayerGameLog.team,
                PlayerGameLog.targets,
                PlayerGameLog.rec_tds,
                PlayerGameLog.rz_targets,
                PlayerGameLog.rz_rec_tds,
            )
            .where(PlayerGameLog.game_id == game_id)
        )
        logs = rows.all()

        # Aggregate by team
        teams: dict[str, dict] = {}
        for row in logs:
            t = row.team
            if t not in teams:
                teams[t] = {"team_targets": 0, "team_rec_tds": 0,
                            "team_rz_targets": 0, "team_rz_tds": 0,
                            "has_rz": False}
            teams[t]["team_targets"] += row.targets or 0
            teams[t]["team_rec_tds"] += row.rec_tds or 0
            if row.rz_targets is not None:
                teams[t]["team_rz_targets"] += row.rz_targets
                teams[t]["has_rz"] = True
            if row.rz_rec_tds is not None:
                teams[t]["team_rz_tds"] += row.rz_rec_tds

        for team, totals in teams.items():
            data: dict[str, Any] = {
                "game_id": game_id,
                "team": team,
                "season": season,
                "week": week,
                "team_targets": totals["team_targets"],
                "team_rec_tds": totals["team_rec_tds"],
                "team_rz_targets": totals["team_rz_targets"] if totals["has_rz"] else None,
                "team_rz_tds": totals["team_rz_tds"] if totals["has_rz"] else None,
            }
            try:
                stmt = (
                    pg_insert(TeamGameStats)
                    .values(**data)
                    .on_conflict_do_update(
                        constraint="uq_team_game_stats",
                        set_={
                            "team_targets": data["team_targets"],
                            "team_rec_tds": data["team_rec_tds"],
                            "team_rz_targets": data["team_rz_targets"],
                            "team_rz_tds": data["team_rz_tds"],
                        },
                    )
                )
                await self._db.execute(stmt)
            except Exception as exc:
                logger.error("TeamGameStats upsert failed %s %s: %s", game_id, team, exc)
                result.n_failed += 1

    async def _emit_alias_events(
        self,
        nflverse: NflverseResult,
        season: int,
        week: int,
        result: SyncResult,
    ) -> None:
        """Write DataQualityEvent rows for every unresolved nflverse name."""
        for name in nflverse.snap_unmatched:
            event = DataQualityEvent(
                event_type="alias_match_failure",
                season=season,
                week=week,
                detail=f"nflverse_snap name unresolved: '{name}' — add to player_aliases",
                auto_resolvable=False,
            )
            self._db.add(event)
            result.add_event(f"alias_match_failure (snap): {name}")

        for name in nflverse.rz_unmatched:
            event = DataQualityEvent(
                event_type="alias_match_failure",
                season=season,
                week=week,
                detail=f"nflverse_pbp name unresolved: '{name}' — add to player_aliases",
                auto_resolvable=False,
            )
            self._db.add(event)
            result.add_event(f"alias_match_failure (pbp): {name}")
