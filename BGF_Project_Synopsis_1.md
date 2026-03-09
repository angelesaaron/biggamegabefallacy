# Big Game Gabe Fallacy — Project Synopsis

> Last updated: March 2026

---

## What We're Building

A solo-developed NFL prop betting app that predicts which wide receivers and tight ends will score an **anytime touchdown (ATTD)** in a given week. The core product is a probability engine backed by an XGBoost ML model, served via a **FastAPI** backend, with a **Next.js** frontend and a **PostgreSQL** database.

**End goal:** 2026 NFL season launch behind a paywall. Auth/payments are intentionally deferred — last on the priority list.

**Priority order:**
1. ML model ✅
2. Data model cleanup
3. Backend reliability
4. Frontend improvements
5. Auth / paywall

---

## Where We Currently Stand

### ML Model (v2 — complete)

The original model was badly overfit: trained only on WRs, evaluated on training data, unlimited tree depth, no class weighting. Rebuilt from scratch.

**BGGTDM v2:**
- Unifies WRs and TEs with a position flag
- XGBoost with probability calibration (BetaCalibration)
- Final metrics:

| Metric | Value | Target | Status |
|---|---|---|---|
| AUC | 0.737 | ≥ 0.72 | ✅ |
| Brier Score | 0.1425 | ≤ 0.14 | ⚠️ ceiling |
| TD Recall @20% | 0.424 | ≥ 0.40 | ✅ |
| Snap Match Rate | 90.1% | ≥ 85% | ✅ |

Brier score is a theoretical ceiling issue given class imbalance (~17% TD rate) — not a fixable bug at current model complexity.

**Artifact:** `ml/model/wr_te_model_v2.pkl`
**2025 season data** is reserved as the true holdout test set.

---

### Backend (`backend_new` — built, under review)

Full phased rebuild replacing the original backend — new data model, new services, new everything.

#### Phase Review Status

| Phase | Description | Status | Notes |
|---|---|---|---|
| Phase 2 | Ingest pipeline | ✅ Solid | Tank01 returns one consensus line per player; `sportsbook='consensus'` is correct |
| Phase 3 | Feature computation | ✅ Strong | Faithfully translates `feature_prep.py` + `early_season.py` |
| Phase 4 | ML inference | ✅ Reviewed | Pre-existing bug in `model_bundle.py` |

#### Bugs (both resolved ✅)

| Bug | Fix |
|---|---|
| Phase 3: `target_share` aggregated from `player.team` instead of `log.team` | Fixed — now uses per-game team |
| `model_bundle.py` `get_eb_params()` wrong key names | Fixed — correct `alpha_eb` / `beta_eb` suffixes |

#### Additional Fixes (session Mar 2026)

| Issue | Fix |
|---|---|
| Migration 0004 failed on fresh DB | Added `IF EXISTS` guard |
| `_SNAP_FEATURES` missing RZ features | Added 3 RZ features — no more false-positive error logs |
| `/health` didn't check model load | Added `model_loaded` field |
| `odds_sync.py` silent FK failures | Docstring ordering note added |
| `render.yaml` missing | Created with pre-deploy alembic command |
| `.env.example` missing `NFLVERSE_CACHE_DIR` | Added with Render disk note |
| Batch scripts missing `await db.commit()` | Fixed in both scripts — writes were silently rolling back |
| 2023–2025 wk1–3 rookies using UDFA bucket | Recomputed with correct draft-round buckets |

#### Overall Assessment: A

All known bugs resolved. 140/140 tests passing. Backend is in solid shape.

---

### Local DB State

| Item | Status |
|---|---|
| Schema | At head, fully in sync with models ✅ |
| Predictions | 17,949 rows across 2022–2025, all 18 weeks ✅ |
| 2023–2025 wk1–3 rookies | Correctly use per-draft-round buckets ✅ |
| 2022 wk1–3 rookies | Still rd0 — no 2021 season state, historical only, not worth fixing |
| Tests | 140/140 passing ✅ |
| Server | Running — `/health` returns `{"status":"ok","db":"ok","model_loaded":true}` ✅ |

### Frontend

Not yet updated to point at `backend_new`. Still wired to the old backend. Public API route review needed before cutover — deferred.

---

## Ideal Data Ingestion Workflow

The pipeline runs **weekly, Tuesday midday** — after Monday Night Football wraps, before Thursday Night kickoff. The entire chain is **fully idempotent**: any step can be re-run without corrupting state. All 9 admin endpoints are wired; the Tuesday batch sequence is manual by design:

```
roster → draft → gamelogs → odds → features → predictions
```

```
Tank01 API                nfl_data_py
     │                        │
     ▼                        ▼
[1] Schedule Sync      [3] Game Log Ingest
[2] Roster Sync             │
     │                      │
     └──────────┬───────────┘
                ▼
        [4] Feature Computation
          ┌─────────────────────┐
          │ Weeks 1–3 (Early)   │
          │  - Carry forward    │
          │    prior season     │
          │  - Team-changers:   │
          │    zero volume feats│
          │  - Rookies: draft   │
          │    round bucket med │
          └─────────────────────┘
          ┌─────────────────────┐
          │ Weeks 4–18 (Live)   │
          │  - Rolling 3-game   │
          │  - Cumulative stats │
          │  - EB shrinkage     │
          └─────────────────────┘
                ▼
        [5] Season State (end of season)
                ▼
        [6] ML Inference
          - Load wr_te_model_v2.pkl
          - Score all WR/TE for the week
          - Store final_prob in predictions
          - model_odds NOT stored (derived at query time)
                ▼
        [7] Odds Sync
          - Pull consensus ATTD lines from Tank01
          - Upsert as sportsbook='consensus'
```

### Step Details

| Step | Service | Source | Output Table |
|---|---|---|---|
| 1. Schedule sync | `ScheduleSyncService` | Tank01 | `games` |
| 2. Roster sync | `RosterSyncService` | Tank01 `getNFLTeamRoster?getStats=true` | `players` |
| 3. Game log ingest | `GameLogSyncService` | `nfl_data_py` | `player_game_logs` |
| 4. Feature computation | `FeatureComputeService.run(season, week)` | `player_game_logs` | `player_week_features` |
| 5. Season state | `SeasonStateService.run(season)` | `player_game_logs` | `player_season_state` |
| 6. ML inference | `PredictionService` | `player_week_features` + pkl | `predictions` |
| 7. Odds sync | `OddsSyncService` | Tank01 betting endpoint | `player_props` |

### Early Season Architecture (Weeks 1–3)

| Player Type | Volume Features | Skill Features |
|---|---|---|
| Returning player | Carry forward from prior season end state | Carry forward |
| Team-changer | Zero out | Preserve (e.g. `td_rate_eb`) |
| Rookie | Draft-round + position bucket medians | Same medians |

Hard cutover to live features at **Week 4** — no blending, avoids distribution shift.

---

## What's Left Before Frontend Cutover

1. **Render deploy** — `render.yaml` is ready; just needs env vars set in Render dashboard and new service pointed at `backend_new/`
2. **Public API review** — haven't verified public routes match what the frontend needs (deferred)
3. **2026 live season data** — local DB has 2025 backfilled for holdout validation; live pipeline needs a fresh run when the season starts

---

## Key Design Decisions

- **Single model pkl** for both early-season and in-season paths — same XGBoost + calibration, no distribution shift risk
- **`model_odds` not stored** — `final_prob` is stored; `model_odds` is deterministic math derived at query time
- **`sportsbook='consensus'`** — Tank01 returns one consensus line per player, not per-sportsbook breakdowns
- **`player_week_features` table** — feature computation lives in DB, not computed on-the-fly at prediction time
- **2025 season as true holdout** — never used in training or validation

---

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python) |
| Frontend | Next.js |
| Database | PostgreSQL |
| ML | XGBoost + BetaCalibration |
| Data (historical) | `nfl_data_py` |
| Data (live/odds) | Tank01 API |

---

## File Locations

```
biggamegabefallacy/
├── ml/
│   ├── model/wr_te_model_v2.pkl
│   ├── feature_prep.py
│   ├── train.py
│   ├── calibrate.py
│   ├── evaluate.py
│   ├── early_season.py
│   ├── ML_Early_Season.md
│   └── ML_v2_Final_Steps.md
├── backend_new/
│   └── app/
│       ├── models/
│       ├── services/
│       │   ├── feature_compute.py
│       │   ├── season_state_service.py
│       │   ├── roster_sync.py
│       │   ├── schedule_sync.py
│       │   └── odds_sync.py
│       ├── ml/
│       │   └── model_bundle.py   ← bug: get_eb_params() wrong key names
│       └── api/
└── frontend/  ← still pointed at old backend
```
