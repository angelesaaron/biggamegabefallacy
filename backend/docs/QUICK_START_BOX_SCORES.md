# Quick Start: Box Score Method

## What Changed?

Instead of making 538 API calls (one per player), we now make 16 API calls (one per game) to fetch game logs. **This reduces weekly API calls from ~556 to ~34 (94% reduction).**

## Usage

### Default (Box Score Method - RECOMMENDED)
```bash
python update_weekly.py
```

### Legacy (Per-Player Method)
```bash
USE_BOX_SCORES=false python update_weekly.py
```

## How It Works

### Before (Per-Player)
```
For each of 538 players:
  → API call: get_games_for_player(player_id)
  → Parse game logs
  → Save to database
```

### After (Box Score)
```
For each of 16 games:
  → API call: get_box_score(game_id)
  → Extract ALL player stats from box score
  → Save to database
```

## Quick Test

Test with Week 17 2025 data:

```bash
# Single game test (detailed)
python test_box_score.py
> Enter: 1

# All games test (summary)
python test_box_score.py
> Enter: 2
```

## What Gets Extracted

From each box score, we extract players with receiving stats:

```python
{
    "player_id": "4685",
    "receptions": 11,
    "receiving_yards": 90,
    "receiving_touchdowns": 1,
    "targets": 11,
    "long_reception": 28,
    "yards_per_reception": 8.2
}
```

## Edge Cases Handled

✅ **Players without receiving stats** → Skipped
✅ **Players with 0 catches** → Included (they got targets)
✅ **Players not in database** → Skipped (logged)
✅ **Missing optional fields** → Set to None
✅ **String values from API** → Converted to int/float

## Expected Results

For a typical week:
- **Games processed:** 16/16
- **Game logs extracted:** ~240-260
- **Receiving TDs:** ~30-50
- **Time:** ~30 seconds (vs 5-10 minutes)

## Rollback

If you encounter issues:

```bash
# Use legacy method
export USE_BOX_SCORES=false
python update_weekly.py
```

Or edit `update_weekly.py` line 476 to default to `false`.

## Validation

After running, verify:

```sql
-- Check game log counts for the week
SELECT week, COUNT(*)
FROM game_logs
WHERE season_year = 2025 AND week = 17
GROUP BY week;

-- Check TD counts
SELECT
    SUM(receiving_touchdowns) as total_tds,
    COUNT(DISTINCT player_id) as players_with_tds
FROM game_logs
WHERE season_year = 2025 AND week = 17
AND receiving_touchdowns > 0;
```

## Full Documentation

See [BOX_SCORE_MIGRATION.md](./BOX_SCORE_MIGRATION.md) for complete details.
