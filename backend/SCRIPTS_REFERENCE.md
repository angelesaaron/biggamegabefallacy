# Backend Scripts Reference

Quick reference for all backend maintenance and data sync scripts.

## One-Time Setup Scripts

### 1. `sync_schedule.py`
**Purpose:** Initial sync of NFL schedule to database

**Usage:**
```bash
python sync_schedule.py
```

**What it does:**
- Fetches schedule for 2024 and 2025 seasons
- Stores all games with gameID, week, teams, dates
- ~36 API calls (18 weeks × 2 years)

**When to run:**
- Once at initial setup
- Or when starting a new season

---

### 2. `sync_game_logs.py`
**Purpose:** Initial sync of all player game logs

**Usage:**
```bash
python sync_game_logs.py
```

**What it does:**
- Fetches game logs for all 538 WR/TE players
- Enriches with week numbers from schedule
- Stores in `game_logs` table
- ~538 API calls (1 per player)

**When to run:**
- Once at initial setup
- Takes ~10 minutes

**Note:** Do not run more than once per day (uses 538 API calls)

---

### 3. `sync_odds.py`
**Purpose:** Manual odds sync for specific week

**Usage:**
```bash
# Sync current week
python sync_odds.py

# Sync specific week
python sync_odds.py --week 4 --year 2025
```

**What it does:**
- Fetches DraftKings + FanDuel odds using gameID
- Stores anytime TD odds for all players
- ~16 API calls (1 per game)

**When to run:**
- Initial setup for current week
- Manual refresh if needed
- Better to use `update_weekly.py` for automation

---

### 4. `generate_predictions.py`
**Purpose:** Batch generate predictions for all players

**Usage:**
```bash
# Generate for current week (auto-detected)
python generate_predictions.py

# Generate for specific week
python generate_predictions.py --week 18 --year 2025
```

**What it does:**
- Generates TD predictions for ~538 WR/TE players
- Uses historical game logs (weeks 1 through N-1)
- Uses sportsbook odds for week N
- Calculates expected value and edge
- Stores in `predictions` table
- **0 API calls** (reads from database only!)

**When to run:**
- After initial data sync
- After weekly update
- Anytime you want fresh predictions

---

## Weekly Maintenance Scripts

### 5. `update_weekly.py` ⭐ MAIN WEEKLY SCRIPT
**Purpose:** All-in-one weekly maintenance

**Usage:**
```bash
# Run every Tuesday after Monday Night Football
python update_weekly.py
```

**What it does:**
1. Updates schedule for current + next week (2 API calls)
2. Fetches game logs for completed week (538 API calls)
3. Syncs odds for upcoming week (~16 API calls)
4. At Week 18: Also syncs playoff schedule

**Total:** ~556 API calls

**When to run:**
- **Every Tuesday morning** after MNF finishes
- Week detection is automatic!
- No .env updates needed

**After running:**
```bash
# Then generate predictions
python generate_predictions.py
```

---

## Optional/Utility Scripts

### 6. `backfill_historical_odds.py` 🆕
**Purpose:** Fetch historical odds for model validation

**Usage:**
```bash
# Backfill specific week
python backfill_historical_odds.py --week 10 --year 2025

# Backfill all weeks so far this season
python backfill_historical_odds.py --year 2025

# Backfill week range
python backfill_historical_odds.py --start-week 1 --end-week 16 --year 2025
```

**What it does:**
- Fetches historical sportsbook odds using gameID
- Stores DK + FD odds for completed games
- Enables model performance analysis
- ~16 API calls per week

**When to run:**
- **After initial setup** to get historical data
- Spread over multiple days to stay within API limits
- Example: 16 weeks × 16 calls = 256 calls total

**Benefits:**
- Test model accuracy against actual betting lines
- Analyze edge detection performance
- Build comprehensive odds database

**Recommended approach:**
```bash
# Day 1: Backfill weeks 1-6 (~96 calls)
python backfill_historical_odds.py --start-week 1 --end-week 6 --year 2025

# Day 2: Backfill weeks 7-12 (~96 calls)
python backfill_historical_odds.py --start-week 7 --end-week 12 --year 2025

# Day 3: Backfill weeks 13-16 (~64 calls)
python backfill_historical_odds.py --start-week 13 --end-week 16 --year 2025
```

---

## Typical Workflow

### Initial Setup (First Time)
```bash
cd backend
source venv/bin/activate

# 1. Sync schedule (~2 min, 36 calls)
python sync_schedule.py

# 2. Sync game logs (~10 min, 538 calls - do this on Day 1)
python sync_game_logs.py

# 3. Sync current week odds (~2 min, 16 calls)
python sync_odds.py

# 4. Generate initial predictions (~5 min, 0 calls)
python generate_predictions.py

# 5. (Optional) Backfill historical odds over next few days
# Day 2: Weeks 1-6
python backfill_historical_odds.py --start-week 1 --end-week 6 --year 2025

# Day 3: Weeks 7-12
python backfill_historical_odds.py --start-week 7 --end-week 12 --year 2025

# Day 4: Weeks 13-current
python backfill_historical_odds.py --start-week 13 --end-week 16 --year 2025
```

### Weekly Maintenance (Every Tuesday)
```bash
cd backend
source venv/bin/activate

# 9:00 AM - Update all data (~5 min, 556 calls)
python update_weekly.py

# 9:10 AM - Generate predictions (~5 min, 0 calls)
python generate_predictions.py

# 9:15 AM - Start API server
uvicorn app.main:app --reload

# Done! Predictions ready for the week
```

### Mid-Week Manual Refresh (Optional)
```bash
# If you want to refresh odds mid-week
# Option 1: Via API endpoint (recommended)
curl -X POST "http://localhost:8000/api/odds/refresh"

# Option 2: Via script
python sync_odds.py

# Then regenerate predictions
python generate_predictions.py
```

---

## API Call Budget Summary

| Operation | Frequency | Calls | Notes |
|-----------|-----------|-------|-------|
| **Initial Setup** |
| sync_schedule.py | Once | 36 | Two seasons |
| sync_game_logs.py | Once | 538 | All WR/TE players |
| sync_odds.py | Once | 16 | Current week |
| **Weekly Maintenance** |
| update_weekly.py | 18×/season | 556 | Tuesday mornings |
| **Optional** |
| backfill_historical_odds.py | Once | ~256 | Spread over 3-4 days |

**Annual Total (without backfill):** ~10,600 calls
**With backfill:** ~10,856 calls
**Available:** 365,000 calls/year (1,000/day)
**Usage:** ~3% of annual limit ✅

---

## Troubleshooting

### Script fails with "Database connection error"
```bash
# Check PostgreSQL is running
pg_isready

# Check .env file has correct DATABASE_URL
cat .env | grep DATABASE_URL
```

### "No games found for week X"
- Schedule might not be synced yet
- Run `python sync_schedule.py` first

### "No odds available for game"
- Odds might not be posted yet (too early in week)
- Historical odds might not exist (very old games)
- Try again closer to game day

### API rate limit hit (1,000/day)
- Check which scripts were run today
- Spread backfill over multiple days
- sync_game_logs.py alone uses 538 calls!

### Week detection returns wrong week
```bash
# Test week detection
python -c "from app.utils.nfl_calendar import get_current_nfl_week; print(get_current_nfl_week())"

# Check schedule table has games
# Most recent game should determine current week
```

---

## Quick Commands

```bash
# Check current week
python -c "from app.utils.nfl_calendar import get_current_nfl_week; print(get_current_nfl_week())"

# Count predictions in database
python -c "
from app.database import SessionLocal
from app.models.prediction import Prediction
from sqlalchemy import select, func
db = SessionLocal()
count = db.execute(select(func.count(Prediction.id))).scalar()
print(f'Total predictions: {count}')
db.close()
"

# Count odds records
python -c "
from app.database import SessionLocal
from app.models.odds import SportsbookOdds
from sqlalchemy import select, func
db = SessionLocal()
count = db.execute(select(func.count(SportsbookOdds.id))).scalar()
print(f'Total odds records: {count}')
db.close()
"

# Start API server
uvicorn app.main:app --reload

# Run tests (if tests exist)
pytest
```

---

## Script Dependencies

All scripts require:
- PostgreSQL running
- `.env` file configured with `DATABASE_URL`
- Virtual environment activated (`source venv/bin/activate`)
- Dependencies installed (`pip install -r requirements.txt`)

## Best Practices

1. **Never run sync_game_logs.py more than once per day** (uses 538 API calls)
2. **Use update_weekly.py for regular maintenance** instead of individual scripts
3. **Backfill historical odds over multiple days** to avoid hitting rate limit
4. **Generate predictions after any data update** (it's free - 0 API calls!)
5. **Monitor API usage** - you have 1,000 calls/day, use them wisely
