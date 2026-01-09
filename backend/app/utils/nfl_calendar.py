from datetime import datetime, timedelta
import pytz
from typing import Optional, Tuple
import json
import os


def _load_season_config() -> Optional[dict]:
    """
    Load manual season override config from nfl_season_config.json.
    Returns None if config doesn't exist or override is disabled.
    """
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        'nfl_season_config.json'
    )

    try:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)

            if config.get('override_enabled', False):
                current_season = config.get('current_season', {})
                if all(k in current_season for k in ['year', 'week', 'season_type']):
                    return current_season
    except Exception:
        pass

    return None


def get_current_nfl_week_from_schedule(db_session=None) -> Tuple[int, int, str]:
    """
    Dynamically determine current NFL week from schedule table.

    TODO (Next Season): Implement dynamic week detection for 2026 season
    - Remove manual override after 2025 season ends
    - Update week boundary logic to handle season transitions automatically
    - Consider using Tank01 API's current week endpoint instead of date math
    - Test thoroughly before 2026 Week 1 kickoff

    Week Boundary Logic (User's Mental Model):
    - NFL week runs Thursday-Monday (games played)
    - TUESDAY = new week starts
    - Monday after Week 1 games → still shows "Week 1" (MNF context)
    - Tuesday onwards → shows "Week 2" (new week begins)

    Logic:
    1. Check for manual override config (nfl_season_config.json)
    2. If TUESDAY: Look forward to next week's games
    3. If MONDAY: Check for MNF game, otherwise show just-completed week
    4. If Wed-Sun: Normal forward-looking logic (4-day window)
    5. Regular season only (18 weeks) - no playoff support

    Args:
        db_session: Optional database session. If None, uses sync session.

    Returns:
        (year, week, season_type) tuple
        season_type: 'reg' for regular season only
    """
    # Check for manual override first
    config = _load_season_config()
    if config:
        return config['year'], config['week'], config['season_type']
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
        from datetime import timedelta
        today = datetime.now().strftime("%Y%m%d")
        today_dt = datetime.now()
        day_of_week = today_dt.weekday()  # 0=Mon, 1=Tue, 2=Wed, ..., 6=Sun

        # WEEK BOUNDARY LOGIC: TUESDAY = NEW WEEK
        if day_of_week == 1:  # Tuesday
            # On Tuesday, new week begins - look forward to upcoming games
            lookahead_days = 4
        elif day_of_week == 0:  # Monday
            # On Monday, check if there's a game TODAY (Monday Night Football)
            result = db_session.execute(
                select(Schedule)
                .where(Schedule.game_date == today)
                .limit(1)
            )
            mnf_game = result.scalar_one_or_none()

            if mnf_game:
                # MNF is playing or played today, return current week
                return mnf_game.season_year, mnf_game.week, mnf_game.season_type
            else:
                # No MNF today, but still show just-completed week until Tuesday
                # Look BACK to most recent game (likely Sunday)
                result = db_session.execute(
                    select(Schedule)
                    .where(Schedule.game_date < today)
                    .order_by(Schedule.game_date.desc())
                    .limit(1)
                )
                recent_game = result.scalar_one_or_none()
                if recent_game:
                    return recent_game.season_year, recent_game.week, recent_game.season_type
                # If no recent game, fall through to normal logic
                lookahead_days = 4
        else:
            # Wed-Sun: Normal forward-looking logic
            lookahead_days = 4

        four_days_from_now = (today_dt + timedelta(days=lookahead_days)).strftime("%Y%m%d")

        # Find games happening within next 4 days
        # NFL weeks run Thu-Mon, so 4-day window captures current week without jumping ahead
        result = db_session.execute(
            select(Schedule)
            .where(Schedule.game_date >= today)
            .where(Schedule.game_date <= four_days_from_now)
            .order_by(Schedule.game_date, Schedule.week)
            .limit(1)
        )
        upcoming_game = result.scalar_one_or_none()

        if upcoming_game:
            return upcoming_game.season_year, upcoming_game.week, upcoming_game.season_type

        # No upcoming games - find most recent game
        result = db_session.execute(
            select(Schedule)
            .order_by(Schedule.game_date.desc(), Schedule.week.desc())
            .limit(1)
        )
        last_game = result.scalar_one_or_none()

        if last_game:
            # Regular season only - no playoff support
            # TODO (Next Season): This logic needs improvement for season transitions

            # If last game was regular season Week 18 → season over, stay at Week 18
            if last_game.season_type == 'reg' and last_game.week == 18:
                # Season ended, stay at Week 18 until manual override
                return last_game.season_year, 18, 'reg'

            # Regular season (not Week 18) → next week
            elif last_game.season_type == 'reg':
                return last_game.season_year, last_game.week + 1, 'reg'

            # If somehow postseason data exists, ignore it and show Week 18
            else:
                return last_game.season_year, 18, 'reg'

        # No games at all - default to current year Week 1 regular season
        return datetime.now().year, 1, 'reg'

    finally:
        if should_close:
            db_session.close()


def get_current_nfl_week() -> Tuple[int, int, str]:
    """
    Get current NFL week using schedule table.
    Falls back to manual detection if DB unavailable.

    Returns:
        (year, week, season_type) tuple
        season_type: 'reg' for regular season, 'post' for playoffs
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        return get_current_nfl_week_from_schedule()
    except Exception as e:
        # Fallback: manual detection based on calendar
        logger.warning(
            f"⚠️  Database week detection failed: {str(e)}. "
            f"Falling back to calendar-based detection. "
            f"This may be inaccurate during playoffs or schedule changes."
        )
        year, week = _fallback_week_detection()
        # Fallback always assumes regular season (can't detect playoffs without DB)
        return year, week, 'reg'


def _fallback_week_detection() -> Tuple[int, int]:
    """
    Fallback week detection using hardcoded calendar logic.
    Used when database is unavailable.

    TODO (Next Season): Update these dates for 2026 season
    - Update season start date when 2026 schedule is announced
    - Remove hardcoded playoff logic (model doesn't support playoffs)
    - Consider using config file for season dates instead of hardcoding

    2025 SEASON CALENDAR (Regular Season Only):
    - Regular Season Week 1-18: Sep 4, 2025 - Jan 5, 2026
    - Week 18: Tue Dec 30, 2025 - Mon Jan 5, 2026
    - After Week 18: Stay at Week 18 (off-season)
    """
    eastern = pytz.timezone('US/Eastern')
    today = datetime.now(eastern)

    # 2025 SEASON CALENDAR (Regular Season Only)
    if today.year == 2025:
        # Regular season: Sep 4, 2025 - Jan 5, 2026
        season_start = eastern.localize(datetime(2025, 9, 4))  # Week 1 Thursday

        if today < season_start:
            # Before 2025 season starts
            return 2025, 1

        # Calculate week based on days since season start
        days_since_start = (today - season_start).days
        week = min(days_since_start // 7 + 1, 18)

        return 2025, week

    elif today.year == 2026:
        # Week 18 ends: Monday, January 5, 2026
        week_18_end = eastern.localize(datetime(2026, 1, 5, 23, 59))

        # TODO (Next Season): Update this date when 2026 schedule announced
        # 2026 season starts: ~Sep 10, 2026 (estimate)
        season_2026_start = eastern.localize(datetime(2026, 9, 10))

        if today <= week_18_end:
            # Still in Week 18 (Dec 30, 2025 - Jan 5, 2026)
            return 2025, 18

        elif today < season_2026_start:
            # Off-season (Jan 6 - Sep 9, 2026): Stay at 2025 Week 18
            # Model doesn't support playoffs, so keep showing Week 18
            return 2025, 18

        else:
            # 2026 season started (Sep 10, 2026+)
            days_since_start = (today - season_2026_start).days
            week = min(days_since_start // 7 + 1, 18)
            return 2026, week

    elif today.year == 2024:
        # 2024 season
        season_start = eastern.localize(datetime(2024, 9, 5))

        if today < season_start:
            return 2024, 1

        days_since_start = (today - season_start).days
        week = min(days_since_start // 7 + 1, 18)
        return 2024, week

    else:
        # Unknown year - default to Week 1
        return today.year, 1


def get_previous_nfl_week() -> Tuple[int, int]:
    """Get the previous NFL week (for results sync)"""
    year, week = get_current_nfl_week()
    if week > 1:
        return year, week - 1
    else:
        # If week 1, return last week of previous season
        return year - 1, 18
