# BGGTDM v2 — Model Training Setup
*Instructions for Claude Code*

---

## Context

Building a TD prediction model for NFL WR + TE players. The goal is to produce **calibrated probabilities** that convert to American odds and can be compared against sportsbook ATTD (Anytime Touchdown) lines to find edges.

The number has to be right, not just the ranking. A model that says everyone is 5–25% is useless because sportsbooks price elite players at +120 to +160 (~38–45% implied). The entire value of the system is in calibration.

---

## Current State

All data fetching and feature engineering is done. The following files exist in `ml/data/`:

| File | Description |
|---|---|
| `game_logs_features.csv` | 9,972 rows, WR + TE, 2022–2025, basic rolling features |
| `game_logs_enriched.csv` | Same + efficiency, streak, consistency, target share features (57 columns) |
| `game_logs_2022.csv` through `game_logs_2025.csv` | Raw per-season game logs |
| `player_lookup.json` | Player ID → name, pos, team, exp |
| `wrGameLog.csv` | Original WR-only 2022–2024 data (legacy, ignore) |
| `anytime_td_odds.csv` | Historical sportsbook ATTD odds (use for calibration evaluation) |

**Training set:** seasons 2022–2024, `games_played >= 1` (in-season rows only) — ~6,300 rows  
**Holdout set:** season 2025, all weeks — ~3,000 rows  
**Target variable:** `scored_td` (binary: 1 if `rec_tds > 0`)  
**Class imbalance:** ~20% positive rate (16.6% TE, 21.8% WR)

---

## Known Problems from v1 — Do Not Repeat

- `class_weight='balanced'` was missing → model almost never predicted a TD
- No depth/leaf constraints → 95.8% in-sample AUC, 69.5% on holdout (pure overfit)
- WR-only training → TE predictions structurally wrong
- Probabilities compressed to 5–25% range → useless for odds comparison
- Evaluated on accuracy, not log-loss/Brier → misleading metrics throughout

---

## What to Build

### Step 1 — Empirical Bayes Shrinkage on `td_rate_per_target`

The raw `td_rate_per_target` feature has near-zero correlation with TD outcomes because it's computed from small samples (a player with 20 targets has a wildly noisy rate estimate). Fix this with Beta-Binomial shrinkage before any model training.

**Task:** Create `ml/feature_prep.py` with a function `shrink_td_rate(df)` that:

1. Fits Beta-Binomial parameters `(alpha, beta)` on the training set via maximum marginal likelihood:
   ```
   maximize: sum_i log BetaBinomial(cum_tds_i; cum_targets_i, alpha, beta)
   ```
   Use `scipy.optimize.minimize` with `scipy.stats.betabinom.logpmf`. Per-player cumulative totals at each row's point in time (no leakage — `cum_tds` and `cum_targets` are already lag-shifted in the enriched CSV).

2. Computes the posterior mean for each row:
   ```
   td_rate_eb = (cum_tds + alpha) / (cum_targets + alpha + beta)
   ```

3. Also adds `td_rate_eb_std = sqrt(posterior variance)` as a second feature (uncertainty itself is signal — high std means unpredictable player).

4. Fits `(alpha, beta)` on training rows only, then applies the same parameters to holdout.

Replace `td_rate_per_target` in the feature set with `td_rate_eb` and `td_rate_eb_std`.

---

### Step 2 — Final Feature Set

Build `ml/feature_prep.py` to load `game_logs_enriched.csv` and produce clean train/holdout matrices.

**In-season features to use** (all are already lag-shifted, no leakage):

```python
FEATURES = [
    # Usage volume (strongest signals, r ~0.17–0.21)
    'targets_pg',
    'roll3_targets',
    'yards_pg',
    'receptions_pg',
    'roll3_yards',
    'roll3_receptions',
    'lag_targets',
    'lag_yards',

    # Target share (r ~0.175 — better than rolling share)
    'target_share',          # cumulative season target share within team

    # Downfield usage (r ~0.143)
    'roll3_long_rec',

    # Usage volatility (r ~0.141 — counterintuitive but real)
    'roll3_target_std',

    # Streak / momentum (r ~0.084–0.132)
    'tds_last3',
    'td_streak',

    # EB shrinkage TD rate (replaces td_rate_per_target)
    'td_rate_eb',
    'td_rate_eb_std',

    # Context
    'is_te',
    'is_home',
    'week',
]
```

**Drop from consideration:**
- `catch_rate` variants (r < 0.01 — no signal)
- `target_cv` (r = -0.023, noisy)
- `season_ypt`, `lag_ypt` (r < 0.04, dominated by yards features)
- `td_rate_per_target` (replaced by EB version)
- `weeks_since_td` (non-monotonic, misleading — the gambler's fallacy feature)
- `target_trend` (r = 0.026, too weak)
- `height_in` (no data coverage)

**Filter rows:**
```python
train = df[(df['season'] <= 2024) & (df['games_played'] >= 1)]
holdout = df[df['season'] == 2025]
```

---

### Step 3 — Logistic Regression Baseline

Before XGBoost, fit a regularized logistic regression as the calibration baseline.

**Task:** In `ml/train.py`, fit:
```python
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)

lr = LogisticRegression(
    class_weight='balanced',
    C=0.1,              # L2 regularization — important given ~6k rows
    max_iter=1000,
    random_state=42
)
lr.fit(X_train_scaled, y_train)
```

Evaluate on 2025 holdout. Print: ROC-AUC, Brier score, log-loss, and the probability distribution (percentiles: 10th, 25th, 50th, 75th, 90th, 95th). The 95th percentile should be > 40% if calibration is working.

---

### Step 4 — XGBoost with Monotone Constraints

**Task:** In `ml/train.py`, fit XGBoost with:

```python
import xgboost as xgb

# Monotone constraints: +1 = must increase, -1 = must decrease, 0 = unconstrained
# Order must match FEATURES list exactly
MONOTONE = {
    'targets_pg': 1,
    'roll3_targets': 1,
    'yards_pg': 1,
    'receptions_pg': 1,
    'roll3_yards': 1,
    'roll3_receptions': 1,
    'lag_targets': 1,
    'lag_yards': 1,
    'target_share': 1,
    'roll3_long_rec': 1,
    'roll3_target_std': 1,    # volatile usage → higher TD rate (from data)
    'tds_last3': 1,
    'td_streak': 1,
    'td_rate_eb': 1,
    'td_rate_eb_std': 0,      # unconstrained — uncertainty could go either way
    'is_te': 0,
    'is_home': 0,
    'week': 0,
}
# Build constraint tuple in feature order
constraints = tuple(MONOTONE[f] for f in FEATURES)

model = xgb.XGBClassifier(
    n_estimators=400,
    max_depth=4,               # shallow — prevents overfit on 6k rows
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    min_child_weight=20,       # conservative — needs 20 samples per leaf
    scale_pos_weight=4,        # handles class imbalance (roughly 80/20 split)
    monotone_constraints=constraints,
    eval_metric='logloss',
    early_stopping_rounds=30,
    random_state=42,
)

# Use last season of training as eval set for early stopping
eval_mask = train['season'] == 2024
X_eval, y_eval = X_train[eval_mask], y_train[eval_mask]
X_tr, y_tr = X_train[~eval_mask], y_train[~eval_mask]

model.fit(
    X_tr, y_tr,
    eval_set=[(X_eval, y_eval)],
    verbose=50
)
```

---

### Step 5 — Probability Calibration

This is the most critical step for the sportsbook comparison use case.

**Task:** In `ml/calibrate.py`:

1. **Temperature scaling** — fit a single parameter τ on the 2023 holdout season (not 2025 — save that for final evaluation):
   ```python
   from scipy.optimize import minimize_scalar
   from scipy.special import expit, logit

   raw_logits = logit(model.predict_proba(X_val)[:, 1].clip(1e-6, 1-1e-6))

   def neg_logloss(tau):
       p = expit(raw_logits / tau)
       return log_loss(y_val, p)

   result = minimize_scalar(neg_logloss, bounds=(0.1, 5.0), method='bounded')
   tau = result.x
   ```

2. **Beta calibration** as alternative — fit using `betacal` library (`pip install betacal`):
   ```python
   from betacal import BetaCalibration
   bc = BetaCalibration(parameters='abm')
   bc.fit(raw_probs_val.reshape(-1, 1), y_val)
   ```

3. **Compare both** on 2025 holdout using reliability diagrams (10 equal-width bins, fraction of positives vs mean predicted probability). Pick whichever is flatter.

4. **Reliability diagram function:**
   ```python
   def reliability_diagram(y_true, y_prob, n_bins=10, title=''):
       bins = np.linspace(0, 1, n_bins + 1)
       bin_means, bin_fracs, bin_counts = [], [], []
       for lo, hi in zip(bins[:-1], bins[1:]):
           mask = (y_prob >= lo) & (y_prob < hi)
           if mask.sum() > 0:
               bin_means.append(y_prob[mask].mean())
               bin_fracs.append(y_true[mask].mean())
               bin_counts.append(mask.sum())
       # plot bin_means (x) vs bin_fracs (y) — perfect calibration = diagonal
   ```

---

### Step 6 — Sportsbook Comparison Evaluation

**Task:** In `ml/evaluate.py`, load `data/anytime_td_odds.csv` and:

1. Parse sportsbook American odds to implied probability:
   ```python
   def american_to_implied_prob(odds):
       """Remove vig and convert to true implied probability."""
       if odds > 0:
           raw = 100 / (odds + 100)
       else:
           raw = abs(odds) / (abs(odds) + 100)
       # Approximate vig removal (assume ~5% book margin)
       return raw / 1.05
   ```

2. For each player-week in 2025 holdout where sportsbook odds exist, compute:
   - `model_prob` — calibrated XGBoost probability
   - `book_prob` — vig-adjusted implied probability from sportsbook
   - `edge` = `model_prob - book_prob`
   - `model_american` — convert model_prob to American odds

3. **Edge detection output table** (sort by edge descending):
   ```
   Player | Week | Model P | Book P | Edge | Model Odds | Book Odds
   ```

4. **Calibration test against book:** Fit a logistic regression with `model_logit` and `book_logit` as inputs, `scored_td` as target, on 2025 holdout:
   ```python
   from sklearn.linear_model import LogisticRegression
   X_cal = np.column_stack([
       logit(model_probs.clip(1e-6, 1-1e-6)),
       logit(book_probs.clip(1e-6, 1-1e-6))
   ])
   lr_test = LogisticRegression(C=1e6).fit(X_cal, y_2025)
   print("Model coefficient:", lr_test.coef_[0][0])
   print("Book coefficient:", lr_test.coef_[0][1])
   ```
   If model coefficient ≈ 0 and book coefficient >> 0, the model adds no information beyond the sportsbook. If both are positive, there's independent signal.

---

### Step 7 — Save Artifacts

**Task:** In `ml/train.py`, save:

```python
import joblib

joblib.dump({
    'model': xgb_calibrated,
    'scaler': scaler,              # if used
    'features': FEATURES,
    'tau': tau,                    # temperature scaling parameter
    'alpha_eb': alpha,             # EB shrinkage params
    'beta_eb': beta,
    'trained_on': '2022-2024',
    'holdout_auc': holdout_auc,
    'holdout_brier': holdout_brier,
}, 'model/wr_te_model_v2.pkl')
```

---

## File Structure to Create

```
ml/
├── feature_prep.py          # EB shrinkage + final feature matrix builder
├── train.py                 # LR baseline + XGBoost training
├── calibrate.py             # Temperature scaling + Beta calibration + reliability plots
├── evaluate.py              # Holdout metrics + sportsbook comparison
├── utils.py                 # american_to_prob, prob_to_american, reliability_diagram
└── model/
    └── wr_te_model_v2.pkl   # Final saved model bundle
```

---

## Evaluation Targets (Minimum Viable)

| Metric | v1 Actual | v2 Target |
|---|---|---|
| Holdout ROC-AUC | 0.695 | > 0.730 |
| Holdout Brier Score | 0.133 | < 0.115 |
| 95th percentile predicted prob | ~0.43 | > 0.50 |
| TD recall at top-20% predicted | ~15% | > 35% |
| Reliability diagram max deviation | unknown | < 0.05 |

If ROC-AUC < 0.700 after all fixes, stop and investigate — something is wrong with feature leakage or the data split.

---

## Notes

- **No leakage check:** all features in `game_logs_enriched.csv` are already lag-shifted (computed from data before the prediction week). Verify by checking that `games_played >= 1` filter removes week 1 rows where rolling features would be NaN.
- **WR vs TE:** train a single unified model with `is_te` as a feature first. If feature importance for `is_te` is > 10%, consider separate models.
- **Do not use `weeks_since_td`** as a feature — it encodes the gambler's fallacy and the data confirms it's non-monotonic and noisy.
- **Training metric must be log-loss** — accuracy is meaningless given class imbalance and will produce a model that never predicts TDs.
- The `.pkl` bundle is what `model_service.py` in the backend loads. Keep the interface identical to v1: input is a dict of feature values, output is a single float probability.
