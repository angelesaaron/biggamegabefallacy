"""
Tank01 NFL API Client - Updated with Real Response Formats

Based on actual Tank01 API responses from RapidAPI.
"""

import httpx
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class Tank01Client:
    """Tank01 NFL API client with correct endpoint parameters and parsing."""

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
            data = response.json()

            # Tank01 wraps responses in {statusCode, body}
            if isinstance(data, dict) and "body" in data:
                return data["body"]
            return data

        except httpx.HTTPStatusError as e:
            logger.error(f"Tank01 API error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Tank01 API request failed: {str(e)}")
            raise

    # ============================================================================
    # PLAYER DATA
    # ============================================================================

    async def get_team_roster(
        self,
        team_abv: str,
        get_stats: bool = True
    ) -> Dict[str, Any]:
        """
        Get roster for a specific team.

        Args:
            team_abv: Team abbreviation (e.g., "CHI", "MIN")
            get_stats: Include player stats (default True)

        Returns:
            Dict with 'team' and 'roster' array
        """
        params = {
            "teamAbv": team_abv,
            "getStats": str(get_stats).lower()
        }

        data = await self._get("getNFLTeamRoster", params=params)
        return data

    async def get_all_rosters(self, positions: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Get rosters for all NFL teams, optionally filtered by position.

        Args:
            positions: List of positions to filter (e.g., ["WR", "TE"])

        Returns:
            List of player dicts
        """
        # Tank01 doesn't have a single endpoint for all players
        # Need to fetch each team separately
        # This is expensive! Cache the results.

        # NFL team abbreviations
        teams = [
            "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE",
            "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC",
            "LAC", "LAR", "LV", "MIA", "MIN", "NE", "NO", "NYG",
            "NYJ", "PHI", "PIT", "SF", "SEA", "TB", "TEN", "WSH"
        ]

        all_players = []

        for team_abv in teams:
            try:
                roster_data = await self.get_team_roster(team_abv, get_stats=False)
                roster = roster_data.get("roster", [])

                # Filter by position if specified
                if positions:
                    roster = [p for p in roster if p.get("pos") in positions]

                all_players.extend(roster)

            except Exception as e:
                logger.error(f"Failed to fetch roster for {team_abv}: {e}")
                continue

        return all_players

    # ============================================================================
    # GAME LOGS
    # ============================================================================

    async def get_games_for_player(
        self,
        player_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get game logs for a specific player.

        Args:
            player_id: Tank01 numeric player ID
            limit: Number of most recent games to return

        Returns:
            List of game log dicts

        Note: Response does NOT include week numbers! Must be enriched separately.
        """
        params = {
            "playerID": player_id,
            "itemFormat": "list"
        }

        games = await self._get("getNFLGamesForPlayer", params=params)

        # Tank01 returns most recent games first
        if limit:
            games = games[:limit]

        return games

    # ============================================================================
    # BETTING ODDS
    # ============================================================================

    async def get_betting_odds(
        self,
        game_date: Optional[str] = None,
        game_id: Optional[str] = None,
        player_props: bool = True,
        implied_totals: bool = True
    ) -> Dict[str, Any]:
        """
        Get NFL betting odds for a specific date or game.

        Args:
            game_date: Date in format "YYYYMMDD" (e.g., "20250907")
            game_id: Game ID (e.g., "20250907_ARI@NO") - alternative to game_date
            player_props: Include player props (anytime TD, etc.)
            implied_totals: Include implied totals

        Returns:
            Dict with statusCode and body (list of games with odds)
        """
        if not game_date and not game_id:
            raise ValueError("Either game_date or game_id must be provided")

        params = {
            "itemFormat": "list",
            "playerProps": str(player_props).lower(),
            "impliedTotals": str(implied_totals).lower()
        }

        if game_id:
            # Use gameID parameter for specific game
            params["gameID"] = game_id
        elif game_date:
            # Use gameDate for all games on a date
            params["gameDate"] = game_date

        # Don't auto-unwrap for this endpoint - return full response
        url = f"{self.BASE_URL}/getNFLBettingOdds"
        try:
            response = await self.client.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()  # Returns {statusCode: 200, body: [...]}
        except Exception as e:
            logger.error(f"Failed to fetch betting odds: {str(e)}")
            raise

    async def get_player_prop_odds(
        self,
        game_date: str,
        prop_type: str = "anytd"
    ) -> Dict[str, int]:
        """
        Get player prop odds for anytime TD scorer.

        Args:
            game_date: Date in format "YYYYMMDD"
            prop_type: Type of prop bet (default "anytd")

        Returns:
            Dict mapping playerID → odds (American format)
        """
        odds_data = await self.get_betting_odds(game_date, player_props=True)

        player_odds = {}

        for game in odds_data:
            for prop in game.get("playerProps", []):
                player_id = prop.get("playerID")
                prop_bets = prop.get("propBets", {})
                odds = prop_bets.get(prop_type)

                if player_id and odds:
                    # Convert to int
                    try:
                        player_odds[player_id] = int(odds)
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid odds format for player {player_id}: {odds}")

        return player_odds

    # ============================================================================
    # SCHEDULE
    # ============================================================================

    async def get_schedule(
        self,
        season: int,
        week: int,
        season_type: str = "reg"
    ) -> List[Dict[str, Any]]:
        """
        Get NFL schedule for a specific week.

        Args:
            season: Season year (e.g., 2025)
            week: Week number (1-18)
            season_type: "reg" (regular season) or "post" (playoffs)

        Returns:
            List of scheduled games
        """
        params = {
            "season": str(season),
            "week": str(week),
            "seasonType": season_type
        }

        schedule = await self._get("getNFLGamesForWeek", params=params)
        return schedule

    def build_game_week_mapping(self, schedule: List[Dict[str, Any]], week: int) -> Dict[str, int]:
        """
        Build a mapping of gameID → week number from schedule.

        Args:
            schedule: List of games from get_schedule()
            week: Week number for these games

        Returns:
            Dict mapping gameID → week
        """
        mapping = {}
        for game in schedule:
            game_id = game.get("gameID")
            if game_id:
                mapping[game_id] = week

        return mapping

    # ============================================================================
    # BOX SCORE (Optional - Expensive!)
    # ============================================================================

    async def get_box_score(
        self,
        game_id: str,
        play_by_play: bool = False
    ) -> Dict[str, Any]:
        """
        Get detailed box score for a game.

        Args:
            game_id: Game ID in format "YYYYMMDD_AWAY@HOME"
            play_by_play: Include play-by-play data

        Returns:
            Dict with game stats

        Warning: This endpoint is expensive! Only use when necessary.
        """
        params = {
            "gameID": game_id,
            "playByPlay": str(play_by_play).lower()
        }

        box_score = await self._get("getNFLBoxScore", params=params)
        return box_score

    async def get_game_logs_from_box_score(
        self,
        game_id: str,
        season_year: int,
        week: int
    ) -> List[Dict[str, Any]]:
        """
        Fetch box score and extract all player game logs.

        This is the optimized alternative to calling get_games_for_player()
        for each individual player. One box score call gets stats for all
        players in that game.

        Args:
            game_id: Game ID in format "YYYYMMDD_AWAY@HOME"
            season_year: Season year (e.g., 2025)
            week: Week number (1-18)

        Returns:
            List of normalized game log dicts for all players with receiving stats

        Example:
            # Instead of 538 API calls (one per player):
            for player in players:
                logs = await client.get_games_for_player(player.id)

            # Make 16 API calls (one per game):
            for game in games:
                logs = await client.get_game_logs_from_box_score(
                    game.game_id, 2025, 17
                )
        """
        box_score = await self.get_box_score(game_id, play_by_play=False)
        return parse_game_logs_from_box_score(box_score, game_id, season_year, week)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def parse_player_from_roster(tank01_player: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse Tank01 roster player data into our internal format.

    Args:
        tank01_player: Raw player data from getNFLTeamRoster

    Returns:
        Normalized player dict
    """
    return {
        "player_id": tank01_player.get("playerID"),
        "full_name": tank01_player.get("longName") or tank01_player.get("espnName"),
        "team_id": tank01_player.get("teamID"),
        "team_name": tank01_player.get("team"),
        "position": tank01_player.get("pos"),
        "jersey_number": tank01_player.get("jerseyNum"),  # Tank01 field: jerseyNum
        "height": tank01_player.get("height"),  # Keep as string (e.g., '6\'1"')
        "weight": tank01_player.get("weight"),  # Keep as string (may be 'R' for rookies)
        "age": tank01_player.get("age"),        # Keep as string (may be 'R' for rookies)
        "experience_years": tank01_player.get("exp"),  # Keep as string (may be 'R' for rookies)
        "headshot_url": tank01_player.get("espnHeadshot"),
        "active_status": tank01_player.get("isFreeAgent") != "True",  # Active if not free agent
    }


def parse_game_log(tank01_game: Dict[str, Any], week: Optional[int] = None) -> Dict[str, Any]:
    """
    Parse Tank01 game log entry into our internal format.

    Args:
        tank01_game: Raw game log data from getNFLGamesForPlayer
        week: Week number (must be provided separately - Tank01 doesn't include it!)

    Returns:
        Normalized game log dict
    """
    receiving = tank01_game.get("Receiving", {})

    return {
        "player_id": tank01_game.get("playerID"),
        "game_id": tank01_game.get("gameID"),
        "week": week,  # MUST be enriched from schedule mapping
        "team": tank01_game.get("team"),
        "team_id": tank01_game.get("teamID"),

        # Receiving stats
        "receptions": int(receiving.get("receptions", 0)),
        "receiving_yards": int(receiving.get("recYds", 0)),
        "receiving_touchdowns": int(receiving.get("recTD", 0)),
        "targets": int(receiving.get("targets", 0)),

        # Additional stats
        "long_reception": int(receiving.get("longRec", 0)) if receiving.get("longRec") else None,
        "yards_per_reception": float(receiving.get("recAvg", 0.0)) if receiving.get("recAvg") else None,
    }


def extract_season_from_game_id(game_id: str) -> int:
    """
    Extract season year from gameID.

    Args:
        game_id: Format "YYYYMMDD_AWAY@HOME"

    Returns:
        Season year (int)
    """
    date_str = game_id.split('_')[0]
    year = int(date_str[:4])
    return year


def extract_date_from_game_id(game_id: str) -> str:
    """
    Extract date from gameID.

    Args:
        game_id: Format "YYYYMMDD_AWAY@HOME"

    Returns:
        Date string "YYYYMMDD"
    """
    return game_id.split('_')[0]


def parse_game_logs_from_box_score(
    box_score: Dict[str, Any],
    game_id: str,
    season_year: int,
    week: int
) -> List[Dict[str, Any]]:
    """
    Extract all player game logs from a box score response.

    This replaces individual per-player API calls by extracting stats
    for all players from a single box score endpoint.

    Args:
        box_score: Response from get_box_score() API call
        game_id: Game ID (format "YYYYMMDD_AWAY@HOME")
        season_year: Season year (e.g., 2025)
        week: Week number (1-18)

    Returns:
        List of normalized game log dicts, one per player with receiving stats

    Example box_score structure:
        {
          "playerStats": {
            "4685": {
              "playerID": "4685",
              "team": "SF",
              "teamID": "26",
              "Receiving": {
                "recTD": "1",
                "targets": "11",
                "receptions": "11",
                "recYds": "90",
                "longRec": "28",
                "recAvg": "8.2"
              }
            }
          }
        }

    Edge Cases:
        - Players without "Receiving" key are skipped (didn't get targets)
        - Players with Receiving but all zeros are included (played but no production)
        - Only returns players with receiving stats (WR/TE focus)
    """
    game_logs = []

    player_stats = box_score.get("playerStats", {})

    for player_id, stats in player_stats.items():
        # Skip if no receiving stats
        receiving = stats.get("Receiving")
        if not receiving:
            continue

        # Extract team info
        team = stats.get("team", "")
        team_id = stats.get("teamID", "")

        # Parse receiving stats - handle both string and numeric values
        try:
            receptions = int(receiving.get("receptions", 0) or 0)
            rec_yards = int(receiving.get("recYds", 0) or 0)
            rec_tds = int(receiving.get("recTD", 0) or 0)
            targets = int(receiving.get("targets", 0) or 0)

            # Optional stats
            long_rec = receiving.get("longRec")
            long_reception = int(long_rec) if long_rec and str(long_rec).strip() else None

            rec_avg = receiving.get("recAvg")
            yards_per_reception = float(rec_avg) if rec_avg and str(rec_avg).strip() else None

        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse receiving stats for player {player_id}: {e}")
            continue

        # Build normalized game log
        game_log = {
            "player_id": player_id,
            "game_id": game_id,
            "season_year": season_year,
            "week": week,
            "team": team,
            "team_id": team_id,
            "receptions": receptions,
            "receiving_yards": rec_yards,
            "receiving_touchdowns": rec_tds,
            "targets": targets,
            "long_reception": long_reception,
            "yards_per_reception": yards_per_reception,
        }

        game_logs.append(game_log)

    return game_logs
