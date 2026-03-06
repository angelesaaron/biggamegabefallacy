"""
NflverseAdapter — wraps nfl_data_py to provide snap count and red zone PBP data.

Two data sources, two name formats:
  nflverse_snap  — import_snap_counts()  → player column is FULL NAME ("D.K. Metcalf")
  nflverse_pbp   — import_pbp_data()    → receiver_player_name is SHORT NAME ("D.Metcalf")

Alias resolution:
  1. Check player_aliases table (source='nflverse_snap' or 'nflverse_pbp')
  2. For snap: fall back to exact match on players.full_name
  3. For PBP: fall back to auto-derived short format ("First Last" → "F.Last")
  4. No match → emit DataQualityEvent, skip player

nfl_data_py is a synchronous library (parquet downloads). All calls are run via
asyncio.to_thread() so the FastAPI event loop stays unblocked.

Team abbreviation normalisation:
  nflverse uses 'LA' for Rams and 'WAS' for Washington; Tank01 uses 'LAR' / 'WSH'.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.player import Player
from app.models.player_alias import PlayerAlias

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
    # Names that failed resolution
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
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def load(self, seasons: list[int]) -> NflverseResult:
        """
        Download snap + PBP data for the given seasons and resolve all names
        to player_ids via the alias table.

        This is the single entry point for the ingest service.
        """
        # Load alias lookup tables from DB (one query each)
        snap_aliases = await self._load_aliases("nflverse_snap")
        pbp_aliases = await self._load_aliases("nflverse_pbp")
        players = await self._load_players()

        # Build resolvers
        snap_resolver = _build_snap_resolver(snap_aliases, players)
        pbp_resolver = _build_pbp_resolver(pbp_aliases, players)

        # Fetch data in thread pool (nfl_data_py is sync)
        snap_data, rz_data = await asyncio.gather(
            asyncio.to_thread(_fetch_snap_counts, seasons),
            asyncio.to_thread(_fetch_rz_pbp, seasons),
        )

        snap_result, snap_unmatched = _resolve_snap(snap_data, snap_resolver)
        rz_result, rz_unmatched = _resolve_rz(rz_data, pbp_resolver)

        if snap_unmatched:
            logger.warning(
                "nflverse_snap: %d unresolved names (add to player_aliases): %s",
                len(snap_unmatched),
                snap_unmatched[:10],
            )
        if rz_unmatched:
            logger.warning(
                "nflverse_pbp: %d unresolved names: %s",
                len(rz_unmatched),
                rz_unmatched[:10],
            )

        return NflverseResult(
            snap=snap_result,
            rz=rz_result,
            snap_unmatched=snap_unmatched,
            rz_unmatched=rz_unmatched,
        )

    # ── DB helpers ────────────────────────────────────────────────────────────

    async def _load_aliases(self, source: str) -> dict[str, str]:
        """Returns {alias_name_lower: player_id} for the given source."""
        rows = await self._db.execute(
            select(PlayerAlias.alias_name, PlayerAlias.player_id)
            .where(PlayerAlias.source == source)
            .where(PlayerAlias.active.is_(True))
        )
        return {row.alias_name.lower(): row.player_id for row in rows}

    async def _load_players(self) -> list[Player]:
        """Load all active WR/TE players."""
        rows = await self._db.execute(
            select(Player).where(Player.position.in_(["WR", "TE"]))
        )
        return list(rows.scalars().all())


# ── nfl_data_py fetch functions (sync, run in thread pool) ────────────────────

def _fetch_snap_counts(seasons: list[int]) -> list[dict]:
    """
    Download snap count data via nfl_data_py.
    Returns list of dicts with keys: player, team, season, week, offense_pct.
    nfl_data_py caches parquet locally after first download.
    """
    import nfl_data_py as nfl  # import here to avoid startup cost if not used

    logger.info("Fetching nflverse snap counts for seasons: %s", seasons)
    df = nfl.import_snap_counts(seasons)
    df = df[df["position"].isin(["WR", "TE"])][
        ["player", "season", "week", "team", "offense_pct"]
    ].copy()
    df["season"] = df["season"].astype(int)
    df["week"] = df["week"].astype(int)
    df["offense_pct"] = df["offense_pct"].astype(float)
    df["team"] = df["team"].replace(_TEAM_MAP)
    return df.to_dict("records")


def _fetch_rz_pbp(seasons: list[int]) -> list[dict]:
    """
    Download PBP data and aggregate red zone (≤20 yard line) pass targets per player/game.
    Returns list of dicts with keys: name_short, team, season, week, rz_targets, rz_tds.
    """
    import nfl_data_py as nfl

    logger.info("Fetching nflverse PBP for seasons: %s (may be slow on first run)", seasons)
    pbp = nfl.import_pbp_data(seasons)

    # Filter to red zone pass plays with a named receiver
    rz = pbp[
        (pbp["play_type"] == "pass")
        & (pbp["yardline_100"] <= 20)
        & pbp["receiver_player_id"].notna()
    ][["receiver_player_name", "posteam", "season", "week", "touchdown"]].copy()

    rz["season"] = rz["season"].astype(int)
    rz["week"] = rz["week"].astype(int)
    rz["posteam"] = rz["posteam"].replace(_TEAM_MAP)

    agg = (
        rz.groupby(["receiver_player_name", "posteam", "season", "week"])
        .agg(rz_targets=("receiver_player_name", "count"), rz_tds=("touchdown", "sum"))
        .reset_index()
        .rename(columns={"receiver_player_name": "name_short", "posteam": "team"})
    )
    agg["rz_targets"] = agg["rz_targets"].astype(int)
    agg["rz_tds"] = agg["rz_tds"].astype(int)
    return agg.to_dict("records")


# ── Name resolution ───────────────────────────────────────────────────────────

def _build_snap_resolver(
    aliases: dict[str, str],
    players: list[Player],
) -> Callable[[str], str | None]:
    """
    Returns a function that maps a nflverse_snap name → player_id.

    Priority:
      1. player_aliases table (source='nflverse_snap')
      2. Exact match on players.full_name (lowercase)
    """
    direct = {p.full_name.lower(): p.player_id for p in players}

    def resolve(name: str) -> str | None:
        norm = name.lower().strip()
        return aliases.get(norm) or direct.get(norm)

    return resolve


def _build_pbp_resolver(
    aliases: dict[str, str],
    players: list[Player],
) -> Callable[[str], str | None]:
    """
    Returns a function that maps a nflverse_pbp short name → player_id.

    Priority:
      1. player_aliases table (source='nflverse_pbp')
      2. Auto-derive: "First Last" → "F.Last" lookup against all player full names
    """
    # Build short_name → player_id from all players
    short_lookup: dict[str, str] = {}
    for p in players:
        short = _to_short(p.full_name).lower()
        # Keep the first match only (rare collision — edge cases go in alias table)
        if short not in short_lookup:
            short_lookup[short] = p.player_id

    def resolve(name: str) -> str | None:
        norm = name.lower().strip()
        return aliases.get(norm) or short_lookup.get(norm)

    return resolve


def _to_short(full_name: str) -> str:
    """
    Convert "First Last" to "F.Last" (nflverse PBP short format).
    Handles multi-word last names: "Brian Thomas Jr" → "B.Thomas Jr"
    """
    parts = full_name.strip().split()
    if len(parts) >= 2:
        return f"{parts[0][0]}.{' '.join(parts[1:])}"
    return full_name


# ── Resolution helpers ────────────────────────────────────────────────────────

def _resolve_snap(
    rows: list[dict],
    resolve: Callable[[str], str | None],
) -> tuple[dict[tuple[str, int, int], SnapRecord], list[str]]:
    resolved: dict[tuple[str, int, int], SnapRecord] = {}
    unmatched: list[str] = []
    seen_unmatched: set[str] = set()

    for row in rows:
        player_id = resolve(row["player"])
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
    resolve: Callable[[str], str | None],
) -> tuple[dict[tuple[str, int, int], RZRecord], list[str]]:
    resolved: dict[tuple[str, int, int], RZRecord] = {}
    unmatched: list[str] = []
    seen_unmatched: set[str] = set()

    for row in rows:
        player_id = resolve(row["name_short"])
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
