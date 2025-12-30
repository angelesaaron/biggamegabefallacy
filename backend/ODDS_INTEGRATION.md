# Sportsbook Odds Integration

## Overview

Complete integration for fetching, storing, and serving DraftKings and FanDuel sportsbook odds for anytime TD props.

## Architecture

### Data Flow
```
Tuesday Sync:
1. Run: python sync_odds.py (or POST /api/odds/refresh)
2. For each game in current week:
   - Call getNFLBettingOdds with gameID parameter
   - Parse playerProps → anytd odds
   - Store in sportsbook_odds table (DraftKings + FanDuel)
3. Database now has fresh odds

Prediction Generation:
1. Read game logs from DB
2. Read sportsbook odds from DB (no API calls!)
3. Generate model prediction
4. Calculate EV and has_edge
5. Return prediction with odds comparison
```

### Database Schema

**sportsbook_odds table:**
```sql
- id (serial primary key)
- player_id (FK to players.player_id)
- game_id (FK to schedule.game_id)  -- Links to specific game
- season_year (int, indexed)
- week (int, indexed)
- sportsbook (varchar) -- 'draftkings' or 'fanduel'
- anytime_td_odds (int) -- American odds (+175, -140, etc.)
- fetched_at (timestamp)

UNIQUE CONSTRAINT: (player_id, game_id, sportsbook)
```

## Automatic Week Detection

No more manual .env updates! The system now auto-detects the current NFL week:

### Primary Method: Schedule Table
```python
from app.utils.nfl_calendar import get_current_nfl_week

year, week = get_current_nfl_week()
# Queries schedule table for next upcoming game
# Returns that game's week
# Handles off-season → returns next season Week 1
```

### Fallback: Calendar-Based
If database unavailable, falls back to hardcoded NFL season start dates.

## API Endpoints

### 1. Manual Refresh (Background Task)
```bash
POST /api/odds/refresh?week=4&year=2025

Response:
{
  "status": "started",
  "message": "Refreshing odds for 2025 Week 4 in background",
  "year": 2025,
  "week": 4
}
```

### 2. Get Current Week Odds
```bash
GET /api/odds/current?sportsbook=draftkings

Response:
{
  "year": 2025,
  "week": 4,
  "sportsbook": "draftkings",
  "odds": [
    {
      "player_id": "3915416",
      "game_id": "20250907_CHI@GB",
      "anytime_td_odds": 175,
      "fetched_at": "2025-12-29T20:00:00Z"
    },
    ...
  ]
}
```

### 3. Compare Model vs Sportsbook
```bash
GET /api/odds/comparison/3915416?week=4&year=2025

Response:
{
  "player_id": "3915416",
  "year": 2025,
  "week": 4,
  "sportsbook_odds": {
    "draftkings": 175,
    "fanduel": 180
  }
}
```

## Scripts

### sync_odds.py - Initial/Manual Sync
```bash
cd backend
source venv/bin/activate

# Sync current week
python sync_odds.py

# Sync specific week
python sync_odds.py --week 5 --year 2025
```

**What it does:**
- Fetches all games for the target week from schedule table
- For each game, calls `getNFLBettingOdds` with `gameID` parameter
- Parses playerProps to extract anytime TD odds
- Stores both DraftKings and FanDuel records
- Replaces existing odds for that week (refresh)

**API Usage:**
- ~1 call per game (e.g., 16 games = 16 API calls)
- Much more efficient than fetching by date

## Tank01 API Integration

### Updated get_betting_odds Method
```python
await client.get_betting_odds(
    game_id="20250907_CHI@GB",  # Use gameID for precise matching
    player_props=True,
    implied_totals=True
)

# Returns:
{
  "statusCode": 200,
  "body": [
    {
      "gameID": "20250907_CHI@GB",
      "playerProps": [
        {
          "playerID": "3915416",
          "propBets": {
            "anytd": "+175",
            "firsttd": "800",
            ...
          }
        },
        ...
      ],
      "sportsBooks": [
        {"sportsBook": "draftkings", "odds": {...}},
        {"sportsBook": "fanduel", "odds": {...}}
      ]
    }
  ]
}
```

## Data Service Updates

### get_betting_odds_for_week()
**Before:** Called Tank01 API per game date
**After:** Reads from sportsbook_odds table

```python
from app.services.data_service import get_data_service

data_service = get_data_service(db)
odds = await data_service.get_betting_odds_for_week(
    season=2025,
    week=4,
    sportsbook="draftkings"
)
# Returns: {"player_id": odds_value, ...}
```

## Weekly Workflow (Updated)

### Tuesday Morning After MNF:
```bash
# 1. Update game logs and schedule
python update_weekly.py

# 2. Sync odds for next week
python sync_odds.py

# 3. Generate predictions
# (predictions now automatically fetch odds from DB)
```

### Manual Refresh (Anytime):
```bash
# Via script
python sync_odds.py --week 5

# Via API (returns immediately, runs in background)
curl -X POST "http://localhost:8000/api/odds/refresh?week=5&year=2025"
```

## Key Features

✅ **Automatic Week Detection** - No manual .env updates
✅ **Database-Backed** - Zero API calls for predictions
✅ **gameID Matching** - Precise player-game association
✅ **Dual Sportsbook** - DraftKings + FanDuel odds
✅ **Background Refresh** - Non-blocking manual updates
✅ **API Efficient** - ~16 calls per week vs hundreds before

## Testing

### 1. Test Week Detection
```bash
python -c "
from app.utils.nfl_calendar import get_current_nfl_week
year, week = get_current_nfl_week()
print(f'Current NFL Week: {year} Week {week}')
"
```

### 2. Test Odds Sync
```bash
# Sync odds for current week
python sync_odds.py
```

### 3. Test API Endpoints
```bash
# Get current odds
curl http://localhost:8000/api/odds/current

# Refresh odds (background task)
curl -X POST http://localhost:8000/api/odds/refresh

# Compare for specific player
curl http://localhost:8000/api/odds/comparison/3915416
```

### 4. Test Prediction with Odds
```bash
curl -X POST "http://localhost:8000/api/predictions/generate/3915416?week=4&year=2025"
# Should include sportsbook_odds and expected_value in response
```

## Future Enhancements

1. **Book-Specific Parsing**: Currently stores same odds for both DK and FD. Tank01 API may provide book-specific odds in sportsBooks array - can parse separately.

2. **Line Movement Tracking**: Add `previous_odds` column to track line changes over time.

3. **Best Line Finding**: Query multiple sportsbooks and return best available odds.

4. **Automated Scheduling**: Add cron job to run `sync_odds.py` automatically on Tuesdays.

## Migration Notes

- Dropped and recreated `sportsbook_odds` table with new schema
- Added `game_id` foreign key to link odds to specific games
- Changed `odds` column to `anytime_td_odds` for clarity
- Added `sync_engine` to database.py for migration scripts
- Installed `psycopg2-binary` for synchronous database operations

## Files Modified/Created

### Created:
- `sync_odds.py` - Bulk odds sync script
- `ODDS_INTEGRATION.md` - This documentation

### Modified:
- `app/models/odds.py` - Updated schema with game_id
- `app/api/odds.py` - Added refresh endpoint and odds queries
- `app/services/data_service.py` - Updated to read odds from DB
- `app/utils/tank01_client.py` - Added game_id parameter support
- `app/utils/nfl_calendar.py` - Automatic week detection from schedule
- `app/database.py` - Added sync_engine for migrations
