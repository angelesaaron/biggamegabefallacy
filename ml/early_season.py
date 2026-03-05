"""
early_season.py — Feature resolver for weeks 1-3.

Resolves feature values for weeks where rolling features are thin or absent.

Priority:
  1. Player has prior-season row + same team → carry-forward
  2. Player has prior-season row + different team → positional mean (volume zeroed)
  3. Player has no prior-season row (rookie / new entrant) → draft-round bucket

Call load_early_season_priors() once, then resolve_early_features() per week.
"""

import numpy as np
import pandas as pd

PRIOR_PATH = 'data/prior_season_final_state.csv'
BUCKETS_PATH = 'data/rookie_buckets.csv'

# Volume features reset for team-changers (new system, unknown role)
# Skill / rate features (td_rate_eb) are kept — ability travels
VOLUME_FEATURES = [
    'targets_pg', 'yards_pg', 'receptions_pg',
    'roll3_targets', 'roll3_yards', 'roll3_receptions',
    'lag_targets', 'lag_yards',
    'target_share',
    'roll3_rz_targets', 'rz_target_share',
    'lag_snap_pct', 'roll3_snap_pct',
]

# Full carry-forward feature set (must match FEATURES in feature_prep.py)
CARRY_FEATURES = VOLUME_FEATURES + [
    'roll3_long_rec',
    'roll3_target_std',
    'tds_last3',
    'td_streak',
    'td_rate_eb',
    'td_rate_eb_std',
    'rz_td_rate_eb',
]


def apply_week_scalar(probs, week, scalars):
    """
    Apply the early-season week-group scalar from the model bundle to raw
    beta-calibrated probabilities.

    Parameters
    ----------
    probs : array-like
        Beta-calibrated probabilities from the model.
    week : int
        Current week number.
    scalars : dict
        bundle['early_season_scalars'] — keys: 'wk1', 'wk2_3', 'wk4_plus'.

    Returns
    -------
    np.ndarray of clipped corrected probabilities.
    """
    probs = np.array(probs, dtype=float)
    if week == 1:
        s = scalars.get('wk1', 1.0)
    elif week <= 3:
        s = scalars.get('wk2_3', 1.0)
    else:
        s = scalars.get('wk4_plus', 1.0)
    corrected = np.clip(probs * s, 0.0, 1.0)
    if s != 1.0:
        print(f'Week {week} scalar applied: {s:.3f}  '
              f'(mean before={probs.mean():.1%}, after={corrected.mean():.1%})')
    return corrected


def load_early_season_priors(prior_path=PRIOR_PATH, buckets_path=BUCKETS_PATH):
    """Load prior-season carry-forward state and rookie draft-round buckets."""
    prior = pd.read_csv(prior_path)
    buckets = pd.read_csv(buckets_path)
    return prior, buckets


def resolve_early_features(players_df, season, week, prior_df, bucket_df):
    """
    Resolve model feature values for an early-season week (1-3).

    Parameters
    ----------
    players_df : DataFrame
        Current week's player list. Required columns:
        player_id, name, pos, team, is_te, draft_round (int, 0=undrafted)
    season : int
        Current season year (e.g. 2026)
    week : int
        Must be <= 3
    prior_df : DataFrame
        Loaded from prior_season_final_state.csv
    bucket_df : DataFrame
        Loaded from rookie_buckets.csv

    Returns
    -------
    DataFrame with all model features filled. Includes a 'resolution' column
    indicating how each row was resolved: 'carry_forward', 'team_changer', 'rookie'.
    """
    assert week <= 3, f'resolve_early_features is only for weeks 1-3, got week={week}'

    players_df = players_df.copy()

    # Filter prior to rows that join into this season (prior season = season - 1)
    prior_this_season = prior_df[prior_df['join_season'] == season].copy()

    merged = players_df.merge(
        prior_this_season,
        on='player_id',
        how='left',
        suffixes=('', '_prior')
    )

    # ---- Determine resolution category ----
    has_prior = merged['targets_pg'].notna()

    # team column: current team from players_df, prior team from prior row
    # After merge with suffix='_prior', current team is 'team', prior team is 'team_prior'
    team_changed = (
        has_prior &
        merged['team_prior'].notna() &
        (merged['team'] != merged['team_prior'])
    )

    carry_forward = has_prior & ~team_changed
    is_rookie = ~has_prior  # no prior row at all

    merged['resolution'] = 'unknown'
    merged.loc[carry_forward, 'resolution'] = 'carry_forward'
    merged.loc[team_changed, 'resolution'] = 'team_changer'
    merged.loc[is_rookie, 'resolution'] = 'rookie'

    # ---- Team-changers: zero out volume features, keep rate features ----
    for col in VOLUME_FEATURES:
        if col in merged.columns:
            merged.loc[team_changed, col] = np.nan  # XGBoost handles NaN natively

    # ---- Rookies: fill from draft_round + pos bucket ----
    if is_rookie.any():
        rookie_rows = merged[is_rookie][['player_id', 'draft_round', 'pos']].copy()
        rookie_filled = rookie_rows.merge(
            bucket_df,
            on=['draft_round', 'pos'],
            how='left'
        )
        # Apply bucket values for all carry features
        for col in CARRY_FEATURES:
            if col in rookie_filled.columns:
                merged.loc[is_rookie, col] = rookie_filled[col].values

    # ---- Logging ----
    n_carry = carry_forward.sum()
    n_changed = team_changed.sum()
    n_rookie = is_rookie.sum()
    print(
        f'Week {week} resolution: '
        f'{n_carry} carry-forward | '
        f'{n_changed} team-changers | '
        f'{n_rookie} rookies/no-prior'
    )

    if n_changed > 0:
        changers = merged.loc[team_changed, ['name', 'team_prior', 'team']]
        print('Team-changers (volume features zeroed, rate features kept):')
        print(changers.to_string(index=False))

    if n_rookie > 0:
        bucket_miss = merged.loc[is_rookie & merged['targets_pg'].isna(), 'name']
        if len(bucket_miss) > 0:
            print(f'WARNING: {len(bucket_miss)} rookies had no bucket match (NaN features):')
            print(bucket_miss.tolist())

    # Drop the prior team column to keep output clean
    if 'team_prior' in merged.columns:
        merged.drop(columns=['team_prior'], inplace=True)

    return merged
