# BGGTDM v2 — ML Notes & Next Steps
*From model review session — March 2026*

---

## Current State (v2 as built)

| Metric | v1 (WR-only, 2024 holdout) | v2 Target | v2 Actual (2025 holdout) |
|---|---|---|---|
| ROC-AUC | 0.695 | > 0.730 | 0.657 |
| Brier Score | 0.133 | < 0.115 | 0.155 |
| 95th pct prob | ~0.43 | > 0.50 | 0.409 |
| TD Recall @20% | ~15% | > 35% | 0.330 |
| Reliability max dev | unknown | < 0.05 | 0.169 |

v2 did not beat v1. Key confounds: v2 includes TEs (harder to predict), 2025 may be a harder holdout year than 2024. The EB shrinkage (α=17.4, β=339.9) is working correctly — that's a sensible prior TD rate of ~4.9% per target.

**Beta calibration selected over temperature scaling (0.17 vs 0.39 max deviation).** Both are still too high — calibration quality is downstream of discrimination quality. A 0.657 AUC model can't calibrate cleanly because there isn't enough signal to tighten probability bands.

---

## Why AUC Is Plateauing

### The Feature Ceiling Problem
From notebook 03, best features top out at r ≈ 0.21 (Pearson). For binary classification this corresponds to a theoretical AUC ceiling of ~0.66–0.68 with the current feature set. The v2 target of 0.730 is not achievable from receiving stats alone. The model is *at* the ceiling of what the current data can support — this is not a tuning problem.

### The Training Split Problem (fixable now)
Current split: train on 2022–2023 (~3,300 rows), use all of 2024 (~2,200 rows) for early stopping. That's 2,000 rows sitting idle that should be training data. Fix: train on 2022 through week 13 of 2024, use weeks 14–18 of 2024 for early stopping only. Same 2025 holdout. This is a one-line change and should be the first thing done before any new data fetching.

### Missing Features (the real fix)
Three features are absent that each independently move AUC:

| Feature | Est. AUC gain | Source | Prediction-time dependency |
|---|---|---|---|
| Offensive snap % | +0.020–0.025 | nfl_data_py `import_snap_counts()` | None — historical only |
| Red zone targets | +0.015–0.020 | nfl_data_py PBP, filter `yardline_100 <= 20` | None — historical only |
| Opp WR/TE TD rate allowed | +0.015–0.020 | Derivable from existing game_logs CSVs | None — already have the data |

**Vegas team totals were considered and rejected.** They'd add similar signal but create a real-time API dependency — if the line isn't posted or the feed is down, predictions break. Opponent defensive TD rate against WR/TE captures the same game-script information from data we already have, with no external call required at prediction time.

---

## Next Steps — In Order

### Step 1 — Fix Training Split (Do First, Before Any Data Fetch)
**One notebook change, ~5 minutes.**

In `04_model_training.ipynb`, replace:
```python
eval_mask = train_df['season'] == 2024
```
with:
```python
eval_mask = (train_df['season'] == 2024) & (train_df['week'] >= 14)
```

Retrain and record the new holdout AUC. This is the baseline to beat before adding features. Estimated gain: +0.010–0.015 AUC.

---

### Step 2 — Fetch New Features (New Notebook: `05_new_features.ipynb`)

**Install:** `pip install nfl_data_py`

No API key needed. All data pulls from nflfastR / Pro Football Reference automatically.

#### Feature A — Opponent WR/TE TD Rate Allowed
*Derivable from existing data — do this first, no new fetch needed.*

For each row in `game_logs_enriched.csv`, we know `team` and `game_id`. Derive the opponent team from the game_id format (`YYYYMMDD_AWAY@HOME`). Then aggregate rolling defensive TD rates:

```python
# From game_logs_enriched.csv (already have this)
# For each game, the opponent is the other team in the game_id

def get_opponent(row):
    parts = row['game_id'].split('_')[1].split('@')
    away, home = parts[0], parts[1]
    return home if row['team'] == away else away

df['opponent'] = df.apply(get_opponent, axis=1)

# Compute rolling WR/TE TDs allowed per team per week
# Then lag-shift and join back as opp_wr_te_td_allowed_pg
# and opp_wr_te_targets_allowed_pg
```

This is the same rolling/lag pattern as all existing features. No leakage risk if shifted correctly.

#### Feature B — Snap Count %
```python
import nfl_data_py as nfl

snaps = nfl.import_snap_counts([2022, 2023, 2024, 2025])
# Returns: player, pfr_player_id, season, week, game_id,
#          position, team, offense_snaps, offense_pct
# Filter to WR/TE, keep offense_pct as snap_pct feature
```

**ID join challenge:** Tank01 uses ESPN player IDs. nflverse uses GSIS IDs. Bridge via:
```python
ids = nfl.import_ids()
# Has columns: gsis_id, espn_id, pfr_id, name, etc.
# Join snap counts to game_logs on (name + team + week + season) as fallback
# if ESPN→GSIS crosswalk is incomplete
```

Name+team+week matching is messy but workable. Fuzzy match on player name if needed.

Rolling features to engineer from snap_pct (same lag pattern as targets):
- `lag_snap_pct` — previous game snap %
- `roll3_snap_pct` — rolling 3-game average snap %
- `season_snap_pct` — cumulative season snap %

#### Feature C — Red Zone Targets
```python
pbp = nfl.import_pbp_data([2022, 2023, 2024, 2025])

rz_targets = (
    pbp[
        (pbp['play_type'] == 'pass') &
        (pbp['yardline_100'] <= 20) &
        (pbp['receiver_player_id'].notna())
    ]
    .groupby(['receiver_player_id', 'season', 'week'])
    .agg(
        rz_targets=('receiver_player_id', 'count'),
        rz_tds=('touchdown', 'sum')
    )
    .reset_index()
)
```

PBP uses GSIS IDs — needs the same crosswalk as snap counts.

Rolling features to engineer:
- `roll3_rz_targets` — rolling 3-game red zone target count
- `rz_target_share` — player RZ targets / team RZ targets (same lag as existing target_share)
- `rz_td_rate` — rolling RZ TD rate (with EB shrinkage — same approach as td_rate_eb)

---

### Step 3 — Retrain Once With Full Improved Dataset

Do not retrain incrementally between Step 1 and Step 2. The right sequence is:

1. Fix split → quick retrain → record baseline AUC
2. Fetch + engineer all three new features
3. Retrain once with full feature set
4. Re-run calibration (Beta calibration on 2024 eval set, evaluate on 2025)
5. Run sportsbook comparison test

Only retrain the model when all features are ready. Retraining twice makes it impossible to attribute what moved the needle.

**Realistic expectation:** AUC 0.690–0.710 after all three features added. That's above v1 WR-only (0.695) on a harder problem (WR+TE, newer holdout year). Calibration max deviation should drop from 0.17 toward 0.08–0.10 — still not perfect but usable.

---

## The Honest Performance Ceiling

If AUC is still under 0.700 after all of the above, the system is at the ceiling of what public receiving + snap + red zone stats can predict. This is not a failure — it reflects the genuine randomness of TD scoring.

**At 0.70 AUC, well-calibrated, the system is still useful for the intended purpose** (ATTD prop comparison against sportsbooks) because:
- The ranking signal is real — top predictions are consistently the right players
- Calibrated probabilities at 0.70 AUC beat naive approaches to ATTD odds significantly
- The edge test (dual logistic regression: model_logit + book_logit predicting scored_td) tells you whether the model adds information *beyond what the book already knows* — that's the real viability question, not raw AUC

If the edge test shows model coefficient ≈ 0, the system has no exploitable edge regardless of AUC. Run that test before doing any further model work.

---

## Data Sources Summary

| Data | Source | Cost | API Key | Prediction-time needed |
|---|---|---|---|---|
| Box scores (existing) | Tank01 RapidAPI | Paid | Yes | Yes (current week) |
| Snap counts | nfl_data_py | Free | No | No |
| Red zone targets | nfl_data_py PBP | Free | No | No |
| Opponent def rates | Existing game_logs CSVs | Free | No | No |
| ATTD odds | Sportsbook API (existing) | Paid | Yes | Yes (for comparison) |

**Tank01 does not have snap counts, red zone breakdowns, or route participation.** It's box score only. All the missing features come from nfl_data_py / nflverse.

---

## What NOT To Do

- **Don't add Vegas team totals** — creates real-time API dependency that breaks predictions when lines aren't posted. Opponent defensive rate achieves the same thing from data you already have.
- **Don't retrain to chase AUC on training data** — v1's 95.8% in-sample / 69.5% holdout gap shows exactly what this looks like. The model already has appropriate regularization.
- **Don't evaluate on accuracy** — with 80/20 class imbalance, accuracy is meaningless. Log-loss and Brier score only.
- **Don't separate WR and TE models yet** — test unified model with `is_te` feature first. Only split if `is_te` feature importance > 10% and per-position AUC is meaningfully better.
- **Don't use `weeks_since_td` as a feature** — encodes the gambler's fallacy. Data confirms non-monotonic, noisy relationship. Remove it and keep it out.

---

## Files Created During This Session

| File | Purpose |
|---|---|
| `ml/feature_prep.py` | EB shrinkage + feature matrix builder |
| `ml/train.py` | LR baseline + XGBoost with monotone constraints |
| `ml/calibrate.py` | Temperature scaling + Beta calibration + reliability plots |
| `ml/evaluate.py` | Holdout metrics + sportsbook comparison |
| `ml/utils.py` | `american_to_implied_prob`, `prob_to_american`, `reliability_diagram` |
| `ml/model/wr_te_model_v2.pkl` | Saved model bundle |
| `ml/model/reliability_diagrams.png` | Calibration diagnostic plots |
| `ml/04_model_training.ipynb` | Full training pipeline notebook |
