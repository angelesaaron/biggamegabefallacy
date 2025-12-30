# Prediction Architecture - Unified Service Pattern

## Overview

This system uses a **unified prediction service** pattern to ensure consistent prediction generation across all entry points. All predictions flow through a single source of truth.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Prediction Sources                        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────┐        ┌──────────────────────────┐  │
│  │  API Endpoint    │        │  Batch Script            │  │
│  │  /generate/...   │        │  generate_historical_... │  │
│  └────────┬─────────┘        └────────┬─────────────────┘  │
│           │                           │                      │
│           └───────────┬───────────────┘                      │
│                       │                                      │
│           ┌───────────▼───────────┐                         │
│           │  PredictionService     │                         │
│           │  (Unified Service)     │                         │
│           └───────────┬───────────┘                         │
│                       │                                      │
│         ┌─────────────┼─────────────┐                       │
│         │             │             │                        │
│    ┌────▼────┐  ┌────▼────┐  ┌────▼────┐                  │
│    │ Get     │  │ Model   │  │ Save    │                   │
│    │ Game    │  │ Service │  │ to DB   │                   │
│    │ Logs    │  │         │  │         │                   │
│    └─────────┘  └─────────┘  └─────────┘                   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │  predictions       │
                    │  (Database Table)  │
                    └───────────────────┘
```

## Components

### 1. PredictionService (`app/services/prediction_service.py`)

**Single source of truth** for all prediction generation.

**Key Methods:**

- `generate_prediction(player_id, season_year, week, save_to_db, update_existing)`
  - Fetches game logs up to (but not including) target week
  - Uses model service to generate prediction
  - Optionally saves to database
  - Handles update vs skip logic

- `generate_current_week_predictions(season_year, week, update_existing)`
  - Batch generates predictions for all players
  - Used by weekly automation scripts

**Features:**

- Week 1: Uses baseline prediction with default features
- Week 2+: Uses trailing game data from same season
- Cumulative per-game averages (yards/game, receptions/game, etc.)
- Rolling 3-game averages with min_periods=1
- All features lagged by 1 week

### 2. API Endpoint (`/api/predictions/generate/{player_id}`)

**Usage:** Generate predictions on-demand via HTTP

**Parameters:**
- `week`: Week number (defaults to current week)
- `year`: Season year (defaults to current year)
- `save_to_db`: Whether to save prediction (default: true)
- `update_existing`: Whether to update existing predictions (default: true)

**Behavior:**
- Uses `PredictionService.generate_prediction()`
- `update_existing=True`: Updates existing predictions (useful for model improvements)
- Returns prediction with sportsbook odds and EV calculation

### 3. Batch Script (`generate_historical_predictions.py`)

**Usage:** Generate predictions for all players/weeks in bulk

**Command:**
```bash
python generate_historical_predictions.py --season 2025 [--dry-run]
```

**Behavior:**
- Uses `PredictionService.generate_prediction()`
- `update_existing=False`: Skips existing predictions (idempotent)
- Processes all player/season combinations
- Shows actual TD results alongside predictions

## Database Table

### `predictions`

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer | Primary key |
| `player_id` | String | FK to players table |
| `season_year` | Integer | Season year (e.g., 2025) |
| `week` | Integer | Week number (1-18) |
| `td_likelihood` | Numeric(5,4) | TD probability (0-1) |
| `model_odds` | Numeric(8,2) | American odds value |
| `favor` | Integer | 1=underdog, -1=favorite |
| `created_at` | DateTime | When prediction was generated |

**Unique Constraint:** `(player_id, season_year, week)`

## Conflict Handling

### Update vs Skip

**API Endpoint (default: update_existing=True):**
- Updates existing predictions
- Useful when model is improved or data is corrected
- Timestamp updated to reflect regeneration

**Batch Script (default: update_existing=False):**
- Skips existing predictions
- Idempotent - can be run multiple times safely
- Only fills in missing predictions

### When to Use Each

**Use `update_existing=True`:**
- Model has been retrained/improved
- Bug fix in feature engineering
- Regenerating all predictions with new methodology

**Use `update_existing=False`:**
- Backfilling historical data
- Regular weekly batch generation
- Don't want to overwrite manual adjustments

## Feature Engineering

All predictions use the same feature extraction logic:

**Week 1 Features:**
```python
[week, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1]  # All zeros except week and is_first_week flag
```

**Week 2+ Features (11 total):**
1. `week` - Week number being predicted
2. `lag_yds` - Previous game receiving yards
3. `cumulative_yards_per_game` - Season average yards/game
4. `cumulative_receptions_per_game` - Season average receptions/game
5. `cumulative_targets_per_game` - Season average targets/game
6. `avg_receiving_yards_last_3` - Rolling 3-game average yards
7. `avg_receptions_last_3` - Rolling 3-game average receptions
8. `avg_targets_last_3` - Rolling 3-game average targets
9. `yards_per_reception` - Previous game yards/reception
10. `td_rate_per_target` - Cumulative TD rate per target
11. `is_first_week` - Binary flag (0 for week 2+)

**Important:**
- All features are **lagged by 1 week**
- Cumulative stats are **per-game averages**, not raw totals
- Rolling windows use `min_periods=1` so they work with 1-2 games
- Only uses data from **same season** (doesn't carry over from previous year)

## Usage Examples

### Generate Current Week Predictions (API)

```bash
# Generate for specific player
curl -X POST "http://localhost:8000/api/predictions/generate/15795?week=18&year=2025"

# Update existing prediction
curl -X POST "http://localhost:8000/api/predictions/generate/15795?update_existing=true"
```

### Backfill Historical Predictions (Batch)

```bash
# Dry run to test
python generate_historical_predictions.py --season 2025 --dry-run

# Generate all 2025 predictions
python generate_historical_predictions.py --season 2025

# Generate all seasons
python generate_historical_predictions.py
```

### Retrieve Predictions

```bash
# Get current week predictions for all players
curl "http://localhost:8000/api/predictions/current"

# Get historical predictions for one player
curl "http://localhost:8000/api/predictions/history/15795?season=2025&weeks=20"
```

## Best Practices

1. **Weekly Workflow:**
   - Monday: Sync rosters and game logs from Tank01
   - Tuesday: Run batch script to generate current week predictions
   - Throughout week: API generates predictions on-demand with latest data

2. **Model Updates:**
   - Retrain model with new data
   - Update `MODEL_PATH` in settings
   - Run batch script with `update_existing=True` to regenerate all predictions

3. **Data Quality:**
   - Always run batch script with `--dry-run` first
   - Review predictions vs actual results for validation
   - Monitor error rates and skipped predictions

4. **Consistency:**
   - **Always use PredictionService** for generating predictions
   - Never bypass the service layer
   - All prediction logic lives in one place

## Future Enhancements

- [ ] Add prediction confidence intervals
- [ ] Store feature values alongside predictions for debugging
- [ ] Add prediction version tracking for model updates
- [ ] Implement prediction performance metrics
- [ ] Add automatic weekly prediction generation (cron job)
