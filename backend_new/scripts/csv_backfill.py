"""
CSV Backfill Script
-------------------
Populates player_game_logs, games, and team_game_stats from the historical
CSVs in ml/data/ (game_logs_20XX.csv).

Run from backend_new/:
    python scripts/csv_backfill.py [--years 2022 2023 2024 2025]

Notes:
- Only inserts rows for player_ids that exist in the players table (WR/TE synced from Tank01).
- snap_pct, rz_targets, rz_rec_tds are left NULL — nflverse data not in CSVs.
- Games are created as status='final', season_type='reg'.
- Fully idempotent — safe to re-run.
"""

import argparse
import asyncio
import csv
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

# Add backend_new/ to sys.path so app imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import AsyncSessionLocal
from app.models.game import Game
from app.models.player import Player
from app.models.player_game_log import PlayerGameLog
from app.models.team_game_stats import TeamGameStats

ML_DATA_DIR = Path(__file__).parent.parent.parent / "ml" / "data"


def parse_game_id(game_id: str) -> dict:
    """YYYYMMDD_AWAY@HOME → {date, away_team, home_team}"""
    date_part, teams_part = game_id.split("_", 1)
    away_team, home_team = teams_part.split("@", 1)
    return {
        "game_date": date(int(date_part[:4]), int(date_part[4:6]), int(date_part[6:8])),
        "away_team": away_team,
        "home_team": home_team,
    }


def load_csv(year: int) -> list[dict]:
    path = ML_DATA_DIR / f"game_logs_{year}.csv"
    if not path.exists():
        print(f"  [SKIP] {path} not found")
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


async def run(years: list[int]) -> None:
    async with AsyncSessionLocal() as db:
        # Load all known WR/TE player_ids
        result = await db.execute(
            select(Player.player_id).where(Player.position.in_(["WR", "TE"]))
        )
        known_ids: set[str] = {row[0] for row in result}
        print(f"Known WR/TE player_ids in DB: {len(known_ids)}")

        total_games = 0
        total_logs = 0
        total_skipped = 0

        for year in years:
            print(f"\n--- {year} ---")
            rows = load_csv(year)
            if not rows:
                continue

            # Collect unique game_ids for this year
            game_ids: dict[str, dict] = {}
            for row in rows:
                gid = row["game_id"]
                if gid not in game_ids:
                    parsed = parse_game_id(gid)
                    game_ids[gid] = {
                        "game_id": gid,
                        "season": int(row["season"]),
                        "week": int(row["week"]),
                        "season_type": "reg",
                        "home_team": parsed["home_team"],
                        "away_team": parsed["away_team"],
                        "game_date": parsed["game_date"],
                        "status": "final",
                    }

            # Upsert game stubs
            for game_data in game_ids.values():
                stmt = (
                    pg_insert(Game)
                    .values(**game_data)
                    .on_conflict_do_update(
                        index_elements=["game_id"],
                        set_={"status": "final", "updated_at": func.now()},
                    )
                )
                await db.execute(stmt)
            total_games += len(game_ids)
            print(f"  Games upserted: {len(game_ids)}")

            # Insert player_game_logs
            year_written = 0
            year_skipped = 0
            log_rows: list[dict] = []

            for row in rows:
                pid = row["player_id"]
                if pid not in known_ids:
                    year_skipped += 1
                    continue

                gid = row["game_id"]
                parsed = parse_game_id(gid)
                is_home = row["team"] == parsed["home_team"]

                log_rows.append({
                    "player_id": pid,
                    "game_id": gid,
                    "season": int(row["season"]),
                    "week": int(row["week"]),
                    "team": row["team"],
                    "is_home": is_home,
                    "targets": int(row["targets"] or 0),
                    "receptions": int(row["receptions"] or 0),
                    "rec_yards": int(row["rec_yards"] or 0),
                    "rec_tds": int(row["rec_tds"] or 0),
                    "long_rec": int(row["long_rec"]) if row.get("long_rec") else None,
                    "snap_count": None,
                    "snap_pct": None,
                    "rz_targets": None,
                    "rz_rec_tds": None,
                    "data_source_flags": {"csv_backfill": True, "nflverse_snap": False, "nflverse_rz": False},
                })

            for log_data in log_rows:
                stmt = (
                    pg_insert(PlayerGameLog)
                    .values(**log_data)
                    .on_conflict_do_update(
                        constraint="uq_player_game_log",
                        set_={
                            "targets": log_data["targets"],
                            "receptions": log_data["receptions"],
                            "rec_yards": log_data["rec_yards"],
                            "rec_tds": log_data["rec_tds"],
                            "long_rec": log_data["long_rec"],
                            "data_source_flags": log_data["data_source_flags"],
                        },
                    )
                )
                await db.execute(stmt)
                year_written += 1

            print(f"  Logs written: {year_written}  |  Skipped (not in roster): {year_skipped}")
            total_logs += year_written
            total_skipped += year_skipped

            # Aggregate team_game_stats from what we just wrote
            await _upsert_team_stats(db, list(game_ids.keys()), int(rows[0]["season"]))

            await db.commit()

        print(f"\n=== Done ===")
        print(f"Games: {total_games}  |  Logs: {total_logs}  |  Skipped: {total_skipped}")


async def _upsert_team_stats(db, game_ids: list[str], season: int) -> None:
    result = await db.execute(
        select(
            PlayerGameLog.game_id,
            PlayerGameLog.team,
            PlayerGameLog.week,
            PlayerGameLog.targets,
            PlayerGameLog.rec_tds,
            PlayerGameLog.rz_targets,
            PlayerGameLog.rz_rec_tds,
        ).where(PlayerGameLog.game_id.in_(game_ids))
    )
    rows = result.all()

    # Aggregate per (game_id, team)
    teams: dict[tuple, dict] = defaultdict(lambda: {
        "team_targets": 0, "team_rec_tds": 0,
        "team_rz_targets": 0, "team_rz_tds": 0,
        "has_rz": False, "week": 0,
    })
    for row in rows:
        key = (row.game_id, row.team)
        teams[key]["week"] = row.week
        teams[key]["team_targets"] += row.targets or 0
        teams[key]["team_rec_tds"] += row.rec_tds or 0
        if row.rz_targets is not None:
            teams[key]["team_rz_targets"] += row.rz_targets
            teams[key]["has_rz"] = True
        if row.rz_rec_tds is not None:
            teams[key]["team_rz_tds"] += row.rz_rec_tds

    for (game_id, team), totals in teams.items():
        data = {
            "game_id": game_id,
            "team": team,
            "season": season,
            "week": totals["week"],
            "team_targets": totals["team_targets"],
            "team_rec_tds": totals["team_rec_tds"],
            "team_rz_targets": totals["team_rz_targets"] if totals["has_rz"] else None,
            "team_rz_tds": totals["team_rz_tds"] if totals["has_rz"] else None,
        }
        stmt = (
            pg_insert(TeamGameStats)
            .values(**data)
            .on_conflict_do_update(
                constraint="uq_team_game_stats",
                set_={
                    "team_targets": data["team_targets"],
                    "team_rec_tds": data["team_rec_tds"],
                    "team_rz_targets": data["team_rz_targets"],
                    "team_rz_tds": data["team_rz_tds"],
                },
            )
        )
        await db.execute(stmt)

    print(f"  Team stats upserted: {len(teams)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", nargs="+", type=int, default=[2022, 2023, 2024, 2025])
    args = parser.parse_args()
    asyncio.run(run(args.years))
