# Admin Dashboard — Phase 2: Pipeline Actions + Week Override

## Phase 1 Status: Fully Complete ✅

Verified correct implementations:
- `is_admin` on User model + migration 0008 ✅
- `require_admin_user` dep, JWT claim, MeResponse ✅
- `admin_users.py` — all account management endpoints ✅
- `GET /api/admin-ui/health` — week-navigable with `season`/`week` query params, `WeekSummary`, `available_weeks`, `missing_game_log_players` week-scoped ✅
- Frontend `HealthPanel` — prev/next week navigation with ChevronLeft/ChevronRight, `WeekSummary` cards, correct auto-refresh behavior ✅
- Admin tab in NavBar (router.push `/admin`), sidebar layout ✅

**Latest migration:** `0008_add_is_admin.py` (`revision="0008"`, `down_revision="0007"`). Any new migration must use `down_revision="0008"`.

---

## Existing Infrastructure to Understand Before Starting

The existing `app/api/admin.py` router already has all pipeline endpoints, gated by `X-Admin-Key` header. **Do not touch this file.** Phase 2 adds new endpoints to `app/api/admin_users.py` (the JWT-gated admin-ui router) that proxy calls to the same underlying services.

Existing services and their signatures (all `async`, return `SyncResult`):
- `RosterSyncService(db, tank01).run()` — no season/week args
- `DraftSyncService(db).run(force_update=False)` — no season/week
- `ScheduleSyncService(db, tank01).run(season)` — season only
- `GameLogIngestService(db, tank01).run(season, week)`
- `OddsSyncService(db, tank01).run(season, week)`
- `FeatureComputeService(db).run(season, week)`
- `InferenceService(db).run(season, week)` — runs predictions
- `SeasonStateService(db).run(season)` — end-of-season only

`Tank01Client` is an async context manager: `async with Tank01Client() as tank01:`

`SyncResult` has: `n_written`, `n_updated`, `n_skipped`, `n_failed`, `events: list[str]`

`SyncResponse` Pydantic model and `_to_response()` helper already exist in `admin.py` — **copy them into `admin_users.py`** rather than importing cross-module (avoids coupling).

No `system_config` table exists yet — Phase 2 creates it.

---

## Phase 2 Scope

### Panel 3 — Pipeline Actions
### Panel 4 — Week Override

---

## Backend Changes

### 1. New migration — `system_config` table

Create `alembic/versions/0009_system_config.py`:

```python
"""Add system_config table.

Revision ID: 0009
Revises: 0008
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"

def upgrade() -> None:
    op.create_table(
        "system_config",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )

def downgrade() -> None:
    op.drop_table("system_config")
```

### 2. New model — `app/models/system_config.py`

```python
from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class SystemConfig(Base):
    __tablename__ = "system_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )
```

Key used for week override: `"current_week_override"` — value is `"2025:14"` (season:week) or `NULL` when cleared.

### 3. New endpoints in `app/api/admin_users.py`

Add these after the existing health endpoint. Copy `SyncResponse` model and `_to_response()` from `admin.py` into `admin_users.py` (do not import from admin.py).

---

#### Pipeline Action Endpoints

All pipeline endpoints:
- Use `require_admin_user` dep (JWT-gated, same as existing admin-ui endpoints)
- Return `SyncResponse`
- Are safe to re-run (idempotent) — no special warnings needed
- Call the same services as the X-Admin-Key endpoints in `admin.py`
- **Do NOT make Tank01/nflverse calls unless the specific action requires external data** — feature compute and inference are DB-only; roster/odds/gamelogs/schedule hit external APIs

```
POST /api/admin-ui/pipeline/roster
```
Calls `RosterSyncService`. Hits Tank01. No body params.

```
POST /api/admin-ui/pipeline/schedule/{season}
```
Calls `ScheduleSyncService(db, tank01).run(season)`. Hits Tank01.
Path param: `season` (int, 2020–2035)

```
POST /api/admin-ui/pipeline/gamelogs/{season}/{week}
```
Calls `GameLogIngestService`. Hits Tank01 + nflverse.
Path params: `season`, `week` (1–18)

```
POST /api/admin-ui/pipeline/odds/{season}/{week}
```
Calls `OddsSyncService`. Hits Tank01.
Path params: `season`, `week`

```
POST /api/admin-ui/pipeline/features/{season}/{week}
```
Calls `FeatureComputeService`. **DB only, no external calls.**
Path params: `season`, `week`

```
POST /api/admin-ui/pipeline/predictions/{season}/{week}
```
Calls `InferenceService`. **DB only, no external calls.**
Path params: `season`, `week`

---

#### Week Override Endpoints

```
GET /api/admin-ui/week-override
```
Response:
```python
class WeekOverrideResponse(BaseModel):
    override_active: bool
    season: int | None
    week: int | None
```
Read `system_config` row where `key="current_week_override"`. If row absent or value is NULL: `{override_active: false, season: null, week: null}`. If value is `"2025:14"`: `{override_active: true, season: 2025, week: 14}`.

```
POST /api/admin-ui/week-override
```
Request body:
```python
class WeekOverrideRequest(BaseModel):
    season: int = Field(..., ge=2020, le=2035)
    week: int = Field(..., ge=1, le=22)
```
Upsert `system_config` row with `key="current_week_override"`, `value=f"{season}:{week}"`. Use `pg_insert` with `on_conflict_do_update` — same pattern used elsewhere in the codebase. Return `WeekOverrideResponse`.

```
DELETE /api/admin-ui/week-override
```
Set `value=NULL` on the `system_config` row (or delete the row). Return `WeekOverrideResponse` with `override_active=False`.

---

### 4. Register routes — no change to `main.py` needed

The new endpoints are added to the existing `admin_users.py` router which is already mounted at `/api/admin-ui`.

---

### 5. Expose week override to the rest of the app — `app/services/week_resolver.py` (NEW)

Create a small utility so the public API can respect the override:

```python
"""
Resolve the current NFL week, respecting any admin override in system_config.

Usage:
    week, season = await resolve_current_week(db)
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.system_config import SystemConfig

async def resolve_current_week(db: AsyncSession) -> tuple[int, int]:
    """
    Returns (week, season).
    If system_config has a current_week_override, use that.
    Otherwise fall back to max(season)/max(week) from player_game_logs.
    """
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == "current_week_override")
    )
    row = result.scalars().first()
    if row and row.value:
        try:
            season_str, week_str = row.value.split(":")
            return int(week_str), int(season_str)
        except (ValueError, AttributeError):
            pass

    # Fallback: max from player_game_logs
    from app.models.player_game_log import PlayerGameLog
    from sqlalchemy import func
    season_res = await db.execute(
        select(func.max(PlayerGameLog.season))
    )
    season = season_res.scalar_one_or_none() or 2025
    week_res = await db.execute(
        select(func.max(PlayerGameLog.week))
        .where(PlayerGameLog.season == season)
    )
    week = week_res.scalar_one_or_none() or 1
    return week, season
```

**Important:** Do NOT wire this into existing public endpoints in this PR. Just create the file. Wiring it into `/api/status/week` and the health endpoint is a separate task.

---

## Frontend Changes

All changes are in `frontend/app/admin/page.tsx`.

### 1. Add `'pipeline' | 'week-override'` to the `Panel` type

```typescript
type Panel = 'accounts' | 'health' | 'pipeline' | 'week-override';
```

### 2. Add two new sidebar items

In the sidebar `ul`, add after the existing two items:
```typescript
{ id: 'pipeline', label: 'Pipeline' },
{ id: 'week-override', label: 'Week Override' },
```

Update the panel content area to render the new panels when active.

### 3. Pipeline Panel — `PipelinePanel` component

This panel has two sections: **DB-Only Actions** and **External API Actions**.

**UX pattern for each action:**
- A labeled button
- On click: button shows spinner/loading state and is disabled
- On complete: inline result card shows below the button with status, counts (written/updated/skipped/failed), and any events
- Result clears when you trigger a different action OR stays until dismissed — either is fine
- Actions do not auto-chain — each is independent

**Layout:** Two columns or two sections separated by a divider. Within each section, actions are stacked vertically with a button + optional inputs for season/week.

---

**Section 1 — DB Only (no external calls)**

These actions never hit Tank01 or nflverse. Make this clear in the UI ("No external API calls").

*Compute Features*
- Season input (number, default to current season from health data if available, else 2025)
- Week input (number 1–18)
- Button: "Compute Features"
- POST `/api/admin-ui/pipeline/features/{season}/{week}`

*Run Predictions*
- Season + week inputs (same defaults)
- Button: "Run Predictions"
- POST `/api/admin-ui/pipeline/predictions/{season}/{week}`

---

**Section 2 — External API (hits Tank01 / nflverse)**

Label this section with a subtle warning: "These actions fetch from external APIs."

*Sync Roster*
- No inputs needed
- Button: "Sync Roster"
- POST `/api/admin-ui/pipeline/roster`

*Sync Schedule*
- Season input only
- Button: "Sync Schedule"
- POST `/api/admin-ui/pipeline/schedule/{season}`

*Ingest Game Logs*
- Season + week inputs
- Button: "Ingest Game Logs"
- POST `/api/admin-ui/pipeline/gamelogs/{season}/{week}`

*Sync Odds*
- Season + week inputs
- Button: "Sync Odds"
- POST `/api/admin-ui/pipeline/odds/{season}/{week}`

---

**Result card component (reuse for all actions):**
```typescript
interface ActionResult {
  status: string;
  n_written: number;
  n_updated: number;
  n_skipped: number;
  n_failed: number;
  events: string[];
}
```
Show: status badge (green=ok/completed, yellow=partial, red=failed), written/updated/skipped/failed counts inline, events list if non-empty. Keep it compact — this is an ops tool.

**Auth:** All pipeline POSTs include `Authorization: Bearer <token>` header. Use `getToken()` from `useAuth()`.

---

### 4. Week Override Panel — `WeekOverridePanel` component

On mount: `GET /api/admin-ui/week-override` to show current state.

**Display:**
- If no override: "No override active — app is using auto-detected current week."
- If override active: "Override active: Season {season}, Week {week}" with a "Clear Override" button

**Set override form:**
- Season input (number, 2020–2035)
- Week input (number 1–22)
- Button: "Set Override"
- On submit: POST `/api/admin-ui/week-override` with `{season, week}`
- On success: refresh the current state display

**Clear override:**
- Button: "Clear Override" (only visible when override is active)
- DELETE `/api/admin-ui/week-override`
- On success: refresh state display

**Important note in UI:** Add a small info text: "This overrides what week the app considers 'current' for pipeline triggers and the public API." Keep it simple — one sentence.

---

## What NOT to touch

- `app/api/admin.py` — untouched (X-Admin-Key pipeline endpoints stay as-is)
- `AccountsPanel` and `HealthPanel` — untouched
- Any ML pipeline service files
- Public API routes (`app/api/public.py`)
- Auth, deps (no changes needed)
- `week_resolver.py` is created but NOT wired into existing endpoints in this PR

---

## Patterns to follow

**Backend:**
- All new endpoints in `admin_users.py` use `require_admin_user` dep
- Copy `SyncResponse` + `_to_response()` into `admin_users.py` — don't import from `admin.py`
- Use `pg_insert` with `on_conflict_do_update` for the week override upsert — check how it's used elsewhere in the codebase (roster_sync, odds_sync) for the exact import and pattern
- `async with Tank01Client() as tank01:` for any endpoint hitting Tank01
- Return `SyncResponse` for all pipeline actions, `WeekOverrideResponse` for override endpoints
- Pydantic models for all requests/responses

**Frontend:**
- Follow existing card/section styling: `border border-sr-border rounded-lg`, `text-sr-text-muted text-xs uppercase tracking-wide mb-3` for section headers
- Input styling matches existing admin inputs: `bg-sr-bg border border-sr-border rounded-lg px-3 py-2 text-sm text-white`
- Button primary: `bg-sr-primary text-white text-sm rounded-lg hover:opacity-90 disabled:opacity-50`
- All fetches include `Authorization: Bearer ${getToken()}` header
- No new npm packages
- TypeScript strict — no `any`

---

## Suggested implementation order

1. Migration `0009_system_config.py`
2. `app/models/system_config.py`
3. `app/services/week_resolver.py`
4. Copy `SyncResponse` + `_to_response()` into `admin_users.py`
5. Add pipeline action endpoints to `admin_users.py`
6. Add week override endpoints to `admin_users.py`
7. Frontend: update `Panel` type + sidebar
8. Frontend: `PipelinePanel` component
9. Frontend: `WeekOverridePanel` component
10. Frontend: wire panels into admin page render
