# nflreadpy Migration

## Background

`nfl-data-py` has been deprecated in favor of `nflreadpy`. No further maintenance
or updates are planned for `nfl-data-py`. All future nflverse Python development
occurs in `nflreadpy`.

Official notice from the nfl-data-py repo:
> nfl_data_py has been deprecated in favour of nflreadpy. All future development
> will occur in nflreadpy and users are encouraged to switch immediately.

## Migration Status

**COMPLETED** (March 2026). All three call sites have been updated.

## API Differences (nfl_data_py → nflreadpy)

This was **not** a drop-in replacement. Key differences:

| Aspect | nfl_data_py (old) | nflreadpy (new) |
|---|---|---|
| Snap counts | `import_snap_counts(seasons, cache=True, alt_path=dir)` | `load_snap_counts(seasons).to_pandas()` |
| PBP | `import_pbp_data(seasons, cache=True, alt_path=dir)` | `load_pbp(seasons).to_pandas()` |
| Players | `import_players()` | `load_players().to_pandas()` |
| DataFrame type | pandas | Polars (convert with `.to_pandas()`) |
| Cache config | Per-call `cache=True, alt_path=dir` params | `update_config(cache_mode="filesystem", cache_dir=dir)` before loading |
| Cache env vars | None | `NFLREADPY_CACHE`, `NFLREADPY_CACHE_DIR` |

## Where nflreadpy Is Used

| File | Functions | Purpose |
|---|---|---|
| `app/utils/nflverse_adapter.py` | `load_snap_counts()`, `load_pbp()` | Core weekly ingest — snap % and red zone PBP |
| `scripts/seed_draft_rounds.py` | `load_players()` | One-time draft round seeding |

## Pinning the Version

`requirements.txt` currently uses `nflreadpy>=0.1.0`. After installing, pin to
the exact version:

```bash
pip install nflreadpy
pip show nflreadpy   # note the Version field
# then update requirements.txt: nflreadpy==<version>
```

## Cache Configuration

nflreadpy cache is configured via `update_config()` (called in `_configure_nflreadpy_cache()`
inside `nflverse_adapter.py`) or via environment variables:

```bash
NFLREADPY_CACHE=filesystem
NFLREADPY_CACHE_DIR=/path/to/cache
```

The cached parquet files from the old `nfl-data-py` cache are **not reusable** —
nflreadpy manages its own cache directory. Expect a one-time re-download of
~300 MB PBP parquet files on the first post-migration ingest.

## Validation

After deploying, run a test ingest for one historical week and confirm:
1. Snap counts load without errors (check `snap_unmatched` list is similar to before)
2. RZ PBP loads and row counts match historical baseline
3. `DataQualityEvent` counts are unchanged
