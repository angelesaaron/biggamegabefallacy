"""
NflverseAdapter — wraps nflreadpy to provide snap count and red zone PBP data.

ID bridge resolution (espn_id in nflverse == playerID in Tank01):
  nflverse_snap  — load_snap_counts()  → pfr_player_id  → pfr_to_tank01  dict → Tank01 player_id
  nflverse_pbp   — load_pbp()         → receiver_player_id (GSIS) → gsis_to_tank01 dict → Tank01 player_id

Bridge is built once per load() call via nflreadpy.load_players() (cross-reference table),
fetched concurrently with snap/PBP data. No DB queries needed for resolution.

Unmatched players (absent from load_players() — typically brand-new rookies before nflverse
updates its registry) are returned in snap_unmatched / rz_unmatched for DQE logging.

nflreadpy is a synchronous library (parquet downloads). All calls are run via
asyncio.to_thread() so the FastAPI event loop stays unblocked.

Caching:
  nflreadpy uses update_config(cache_mode="filesystem", cache_dir=...) instead of
  per-call parameters. Configured once per fetch call inside the thread.

Team abbreviation normalisation:
  nflverse uses 'LA' for Rams and 'WAS' for Washington; Tank01 uses 'LAR' / 'WSH'.
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Callable

from app.config import settings

logger = logging.getLogger(__name__)

# Team abbreviation map: nflverse → Tank01
_TEAM_MAP: dict[str, str] = {"LA": "LAR", "WAS": "WSH"}


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class SnapRecord:
    player_id: str
    team: str
    season: int
    week: int
    snap_pct: float | None


@dataclass
class RZRecord:
    player_id: str
    team: str
    season: int
    week: int
    rz_targets: int
    rz_tds: int


@dataclass
class NflverseResult:
    """Resolved data ready for player_game_logs enrichment."""
    # Keyed by (player_id, season, week)
    snap: dict[tuple[str, int, int], SnapRecord]
    rz: dict[tuple[str, int, int], RZRecord]
    # All-position team RZ targets — keyed by (team, season, week).
    # Used as the denominator for rz_target_share (matches training methodology).
    team_rz_all_pos: dict[tuple[str, int, int], int]
    # IDs/names that failed resolution (absent from load_players() bridge)
    snap_unmatched: list[str]
    rz_unmatched: list[str]


# ── Public adapter ─────────────────────────────────────────────────────────────

class NflverseAdapter:
    """
    Fetches and resolves nflverse snap + red zone data for a list of seasons.

    Usage:
        adapter = NflverseAdapter(db)
        result = await adapter.load(seasons=[2025])
        snap = result.snap.get((player_id, 2025, 7))

    Resolution is entirely ID-bridge based (nflreadpy.load_players cross-reference).
    No DB access needed.
    """

    async def load(self, seasons: list[int]) -> NflverseResult:
        """
        Download snap + PBP data for the given seasons and resolve all players
        to Tank01 player_ids via the nflverse ID bridge.

        All three network calls (load_players, load_snap_counts, load_pbp) run
        concurrently in the thread pool.
        """
        (gsis_to_tank01, pfr_to_tank01), snap_data, (rz_data, team_rz_data) = (
            await asyncio.gather(
                asyncio.to_thread(_fetch_player_bridge, settings.NFLVERSE_CACHE_DIR),
                asyncio.to_thread(_fetch_snap_counts, seasons),
                asyncio.to_thread(_fetch_rz_pbp, seasons),
            )
        )

        snap_resolver = _build_snap_resolver(pfr_to_tank01)
        pbp_resolver = _build_pbp_resolver(gsis_to_tank01)

        snap_result, snap_unmatched = _resolve_snap(snap_data, snap_resolver)
        rz_result, rz_unmatched = _resolve_rz(rz_data, pbp_resolver)
        team_rz_all_pos = _build_team_rz_all_pos(team_rz_data)

        if snap_unmatched:
            logger.warning(
                "nflverse_snap: %d unresolved players (not in load_players() bridge): %s",
                len(snap_unmatched),
                snap_unmatched[:10],
            )
        if rz_unmatched:
            logger.warning(
                "nflverse_pbp: %d unresolved players (not in load_players() bridge): %s",
                len(rz_unmatched),
                rz_unmatched[:10],
            )

        return NflverseResult(
            snap=snap_result,
            rz=rz_result,
            team_rz_all_pos=team_rz_all_pos,
            snap_unmatched=snap_unmatched,
            rz_unmatched=rz_unmatched,
        )


# ── nflreadpy fetch functions (sync, run in thread pool) ─────────────────────

def _configure_nflreadpy_cache(cache_dir: str) -> None:
    """Configure nflreadpy filesystem cache. Called once per thread before any load_*."""
    from pathlib import Path
    from nflreadpy.config import update_config
    update_config(cache_mode="filesystem", cache_dir=Path(cache_dir))


def _fetch_player_bridge(cache_dir: str) -> tuple[dict[str, str], dict[str, str]]:
    """
    Build Tank01 player ID lookup tables from nflreadpy cross-reference data.
    espn_id in nflverse == playerID in Tank01 (canonical system key).

    Returns:
        gsis_to_tank01: {gsis_id: tank01_player_id}  — for PBP resolution
        pfr_to_tank01:  {pfr_id: tank01_player_id}   — for snap resolution
    """
    import nflreadpy as nfl

    os.makedirs(cache_dir, exist_ok=True)
    _configure_nflreadpy_cache(cache_dir)

    logger.info("Fetching nflverse player bridge (cache_dir: %s)", cache_dir)
    df = nfl.load_players().to_pandas()
    df = df[df["espn_id"].notna()].copy()
    # espn_id arrives as float from parquet (e.g. 4047646.0) — cast via int to drop ".0"
    df["espn_id"] = df["espn_id"].astype(float).astype(int).astype(str)

    gsis_to_tank01 = (
        df[df["gsis_id"].notna()]
        .set_index("gsis_id")["espn_id"]
        .to_dict()
    )
    pfr_to_tank01 = (
        df[df["pfr_id"].notna()]
        .set_index("pfr_id")["espn_id"]
        .to_dict()
    )
    logger.info(
        "Player bridge built: %d GSIS entries, %d PFR entries",
        len(gsis_to_tank01), len(pfr_to_tank01),
    )
    return gsis_to_tank01, pfr_to_tank01


def _fetch_snap_counts(seasons: list[int]) -> list[dict]:
    """
    Download snap count data via nflreadpy.
    Returns list of dicts with keys: player, pfr_player_id, team, season, week, offense_pct.

    Cache behaviour:
      nflreadpy saves parquet files to NFLVERSE_CACHE_DIR (default ~/.bggtdm_cache/nflverse).
      On ephemeral hosting (e.g. Render free tier), this cache is wiped on each deploy.
      First ingest after a cold deploy will re-download. For production, mount a persistent
      disk and point NFLVERSE_CACHE_DIR at it.
    """
    import nflreadpy as nfl

    cache_dir = settings.NFLVERSE_CACHE_DIR
    os.makedirs(cache_dir, exist_ok=True)
    _configure_nflreadpy_cache(cache_dir)

    logger.info("Fetching nflverse snap counts for seasons: %s (cache_dir: %s)", seasons, cache_dir)
    df = nfl.load_snap_counts(seasons).to_pandas()
    df = df[df["position"].isin(["WR", "TE"])][
        ["player", "pfr_player_id", "season", "week", "team", "offense_pct"]
    ].copy()
    df["season"] = df["season"].astype(int)
    df["week"] = df["week"].astype(int)
    df["offense_pct"] = df["offense_pct"].astype(float)
    df["team"] = df["team"].replace(_TEAM_MAP)
    return df.to_dict("records")


def _fetch_rz_pbp(seasons: list[int]) -> tuple[list[dict], list[dict]]:
    """
    Download PBP data and aggregate red zone (≤20 yard line) pass targets.

    Returns (player_rows, team_rows):
      player_rows — per-player/game: gsis_id, name_short, team, season, week, rz_targets, rz_tds
      team_rows   — per-team/game (ALL positions): team, season, week, team_rz_targets
                    Used as the denominator for rz_target_share — matches training.

    Cache behaviour: same as _fetch_snap_counts — see that docstring.
    """
    import nflreadpy as nfl

    cache_dir = settings.NFLVERSE_CACHE_DIR
    os.makedirs(cache_dir, exist_ok=True)
    _configure_nflreadpy_cache(cache_dir)

    logger.info(
        "Fetching nflverse PBP for seasons: %s (may be slow on first run; cache: %s)",
        seasons, cache_dir,
    )
    pbp = nfl.load_pbp(seasons).to_pandas()

    # Filter to red zone pass plays with a named receiver
    rz = pbp[
        (pbp["play_type"] == "pass")
        & (pbp["yardline_100"] <= 20)
        & pbp["receiver_player_id"].notna()
    ][["receiver_player_id", "receiver_player_name", "posteam", "season", "week", "touchdown"]].copy()

    rz["season"] = rz["season"].astype(int)
    rz["week"] = rz["week"].astype(int)
    rz["posteam"] = rz["posteam"].replace(_TEAM_MAP)

    # Player-level aggregation — gsis_id is 1:1 with receiver_player_name, safe to include
    player_agg = (
        rz.groupby(["receiver_player_id", "receiver_player_name", "posteam", "season", "week"])
        .agg(rz_targets=("receiver_player_name", "count"), rz_tds=("touchdown", "sum"))
        .reset_index()
        .rename(columns={
            "receiver_player_id": "gsis_id",
            "receiver_player_name": "name_short",
            "posteam": "team",
        })
    )
    player_agg["rz_targets"] = player_agg["rz_targets"].astype(int)
    player_agg["rz_tds"] = player_agg["rz_tds"].astype(int)

    # Team-level aggregation — ALL positions, correct denominator for rz_target_share
    team_agg = (
        rz.groupby(["posteam", "season", "week"])
        .agg(team_rz_targets=("receiver_player_name", "count"))
        .reset_index()
        .rename(columns={"posteam": "team"})
    )
    team_agg["team_rz_targets"] = team_agg["team_rz_targets"].astype(int)

    return player_agg.to_dict("records"), team_agg.to_dict("records")


# ── ID resolution ─────────────────────────────────────────────────────────────

def _build_snap_resolver(
    pfr_to_tank01: dict[str, str],
) -> Callable[[str | None], str | None]:
    """Maps pfr_player_id → Tank01 player_id. Returns None if absent from bridge."""
    def resolve(pfr_id: str | None) -> str | None:
        if pfr_id:
            return pfr_to_tank01.get(pfr_id)
        return None
    return resolve


def _build_pbp_resolver(
    gsis_to_tank01: dict[str, str],
) -> Callable[[str | None], str | None]:
    """Maps receiver_player_id (GSIS) → Tank01 player_id. Returns None if absent from bridge."""
    def resolve(gsis_id: str | None) -> str | None:
        if gsis_id:
            return gsis_to_tank01.get(gsis_id)
        return None
    return resolve


# ── Team RZ all-position aggregation ─────────────────────────────────────────

def _build_team_rz_all_pos(
    rows: list[dict],
) -> dict[tuple[str, int, int], int]:
    """Build (team, season, week) → total all-position RZ targets dict."""
    result: dict[tuple[str, int, int], int] = {}
    for row in rows:
        key = (row["team"], int(row["season"]), int(row["week"]))
        result[key] = int(row["team_rz_targets"])
    return result


# ── Resolution helpers ────────────────────────────────────────────────────────

def _resolve_snap(
    rows: list[dict],
    resolve: Callable[[str | None], str | None],
) -> tuple[dict[tuple[str, int, int], SnapRecord], list[str]]:
    resolved: dict[tuple[str, int, int], SnapRecord] = {}
    unmatched: list[str] = []
    seen_unmatched: set[str] = set()

    for row in rows:
        player_id = resolve(row.get("pfr_player_id"))
        if player_id is None:
            name = row["player"]
            if name not in seen_unmatched:
                unmatched.append(name)
                seen_unmatched.add(name)
            continue

        key = (player_id, int(row["season"]), int(row["week"]))
        resolved[key] = SnapRecord(
            player_id=player_id,
            team=row["team"],
            season=int(row["season"]),
            week=int(row["week"]),
            snap_pct=row.get("offense_pct"),
        )

    return resolved, unmatched


def _resolve_rz(
    rows: list[dict],
    resolve: Callable[[str | None], str | None],
) -> tuple[dict[tuple[str, int, int], RZRecord], list[str]]:
    resolved: dict[tuple[str, int, int], RZRecord] = {}
    unmatched: list[str] = []
    seen_unmatched: set[str] = set()

    for row in rows:
        player_id = resolve(row.get("gsis_id"))
        if player_id is None:
            name = row["name_short"]
            if name not in seen_unmatched:
                unmatched.append(name)
                seen_unmatched.add(name)
            continue

        key = (player_id, int(row["season"]), int(row["week"]))
        # If a player had multiple RZ entries for the same game-week (shouldn't happen
        # after aggregation, but guard anyway by summing)
        if key in resolved:
            existing = resolved[key]
            resolved[key] = RZRecord(
                player_id=player_id,
                team=existing.team,
                season=existing.season,
                week=existing.week,
                rz_targets=existing.rz_targets + int(row["rz_targets"]),
                rz_tds=existing.rz_tds + int(row["rz_tds"]),
            )
        else:
            resolved[key] = RZRecord(
                player_id=player_id,
                team=row["team"],
                season=int(row["season"]),
                week=int(row["week"]),
                rz_targets=int(row["rz_targets"]),
                rz_tds=int(row["rz_tds"]),
            )

    return resolved, unmatched
