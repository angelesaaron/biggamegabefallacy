# ML Model Evaluation Report
*Big Game Gabe Fallacy — Random Forest TD Prediction Model*
*Evaluated: March 2026 | Based on full analysis of training data and notebook*

---

## What the Model Actually Is

| Attribute | Value |
|-----------|-------|
| **Algorithm** | `RandomForestClassifier()` — all sklearn defaults (100 trees, unlimited depth) |
| **Training data** | `wrGameLog.csv` — 5,329 game-weeks, 219 unique WRs, seasons 2022–2024 |
| **Positions trained on** | **WR only** |
| **Target variable** | Binary: did player score any TD in that game (1) or not (0) |
| **Cross-validation** | `TimeSeriesSplit(n_splits=3)` |
| **sklearn version** | 1.5.1 |

The training data **does still exist** at `BGGDP/wrGameLog.csv` — so retraining is fully possible.

---

## The Core Problem: Class Imbalance

This is the most important number in the entire evaluation:

| Class | Count | Rate |
|-------|-------|------|
| No TD (0) | 4,435 | **83.2%** |
| TD (1) | 894 | **16.8%** |

A model that **always predicts "no TD"** would achieve **83.2% accuracy** while being completely useless. This is why the notebook's reported accuracy of 82–84% is misleading — the model is barely beating a coin flip in a meaningful sense.

---

## Real Performance Metrics

### In-Sample (What the Notebook Reported)
The notebook evaluated on the same data it trained on — this is the classic overfitting trap:

| Metric | Value |
|--------|-------|
| Accuracy | 95.8% |
| ROC-AUC | 0.959 |
| Brier Score | 0.047 |

These numbers are **inflated by overfitting**. The model memorized the training data.

### Proper Holdout Test (Train 2022–2023, Test 2024)
This is what the model actually performs like on new data:

| Metric | Value | Interpretation |
|--------|-------|----------------|
| Accuracy | 82.2% | Same as "always predict no TD" |
| **ROC-AUC** | **0.695** | Modest signal — 0.5 = random, 1.0 = perfect |
| Brier Score | 0.133 | Mediocre probability calibration |
| R² | -0.263 | Negative — worse than predicting the mean |

### Confusion Matrix (2024 holdout)
```
                Predicted No-TD   Predicted TD
Actual No-TD         658              12
Actual TD            131               3
```

Of 134 actual TDs in 2024 test data:
- Model correctly identified **3** (2.2% recall)
- Missed **131** (97.8% of all actual TDs)

At the default 50% threshold, the model almost **never predicts a TD**. This explains the behavior you've been seeing in the app — the model produces probabilities but rarely crosses the threshold that would feel like a meaningful prediction.

---

## Probability Distribution Problem

| Percentile | Production Model |
|------------|-----------------|
| 25th | 0.05 |
| Median | 0.12 |
| 75th | 0.25 |
| 95th | 0.43 |
| Max | 0.64 |

The model's predicted probabilities are **heavily compressed toward zero**. Most players get predicted probabilities of 5–25%, which converts to American odds of +300 to +1900. These are meaningful as relative rankings but are not well-calibrated as actual probabilities. When the app converts these to American odds, it produces numbers that look dramatic but aren't honest probability estimates.

**However — there's something important here:** looking at actual 2024 predictions, the model is correctly identifying the right players at the top of the rankings most of the time. Justin Jefferson, Ja'Marr Chase, CeeDee Lamb, Cooper Kupp — these show up as top predictions in weeks they score. The **ranking signal is real even if the probability values aren't well-calibrated**.

---

## What's Actually Working

The model has genuine discriminative ability. The problem is overfitting and probability miscalibration, not that the features are wrong.

**Feature importance is sensible and consistent:**

| Feature | Importance | Notes |
|---------|-----------|-------|
| `cumulative_yards_per_game` | 13.1% | Season-long usage signal |
| `avg_receiving_yards_last_3` | 11.5% | Recent form |
| `cumulative_targets_per_game` | 11.2% | Opportunity measure |
| `cumulative_receptions_per_game` | 10.5% | Usage confirmation |
| `lag_yds` | 10.3% | Prior game performance |
| `yards_per_reception` | 9.9% | Efficiency proxy |
| `td_rate_per_target` | 9.7% | Career scoring rate |
| `avg_targets_last_3` | 8.8% | Target trend |
| `week` | 7.7% | Season progression |
| `avg_receptions_last_3` | 7.2% | Reception trend |
| `is_first_week` | 0.1% | Near-zero signal |

---

## The TE Problem

The production app predicts both WR and TE players, but **the model was trained exclusively on WR data**. When it evaluates Travis Kelce or Sam LaPorta, it's applying patterns learned from wide receivers. TEs typically:
- Average 5–6 targets/game vs 7–8 for WRs
- Have meaningfully different red-zone usage patterns
- Have higher per-target TD rates than WRs

A TE with 5 targets/game looks like a low-usage, borderline WR to this model. The predictions for TEs are structurally unreliable.

---

## Decision: Retrain or Keep?

### Option A: Keep and Fix (Recommended First Step)
The features are good. The problems are fixable without new data:

1. **Apply `class_weight='balanced'`** — fixes the imbalance problem
2. **Cap `max_depth=8`, `min_samples_leaf=10`** — reduces overfitting
3. **Add probability calibration** (isotonic regression) — makes probabilities honest
4. **Add 3 new features** using existing data:
   - `career_td_rate` — cross-season TD memory (AUC gain: +0.009)
   - `target_trend` — recent targets vs seasonal average
   - `weeks_since_td` — recency of last scoring game

This gives you a retrained model with the **same 11-feature interface** your current production pipeline expects, so no data model changes required. The `.pkl` just gets replaced.

Estimated AUC improvement: **0.695 → 0.733** (measured on 2024 holdout).

### Option B: Retrain with TE Data (Better Long-Term)
Scrape TE game logs for 2022–2024 (same format as `wrGameLog.csv`), add a `position` flag as a feature, and retrain a unified model. This is the right approach for 2026 season launch if you have time.

The feature vector only changes by adding one column (`position` as binary 0/1 or one-hot), which requires a small update to `feature_engineering.py` and the `model_service.py` feature list.

### Option C: Two Separate Models
Train `wr-model.pkl` and `te-model.pkl` independently. Cleanest separation, slightly more maintenance. The model_service.py would need to route by player position.

---

## Recommended Path

**Phase ML-1 (Do now, before anything else):**
Retrain the existing model with fixes applied (Option A). Same features, same pipeline interface, just a better `.pkl`. This is a ~2 hour notebook exercise using the existing `wrGameLog.csv`. Call this `wr-model-v2.pkl`.

**Phase ML-2 (Before 2026 season):**
Scrape TE data, retrain with position flag (Option B). Update `feature_engineering.py` to pass position as a feature. This is the version you deploy for real users.

**Phase ML-3 (Nice to have):**
Add 2025 season data once available. Retrain annually. Consider adding opponent context (facing a defense that gives up 10 TDs/game to WRs vs 2) — this is the biggest missing signal in the current feature set.

---

## What This Means for the App Right Now

The model's **ranking signal is real** — it correctly puts the high-usage, high-opportunity players at the top. The **absolute probability values are not reliable** as betting inputs.

The edge detection (comparing model odds to sportsbook odds) is only as good as the model's probability calibration. Right now, if the model says 40% and the sportsbook implies 25%, you can't trust that 40% number enough to call it an edge with confidence.

After Option A retrain:
- Probabilities will be better calibrated (model saying 30% should actually mean ~30%)
- The edge detection becomes more meaningful
- Predictions will spread more naturally across the full 10–60% range instead of clustering at the low end
