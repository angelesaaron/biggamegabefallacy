# BGGTDM v2 — Data Model Brainstorm
*Clean slate. No legacy constraints. Built around what the model actually needs.*

---

## Ground Truth: What the Model Needs

The v2 XGBoost model has 21 features. Every design decision flows from making those 21 features
reliably available, per player, per week, without fragile on-the-fly computation.

**From Tank01 box score (easy, 16 calls/week):**
targets, receptions, rec_yards, rec_tds, long_rec

**From nflverse PBP (the historic pain point):**
snap_count, snap_pct, rz_targets, rz_tds

**Derived (need team totals to exist first):**
target_share, rz_target_share

**Modeled/computed:**
td_rate_eb, rz_td_rate_eb, td_rate_eb_std, roll3_*, lag_*, tds_last3, td_streak

**Static player attributes:**
is_te, draft_round

---

## The Root Cause of All Prior Pain

The snap/RZ data came from a completely separate source (nflverse) using player *names*
as the join key to Tank01 *numeric IDs*. Name mismatches = silent NaN = model getting
garbage features with no visibility into it. ~10% NaN rate on the two snap features,
unknown NaN rate on RZ features.

The fix is not better fuzzy matching at runtime. The fix is a persistent alias table
that is built once, audited, and queried deterministically. Failed matches emit
a logged data quality event — they never silently produce a NULL in a feature row.

---

## The 8 Tables

### 1. `players`
*Identity. Written by roster sync. Rarely mutated.*

| Column | Type | Notes |
|---|---|---|
| player_id | TEXT PK | Tank01 numeric ID — this is canonical |
| full_name | TEXT | Tank01 longName |
| position | TEXT | WR or TE |
| team | TEXT | Current team abbreviation |
| is_te | BOOL | Derived from position, stored for convenience |
| draft_round | INT | 0 = undrafted/UDFA, NULL = unknown |
| experience | INT | Years in NFL (0 = rookie) |
| active | BOOL | False when cut/retired |
| headshot_url | TEXT | |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

**What changed from v1:** Added `is_te`, `draft_round`, `experience`.
Removed string fields for height/weight/age that were never used anywhere.

---

### 2. `player_aliases`
*The fix for the name matching problem. Written once, maintained as exceptions arise.*

| Column | Type | Notes |
|---|---|---|
| player_id | TEXT FK → players | Tank01 ID |
| source | TEXT | 'nflverse', 'sleeper', 'espn' |
| alias_name | TEXT | Name as it appears in that source |
| match_type | TEXT | 'exact', 'manual', 'fuzzy' |
| active | BOOL | Inactive if player left source |
| created_at | TIMESTAMPTZ | |

**Unique constraint:** (player_id, source)

This is a small table — ~600 rows for all active WR/TE. Built once during backfill,
then maintained by the data quality pipeline when new match failures appear.
Every nflverse join goes through this table. Zero guessing at runtime.

---

### 3. `games`
*One row per NFL game. Written by schedule sync.*

| Column | Type | Notes |
|---|---|---|
| game_id | TEXT PK | Tank01 format: YYYYMMDD_AWAY@HOME |
| season | INT | |
| week | INT | |
| season_type | TEXT | 'reg', 'post', 'pre' |
| home_team | TEXT | |
| away_team | TEXT | |
| game_date | DATE | |
| status | TEXT | 'scheduled', 'final', 'in_progress' |
| updated_at | TIMESTAMPTZ | |

**What changed from v1:** Simplified. Removed unused team_id fields.
`game_date` is a proper DATE not a string.

---

### 4. `player_game_logs`
*Raw box score stats per player per game. Written by ingest. Never mutated after game is final.*

| Column | Type | Notes |
|---|---|---|
| id | BIGINT PK | |
| player_id | TEXT FK → players | |
| game_id | TEXT FK → games | |
| season | INT | Denormalized for query efficiency |
| week | INT | Denormalized for query efficiency |
| team | TEXT | Team player was on for this game |
| is_home | BOOL | Derived from game |
| targets | INT | |
| receptions | INT | |
| rec_yards | INT | |
| rec_tds | INT | |
| long_rec | INT | Nullable |
| snap_count | INT | Nullable — from nflverse via alias table |
| snap_pct | NUMERIC(4,3) | Nullable — from nflverse |
| rz_targets | INT | Nullable — from nflverse PBP |
| rz_rec_tds | INT | Nullable — from nflverse PBP, TDs from RZ ≤20yd |
| data_source_flags | JSONB | Which sources successfully populated this row |
| created_at | TIMESTAMPTZ | |

**Unique constraint:** (player_id, game_id)

**What changed from v1:** Added snap_count, snap_pct, rz_targets, rz_rec_tds directly
onto the game log row. No separate tables, no joins at feature time. The ingest pipeline
resolves all sources and writes one complete row.

`data_source_flags` looks like: `{"tank01": true, "nflverse_snap": true, "nflverse_rz": false}`
This is how you audit data completeness per row without a separate log table for every game.

---

### 5. `team_game_stats`
*Aggregated team totals per game. Derived from player_game_logs. Enables share features.*

| Column | Type | Notes |
|---|---|---|
| id | BIGINT PK | |
| game_id | TEXT FK → games | |
| team | TEXT | |
| season | INT | |
| week | INT | |
| team_targets | INT | Sum of all player targets for this team in this game |
| team_rec_tds | INT | |
| team_rz_targets | INT | Nullable — only populated when RZ data available |
| team_rz_tds | INT | Nullable |
| created_at | TIMESTAMPTZ | |

**Unique constraint:** (game_id, team)

This table is what makes `target_share = player_targets / team_targets` and
`rz_target_share = player_rz_targets / team_rz_targets` computable entirely from
the database. Previously these required CSVs and Pandas. Now they're a SQL join.

Written by the same ingest job that finalizes `player_game_logs` for a completed week.

---

### 6. `player_features`
*Pre-computed model features. The most important new table.*

| Column | Type | Notes |
|---|---|---|
| id | BIGINT PK | |
| player_id | TEXT FK → players | |
| season | INT | |
| week | INT | The week these features are FOR (predict this week using these) |
| feature_version | TEXT | e.g. 'v2' — allows re-computation without destroying history |
| — | | **All 21 model features below** |
| targets_pg | NUMERIC | |
| roll3_targets | NUMERIC | |
| yards_pg | NUMERIC | |
| roll3_yards | NUMERIC | |
| receptions_pg | NUMERIC | |
| roll3_receptions | NUMERIC | |
| lag_targets | NUMERIC | |
| lag_yards | NUMERIC | |
| target_share | NUMERIC | |
| roll3_long_rec | NUMERIC | |
| roll3_target_std | NUMERIC | |
| tds_last3 | NUMERIC | |
| td_streak | INT | |
| td_rate_eb | NUMERIC | |
| td_rate_eb_std | NUMERIC | |
| is_te | BOOL | |
| lag_snap_pct | NUMERIC | Nullable |
| roll3_snap_pct | NUMERIC | Nullable |
| roll3_rz_targets | NUMERIC | Nullable |
| rz_target_share | NUMERIC | Nullable |
| rz_td_rate_eb | NUMERIC | Nullable |
| — | | **Metadata** |
| is_early_season | BOOL | True for weeks 1-3 |
| carry_forward_used | BOOL | True if features came from prior season state |
| completeness_score | NUMERIC(3,2) | Fraction of non-null features (0.00–1.00) |
| computed_at | TIMESTAMPTZ | |

**Unique constraint:** (player_id, season, week, feature_version)

**This is the architectural shift.** Prediction is no longer "compute features on the fly
from raw game logs at request time." It's "read a pre-validated row from this table,
run inference, done." Feature computation runs as a discrete pipeline step after
game log ingest completes, validates output (no NaN in required features,
completeness_score logged), and stamps each row.

Predictions for players with `completeness_score < 0.75` get flagged as low-confidence.

---

### 7. `player_season_state`
*End-of-season carry-forward state. Replaces prior_season_final_state.csv.*

| Column | Type | Notes |
|---|---|---|
| id | BIGINT PK | |
| player_id | TEXT FK → players | |
| season | INT | The season this state represents |
| join_season | INT | season + 1 — the season this is used for |
| team | TEXT | Team at end of season |
| draft_round | INT | |
| — | | **All carry-forward feature values** |
| targets_pg | NUMERIC | |
| yards_pg | NUMERIC | |
| receptions_pg | NUMERIC | |
| roll3_targets | NUMERIC | |
| roll3_yards | NUMERIC | |
| roll3_receptions | NUMERIC | |
| lag_targets | NUMERIC | |
| lag_yards | NUMERIC | |
| target_share | NUMERIC | |
| roll3_long_rec | NUMERIC | |
| roll3_target_std | NUMERIC | |
| tds_last3 | INT | |
| td_streak | INT | |
| td_rate_eb | NUMERIC | |
| td_rate_eb_std | NUMERIC | |
| lag_snap_pct | NUMERIC | Nullable |
| roll3_snap_pct | NUMERIC | Nullable |
| roll3_rz_targets | NUMERIC | Nullable |
| rz_target_share | NUMERIC | Nullable |
| rz_td_rate_eb | NUMERIC | |
| created_at | TIMESTAMPTZ | |

**Unique constraint:** (player_id, season)

Written by an end-of-season job. Read by the early-season feature pipeline when
`is_early_season = true` and no in-season game logs exist yet.

---

### 8. `predictions`
*One row per player per week. Model output. Immutable after creation.*

| Column | Type | Notes |
|---|---|---|
| id | BIGINT PK | |
| player_id | TEXT FK → players | |
| season | INT | |
| week | INT | |
| model_version | TEXT | 'v2_xgb_beta' — explicit |
| feature_row_id | BIGINT FK → player_features | The exact features that drove this |
| raw_prob | NUMERIC(6,5) | Pre-calibration XGBoost output |
| calibrated_prob | NUMERIC(6,5) | Post-beta-calibration |
| week_scalar | NUMERIC(5,4) | Early-season scalar applied (1.0 for wks 4+) |
| final_prob | NUMERIC(6,5) | calibrated_prob × week_scalar — what the UI shows |
| completeness_score | NUMERIC(3,2) | Copied from player_features |
| is_low_confidence | BOOL | True if completeness_score < 0.75 |
| created_at | TIMESTAMPTZ | |

**Unique constraint:** (player_id, season, week, model_version)

**What changed from v1:** model_version is explicit. raw_prob and calibrated_prob
are stored separately — you can see the calibration effect. feature_row_id is an FK
to the exact feature row, so you can always reconstruct what drove a prediction.
`model_odds` and `favor` are gone — these are computed at query time from final_prob,
not stored. They're math, not data.

---

### Bonus: `sportsbook_odds`
*Keep mostly as-is from v1, minor additions.*

| Column | Notes |
|---|---|
| player_id | FK → players |
| game_id | FK → games |
| season | |
| week | |
| sportsbook | 'draftkings', 'fanduel', 'betmgm', 'bovada' |
| odds | American format |
| implied_prob | NUMERIC — computed on write: 1 / (1 + 100/abs(odds)) |
| fetched_at | TIMESTAMPTZ |

**Unique constraint:** (player_id, game_id, sportsbook)

`implied_prob` computed and stored on write. When the UI queries for edge
(model_prob vs market_prob), it's a direct numeric comparison — no conversion logic needed.

---

### Bonus: `data_quality_events`
*Replaces silent failures. Written by ingest pipeline whenever something goes wrong.*

| Column | Notes |
|---|---|
| id | BIGINT PK |
| event_type | 'alias_match_failure', 'null_snap_pct', 'null_rz_data', 'low_completeness', 'prediction_skipped' |
| player_id | Nullable FK |
| game_id | Nullable FK |
| season | |
| week | |
| detail | TEXT — what specifically failed |
| auto_resolvable | BOOL — can the pipeline retry this? |
| resolved_at | Nullable TIMESTAMPTZ |
| created_at | TIMESTAMPTZ |

A batch run summary can query this table and surface: "8 alias match failures this week —
these players have null snap features." You fix the alias table, re-run the feature job,
and the null snaps go away. No more invisible model degradation.

---

## Pipeline Flow (Clean)

```
1. SCHEDULE SYNC
   Tank01 → games table
   ~16 API calls/week, idempotent

2. GAME LOG INGEST (after games are final)
   Tank01 box score → player_game_logs (targets, rec, yards, tds, long_rec)
   nflverse (via player_aliases) → player_game_logs (snap_pct, rz_targets, rz_tds)
   Aggregate → team_game_stats
   Failures → data_quality_events
   ~16 API calls/week for Tank01, 0 API calls for nflverse (local data)

3. FEATURE COMPUTATION
   player_game_logs + team_game_stats → player_features
   Weeks 1-3: reads player_season_state instead of game logs
   Validates completeness_score per row
   0 API calls

4. PREDICTION
   player_features → XGBoost inference → predictions
   0 API calls

5. ODDS SYNC
   Tank01 → sportsbook_odds (with implied_prob on write)
   ~16 API calls/week

6. END OF SEASON
   player_features (final week) → player_season_state
   0 API calls
```

---

## Backfill Path (Using Existing CSVs)

The historical CSVs become the seed data:

| CSV | Target table | Notes |
|---|---|---|
| game_logs_2022/23/24/25.csv | player_game_logs | Direct columns map, snap/rz from enriched |
| game_logs_enriched.csv | player_game_logs + team_game_stats | Has all 66 columns including snap and rz |
| game_logs_features.csv | player_features | Nearly direct — already computed features |
| prior_season_final_state.csv | player_season_state | Direct column map |
| rookie_buckets.csv | No table needed — baked into feature computation code |
| anytime_td_odds.csv | sportsbook_odds | Historical odds |

The enriched CSV is the richest asset — 9,972 rows, 66 columns. A single backfill script
reads it and populates `player_game_logs`, `team_game_stats`, and `player_features` in one pass.
This gives the new DB full historical coverage from day one with zero API calls.

---

## What This Solves vs Prior Architecture

| Problem | Before | After |
|---|---|---|
| Snap NaN rate ~10% | Silent NaN in features | Alias table + data_quality_events |
| RZ data not in DB | CSV-only, Pandas join | player_game_logs columns + team_game_stats |
| Target share not computable | Required CSV team aggregates | team_game_stats enables SQL join |
| Features computed at request time | Fragile, no audit trail | player_features: pre-computed, validated |
| Early-season state in CSV file | Can't query/audit | player_season_state table |
| No model versioning | Can't compare v1 vs v2 | predictions.model_version + feature_row_id |
| Prediction not debuggable | Black box | feature_row_id FK to exact inputs |
| model_odds/favor stored | Math stored as data | Computed at query time from final_prob |
| Old feature engineering code | 11-feature v1 pipeline still running | Full rebuild, v2 only |
