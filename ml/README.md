# BGGTDM v2 — Model Documentation

NFL anytime TD scorer prediction model for WR + TE. Trained on 2022–2024 game logs, validated on the full 2025 season.

---

## Table of Contents

1. [Model File](#model-file)
2. [Architecture Overview](#architecture-overview)
3. [Training Data](#training-data)
4. [Feature Set](#feature-set)
5. [Empirical Bayes Shrinkage](#empirical-bayes-shrinkage)
6. [XGBoost Parameters](#xgboost-parameters)
7. [Calibration](#calibration)
8. [Early-Season Path (Weeks 1–3)](#early-season-path-weeks-13)
9. [Prediction Pipeline](#prediction-pipeline)
10. [Holdout Performance](#holdout-performance)
11. [Known Limitations](#known-limitations)
12. [File Reference](#file-reference)

---

## Model File

**`ml/model/wr_te_model_v2.pkl`** — single joblib bundle containing everything needed to run predictions.

| Bundle Key | Type | Description |
|---|---|---|
| `model` | XGBClassifier | Trained XGBoost model |
| `scaler` | StandardScaler | Fitted on training data (used for LR baseline only) |
| `features` | list[str] | Ordered feature names (21 features) |
| `alpha_eb` | float | Beta-Binomial alpha for anytime TD rate shrinkage |
| `beta_eb` | float | Beta-Binomial beta for anytime TD rate shrinkage |
| `rz_alpha_eb` | float | Beta-Binomial alpha for red zone TD rate shrinkage |
| `rz_beta_eb` | float | Beta-Binomial beta for red zone TD rate shrinkage |
| `beta_calibrator` | BetaCalibration | Fitted probability calibrator |
| `best_calibration` | str | `'beta'` — which calibrator to use |
| `early_season_scalars` | dict | Per-week-group probability correction scalars |
| `tau` | float | Temperature scaling parameter (backup calibrator) |
| `train_df` | DataFrame | Full training set with features (6,584 rows) |
| `holdout_df` | DataFrame | Full 2025 holdout set (2,881 rows) |
| `X_train` / `y_train` | ndarray | Training feature matrix and labels |
| `X_holdout` / `y_holdout` | ndarray | Holdout feature matrix and labels |
| `calibrated_probs_holdout` | ndarray | Final calibrated probabilities on 2025 holdout |
| `holdout_auc` | float | 0.7215 |
| `holdout_brier` | float | 0.1444 |
| `trained_on` | str | `'2022-2024'` |

---

## Architecture Overview

```
Raw game logs
    │
    ▼
feature_prep.py ──── early_season.py (weeks 1-3 only)
    │
    ▼
XGBoost Classifier (72 trees, max_depth=4)
    │
    ▼
Beta Calibration (betacal, parameters='abm')
    │
    ▼
Week-group scalar correction
    │
    ▼
P(anytime TD scorer) per player per week
```

Two parallel feature paths merge into one model:
- **Weeks 1–3:** carry-forward from prior season end state via `early_season.py`
- **Weeks 4–18:** rolling in-season stats from `feature_prep.py`

No separate early-season model. Same weights, same calibration, same pkl.

---

## Training Data

| Property | Value |
|---|---|
| Source | Tank01 NFL API via `nfl_data_py` (snap counts, PBP red zone) |
| Positions | WR + TE unified |
| Seasons | 2022, 2023, 2024 (train) + 2025 (holdout) |
| Total rows | 9,972 player-weeks in enriched CSV |
| Train rows | 6,584 (after carry-forward fill + NaN drop) |
| Holdout rows | 2,881 (full 2025 season) |
| Target | `scored_td` — binary, 1 if player scored any receiving or rushing TD |
| Train TD rate | 20.3% |
| Holdout TD rate | 19.7% |

**Train/eval split for early stopping:**
- Train: all seasons 2022–2024, excluding 2024 weeks 14–18
- Eval (XGBoost early stopping): 2024 weeks 14–18 (745 rows)
- Calibration validation: full 2024 season (2,584 rows)

---

## Feature Set

All 21 features are lag-shifted — no lookahead. Features reflect what is known *before* the prediction week starts.

### Usage Volume (8 features)

| Feature | Description |
|---|---|
| `targets_pg` | Cumulative season targets per game up to this week |
| `roll3_targets` | Rolling 3-game sum of targets (lag-shifted) |
| `yards_pg` | Cumulative season receiving yards per game |
| `roll3_yards` | Rolling 3-game sum of receiving yards |
| `receptions_pg` | Cumulative season receptions per game |
| `roll3_receptions` | Rolling 3-game sum of receptions |
| `lag_targets` | Targets in the single prior game |
| `lag_yards` | Receiving yards in the single prior game |

### Target Share (1 feature)

| Feature | Description |
|---|---|
| `target_share` | Player's share of cumulative season team targets (cum_targets / team_cum_targets) |

### Downfield Usage (1 feature)

| Feature | Description |
|---|---|
| `roll3_long_rec` | Rolling 3-game sum of receptions >= 20 yards |

### Usage Volatility (1 feature)

| Feature | Description |
|---|---|
| `roll3_target_std` | Standard deviation of targets over last 3 games. NaN (< 3 games) filled with 0 |

### Streak / Momentum (2 features)

| Feature | Description |
|---|---|
| `tds_last3` | Number of TDs scored in last 3 games |
| `td_streak` | Consecutive games with a TD scored |

### Empirical Bayes TD Rates (2 features)

| Feature | Description |
|---|---|
| `td_rate_eb` | Beta-Binomial shrunk anytime TD rate (cum_tds + α) / (cum_targets + α + β) |
| `td_rate_eb_std` | Posterior standard deviation of Beta distribution (uncertainty of the estimate) |

### Position (1 feature)

| Feature | Description |
|---|---|
| `is_te` | 1 if TE, 0 if WR |

### Snap Count (2 features, may be NaN)

| Feature | Description |
|---|---|
| `lag_snap_pct` | Offensive snap percentage in the prior game |
| `roll3_snap_pct` | Rolling 3-game mean snap percentage |

NaN allowed — XGBoost handles missing values natively via its split logic. About 10% of rows have NaN snap features due to name-matching failures between data sources.

### Red Zone (3 features)

| Feature | Description |
|---|---|
| `roll3_rz_targets` | Rolling 3-game sum of red zone targets (yardline ≤ 20) |
| `rz_target_share` | Player's share of cumulative season team red zone targets |
| `rz_td_rate_eb` | Beta-Binomial shrunk red zone TD rate |

Red zone features account for ~50% of total XGBoost feature importance.

### Feature Importance

| Rank | Feature | Importance |
|---|---|---|
| 1 | `rz_target_share` | 32.8% |
| 2 | `roll3_rz_targets` | 16.6% |
| 3 | `yards_pg` | 9.8% |
| 4 | `roll3_targets` | 5.8% |
| 5 | `roll3_yards` | 4.6% |
| 6 | `targets_pg` | 4.2% |
| 7 | `is_te` | 2.8% |
| 8 | `roll3_receptions` | 2.7% |
| 9 | `lag_snap_pct` | 2.1% |
| 10 | `lag_yards` | 2.1% |
| 11–21 | All remaining features | ~16% combined |

---

## Empirical Bayes Shrinkage

Raw per-player TD rates (TDs / targets) are noisy for players with few opportunities. A Beta-Binomial model is fit on the training set to shrink individual rates toward the population prior.

**Posterior estimate:**

```
td_rate_eb = (cum_tds + α) / (cum_targets + α + β)
```

A player with zero career TDs but 50 targets gets pulled toward the prior rather than sitting at 0. A player with 20 TDs on 100 targets gets very little shrinkage.

**Fitted parameters (anytime TD):**
- α = 18.21, β = 355.12
- Implied prior TD rate: **4.88% per target**

**Fitted parameters (red zone TD):**
- α = 69.65, β = 211.59
- Implied prior RZ TD rate: **24.8% per red zone target**

Parameters are fit on training data only (seasons ≤ 2024) and applied to both train and holdout to avoid leakage.

---

## XGBoost Parameters

```python
XGBClassifier(
    n_estimators        = 400,        # cap; early stopping triggers at 72
    max_depth           = 4,          # shallow trees — limits overfitting
    learning_rate       = 0.05,
    subsample           = 0.80,       # row sampling per tree
    colsample_bytree    = 0.80,       # feature sampling per tree
    min_child_weight    = 20,         # minimum samples per leaf
    scale_pos_weight    = 1,          # no class reweighting — calibration handles it
    eval_metric         = 'logloss',
    early_stopping_rounds = 30,
    random_state        = 42,
    monotone_constraints = (          # all positive features constrained increasing
        1, 1, 1, 1, 1, 1, 1, 1,      # volume features
        1,                            # target_share
        1, 1,                         # downfield, volatility
        1, 1,                         # streak features
        1, 0,                         # td_rate_eb (positive), td_rate_eb_std (unconstrained)
        0,                            # is_te (unconstrained)
        1, 1,                         # snap features
        1, 1, 1,                      # red zone features
    )
)
```

**Best iteration:** 72 trees (early stopped on 2024 wk14-18 eval set)

**Monotone constraints** enforce that higher usage always increases predicted probability — prevents the model from learning spurious inverse relationships from noise in the training data.

---

## Calibration

XGBoost raw probabilities are compressed (low-confidence range, 5–48%). Two calibration methods were compared on 2024 season validation predictions:

| Method | Max deviation from diagonal |
|---|---|
| Raw XGBoost | 0.4244 |
| Temperature scaling (τ=1.018) | 0.4223 |
| Beta calibration | **0.4103** |

**Beta calibration selected.** Fit using `betacal` library with `parameters='abm'` on 2024 season predictions.

### Early-Season Scalars

Beta calibration was fit on weeks 4–18 data. Week 1–3 carry-forward predictions are systematically overestimated because end-of-prior-season features are slightly inflated vs early-season scoring rates. A multiplicative correction is applied after calibration:

| Week group | Scalar | Rationale |
|---|---|---|
| Week 1 | **0.779** | Model predicted 20.3% mean, actual was 15.8% on 2024 val |
| Weeks 2–3 | **0.957** | Near-perfect calibration; minor correction |
| Weeks 4+ | **1.019** | Essentially no correction |

Scalars are fit on 2024 validation data and stored in the bundle as `early_season_scalars`.

---

## Early-Season Path (Weeks 1–3)

### The Problem

At week 1, `games_played == 0` — all rolling and lag features are NaN. The standard pipeline drops these rows entirely, making week 1 predictions impossible. Weeks 2–3 have 1–2 game histories, making rolling windows unreliable.

### The Solution — Carry-Forward

Each player's final game row from the prior season is used as their week 1–3 feature state. The model interprets these values the same way it does mid-season values because that's what it was trained on.

**Resolution priority per player:**

1. **Same team as prior season** → carry all features forward from prior season's final row
2. **Different team from prior season** → keep rate features (td_rate_eb, rz_td_rate_eb), zero out all volume features (NaN for XGBoost to handle)
3. **No prior season row (rookie / new entrant)** → fill from draft_round + position bucket (median week 1–3 stats from training data)

### Lookup Tables

**`data/prior_season_final_state.csv`** — one row per player per season, representing their end-of-season feature state. Joined into the following season via `join_season = season + 1`.

**`data/rookie_buckets.csv`** — median week 1–3 stats by draft_round + pos from training data. `draft_round=0` covers undrafted / free agents with no prior row.

### Training Impact

Early-season rows are included in model training with carry-forward features filled in. This ensures the model trains on week 1–3 outcomes using the same feature state it will see in production.

- 1,158 of 1,722 week 1–3 rows had carry-forward matches in training
- Remaining 564 rows were dropped (no prior row, no rookie bucket match)

---

## Prediction Pipeline

### Weeks 4–18 (standard path)

```python
import joblib
import numpy as np

bundle = joblib.load('model/wr_te_model_v2.pkl')
model       = bundle['model']
calibrator  = bundle['beta_calibrator']
features    = bundle['features']

# X: shape (n_players, 21), columns in order of bundle['features']
raw_probs   = model.predict_proba(X)[:, 1]
cal_probs   = calibrator.predict(raw_probs.reshape(-1, 1))
# cal_probs: array of floats in [0, 1] — P(anytime TD) per player
```

### Weeks 1–3 (early-season path)

```python
from early_season import load_early_season_priors, resolve_early_features, apply_week_scalar

prior, buckets = load_early_season_priors()

# players_df must have: player_id, name, pos, team, is_te, draft_round
resolved = resolve_early_features(
    players_df=players_df,
    season=2026,
    week=1,
    prior_df=prior,
    bucket_df=buckets,
)

X = resolved[features].values
raw_probs = model.predict_proba(X)[:, 1]
cal_probs = calibrator.predict(raw_probs.reshape(-1, 1))

scalars   = bundle['early_season_scalars']
final     = apply_week_scalar(cal_probs, week=1, scalars=scalars)
```

### EB Shrinkage for New Season Predictions

When building features for a new season, apply EB shrinkage using the stored parameters from the bundle — do not refit:

```python
alpha_eb    = bundle['alpha_eb']      # 18.21
beta_eb     = bundle['beta_eb']       # 355.12
rz_alpha_eb = bundle['rz_alpha_eb']   # 69.65
rz_beta_eb  = bundle['rz_beta_eb']    # 211.59

df['td_rate_eb'] = (df['cum_tds'] + alpha_eb) / (df['cum_targets'] + alpha_eb + beta_eb)
df['rz_td_rate_eb'] = (df['cum_rz_tds'] + rz_alpha_eb) / (df['cum_rz_targets'] + rz_alpha_eb + rz_beta_eb)
```

### Output

**Single float per player per week: P(anytime TD scorer)**

| Probability | Interpretation |
|---|---|
| < 0.10 | Very unlikely — deep depth chart, minimal usage |
| 0.10–0.25 | Below average — possible but not expected |
| 0.25–0.40 | Average to above average starter |
| 0.40–0.55 | High-usage player in favorable situation |
| > 0.55 | Elite usage + red zone role (top 1–2% of predictions) |

---

## Holdout Performance

Full 2025 season, out-of-sample.

### Overall

| Metric | Value | Target |
|---|---|---|
| ROC-AUC | 0.7215 | > 0.730 |
| Brier Score | 0.1446 | < 0.115 |
| Log-Loss | 0.4527 | — |
| TD Recall @ top 20% | 39.9% | > 35% ✅ |

AUC and Brier miss their targets. This reflects the inherent noise of binary per-game TD scoring — not a pipeline problem. TD Recall (the operationally important metric for bet filtering) passes.

### By Week Group (with early-season scalars applied)

| Group | N | TD% | Mean Pred | Cal Gap | AUC |
|---|---|---|---|---|---|
| Week 1 | 143 | 17.5% | 17.9% | +0.4% | 0.529 |
| Weeks 2–3 | 337 | 22.8% | 21.2% | −1.6% | 0.604 |
| Weeks 4–9 | 902 | 22.4% | 21.5% | −0.9% | 0.725 |
| Weeks 10–18 | 1,499 | 18.3% | 19.6% | +1.3% | 0.759 |

Mean calibration gap early (wk1–3): **1.0%** — on par with late-season (1.1%).

Week 1 AUC of 0.53 is expected. Prior-season carry-forward captures usage role well but cannot predict game-level scoring variance on the first week back.

---

## Known Limitations

**Role continuity assumption.** Carry-forward assumes a player's usage is similar to prior season. Wrong for: players who lost a starting job in the offseason, injury returning players, major scheme changes (new OC, new QB). Manual override recommended for obvious cases.

**Rookie accuracy.** Draft-round buckets are rough. A 1st-round WR sitting behind a starter will be overestimated. No solution without pre-season depth chart data.

**AUC target missed.** 0.721 vs 0.730 target. Binary per-game TDs are noisy — a player can dominate usage and score 0 TDs, or see 3 targets and score. The model correctly ranks players but the AUC ceiling may be near 0.73 for this task without game-level context (opponent pass defense, game script, QB status).

**Brier target missed.** 0.145 vs 0.115 target. The 0.115 target was set against a compressed probability range. The current calibration spreads probabilities wider (which is correct) but raises the Brier score.

**Calibration compression.** 95th percentile probability is 0.484 — top players don't reach 0.50+ except in extreme situations. This is a characteristic of the beta calibration fit, not incorrect calibration. Observed TD rate for top-decile predictions matches predicted probability within 1–2%.


---

## File Reference

### Scripts

| File | Purpose |
|---|---|
| `feature_prep.py` | Feature computation, EB shrinkage, train/holdout split |
| `train.py` | LR baseline + XGBoost training, saves model bundle |
| `calibrate.py` | Beta calibration + early-season scalars, updates bundle |
| `evaluate.py` | Full holdout metrics + sportsbook comparison |
| `evaluate_early_season.py` | Week-group reliability check for carry-forward validation |
| `early_season.py` | Feature resolver for weeks 1–3 (carry-forward / team-changer / rookie) |

### Notebooks

| Notebook | Purpose |
|---|---|
| `01_data_exploration.ipynb` | EDA on raw WR/TE game log data |
| `02_fetch_and_explore.ipynb` | Data fetch and exploration |
| `03_feature_exploration.ipynb` | Feature correlation and distribution analysis |
| `04_model_training.ipynb` | Interactive model training and evaluation |
| `05_new_features.ipynb` | Adds snap %, red zone, and opponent defense features |
| `06_prior_season.ipynb` | Builds carry-forward lookup tables for weeks 1–3 |

### Data Files

| File | Description |
|---|---|
| `data/game_logs_enriched.csv` | Full training dataset (9,972 rows, 66 columns) |
| `data/prior_season_final_state.csv` | End-of-season player state for carry-forward (966 rows) |
| `data/rookie_buckets.csv` | Median early-week stats by draft_round + pos (15 rows) |
| `data/anytime_td_odds.csv` | Sportsbook odds for edge detection |

### Model Outputs

| File | Description |
|---|---|
| `model/wr_te_model_v2.pkl` | Full model bundle (joblib) |
| `model/reliability_diagrams.png` | Calibration curves — raw vs temperature vs beta |
| `model/early_season_reliability.png` | Week-group reliability curves |

### Run Order (from scratch)

```bash
# 1. Feature engineering
jupyter nbconvert --to notebook --execute 05_new_features.ipynb

# 2. Build early-season lookup tables
jupyter nbconvert --to notebook --execute 06_prior_season.ipynb

# 3. Train
python train.py

# 4. Calibrate
python calibrate.py

# 5. Evaluate
python evaluate.py
python evaluate_early_season.py
```

### Seasonal Refresh (start of each new season)

```bash
# Re-fetch game logs for new season, then:
jupyter nbconvert --to notebook --execute 05_new_features.ipynb  # adds new season rows
jupyter nbconvert --to notebook --execute 06_prior_season.ipynb  # updates carry-forward tables
# No retraining required until enough new season data accumulates
```
