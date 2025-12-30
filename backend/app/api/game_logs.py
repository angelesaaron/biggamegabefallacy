from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.database import get_db
from app.models.game_log import GameLog

router = APIRouter()


@router.get("/{player_id}")
async def get_player_game_logs(
    player_id: str,
    season: int | None = Query(None, description="Filter by season year"),
    limit: int = Query(20, description="Max number of game logs to return"),
    db: AsyncSession = Depends(get_db)
):
    """Get game logs for a specific player"""
    query = select(GameLog).where(GameLog.player_id == player_id)

    if season:
        query = query.where(GameLog.season_year == season)

    query = query.order_by(GameLog.season_year.desc(), GameLog.week.desc()).limit(limit)

    result = await db.execute(query)
    game_logs = result.scalars().all()

    if not game_logs:
        return []

    return [
        {
            "id": log.id,
            "player_id": log.player_id,
            "game_id": log.game_id,
            "season_year": log.season_year,
            "week": log.week,
            "team": log.team,
            "opponent": _extract_opponent(log.game_id, log.team),
            "receptions": log.receptions,
            "receiving_yards": log.receiving_yards,
            "receiving_touchdowns": log.receiving_touchdowns,
            "targets": log.targets,
            "long_reception": log.long_reception,
            "yards_per_reception": float(log.yards_per_reception) if log.yards_per_reception else None,
        }
        for log in game_logs
    ]


def _extract_opponent(game_id: str, player_team: str | None) -> str:
    """Extract opponent from game_id format: YYYYMMDD_AWAY@HOME"""
    if not game_id or '@' not in game_id:
        return 'OPP'

    try:
        # Split on underscore to get the teams part (AWAY@HOME)
        teams_part = game_id.split('_', 1)[1]
        away_team, home_team = teams_part.split('@')

        # Return the team that's NOT the player's team
        if player_team:
            if away_team == player_team:
                return home_team
            else:
                return away_team

        # If we don't know the player's team, return both
        return teams_part.replace('@', ' @ ')
    except (IndexError, ValueError):
        return 'OPP'
