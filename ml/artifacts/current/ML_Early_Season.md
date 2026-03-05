# BGGTDM v2 — Early Season Predictions
*From post-training review — March 2026*

---

## The Problem

The model cannot make week 1 predictions for anyone. `feature_prep.py` filters
`games_played >= 1` which drops all week 1 rows. Weeks 2–3 run but rolling
features are based on 1–2 games — `roll3_rz_targets`, `roll3_snap_pct` etc. are
essentially noise that early.

Rookies have no prior-season row at all, so they'd produce NaN across the board
regardless of week.

| Week | Coverage today | With fix |
|---|---|---|
| Week 1 | ❌ No predictions | ✅ Carry-forward |
| Weeks 2–3 | ⚠️ 1–2 game history | ✅ Blend carry-forward + live |
| Weeks 4+ | ✅ Model works | ✅ Unchanged |
| Rookie week 1–3 | ❌ No signal | ✅ Draft-round bucket |

---

## The Approach — Carry-Forward, No Second Model

Rather than training a separate early-season model (extra complexity, small
training sample, separate calibration, two pkl files to maintain), warm-start
week 1 with each player's end-of-prior-season feature values. Same model, same
features, same weights — no distribution shift.

**For vets:** take each player's final row from the prior season as their
week 1–3 feature state. The model already knows how to interpret these values
because that's what it trained on.

**For rookies:** assign the historical average stats for their draft-round +
position bucket. A 1st-round WR gets something near the 65th percentile of
historical first-round WR week 1 stats. A 5th-round TE gets the positional mean.
Built once from training data, never needs updating.

**For team-changers:** flag automatically (prior team ≠ current team). Their
carry-forward usage stats are from a different system — override with positional
mean for that slot, or hold for manual review. Week 1 lines for major free agent
signings are going to be priced with uncertainty anyway.

---

## Implementation

### Step 1 — Build `prior_season_final_state` table

Add to `06_prior_season.ipynb` (new notebook) or append to `05_new_features.ipynb`:

```python
# Take each player's last game of the season as their carry-forward state
prior_final = (
    df.sort_values(['player_id', 'season', 'week'])
    .groupby(['player_id', 'season'])
    .last()
    .reset_index()
)

# Rename to prior_ prefix so they don't collide with current-season columns
carry_cols = [
    'targets_pg', 'yards_pg', 'receptions_pg',
    'roll3_targets', 'roll3_yards', 'roll3_receptions',
    'lag_targets', 'lag_yards',
    'target_share', 'roll3_long_rec', 'roll3_target_std',
    'tds_last3', 'td_streak',
    'td_rate_eb', 'td_rate_eb_std',
    'lag_snap_pct', 'roll3_snap_pct',
    'roll3_rz_targets', 'rz_target_share', 'rz_td_rate_eb',
    'team',
]
prior_final = prior_final[['player_id', 'season', 'name', 'pos', 'team'] + carry_cols]
prior_final['join_season'] = prior_final['season'] + 1

# Save
prior_final.to_csv('data/prior_season_final_state.csv', index=False)
```

### Step 2 — Build `rookie_buckets` table

```python
# Historical week 1–3 stats by draft_round + pos (from training data)
# Use as the prior for any player with no prior-season row
early_weeks = df[df['week'] <= 3].copy()

rookie_buckets = (
    early_weeks.groupby(['draft_round', 'pos'])[carry_cols]
    .median()
    .reset_index()
)
# draft_round=0 = undrafted / vet with no prior season in dataset
rookie_buckets.to_csv('data/rookie_buckets.csv', index=False)
```

### Step 3 — Early Season Feature Resolver

Create `ml/early_season.py`:

```python
"""
Resolves feature values for weeks 1–3 where rolling features are thin or absent.

Priority:
  1. Player has prior-season row + same team → carry-forward
  2. Player has prior-season row + different team → positional mean (team-changer flag)
  3. Player has no prior-season row (rookie) → draft-round bucket
"""

import pandas as pd
import numpy as np

PRIOR_PATH = 'data/prior_season_final_state.csv'
BUCKETS_PATH = 'data/rookie_buckets.csv'

def load_early_season_priors():
    prior = pd.read_csv(PRIOR_PATH)
    buckets = pd.read_csv(BUCKETS_PATH)
    return prior, buckets

def resolve_early_features(players_df, season, week, prior_df, bucket_df):
    """
    players_df: current week's player list with (player_id, name, pos, team, draft_round)
    Returns players_df with all model features filled.
    """
    assert week <= 3, 'Use main pipeline for week >= 4'

    prior_this_season = prior_df[prior_df['join_season'] == season]

    merged = players_df.merge(
        prior_this_season,
        on='player_id',
        how='left',
        suffixes=('', '_prior')
    )

    # Flag team-changers (prior team != current team)
    merged['team_changed'] = (
        merged['team_prior'].notna() &
        (merged['team'] != merged['team_prior'])
    )

    # For team-changers: zero out usage features (new system, unknown role)
    # Keep td_rate_eb (skill travels) but reset volume features
    volume_features = [
        'targets_pg', 'yards_pg', 'receptions_pg',
        'roll3_targets', 'roll3_yards', 'roll3_receptions',
        'lag_targets', 'lag_yards', 'target_share',
        'roll3_rz_targets', 'rz_target_share',
        'lag_snap_pct', 'roll3_snap_pct',
    ]
    for col in volume_features:
        merged.loc[merged['team_changed'], col] = np.nan  # XGBoost handles natively

    # For rookies (no prior row): fill from draft_round + pos bucket
    no_prior = merged['targets_pg'].isna() & ~merged['team_changed']
    if no_prior.any():
        bucket_fill = merged[no_prior].merge(
            bucket_df, on=['draft_round', 'pos'], how='left'
        )
        for col in volume_features + ['td_rate_eb', 'td_rate_eb_std']:
            merged.loc[no_prior, col] = bucket_fill[col].values

    # Log what happened
    n_carry = (~merged['team_changed'] & merged['targets_pg'].notna()).sum()
    n_changed = merged['team_changed'].sum()
    n_rookie = no_prior.sum()
    print(f'Week {week} feature resolution: '
          f'{n_carry} carry-forward, {n_changed} team-changers, {n_rookie} rookies/no-prior')

    if n_changed > 0:
        changers = merged[merged['team_changed']][['name', 'team_prior', 'team']]
        print('Team-changers flagged (volume features zeroed):')
        print(changers.to_string(index=False))

    return merged
```

### Step 4 — Hook into training

To validate the early-season model works, retrain `04_model_training.ipynb` with
the early-season rows included using carry-forward features:

```python
# In feature_prep.py — modify load_and_prepare() to include early-season rows
# Currently: filter games_played >= 1 (drops all week 1)
# New: for week <= 3, allow games_played == 0 IF carry-forward features are present

# The simplest approach during training: include historical week 1–3 rows
# by joining prior_season_final_state onto them before the games_played filter
```

This lets the model train on week 1–3 outcomes with the same carry-forward
features it will use in production — it learns that carry-forward stats predict
early-season TDs rather than being evaluated blind.

---

## Weeks 2–3 Blending

For weeks 2–3 the player has some live data but not enough for rolling windows
to be meaningful. Two options:

**Option A (simple):** Keep the carry-forward through week 3, switch to live
features from week 4 onward. Clean cutoff, no blending logic.

**Option B (weighted blend):** For week 2, use 70% carry-forward / 30% live.
For week 3, use 40% carry-forward / 60% live.

Recommendation: start with Option A. The 1–2 game live window is too small to
reliably beat prior-season signal. Revisit blending after you have a full early
season of data to calibrate against.

---

## Honest Limitations

- **Role continuity assumption:** carry-forward works when usage is stable. It's
  wrong for players who lost starting jobs in the offseason, players recovering
  from injury, and major scheme changes (new OC, new QB). Human override for
  obvious cases.
- **Rookie accuracy:** draft-round buckets are rough. A 1st-round WR who sits
  behind a starter week 1 will be overestimated. There's no way around this
  without snap/depth chart data that isn't available before the season starts.
- **Calibration:** the Beta calibration was fitted on weeks 4–18 data. Early
  season probabilities may be slightly off even if the ranking is correct. Run
  a reliability check on early-season holdout weeks (2023/2024 weeks 1–3) once
  the prior-season feature join is built.

---

## Files to Create

| File | Purpose |
|---|---|
| `ml/06_prior_season.ipynb` | Build `prior_season_final_state.csv` + `rookie_buckets.csv` |
| `ml/early_season.py` | Feature resolver for weeks 1–3 |
| `ml/data/prior_season_final_state.csv` | End-of-season carry-forward state per player |
| `ml/data/rookie_buckets.csv` | Median stats by draft_round + pos |

`feature_prep.py` and `train.py` get minor updates to include early-season rows
using carry-forward features. No second model. No second pkl. Same calibration.
