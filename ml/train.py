"""
BGGTDM v2 — Model Training
Step 1: Logistic Regression baseline
Step 2: XGBoost with monotone constraints + early stopping
Step 3: Save model bundle
"""

import os
import numpy as np
import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, brier_score_loss, log_loss
import xgboost as xgb

from feature_prep import load_and_prepare, FEATURES, FEATURES_V2_BASE

MODEL_DIR = 'model'
MODEL_PATH = os.path.join(MODEL_DIR, 'wr_te_model_v2.pkl')

MONOTONE = {
    'targets_pg':        1,
    'roll3_targets':     1,
    'yards_pg':          1,
    'receptions_pg':     1,
    'roll3_yards':       1,
    'roll3_receptions':  1,
    'lag_targets':       1,
    'lag_yards':         1,
    'target_share':      1,
    'roll3_long_rec':    1,
    'roll3_target_std':  1,
    'tds_last3':         1,
    'td_streak':         1,
    'td_rate_eb':        1,
    'td_rate_eb_std':              0,
    'is_te':                       0,
    # New features (added after 05_new_features.ipynb)
    'lag_snap_pct':                1,
    'roll3_snap_pct':              1,
    'roll3_rz_targets':            1,
    'rz_target_share':             1,
    'rz_td_rate_eb':               1,
}


def print_metrics(label, y_true, y_prob):
    auc = roc_auc_score(y_true, y_prob)
    brier = brier_score_loss(y_true, y_prob)
    ll = log_loss(y_true, y_prob)
    print(f'\n--- {label} ---')
    print(f'  ROC-AUC:     {auc:.4f}')
    print(f'  Brier Score: {brier:.4f}')
    print(f'  Log-Loss:    {ll:.4f}')
    pcts = np.percentile(y_prob, [10, 25, 50, 75, 90, 95])
    print(f'  Prob percentiles (10/25/50/75/90/95): '
          f'{pcts[0]:.3f} / {pcts[1]:.3f} / {pcts[2]:.3f} / '
          f'{pcts[3]:.3f} / {pcts[4]:.3f} / {pcts[5]:.3f}')
    return auc, brier, ll


def train_lr(X_train, y_train, X_holdout, y_holdout):
    """Regularized logistic regression baseline."""
    # LR doesn't handle NaN — impute with column median (snap features may have NaN)
    col_medians = np.nanmedian(X_train, axis=0)
    nan_mask_tr = np.isnan(X_train)
    nan_mask_ho = np.isnan(X_holdout)
    X_train = X_train.copy()
    X_holdout = X_holdout.copy()
    X_train[nan_mask_tr] = np.take(col_medians, np.where(nan_mask_tr)[1])
    X_holdout[nan_mask_ho] = np.take(col_medians, np.where(nan_mask_ho)[1])

    scaler = StandardScaler()
    X_tr_scaled = scaler.fit_transform(X_train)
    X_ho_scaled = scaler.transform(X_holdout)

    lr = LogisticRegression(
        class_weight='balanced',
        C=0.1,
        max_iter=1000,
        random_state=42
    )
    lr.fit(X_tr_scaled, y_train)

    probs_train = lr.predict_proba(X_tr_scaled)[:, 1]
    probs_holdout = lr.predict_proba(X_ho_scaled)[:, 1]

    print_metrics('LR Baseline — Train', y_train, probs_train)
    auc, brier, ll = print_metrics('LR Baseline — Holdout (2025)', y_holdout, probs_holdout)

    return lr, scaler, probs_holdout, auc, brier


def train_xgb(X_train, y_train, train_df, active_features=None):
    """XGBoost with monotone constraints and season-based early stopping."""
    if active_features is None:
        active_features = FEATURES
    constraints = tuple(MONOTONE[f] for f in active_features)

    model = xgb.XGBClassifier(
        n_estimators=400,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=20,
        scale_pos_weight=1,        # no upsampling — calibration handles class balance
        monotone_constraints=constraints,
        eval_metric='logloss',
        early_stopping_rounds=30,
        random_state=42,
    )

    eval_mask = (train_df['season'] == 2024) & (train_df['week'] >= 14)
    X_eval = X_train[eval_mask]
    y_eval = y_train[eval_mask]
    X_tr = X_train[~eval_mask]
    y_tr = y_train[~eval_mask]

    print(f'\nXGBoost training split: {len(X_tr)} rows train, {len(X_eval)} rows eval (2024 wk14-18)')
    model.fit(
        X_tr, y_tr,
        eval_set=[(X_eval, y_eval)],
        verbose=50
    )
    print(f'  Best iteration: {model.best_iteration}')

    return model


def main():
    # Load data
    print('Loading and preparing features...')
    X_train, y_train, X_holdout, y_holdout, train_df, holdout_df, eb_params = load_and_prepare()

    # LR baseline
    print('\n=== LOGISTIC REGRESSION BASELINE ===')
    lr, scaler, lr_probs_holdout, lr_auc, lr_brier = train_lr(
        X_train, y_train, X_holdout, y_holdout
    )

    # Determine active feature set (base vs full depending on CSV contents)
    from feature_prep import _has_new_features
    import pandas as pd
    _df_check = pd.read_csv('data/game_logs_enriched.csv', nrows=1)
    active_features = FEATURES if _has_new_features(_df_check) else FEATURES_V2_BASE
    print(f'Using {len(active_features)} features '
          f'({"full" if len(active_features) == len(FEATURES) else "base"} set)')

    # XGBoost
    print('\n=== XGBOOST ===')
    xgb_model = train_xgb(X_train, y_train, train_df, active_features=active_features)

    xgb_probs_train = xgb_model.predict_proba(X_train)[:, 1]
    xgb_probs_holdout = xgb_model.predict_proba(X_holdout)[:, 1]

    print_metrics('XGBoost — Train', y_train, xgb_probs_train)
    xgb_auc, xgb_brier, _ = print_metrics('XGBoost — Holdout (2025)', y_holdout, xgb_probs_holdout)

    # Feature importance
    print('\n--- Feature Importance (top 10) ---')
    importances = xgb_model.feature_importances_
    fi = sorted(zip(active_features, importances), key=lambda x: -x[1])
    for feat, imp in fi[:10]:
        print(f'  {feat:<25} {imp:.4f}')

    is_te_imp = dict(fi).get('is_te', 0)
    if is_te_imp > 0.10:
        print(f'\nWARNING: is_te importance = {is_te_imp:.3f} > 10% — consider separate WR/TE models')

    # Sanity check
    if xgb_auc < 0.700:
        print('\nWARNING: AUC < 0.700 — investigate feature leakage or data split issues')

    # Save artifacts
    os.makedirs(MODEL_DIR, exist_ok=True)
    bundle = {
        'model': xgb_model,
        'scaler': scaler,
        'features': active_features,
        'tau': None,            # filled in by calibrate.py
        'alpha_eb': eb_params['alpha'],
        'beta_eb': eb_params['beta'],
        'rz_alpha_eb': eb_params.get('rz_alpha'),
        'rz_beta_eb': eb_params.get('rz_beta'),
        'trained_on': '2022-2024',
        'holdout_auc': xgb_auc,
        'holdout_brier': xgb_brier,
        'lr_baseline': lr,
        'lr_probs_holdout': lr_probs_holdout,
        'xgb_probs_holdout': xgb_probs_holdout,
        'y_holdout': y_holdout,
        'train_df': train_df,
        'holdout_df': holdout_df,
        'X_train': X_train,
        'y_train': y_train,
        'X_holdout': X_holdout,
    }
    joblib.dump(bundle, MODEL_PATH)
    print(f'\nSaved model bundle to {MODEL_PATH}')
    print(f'XGBoost AUC: {xgb_auc:.4f} | Brier: {xgb_brier:.4f}')

    return bundle


if __name__ == '__main__':
    main()
