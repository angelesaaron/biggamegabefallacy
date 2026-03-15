"""
Admin UI router — user management and DB health.
Mounted at /api/admin-ui in main.py.
All endpoints require a valid JWT with is_admin=True (require_admin_user dep).
"""
import secrets
import uuid
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin_user
from app.database import get_db
from app.models.system_config import SystemConfig
from app.models.user import User
from app.services.account_service import initiate_password_reset
from app.services.auth_service import hash_password
from app.services.email_service import EmailService
from app.services.draft_sync import DraftSyncService
from app.services.feature_compute import FeatureComputeService
from app.services.game_log_ingest import GameLogIngestService
from app.services.inference_service import InferenceService
from app.services.odds_sync import OddsSyncService
from app.services.roster_sync import RosterSyncService
from app.services.schedule_sync import ScheduleSyncService
from app.services.sync_result import SyncResult
from app.utils.tank01_client import Tank01Client

router = APIRouter(prefix="/admin-ui", tags=["admin-ui"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class UserRow(BaseModel):
    id: str
    email: str
    is_subscriber: bool
    is_active: bool
    has_stripe: bool
    created_at: str  # ISO datetime string

    model_config = {"from_attributes": True}


class UsersListResponse(BaseModel):
    users: list[UserRow]
    total: int


class ToggleResponse(BaseModel):
    id: str
    is_subscriber: bool
    is_active: bool


class GrantRequest(BaseModel):
    email: str


class GrantResponse(BaseModel):
    created: bool
    user_id: str
    email: str


# ---------------------------------------------------------------------------
# GET /admin-ui/users
# ---------------------------------------------------------------------------

@router.get("/users", response_model=UsersListResponse)
async def list_users(
    search: Optional[str] = Query(default=None),
    _admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
) -> UsersListResponse:
    stmt = select(User).order_by(User.created_at.desc())
    result = await db.execute(stmt)
    all_users = list(result.scalars().all())

    if search:
        needle = search.strip().lower()
        all_users = [u for u in all_users if needle in u.email.lower()]

    rows = [
        UserRow(
            id=str(u.id),
            email=u.email,
            is_subscriber=u.is_subscriber,
            is_active=u.is_active,
            has_stripe=u.stripe_customer_id is not None,
            created_at=u.created_at.isoformat(),
        )
        for u in all_users
    ]
    return UsersListResponse(users=rows, total=len(rows))


# ---------------------------------------------------------------------------
# PATCH /admin-ui/users/{user_id}/subscriber
# ---------------------------------------------------------------------------

@router.patch("/users/{user_id}/subscriber", response_model=ToggleResponse)
async def toggle_subscriber(
    user_id: str,
    _admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
) -> ToggleResponse:
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid user ID.")

    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalars().first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    user.is_subscriber = not user.is_subscriber
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return ToggleResponse(id=str(user.id), is_subscriber=user.is_subscriber, is_active=user.is_active)


# ---------------------------------------------------------------------------
# PATCH /admin-ui/users/{user_id}/active
# ---------------------------------------------------------------------------

@router.patch("/users/{user_id}/active", response_model=ToggleResponse)
async def toggle_active(
    user_id: str,
    _admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
) -> ToggleResponse:
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid user ID.")

    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalars().first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    user.is_active = not user.is_active
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return ToggleResponse(id=str(user.id), is_subscriber=user.is_subscriber, is_active=user.is_active)


# ---------------------------------------------------------------------------
# POST /admin-ui/users/grant
# ---------------------------------------------------------------------------

@router.post("/users/grant", response_model=GrantResponse, status_code=status.HTTP_200_OK)
async def grant_access(
    body: GrantRequest,
    _admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
) -> GrantResponse:
    normalised = body.email.strip().lower()
    result = await db.execute(select(User).where(User.email == normalised))
    user = result.scalars().first()

    if user is not None:
        user.is_subscriber = True
        db.add(user)
        await db.commit()
        return GrantResponse(created=False, user_id=str(user.id), email=user.email)
    else:
        new_user = User(
            email=normalised,
            hashed_password=hash_password(secrets.token_hex(32)),
            is_subscriber=True,
        )
        db.add(new_user)
        await db.flush()
        await db.refresh(new_user)
        await db.commit()
        email_service = EmailService()
        await initiate_password_reset(normalised, db, email_service)
        return GrantResponse(created=True, user_id=str(new_user.id), email=new_user.email)


# ---------------------------------------------------------------------------
# DB Health schemas
# ---------------------------------------------------------------------------

class TableCounts(BaseModel):
    users: int
    players: int
    games: int
    player_game_logs: int
    player_features: int
    player_season_state: int
    predictions: int
    sportsbook_odds: int
    data_quality_events: int
    rookie_buckets: int
    team_game_stats: int


class LastUpdated(BaseModel):
    players: Optional[str]
    player_game_logs: Optional[str]
    player_features: Optional[str]
    predictions: Optional[str]
    sportsbook_odds: Optional[str]


class MissingGameLogPlayer(BaseModel):
    player_id: str
    name: Optional[str]


class WeekSummary(BaseModel):
    game_logs_ingested: int
    features_computed: int
    predictions_generated: int
    odds_available: int
    players_with_game_logs: int
    players_missing_game_logs: int


class DataQualityRow(BaseModel):
    id: str
    event_type: str
    detail: Optional[str]
    created_at: str


class HealthResponse(BaseModel):
    season: int
    week: int
    counts: TableCounts
    last_updated: LastUpdated
    week_summary: WeekSummary
    missing_game_log_players: list[MissingGameLogPlayer]
    recent_data_quality_events: list[DataQualityRow]
    available_weeks: list[dict]


# ---------------------------------------------------------------------------
# GET /admin-ui/health
# ---------------------------------------------------------------------------

@router.get("/health", response_model=HealthResponse)
async def db_health(
    season: int | None = Query(default=None, ge=2020, le=2035),
    week: int | None = Query(default=None, ge=1, le=22),
    _admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
) -> HealthResponse:
    from app.models.player import Player
    from app.models.game import Game
    from app.models.player_game_log import PlayerGameLog
    from app.models.player_features import PlayerFeatures
    from app.models.player_season_state import PlayerSeasonState
    from app.models.prediction import Prediction
    from app.models.sportsbook_odds import SportsbookOdds
    from app.models.data_quality_event import DataQualityEvent
    from app.models.rookie_bucket import RookieBucket
    from app.models.team_game_stats import TeamGameStats

    # --- resolve season/week (fall back to max from player_game_logs) ---
    if season is None or week is None:
        season_res = await db.execute(
            select(func.max(PlayerGameLog.season)).select_from(PlayerGameLog)
        )
        detected_season = season_res.scalar_one_or_none() or 2024

        week_res = await db.execute(
            select(func.max(PlayerGameLog.week))
            .select_from(PlayerGameLog)
            .where(PlayerGameLog.season == detected_season)
        )
        detected_week = week_res.scalar_one_or_none() or 1

        resolved_season = season if season is not None else detected_season
        resolved_week = week if week is not None else detected_week
    else:
        resolved_season = season
        resolved_week = week

    # --- counts ---
    async def count(model):
        res = await db.execute(select(func.count()).select_from(model))
        return res.scalar_one()

    counts = TableCounts(
        users=await count(User),
        players=await count(Player),
        games=await count(Game),
        player_game_logs=await count(PlayerGameLog),
        player_features=await count(PlayerFeatures),
        player_season_state=await count(PlayerSeasonState),
        predictions=await count(Prediction),
        sportsbook_odds=await count(SportsbookOdds),
        data_quality_events=await count(DataQualityEvent),
        rookie_buckets=await count(RookieBucket),
        team_game_stats=await count(TeamGameStats),
    )

    # --- last updated ---
    # Each model uses different timestamp column names:
    #   Player          → updated_at
    #   PlayerGameLog   → created_at (no updated_at)
    #   PlayerFeatures  → computed_at (no updated_at)
    #   Prediction      → created_at (no updated_at)
    #   SportsbookOdds  → fetched_at (no updated_at)
    async def _max_col(model, col_name: str) -> Optional[str]:
        col = getattr(model, col_name, None)
        if col is None:
            return None
        res = await db.execute(select(func.max(col)).select_from(model))
        val = res.scalar_one_or_none()
        return val.isoformat() if val else None

    last_updated = LastUpdated(
        players=await _max_col(Player, "updated_at"),
        player_game_logs=await _max_col(PlayerGameLog, "created_at"),
        player_features=await _max_col(PlayerFeatures, "computed_at"),
        predictions=await _max_col(Prediction, "created_at"),
        sportsbook_odds=await _max_col(SportsbookOdds, "fetched_at"),
    )

    # --- week summary ---
    async def _count_week(model):
        res = await db.execute(
            select(func.count())
            .select_from(model)
            .where(model.season == resolved_season, model.week == resolved_week)
        )
        return res.scalar_one()

    game_logs_ingested = await _count_week(PlayerGameLog)
    features_computed = await _count_week(PlayerFeatures)
    predictions_generated = await _count_week(Prediction)
    odds_available = await _count_week(SportsbookOdds)

    players_with_logs_res = await db.execute(
        select(func.count(PlayerGameLog.player_id.distinct()))
        .select_from(PlayerGameLog)
        .where(PlayerGameLog.season == resolved_season, PlayerGameLog.week == resolved_week)
    )
    players_with_game_logs = players_with_logs_res.scalar_one()

    week_subq = (
        select(PlayerGameLog.player_id)
        .where(
            PlayerGameLog.season == resolved_season,
            PlayerGameLog.week == resolved_week,
        )
        .distinct()
        .scalar_subquery()
    )
    missing_count_res = await db.execute(
        select(func.count())
        .select_from(Player)
        .where(
            Player.active == True,
            Player.position.in_(["WR", "TE"]),
            Player.player_id.not_in(week_subq),
        )
    )
    players_missing_game_logs = missing_count_res.scalar_one()

    week_summary = WeekSummary(
        game_logs_ingested=game_logs_ingested,
        features_computed=features_computed,
        predictions_generated=predictions_generated,
        odds_available=odds_available,
        players_with_game_logs=players_with_game_logs,
        players_missing_game_logs=players_missing_game_logs,
    )

    # --- active WR/TE players missing game logs for resolved week (capped at 100) ---
    missing_res = await db.execute(
        select(Player.player_id, Player.full_name)
        .where(
            Player.active == True,
            Player.position.in_(["WR", "TE"]),
            Player.player_id.not_in(week_subq),
        )
        .order_by(Player.full_name)
        .limit(100)
    )
    missing_rows = [
        MissingGameLogPlayer(player_id=r.player_id, name=r.full_name)
        for r in missing_res.all()
    ]

    # --- recent data quality events (last 10) ---
    dqe_res = await db.execute(
        select(DataQualityEvent)
        .order_by(DataQualityEvent.created_at.desc())
        .limit(10)
    )
    dqe_rows = [
        DataQualityRow(
            id=str(r.id),
            event_type=r.event_type,
            detail=r.detail,
            created_at=r.created_at.isoformat(),
        )
        for r in dqe_res.scalars().all()
    ]

    # --- available weeks (distinct season+week from player_game_logs, capped at 50) ---
    avail_res = await db.execute(
        select(PlayerGameLog.season, PlayerGameLog.week)
        .distinct()
        .order_by(PlayerGameLog.season.desc(), PlayerGameLog.week.desc())
        .limit(50)
    )
    available_weeks = [{"season": r.season, "week": r.week} for r in avail_res.all()]

    return HealthResponse(
        season=resolved_season,
        week=resolved_week,
        counts=counts,
        last_updated=last_updated,
        week_summary=week_summary,
        missing_game_log_players=missing_rows,
        recent_data_quality_events=dqe_rows,
        available_weeks=available_weeks,
    )


# ---------------------------------------------------------------------------
# Pipeline Action helpers — copied from admin.py (not imported to avoid coupling)
# ---------------------------------------------------------------------------

SeasonPath = Annotated[int, Path(ge=2020, le=2035, description="NFL season year")]
WeekPath = Annotated[int, Path(ge=1, le=18, description="Regular season week (1–18)")]


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
        _status = "failed"
    elif result.n_failed > 0:
        _status = "partial"
    else:
        _status = success_msg
    return SyncResponse(
        status=_status,
        n_written=result.n_written,
        n_updated=result.n_updated,
        n_skipped=result.n_skipped,
        n_failed=result.n_failed,
        events=result.events,
    )


# ---------------------------------------------------------------------------
# POST /admin-ui/pipeline/roster
# ---------------------------------------------------------------------------

@router.post("/pipeline/roster", response_model=SyncResponse)
async def pipeline_roster(
    _admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
) -> SyncResponse:
    async with Tank01Client() as tank01:
        result = await RosterSyncService(db, tank01).run()
    return _to_response(result)


# ---------------------------------------------------------------------------
# POST /admin-ui/pipeline/schedule/{season}
# ---------------------------------------------------------------------------

@router.post("/pipeline/schedule/{season}", response_model=SyncResponse)
async def pipeline_schedule(
    season: SeasonPath,
    _admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
) -> SyncResponse:
    async with Tank01Client() as tank01:
        result = await ScheduleSyncService(db, tank01).run(season)
    return _to_response(result)


# ---------------------------------------------------------------------------
# POST /admin-ui/pipeline/gamelogs/{season}/{week}
# ---------------------------------------------------------------------------

@router.post("/pipeline/gamelogs/{season}/{week}", response_model=SyncResponse)
async def pipeline_gamelogs(
    season: SeasonPath,
    week: WeekPath,
    _admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
) -> SyncResponse:
    async with Tank01Client() as tank01:
        result = await GameLogIngestService(db, tank01).run(season, week)
    return _to_response(result)


# ---------------------------------------------------------------------------
# POST /admin-ui/pipeline/odds/{season}/{week}
# ---------------------------------------------------------------------------

@router.post("/pipeline/odds/{season}/{week}", response_model=SyncResponse)
async def pipeline_odds(
    season: SeasonPath,
    week: WeekPath,
    _admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
) -> SyncResponse:
    async with Tank01Client() as tank01:
        result = await OddsSyncService(db, tank01).run(season, week)
    return _to_response(result)


# ---------------------------------------------------------------------------
# POST /admin-ui/pipeline/features/{season}/{week}
# ---------------------------------------------------------------------------

@router.post("/pipeline/features/{season}/{week}", response_model=SyncResponse)
async def pipeline_features(
    season: SeasonPath,
    week: WeekPath,
    _admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
) -> SyncResponse:
    result = await FeatureComputeService(db).run(season, week)
    return _to_response(result)


# ---------------------------------------------------------------------------
# POST /admin-ui/pipeline/predictions/{season}/{week}
# ---------------------------------------------------------------------------

@router.post("/pipeline/predictions/{season}/{week}", response_model=SyncResponse)
async def pipeline_predictions(
    season: SeasonPath,
    week: WeekPath,
    _admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
) -> SyncResponse:
    result = await InferenceService(db).run(season, week)
    return _to_response(result)


# ---------------------------------------------------------------------------
# Week Override schemas
# ---------------------------------------------------------------------------

class WeekOverrideResponse(BaseModel):
    override_active: bool
    season: Optional[int]
    week: Optional[int]


class WeekOverrideRequest(BaseModel):
    season: int = Field(..., ge=2020, le=2035)
    week: int = Field(..., ge=1, le=22)


# ---------------------------------------------------------------------------
# GET /admin-ui/week-override
# ---------------------------------------------------------------------------

@router.get("/week-override", response_model=WeekOverrideResponse)
async def get_week_override(
    _admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
) -> WeekOverrideResponse:
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == "current_week_override")
    )
    row = result.scalars().first()
    if row and row.value:
        try:
            season_str, week_str = row.value.split(":")
            return WeekOverrideResponse(
                override_active=True,
                season=int(season_str),
                week=int(week_str),
            )
        except (ValueError, AttributeError):
            pass
    return WeekOverrideResponse(override_active=False, season=None, week=None)


# ---------------------------------------------------------------------------
# POST /admin-ui/week-override
# ---------------------------------------------------------------------------

@router.post("/week-override", response_model=WeekOverrideResponse)
async def set_week_override(
    body: WeekOverrideRequest,
    _admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
) -> WeekOverrideResponse:
    stmt = (
        pg_insert(SystemConfig)
        .values(key="current_week_override", value=f"{body.season}:{body.week}")
        .on_conflict_do_update(
            index_elements=["key"],
            set_={"value": f"{body.season}:{body.week}", "updated_at": func.now()},
        )
    )
    await db.execute(stmt)
    await db.commit()
    return WeekOverrideResponse(override_active=True, season=body.season, week=body.week)


# ---------------------------------------------------------------------------
# DELETE /admin-ui/week-override
# ---------------------------------------------------------------------------

@router.delete("/week-override", response_model=WeekOverrideResponse)
async def clear_week_override(
    _admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
) -> WeekOverrideResponse:
    stmt = (
        pg_insert(SystemConfig)
        .values(key="current_week_override", value=None)
        .on_conflict_do_update(
            index_elements=["key"],
            set_={"value": None, "updated_at": func.now()},
        )
    )
    await db.execute(stmt)
    await db.commit()
    return WeekOverrideResponse(override_active=False, season=None, week=None)
