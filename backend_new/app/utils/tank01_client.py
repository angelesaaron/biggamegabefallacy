"""
Tank01 NFL API client (RapidAPI).

Design principles:
- Box-score-first: fetch one box score per game (16 calls/week) rather than
  one call per player (500+ calls/week).
- All methods are async (httpx.AsyncClient).
- Retry with exponential backoff on 429 / 5xx.
- Callers receive raw parsed body dicts — normalisation happens in services.
"""

import asyncio
import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = (
    "https://tank01-nfl-live-in-game-real-time-statistics-nfl.p.rapidapi.com"
)
_MAX_RETRIES = 3
_RETRY_STATUSES = {429, 500, 502, 503, 504}


class Tank01Client:
    """Async HTTP client for the Tank01 NFL API."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.TANK01_API_KEY
        self._headers = {
            "X-RapidAPI-Key": self._api_key,
            "X-RapidAPI-Host": (
                "tank01-nfl-live-in-game-real-time-statistics-nfl.p.rapidapi.com"
            ),
        }
        self._client = httpx.AsyncClient(timeout=30.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "Tank01Client":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    # ── Private ──────────────────────────────────────────────────────────────

    async def _get(self, endpoint: str, params: dict | None = None) -> Any:
        """GET with retry. Returns the unwrapped response body."""
        url = f"{_BASE_URL}/{endpoint}"
        params = params or {}
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                resp = await self._client.get(url, headers=self._headers, params=params)

                if resp.status_code in _RETRY_STATUSES:
                    wait = 2 ** attempt
                    logger.warning(
                        "Tank01 %s → %d, retrying in %ds (attempt %d/%d)",
                        endpoint, resp.status_code, wait, attempt + 1, _MAX_RETRIES,
                    )
                    await asyncio.sleep(wait)
                    continue

                resp.raise_for_status()
                data = resp.json()

                # Tank01 wraps all responses: {"statusCode": 200, "body": ...}
                return data.get("body", data) if isinstance(data, dict) else data

            except httpx.HTTPStatusError as exc:
                logger.error("Tank01 HTTP error %s: %s", endpoint, exc)
                last_exc = exc
                break
            except httpx.RequestError as exc:
                wait = 2 ** attempt
                logger.warning("Tank01 request error %s, retrying in %ds: %s", endpoint, wait, exc)
                last_exc = exc
                await asyncio.sleep(wait)

        raise last_exc or RuntimeError(f"Tank01 {endpoint} failed after {_MAX_RETRIES} attempts")

    # ── Roster ────────────────────────────────────────────────────────────────

    async def get_team_roster(self, team_abv: str) -> dict:
        """
        Fetch a single team's roster.
        Returns Tank01 body: {"team": ..., "roster": [...]}
        """
        return await self._get("getNFLTeamRoster", {"teamAbv": team_abv, "getStats": "false"})

    # ── Schedule ──────────────────────────────────────────────────────────────

    async def get_schedule_week(self, season: int, week: int) -> list[dict]:
        """
        Fetch all games for a regular-season week.
        Returns list of game dicts with at minimum: gameID, gameDate, home, away, gameStatus.
        """
        body = await self._get(
            "getNFLGamesForWeek",
            {"season": str(season), "week": str(week), "seasonType": "reg"},
        )
        # Tank01 may return a list or a dict with a key
        if isinstance(body, list):
            return body
        return body.get("schedule", body.get("games", []))

    # ── Box score (primary game-log source) ───────────────────────────────────

    async def get_box_score(self, game_id: str) -> dict:
        """
        Fetch box score for a completed game.
        Key fields: playerStats → {player_id: {Receiving: {...}}}
        This is the preferred approach: 16 API calls/week for all player stats.
        """
        return await self._get("getNFLBoxScore", {"gameID": game_id, "playByPlay": "false"})

    # ── Odds ──────────────────────────────────────────────────────────────────

    async def get_player_props(self, game_date: str) -> list[dict]:
        """
        Fetch player prop odds for all games on a date (format: "YYYYMMDD").
        Returns raw body list — callers filter for prop_type='anytd'.
        """
        body = await self._get(
            "getNFLBettingOdds",
            {"gameDate": game_date, "playerProps": "true", "impliedTotals": "false", "itemFormat": "list"},
        )
        if isinstance(body, list):
            return body
        return body.get("games", [])


# ── Parsing helpers (pure functions, no I/O) ─────────────────────────────────

NFL_TEAMS = [
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE",
    "DAL", "DEN", "DET", "GB",  "HOU", "IND", "JAX", "KC",
    "LAC", "LAR", "LV",  "MIA", "MIN", "NE",  "NO",  "NYG",
    "NYJ", "PHI", "PIT", "SF",  "SEA", "TB",  "TEN", "WSH",
]


def parse_teams_from_game_id(game_id: str) -> tuple[str, str]:
    """'YYYYMMDD_AWAY@HOME' → (away_team, home_team)"""
    matchup = game_id.split("_")[1]
    away, home = matchup.split("@")
    return away, home


def parse_player_from_roster(raw: dict) -> dict:
    """
    Normalise a Tank01 roster player entry.
    Returns a dict suitable for upserting into the players table.
    """
    exp_raw = raw.get("exp", "")
    try:
        experience = int(exp_raw)
    except (ValueError, TypeError):
        experience = 0 if str(exp_raw).upper() == "R" else None

    return {
        "player_id": raw.get("playerID"),
        "full_name": raw.get("longName") or raw.get("espnName") or "",
        "position": raw.get("pos", ""),
        "team": raw.get("team") or raw.get("teamAbv"),
        "is_te": raw.get("pos") == "TE",
        "experience": experience,
        "active": raw.get("isFreeAgent", "False") != "True",
        "headshot_url": raw.get("espnHeadshot"),
    }


def parse_game_from_schedule(raw: dict, season: int, week: int) -> dict:
    """
    Normalise a Tank01 schedule game entry.
    Returns a dict suitable for upserting into the games table.
    """
    game_id = raw.get("gameID", "")
    return {
        "game_id": game_id,
        "season": season,
        "week": week,
        "season_type": "reg",
        "home_team": raw.get("home", ""),
        "away_team": raw.get("away", ""),
        "game_date": game_id[:8] if game_id else None,  # "YYYYMMDD"
        "status": _normalise_status(raw.get("gameStatus", "scheduled")),
    }


def _normalise_status(raw: str) -> str:
    raw = (raw or "").lower()
    if "final" in raw or "completed" in raw:
        return "final"
    if "progress" in raw or "live" in raw or "quarter" in raw or "half" in raw:
        return "in_progress"
    return "scheduled"


def parse_game_logs_from_box_score(
    box_score: dict,
    game_id: str,
    season: int,
    week: int,
) -> list[dict]:
    """
    Extract per-player receiving stats from a Tank01 box score.
    Skips players with no Receiving key (non-skill positions).
    Returns list of dicts ready for PlayerGameLog upsert.
    """
    away, home = parse_teams_from_game_id(game_id)
    logs = []

    for player_id, stats in box_score.get("playerStats", {}).items():
        receiving = stats.get("Receiving")
        if not receiving:
            continue

        team = stats.get("team", "")
        try:
            log = {
                "player_id": player_id,
                "game_id": game_id,
                "season": season,
                "week": week,
                "team": team,
                "is_home": team == home,
                "targets": _int(receiving.get("targets")),
                "receptions": _int(receiving.get("receptions")),
                "rec_yards": _int(receiving.get("recYds")),
                "rec_tds": _int(receiving.get("recTD")),
                "long_rec": _int_or_none(receiving.get("longRec")),
            }
            logs.append(log)
        except Exception as exc:
            logger.warning("Failed to parse box score row for %s: %s", player_id, exc)

    return logs


def parse_anytime_td_odds(games_body: list[dict]) -> list[dict]:
    """
    Extract anytime TD player props from the getNFLBettingOdds response.
    Returns list of {player_id, game_id, odds (American int)} dicts.
    """
    results = []
    for game in games_body:
        game_id = game.get("gameID", "")
        for prop in game.get("playerProps", []):
            player_id = prop.get("playerID")
            prop_bets = prop.get("propBets") or {}
            odds_raw = prop_bets.get("anytd")
            if not player_id or odds_raw is None:
                continue
            try:
                results.append({"player_id": player_id, "game_id": game_id, "odds": int(odds_raw)})
            except (ValueError, TypeError):
                pass
    return results


# ── Internal helpers ──────────────────────────────────────────────────────────

def _int(v: Any, default: int = 0) -> int:
    try:
        return int(v or 0)
    except (ValueError, TypeError):
        return default


def _int_or_none(v: Any) -> int | None:
    if v is None or str(v).strip() == "":
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None
