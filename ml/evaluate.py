"""
BGGTDM v2 — Holdout Evaluation + Sportsbook Comparison
- Final metrics on 2025 holdout
- Edge detection vs sportsbook lines
- Calibration test: model vs book
"""

import numpy as np
import pandas as pd
import joblib
from scipy.special import logit
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, brier_score_loss, log_loss

from utils import american_to_implied_prob, prob_to_american

MODEL_PATH = 'model/wr_te_model_v2.pkl'
ODDS_PATH = 'data/anytime_td_odds.csv'


def td_recall_at_top_k(y_true, y_prob, top_pct=0.20):
    """Fraction of actual TDs in top-k% predicted rows."""
    n = int(len(y_true) * top_pct)
    idx = np.argsort(y_prob)[::-1][:n]
    return y_true[idx].sum() / y_true.sum()


def main():
    print('Loading model bundle...')
    bundle = joblib.load(MODEL_PATH)

    y_holdout = bundle['y_holdout']
    holdout_df = bundle['holdout_df']

    # Use calibrated probabilities if available, else raw
    if 'calibrated_probs_holdout' in bundle:
        cal_probs = bundle['calibrated_probs_holdout']
        cal_method = bundle.get('best_calibration', 'unknown')
        print(f'Using calibrated probabilities ({cal_method})')
    else:
        cal_probs = bundle['xgb_probs_holdout']
        print('Using raw XGBoost probabilities (run calibrate.py first)')

    raw_probs = bundle['xgb_probs_holdout']

    # Final holdout metrics
    auc = roc_auc_score(y_holdout, cal_probs)
    brier = brier_score_loss(y_holdout, cal_probs)
    ll = log_loss(y_holdout, cal_probs)
    recall_top20 = td_recall_at_top_k(y_holdout, cal_probs, 0.20)

    print('\n=== FINAL HOLDOUT METRICS (2025) ===')
    print(f'  ROC-AUC:               {auc:.4f}  (target: > 0.730)')
    print(f'  Brier Score:           {brier:.4f}  (target: < 0.115)')
    print(f'  Log-Loss:              {ll:.4f}')
    print(f'  TD Recall @ top 20%:   {recall_top20:.3f}  (target: > 0.35)')

    pcts = np.percentile(cal_probs, [10, 25, 50, 75, 90, 95])
    print(f'\n  Prob percentiles (10/25/50/75/90/95):')
    print(f'  {pcts[0]:.3f} / {pcts[1]:.3f} / {pcts[2]:.3f} / '
          f'{pcts[3]:.3f} / {pcts[4]:.3f} / {pcts[5]:.3f}')
    print(f'  95th pct target: > 0.50, got {pcts[5]:.3f}')

    # Grade vs targets
    print('\n=== V2 TARGET SCORECARD ===')
    checks = [
        ('ROC-AUC > 0.730',       auc > 0.730,         f'{auc:.4f}'),
        ('Brier < 0.115',         brier < 0.115,        f'{brier:.4f}'),
        ('95th pct > 0.50',       pcts[5] > 0.50,       f'{pcts[5]:.3f}'),
        ('TD Recall top-20% > 35%', recall_top20 > 0.35, f'{recall_top20:.3f}'),
    ]
    for desc, passed, val in checks:
        status = 'PASS' if passed else 'FAIL'
        print(f'  [{status}] {desc}: {val}')

    # Sportsbook comparison
    print('\n=== SPORTSBOOK COMPARISON ===')
    try:
        odds_df = pd.read_csv(ODDS_PATH, index_col=0)
        odds_df.index.name = 'name'

        # Use consensus odds: average across available books
        sportsbook_cols = [c for c in odds_df.columns if odds_df[c].notna().sum() > 0]
        odds_df['consensus_odds'] = odds_df[sportsbook_cols].mean(axis=1)
        odds_df = odds_df[odds_df['consensus_odds'].notna()].reset_index()

        print(f'Odds file loaded: {len(odds_df)} players')
        print('Note: odds file lacks week/season info — matching by player name only')

        # Match to holdout by name
        holdout_with_probs = holdout_df.copy()
        holdout_with_probs['model_prob'] = cal_probs

        # Normalize names for merge
        agg_dict = {'model_prob': ('model_prob', 'mean'), 'scored_td': ('scored_td', 'mean')}
        if 'roll3_rz_targets' in holdout_with_probs.columns:
            agg_dict['roll3_rz_targets'] = ('roll3_rz_targets', 'mean')
        holdout_agg = (
            holdout_with_probs
            .groupby('name')
            .agg(**agg_dict)
            .reset_index()
        )

        merged = holdout_agg.merge(odds_df[['name', 'consensus_odds']], on='name', how='inner')
        print(f'Matched {len(merged)} players to sportsbook odds')

        if len(merged) > 0:
            merged['book_prob'] = merged['consensus_odds'].apply(american_to_implied_prob)
            merged['edge'] = merged['model_prob'] - merged['book_prob']
            merged['model_american'] = merged['model_prob'].apply(prob_to_american)
            merged['book_american'] = merged['consensus_odds'].round(0).astype(int)

            top_edges = merged.sort_values('edge', ascending=False).head(20)
            print('\nTop 20 edges (model vs book):')
            print(f"{'Player':<25} {'Model%':>8} {'Book%':>8} {'Edge':>8} {'Model Odds':>12} {'Book Odds':>10}")
            print('-' * 75)
            for _, row in top_edges.iterrows():
                print(f"{row['name']:<25} {row['model_prob']:>7.1%} {row['book_prob']:>7.1%} "
                      f"{row['edge']:>+7.1%} {row['model_american']:>12} {row['book_american']:>10}")

            # Actionable edges: liquid lines only, meaningful RZ history, >5% edge
            actionable_mask = (
                (merged['consensus_odds'] >= -200) &
                (merged['consensus_odds'] <= 500) &
                (merged['edge'] > 0.05)
            )
            if 'roll3_rz_targets' in merged.columns:
                actionable_mask &= (merged['roll3_rz_targets'] > 1)
            actionable = merged[actionable_mask].sort_values('edge', ascending=False)
            print(f'\n=== ACTIONABLE EDGES ({len(actionable)} players) ===')
            print('Filters: odds -200 to +500, edge > 5%' +
                  (', roll3_rz_targets > 1' if 'roll3_rz_targets' in merged.columns else ''))
            if len(actionable) > 0:
                print(f"{'Player':<25} {'Model%':>8} {'Book%':>8} {'Edge':>8} {'Book Odds':>10}")
                print('-' * 65)
                for _, row in actionable.iterrows():
                    print(f"{row['name']:<25} {row['model_prob']:>7.1%} {row['book_prob']:>7.1%} "
                          f"{row['edge']:>+7.1%} {row['book_american']:>10}")
            else:
                print('  No actionable edges found.')

            # Calibration test: model vs book — needs binary TD outcomes
            # Use majority vote (most common outcome) per player as proxy
            binary_merged = merged[merged['scored_td'].isin([0.0, 1.0])].copy()
            if len(binary_merged) >= 20:
                model_probs_m = np.clip(binary_merged['model_prob'].values, 1e-6, 1 - 1e-6)
                book_probs_m = np.clip(binary_merged['book_prob'].values, 1e-6, 1 - 1e-6)
                y_m = (binary_merged['scored_td'].values > 0.5).astype(int)

                X_cal = np.column_stack([
                    logit(model_probs_m),
                    logit(book_probs_m)
                ])
                lr_test = LogisticRegression(C=1e6, max_iter=1000).fit(X_cal, y_m)
                print(f'\nCalibration test (logistic with model_logit + book_logit):')
                print(f'  Model coefficient: {lr_test.coef_[0][0]:.4f}')
                print(f'  Book coefficient:  {lr_test.coef_[0][1]:.4f}')
                print('  (If both coefs > 0, model adds independent signal beyond the book)')
            else:
                print('  Too few binary-outcome rows for calibration test')

    except FileNotFoundError:
        print(f'  {ODDS_PATH} not found — skipping sportsbook comparison')
    except Exception as e:
        print(f'  Sportsbook comparison error: {e}')


if __name__ == '__main__':
    main()
