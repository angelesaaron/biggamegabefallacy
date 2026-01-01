# Debug Tools

This folder contains diagnostic and manual maintenance scripts for the BGGTDM backend.

## Scripts

### Player Data Diagnostics

**`check_player_simple.py`** - Check game logs and predictions for a specific player
```bash
DATABASE_URL="..." python debug_tools/check_player_simple.py "Player Name"
```
Shows week-by-week breakdown of game logs vs predictions, identifies missing predictions.

**`check_player_data.py`** - Full player data check (requires app config)
```bash
python debug_tools/check_player_data.py "Player Name"
```

**`debug_backfill_predictions.py`** - Debug why a specific player/week prediction isn't generating
```bash
DATABASE_URL="..." python debug_tools/debug_backfill_predictions.py PLAYER_ID WEEK [YEAR]
```
Example: `python debug_tools/debug_backfill_predictions.py 4426515 15 2025`

### Batch & Data Checks

**`check_batch_runs.py`** - View recent batch run history
```bash
python debug_tools/check_batch_runs.py [--limit 20]
```

**`check_data.py`** - Check database for data integrity issues

### Manual Maintenance

**`manual_backfill_predictions.py`** - Manually backfill missing predictions
```bash
# Dry run to see what's missing
DATABASE_URL="..." python debug_tools/manual_backfill_predictions.py --all --dry-run

# Backfill all missing predictions
DATABASE_URL="..." python debug_tools/manual_backfill_predictions.py --all

# Backfill specific week range
DATABASE_URL="..." python debug_tools/manual_backfill_predictions.py --start-week 6 --end-week 16
```

## Usage Notes

- Most scripts require `DATABASE_URL` environment variable for production database access
- Use `--dry-run` flags when available to preview changes before making them
- Scripts in this folder are safe to run and won't modify data unless explicitly designed to do so
