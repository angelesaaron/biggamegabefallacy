"""
Resolve the current NFL week, respecting any admin override in system_config.

Usage:
    week, season = await resolve_current_week(db)
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.system_config import SystemConfig


async def resolve_current_week(db: AsyncSession) -> tuple[int, int]:
    """
    Returns (week, season).
    If system_config has a current_week_override, use that.
    Otherwise fall back to max(season)/max(week) from player_game_logs.
    """
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == "current_week_override")
    )
    row = result.scalars().first()
    if row and row.value:
        try:
            season_str, week_str = row.value.split(":")
            return int(week_str), int(season_str)
        except (ValueError, AttributeError):
            pass

    # Fallback: max from player_game_logs
    from app.models.player_game_log import PlayerGameLog
    from sqlalchemy import func
    season_res = await db.execute(
        select(func.max(PlayerGameLog.season))
    )
    season = season_res.scalar_one_or_none() or 2025
    week_res = await db.execute(
        select(func.max(PlayerGameLog.week))
        .where(PlayerGameLog.season == season)
    )
    week = week_res.scalar_one_or_none() or 1
    return week, season
