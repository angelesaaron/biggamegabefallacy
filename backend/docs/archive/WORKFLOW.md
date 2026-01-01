# Weekly Workflow

## Timeline

### One-Time Setup (Today)
```
1. ✅ Already done: Players synced (538 WR/TE)
2. Run: python sync_schedule.py        (~2 min, 36 API calls)
3. Run: python sync_game_logs.py       (~10 min, 538 API calls)
4. Run: python sync_odds.py            (~2 min, 16 API calls)
5. Run: python generate_predictions.py (~5 min, 0 API calls)
```

**Result:** Database populated with all historical data and predictions ready

---

### Every Tuesday Morning (Weekly Maintenance)
```
Tuesday Morning (after Monday Night Football finishes):
├─ 9:00 AM - Run: python update_weekly.py
│           (~5 min, 556 API calls)
│           ├─ Updates schedule for Week N+1
│           ├─ Fetches Week N game logs
│           └─ Syncs odds for Week N+1
│
├─ 9:10 AM - Run: python generate_predictions.py
│           (~5 min, 0 API calls)
│           └─ Generate predictions for Week N+1
│              (Reads from DB, runs model, saves predictions)
│
└─ 9:15 AM - Predictions ready!
            ├─ Week detection is automatic (no .env update needed!)
            └─ Users can query Week N+1 predictions
```

---

### Daily (Optional - for live odds)
```
If you want fresh sportsbook odds:
└─ Run odds sync daily (separate feature, not built yet)
```

---

## Prediction Generation Flow

### Current State (After Initial Sync)
```
Week 17 (Current):
├─ schedule table: Has Week 1-18 games for 2024-2025
├─ game_logs table: Has Weeks 1-16 game logs (historical data)
├─ sportsbook_odds table: Has Week 17 odds (DraftKings + FanDuel)
└─ Ready to predict: Week 17

To predict Week 17:
1. Query game_logs for player (Weeks 1-16 only, historical)
2. Extract features from recent games
3. Run ML model to get TD probability
4. Fetch sportsbook odds for Week 17
5. Calculate expected value and edge
6. Return prediction with model odds + sportsbook comparison
```

### After Tuesday Update (Next Week)
```
Tuesday after Week 17 MNF:
├─ schedule table: Updated with latest games
├─ game_logs table: Added Week 17 new game logs
├─ sportsbook_odds table: Fetched Week 18 odds
└─ Ready to predict: Week 18

To predict Week 18:
1. Query game_logs for player (Weeks 1-17 historical)
2. Extract features from 17 weeks of data
3. Run ML model
4. Fetch Week 18 sportsbook odds
5. Return Week 18 prediction
```

---

## Data Freshness

| Data | Update Frequency | Script |
|------|-----------------|--------|
| Players | Monthly or when needed | `sync_rosters.py` |
| Schedule | Weekly (Monday) | `update_weekly.py` |
| Game Logs | Weekly (Monday) | `update_weekly.py` |
| Predictions | Weekly (Monday) | Generate batch predictions |
| Odds | Daily (optional) | TBD |

---

## API Call Budget

| Operation | Frequency | Calls | Annual Total |
|-----------|-----------|-------|--------------|
| Initial schedule sync | Once | 36 | 36 |
| Initial game logs sync | Once | 538 | 538 |
| Weekly schedule update | 18x/season | 2 | 36 |
| Weekly game logs update | 18x/season | 538 | 9,684 |
| **Annual Total** | | | **~10,300 calls** |

With 10,000 free Tank01 calls/month, you're well within limits.

---

## Example: Week 17 → Week 18 Transition

**Friday, Week 17:**
- Users query predictions for Week 17 games
- All data served from database (instant)

**Sunday/Monday, Week 17:**
- Games are played
- No action needed yet

**Tuesday Morning (after Monday Night Football):**
```bash
# 1. Update data (fetches Week 17 game logs + Week 18 odds)
python update_weekly.py

# 2. Generate Week 18 predictions
python generate_predictions.py
# - Model trains on: Weeks 1-17 historical game logs
# - Uses: Week 18 sportsbook odds
# - Outputs: Week 18 TD predictions

# 3. Users can now query Week 18 predictions
# Week detection is automatic - no .env updates needed!
```

**Week 18 Games (Thurs/Sat/Sun/Mon):**
- Users query Week 18 predictions throughout the week
- All data served from cache
- Zero API calls