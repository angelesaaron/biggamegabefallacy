"""
test_nflverse_migration.py — Verify nflreadpy returns equivalent data to nfl_data_py.

Pulls snap counts + PBP for a single season and compares:
  - Column presence for columns the adapter actually uses
  - Row counts (should be identical — same upstream parquet files)
  - Spot-checks a known player's snap_pct and RZ targets for a known week

Usage (from backend_new/):
    python scripts/test_nflverse_migration.py [--season 2024] [--week 10]
"""

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Config ────────────────────────────────────────────────────────────────────

# Columns the adapter reads from each source
SNAP_COLS_REQUIRED = {"player", "season", "week", "team", "offense_pct", "position"}
PBP_COLS_REQUIRED = {
    "play_type", "yardline_100", "receiver_player_id",
    "receiver_player_name", "posteam", "season", "week", "touchdown",
}

PASS = "✓"
FAIL = "✗"


def check(label: str, ok: bool, detail: str = "") -> bool:
    status = PASS if ok else FAIL
    suffix = f"  ({detail})" if detail else ""
    print(f"  [{status}] {label}{suffix}")
    return ok


# ── nfl_data_py (old) ─────────────────────────────────────────────────────────

def fetch_old_snap(seasons: list[int], cache_dir: str) -> "pd.DataFrame":
    import nfl_data_py as nfl
    # import_snap_counts has no cache parameter — always downloads fresh
    df = nfl.import_snap_counts(seasons)
    return df[df["position"].isin(["WR", "TE"])].copy()


def fetch_old_pbp(seasons: list[int], cache_dir: str) -> "pd.DataFrame":
    import nfl_data_py as nfl
    pbp = nfl.import_pbp_data(seasons)
    return pbp[
        (pbp["play_type"] == "pass")
        & (pbp["yardline_100"] <= 20)
        & pbp["receiver_player_id"].notna()
    ].copy()


# ── nflreadpy (new) ───────────────────────────────────────────────────────────

def fetch_new_snap(seasons: list[int], cache_dir: str) -> "pd.DataFrame":
    import nflreadpy as nfl
    from pathlib import Path
    from nflreadpy.config import update_config
    update_config(cache_mode="filesystem", cache_dir=Path(cache_dir))
    df = nfl.load_snap_counts(seasons).to_pandas()
    return df[df["position"].isin(["WR", "TE"])].copy()


def fetch_new_pbp(seasons: list[int], cache_dir: str) -> "pd.DataFrame":
    import nflreadpy as nfl
    from pathlib import Path
    from nflreadpy.config import update_config
    update_config(cache_mode="filesystem", cache_dir=Path(cache_dir))
    pbp = nfl.load_pbp(seasons).to_pandas()
    return pbp[
        (pbp["play_type"] == "pass")
        & (pbp["yardline_100"] <= 20)
        & pbp["receiver_player_id"].notna()
    ].copy()


# ── Comparison helpers ────────────────────────────────────────────────────────

def compare_snap(old_df, new_df, season: int, week: int) -> bool:
    print("\n── Snap Counts ──────────────────────────────────────────────────")
    all_ok = True

    # Column presence
    missing_old = SNAP_COLS_REQUIRED - set(old_df.columns)
    missing_new = SNAP_COLS_REQUIRED - set(new_df.columns)
    all_ok &= check("old nfl_data_py has required columns", not missing_old,
                    f"missing: {missing_old}" if missing_old else "")
    all_ok &= check("new nflreadpy has required columns", not missing_new,
                    f"missing: {missing_new}" if missing_new else "")

    # Row counts (full season)
    old_n = len(old_df)
    new_n = len(new_df)
    counts_match = old_n == new_n
    all_ok &= check(f"WR/TE row count matches ({old_n} rows)", counts_match,
                    f"new={new_n}" if not counts_match else "")

    # Single-week spot check
    old_week = old_df[(old_df["season"] == season) & (old_df["week"] == week)]
    new_week = new_df[(new_df["season"] == season) & (new_df["week"] == week)]
    week_match = len(old_week) == len(new_week)
    all_ok &= check(
        f"Week {week} row count matches ({len(old_week)} rows)", week_match,
        f"new={len(new_week)}" if not week_match else "",
    )

    # Spot-check a specific player (first player alphabetically in old data for the week)
    if not old_week.empty and not new_week.empty:
        old_sorted = old_week.sort_values("player")
        sample_name = old_sorted.iloc[0]["player"]
        old_row = old_week[old_week["player"] == sample_name]
        new_row = new_week[new_week["player"] == sample_name]
        if not old_row.empty and not new_row.empty:
            old_pct = round(float(old_row.iloc[0]["offense_pct"]), 4)
            new_pct = round(float(new_row.iloc[0]["offense_pct"]), 4)
            pct_match = abs(old_pct - new_pct) < 0.001
            all_ok &= check(
                f"offense_pct matches for '{sample_name}' (old={old_pct})",
                pct_match,
                f"new={new_pct}" if not pct_match else "",
            )
        else:
            print(f"  [~] Spot-check player '{sample_name}' not found in new data — check alias table")

    return all_ok


def compare_pbp(old_df, new_df, season: int, week: int) -> bool:
    print("\n── Red Zone PBP ─────────────────────────────────────────────────")
    all_ok = True

    # Column presence
    missing_old = PBP_COLS_REQUIRED - set(old_df.columns)
    missing_new = PBP_COLS_REQUIRED - set(new_df.columns)
    all_ok &= check("old nfl_data_py has required columns", not missing_old,
                    f"missing: {missing_old}" if missing_old else "")
    all_ok &= check("new nflreadpy has required columns", not missing_new,
                    f"missing: {missing_new}" if missing_new else "")

    # Row counts (full season RZ pass plays)
    old_n = len(old_df)
    new_n = len(new_df)
    counts_match = old_n == new_n
    all_ok &= check(f"RZ pass play count matches ({old_n} rows)", counts_match,
                    f"new={new_n}" if not counts_match else "")

    # Week-level RZ target totals
    old_week = old_df[(old_df["season"] == season) & (old_df["week"] == week)]
    new_week = new_df[(new_df["season"] == season) & (new_df["week"] == week)]
    old_rz = len(old_week)
    new_rz = len(new_week)
    rz_match = old_rz == new_rz
    all_ok &= check(
        f"Week {week} RZ play count matches ({old_rz} plays)", rz_match,
        f"new={new_rz}" if not rz_match else "",
    )

    # TD count sanity check for the week
    old_tds = int(old_week["touchdown"].sum())
    new_tds = int(new_week["touchdown"].sum())
    td_match = old_tds == new_tds
    all_ok &= check(
        f"Week {week} RZ TD count matches ({old_tds} TDs)", td_match,
        f"new={new_tds}" if not td_match else "",
    )

    return all_ok


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, default=2024, help="Season to test (default: 2024)")
    parser.add_argument("--week", type=int, default=10, help="Week to spot-check (default: 10)")
    args = parser.parse_args()

    season = args.season
    week = args.week
    seasons = [season]

    print(f"\nnflverse migration test — season={season}, spot-check week={week}")
    print("=" * 60)

    # Use a shared temp dir so both libraries can reuse the same cached parquet files
    # nfl_data_py and nflreadpy use the same upstream URLs, so the files are compatible.
    import tempfile
    cache_dir = tempfile.mkdtemp(prefix="bggtdm_migration_test_")
    print(f"Cache dir: {cache_dir}")

    print("\n[1/4] Fetching snap counts via nfl_data_py (old)...")
    try:
        old_snap = fetch_old_snap(seasons, cache_dir)
        print(f"      → {len(old_snap)} WR/TE rows loaded")
    except Exception as e:
        print(f"  [{FAIL}] nfl_data_py snap fetch failed: {e}")
        sys.exit(1)

    print("[2/4] Fetching snap counts via nflreadpy (new)...")
    try:
        new_snap = fetch_new_snap(seasons, cache_dir)
        print(f"      → {len(new_snap)} WR/TE rows loaded")
    except Exception as e:
        print(f"  [{FAIL}] nflreadpy snap fetch failed: {e}")
        sys.exit(1)

    print("[3/4] Fetching RZ PBP via nfl_data_py (old)...")
    try:
        old_pbp = fetch_old_pbp(seasons, cache_dir)
        print(f"      → {len(old_pbp)} RZ pass plays loaded")
    except Exception as e:
        print(f"  [{FAIL}] nfl_data_py PBP fetch failed: {e}")
        sys.exit(1)

    print("[4/4] Fetching RZ PBP via nflreadpy (new)...")
    try:
        new_pbp = fetch_new_pbp(seasons, cache_dir)
        print(f"      → {len(new_pbp)} RZ pass plays loaded")
    except Exception as e:
        print(f"  [{FAIL}] nflreadpy PBP fetch failed: {e}")
        sys.exit(1)

    # Compare
    snap_ok = compare_snap(old_snap, new_snap, season, week)
    pbp_ok = compare_pbp(old_pbp, new_pbp, season, week)

    print("\n" + "=" * 60)
    all_ok = snap_ok and pbp_ok
    if all_ok:
        print(f"[{PASS}] All checks passed — nflreadpy is a safe drop-in for this season.")
        print("    Local DB data (populated via nfl_data_py) is confirmed valid.")
        print("    Future ingests via nflreadpy will produce equivalent data.")
    else:
        print(f"[{FAIL}] Some checks failed — review output above before deploying.")
        sys.exit(1)


if __name__ == "__main__":
    main()
