# Data Sync Guide

## Overview

The system now uses **database-backed** data instead of making API calls on every request. This is much more efficient and faster.

## One-Time Setup (Run These Once)

### 1. Sync Schedule (~36 API calls, ~2 minutes)
Fetches the full 2024 and 2025 season schedules and stores them in the database.

```bash
cd backend
source venv/bin/activate
python sync_schedule.py
```

This creates the `gameID → week number` mapping for all games.

### 2. Sync Game Logs (~538 API calls, ~10 minutes)
Fetches all historical game logs for all 538 WR/TE players and stores them in the database.

```bash
python sync_game_logs.py
```

This populates the `game_logs` table with all player performance data.

## After Sync

Once synced, predictions will:
- ✅ Read game logs from database (no API calls)
- ✅ Have week numbers already attached
- ✅ Be much faster
- ✅ Work offline

## Weekly Maintenance

Run this every **Monday morning** after Sunday/Monday night games finish:

```bash
cd backend
source venv/bin/activate

# Update schedule and fetch new game logs (~540 API calls)
python update_weekly.py
```

This script will:
- ✅ Update schedule with current and next week's games
- ✅ Fetch only NEW game logs (checks last 10 games per player)
- ✅ Much faster than re-syncing everything
- ✅ Keeps data fresh for predictions

Optionally update rosters if new players are added mid-season:
```bash
python sync_rosters.py
```

## Architecture

### Old Way (Broken)
```
Request → API call per player → Fetch schedule 36 times → Enrich → Predict
```

### New Way (Fast & Efficient)
```
[One-time setup]
Sync schedule → DB (36 API calls once)
Sync game logs → DB (538 API calls once)

[Every request]
Request → Read from DB → Predict (0 API calls!)
```

## Database Tables

- `players` - 538 WR/TE players
- `schedule` - All games with week numbers (~544 games)
- `game_logs` - Historical player performance (~7,000+ game logs)
- `predictions` - Generated predictions (populated by batch job)

## Next Steps

1. Run sync scripts above
2. Generate predictions for all players
3. Serve predictions from DB (instant responses)
