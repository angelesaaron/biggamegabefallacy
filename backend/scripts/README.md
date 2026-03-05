# Backend Scripts

All scripts are run from the `backend/` directory with the virtual environment activated.

```bash
cd backend
source venv/bin/activate
```

## Weekly Maintenance

### `update_weekly.py` — Primary weekly script
Runs every Tuesday after Monday Night Football. Updates schedule, fetches game logs, syncs odds, and generates predictions.

```bash
python scripts/update_weekly.py

# Odds-only mode
python scripts/update_weekly.py --mode odds_only --week 17 --year 2025
```

~556 API calls per run. Also triggered automatically by GitHub Actions.

### `generate_predictions.py` — Batch prediction generation
Generates TD predictions for all WR/TE players. Reads from database only (0 API calls).

```bash
python scripts/generate_predictions.py
python scripts/generate_predictions.py --week 18 --year 2025
python scripts/generate_predictions.py --force  # overwrite existing
```

## Data Management

### `refresh_rosters.py` — Sync player rosters
Fetches current WR/TE rosters from Tank01 API.

```bash
python scripts/refresh_rosters.py --dry-run
python scripts/refresh_rosters.py
python scripts/refresh_rosters.py --backfill --max-weeks 20
```

### `backfill_complete.py` — Historical data backfill
Backfills historical odds and game data for model validation.

```bash
python scripts/backfill_complete.py --weeks 5
python scripts/backfill_complete.py --week 10 --year 2025
python scripts/backfill_complete.py --start-week 10 --end-week 15 --year 2025
```

### `generate_historical_predictions.py` — Historical predictions
Generates predictions for past weeks (for model accuracy analysis).

```bash
python scripts/generate_historical_predictions.py --season 2025 --dry-run
python scripts/generate_historical_predictions.py --season 2025
```

## Setup

### `create_tables.py` — Database table creation
Creates all database tables. Run once after PostgreSQL is set up.

```bash
python scripts/create_tables.py
```

## API Call Budget

| Script | Frequency | Calls/Run |
|--------|-----------|-----------|
| `update_weekly.py` | Weekly | ~556 |
| `generate_predictions.py` | Weekly | 0 |
| `refresh_rosters.py` | As needed | ~32 |
| `backfill_complete.py` | One-time | ~16/week |
| `create_tables.py` | One-time | 0 |

Annual total: ~10,600 calls (well within 120,000/year limit).
