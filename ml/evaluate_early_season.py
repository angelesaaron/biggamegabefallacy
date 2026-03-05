"""
evaluate_early_season.py — Early-season carry-forward reliability check.

Validates that carry-forward predictions for weeks 1-3 are well-calibrated
by splitting the 2025 holdout by week group and comparing:
  - AUC, Brier, TD recall per group
  - Reliability curves (observed vs predicted) per group
  - Carry-forward vs non-carry-forward rows within early weeks

Run after train.py + calibrate.py.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import joblib
from sklearn.metrics import roc_auc_score, brier_score_loss

from utils import reliability_diagram

MODEL_PATH = 'model/wr_te_model_v2.pkl'


def group_label(week):
    if week == 1:
        return 'Week 1'
    elif week <= 3:
        return 'Weeks 2-3'
    elif week <= 9:
        return 'Weeks 4-9'
    else:
        return 'Weeks 10-18'


GROUP_ORDER = ['Week 1', 'Weeks 2-3', 'Weeks 4-9', 'Weeks 10-18']


def metrics_for(y, probs, label):
    if len(y) < 10:
        return None
    n_td = int(y.sum())
    td_rate = y.mean()
    try:
        auc = roc_auc_score(y, probs) if len(np.unique(y)) > 1 else float('nan')
    except Exception:
        auc = float('nan')
    brier = brier_score_loss(y, probs)
    mean_pred = probs.mean()

    # TD recall @ top 20%
    n = max(1, int(len(y) * 0.20))
    top_idx = np.argsort(probs)[::-1][:n]
    recall_top20 = y[top_idx].sum() / max(y.sum(), 1)

    return {
        'label': label,
        'n': len(y),
        'n_td': n_td,
        'td_rate': td_rate,
        'mean_pred': mean_pred,
        'calibration_gap': mean_pred - td_rate,
        'auc': auc,
        'brier': brier,
        'recall_top20': recall_top20,
    }


def main():
    print('Loading model bundle...')
    bundle = joblib.load(MODEL_PATH)

    holdout_df = bundle['holdout_df'].copy()
    y_holdout = bundle['y_holdout']

    if 'calibrated_probs_holdout' in bundle:
        cal_probs = bundle['calibrated_probs_holdout']
        cal_method = bundle.get('best_calibration', 'unknown')
        print(f'Using calibrated probabilities ({cal_method})')
    else:
        cal_probs = bundle['xgb_probs_holdout']
        print('Using raw XGBoost probabilities (run calibrate.py first)')

    # Apply early-season week-group scalars if present in bundle
    scalars = bundle.get('early_season_scalars', {})
    if scalars:
        cal_probs = cal_probs.copy()
        for key, wk_lo, wk_hi in [('wk1', 1, 1), ('wk2_3', 2, 3), ('wk4_plus', 4, 99)]:
            s = scalars.get(key, 1.0)
            if s != 1.0:
                mask_wk = (holdout_df['week'] >= wk_lo) & (holdout_df['week'] <= wk_hi)
                if mask_wk.any():
                    cal_probs[mask_wk.values] = np.clip(cal_probs[mask_wk.values] * s, 0.0, 1.0)
        print(f'Early-season scalars applied: {scalars}')

    holdout_df['cal_prob'] = cal_probs
    holdout_df['y'] = y_holdout
    holdout_df['week_group'] = holdout_df['week'].apply(group_label)

    print(f'\nHoldout rows: {len(holdout_df)} | seasons: {sorted(holdout_df["season"].unique())}')
    print(f'Week range: {holdout_df["week"].min()} - {holdout_df["week"].max()}')

    # ---- Metrics by week group ----
    print('\n=== METRICS BY WEEK GROUP (2025 holdout) ===')
    print(f"{'Group':<14} {'N':>5} {'TDs':>5} {'TD%':>6} {'MeanPred':>9} "
          f"{'CalGap':>8} {'AUC':>7} {'Brier':>7} {'Recall20%':>10}")
    print('-' * 80)

    results = []
    for grp in GROUP_ORDER:
        mask = holdout_df['week_group'] == grp
        if not mask.any():
            continue
        sub = holdout_df[mask]
        m = metrics_for(sub['y'].values, sub['cal_prob'].values, grp)
        if m:
            results.append(m)
            auc_str = f"{m['auc']:.4f}" if not np.isnan(m['auc']) else '  n/a '
            print(f"{m['label']:<14} {m['n']:>5} {m['n_td']:>5} "
                  f"{m['td_rate']:>5.1%} {m['mean_pred']:>9.1%} "
                  f"{m['calibration_gap']:>+7.1%} {auc_str:>7} "
                  f"{m['brier']:>7.4f} {m['recall_top20']:>9.1%}")

    # ---- Carry-forward breakdown within early weeks ----
    early_mask = holdout_df['week'] <= 3
    if early_mask.any() and 'has_carry_forward' in holdout_df.columns:
        print('\n=== EARLY WEEKS — CARRY-FORWARD vs NON-CARRY-FORWARD ===')
        for cf_val, label in [(True, 'carry-forward'), (False, 'no prior (rookie/new)')]:
            sub_mask = early_mask & (holdout_df['has_carry_forward'] == cf_val)
            if not sub_mask.any():
                continue
            sub = holdout_df[sub_mask]
            m = metrics_for(sub['y'].values, sub['cal_prob'].values, label)
            if m:
                auc_str = f"{m['auc']:.4f}" if not np.isnan(m['auc']) else 'n/a'
                print(f"  {label:<30} n={m['n']:>4}  TD%={m['td_rate']:.1%}  "
                      f"pred={m['mean_pred']:.1%}  gap={m['calibration_gap']:+.1%}  "
                      f"AUC={auc_str}")

    # ---- Reliability plots by group ----
    groups_to_plot = [g for g in GROUP_ORDER if (holdout_df['week_group'] == g).sum() >= 20]
    if groups_to_plot:
        fig, axes = plt.subplots(1, len(groups_to_plot),
                                 figsize=(5 * len(groups_to_plot), 5))
        if len(groups_to_plot) == 1:
            axes = [axes]

        for ax, grp in zip(axes, groups_to_plot):
            mask = holdout_df['week_group'] == grp
            sub = holdout_df[mask]
            n_bins = min(8, max(4, len(sub) // 30))
            try:
                reliability_diagram(
                    sub['y'].values,
                    sub['cal_prob'].values,
                    title=f'{grp}\n(n={len(sub)}, TD%={sub["y"].mean():.1%})',
                    ax=ax,
                    n_bins=n_bins,
                )
            except Exception as e:
                ax.set_title(f'{grp} — insufficient data\n{e}')

        plt.suptitle('Reliability by Week Group — 2025 Holdout', fontsize=13, y=1.02)
        plt.tight_layout()
        plt.savefig('model/early_season_reliability.png', dpi=120, bbox_inches='tight')
        print('\nSaved model/early_season_reliability.png')
        plt.show()

    # ---- Week 1 spot-check: top predicted players ----
    wk1 = holdout_df[holdout_df['week'] == 1].sort_values('cal_prob', ascending=False)
    if len(wk1) > 0:
        print(f'\n=== WEEK 1 TOP PREDICTIONS (2025, n={len(wk1)}) ===')
        cols = ['name', 'pos', 'team', 'cal_prob', 'y']
        if 'has_carry_forward' in wk1.columns:
            cols.insert(4, 'has_carry_forward')
        print(wk1[cols].head(20).to_string(index=False))
        print(f'\nWeek 1 actual TD rate: {wk1["y"].mean():.1%}  '
              f'Mean predicted: {wk1["cal_prob"].mean():.1%}')

    # ---- Summary ----
    if results:
        early_results = [r for r in results if r['label'] in ('Week 1', 'Weeks 2-3')]
        late_results  = [r for r in results if r['label'] in ('Weeks 4-9', 'Weeks 10-18')]
        if early_results and late_results:
            early_gap = np.mean([abs(r['calibration_gap']) for r in early_results])
            late_gap  = np.mean([abs(r['calibration_gap']) for r in late_results])
            print(f'\n=== CARRY-FORWARD CALIBRATION SUMMARY ===')
            print(f'  Mean |calibration gap| early (wk1-3): {early_gap:.1%}')
            print(f'  Mean |calibration gap| late  (wk4+):  {late_gap:.1%}')
            if early_gap <= late_gap * 1.5:
                print('  PASS: Early-season calibration within 1.5x of late-season')
            else:
                print('  WARN: Early-season calibration notably worse than late-season')
                print('        Consider re-running 06_prior_season.ipynb or adjusting blending')


if __name__ == '__main__':
    main()
