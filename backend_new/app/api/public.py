"""
Public API router — user-facing prediction and player endpoints.

No auth required. All computed fields (model_odds, favor) are derived at
query time so stored predictions never need to be rewritten after odds update.
"""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.player import Player
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
