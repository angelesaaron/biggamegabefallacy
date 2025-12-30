from datetime import datetime, timedelta
import pytz
from typing import Optional, Tuple


def get_current_nfl_week_from_schedule(db_session=None) -> Tuple[int, int]:
    """
    Dynamically determine current NFL week from schedule table.

    Logic:
    1. Query schedule table for games with status indicating current/upcoming
    2. Find the earliest upcoming game or most recent completed game
    3. Return that week
    4. If off-season (no games scheduled), return next season Week 1

    Args:
        db_session: Optional database session. If None, uses sync session.

    Returns:
        (year, week) tuple
    """
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from app.models.schedule import Schedule
    from app.database import SessionLocal
    import asyncio

    # Use provided session or create new one
    should_close = False
    if db_session is None:
        db_session = SessionLocal()
        should_close = True

    try:
        today = datetime.now().strftime("%Y%m%d")

        # Find games on or after today, ordered by date
        result = db_session.execute(
            select(Schedule)
            .where(Schedule.game_date >= today)
            .order_by(Schedule.game_date, Schedule.week)
            .limit(1)
        )
        upcoming_game = result.scalar_one_or_none()

        if upcoming_game:
            return upcoming_game.season_year, upcoming_game.week

        # No upcoming games - find most recent game
        result = db_session.execute(
            select(Schedule)
            .order_by(Schedule.game_date.desc(), Schedule.week.desc())
            .limit(1)
        )
        last_game = result.scalar_one_or_none()

        if last_game:
            # If last game was Week 18, next season starts
            if last_game.week == 18:
                return last_game.season_year + 1, 1
            else:
                # Otherwise return next week
                return last_game.season_year, last_game.week + 1

        # No games at all - default to current year Week 1
        return datetime.now().year, 1

    finally:
        if should_close:
            db_session.close()


def get_current_nfl_week() -> Tuple[int, int]:
    """
    Get current NFL week using schedule table.
    Falls back to manual detection if DB unavailable.
    """
    try:
        return get_current_nfl_week_from_schedule()
    except Exception as e:
        # Fallback: manual detection based on calendar
        return _fallback_week_detection()


def _fallback_week_detection() -> Tuple[int, int]:
    """
    Fallback week detection using hardcoded calendar logic.
    Used when database is unavailable.
    """
    eastern = pytz.timezone('US/Eastern')
    today = datetime.now(eastern)

    # NFL season typically starts first Thursday after Labor Day
    # For simplicity, use hardcoded start dates
    nfl_start_dates = {
        2024: eastern.localize(datetime(2024, 9, 5)),   # Week 1 starts Sep 5, 2024
        2025: eastern.localize(datetime(2025, 9, 4)),   # Week 1 starts Sep 4, 2025
        2026: eastern.localize(datetime(2026, 9, 10)),  # Week 1 starts Sep 10, 2026
    }

    current_year = today.year

    # Check if we're before season start
    if current_year in nfl_start_dates:
        nfl_start = nfl_start_dates[current_year]
        if today < nfl_start:
            # Off-season: return Week 1 of current year
            return current_year, 1

        # Calculate week based on days since season start
        # NFL weeks run Thursday-Wednesday (game weeks)
        # But we consider "current week" starting Tuesday after previous Monday
        days_since_start = (today - nfl_start).days
        week = min(days_since_start // 7 + 1, 18)

        return current_year, week

    # Unknown year - default to Week 1
    return current_year, 1


def get_previous_nfl_week() -> Tuple[int, int]:
    """Get the previous NFL week (for results sync)"""
    year, week = get_current_nfl_week()
    if week > 1:
        return year, week - 1
    else:
        # If week 1, return last week of previous season
        return year - 1, 18
