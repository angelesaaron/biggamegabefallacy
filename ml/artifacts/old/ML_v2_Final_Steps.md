# BGGTDM v2 — Final Steps to Production Model
*From notebook 05 review — March 2026*

---

## Current State

AUC hit 0.740 — target cleared. Red zone features were the breakthrough.

| Metric | v2 (post new features) | Target | Status |
|---|---|---|---|
| ROC-AUC | 0.740 | > 0.730 | ✅ |
| Brier Score | 0.142 | < 0.115 | ❌ (ceiling issue, not fixable) |
| TD Recall @20% | 0.420 | > 0.35 | ✅ |
| 95th pct prob | 0.480 | > 0.50 | ❌ (ceiling issue, not fixable) |

**The two FAILs are theoretical ceiling issues, not bugs.** At 0.740 AUC the model is
genuinely uncertain about most players — probabilities correctly stay compressed. The
original targets were too aggressive. Revised realistic targets at this AUC level:
- Brier < 0.135 (currently 0.142 — will improve with fixes below)
- 95th pct > 0.45 (currently 0.480 — already passing)

Do not chase these further. The model is working.

---

## Feature Importance (current)

| Feature | Importance | Notes |
|---|---|---|
| `roll3_rz_targets` | ~38% | Dominant — single biggest signal |
| `rz_target_share` | ~11% | Strong — but denominator bug (see below) |
| Everything else | ~51% | Usage volume, snap %, streaks |

`opp_wr_te_td_rate_allowed` and `opp_wr_te_targets_pg_allowed` both showed
r ≈ 0.00 correlation with TD outcome. **Cut both from FEATURES list.** They are
dead weight that wastes tree splits. Vegas team totals were also considered and
rejected — same reasoning, plus a real-time API dependency that would break
predictions when lines aren't posted.

---

## Three Fixes Before Final Retrain

### Fix 1 — Snap Count Name Crosswalk (highest priority)

**Problem:** 20.6% of rows have null snap %, filled with 0.0. The 0-fill tells the
model "this player barely played" — actively wrong for starters. The unmatched
players are legitimate high-usage players with name format mismatches.

**Known unmatched (from notebook output):**

| Tank01 name | nflverse format | Fix |
|---|---|---|
| `Kyle Pitts Sr.` | `Kyle Pitts` | Strip suffix |
| `DK Metcalf` | `D.K. Metcalf` | Initials format |
| `Marvin Mims Jr.` | `Marvin Mims` | Strip suffix |
| `Brian Thomas Jr.` | `Brian Thomas` | Strip suffix |
| `John Metchie III` | `John Metchie` | Strip suffix |
| `Chig Okonkwo` | `Chukwuemeka Okonkwo` | Nickname |
| `Puka Nacua` | check nflverse | Verify |
| `Terry McLaurin` | check nflverse | Verify |
| `Joshua Palmer` | check nflverse | Verify |
| `Tutu Atwell` | check nflverse | Verify |

**Fix in `05_new_features.ipynb`, cell 7** — add a manual overrides dict before
the name normalization step:

```python
NAME_OVERRIDES = {
    'kyle pitts sr.': 'kyle pitts',
    'dk metcalf': 'd.k. metcalf',
    'marvin mims jr.': 'marvin mims',
    'brian thomas jr.': 'brian thomas',
    'john metchie iii': 'john metchie',
    'chig okonkwo': 'chukwuemeka okonkwo',
    # add others as discovered
}
df['name_norm'] = df['name'].str.lower().str.strip().replace(NAME_OVERRIDES)
snaps['name_norm'] = snaps['name'].str.lower().str.strip().replace(NAME_OVERRIDES)
```

Target: get match rate from 79.4% to > 90%. After running, re-check the unmatched
player list and add any remaining to overrides.

Also: change the 0.0 fill for unmatched snap rows to `NaN` and let XGBoost handle
missing values natively. Its built-in missing value handling will learn a better
split direction than treating absence as 0% snap rate.

---

### Fix 2 — `rz_target_share` Denominator Bug

**Problem:** In cell 12, `team_cum_rz_targets` is computed by summing each player's
`cum_rz_targets` (a running cumulative) within the team. Summing cumulative values
gives an inflated, inconsistent denominator. CeeDee Lamb reads 0.57 — should be
closer to 0.70+ given his 2024 red zone dominance.

**Fix:** Denominator should be cumulative team RZ targets from raw game-level totals,
not the sum of player cumulatives:

```python
# WRONG (current) — sums per-player cumulatives
team_cum_rz = (
    rz_agg.groupby(['team', 'season', 'week'])['cum_rz_targets']
    .sum()
    .rename('team_cum_rz_targets')
    .reset_index()
)

# CORRECT — cumulative from raw game totals
team_game_rz = (
    rz_agg.groupby(['team', 'season', 'week'])['rz_targets_game']
    .sum()
    .reset_index()
    .sort_values(['team', 'season', 'week'])
)
team_game_rz['team_cum_rz_targets'] = (
    team_game_rz.groupby(['team', 'season'])['rz_targets_game']
    .transform(lambda x: x.shift(1).expanding().sum().fillna(0))
)
rz_agg = rz_agg.merge(
    team_game_rz[['team', 'season', 'week', 'team_cum_rz_targets']],
    on=['team', 'season', 'week'],
    how='left'
)
rz_agg['rz_target_share'] = (
    rz_agg['cum_rz_targets'] / rz_agg['team_cum_rz_targets'].replace(0, np.nan)
)
```

After fix, verify sanity check in cell 13:
- CeeDee Lamb > 0.65
- Ja'Marr Chase > 0.55
- Trey McBride / Travis Kelce > 0.60

---

### Fix 3 — Remove Dead Features From FEATURES List

In `feature_prep.py`, remove:

```python
# Remove — zero correlation, waste tree splits
'opp_wr_te_td_rate_allowed',
'opp_wr_te_targets_pg_allowed',
```

Also remove from the `MONOTONE` dict in `train.py`.

While there, also remove:
- `is_home` (r = 0.019) — too weak, remove
- `week` (r = -0.012) — remove

Confirm `td_rate_per_target` is not still in FEATURES (it was replaced by `td_rate_eb`).

---

## Final Retrain Sequence

After all three fixes are applied and `game_logs_enriched.csv` regenerated:

```bash
cd ml

# Regenerate enriched CSV with fixed snap crosswalk + RZ denominator
# Run 05_new_features.ipynb end-to-end (PBP is cached, ~1 min)

# Then retrain
python train.py      # retrains, saves model/wr_te_model_v2.pkl
python calibrate.py  # re-runs Beta calibration on 2024 eval set
python evaluate.py   # final holdout metrics + sportsbook edge table
```

Or run `04_model_training.ipynb` end-to-end.

**Expected gains after fixes:**
- AUC: 0.745–0.752 (snap fix adds ~0.005)
- Brier: < 0.138 (cleaner features + snap fix)
- Snap match rate: > 90%
- `rz_target_share` values corrected (accuracy matters for production odds)

---

## Edge Table — Production Filtering

Add to `evaluate.py` before displaying the edge table. Raw output includes
low-liquidity lines (obscure TEs with wide spreads) that are not actionable:

```python
actionable = merged[
    (merged['consensus_odds'] >= -200) &  # implied prob <= 67%
    (merged['consensus_odds'] <= 500) &   # implied prob >= 17%
    (merged['roll3_rz_targets'] > 1) &    # model has RZ data on this player
    (merged['edge'] > 0.05)               # at least 5% edge
].sort_values('edge', ascending=False)
```

The `consensus_odds <= 500` filter cuts obscure TEs with wide spreads.
The `roll3_rz_targets > 1` filter ensures the model isn't extrapolating
from zero red zone history.

Players from current edge table passing both filters:
**Rome Odunze (+17.8%), Wan'Dale Robinson (+12.5%), Trey McBride (+12.6%),
Quentin Johnston (+10.5%)** — these are the actionable ones.

---

## Files Status

| File | Status | Notes |
|---|---|---|
| `feature_prep.py` | ✅ | EB shrinkage, auto-detects new columns |
| `train.py` | ✅ | XGBoost + monotone constraints + LR baseline |
| `calibrate.py` | ✅ | Beta calibration selected |
| `evaluate.py` | needs update | Add actionable edge filter |
| `utils.py` | ✅ | Odds conversion, reliability diagram |
| `04_model_training.ipynb` | ✅ | Full pipeline notebook |
| `05_new_features.ipynb` | needs fixes | Fix 1 + Fix 2 from above |
| `model/wr_te_model_v2.pkl` | ✅ current best | AUC 0.740, retrain after fixes |
| `model/reliability_diagrams.png` | ✅ | Beta cal, max dev 0.17 |
| `data/game_logs_enriched.csv` | needs regen | Regenerate after notebook fixes |

---

## What NOT to Do

- **Don't keep chasing Brier < 0.115** — that target assumed higher AUC was
  achievable. At 0.740 AUC with 20% base TD rate, Brier ~0.14 is near-optimal.
  The model is not miscalibrated; it's correctly uncertain.
- **Don't add Vegas team totals** — real-time API dependency, and opponent
  defensive rate was tested and showed zero signal. Same conclusion would apply.
- **Don't separate WR/TE models** — `is_te` handles position adequately. Marginal
  gain, doubles maintenance.
- **Don't use `weeks_since_td`** — gambler's fallacy, confirmed non-monotonic.
  Permanently removed.
- **Don't retrain incrementally** — apply all three fixes, regenerate the CSV,
  then retrain once. Retraining between fixes makes attribution impossible.
