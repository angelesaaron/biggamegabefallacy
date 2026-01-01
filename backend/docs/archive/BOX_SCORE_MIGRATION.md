# Box Score Migration - API Call Reduction

## Overview

This document describes the migration from per-player game log fetching to box score-based fetching, reducing weekly API calls from ~556 to ~34 (94% reduction).

## Background

### Previous Architecture (Per-Player Method)
- Fetched game logs individually for each WR/TE player
- **API Calls per week:** ~556 total
  - 2 schedule calls
  - 538 player game log calls (one per player)
  - 16 odds calls
- **Implementation:** `update_game_logs()` in [update_weekly.py](../update_weekly.py)

### New Architecture (Box Score Method)
- Fetches box scores for completed games
- Extracts all player stats from each box score
- **API Calls per week:** ~34 total
  - 2 schedule calls
  - 16 box score calls (one per game)
  - 16 odds calls
- **Implementation:** `update_game_logs_from_box_scores()` in [update_weekly.py](../update_weekly.py)

**Reduction: 538 calls → 16 calls (97% reduction in game log calls)**

## Implementation Details

### 1. Tank01Client Updates

Added helper function to parse box scores:
```python
def parse_game_logs_from_box_score(
    box_score: Dict[str, Any],
    game_id: str,
    season_year: int,
    week: int
) -> List[Dict[str, Any]]
```

Added client method:
```python
async def get_game_logs_from_box_score(
    self,
    game_id: str,
    season_year: int,
    week: int
) -> List[Dict[str, Any]]
```

**Location:** [app/utils/tank01_client.py](../app/utils/tank01_client.py)

### 2. Weekly Update Script

Added new function:
```python
async def update_game_logs_from_box_scores(db, client, current_season, current_week)
```

**Location:** [update_weekly.py](../update_weekly.py)

### 3. Feature Flag

Box score method is enabled by default. To use legacy per-player method:

```bash
USE_BOX_SCORES=false python update_weekly.py
```

Or set in environment:
```bash
export USE_BOX_SCORES=false
```

Default: `true` (box score method)

## Box Score Data Structure

### API Response Format
```json
{
  "body": {
    "gameID": "20241229_DET@SF",
    "playerStats": {
      "4685": {
        "playerID": "4685",
        "team": "SF",
        "teamID": "26",
        "Receiving": {
          "recTD": "1",
          "targets": "11",
          "receptions": "11",
          "recYds": "90",
          "longRec": "28",
          "recAvg": "8.2"
        }
      }
    }
  }
}
```

### Extracted Game Log Format
```python
{
    "player_id": "4685",
    "game_id": "20241229_DET@SF",
    "season_year": 2024,
    "week": 17,
    "team": "SF",
    "team_id": "26",
    "receptions": 11,
    "receiving_yards": 90,
    "receiving_touchdowns": 1,
    "targets": 11,
    "long_reception": 28,
    "yards_per_reception": 8.2
}
```

## Edge Cases & Validation

### 1. Players Without Receiving Stats
**Scenario:** QB, RB, OL, DEF players in box score
**Handling:** Skipped (no "Receiving" key)
**Impact:** Only WR/TE with targets are included

### 2. Players with Zero Stats
**Scenario:** WR targeted but got 0 catches
**Example:** 2 targets, 0 receptions, 0 yards
**Handling:** Included in game logs
**Reason:** Model needs to know player played but had no production

### 3. Inactive Players
**Scenario:** Player on roster but didn't play
**Handling:** Not in box score, so not included
**Impact:** No game log created (correct behavior)

### 4. Players Not in Database
**Scenario:** Box score contains player we don't track (e.g., QB, RB)
**Handling:** Skipped to avoid foreign key violations
**Logging:** Counted and reported at end

### 5. Missing Optional Fields
**Scenario:** `longRec` or `recAvg` might be missing
**Handling:** Set to `None` if missing/empty
**Code:** Safe parsing with fallbacks

### 6. String vs Numeric Values
**Scenario:** API returns "1" instead of 1
**Handling:** Explicit `int()` and `float()` conversion
**Fallback:** 0 for required fields, None for optional

## Test Results (Week 17 2025)

### Single Game Test
```
Game: 20251225_DAL@WSH
✅ Box score fetched: 92 total players
✅ Extracted 17 game logs (with receiving stats)
✅ Found 2 receiving TDs
✅ Correctly included 3 players with 0 catches
```

### All Games Test
```
Games processed: 16/16
Total game logs: 258
Total receiving TDs: 40
✅ All games successful
```

**Run tests:**
```bash
python test_box_score.py
```

## Migration Plan

### Phase 1: Testing (COMPLETED)
- ✅ Implement box score parsing
- ✅ Add client methods
- ✅ Test with Week 17 2025 data
- ✅ Validate edge cases

### Phase 2: Soft Launch (CURRENT)
- ✅ Add feature flag (default: enabled)
- ⏳ Run alongside per-player method for 1-2 weeks
- ⏳ Monitor for discrepancies
- ⏳ Compare data completeness

### Phase 3: Full Migration (FUTURE)
- Remove feature flag
- Remove legacy `update_game_logs()` function
- Update documentation
- Announce in changelog

## Performance Comparison

| Metric | Per-Player | Box Score | Savings |
|--------|------------|-----------|---------|
| Game log API calls | 538 | 16 | 97% |
| Total API calls/week | ~556 | ~34 | 94% |
| Execution time | ~5-10 min | ~30 sec | 90% |
| Rate limit risk | High | Low | - |

## Rollback Plan

If issues are discovered:

1. Set environment variable:
   ```bash
   export USE_BOX_SCORES=false
   ```

2. Or modify [update_weekly.py](../update_weekly.py) line 476:
   ```python
   use_box_scores = os.environ.get('USE_BOX_SCORES', 'false').lower() == 'true'
   ```

3. Re-run weekly update script

## Known Limitations

1. **Historical Data:** Box scores only available for completed games. Cannot backfill historical seasons this way.

2. **Position Filtering:** We don't filter by position - we include ALL players with receiving stats. This may include RBs with targets.

3. **Game Status:** Must wait until game is marked complete before box score is available.

4. **API Availability:** If Tank01 box score endpoint is down, can fallback to per-player method.

## Validation Checklist

When testing new week data, verify:

- ✅ Number of game logs matches expected (16 games × ~15 players = ~240 logs)
- ✅ Total TDs matches NFL.com stats
- ✅ No foreign key violations (all player_ids in database)
- ✅ Zero-stat players included (targets > 0, receptions = 0)
- ✅ All required fields populated
- ✅ No duplicate game logs

## Future Optimizations

1. **Batch Processing:** Process multiple box scores concurrently
2. **Caching:** Cache box score responses to avoid re-fetching
3. **Incremental Updates:** Only fetch box scores for new games
4. **Compression:** Request compressed responses from API

## Questions & Troubleshooting

### Q: What if a box score is missing?
**A:** Fall back to per-player method for that specific week, or wait for API to populate data.

### Q: Do we get defensive TDs?
**A:** No, we only extract "Receiving" stats. Defensive TDs are in different stat categories.

### Q: What about playoff games?
**A:** Same approach works - just use `season_type="post"` in schedule query.

### Q: Can we use this for historical backfill?
**A:** Yes, if box scores are available for those historical weeks. Test first.

## References

- Tank01 API Docs: https://rapidapi.com/tank01/api/tank01-nfl-live-in-game-real-time-statistics-nfl
- Implementation PR: [TBD]
- Test Results: [test_box_score.py](../test_box_score.py)
