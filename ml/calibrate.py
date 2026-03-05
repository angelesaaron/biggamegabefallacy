"""
BGGTDM v2 — Probability Calibration
- Temperature scaling (single parameter tau)
- Beta calibration (betacal library)
- Reliability diagrams comparing both
"""

import numpy as np
import matplotlib.pyplot as plt
import joblib
from scipy.optimize import minimize_scalar
from scipy.special import expit, logit
from sklearn.metrics import log_loss
from betacal import BetaCalibration

from utils import reliability_diagram

MODEL_PATH = 'model/wr_te_model_v2.pkl'


def fit_temperature_scaling(raw_probs_val, y_val):
    """Fit temperature parameter tau to minimize log-loss on validation set."""
    raw_logits = logit(np.clip(raw_probs_val, 1e-6, 1 - 1e-6))

    def neg_logloss(tau):
        p = expit(raw_logits / tau)
        return log_loss(y_val, p)

    result = minimize_scalar(neg_logloss, bounds=(0.1, 5.0), method='bounded')
    tau = result.x
    print(f'Temperature scaling tau = {tau:.4f}')
    return tau


def apply_temperature_scaling(raw_probs, tau):
    raw_logits = logit(np.clip(raw_probs, 1e-6, 1 - 1e-6))
    return expit(raw_logits / tau)


def fit_beta_calibration(raw_probs_val, y_val):
    """Fit Beta calibration on validation set."""
    bc = BetaCalibration(parameters='abm')
    bc.fit(raw_probs_val.reshape(-1, 1), y_val)
    return bc


def main():
    print('Loading model bundle...')
    bundle = joblib.load(MODEL_PATH)

    model = bundle['model']
    X_train = bundle['X_train']
    y_train = bundle['y_train']
    X_holdout = bundle['X_holdout']
    y_holdout = bundle['y_holdout']
    train_df = bundle['train_df']

    # Use 2024 season (XGBoost eval set) as calibration validation set.
    # This data was held out from XGBoost gradient updates — genuine val preds.
    val_mask = train_df['season'] == 2024
    X_val = X_train[val_mask]
    y_val = y_train[val_mask]

    raw_probs_val = model.predict_proba(X_val)[:, 1]
    raw_probs_holdout = model.predict_proba(X_holdout)[:, 1]

    print(f'Validation (2024) rows: {len(y_val)} | TD rate: {y_val.mean():.3f}')

    # Temperature scaling
    tau = fit_temperature_scaling(raw_probs_val, y_val)
    ts_probs_holdout = apply_temperature_scaling(raw_probs_holdout, tau)

    # Beta calibration
    bc = fit_beta_calibration(raw_probs_val, y_val)
    bc_probs_holdout = bc.predict(raw_probs_holdout.reshape(-1, 1))

    # Reliability diagrams
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    print('\n=== Reliability Diagrams on 2025 Holdout ===')

    bm, bf, _ = reliability_diagram(y_holdout, raw_probs_holdout,
                                     title='Raw XGBoost', ax=axes[0])
    raw_max_dev = np.max(np.abs(bm - bf))

    bm, bf, _ = reliability_diagram(y_holdout, ts_probs_holdout,
                                     title=f'Temperature Scaling (τ={tau:.3f})', ax=axes[1])
    ts_max_dev = np.max(np.abs(bm - bf))

    bm, bf, _ = reliability_diagram(y_holdout, bc_probs_holdout,
                                     title='Beta Calibration', ax=axes[2])
    bc_max_dev = np.max(np.abs(bm - bf))

    print(f'  Raw XGBoost max deviation:       {raw_max_dev:.4f}')
    print(f'  Temperature scaling max deviation: {ts_max_dev:.4f}')
    print(f'  Beta calibration max deviation:   {bc_max_dev:.4f}')

    best = 'temperature' if ts_max_dev <= bc_max_dev else 'beta'
    print(f'\nBest calibration: {best}')

    # Probability distribution after best calibration
    best_probs = ts_probs_holdout if best == 'temperature' else bc_probs_holdout
    pcts = np.percentile(best_probs, [10, 25, 50, 75, 90, 95])
    print(f'\nCalibrated prob percentiles (10/25/50/75/90/95):')
    print(f'  {pcts[0]:.3f} / {pcts[1]:.3f} / {pcts[2]:.3f} / '
          f'{pcts[3]:.3f} / {pcts[4]:.3f} / {pcts[5]:.3f}')

    if pcts[4] < 0.50:
        print('WARNING: 95th percentile < 0.50 — calibration may still be compressed')

    plt.tight_layout()
    plt.savefig('model/reliability_diagrams.png', dpi=120, bbox_inches='tight')
    print('\nSaved reliability diagrams to model/reliability_diagrams.png')
    plt.show()

    # ---- Early-season week-group scalars ----
    # Fit additive correction on 2024 validation data so week 1-3 carry-forward
    # predictions aren't systematically over/under vs actual early-season TD rates.
    # Stored as {group: scalar} where scalar = actual_td_rate / mean_predicted.
    # Applied multiplicatively to raw beta-calibrated probs at prediction time.
    train_df = bundle['train_df']
    val_df = train_df[train_df['season'] == 2024].copy()
    val_df['bc_prob'] = bc.predict(
        model.predict_proba(bundle['X_train'][val_mask])[:, 1].reshape(-1, 1)
    )

    print('\n=== EARLY-SEASON WEEK-GROUP SCALARS (fit on 2024 val) ===')
    early_season_scalars = {}
    for key, wk_lo, wk_hi in [('wk1', 1, 1), ('wk2_3', 2, 3), ('wk4_plus', 4, 99)]:
        grp = val_df[(val_df['week'] >= wk_lo) & (val_df['week'] <= wk_hi)]
        if len(grp) >= 15 and grp['scored_td'].sum() > 0:
            actual = grp['scored_td'].mean()
            pred   = grp['bc_prob'].mean()
            scalar = actual / max(pred, 1e-6)
        else:
            scalar = 1.0
            actual = pred = float('nan')
        early_season_scalars[key] = round(scalar, 4)
        print(f'  {key:<12} n={len(grp):>4}  actual={actual:.1%}  '
              f'pred={pred:.1%}  scalar={scalar:.3f}')

    # Update bundle with calibration artifacts
    bundle['tau'] = tau
    bundle['beta_calibrator'] = bc
    bundle['ts_probs_holdout'] = ts_probs_holdout
    bundle['bc_probs_holdout'] = bc_probs_holdout
    bundle['best_calibration'] = best
    bundle['calibrated_probs_holdout'] = best_probs
    bundle['early_season_scalars'] = early_season_scalars
    joblib.dump(bundle, MODEL_PATH)
    print(f'Updated bundle saved to {MODEL_PATH}')

    return tau, bc, best_probs


if __name__ == '__main__':
    main()
