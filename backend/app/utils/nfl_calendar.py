from datetime import datetime, timedelta
import pytz
from typing import Optional, Tuple


def get_current_nfl_week_from_schedule(db_session=None) -> Tuple[int, int, str]:
    """
    Dynamically determine current NFL week from schedule table.

    Week Boundary Logic (User's Mental Model):
    - NFL week runs Thursday-Monday (games played)
    - TUESDAY = new week starts
    - Monday after Week 1 games → still shows "Week 1" (MNF context)
    - Tuesday onwards → shows "Week 2" (new week begins)

    Logic:
    1. If TUESDAY: Look forward to next week's games
    2. If MONDAY: Check for MNF game, otherwise show just-completed week
    3. If Wed-Sun: Normal forward-looking logic (4-day window)
    4. Handles regular season → playoffs → off-season transitions

    Args:
        db_session: Optional database session. If None, uses sync session.

    Returns:
        (year, week, season_type) tuple
        season_type: 'reg' for regular season, 'post' for playoffs
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
            # Determine next week/season based on season_type

            # If last game was regular season Week 18 → Check for playoffs
            if last_game.season_type == 'reg' and last_game.week == 18:
                # Check if playoff schedule exists
                playoff_check = db_session.execute(
                    select(Schedule)
                    .where(
                        Schedule.season_year == last_game.season_year,
                        Schedule.season_type == 'post'
                    )
                    .order_by(Schedule.week)
                    .limit(1)
                )
                first_playoff = playoff_check.scalar_one_or_none()

                if first_playoff:
                    # Playoffs exist, return first playoff week
                    return last_game.season_year, first_playoff.week, 'post'
                else:
                    # Playoffs not yet scheduled → off-season, next season starts
                    return last_game.season_year + 1, 1, 'reg'

            # If in playoffs (POST season)
            elif last_game.season_type == 'post':
                # Check if there's a next playoff week
                next_playoff = db_session.execute(
                    select(Schedule)
                    .where(
                        Schedule.season_year == last_game.season_year,
                        Schedule.season_type == 'post',
                        Schedule.week > last_game.week
                    )
                    .order_by(Schedule.week)
                    .limit(1)
                )
                next_playoff_game = next_playoff.scalar_one_or_none()

                if next_playoff_game:
                    # More playoff rounds exist
                    return last_game.season_year, next_playoff_game.week, 'post'
                else:
                    # Playoffs complete → next season starts
                    return last_game.season_year + 1, 1, 'reg'

            # Regular season (not Week 18) → next week
            else:
                return last_game.season_year, last_game.week + 1, 'reg'

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

    COMPLETE 2025 SEASON CALENDAR (including playoffs):
    - Regular Season Week 1-18: Sep 4, 2025 - Jan 5, 2026
    - Week 18: Tue Dec 30, 2025 - Mon Jan 5, 2026
    - Playoff Week 1 (Wildcard): Tue Jan 6, 2026 - Mon Jan 12, 2026
    - Playoff Week 2 (Divisional): Tue Jan 13, 2026 - Mon Jan 19, 2026
    - Playoff Week 3 (Conference): Tue Jan 20, 2026 - Mon Jan 26, 2026
    - Super Bowl: ~Feb 9, 2026
    - After playoffs: Jump to 2026 Season Week 1
    """
    eastern = pytz.timezone('US/Eastern')
    today = datetime.now(eastern)

    # 2025 SEASON CALENDAR (with playoffs through Jan 2026)
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
        # Handle 2025 playoffs (in calendar year 2026)

        # Week 18 ends: Monday, January 5, 2026
        week_18_end = eastern.localize(datetime(2026, 1, 5, 23, 59))

        # Playoff Week 1 (Wildcard): Tue Jan 6 - Mon Jan 12, 2026
        playoff_week_1_start = eastern.localize(datetime(2026, 1, 6))
        playoff_week_1_end = eastern.localize(datetime(2026, 1, 12, 23, 59))

        # Playoff Week 2 (Divisional): Tue Jan 13 - Mon Jan 19, 2026
        playoff_week_2_start = eastern.localize(datetime(2026, 1, 13))
        playoff_week_2_end = eastern.localize(datetime(2026, 1, 19, 23, 59))

        # Playoff Week 3 (Conference): Tue Jan 20 - Mon Jan 26, 2026
        playoff_week_3_start = eastern.localize(datetime(2026, 1, 20))
        playoff_week_3_end = eastern.localize(datetime(2026, 1, 26, 23, 59))

        # Super Bowl week: ~Jan 27 - Feb 9, 2026
        super_bowl_approx = eastern.localize(datetime(2026, 2, 9, 23, 59))

        # 2026 season starts: ~Sep 10, 2026
        season_2026_start = eastern.localize(datetime(2026, 9, 10))

        if today <= week_18_end:
            # Still in Week 18 (Dec 30, 2025 - Jan 5, 2026)
            return 2025, 18

        elif playoff_week_1_start <= today <= playoff_week_1_end:
            # Playoff Week 1 (Wildcard)
            # Note: Playoffs use season_type='post', but fallback can't distinguish
            # Database detection should be used for accurate playoff tracking
            return 2025, 18  # Show regular season Week 18 as fallback

        elif playoff_week_2_start <= today <= playoff_week_2_end:
            # Playoff Week 2 (Divisional)
            return 2025, 18

        elif playoff_week_3_start <= today <= playoff_week_3_end:
            # Playoff Week 3 (Conference Championships)
            return 2025, 18

        elif playoff_week_3_end < today <= super_bowl_approx:
            # Super Bowl week
            return 2025, 18

        elif super_bowl_approx < today < season_2026_start:
            # Off-season (Feb - Aug 2026): Show 2026 Week 1
            return 2026, 1

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
