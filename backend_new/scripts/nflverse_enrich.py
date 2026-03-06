"""
nflverse Enrichment Script
--------------------------
Patches player_game_logs with snap_pct and rz_targets/rz_rec_tds from nflverse,
then re-aggregates team_game_stats rz columns.

Run from backend_new/:
    python scripts/nflverse_enrich.py [--years 2022 2023 2024 2025]

First run downloads nflverse parquet files (cached locally after that).
PBP data is large (~500MB per season) — expect the first run to take a few minutes.
"""

import argparse
import asyncio
import logging
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import AsyncSessionLocal
from app.models.player_game_log import PlayerGameLog
from app.models.team_game_stats import TeamGameStats
from app.utils.nflverse_adapter import NflverseAdapter

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def run(years: list[int]) -> None:
    async with AsyncSessionLocal() as db:
        print(f"Loading nflverse data for seasons: {years}")
        print("(Snap counts download is fast; PBP is large on first run)\n")

        nflverse = await NflverseAdapter(db).load(seasons=years)

        print(f"Resolved snap records        : {len(nflverse.snap)}")
        print(f"Resolved RZ records          : {len(nflverse.rz)}")
        print(f"Team RZ all-pos records      : {len(nflverse.team_rz_all_pos)}")
        print(f"Snap unmatched names         : {len(nflverse.snap_unmatched)}")
        print(f"RZ unmatched names           : {len(nflverse.rz_unmatched)}")
        if nflverse.snap_unmatched:
            print(f"  snap unresolved: {nflverse.snap_unmatched[:15]}")
        if nflverse.rz_unmatched:
            print(f"  rz unresolved : {nflverse.rz_unmatched[:15]}")
        print()

        # Fetch all existing game log (player_id, season, week, game_id, id)
        result = await db.execute(
            select(
                PlayerGameLog.id,
                PlayerGameLog.player_id,
                PlayerGameLog.season,
                PlayerGameLog.week,
                PlayerGameLog.game_id,
            ).where(PlayerGameLog.season.in_(years))
        )
        log_rows = result.all()
        print(f"Existing game log rows to enrich: {len(log_rows)}")

        snap_updated = 0
        rz_updated = 0
        both_updated = 0
        no_match = 0

        for row in log_rows:
            key = (row.player_id, row.season, row.week)
            snap = nflverse.snap.get(key)
            rz = nflverse.rz.get(key)

            if snap is None and rz is None:
                no_match += 1
                continue

            updates: dict = {}
            if snap is not None:
                updates["snap_pct"] = snap.snap_pct
                snap_updated += 1
            if rz is not None:
                updates["rz_targets"] = rz.rz_targets
                updates["rz_rec_tds"] = rz.rz_tds
                rz_updated += 1
            if snap is not None and rz is not None:
                both_updated += 1

            # Update data_source_flags too
            updates["data_source_flags"] = {
                "csv_backfill": True,
                "nflverse_snap": snap is not None,
                "nflverse_rz": rz is not None,
            }

            await db.execute(
                update(PlayerGameLog)
                .where(PlayerGameLog.id == row.id)
                .values(**updates)
            )

        await db.commit()

        print(f"\nSnap updated  : {snap_updated}")
        print(f"RZ updated    : {rz_updated}")
        print(f"Both updated  : {both_updated}")
        print(f"No match      : {no_match}")

        # Write all-position team RZ targets and re-aggregate WR/TE rz columns
        print("\nWriting team_rz_targets_all_pos and re-aggregating rz data...")
        await _write_team_rz_all_pos(db, nflverse.team_rz_all_pos, years)
        await _reaggregate_team_rz(db, years)
        print("Done.")


async def _write_team_rz_all_pos(
    db,
    team_rz_all_pos: dict[tuple[str, int, int], int],
    years: list[int],
) -> None:
    """
    Write team_rz_targets_all_pos to team_game_stats.
    team_rz_all_pos is keyed by (team, season, week).
    We look up the game_id via the games table (one game per team per week).
    """
    from sqlalchemy import select
    from app.models.game import Game

    # Load all games for these years so we can resolve (team, season, week) → game_id
    result = await db.execute(
        select(Game.game_id, Game.home_team, Game.away_team, Game.season, Game.week)
        .where(Game.season.in_(years))
    )
    games = result.all()

    # Build lookup: (team, season, week) → game_id (each team plays once per week)
    game_lookup: dict[tuple[str, int, int], str] = {}
    for g in games:
        game_lookup[(g.home_team, g.season, g.week)] = g.game_id
        game_lookup[(g.away_team, g.season, g.week)] = g.game_id

    updated = 0
    for (team, season, week), total in team_rz_all_pos.items():
        if season not in years:
            continue
        game_id = game_lookup.get((team, season, week))
        if game_id is None:
            continue
        stmt = (
            pg_insert(TeamGameStats)
            .values(
                game_id=game_id, team=team, season=season, week=week,
                team_targets=0, team_rec_tds=0,
                team_rz_targets_all_pos=total,
            )
            .on_conflict_do_update(
                constraint="uq_team_game_stats",
                set_={"team_rz_targets_all_pos": total},
            )
        )
        await db.execute(stmt)
        updated += 1

    await db.commit()
    print(f"  team_rz_targets_all_pos written: {updated}")


async def _reaggregate_team_rz(db, years: list[int]) -> None:
    """Recompute team_rz_targets and team_rz_tds from updated player_game_logs."""
    result = await db.execute(
        select(
            PlayerGameLog.game_id,
            PlayerGameLog.team,
            PlayerGameLog.week,
            PlayerGameLog.season,
            PlayerGameLog.rz_targets,
            PlayerGameLog.rz_rec_tds,
        ).where(PlayerGameLog.season.in_(years))
    )
    rows = result.all()

    teams: dict[tuple, dict] = defaultdict(lambda: {
        "team_rz_targets": 0, "team_rz_tds": 0, "has_rz": False,
        "week": 0, "season": 0,
    })
    for row in rows:
        key = (row.game_id, row.team)
        teams[key]["week"] = row.week
        teams[key]["season"] = row.season
        if row.rz_targets is not None:
            teams[key]["team_rz_targets"] += row.rz_targets
            teams[key]["has_rz"] = True
        if row.rz_rec_tds is not None:
            teams[key]["team_rz_tds"] += row.rz_rec_tds

    updated = 0
    for (game_id, team), totals in teams.items():
        if not totals["has_rz"]:
            continue
        stmt = (
            pg_insert(TeamGameStats)
            .values(
                game_id=game_id,
                team=team,
                season=totals["season"],
                week=totals["week"],
                team_targets=0,  # won't overwrite — see set_ below
                team_rec_tds=0,
                team_rz_targets=totals["team_rz_targets"],
                team_rz_tds=totals["team_rz_tds"],
            )
            .on_conflict_do_update(
                constraint="uq_team_game_stats",
                set_={
                    "team_rz_targets": totals["team_rz_targets"],
                    "team_rz_tds": totals["team_rz_tds"],
                },
            )
        )
        await db.execute(stmt)
        updated += 1

    await db.commit()
    print(f"Team stats rz updated: {updated}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", nargs="+", type=int, default=[2022, 2023, 2024, 2025])
    args = parser.parse_args()
    asyncio.run(run(args.years))
