from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.database import get_db
from app.models.player import Player
from app.schemas.player import PlayerResponse, PlayerListItem

router = APIRouter()


@router.get("/", response_model=List[PlayerListItem])
async def list_players(
    position: str | None = Query(None, description="Filter by position (WR, TE)"),
    team_id: str | None = Query(None, description="Filter by team ID"),
    active_only: bool = Query(True, description="Show only active players"),
    db: AsyncSession = Depends(get_db)
):
    """List all players with optional filtering"""
    query = select(Player)

    if active_only:
        query = query.where(Player.active_status == True)
    if position:
        query = query.where(Player.position == position)
    if team_id:
        query = query.where(Player.team_id == team_id)

    query = query.order_by(Player.full_name)

    result = await db.execute(query)
    players = result.scalars().all()

    return players


@router.get("/{player_id}", response_model=PlayerResponse)
async def get_player(
    player_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get single player details"""
    result = await db.execute(
        select(Player).where(Player.player_id == player_id)
    )
    player = result.scalar_one_or_none()

    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    return player


@router.get("/search/{query}")
async def search_players(
    query: str,
    db: AsyncSession = Depends(get_db)
):
    """Search players by name"""
    result = await db.execute(
        select(Player).where(
            Player.full_name.ilike(f"%{query}%")
        ).where(
            Player.active_status == True
        ).order_by(Player.full_name).limit(20)
    )
    players = result.scalars().all()

    return [PlayerListItem.model_validate(p) for p in players]
