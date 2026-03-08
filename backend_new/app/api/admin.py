"""
Admin API router — pipeline trigger endpoints.

All endpoints require X-Admin-Key header matching settings.ADMIN_KEY.
Returns a SyncResponse summarising what happened — never silently succeeds
or fails without reporting.

Endpoints are intentionally NOT auto-cascading:
  - Syncing schedule does NOT trigger game log ingest.
  - Ingesting game logs does NOT trigger feature computation.
  - Each step is discrete and user-triggered, so one failing step
    does not silently corrupt downstream data.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.services.alias_seed import AliasSeedService
from app.services.draft_sync import DraftSyncService
from app.services.feature_compute import FeatureComputeService
from app.services.game_log_ingest import GameLogIngestService
from app.services.inference_service import InferenceService
from app.services.odds_sync import OddsSyncService
from app.services.rookie_bucket_seed import RookieBucketSeedService
from app.services.roster_sync import RosterSyncService
from app.services.schedule_sync import ScheduleSyncService
from app.services.season_state_service import SeasonStateService
from app.services.sync_result import SyncResult
from app.utils.tank01_client import Tank01Client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

SeasonPath = Annotated[int, Path(ge=2020, le=2035, description="NFL season year")]
WeekPath = Annotated[int, Path(ge=1, le=18, description="Regular season week (1–18)")]


# ── Auth dependency ───────────────────────────────────────────────────────────

async def require_admin(x_admin_key: str | None = Header(default=None)) -> None:
    if not settings.ADMIN_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ADMIN_KEY is not configured on the server.",
        )
    if x_admin_key != settings.ADMIN_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing X-Admin-Key header.",
        )


# ── Response schema ───────────────────────────────────────────────────────────

class SyncResponse(BaseModel):
    status: str
    n_written: int
    n_updated: int
    n_skipped: int
    n_failed: int
    events: list[str]


def _to_response(result: SyncResult, success_msg: str = "completed") -> SyncResponse:
    total_ok = result.n_written + result.n_updated
    if result.n_failed > 0 and total_ok == 0:
        status = "failed"
    elif result.n_failed > 0:
        status = "partial"
    else:
        status = success_msg
    return SyncResponse(
        status=status,
        n_written=result.n_written,
        n_updated=result.n_updated,
        n_skipped=result.n_skipped,
        n_failed=result.n_failed,
        events=result.events,
    )


# ── Roster ────────────────────────────────────────────────────────────────────

@router.post("/sync/roster", response_model=SyncResponse, dependencies=[Depends(require_admin)])
async def sync_roster(db: AsyncSession = Depends(get_db)) -> SyncResponse:
    """
    Fetch all 32 team rosters from Tank01 and upsert WR/TE players.
    Run at the start of each season and when players change teams.
    """
    async with Tank01Client() as tank01:
        result = await RosterSyncService(db, tank01).run()
    return _to_response(result)


# ── Draft rounds ─────────────────────────────────────────────────────────────

@router.post("/sync/draft", response_model=SyncResponse, dependencies=[Depends(require_admin)])
async def sync_draft_rounds(
    force_update: bool = False,
    db: AsyncSession = Depends(get_db),
) -> SyncResponse:
    """
    Populate players.draft_round from the nflverse player registry.

    Tank01 does not return draft data. nflverse espn_id == Tank01 playerID,
    so matching is exact — no name fuzzing.

    Run after roster sync at the start of each season and after the annual draft
    to populate draft_round for incoming rookies.

    draft_round values written: 1-7 = drafted round, 0 = UDFA (confirmed undrafted).
    Players not found in nflverse are skipped (draft_round stays NULL, treated as
    UDFA bucket by feature_compute).

    Args:
        force_update: If True, overwrite existing draft_round values.
                      Default False — only updates NULL rows.
    """
    result = await DraftSyncService(db).run(force_update=force_update)
    return _to_response(result)


# ── Schedule ──────────────────────────────────────────────────────────────────

@router.post("/sync/schedule/{season}", response_model=SyncResponse, dependencies=[Depends(require_admin)])
async def sync_schedule(season: SeasonPath, db: AsyncSession = Depends(get_db)) -> SyncResponse:
    """
    Fetch the full regular-season schedule for a given season year.
    Re-run weekly to pick up status changes (scheduled → final).
    """
    async with Tank01Client() as tank01:
        result = await ScheduleSyncService(db, tank01).run(season)
    return _to_response(result)


# ── Game log ingest ───────────────────────────────────────────────────────────

@router.post("/ingest/gamelogs/{season}/{week}", response_model=SyncResponse, dependencies=[Depends(require_admin)])
async def ingest_game_logs(season: SeasonPath, week: WeekPath, db: AsyncSession = Depends(get_db)) -> SyncResponse:
    """
    Fetch box scores for all final games in a week, enrich with nflverse
    snap + RZ data, and write player_game_logs + team_game_stats.

    Prerequisite: schedule must be synced (games need status='final').
    Safe to re-run after alias table updates to backfill null snap/RZ data.

    Note: nflverse PBP download is ~300 MB on first run (cached locally after).
    """
    async with Tank01Client() as tank01:
        result = await GameLogIngestService(db, tank01).run(season, week)
    return _to_response(result)


# ── Odds sync ─────────────────────────────────────────────────────────────────

@router.post("/sync/odds/{season}/{week}", response_model=SyncResponse, dependencies=[Depends(require_admin)])
async def sync_odds(season: SeasonPath, week: WeekPath, db: AsyncSession = Depends(get_db)) -> SyncResponse:
    """
    Fetch anytime TD player props from Tank01 and upsert into sportsbook_odds.
    Run any time during game week to refresh lines. Safe to re-run repeatedly.

    Prerequisite: schedule must be synced (to know game dates).
    """
    async with Tank01Client() as tank01:
        result = await OddsSyncService(db, tank01).run(season, week)
    return _to_response(result)


# ── One-time seeds ────────────────────────────────────────────────────────────

@router.post("/seed/rookie-buckets", response_model=SyncResponse, dependencies=[Depends(require_admin)])
async def seed_rookie_buckets(db: AsyncSession = Depends(get_db)) -> SyncResponse:
    """
    Populate the rookie_buckets table from hard-coded training data
    (derived from ml/data/rookie_buckets.csv).

    Run once after the initial migration. Safe to re-run — upserts on
    (draft_round, pos). Re-run whenever the model is retrained with new buckets.
    """
    result = await RookieBucketSeedService(db).run()
    return _to_response(result)


# ── Feature computation ───────────────────────────────────────────────────────

@router.post("/compute/features/{season}/{week}", response_model=SyncResponse, dependencies=[Depends(require_admin)])
async def compute_features(season: SeasonPath, week: WeekPath, db: AsyncSession = Depends(get_db)) -> SyncResponse:
    """
    Compute model features for all active WR/TE players for a given week and write
    to player_features.

    For weeks 4+: computes all 21 features from in-season game logs (weeks 1..week-1).
    For weeks 1-3: resolves features via carry-forward / team-changer / rookie buckets.

    Prerequisites:
      - Model bundle must exist at MODEL_PATH (EB params are read from it).
      - For week >= 4: game logs must be ingested for the season up to week-1.
      - For week <= 3: player_season_state must be populated (run compute/season-state
        at end of prior season) and rookie_buckets table must be seeded.

    Safe to re-run — upserts on (player_id, season, week, feature_version).
    """
    result = await FeatureComputeService(db).run(season, week)
    return _to_response(result)


@router.post("/compute/season-state/{season}", response_model=SyncResponse, dependencies=[Depends(require_admin)])
async def compute_season_state(season: SeasonPath, db: AsyncSession = Depends(get_db)) -> SyncResponse:
    """
    Write end-of-season carry-forward state to player_season_state for all WR/TE
    who appeared in at least one game this season.

    Run ONCE after all game logs for the season are ingested. The resulting rows
    are consumed by the early-season feature pipeline (weeks 1-3) for season+1.

    Safe to re-run — upserts on (player_id, season).
    """
    result = await SeasonStateService(db).run(season)
    return _to_response(result)


@router.post("/run/predictions/{season}/{week}", response_model=SyncResponse, dependencies=[Depends(require_admin)])
async def run_predictions(season: SeasonPath, week: WeekPath, db: AsyncSession = Depends(get_db)) -> SyncResponse:
    """
    Run XGBoost inference + calibration for all players with feature rows for
    this season/week and write to predictions.

    Prerequisite: player_features must be populated (run compute/features first).
    Safe to re-run — upserts on (player_id, season, week, model_version).
    Re-running after a retrain + recalibration will update probabilities in place.
    """
    result = await InferenceService(db).run(season, week)
    return _to_response(result)


# ── Alias management ──────────────────────────────────────────────────────────

@router.post("/aliases/seed", response_model=SyncResponse, dependencies=[Depends(require_admin)])
async def seed_aliases(db: AsyncSession = Depends(get_db)) -> SyncResponse:
    """
    Seed player_aliases with known Tank01 → nflverse name mismatches.
    Run once after initial roster sync. Safe to re-run.

    After seeding, re-run ingest/gamelogs to backfill previously null
    snap/RZ data for the affected players.
    """
    result = await AliasSeedService(db).run()
    return _to_response(result)


@router.get("/aliases/unresolved", dependencies=[Depends(require_admin)])
async def list_unresolved_aliases(
    season: int = Query(ge=2020, le=2035, description="NFL season year"),
    week: int | None = Query(default=None, ge=1, le=18, description="Filter to a single week"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    List recent alias_match_failure events so you know which players
    to add to the alias table.
    """
    from sqlalchemy import select
    from app.models.data_quality_event import DataQualityEvent

    q = (
        select(DataQualityEvent)
        .where(DataQualityEvent.event_type == "alias_match_failure")
        .where(DataQualityEvent.season == season)
        .where(DataQualityEvent.resolved_at.is_(None))
        .order_by(DataQualityEvent.created_at.desc())
    )
    if week is not None:
        q = q.where(DataQualityEvent.week == week)

    rows = await db.execute(q)
    events = rows.scalars().all()

    return {
        "count": len(events),
        "events": [
            {"id": e.id, "week": e.week, "detail": e.detail, "created_at": str(e.created_at)}
            for e in events
        ],
    }
