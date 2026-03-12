"""
Public API router — user-facing prediction and player endpoints.

No auth required. All computed fields (model_odds, favor) are derived at
query time so stored predictions never need to be rewritten after odds update.
"""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func, cast, Float, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.game import Game
from app.models.player import Player
from app.models.player_game_log import PlayerGameLog
from app.models.prediction import Prediction
from app.models.sportsbook_odds import SportsbookOdds
from app.utils.odds_utils import american_from_prob

router = APIRouter(tags=["public"])

SeasonPath = Annotated[int, Path(ge=2020, le=2035, description="NFL season year")]
WeekPath = Annotated[int, Path(ge=1, le=18, description="Regular season week (1–18)")]


# ── Response schemas ──────────────────────────────────────────────────────────

class PredictionRow(BaseModel):
    player_id: str
    full_name: str
    position: str
    team: Optional[str]
    headshot_url: Optional[str]
    final_prob: float
    model_odds: int                  # American odds derived from final_prob
    sportsbook_odds: Optional[int]   # American odds from market (None if unavailable)
    implied_prob: Optional[float]    # Market implied probability (None if unavailable)
    favor: Optional[float]           # final_prob - implied_prob (positive = model likes it)
    is_low_confidence: bool
    model_version: str


class PredictionsResponse(BaseModel):
    season: int
    week: int
    count: int
    predictions: list[PredictionRow]


class PlayerRow(BaseModel):
    player_id: str
    full_name: str
    position: str
    team: Optional[str]
    draft_round: Optional[int]
    experience: Optional[int]
    headshot_url: Optional[str]


class HistoryRow(BaseModel):
    season: int
    week: int
    final_prob: float
    model_odds: int
    is_low_confidence: bool
    model_version: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_american(prob: float) -> int:
    """american_from_prob clamped so extreme probs don't raise."""
    clamped = max(0.001, min(0.999, prob))
    return american_from_prob(clamped)


# ── Predictions ───────────────────────────────────────────────────────────────

@router.get(
    "/predictions/{season}/{week}",
    response_model=PredictionsResponse,
    summary="Ranked TD predictions for a week",
)
async def get_predictions(
    season: SeasonPath,
    week: WeekPath,
    position: Optional[str] = Query(default=None, description="Filter by WR or TE"),
    team: Optional[str] = Query(default=None, description="Filter by team abbreviation"),
    player_id: Optional[str] = Query(default=None, description="Filter to a single player ID"),
    db: AsyncSession = Depends(get_db),
) -> PredictionsResponse:
    """
    Returns one prediction row per player, ranked by final_prob descending.

    When multiple model versions exist for the same (player, season, week),
    the most recently created prediction is returned.

    model_odds and favor are computed at query time — not stored.
    favor = final_prob − market implied_prob (positive = model sees edge).
    """
    # Subquery: latest prediction id per player for this season/week
    latest_sq = (
        select(func.max(Prediction.id).label("id"))
        .where(Prediction.season == season)
        .where(Prediction.week == week)
        .group_by(Prediction.player_id)
        .subquery()
    )

    # Fetch predictions joined to players
    pred_q = (
        select(Prediction, Player)
        .join(latest_sq, Prediction.id == latest_sq.c.id)
        .join(Player, Prediction.player_id == Player.player_id)
        .where(Player.active.is_(True))
        .order_by(Prediction.final_prob.desc())
    )
    if position:
        pred_q = pred_q.where(Player.position == position.upper())
    if team:
        pred_q = pred_q.where(Player.team == team.upper())
    if player_id:
        pred_q = pred_q.where(Player.player_id == player_id)

    pred_rows = (await db.execute(pred_q)).all()

    if not pred_rows:
        return PredictionsResponse(season=season, week=week, count=0, predictions=[])

    # Fetch consensus odds for all relevant players in one query
    player_ids = [p.player_id for _, p in pred_rows]
    odds_q = (
        select(SportsbookOdds)
        .where(SportsbookOdds.season == season)
        .where(SportsbookOdds.week == week)
        .where(SportsbookOdds.sportsbook == "consensus")
        .where(SportsbookOdds.player_id.in_(player_ids))
    )
    odds_rows = (await db.execute(odds_q)).scalars().all()
    odds_by_player: dict[str, SportsbookOdds] = {o.player_id: o for o in odds_rows}

    # Build response rows
    result: list[PredictionRow] = []
    for pred, player in pred_rows:
        final_prob = float(pred.final_prob)
        odds_row = odds_by_player.get(pred.player_id)

        market_odds: Optional[int] = None
        implied: Optional[float] = None
        favor: Optional[float] = None
        if odds_row is not None:
            market_odds = odds_row.odds
            implied = float(odds_row.implied_prob)
            favor = round(final_prob - implied, 5)

        result.append(
            PredictionRow(
                player_id=pred.player_id,
                full_name=player.full_name,
                position=player.position,
                team=player.team,
                headshot_url=player.headshot_url,
                final_prob=final_prob,
                model_odds=_safe_american(final_prob),
                sportsbook_odds=market_odds,
                implied_prob=implied,
                favor=favor,
                is_low_confidence=pred.is_low_confidence,
                model_version=pred.model_version,
            )
        )

    return PredictionsResponse(
        season=season,
        week=week,
        count=len(result),
        predictions=result,
    )


# ── Players ───────────────────────────────────────────────────────────────────

@router.get(
    "/players",
    response_model=list[PlayerRow],
    summary="Active WR/TE player list",
)
async def list_players(
    position: Optional[str] = Query(default=None, description="WR or TE"),
    team: Optional[str] = Query(default=None, description="Team abbreviation"),
    db: AsyncSession = Depends(get_db),
) -> list[PlayerRow]:
    """Returns active WR and TE players, optionally filtered by position and team."""
    q = (
        select(Player)
        .where(Player.active.is_(True))
        .where(Player.position.in_(["WR", "TE"]))
        .order_by(Player.full_name)
    )
    if position:
        q = q.where(Player.position == position.upper())
    if team:
        q = q.where(Player.team == team.upper())

    players = (await db.execute(q)).scalars().all()
    return [
        PlayerRow(
            player_id=p.player_id,
            full_name=p.full_name,
            position=p.position,
            team=p.team,
            draft_round=p.draft_round,
            experience=p.experience,
            headshot_url=p.headshot_url,
        )
        for p in players
    ]


@router.get(
    "/players/{player_id}",
    response_model=PlayerRow,
    summary="Single player details",
)
async def get_player(
    player_id: str,
    db: AsyncSession = Depends(get_db),
) -> PlayerRow:
    player = await db.get(Player, player_id)
    if player is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found.")
    return PlayerRow(
        player_id=player.player_id,
        full_name=player.full_name,
        position=player.position,
        team=player.team,
        draft_round=player.draft_round,
        experience=player.experience,
        headshot_url=player.headshot_url,
    )


# ── Player history ────────────────────────────────────────────────────────────

@router.get(
    "/players/{player_id}/history",
    response_model=list[HistoryRow],
    summary="Season prediction history for a player",
)
async def get_player_history(
    player_id: str,
    season: Optional[int] = Query(default=None, description="Filter to a single season"),
    db: AsyncSession = Depends(get_db),
) -> list[HistoryRow]:
    """
    Returns every prediction for this player, newest-first.
    When multiple model versions exist for the same week, only the latest is returned.
    """
    # Verify player exists
    if await db.get(Player, player_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found.")

    # Latest prediction id per (season, week) for this player
    latest_sq = (
        select(func.max(Prediction.id).label("id"))
        .where(Prediction.player_id == player_id)
        .group_by(Prediction.season, Prediction.week)
        .subquery()
    )
    q = (
        select(Prediction)
        .join(latest_sq, Prediction.id == latest_sq.c.id)
        .order_by(Prediction.season.desc(), Prediction.week.desc())
    )
    if season is not None:
        q = q.where(Prediction.season == season)

    preds = (await db.execute(q)).scalars().all()
    return [
        HistoryRow(
            season=p.season,
            week=p.week,
            final_prob=float(p.final_prob),
            model_odds=_safe_american(float(p.final_prob)),
            is_low_confidence=p.is_low_confidence,
            model_version=p.model_version,
        )
        for p in preds
    ]


# ── Player game logs ──────────────────────────────────────────────────────────

class GameLogRow(BaseModel):
    season: int
    week: int
    team: str
    opponent: str
    is_home: bool
    targets: int
    receptions: int
    rec_yards: int
    rec_tds: int
    snap_pct: Optional[float]
    rz_targets: Optional[int]


class GameLogsResponse(BaseModel):
    player_id: str
    season: int
    game_logs: list[GameLogRow]


@router.get(
    "/players/{player_id}/game-logs",
    response_model=GameLogsResponse,
    summary="Recent game logs for a player",
)
async def get_player_game_logs(
    player_id: str,
    season: Optional[int] = Query(default=None, description="Filter to a season (default: most recent with logs)"),
    limit: int = Query(default=20, ge=1, le=30, description="Max rows to return (default 20, max 30)"),
    db: AsyncSession = Depends(get_db),
) -> GameLogsResponse:
    """
    Returns recent game logs for a player, most-recent first.

    opponent is derived from the joined games row:
      is_home=True  → opponent = game.away_team
      is_home=False → opponent = game.home_team
    """
    # Verify player exists
    if await db.get(Player, player_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found.")

    # Resolve season — default to most recent season with logs for this player
    if season is not None:
        resolved_season = season
    else:
        max_season_q = (
            select(func.max(PlayerGameLog.season))
            .where(PlayerGameLog.player_id == player_id)
        )
        max_season = (await db.execute(max_season_q)).scalar_one_or_none()
        if max_season is None:
            return GameLogsResponse(player_id=player_id, season=0, game_logs=[])
        resolved_season = int(max_season)

    # Cap limit defensively (query param validator already enforces le=30)
    capped_limit = min(limit, 30)

    q = (
        select(PlayerGameLog, Game)
        .join(Game, PlayerGameLog.game_id == Game.game_id)
        .where(PlayerGameLog.player_id == player_id)
        .where(PlayerGameLog.season == resolved_season)
        .order_by(PlayerGameLog.season.desc(), PlayerGameLog.week.desc())
        .limit(capped_limit)
    )

    rows = (await db.execute(q)).all()

    game_logs: list[GameLogRow] = []
    for log, game in rows:
        opponent = game.away_team if log.is_home else game.home_team
        game_logs.append(
            GameLogRow(
                season=log.season,
                week=log.week,
                team=log.team,
                opponent=opponent,
                is_home=log.is_home,
                targets=log.targets,
                receptions=log.receptions,
                rec_yards=log.rec_yards,
                rec_tds=log.rec_tds,
                snap_pct=float(log.snap_pct) if log.snap_pct is not None else None,
                rz_targets=log.rz_targets,
            )
        )

    return GameLogsResponse(
        player_id=player_id,
        season=resolved_season,
        game_logs=game_logs,
    )


# ── Player odds ────────────────────────────────────────────────────────────────

class PlayerOddsResponse(BaseModel):
    player_id: str
    season: int
    week: int
    sportsbook: str
    odds: Optional[int]
    implied_prob: Optional[float]


@router.get(
    "/players/{player_id}/odds",
    response_model=PlayerOddsResponse,
    summary="Current week sportsbook odds for a player",
)
async def get_player_odds(
    player_id: str,
    season: int = Query(description="NFL season year"),
    week: int = Query(ge=1, le=18, description="Regular season week (1–18)"),
    db: AsyncSession = Depends(get_db),
) -> PlayerOddsResponse:
    """
    Returns the consensus sportsbook odds for a player for the given season/week.

    If no odds row exists, returns a response with odds=None and implied_prob=None.
    """
    # Verify player exists
    if await db.get(Player, player_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found.")

    q = (
        select(SportsbookOdds)
        .where(SportsbookOdds.player_id == player_id)
        .where(SportsbookOdds.season == season)
        .where(SportsbookOdds.week == week)
        .where(SportsbookOdds.sportsbook == "consensus")
        .limit(1)
    )
    odds_row = (await db.execute(q)).scalars().first()

    if odds_row is None:
        return PlayerOddsResponse(
            player_id=player_id,
            season=season,
            week=week,
            sportsbook="consensus",
            odds=None,
            implied_prob=None,
        )

    return PlayerOddsResponse(
        player_id=player_id,
        season=season,
        week=week,
        sportsbook=odds_row.sportsbook,
        odds=odds_row.odds,
        implied_prob=float(odds_row.implied_prob),
    )


# ── Status / week ─────────────────────────────────────────────────────────────

_DEFAULT_SEASON = 2025
_DEFAULT_WEEK = 1


class WeekStatusResponse(BaseModel):
    season: int
    week: int


@router.get(
    "/status/week",
    response_model=WeekStatusResponse,
    summary="Current season and week",
)
async def get_status_week(
    db: AsyncSession = Depends(get_db),
) -> WeekStatusResponse:
    """
    Returns the season and week of the most recently completed (final) game.

    Strategy:
      1. Query games table for latest (season, week) where status='final' and season_type='reg'.
      2. Fall back to latest (season, week) in predictions table.
      3. Return hard-coded default (2025, week 1) if no data exists.
    """
    games_q = (
        select(Game.season, Game.week)
        .where(Game.status == "final")
        .where(Game.season_type == "reg")
        .order_by(Game.season.desc(), Game.week.desc())
        .limit(1)
    )
    games_row = (await db.execute(games_q)).first()
    if games_row is not None:
        return WeekStatusResponse(season=games_row.season, week=games_row.week)

    preds_q = (
        select(Prediction.season, Prediction.week)
        .order_by(Prediction.season.desc(), Prediction.week.desc())
        .limit(1)
    )
    preds_row = (await db.execute(preds_q)).first()
    if preds_row is not None:
        return WeekStatusResponse(season=preds_row.season, week=preds_row.week)

    return WeekStatusResponse(season=_DEFAULT_SEASON, week=_DEFAULT_WEEK)


# ── Track record ───────────────────────────────────────────────────────────────

_HIT_THRESHOLD = 0.15        # final_prob >= this → prediction is "actionable"
_HIGH_CONF_THRESHOLD = 0.30  # final_prob >= this → "high confidence"


class WeekTrackRecord(BaseModel):
    week: int
    predictions_count: int
    hits: int
    misses: int
    calibration_error: float
    high_confidence_hits: int
    high_confidence_total: int


class SeasonSummary(BaseModel):
    total_predictions: int
    overall_hit_rate: float
    high_confidence_hit_rate: float
    mean_calibration_error: float


class TrackRecordResponse(BaseModel):
    season: int
    weeks: list[WeekTrackRecord]
    season_summary: SeasonSummary


@router.get(
    "/track-record",
    response_model=TrackRecordResponse,
    summary="Model accuracy track record by week",
)
async def get_track_record(
    season: Optional[int] = Query(
        default=None,
        description="NFL season year. Defaults to the most recent season with predictions.",
    ),
    db: AsyncSession = Depends(get_db),
) -> TrackRecordResponse:
    """
    Returns per-week hit-rate and calibration statistics for the model.

    A "hit": player scored >= 1 rec TD AND final_prob >= 0.15 (actionable call).
    A "miss": final_prob >= 0.15 but rec_tds == 0.
    Calibration error: mean |final_prob - actual_outcome| across all predictions
    that week (regardless of threshold), only for rows with a game log.

    Joining: LEFT JOIN player_game_logs on (player_id, season, week).
    Rows without a game log (bye, inactive) are excluded from hits/misses
    but included in calibration only when has_log=1.
    """
    from collections import defaultdict

    # Resolve season
    if season is not None:
        resolved_season = season
    else:
        max_season_q = select(func.max(Prediction.season))
        max_season = (await db.execute(max_season_q)).scalar_one_or_none()
        if max_season is None:
            return TrackRecordResponse(
                season=_DEFAULT_SEASON,
                weeks=[],
                season_summary=SeasonSummary(
                    total_predictions=0,
                    overall_hit_rate=0.0,
                    high_confidence_hit_rate=0.0,
                    mean_calibration_error=0.0,
                ),
            )
        resolved_season = int(max_season)

    # Deduplicate: latest prediction per (player_id, week)
    latest_sq = (
        select(func.max(Prediction.id).label("id"))
        .where(Prediction.season == resolved_season)
        .group_by(Prediction.player_id, Prediction.week)
        .subquery()
    )

    q = (
        select(
            Prediction.week,
            cast(Prediction.final_prob, Float).label("final_prob"),
            func.coalesce(PlayerGameLog.rec_tds, 0).label("rec_tds"),
            case(
                (PlayerGameLog.id.isnot(None), 1),
                else_=0,
            ).label("has_log"),
        )
        .join(latest_sq, Prediction.id == latest_sq.c.id)
        .outerjoin(
            PlayerGameLog,
            (PlayerGameLog.player_id == Prediction.player_id)
            & (PlayerGameLog.season == Prediction.season)
            & (PlayerGameLog.week == Prediction.week),
        )
        .order_by(Prediction.week)
    )

    rows = (await db.execute(q)).all()

    if not rows:
        return TrackRecordResponse(
            season=resolved_season,
            weeks=[],
            season_summary=SeasonSummary(
                total_predictions=0,
                overall_hit_rate=0.0,
                high_confidence_hit_rate=0.0,
                mean_calibration_error=0.0,
            ),
        )

    # Aggregate in Python — max ~2700 rows (18 weeks × ~150 players)
    week_data: dict[int, list[tuple[float, int, int]]] = defaultdict(list)
    for row in rows:
        week_data[row.week].append((float(row.final_prob), int(row.rec_tds), int(row.has_log)))

    week_records: list[WeekTrackRecord] = []
    total_hits = 0
    total_misses = 0
    total_high_conf = 0
    total_high_conf_hits = 0
    total_predictions = 0
    calibration_errors: list[float] = []

    for week_num in sorted(week_data.keys()):
        entries = week_data[week_num]
        week_hits = week_misses = week_high_conf = week_high_conf_hits = 0
        week_cal_errors: list[float] = []

        for final_prob, rec_tds, has_log in entries:
            scored_td = rec_tds >= 1
            actionable = final_prob >= _HIT_THRESHOLD
            high_conf = final_prob >= _HIGH_CONF_THRESHOLD

            if has_log:
                week_cal_errors.append(abs(final_prob - (1.0 if scored_td else 0.0)))

            if actionable and has_log:
                if scored_td:
                    week_hits += 1
                else:
                    week_misses += 1

            if high_conf and has_log:
                week_high_conf += 1
                if scored_td:
                    week_high_conf_hits += 1

        cal_err = sum(week_cal_errors) / len(week_cal_errors) if week_cal_errors else 0.0

        week_records.append(
            WeekTrackRecord(
                week=week_num,
                predictions_count=len(entries),
                hits=week_hits,
                misses=week_misses,
                calibration_error=round(cal_err, 5),
                high_confidence_hits=week_high_conf_hits,
                high_confidence_total=week_high_conf,
            )
        )

        total_predictions += len(entries)
        total_hits += week_hits
        total_misses += week_misses
        total_high_conf += week_high_conf
        total_high_conf_hits += week_high_conf_hits
        calibration_errors.extend(week_cal_errors)

    actionable_total = total_hits + total_misses
    return TrackRecordResponse(
        season=resolved_season,
        weeks=week_records,
        season_summary=SeasonSummary(
            total_predictions=total_predictions,
            overall_hit_rate=round(total_hits / actionable_total, 5) if actionable_total else 0.0,
            high_confidence_hit_rate=round(total_high_conf_hits / total_high_conf, 5) if total_high_conf else 0.0,
            mean_calibration_error=round(sum(calibration_errors) / len(calibration_errors), 5) if calibration_errors else 0.0,
        ),
    )
