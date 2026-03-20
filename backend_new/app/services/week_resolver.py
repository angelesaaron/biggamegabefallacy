"""
Resolve the current NFL week for internal backend use.

Priority:
  1. system_config 'current_week_override' (admin-set)
  2. system_config 'active_display_week' (pipeline-set on success)
  3. Hard fallback: week=1, season=2026

Never queries games, predictions, or player_game_logs.
"""
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.system_config import SystemConfig

logger = logging.getLogger(__name__)


def _parse_season_week(value: str) -> tuple[int, int] | None:
    try:
        season_str, week_str = value.split(":")
        season = int(season_str)
        week = int(week_str)
        if 2020 <= season <= 2035 and 1 <= week <= 22:
            return week, season  # NOTE: (week, season) to match all existing call sites
    except (ValueError, AttributeError):
        pass
    return None


async def resolve_current_week(db: AsyncSession) -> tuple[int, int]:
    """
    Returns (week, season) — NOT (season, week).
    This order matches all existing call sites throughout the codebase.
    Do not change call sites.
    """
    for key in ("current_week_override", "active_display_week"):
        row = (await db.execute(
            select(SystemConfig).where(SystemConfig.key == key)
        )).scalars().first()
        if row and row.value:
            parsed = _parse_season_week(row.value)
            if parsed:
                return parsed  # (week, season)

    return 1, 2026  # hard fallback
