"""
Schedule Service - Manages NFL schedule and gameID → week mapping

This service is critical for enriching Tank01 game logs with week numbers,
since Tank01's getNFLGamesForPlayer endpoint doesn't include them.

Strategy:
1. Fetch schedule once per week from Tank01
2. Build gameID → week mapping
3. Cache mapping in memory (refreshed weekly)
4. Provide lookup function for game logs
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from app.utils.tank01_client import Tank01Client
from app.config import settings

logger = logging.getLogger(__name__)


class ScheduleService:
    """Service for managing NFL schedule and week number mappings."""

    def __init__(self):
        self.tank01_client = Tank01Client()
        self._week_mapping_cache: Dict[str, int] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl_hours = 168  # 7 days

    async def close(self):
        """Close Tank01 client"""
        await self.tank01_client.close()

    def _is_cache_valid(self) -> bool:
        """Check if cached week mapping is still valid"""
        if not self._cache_timestamp:
            return False

        age = datetime.utcnow() - self._cache_timestamp
        return age < timedelta(hours=self._cache_ttl_hours)

    async def get_week_mapping(
        self,
        season: Optional[int] = None,
        week: Optional[int] = None,
        force_refresh: bool = False
    ) -> Dict[str, int]:
        """
        Get gameID → week number mapping.

        Args:
            season: Season year (defaults to current season from settings)
            week: Week number (defaults to current week from settings)
            force_refresh: Force cache refresh even if valid

        Returns:
            Dict mapping gameID → week number

        Example:
            mapping = await service.get_week_mapping(2025, 1)
            week_num = mapping.get("20250907_ARI@NO")  # Returns 1
        """
        # Use cache if valid
        if not force_refresh and self._is_cache_valid() and self._week_mapping_cache:
            logger.info("Using cached week mapping")
            return self._week_mapping_cache

        # Fetch fresh data
        season = season or settings.NFL_SEASON_YEAR
        week = week or settings.NFL_CURRENT_WEEK

        logger.info(f"Fetching schedule for {season} week {week}")

        try:
            schedule = await self.tank01_client.get_schedule(
                season=season,
                week=week,
                season_type="reg"
            )

            # Build mapping
            mapping = self.tank01_client.build_game_week_mapping(schedule, week)

            # Update cache
            self._week_mapping_cache = mapping
            self._cache_timestamp = datetime.utcnow()

            logger.info(f"Built week mapping with {len(mapping)} games")
            return mapping

        except Exception as e:
            logger.error(f"Failed to fetch schedule: {e}")
            # Return cached data if available, even if expired
            if self._week_mapping_cache:
                logger.warning("Returning expired cache due to fetch error")
                return self._week_mapping_cache
            raise

    async def get_full_season_mapping(
        self,
        season: int,
        weeks: Optional[List[int]] = None
    ) -> Dict[str, int]:
        """
        Build gameID → week mapping for multiple weeks or entire season.

        Args:
            season: Season year
            weeks: List of week numbers (defaults to 1-18 for regular season)

        Returns:
            Dict mapping gameID → week for all specified weeks

        Warning: This makes multiple API calls! Use sparingly.
        """
        weeks = weeks or list(range(1, 19))  # Regular season: weeks 1-18
        full_mapping = {}

        logger.info(f"Building full season mapping for {season}, weeks {weeks[0]}-{weeks[-1]}")

        for week in weeks:
            try:
                schedule = await self.tank01_client.get_schedule(
                    season=season,
                    week=week,
                    season_type="reg"
                )
                week_mapping = self.tank01_client.build_game_week_mapping(schedule, week)
                full_mapping.update(week_mapping)

                logger.debug(f"Added {len(week_mapping)} games from week {week}")

            except Exception as e:
                logger.error(f"Failed to fetch schedule for week {week}: {e}")
                # Continue with other weeks
                continue

        logger.info(f"Built full season mapping with {len(full_mapping)} total games")
        return full_mapping

    async def enrich_game_logs_with_weeks(
        self,
        game_logs: List[Dict[str, Any]],
        season: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Enrich game logs with week numbers using schedule mapping.

        Args:
            game_logs: List of game log dicts from Tank01 (must have 'gameID' field)
            season: Season year (optional, will use current season)

        Returns:
            List of game logs with 'week' field added

        Note: If a gameID is not found in the mapping, week will be None
        """
        # Get full season mapping (cached or fetch all weeks)
        season = season or settings.NFL_SEASON_YEAR

        # Use cached mapping if valid, otherwise fetch full season + previous season
        if not self._is_cache_valid() or not self._week_mapping_cache:
            logger.info(f"Fetching schedule for seasons {season-1} and {season}")
            week_mapping = {}

            # Fetch previous season (for historical game logs)
            try:
                prev_season_mapping = await self.get_full_season_mapping(season=season-1)
                week_mapping.update(prev_season_mapping)
                logger.info(f"Added {len(prev_season_mapping)} games from {season-1} season")
            except Exception as e:
                logger.warning(f"Could not fetch {season-1} schedule: {e}")

            # Fetch current season (regular + preseason)
            current_season_mapping = await self.get_full_season_mapping(season=season)
            week_mapping.update(current_season_mapping)
            logger.info(f"Added {len(current_season_mapping)} games from {season} season")

            # Update cache with combined mapping
            self._week_mapping_cache = week_mapping
            self._cache_timestamp = datetime.utcnow()
        else:
            week_mapping = self._week_mapping_cache

        enriched_logs = []
        missing_game_ids = []

        for log in game_logs:
            # Try both field names (gameID from schedule, game_id from parsed logs)
            game_id = log.get("game_id") or log.get("gameID")

            if not game_id:
                logger.warning(f"Game log missing game_id/gameID: {log}")
                enriched_logs.append({**log, "week": None})
                continue

            week = week_mapping.get(game_id)

            if week is None:
                missing_game_ids.append(game_id)
                # Try to infer week from date
                week = self._infer_week_from_game_id(game_id, season or settings.NFL_SEASON_YEAR)

            enriched_logs.append({**log, "week": week})

        if missing_game_ids:
            logger.warning(f"Could not find week numbers for {len(missing_game_ids)} games: {missing_game_ids[:5]}")

        return enriched_logs

    def _infer_week_from_game_id(self, game_id: str, season: int) -> Optional[int]:
        """
        Attempt to infer week number from gameID date.

        Args:
            game_id: Game ID in format "YYYYMMDD_AWAY@HOME"
            season: Season year

        Returns:
            Inferred week number or None

        Note: This is a fallback and may not be 100% accurate (byes, scheduling, etc.)
        """
        try:
            date_str = game_id.split('_')[0]
            game_date = datetime.strptime(date_str, "%Y%m%d")

            # NFL season typically starts in early September
            # Week 1 is usually the first full week of September
            # This is a rough approximation

            # Assume season starts Sept 5 (typical)
            season_start = datetime(season, 9, 5)

            # Calculate weeks since season start
            days_since_start = (game_date - season_start).days

            if days_since_start < 0:
                return None  # Game is before season start

            # Rough week calculation (7 days per week)
            inferred_week = (days_since_start // 7) + 1

            # Sanity check: regular season is weeks 1-18
            if 1 <= inferred_week <= 18:
                logger.info(f"Inferred week {inferred_week} for gameID {game_id}")
                return inferred_week

            return None

        except Exception as e:
            logger.error(f"Failed to infer week from gameID {game_id}: {e}")
            return None

    async def get_games_for_week(
        self,
        season: int,
        week: int
    ) -> List[Dict[str, Any]]:
        """
        Get all games scheduled for a specific week.

        Args:
            season: Season year
            week: Week number

        Returns:
            List of game dicts from Tank01 schedule endpoint
        """
        try:
            schedule = await self.tank01_client.get_schedule(
                season=season,
                week=week,
                season_type="reg"
            )
            return schedule

        except Exception as e:
            logger.error(f"Failed to get games for week {week}: {e}")
            raise

    def get_week_for_game_id(self, game_id: str) -> Optional[int]:
        """
        Look up week number for a specific gameID (uses cache).

        Args:
            game_id: Game ID in format "YYYYMMDD_AWAY@HOME"

        Returns:
            Week number or None if not found in cache
        """
        return self._week_mapping_cache.get(game_id)


# Singleton instance
_schedule_service: Optional[ScheduleService] = None


def get_schedule_service() -> ScheduleService:
    """Get singleton ScheduleService instance"""
    global _schedule_service
    if _schedule_service is None:
        _schedule_service = ScheduleService()
    return _schedule_service
