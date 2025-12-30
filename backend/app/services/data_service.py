"""
Data Service - Orchestrates Tank01 API calls and database caching

This service is the main interface for fetching NFL data. It:
1. Fetches data from Tank01 API
2. Enriches with week numbers from schedule service
3. Caches in database to minimize API calls
4. Provides clean, normalized data to API endpoints

Cost optimization strategy:
- Cache rosters monthly (32 calls)
- Cache game logs after fetching (100 calls/week)
- Fetch betting odds once per week (1 call)
- Total: ~102 calls/week = 408/month
"""

import logging
from typing import Dict, List, Optional, Any, Tuple, AsyncGenerator
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.utils.tank01_client import Tank01Client, parse_player_from_roster, parse_game_log
from app.services.schedule_service import get_schedule_service
from app.models.player import Player
from app.models.odds import SportsbookOdds
from app.config import settings

logger = logging.getLogger(__name__)


class DataService:
    """Service for fetching and caching NFL data from Tank01"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.tank01_client = Tank01Client()
        self.schedule_service = get_schedule_service()

    async def close(self):
        """Close HTTP clients"""
        await self.tank01_client.close()
        await self.schedule_service.close()

    # ============================================================================
    # PLAYER DATA
    # ============================================================================

    async def get_or_create_player(self, player_id: str) -> Optional[Player]:
        """
        Get player from database or fetch from Tank01 if not exists.

        Args:
            player_id: Tank01 player ID

        Returns:
            Player model instance or None
        """
        # Check database first
        result = await self.db.execute(
            select(Player).where(Player.player_id == player_id)
        )
        player = result.scalar_one_or_none()

        if player:
            logger.debug(f"Player {player_id} found in database")
            return player

        # Not in database - need to fetch from Tank01
        # We don't have a single-player endpoint, so we'll need to fetch rosters
        logger.warning(f"Player {player_id} not in database - roster sync needed")
        return None

    async def sync_rosters(
        self,
        positions: Optional[List[str]] = None
    ) -> int:
        """
        Sync all team rosters from Tank01 to database.

        Args:
            positions: Filter to specific positions (e.g., ["WR", "TE"])

        Returns:
            Number of players synced

        Warning: This makes 32 API calls! Run sparingly (monthly).
        """
        logger.info(f"Starting roster sync for positions: {positions or 'ALL'}")

        players_data = await self.tank01_client.get_all_rosters(positions=positions)

        synced_count = 0

        for tank01_player in players_data:
            try:
                normalized = parse_player_from_roster(tank01_player)
                player_id = normalized.get("player_id")

                if not player_id:
                    logger.warning(f"Skipping player with no ID: {normalized.get('full_name')}")
                    continue

                # Check if player exists
                result = await self.db.execute(
                    select(Player).where(Player.player_id == player_id)
                )
                existing_player = result.scalar_one_or_none()

                if existing_player:
                    # Update existing player
                    for key, value in normalized.items():
                        setattr(existing_player, key, value)
                    existing_player.last_updated = datetime.utcnow()
                else:
                    # Create new player
                    new_player = Player(**normalized)
                    self.db.add(new_player)

                synced_count += 1

            except Exception as e:
                logger.error(f"Failed to sync player {tank01_player.get('playerID')}: {e}")
                continue

        await self.db.commit()
        logger.info(f"Roster sync complete. Synced {synced_count} players.")

        return synced_count

    async def get_active_players(
        self,
        positions: Optional[List[str]] = None,
        team_id: Optional[str] = None
    ) -> List[Player]:
        """
        Get active players from database.

        Args:
            positions: Filter by positions (e.g., ["WR", "TE"])
            team_id: Filter by team ID

        Returns:
            List of Player model instances
        """
        query = select(Player).where(Player.active_status == True)

        if positions:
            query = query.where(Player.position.in_(positions))

        if team_id:
            query = query.where(Player.team_id == team_id)

        result = await self.db.execute(query)
        return result.scalars().all()

    # ============================================================================
    # GAME LOGS
    # ============================================================================

    async def get_player_game_logs(
        self,
        player_id: str,
        season: Optional[int] = None,
        limit: Optional[int] = None,
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get game logs for a player from DATABASE (no API calls).

        Args:
            player_id: Tank01 player ID
            season: Season year (optional filter)
            limit: Max number of games to return
            use_cache: Use cached data (always True now - reads from DB)

        Returns:
            List of game log dicts with week numbers
        """
        from app.models.game_log import GameLog

        logger.info(f"Fetching game logs for player {player_id} from database")

        # Build query
        query = select(GameLog).where(GameLog.player_id == player_id)

        # Filter by season if specified
        if season:
            query = query.where(GameLog.season_year == season)

        # Order by date (newest first)
        query = query.order_by(GameLog.season_year.desc(), GameLog.week.desc())

        # Apply limit
        if limit:
            query = query.limit(limit)

        # Execute query
        result = await self.db.execute(query)
        game_logs = result.scalars().all()

        if not game_logs:
            logger.warning(f"No game logs found in database for player {player_id}")
            return []

        # Convert to dict format
        logs_list = [
            {
                "player_id": log.player_id,
                "game_id": log.game_id,
                "season_year": log.season_year,
                "week": log.week,
                "team": log.team,
                "team_id": log.team_id,
                "receptions": log.receptions,
                "receiving_yards": log.receiving_yards,
                "receiving_touchdowns": log.receiving_touchdowns,
                "targets": log.targets,
                "long_reception": log.long_reception,
                "yards_per_reception": float(log.yards_per_reception) if log.yards_per_reception else None,
            }
            for log in game_logs
        ]

        logger.info(f"Retrieved {len(logs_list)} game logs from database for player {player_id}")

        return logs_list

    async def get_game_logs_for_current_season(
        self,
        player_id: str,
        current_week: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get game logs for current season only, up to (but not including) current week.

        Args:
            player_id: Tank01 player ID
            current_week: Current week number (defaults to settings)

        Returns:
            List of game logs for current season
        """
        current_week = current_week or settings.NFL_CURRENT_WEEK
        current_season = settings.NFL_SEASON_YEAR

        all_logs = await self.get_player_game_logs(
            player_id=player_id,
            season=current_season
        )

        logger.info(f"Total enriched game logs for player {player_id}: {len(all_logs)}")

        # Filter to games before current week
        filtered_logs = [
            log for log in all_logs
            if log.get("week") and log["week"] < current_week
        ]

        logger.info(f"Filtered to {len(filtered_logs)} games before week {current_week}")
        if not filtered_logs and all_logs:
            logger.warning(f"All {len(all_logs)} logs filtered out. Week range in logs: {min(log.get('week', 999) for log in all_logs if log.get('week'))} to {max(log.get('week', 0) for log in all_logs if log.get('week'))}")

        return filtered_logs

    # ============================================================================
    # BETTING ODDS
    # ============================================================================

    async def get_betting_odds_for_week(
        self,
        season: int,
        week: int,
        sportsbook: str = "draftkings"
    ) -> Dict[str, int]:
        """
        Get anytime TD odds for all players for a specific week from database.

        Args:
            season: Season year
            week: Week number
            sportsbook: Sportsbook name ('draftkings' or 'fanduel')

        Returns:
            Dict mapping player_id → American odds
        """
        from app.models.odds import SportsbookOdds

        logger.info(f"Fetching betting odds from DB for {season} week {week} ({sportsbook})")

        # Query odds from database
        result = await self.db.execute(
            select(SportsbookOdds)
            .where(
                SportsbookOdds.season_year == season,
                SportsbookOdds.week == week,
                SportsbookOdds.sportsbook == sportsbook
            )
        )
        odds_records = result.scalars().all()

        # Convert to dict: player_id → odds
        all_odds = {
            record.player_id: record.anytime_td_odds
            for record in odds_records
        }

        logger.info(f"Retrieved odds for {len(all_odds)} players from database")

        return all_odds

    async def get_current_week_odds(self) -> Dict[str, int]:
        """
        Get anytime TD odds for current week.

        Returns:
            Dict mapping player_id → American odds
        """
        return await self.get_betting_odds_for_week(
            season=settings.NFL_SEASON_YEAR,
            week=settings.NFL_CURRENT_WEEK
        )

    async def cache_odds_to_db(
        self,
        player_odds: Dict[str, int],
        season: int,
        week: int,
        sportsbook: str = "consensus"
    ) -> int:
        """
        Store betting odds in database.

        Args:
            player_odds: Dict mapping player_id → odds
            season: Season year
            week: Week number
            sportsbook: Sportsbook name (default "consensus")

        Returns:
            Number of odds records created
        """
        cached_count = 0

        for player_id, odds in player_odds.items():
            try:
                odds_record = SportsbookOdds(
                    player_id=player_id,
                    season_year=season,
                    week=week,
                    sportsbook=sportsbook,
                    bet_type="anytime_td",
                    odds=odds,
                    fetched_at=datetime.utcnow()
                )
                self.db.add(odds_record)
                cached_count += 1

            except Exception as e:
                logger.error(f"Failed to cache odds for player {player_id}: {e}")
                continue

        await self.db.commit()
        logger.info(f"Cached {cached_count} odds records to database")

        return cached_count

    # ============================================================================
    # CONVENIENCE METHODS
    # ============================================================================

    async def get_player_data_for_prediction(
        self,
        player_id: str,
        next_week: Optional[int] = None
    ) -> Tuple[Optional[Player], List[Dict[str, Any]], Optional[int]]:
        """
        Get all data needed to make a TD prediction for a player.

        Args:
            player_id: Tank01 player ID
            next_week: Week to predict (defaults to current week)

        Returns:
            Tuple of (player, game_logs, sportsbook_odds)
        """
        next_week = next_week or settings.NFL_CURRENT_WEEK

        # Get player info
        player = await self.get_or_create_player(player_id)

        # Get game logs (up to but not including next week)
        game_logs = await self.get_game_logs_for_current_season(
            player_id=player_id,
            current_week=next_week
        )

        # Get sportsbook odds for next week
        week_odds = await self.get_current_week_odds()
        sportsbook_odds = week_odds.get(player_id)

        return player, game_logs, sportsbook_odds

    async def get_api_usage_stats(self) -> Dict[str, int]:
        """
        Get approximate API usage statistics.

        Returns:
            Dict with usage counts
        """
        # TODO: Implement job_runs tracking
        # For now, return estimates

        return {
            "estimated_weekly_calls": 102,
            "estimated_monthly_calls": 408,
            "rosters_sync": 32,  # All teams
            "game_logs_per_week": 100,  # Active WR/TE
            "odds_per_week": 1,
            "schedule_per_week": 1
        }


def get_data_service(db: AsyncSession) -> DataService:
    """Factory function to create DataService with database session"""
    return DataService(db)
