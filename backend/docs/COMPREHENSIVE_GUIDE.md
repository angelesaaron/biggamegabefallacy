# BGGTDM - Comprehensive Developer Guide

## Table of Contents
1. [Local Development Setup](#local-development-setup)
2. [Batch Processing System](#batch-processing-system)
3. [Roster Refresh](#roster-refresh)
4. [Season & Week Detection](#season--week-detection)
5. [Batch Tracking & Observability](#batch-tracking--observability)
6. [Testing Locally](#testing-locally)

---

## Local Development Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 14+

### 1. Database Setup

#### Start PostgreSQL (macOS)
```bash
# Using Homebrew
brew services start postgresql@14

# Or using Docker
docker run --name bggtdm-postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=bggtdm \
  -p 5432:5432 \
  -d postgres:14
```

#### Create Database
```bash
# Connect to PostgreSQL
psql postgres

# Create database
CREATE DATABASE bggtdm;

# Connect to database
\c bggtdm

# Exit
\q
```

#### Apply Migrations
```bash
cd backend

# Create all tables
python create_tables.py

# Apply batch tracking migration
python apply_batch_tracking_migration.py
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/bggtdm"
export TANK01_API_KEY="your_rapidapi_key_here"
export NFL_SEASON_YEAR=2025

# Start backend server
uvicorn app.main:app --reload --port 8000
```

Backend will be available at: http://localhost:8000

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Set environment variable
export NEXT_PUBLIC_API_URL="http://localhost:8000"

# Start development server
npm run dev
```

Frontend will be available at: http://localhost:3000

---

## Batch Processing System

### Overview
The batch system has **4 modes** for flexible data management:

| Mode | Schedule | Logs | Odds | Use Case |
|------|----------|------|------|----------|
| `full` | ✅ | ✅ | ✅ | Weekly automated update |
| `odds_only` | ❌ | ❌ | ✅ | Mid-week odds refresh |
| `ingest_only` | ✅ | ✅ | ❌ | Data corrections |
| `schedule_only` | ✅ | ❌ | ❌ | Schedule fixes |

### Weekly Update Script

**Location**: `backend/update_weekly.py`

**What it does**:
1. **Schedule Sync**: Fetches current + next week games
2. **Game Logs**: Fetches box scores (optimized: ~16 API calls vs ~538)
3. **Odds Sync**: Fetches sportsbook odds (DraftKings + FanDuel)

**Usage**:
```bash
# Full weekly update (default)
python update_weekly.py

# With explicit mode
python update_weekly.py --mode full

# Mid-week odds refresh (predictions unchanged)
python update_weekly.py --mode odds_only --week 17 --year 2025

# Data correction (re-fetch box scores)
python update_weekly.py --mode ingest_only --week 16 --year 2025

# Schedule fix only
python update_weekly.py --mode schedule_only
```

**Key Features**:
- ✅ **Idempotent** - Safe to run multiple times
- ✅ **Playoff-aware** - Auto-detects season type
- ✅ **Box score optimization** - 97% fewer API calls
- ✅ **Auto week detection** - Or manual override

**Example Output**:
```
Weekly Data Update
Season: 2025
Week: 17 (auto-detected)
Season Type: REG
Batch Mode: FULL

This will:
  1. Update schedule for current/next week
  2. Fetch box scores for Week 16 (completed)
  3. Fetch odds for Week 17 (upcoming)
  4. Then run: python generate_predictions.py (separate step)

📅 Updating Schedule...
   Week 17: ✅ Updated
   Week 18: ✅ Updated

🏈 Updating Game Logs (Box Score Method)...
   [16/16] ✅ Complete: 16 games processed, 234 new game logs added

📊 Syncing Odds for Week 17...
   ✅ Synced 1076 odds records for Week 17

✅ Batch Complete (FULL)
```

### Prediction Generation

**Location**: `backend/generate_predictions.py`

**What it does**:
1. Checks for existing predictions (immutability)
2. Generates predictions ONLY for NEW players
3. Uses game logs from database (0 API calls)
4. Stores predictions for fast retrieval

**Usage**:
```bash
# Generate predictions (auto-detects week)
python generate_predictions.py

# Specific week
python generate_predictions.py --week 17 --year 2025

# DANGEROUS: Force regeneration (requires confirmation)
python generate_predictions.py --force
```

**Immutability Protection**:
```bash
$ python generate_predictions.py

⚠️  WARNING: 538 predictions already exist for Week 17
   Predictions are IMMUTABLE. Will only generate for new players.
   To regenerate (DANGEROUS), use --force flag

Found 538 active WR/TE players
Skipping 538 players with existing predictions

✅ All players already have predictions. Nothing to do.
```

**With --force flag**:
```bash
$ python generate_predictions.py --force

⚠️  DANGER: Deleting 538 existing predictions
   This violates prediction immutability!

Are you ABSOLUTELY SURE? Type 'DELETE' to confirm: DELETE

Deleted 538 existing predictions
Generating predictions for 538 new players...
```

**Playoff Protection**:
```bash
$ python generate_predictions.py
# Auto-detects: 2025 Week 1 (POST)

⚠️  ERROR: Cannot generate predictions for playoff games

The model is trained on regular season data only.
Playoff predictions are not supported.
```

---

## Roster Refresh

### New Player Onboarding

**Location**: `backend/refresh_rosters.py`

**What it does**:
1. Fetches all rosters from Tank01 (32 teams)
2. Compares against existing players
3. Adds NEW players only
4. Optionally backfills historical game logs

**Usage**:
```bash
# Preview new players (dry run)
python refresh_rosters.py --dry-run

# Add new players (no historical backfill)
python refresh_rosters.py

# Add new players WITH historical backfill
python refresh_rosters.py --backfill

# Limit backfill to 20 weeks
python refresh_rosters.py --backfill --max-weeks 20

# Custom positions
python refresh_rosters.py --positions WR TE RB
```

**Example Output (Dry Run)**:
```
Roster Refresh - Player Onboarding
Mode: DRY RUN (preview only)
Positions: WR, TE
Backfill: NO

Fetching rosters from Tank01 (32 teams)...
Found 892 WR/TE players from API

Database has 538 existing players

🆕 Detected 3 NEW players:
   1. Marvin Harrison Jr. (WR, ARI)
   2. Brock Bowers (TE, LV)
   3. Rome Odunze (WR, CHI)

Estimated API calls: 32

DRY RUN - No changes will be made

To apply changes, run without --dry-run:
  python refresh_rosters.py
  python refresh_rosters.py --backfill
```

**With Backfill**:
```
Roster Refresh - Player Onboarding
Mode: LIVE
Positions: WR, TE
Backfill: YES (up to 52 weeks)

Adding new players to database...
✅ Added 3 new players

Starting historical backfill for 3 players...
[1/3] Backfilled 12 logs...
[2/3] Backfilled 24 logs...
[3/3] Backfilled 36 logs...

✅ Backfilled 36 historical game logs

Players scanned: 892
Players added: 3
Game logs backfilled: 36
Duration: 8s

Next steps:
  1. Run weekly batch to generate predictions for new players:
     python generate_predictions.py
```

**Idempotency**:
- ✅ Safe to run multiple times
- ✅ Skips existing players
- ✅ Duplicate game logs prevented by unique constraint

**When to Run**:
- Beginning of season (draft rookies)
- Mid-season (injuries, signings)
- Before playoffs (roster changes)
- When weekly batch shows "skipped players" warnings

---

## Season & Week Detection

### NFL Calendar System

**Location**: `backend/app/utils/nfl_calendar.py`

**Function**: `get_current_nfl_week() -> (year, week, season_type)`

**Logic**:
1. Query schedule for games in next 4 days → use that week
2. Else: find most recent completed game + 1 week
3. Handle season transitions correctly

**Season Transitions**:

```python
# Regular season Week 17 → Week 18
get_current_nfl_week()  # → (2025, 18, 'reg')

# Week 18 complete → Check for playoffs
get_current_nfl_week()  # → (2025, 1, 'post')  # Wildcard

# Playoff progression
get_current_nfl_week()  # → (2025, 1, 'post')  # Wildcard
get_current_nfl_week()  # → (2025, 2, 'post')  # Divisional
get_current_nfl_week()  # → (2025, 3, 'post')  # Conference
get_current_nfl_week()  # → (2025, 4, 'post')  # Super Bowl

# After Super Bowl → Next season
get_current_nfl_week()  # → (2026, 1, 'reg')
```

**Playoff Handling**:
```python
# ❌ OLD (BROKEN):
if last_game.week == 18:
    return last_game.season_year + 1, 1  # Wrong!

# ✅ NEW (CORRECT):
if last_game.season_type == 'reg' and last_game.week == 18:
    # Check if playoff schedule exists
    playoff_check = db.execute(...)
    if first_playoff:
        return last_game.season_year, first_playoff.week, 'post'
    else:
        return last_game.season_year + 1, 1, 'reg'
```

**Usage in Code**:
```python
from app.utils.nfl_calendar import get_current_nfl_week

# Get current week
year, week, season_type = get_current_nfl_week()

# Check if playoffs
if season_type == 'post':
    print("Playoffs - predictions not supported")
    skip_predictions = True

# All callers updated to handle 3-tuple return
# - update_weekly.py
# - generate_predictions.py
# - app/api/predictions.py
# - app/api/odds.py
# - app/api/admin.py
```

**Manual Override**:
```bash
# Override week detection
python update_weekly.py --week 17 --year 2025 --season-type reg
```

---

## Batch Tracking & Observability

### Database Tables

#### `batch_runs` - Audit Log
Tracks all batch process executions.

**Schema**:
```sql
CREATE TABLE batch_runs (
    id SERIAL PRIMARY KEY,
    batch_type VARCHAR(50),           -- 'weekly_update', 'prediction_generation'
    batch_mode VARCHAR(50),            -- 'full', 'odds_only', etc.
    season_year INT,
    week INT,
    season_type VARCHAR(10),           -- 'reg', 'post'
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds INT,
    status VARCHAR(20),                -- 'running', 'success', 'partial', 'failed'
    api_calls_made INT,
    games_processed INT,
    game_logs_added INT,
    predictions_generated INT,
    predictions_skipped INT,
    odds_synced INT,
    errors_encountered INT,
    warnings JSONB,
    error_message TEXT,
    triggered_by VARCHAR(100)          -- 'github_actions', 'manual'
);
```

#### `data_readiness` - Week Status
Tracks data availability per week.

**Schema**:
```sql
CREATE TABLE data_readiness (
    id SERIAL PRIMARY KEY,
    season_year INT,
    week INT,
    season_type VARCHAR(10),
    schedule_complete BOOLEAN,
    game_logs_available BOOLEAN,
    predictions_available BOOLEAN,
    draftkings_odds_available BOOLEAN,
    fanduel_odds_available BOOLEAN,
    games_count INT,
    game_logs_count INT,
    predictions_count INT,
    draftkings_odds_count INT,
    fanduel_odds_count INT,
    last_updated TIMESTAMP,
    UNIQUE(season_year, week, season_type)
);
```

### BatchTracker Service

**Location**: `backend/app/services/batch_tracking.py`

**Usage**:
```python
from app.services.batch_tracking import BatchTracker

async def my_batch():
    async with AsyncSessionLocal() as db:
        async with BatchTracker(
            db=db,
            batch_type='weekly_update',
            season_year=2025,
            week=17,
            batch_mode='full',
            season_type='reg',
            triggered_by='manual'
        ) as tracker:
            # Do work
            games = await fetch_schedule()
            tracker.increment_metric('games_processed', len(games))

            # Add warnings
            if skipped > 0:
                tracker.add_warning('game_logs', f'Skipped {skipped} players')

            # Automatic tracking on exit:
            # - Calculates duration
            # - Sets status (success/partial/failed)
            # - Updates data_readiness table
```

**Available Metrics**:
- `api_calls_made`
- `games_processed`
- `game_logs_added`
- `predictions_generated`
- `predictions_skipped`
- `odds_synced`
- `errors_encountered`

**Status Logic**:
- `running` - Currently executing
- `success` - Completed with no warnings/errors
- `partial` - Completed with warnings
- `failed` - Exception occurred

### API Endpoints

**Get Latest Batch Run**:
```bash
curl http://localhost:8000/api/admin/batch-runs/latest
```

**Get Batch History**:
```bash
curl http://localhost:8000/api/admin/batch-runs/history?limit=10
```

**Get Current Week Data Readiness**:
```bash
curl http://localhost:8000/api/admin/data-readiness/current
```

**Get System Health Summary**:
```bash
curl http://localhost:8000/api/admin/health/summary
```

**Response Example**:
```json
{
  "current_week": {"year": 2025, "week": 17, "season_type": "reg"},
  "health_score": "healthy",
  "latest_batch": {
    "type": "weekly_update",
    "status": "success",
    "started_at": "2025-01-07T12:00:00Z",
    "duration_seconds": 142
  },
  "data_readiness": {
    "schedule": true,
    "predictions": true,
    "odds": true,
    "games_count": 16,
    "predictions_count": 538
  }
}
```

### System Status Page

**URL**: http://localhost:3000/system-status

**Features**:
- Current week data readiness
- Latest batch run status
- Recent batch history
- Metrics (API calls, processing counts)
- Warnings and errors
- Auto-refresh every 30 seconds

---

## Testing Locally

### Full Development Workflow

#### 1. Initial Setup
```bash
# Terminal 1: Start database
brew services start postgresql@14

# Create database and tables
psql postgres -c "CREATE DATABASE bggtdm;"
cd backend
python create_tables.py
python apply_batch_tracking_migration.py

# Terminal 2: Start backend
cd backend
source venv/bin/activate
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/bggtdm"
export TANK01_API_KEY="your_key_here"
uvicorn app.main:app --reload --port 8000

# Terminal 3: Start frontend
cd frontend
npm run dev
```

#### 2. Populate Initial Data

**Option A: Use Production Backup** (if available)
```bash
# Restore from backup
psql bggtdm < bggtdm_backup.sql
```

**Option B: Sync from Scratch**
```bash
cd backend

# 1. Sync rosters (32 API calls)
python sync_rosters.py

# 2. Sync schedule for current season
python update_weekly.py --mode schedule_only

# 3. Backfill historical game logs (expensive!)
# Only do this for recent weeks
python update_weekly.py --mode ingest_only --week 16 --year 2025
python update_weekly.py --mode ingest_only --week 15 --year 2025
# ... etc

# 4. Sync odds for current week
python update_weekly.py --mode odds_only --week 17 --year 2025

# 5. Generate predictions
python generate_predictions.py --week 17 --year 2025
```

#### 3. Test Batch Modes

**Test Full Update**:
```bash
python update_weekly.py --mode full
python generate_predictions.py
```

**Test Odds Refresh**:
```bash
# Change odds mid-week
python update_weekly.py --mode odds_only --week 17 --year 2025

# Verify predictions unchanged
python -c "
from app.database import AsyncSessionLocal
from app.models.prediction import Prediction
from sqlalchemy import select
import asyncio

async def check():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Prediction.created_at)
            .where(Prediction.season_year == 2025, Prediction.week == 17)
            .limit(1)
        )
        pred = result.scalar_one()
        print(f'Prediction created at: {pred}')

asyncio.run(check())
"
```

**Test Roster Refresh**:
```bash
# Dry run
python refresh_rosters.py --dry-run

# Add new player manually to test
psql bggtdm -c "DELETE FROM players WHERE full_name = 'Test Player';"

# Run roster refresh
python refresh_rosters.py

# Generate predictions for new player
python generate_predictions.py
```

**Test Playoff Transition**:
```bash
# Manually set schedule to playoff
psql bggtdm -c "
UPDATE schedule
SET season_type = 'post', week = 1
WHERE season_year = 2025 AND week = 18;
"

# Test batch behavior
python update_weekly.py
# Should skip game logs with warning

python generate_predictions.py
# Should exit with error
```

#### 4. Test Frontend

**Open Pages**:
- Main page: http://localhost:3000
  - Player Model tab
  - Weekly Value tab
  - Week selector

- System Status: http://localhost:3000/system-status
  - Data readiness indicators
  - Latest batch run
  - Batch history

**Test Week Selector**:
- Change week
- Verify predictions update
- Check URL params

**Test System Status**:
- Run a batch
- Watch status update (auto-refresh)
- Check metrics display

#### 5. Verify Data Integrity

**Check Predictions**:
```sql
SELECT season_year, week, COUNT(*) as predictions
FROM predictions
GROUP BY season_year, week
ORDER BY season_year DESC, week DESC;
```

**Check Game Logs**:
```sql
SELECT season_year, week, COUNT(*) as logs
FROM game_logs
GROUP BY season_year, week
ORDER BY season_year DESC, week DESC;
```

**Check Batch Runs**:
```sql
SELECT batch_type, status, started_at, duration_seconds
FROM batch_runs
ORDER BY started_at DESC
LIMIT 10;
```

**Check Data Readiness**:
```sql
SELECT * FROM data_readiness
WHERE season_year = 2025
ORDER BY week DESC;
```

---

## Troubleshooting

### Database Connection Issues
```bash
# Check if PostgreSQL is running
brew services list

# Check connection
psql postgres -c "SELECT version();"

# Reset connection
pkill -f postgres
brew services restart postgresql@14
```

### API Key Issues
```bash
# Verify key is set
echo $TANK01_API_KEY

# Test API connection
curl -H "X-RapidAPI-Key: $TANK01_API_KEY" \
  "https://tank01-nfl-live-in-game-real-time-statistics-nfl.p.rapidapi.com/getNFLTeamRoster?teamAbv=SF"
```

### Migration Issues
```bash
# Reset migrations
psql bggtdm -c "DROP TABLE IF EXISTS batch_runs CASCADE;"
psql bggtdm -c "DROP TABLE IF EXISTS data_readiness CASCADE;"

# Reapply
python apply_batch_tracking_migration.py
```

### Frontend Not Loading Data
```bash
# Check backend is running
curl http://localhost:8000/health

# Check CORS
# Make sure CORS_ORIGINS includes http://localhost:3000

# Check API URL
echo $NEXT_PUBLIC_API_URL
```

---

## Production Deployment

### Environment Variables
```bash
# Backend
DATABASE_URL=postgresql+asyncpg://user:pass@host:port/bggtdm
TANK01_API_KEY=your_rapidapi_key
NFL_SEASON_YEAR=2025
USE_BOX_SCORES=true
CI=true  # For GitHub Actions

# Frontend
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
```

### GitHub Actions
Runs automatically every Tuesday at 7 AM EST.

**Manual trigger**:
1. Go to GitHub Actions tab
2. Select "Weekly NFL Data Update"
3. Click "Run workflow"

### Monitoring
- Check System Status page
- Review batch_runs table
- Monitor API quota usage
- Set up alerts for failed batches

---

## Quick Reference

### Common Commands
```bash
# Full weekly update
python update_weekly.py && python generate_predictions.py

# Mid-week odds refresh
python update_weekly.py --mode odds_only --week 17 --year 2025

# New player onboarding
python refresh_rosters.py --dry-run
python refresh_rosters.py

# Check system status
curl http://localhost:8000/api/admin/health/summary

# Check current week
python -c "from app.utils.nfl_calendar import get_current_nfl_week; print(get_current_nfl_week())"
```

### File Locations
- Batch scripts: `backend/*.py`
- Models: `backend/app/models/`
- Services: `backend/app/services/`
- API routes: `backend/app/api/`
- Utils: `backend/app/utils/`
- Frontend pages: `frontend/app/*/page.tsx`
- Frontend components: `frontend/components/`

### Database Schema
See: `backend/app/models/` for all table definitions
