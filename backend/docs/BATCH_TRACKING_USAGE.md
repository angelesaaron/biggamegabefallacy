# Batch Tracking Usage Guide

## Overview

The batch tracking system provides observability into all batch processes through two tables:
- `batch_runs` - Audit log of batch executions
- `data_readiness` - Data availability status per week

## Installation

1. Apply the migration:
```bash
python apply_batch_tracking_migration.py
```

## Usage

### Using BatchTracker Context Manager

The `BatchTracker` context manager automatically tracks batch execution:

```python
from app.services.batch_tracking import BatchTracker
from app.utils.nfl_calendar import get_current_nfl_week

async def my_batch_process():
    season_year, week, season_type = get_current_nfl_week()

    async with AsyncSessionLocal() as db:
        # Start tracking
        async with BatchTracker(
            db=db,
            batch_type='weekly_update',
            season_year=season_year,
            week=week,
            batch_mode='full',
            season_type=season_type,
            triggered_by='github_actions'  # or 'manual', 'api'
        ) as tracker:
            # Do work
            games = await fetch_schedule()
            tracker.increment_metric('games_processed', len(games))

            # Add warnings if needed
            if skipped_players:
                tracker.add_warning(
                    'game_logs',
                    f'Skipped {len(skipped_players)} players not in database'
                )

            # Metrics are automatically saved on exit
```

### Available Metrics

Increment these metrics using `tracker.increment_metric()`:

- `api_calls_made` - API calls to external services
- `games_processed` - Games processed
- `game_logs_added` - New game logs inserted
- `predictions_generated` - New predictions created
- `predictions_skipped` - Predictions skipped (immutability)
- `odds_synced` - Odds records synced
- `errors_encountered` - Errors during execution

### Batch Types

- `weekly_update` - Weekly data ingestion (schedule + logs + odds)
- `prediction_generation` - ML prediction batch
- `roster_refresh` - Player onboarding

### Batch Modes (for weekly_update)

- `full` - Complete update (schedule + logs + odds)
- `odds_only` - Refresh odds only
- `ingest_only` - Data ingestion only (no odds)
- `schedule_only` - Schedule sync only

### Status Values

- `running` - Currently executing
- `success` - Completed successfully
- `partial` - Completed with warnings
- `failed` - Failed with error

## Querying Batch Runs

### Get Latest Batch Run

```python
from app.models.batch_run import BatchRun
from sqlalchemy import select

async with AsyncSessionLocal() as db:
    result = await db.execute(
        select(BatchRun)
        .order_by(BatchRun.started_at.desc())
        .limit(1)
    )
    latest = result.scalar_one_or_none()
```

### Get Batch History for Week

```python
result = await db.execute(
    select(BatchRun)
    .where(
        BatchRun.season_year == 2025,
        BatchRun.week == 17
    )
    .order_by(BatchRun.started_at.desc())
)
batches = result.scalars().all()
```

## Data Readiness

Data readiness is automatically updated after each successful batch run.

### Check Week Readiness

```python
from app.models.batch_run import DataReadiness

result = await db.execute(
    select(DataReadiness)
    .where(
        DataReadiness.season_year == 2025,
        DataReadiness.week == 17
    )
)
readiness = result.scalar_one_or_none()

if readiness:
    print(f"Schedule complete: {readiness.schedule_complete}")
    print(f"Predictions available: {readiness.predictions_available}")
    print(f"Games: {readiness.games_count}")
    print(f"Predictions: {readiness.predictions_count}")
```

### Manual Update

```python
from app.services.batch_tracking import update_data_readiness

await update_data_readiness(db, season_year=2025, week=17, season_type='reg')
```

## Example: Instrumenting update_weekly.py

```python
# In update_weekly.py main()

import os
from app.services.batch_tracking import BatchTracker

async def main():
    # ... parse args ...

    triggered_by = 'github_actions' if os.environ.get('CI') else 'manual'

    async with AsyncSessionLocal() as db:
        async with BatchTracker(
            db=db,
            batch_type='weekly_update',
            season_year=current_season,
            week=current_week,
            batch_mode=args.mode,
            season_type=season_type,
            triggered_by=triggered_by
        ) as tracker:
            # Schedule sync
            if args.mode in ['full', 'ingest_only', 'schedule_only']:
                games_added = await update_schedule(...)
                tracker.increment_metric('games_processed', games_added)

            # Game logs
            if args.mode in ['full', 'ingest_only']:
                logs_added, skipped = await update_game_logs_from_box_scores(...)
                tracker.increment_metric('game_logs_added', logs_added)
                tracker.increment_metric('api_calls_made', games_processed)

                if skipped:
                    tracker.add_warning(
                        'game_logs',
                        f'Skipped {skipped} players not in database'
                    )

            # Odds
            if args.mode in ['full', 'odds_only']:
                odds_count = await sync_odds_for_next_week(...)
                tracker.increment_metric('odds_synced', odds_count)
                tracker.increment_metric('api_calls_made', games_count)
```

## API Endpoints (Future)

These endpoints will be added for the System Status page:

- `GET /api/admin/batch-runs/latest` - Latest batch run
- `GET /api/admin/batch-runs/history` - Recent batch history
- `GET /api/admin/data-readiness/current` - Current week readiness
- `GET /api/admin/data-readiness/{week}` - Week-specific readiness

## Benefits

1. **Audit Trail** - Complete history of all batch executions
2. **Debugging** - Warnings and errors are logged with context
3. **Monitoring** - Track API usage, processing time, success rates
4. **Data Quality** - Know exactly what data is available per week
5. **Transparency** - Power the System Status page for users
