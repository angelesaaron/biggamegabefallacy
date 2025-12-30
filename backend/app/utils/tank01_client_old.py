"""
Tank01 NFL API Client

Provides clean interface to Tank01 NFL Live In-Game Real-Time Statistics API.
Includes player data, game logs, betting odds, and rosters.
"""

import httpx
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class Tank01Client:
    """
    Tank01 NFL API client.

    Uses Tank01 as single source of truth for:
    - Player IDs (numeric)
    - Game logs and statistics
    - Player prop betting odds
    - Team rosters
    """

    BASE_URL = "https://tank01-nfl-live-in-game-real-time-statistics-nfl.p.rapidapi.com"

    def __init__(self, api_key: Optional[str] = None):
        """Initialize Tank01 client with API key"""
        self.api_key = api_key or settings.TANK01_API_KEY
        self.headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": "tank01-nfl-live-in-game-real-time-statistics-nfl.p.rapidapi.com"
        }
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

    async def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make GET request to Tank01 API"""
        url = f"{self.BASE_URL}/{endpoint}"

        try:
            response = await self.client.get(url, headers=self.headers, params=params or {})
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Tank01 API error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Tank01 API request failed: {str(e)}")
            raise

    # ============================================================================
    # PLAYER DATA
    # ============================================================================

    async def get_player_list(self, position: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get list of all NFL players.

        Args:
            position: Filter by position (e.g., "WR", "TE")

        Returns:
            List of player dictionaries with playerID, name, team, position
        """
        data = await self._get("getNFLPlayerList")
        players = data.get("body", [])

        if position:
            players = [p for p in players if p.get("pos") == position]

        return players

    async def get_team_roster(self, team_abbr: str) -> Dict[str, Any]:
        """
        Get roster for a specific team.

        Args:
            team_abbr: Team abbreviation (e.g., "MIN", "BUF")

        Returns:
            Dict with team info and roster
        """
        params = {"teamAbv": team_abbr}
        data = await self._get("getNFLTeamRoster", params=params)
        return data.get("body", {})

    # ============================================================================
    # GAME LOGS & STATS
    # ============================================================================

    async def get_player_game_log(
        self,
        player_id: str,
        season: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get game log for a player (season or career).

        Args:
            player_id: Tank01 numeric player ID
            season: Specific season year (e.g., 2024), or None for all

        Returns:
            List of game log entries
        """
        # TODO: Confirm Tank01 endpoint name for player game logs
        # This may be part of getPlayerStats or a separate endpoint
        params = {"playerID": player_id}
        if season:
            params["season"] = season

        try:
            data = await self._get("getPlayerStats", params=params)
            return data.get("body", [])
        except Exception as e:
            logger.warning(f"Failed to fetch game log for player {player_id}: {e}")
            return []

    async def get_player_stats(
        self,
        player_id: str,
        season: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get aggregated stats for a player.

        Args:
            player_id: Tank01 numeric player ID
            season: Specific season year

        Returns:
            Dict with player stats
        """
        params = {"playerID": player_id}
        if season:
            params["season"] = season

        data = await self._get("getPlayerStats", params=params)
        return data.get("body", {})

    # ============================================================================
    # BETTING ODDS
    # ============================================================================

    async def get_betting_odds(
        self,
        game_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get NFL betting odds including player props.

        Args:
            game_id: Specific game ID, or None for all upcoming games

        Returns:
            Dict with betting odds data including player anytime TD props
        """
        params = {}
        if game_id:
            params["gameID"] = game_id

        data = await self._get("getNFLBettingOdds", params=params)
        return data.get("body", {})

    async def get_player_props(
        self,
        week: Optional[int] = None,
        season: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get player prop odds (anytime TD scorer).

        Args:
            week: NFL week number
            season: Season year

        Returns:
            List of player prop odds
        """
        betting_data = await self.get_betting_odds()

        # Extract player props from betting data
        # Tank01 embeds player props within betting odds response
        # Format: {"playerID": "12345", "playerName": "...", "odds": {...}}

        props = []

        # TODO: Parse Tank01 response structure for player props
        # This will depend on exact Tank01 response format
        # Placeholder for now

        return props

    # ============================================================================
    # SCHEDULE
    # ============================================================================

    async def get_schedule(
        self,
        season: int,
        week: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get NFL schedule.

        Args:
            season: Season year
            week: Specific week, or None for full season

        Returns:
            List of scheduled games
        """
        params = {"season": season}
        if week:
            params["week"] = week

        data = await self._get("getNFLGamesForWeek", params=params)
        return data.get("body", [])


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def parse_player_data(tank01_player: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse Tank01 player data into our internal format.

    Args:
        tank01_player: Raw player data from Tank01

    Returns:
        Normalized player dict
    """
    return {
        "player_id": tank01_player.get("playerID"),
        "full_name": tank01_player.get("longName") or tank01_player.get("playerName"),
        "first_name": tank01_player.get("firstName"),
        "last_name": tank01_player.get("lastName"),
        "team_id": tank01_player.get("teamID"),
        "team_name": tank01_player.get("team"),
        "position": tank01_player.get("pos"),
        "height": tank01_player.get("height"),
        "weight": tank01_player.get("weight"),
        "age": tank01_player.get("age"),
        "experience_years": tank01_player.get("exp"),
        "headshot_url": tank01_player.get("espnHeadshot") or tank01_player.get("nflHeadshot"),
    }


def parse_game_log_entry(tank01_game: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse Tank01 game log entry into our internal format.

    Args:
        tank01_game: Raw game log data from Tank01

    Returns:
        Normalized game log dict
    """
    return {
        "player_id": tank01_game.get("playerID"),
        "season_year": tank01_game.get("season"),
        "week": tank01_game.get("week"),
        "opponent": tank01_game.get("opponent"),
        "game_date": tank01_game.get("gameDate"),

        # Receiving stats
        "receptions": int(tank01_game.get("Rec", 0)),
        "receiving_yards": int(tank01_game.get("recYds", 0)),
        "receiving_touchdowns": int(tank01_game.get("recTD", 0)),
        "targets": int(tank01_game.get("targets", 0)),

        # Game result
        "home_score": tank01_game.get("homeScore"),
        "away_score": tank01_game.get("awayScore"),
        "result": tank01_game.get("result"),  # W/L
    }
