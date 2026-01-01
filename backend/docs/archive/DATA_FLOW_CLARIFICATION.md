# Data Flow Clarification

## Critical Understanding: Week Detection vs Prediction

### How Week Detection Works

`get_current_nfl_week()` returns the **next upcoming week** to predict:

```python
# Tuesday after Week 17 MNF finishes
current_season, current_week = get_current_nfl_week()
# Returns: (2025, 18)
#
# This is Week 18 - the upcoming week we want to predict
```

### Data Requirements for Predictions

When predicting Week N, we need:
1. **Historical game logs:** Weeks 1 through (N-1)
2. **Sportsbook odds:** Week N

**Example: Predicting Week 18**
- Model input: Game logs from Weeks 1-17 (historical performance)
- Sportsbook odds: Week 18 (the week we're predicting)
- Output: Week 18 TD predictions

## Tuesday Workflow Example

**Scenario:** It's Tuesday, Dec 31, 2024. Week 17 games just finished on Monday night.

### Step 1: Automatic Week Detection

```bash
current_season, current_week = get_current_nfl_week()
# Returns: (2025, 18)
#
# The function looks at schedule table, finds next upcoming games → Week 18
```

### Step 2: Update Weekly Data

```bash
python update_weekly.py
```

**What it does:**

1. **Updates Schedule** (Weeks 18-19)
   - Ensures we have game IDs for upcoming weeks

2. **Fetches Game Logs** for Week `current_week - 1` = **Week 17**
   - These are the games that just finished
   - Updates historical data

3. **Fetches Sportsbook Odds** for Week `current_week` = **Week 18**
   - These are the upcoming games
   - DraftKings + FanDuel anytime TD odds

**Result:**
- Database now has Weeks 1-17 game logs (historical)
- Database now has Week 18 odds (upcoming)

### Step 3: Generate Predictions

```bash
python generate_predictions.py
```

**What it does:**

For each WR/TE player:

1. **Fetch game logs** from database
   ```python
   # In get_game_logs_for_current_season():
   filtered_logs = [
       log for log in all_logs
       if log.get("week") and log["week"] < current_week
   ]
   # Returns: Weeks 1-17 (current_week=18, so week < 18)
   ```

2. **Fetch sportsbook odds** from database
   ```python
   # In get_betting_odds_for_week():
   odds = get_betting_odds_for_week(
       season=current_season,
       week=current_week  # Week 18
   )
   ```

3. **Run ML model**
   - Extract features from Weeks 1-17 historical data
   - Calculate TD probability
   - Convert to American odds

4. **Calculate expected value**
   - Compare model probability vs sportsbook implied probability
   - Determine if bet has positive edge

5. **Store prediction** in database

**Result:**
- 538 predictions for Week 18
- Each prediction uses correct historical data (Weeks 1-17)
- Each prediction compares against correct odds (Week 18)

## Visual Data Flow

```
Tuesday Morning After Week 17 MNF
==================================

┌─────────────────────────────────────────┐
│  get_current_nfl_week()                 │
│  → Queries schedule table               │
│  → Finds next upcoming games            │
│  → Returns: (2025, 18)                  │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│  update_weekly.py                       │
│  current_week = 18                      │
├─────────────────────────────────────────┤
│  1. Update schedule (Weeks 18-19)       │
│  2. Fetch game logs (Week 17)           │
│     current_week - 1 = 17               │
│  3. Fetch odds (Week 18)                │
│     current_week = 18                   │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│  Database State                         │
├─────────────────────────────────────────┤
│  game_logs: Weeks 1-17 ✅               │
│  sportsbook_odds: Week 18 ✅            │
│  schedule: Weeks 1-19 ✅                │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│  generate_predictions.py                │
│  current_week = 18                      │
├─────────────────────────────────────────┤
│  For each player:                       │
│    1. Get game logs (Weeks 1-17)        │
│       week < current_week               │
│    2. Get odds (Week 18)                │
│       week = current_week               │
│    3. Run ML model                      │
│    4. Calculate EV                      │
│    5. Save prediction                   │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│  Result: Week 18 Predictions Ready      │
├─────────────────────────────────────────┤
│  Model trained on: Weeks 1-17           │
│  Sportsbook odds: Week 18               │
│  Prediction output: Week 18 TD probs    │
└─────────────────────────────────────────┘
```

## Common Mistakes to Avoid

❌ **WRONG:** Fetch odds for `current_week + 1`
- If current_week = 18, this would fetch Week 19 odds
- We're predicting Week 18, not Week 19!

✅ **CORRECT:** Fetch odds for `current_week`
- current_week is already the next upcoming week
- get_current_nfl_week() handles this automatically

❌ **WRONG:** Use game logs including current_week
- If predicting Week 18, don't include Week 18 game logs
- Those games haven't been played yet!

✅ **CORRECT:** Filter logs to `week < current_week`
- Only use historical data
- Week 18 games haven't happened yet

## Key Takeaway

**The user's correction was spot-on:**

> "one thing its not N+1; if i am looking at app on week 17; the model params are week 16 and sportsbook odds are week 17 bc im looking at week 17"

When viewing Week N predictions:
- **Model trains on:** Weeks 1 through (N-1) — historical data
- **Sportsbook odds are:** Week N — the week being predicted

This is now correctly implemented in the system.
