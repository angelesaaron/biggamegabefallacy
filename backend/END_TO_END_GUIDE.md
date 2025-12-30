# End-to-End System Guide

Complete guide for running the NFL TD Prediction System from data sync to predictions.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     ONE-TIME SETUP                          │
├─────────────────────────────────────────────────────────────┤
│ 1. sync_schedule.py   → Populate schedule table            │
│ 2. sync_game_logs.py  → Populate game_logs table          │
│ 3. sync_odds.py       → Populate sportsbook_odds table    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              WEEKLY MAINTENANCE (Tuesday AM)                │
├─────────────────────────────────────────────────────────────┤
│ 1. update_weekly.py   → Updates schedule, game logs, odds  │
│ 2. generate_predictions.py → Batch prediction generation   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    PREDICTION SERVING                       │
├─────────────────────────────────────────────────────────────┤
│ GET /api/predictions/current  → Serve from database        │
│ GET /api/predictions/{id}     → Zero API calls!            │
└─────────────────────────────────────────────────────────────┘
```

## One-Time Setup (First Run)

### Prerequisites
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt

# Start PostgreSQL database
# Update .env with database credentials
```

### Step 1: Sync Schedule (~2 minutes, 36 API calls)
```bash
python sync_schedule.py
```

**What it does:**
- Fetches all games for 2024 and 2025 seasons
- Stores in `schedule` table with `game_id`, `week`, `season_year`
- Creates the foundation for week detection and game mapping

**Result:**
- ~544 games in database (272 per season × 2 years)

### Step 2: Sync Game Logs (~10 minutes, 538 API calls)
```bash
python sync_game_logs.py
```

**What it does:**
- Fetches historical game logs for all 538 WR/TE players
- Uses schedule table to enrich with week numbers
- Stores in `game_logs` table

**Result:**
- ~7,000+ game logs in database
- Each log has `player_id`, `game_id`, `week`, stats

### Step 3: Sync Sportsbook Odds (~2 minutes, ~16 API calls)
```bash
# Sync for current week
python sync_odds.py

# Or specific week
python sync_odds.py --week 4 --year 2025
```

**What it does:**
- Fetches betting odds using `gameID` parameter
- Parses `playerProps` → `anytd` odds
- Stores DraftKings and FanDuel odds separately

**Result:**
- Odds for all players in target week
- Linked to specific games via `game_id`

### Step 4: Generate Initial Predictions (~5 minutes, 0 API calls!)
```bash
python generate_predictions.py
```

**What it does:**
- Generates predictions for all WR/TE players
- Reads game logs from database
- Reads sportsbook odds from database
- Stores predictions in database

**Result:**
- ~538 predictions ready to serve
- All data pre-computed, instant API responses

---

## Weekly Maintenance (Every Tuesday)

### The All-in-One Script

```bash
# Run after Monday Night Football
python update_weekly.py
```

**What it does:**
1. **Updates Schedule** - Fetches current + next week games (2 API calls)
2. **Updates Game Logs** - Fetches new logs from last week (538 API calls)
3. **Syncs Odds** - Fetches odds for next week (~16 API calls)

**Total:** ~556 API calls (well within 10,000/month limit)

### Generate Predictions for Next Week

```bash
python generate_predictions.py
```

**What it does:**
- Generates predictions for all players for upcoming week
- Uses freshly updated game logs
- Uses freshly synced odds
- Stores in database for instant serving

---

## Complete Tuesday Workflow Example

**Scenario:** It's Tuesday morning, Dec 31, 2024. Week 17 games just finished.

```bash
cd backend
source venv/bin/activate

# 9:00 AM - Update all data
python update_weekly.py
# ✅ Schedule updated (Weeks 17-18)
# ✅ Game logs updated (Week 17 stats added)
# ✅ Odds synced for Week 18

# 9:10 AM - Generate predictions
python generate_predictions.py
# Enter 'yes' when prompted
# ✅ 538 predictions generated for Week 18
#    - Uses Weeks 1-17 historical game logs
#    - Uses Week 18 sportsbook odds
# ✅ All stored in database

# 9:15 AM - Start API server
uvicorn app.main:app --reload

# Done! Week 18 predictions ready to serve
```

**No .env updates needed** - Week detection is automatic!

---

## API Usage

### Get Current Week Predictions
```bash
# Get all predictions for current week
curl http://localhost:8000/api/predictions/current

# Get prediction for specific player
curl http://localhost:8000/api/predictions/3915416
```

### Generate On-Demand Prediction
```bash
# Generate fresh prediction (reads from DB, 0 API calls)
curl -X POST "http://localhost:8000/api/predictions/generate/3915416?week=4&year=2025"

# Response includes:
# - Model prediction (TD probability, odds)
# - Sportsbook odds (DraftKings, FanDuel)
# - Expected value (EV)
# - Edge indicator (has_edge: true/false)
```

### Manual Odds Refresh
```bash
# Refresh odds for current week (background task)
curl -X POST http://localhost:8000/api/odds/refresh

# Refresh specific week
curl -X POST "http://localhost:8000/api/odds/refresh?week=5&year=2025"
```

### Get Sportsbook Odds
```bash
# Get all odds for current week
curl "http://localhost:8000/api/odds/current?sportsbook=draftkings"

# Compare model vs sportsbook for player
curl "http://localhost:8000/api/odds/comparison/3915416?week=4"
```

---

## Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                    PREDICTION REQUEST                         │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│          1. Fetch Game Logs from Database                    │
│             - SELECT * FROM game_logs WHERE...               │
│             - 0 API calls                                    │
└──────────────────────────────────��───────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│          2. Extract Features                                 │
│             - Calculate lagged stats                         │
│             - Rolling averages                               │
│             - TD rates                                       │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│          3. Run ML Model                                     │
│             - Random Forest prediction                       │
│             - Convert probability → American odds            │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│          4. Fetch Sportsbook Odds from Database              │
│             - SELECT * FROM sportsbook_odds WHERE...         │
│             - 0 API calls                                    │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│          5. Calculate Expected Value                         │
│             - EV = (model_prob × payout) - (1 - model_prob)  │
│             - has_edge = model_prob > implied_prob           │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│          6. Return Prediction                                │
│             {                                                │
│               "td_probability": 0.41,                        │
│               "model_odds": "+144",                          │
│               "sportsbook_odds": 175,                        │
│               "expected_value": 0.1275,                      │
│               "has_edge": true                               │
│             }                                                │
└──────────────────────────────────────────────────────────────┘
```

---

## Automatic Week Detection

No more manual .env updates! The system auto-detects current week.

### How It Works

1. **Primary Method:** Query schedule table
   ```python
   from app.utils.nfl_calendar import get_current_nfl_week

   year, week = get_current_nfl_week()
   # Finds next upcoming game → returns that week
   ```

2. **Fallback:** Calendar-based calculation
   - Uses hardcoded NFL season start dates
   - Calculates week based on days elapsed

3. **Off-Season Handling:**
   - After Week 18 → Returns next season Week 1
   - Before season starts → Returns current year Week 1

---

## Database Schema

### Players Table
```sql
- player_id (PK) - Tank01 player ID
- full_name, position, team
- active_status
```

### Schedule Table
```sql
- game_id (PK) - "YYYYMMDD_AWAY@HOME"
- season_year, week
- home_team, away_team
- game_date, game_status
```

### Game Logs Table
```sql
- player_id (FK)
- game_id (FK)
- season_year, week
- receptions, receiving_yards, receiving_touchdowns
- targets, yards_per_reception
```

### Sportsbook Odds Table
```sql
- player_id (FK)
- game_id (FK)
- season_year, week
- sportsbook ('draftkings', 'fanduel')
- anytime_td_odds (American odds)
- fetched_at
```

### Predictions Table
```sql
- player_id (FK)
- season_year, week
- td_likelihood (probability)
- model_odds (American odds)
- favor (underdog/favorite)
- created_at
```

---

## API Call Budget

| Operation | Frequency | Calls/Run | Annual Total |
|-----------|-----------|-----------|--------------|
| Initial schedule sync | Once | 36 | 36 |
| Initial game logs sync | Once | 538 | 538 |
| Initial odds sync | Once | 16 | 16 |
| Weekly schedule update | 18×/season | 2 | 36 |
| Weekly game logs update | 18×/season | 538 | 9,684 |
| Weekly odds sync | 18×/season | 16 | 288 |
| **Annual Total** | | | **~10,600 calls** |

**Within limits:** 10,000 free calls/month from Tank01 = 120,000/year

---

## Troubleshooting

### No predictions returned
```bash
# Check if predictions exist for current week
python -c "
from app.utils.nfl_calendar import get_current_nfl_week
year, week = get_current_nfl_week()
print(f'Current week: {year} Week {week}')
"

# Generate predictions if needed
python generate_predictions.py
```

### Odds not found
```bash
# Check current week odds
curl http://localhost:8000/api/odds/current

# Sync if needed
python sync_odds.py
```

### Week detection wrong
```bash
# Check schedule table
python -c "
from app.database import SessionLocal
from app.models.schedule import Schedule
from sqlalchemy import select
db = SessionLocal()
result = db.execute(select(Schedule).order_by(Schedule.game_date).limit(5))
for game in result.scalars():
    print(f'{game.game_date} - Week {game.week}')
db.close()
"
```

---

## Performance Metrics

- **Prediction Generation:** 0 API calls (reads from DB)
- **Average Response Time:** <100ms (database queries)
- **Weekly Maintenance:** ~556 API calls (~5% of monthly limit)
- **Data Freshness:** Updates every Tuesday after MNF

---

## Next Steps

1. **Add Cron Job** - Automate Tuesday maintenance
2. **Build Frontend** - Display predictions with odds comparison
3. **Value Picks** - Filter predictions by `has_edge: true`
4. **Line Movement** - Track odds changes over time
5. **Model Retraining** - Periodically retrain with new data
