"""
Feature preparation for BGGTDM v2.
- Computes target_share (missing from enriched CSV)
- Applies Empirical Bayes (Beta-Binomial) shrinkage on td_rate_per_target
- Returns clean train/holdout feature matrices
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import betabinom


DATA_PATH = 'data/game_logs_enriched.csv'
EARLY_SEASON_PRIOR_PATH = 'data/prior_season_final_state.csv'

# Features overridden with carry-forward values for weeks 1-3
# (td_rate_eb / td_rate_eb_std / rz_td_rate_eb are included — override after EB shrinkage)
CARRY_OVERRIDE_COLS = [
    'targets_pg', 'yards_pg', 'receptions_pg',
    'roll3_targets', 'roll3_yards', 'roll3_receptions',
    'lag_targets', 'lag_yards',
    'target_share',
    'roll3_long_rec', 'roll3_target_std',
    'tds_last3', 'td_streak',
    'td_rate_eb', 'td_rate_eb_std',
    'lag_snap_pct', 'roll3_snap_pct',
    'roll3_rz_targets', 'rz_target_share', 'rz_td_rate_eb',
]

FEATURES = [
    # Usage volume
    'targets_pg',
    'roll3_targets',
    'yards_pg',
    'receptions_pg',
    'roll3_yards',
    'roll3_receptions',
    'lag_targets',
    'lag_yards',
    # Target share
    'target_share',
    # Downfield usage
    'roll3_long_rec',
    # Usage volatility
    'roll3_target_std',
    # Streak / momentum
    'tds_last3',
    'td_streak',
    # EB shrinkage TD rate (replaces td_rate_per_target)
    'td_rate_eb',
    'td_rate_eb_std',
    # Context
    'is_te',
    # Snap count (added via 05_new_features.ipynb)
    'lag_snap_pct',
    'roll3_snap_pct',
    # Red zone (added via 05_new_features.ipynb)
    'roll3_rz_targets',
    'rz_target_share',
    'rz_td_rate_eb',
]

# Features available before 05_new_features.ipynb is run
FEATURES_V2_BASE = [f for f in FEATURES if f not in (
    'lag_snap_pct', 'roll3_snap_pct',
    'roll3_rz_targets', 'rz_target_share', 'rz_td_rate_eb',
)]

# Snap features are allowed to be NaN — XGBoost handles missing values natively
SNAP_FEATURES = {'lag_snap_pct', 'roll3_snap_pct'}


def add_target_share(df):
    """
    Compute cumulative season target share within team at each row's point in time.
    Uses cum_targets / team_cum_targets (lag-shifted cumulative values, no leakage).
    """
    df = df.copy()
    team_cum = (
        df.groupby(['season', 'week', 'team'])['cum_targets']
        .transform('sum')
    )
    df['target_share'] = df['cum_targets'] / team_cum.replace(0, np.nan)
    return df


def fit_beta_binomial(cum_tds, cum_targets):
    """
    Fit Beta-Binomial (alpha, beta) via maximum marginal likelihood.
    cum_tds and cum_targets are 1-D arrays.
    """
    cum_tds = np.array(cum_tds, dtype=float)
    cum_targets = np.array(cum_targets, dtype=float)

    # Filter rows where cum_targets >= 1 (need at least one trial)
    mask = cum_targets >= 1
    k = cum_tds[mask].astype(int)
    n = cum_targets[mask].astype(int)

    def neg_log_marglik(params):
        alpha, beta = params
        if alpha <= 0 or beta <= 0:
            return 1e10
        try:
            ll = betabinom.logpmf(k, n, alpha, beta).sum()
            return -ll
        except Exception:
            return 1e10

    # Try multiple starting points and keep best
    best_result = None
    for a0, b0 in [(1.0, 5.0), (0.5, 3.0), (2.0, 10.0), (0.3, 2.0)]:
        res = minimize(
            neg_log_marglik,
            x0=[a0, b0],
            method='Nelder-Mead',
            options={'xatol': 1e-5, 'fatol': 1e-5, 'maxiter': 5000}
        )
        if best_result is None or res.fun < best_result.fun:
            best_result = res

    alpha, beta = best_result.x
    return max(alpha, 1e-6), max(beta, 1e-6)


def shrink_td_rate(df, alpha=None, beta=None):
    """
    Apply Beta-Binomial shrinkage to td_rate_per_target.
    If alpha/beta are None, fit from df (call on training set).
    Returns (df_with_features, alpha, beta).
    """
    if alpha is None or beta is None:
        print('Fitting Beta-Binomial parameters...')
        alpha, beta = fit_beta_binomial(df['cum_tds'], df['cum_targets'])
        print(f'  alpha={alpha:.4f}, beta={beta:.4f}')

    df = df.copy()
    df['td_rate_eb'] = (df['cum_tds'] + alpha) / (df['cum_targets'] + alpha + beta)

    # Posterior variance of Beta distribution
    a_post = df['cum_tds'] + alpha
    b_post = (df['cum_targets'] - df['cum_tds']) + beta
    ab_post = a_post + b_post
    df['td_rate_eb_std'] = np.sqrt(
        (a_post * b_post) / (ab_post ** 2 * (ab_post + 1))
    )

    return df, alpha, beta


def shrink_rz_td_rate(df, alpha=None, beta=None):
    """
    Apply Beta-Binomial shrinkage to red zone TD rate.
    Uses cum_rz_tds / cum_rz_targets from 05_new_features.ipynb output.
    If alpha/beta are None, fit from df (call on training set).
    Returns (df_with_feature, alpha, beta).
    """
    if 'cum_rz_tds' not in df.columns or 'cum_rz_targets' not in df.columns:
        return df, None, None

    if alpha is None or beta is None:
        print('Fitting Beta-Binomial parameters for RZ TD rate...')
        alpha, beta = fit_beta_binomial(df['cum_rz_tds'], df['cum_rz_targets'])
        print(f'  RZ EB: alpha={alpha:.4f}, beta={beta:.4f}')

    df = df.copy()
    df['rz_td_rate_eb'] = (
        (df['cum_rz_tds'] + alpha) / (df['cum_rz_targets'] + alpha + beta)
    )
    return df, alpha, beta


def apply_early_season_carry_forward(df, prior_path=EARLY_SEASON_PRIOR_PATH):
    """
    For week 1-3 rows, override rolling/lag features with the player's prior-season
    final state. This lets the model train on early-season outcomes using the same
    carry-forward features it will see in production.

    Adds 'has_carry_forward' bool column to df.
    Returns modified df (copy).
    """
    import os
    if not os.path.exists(prior_path):
        print(f'NOTE: {prior_path} not found — skipping early-season carry-forward.')
        print('      Run 06_prior_season.ipynb to generate it.')
        df = df.copy()
        df['has_carry_forward'] = False
        return df

    prior = pd.read_csv(prior_path)

    df = df.copy()
    df['has_carry_forward'] = False

    early_mask = df['week'] <= 3
    if not early_mask.any():
        return df

    # Get indices of early-season rows
    early_idx = df.index[early_mask]
    early = df.loc[early_idx, ['player_id', 'season']].copy()

    # Join prior state on player_id + season == join_season
    prior_cols = ['player_id', 'join_season'] + [c for c in CARRY_OVERRIDE_COLS if c in prior.columns]
    merged = early.merge(
        prior[prior_cols],
        left_on=['player_id', 'season'],
        right_on=['player_id', 'join_season'],
        how='left',
    )
    # merged has the same row order as early (left join preserves order)
    has_cf = merged['join_season'].notna().values

    # Update feature columns in-place for rows that matched
    for col in CARRY_OVERRIDE_COLS:
        if col in merged.columns and col in df.columns:
            new_vals = merged[col].values
            # Only overwrite where a carry-forward row was found
            df.loc[early_idx[has_cf], col] = new_vals[has_cf]

    df.loc[early_idx[has_cf], 'has_carry_forward'] = True

    n_cf = int(has_cf.sum())
    n_early = int(early_mask.sum())
    print(f'Early-season carry-forward: {n_cf}/{n_early} week 1-3 rows filled from prior season')
    return df


def _has_new_features(df):
    """Check whether 05_new_features.ipynb columns are present in the data."""
    new_cols = ['opp_wr_te_td_rate_allowed', 'lag_snap_pct', 'cum_rz_tds']
    return all(c in df.columns for c in new_cols)


def load_and_prepare(data_path=DATA_PATH, include_early_season=True):
    """
    Load enriched data, add target_share, apply EB shrinkage, return:
      X_train, y_train, X_holdout, y_holdout, train_df, holdout_df, eb_params

    include_early_season: if True and prior_season_final_state.csv exists, week 1-3
      rows are filled via carry-forward and included in training. Matches production.
    """
    df = pd.read_csv(data_path)

    # Add target_share
    df = add_target_share(df)

    # Auto-detect which feature set to use
    use_new_features = _has_new_features(df)
    active_features = FEATURES if use_new_features else FEATURES_V2_BASE
    if not use_new_features:
        print('NOTE: New features (opp defense, snap %, red zone) not found in CSV.')
        print('      Run 05_new_features.ipynb to add them. Using base feature set.')

    # Apply early-season carry-forward before splitting (marks has_carry_forward)
    if include_early_season:
        df = apply_early_season_carry_forward(df)
    else:
        df['has_carry_forward'] = False

    # Training filter: standard games_played >= 1 rows, PLUS week 1-3 rows that
    # have carry-forward features (so the model trains on early-season outcomes
    # using the same feature state it will see in production)
    early_ok = (df['week'] <= 3) & df['has_carry_forward']
    train = df[(df['season'] <= 2024) & ((df['games_played'] >= 1) | early_ok)].copy()
    holdout = df[df['season'] == 2025].copy()

    # Fit EB on training set, apply to both (anytime TD rate)
    train, alpha, beta = shrink_td_rate(train)
    holdout, _, _ = shrink_td_rate(holdout, alpha=alpha, beta=beta)

    # Fit RZ EB if new features present
    rz_alpha, rz_beta = None, None
    if use_new_features:
        train, rz_alpha, rz_beta = shrink_rz_td_rate(train)
        holdout, _, _ = shrink_rz_td_rate(holdout, alpha=rz_alpha, beta=rz_beta)

    print(f'Train: {len(train)} rows | Holdout: {len(holdout)} rows')
    print(f'Train TD rate: {train["scored_td"].mean():.3f} | '
          f'Holdout TD rate: {holdout["scored_td"].mean():.3f}')

    # Check all active features present
    missing = [f for f in active_features if f not in train.columns]
    if missing:
        raise ValueError(f'Missing features: {missing}')

    # roll3_target_std NaN means < 3 games history → 0 volatility is correct prior
    # RZ features NaN means player had zero RZ activity → 0 is correct
    # snap_pct NaN means unmatched player name — leave NaN, XGBoost handles natively
    for df_ in [train, holdout]:
        df_['roll3_target_std'] = df_['roll3_target_std'].fillna(0.0)
        if use_new_features:
            for col in ('roll3_rz_targets', 'rz_target_share', 'rz_td_rate_eb'):
                if col in df_.columns:
                    df_[col] = df_[col].fillna(0.0)
    # lag_targets / lag_yards NaN means no prior game (rookies, new entrants)
    # Keep as NaN — these rows will be dropped to avoid poisoning the model
    # with an arbitrary 0 for players whose true prior is unknown

    # Drop rows with NaN in required features (snap NaN is allowed — XGBoost handles it)
    dropna_features = [f for f in active_features if f not in SNAP_FEATURES]
    train_clean = train.dropna(subset=dropna_features)
    holdout_clean = holdout.dropna(subset=dropna_features)
    dropped_train = len(train) - len(train_clean)
    dropped_holdout = len(holdout) - len(holdout_clean)
    if dropped_train:
        print(f'  Dropped {dropped_train} train rows with NaN features')
    if dropped_holdout:
        print(f'  Dropped {dropped_holdout} holdout rows with NaN features')

    X_train = train_clean[active_features].values
    y_train = train_clean['scored_td'].values
    X_holdout = holdout_clean[active_features].values
    y_holdout = holdout_clean['scored_td'].values

    eb_params = {'alpha': alpha, 'beta': beta}
    if use_new_features:
        eb_params['rz_alpha'] = rz_alpha
        eb_params['rz_beta'] = rz_beta

    return X_train, y_train, X_holdout, y_holdout, train_clean, holdout_clean, eb_params


if __name__ == '__main__':
    X_tr, y_tr, X_ho, y_ho, tr_df, ho_df, eb = load_and_prepare()
    print(f'\nX_train shape: {X_tr.shape}')
    print(f'X_holdout shape: {X_ho.shape}')
    print(f'\ntd_rate_eb percentiles (train):')
    for p in [10, 25, 50, 75, 90, 95, 99]:
        idx = int(len(tr_df) * p / 100)
        val = np.sort(tr_df['td_rate_eb'].values)[idx]
        print(f'  {p}th: {val:.4f}')
