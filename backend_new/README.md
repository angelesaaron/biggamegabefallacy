# BGGTDM API v2

FastAPI backend for the Big Game Gabe TD Model — an NFL anytime touchdown prediction system for WR/TE players.

---

## Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI + Uvicorn |
| Database | PostgreSQL (asyncpg) |
| ORM / Migrations | SQLAlchemy 2.0 async + Alembic |
| ML | XGBoost + beta calibration (scikit-learn / betacal) |
| Data sources | Tank01 NFL API (via RapidAPI), nflverse PBP parquet |
| Config | pydantic-settings v2 |

---

## Project Structure

```
backend_new/
├── app/
│   ├── api/
│   │   ├── admin.py          # Admin/pipeline endpoints (X-Admin-Key required)
│   │   └── public.py         # Public prediction + player endpoints
│   ├── ml/
│   │   ├── feature_math.py   # Shared feature computation logic
│   │   └── model_bundle.py   # pkl bundle loader (cached after first load)
│   ├── models/               # SQLAlchemy ORM models (one file per table)
│   ├── services/             # Business logic — one service per pipeline step
│   ├── utils/
│   │   ├── odds_utils.py     # American odds ↔ implied probability
│   │   ├── tank01_client.py  # Async HTTP client for Tank01 API
│   │   └── nflverse_adapter.py # nflverse parquet fetcher (snap + RZ data)
│   ├── config.py             # Settings (pydantic-settings v2)
│   ├── database.py           # Engine, session factory, get_db dependency
│   └── main.py               # FastAPI app, middleware, lifespan
├── alembic/
│   └── versions/
│       ├── 0001_initial_schema.py   # All 11 tables
│       └── 0002_player_season_state_fixes.py
├── .env.example
├── alembic.ini
└── requirements.txt
```

---

## Setup

### 1. Environment

```bash
cp .env.example .env
# Fill in real values — see Environment Variables below
```

### 2. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Run migrations

```bash
alembic upgrade head
```

### 4. Start the server

```bash
uvicorn app.main:app --reload        # development
uvicorn app.main:app --host 0.0.0.0  # production
```

The `/health` endpoint confirms the server and DB are both reachable.

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Description |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host:5432/dbname` |
| `TANK01_API_KEY` | RapidAPI key for Tank01 NFL API |
| `ADMIN_KEY` | Secret for all `/admin/*` endpoints. Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `MODEL_PATH` | Path to the XGBoost pkl bundle (relative to `backend_new/` or absolute) |
| `MODEL_VERSION` | Version string written to every prediction row (e.g. `v2_xgb`) |
| `CORS_ORIGINS` | JSON array of allowed origins: `["https://yoursite.com"]` |
| `DEBUG` | `true` enables SQL echo and `/docs` + `/redoc` |

> **Note:** `CORS_ORIGINS` must be a JSON array string, not comma-separated.

---

## Data Pipeline

All pipeline steps are discrete and manually triggered via admin endpoints. No step auto-cascades into the next — a failure in one step cannot silently corrupt downstream data.

### Weekly workflow (regular season)

```
1. POST /admin/sync/roster                    # Once per season (or after trades)
2. POST /admin/sync/schedule/{season}         # Re-run weekly to pick up final game status
3. POST /admin/ingest/gamelogs/{season}/{week}
4. POST /admin/sync/odds/{season}/{week}      # Optional — anytime during game week
5. POST /admin/compute/features/{season}/{week}
6. POST /admin/run/predictions/{season}/{week}
```

### End-of-season workflow

```
POST /admin/compute/season-state/{season}    # After all game logs ingested
```

Writes carry-forward state used by the early-season feature pipeline (weeks 1–3) the following year.

### One-time seeds (run after initial migration)

```
POST /admin/seed/rookie-buckets    # Populate rookie draft-round buckets
POST /admin/aliases/seed           # Seed known Tank01 → nflverse name mismatches
```

All admin endpoints require the `X-Admin-Key` header matching `ADMIN_KEY`.
All admin endpoints return a `SyncResult` — `n_written`, `n_updated`, `n_skipped`, `n_failed`, `events`.
All writes are idempotent — safe to re-run.

---

## Public API

No authentication required.

| Endpoint | Description |
|---|---|
| `GET /health` | Server + DB status |
| `GET /predictions/{season}/{week}` | Ranked TD predictions. Filters: `?position=WR&team=KC` |
| `GET /players` | Active WR/TE roster. Filters: `?position=TE&team=SF` |
| `GET /players/{player_id}` | Single player |
| `GET /players/{player_id}/history` | All predictions for a player. Filter: `?season=2025` |

**Computed fields** (derived at query time, not stored):
- `model_odds` — American odds from `final_prob`
- `favor` — `final_prob − market implied_prob` (positive = model sees edge)

---

## Database Schema

11 tables managed by Alembic:

| Table | Description |
|---|---|
| `players` | Canonical WR/TE identity (Tank01 player_id as PK) |
| `games` | Regular season schedule |
| `player_game_log` | Per-player per-game box score stats |
| `team_game_stats` | Per-team per-game totals (for target share denominators) |
| `player_aliases` | Tank01 → nflverse name mappings |
| `rookie_buckets` | Median rookie stats by draft round + position |
| `player_season_state` | End-of-season carry-forward features for early-season pipeline |
| `player_features` | Computed model input features per player per week |
| `predictions` | Model output — raw, calibrated, and final probabilities |
| `sportsbook_odds` | Market odds (American format + implied prob) |
| `data_quality_events` | Alias match failures and other pipeline data issues |

---

## ML Model

The XGBoost bundle (`wr_te_model_v2.pkl`) is loaded at startup and cached in memory.

**Feature computation** (`app/services/feature_compute.py`):
- Weeks 4+: computed from in-season game logs (rolling stats, EB rates)
- Weeks 1–3 (early season): resolved from carry-forward state, team-changer logic, or rookie buckets

**Inference** (`app/services/inference_service.py`):
- XGBoost prediction → beta calibration (or temperature scaling) → early-season week scalar
- All CPU-bound work runs in `asyncio.to_thread()` to avoid blocking the event loop

**Empirical Bayes TD rates**: `alpha`/`beta` parameters are read from the bundle — never refit at runtime.

---

## Migrations

```bash
alembic upgrade head          # Apply all migrations
alembic downgrade -1          # Roll back one migration
alembic upgrade --sql head    # Print DDL SQL without connecting (validation)
```

To add a new migration:
```bash
alembic revision -m "description"
# Edit the generated file in alembic/versions/
```

Auto-generation (`--autogenerate`) is not used — migrations are written by hand to keep full control over type choices and index names that services reference by name in upsert constraints.
