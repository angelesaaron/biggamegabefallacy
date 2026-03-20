# Claude Code Prompt — Week Resolution + Pre-Season Setup

## Scope
Two related changes implemented together because they touch the same files:

1. **Week Resolution** — fix how the app determines and displays the current week.
   The current implementation queries the `games` table (completed week). It should
   query `system_config` only (explicit writes from admin or pipeline).

2. **Pre-Season Setup** — add a sequenced admin action that runs once per year after
   the NFL Draft to initialize a new season.

Read this entire document before writing any code. Do not start implementing
until you have read all sections.

---

## Part 1 — Week Resolution

### The Core Concept

There are exactly two `system_config` keys that control what week the UI shows:

**`current_week_override`** — already exists. Set manually by admin via the
Week Override panel. Highest priority. Use case: freeze the UI on a specific
week (e.g. bad pipeline run, pre-season setup). Format: `"2026:17"`.

**`active_display_week`** — NEW key, does not yet exist in code. Will be written
automatically by the weekly pipeline on successful completion (pipeline is a
future phase — this prompt just adds backend support for reading it). Format:
`"2026:17"`. Second priority.

**Resolution order** (strictly enforced, no exceptions):
1. `current_week_override` if set and valid → `source="admin_override"`
2. `active_display_week` if set and valid → `source="pipeline"`
3. Hard fallback → `source="default"`, season=2026, week=1

No other data sources. No `games` table. No `predictions` table. No
`player_game_logs`. The display week is always driven by explicit writes.

**Why this matters:** If the pipeline fails mid-run, it does NOT write
`active_display_week`. The UI stays on whatever it was showing before. The
operator does not need to do anything. If the pipeline succeeds, it writes
`active_display_week` and the UI flips automatically. The admin can always
force a specific week by setting `current_week_override`.

### `_parse_season_week` helper

This small helper is used in multiple places. Define it once per module that
needs it (it's small enough to duplicate rather than create a shared util):

```python
def _parse_season_week(value: str) -> tuple[int, int] | None:
    """
    Parse "YYYY:WW" into (season, week). Returns None if malformed.
    Caller falls through to next priority level on None.
    """
    try:
        season_str, week_str = value.split(":")
        season = int(season_str)
        week = int(week_str)
        if 2020 <= season <= 2035 and 1 <= week <= 22:
            return season, week
    except (ValueError, AttributeError):
        pass
    return None
```

---

### Backend Change 1 — `app/api/public.py`

**Update `WeekStatusResponse`** — add `source` field:

```python
class WeekStatusResponse(BaseModel):
    season: int
    week: int
    is_early_season: bool
    source: str  # "admin_override" | "pipeline" | "default"
```

**Replace `get_status_week` entirely:**

```python
@router.get("/status/week", response_model=WeekStatusResponse, summary="Current season and week for display")
@limiter.limit("60/minute")
async def get_status_week(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> WeekStatusResponse:
    """
    Returns the season and week the UI should display by default.

    Resolution order (highest to lowest priority):
      1. system_config 'current_week_override' — set manually by admin
      2. system_config 'active_display_week' — set by pipeline on success
      3. Hard fallback: season=2026, week=1

    Never queries games, predictions, or player_game_logs.
    """
    for key, source in [
        ("current_week_override", "admin_override"),
        ("active_display_week", "pipeline"),
    ]:
        row = (await db.execute(
            select(SystemConfig).where(SystemConfig.key == key)
        )).scalars().first()
        if row and row.value:
            parsed = _parse_season_week(row.value)
            if parsed:
                season, week = parsed
                return WeekStatusResponse(
                    season=season,
                    week=week,
                    is_early_season=week <= 3,
                    source=source,
                )

    return WeekStatusResponse(season=2026, week=1, is_early_season=True, source="default")
```

**Add import** (if not already present):
```python
from app.models.system_config import SystemConfig
```

**Remove** the old `_DEFAULT_SEASON = 2025` and `_DEFAULT_WEEK = 1` constants.
Remove all old logic that queries `games` or `predictions` tables in this endpoint.

---

### Backend Change 2 — `app/services/week_resolver.py`

Replace the file entirely:

```python
"""
Resolve the current NFL week for internal backend use.

Priority:
  1. system_config 'current_week_override' (admin-set)
  2. system_config 'active_display_week' (pipeline-set on success)
  3. Hard fallback: week=1, season=2026

Never queries games, predictions, or player_game_logs.
"""
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.system_config import SystemConfig

logger = logging.getLogger(__name__)


def _parse_season_week(value: str) -> tuple[int, int] | None:
    try:
        season_str, week_str = value.split(":")
        season = int(season_str)
        week = int(week_str)
        if 2020 <= season <= 2035 and 1 <= week <= 22:
            return week, season  # NOTE: (week, season) to match all existing call sites
    except (ValueError, AttributeError):
        pass
    return None


async def resolve_current_week(db: AsyncSession) -> tuple[int, int]:
    """
    Returns (week, season) — NOT (season, week).
    This order matches all existing call sites throughout the codebase.
    Do not change call sites.
    """
    for key in ("current_week_override", "active_display_week"):
        row = (await db.execute(
            select(SystemConfig).where(SystemConfig.key == key)
        )).scalars().first()
        if row and row.value:
            parsed = _parse_season_week(row.value)
            if parsed:
                return parsed  # (week, season)

    return 1, 2026  # hard fallback
```

**After writing this file**, search the entire codebase for calls to
`resolve_current_week` and verify each destructuring is `week, season = await
resolve_current_week(db)`. Do not change the call sites — just verify they match.

---

### Backend Change 3 — `app/api/admin_users.py` — `active_display_week` endpoints

The admin panel needs to see when the pipeline last successfully wrote
`active_display_week` and clear it if needed (e.g. a bad pipeline run somehow
wrote it). Add these two endpoints:

```python
class ActiveDisplayWeekResponse(BaseModel):
    active: bool
    season: Optional[int]
    week: Optional[int]
    updated_at: Optional[str]  # ISO datetime — shows when pipeline last ran successfully


@router.get("/active-display-week", response_model=ActiveDisplayWeekResponse)
async def get_active_display_week(
    _admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
) -> ActiveDisplayWeekResponse:
    """
    Returns the pipeline-set active display week.
    Written automatically by the weekly pipeline on full successful completion.
    Use /week-override to manually force a week instead of editing this.
    """
    row = (await db.execute(
        select(SystemConfig).where(SystemConfig.key == "active_display_week")
    )).scalars().first()
    if row and row.value:
        try:
            season_str, week_str = row.value.split(":")
            return ActiveDisplayWeekResponse(
                active=True,
                season=int(season_str),
                week=int(week_str),
                updated_at=row.updated_at.isoformat() if row.updated_at else None,
            )
        except (ValueError, AttributeError):
            pass
    return ActiveDisplayWeekResponse(active=False, season=None, week=None, updated_at=None)


@router.delete("/active-display-week", response_model=ActiveDisplayWeekResponse)
async def clear_active_display_week(
    _admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
) -> ActiveDisplayWeekResponse:
    """
    Clears the pipeline-set active display week.
    After clearing, the UI falls back to current_week_override (if set) or
    the hard default. Use this if a bad pipeline run wrote an incorrect week.
    """
    stmt = (
        pg_insert(SystemConfig)
        .values(key="active_display_week", value=None)
        .on_conflict_do_update(
            index_elements=["key"],
            set_={"value": None, "updated_at": func.now()},
        )
    )
    await db.execute(stmt)
    await db.commit()
    return ActiveDisplayWeekResponse(active=False, season=None, week=None, updated_at=None)
```

---

### Frontend Change 1 — `hooks/useCurrentWeek.ts`

Add `source` field to `WeekStatus` interface and map it from the API response:

```typescript
interface WeekStatus {
  week: number | null;
  season: number | null;
  isEarlySeason: boolean;
  source: 'admin_override' | 'pipeline' | 'default' | null; // null = loading
}
```

Update `setStatus` call to include `source: data.source ?? null`.

Update the default state to include `source: null`.

---

### Frontend Change 2 — `components/weekly/PlayerWeekToggle.tsx`

Cap forward navigation at `currentWeek` so users cannot navigate to future
weeks that have no predictions.

Change this line:
```typescript
const canGoForward = selectedWeek < 18;
```

To:
```typescript
const canGoForward = currentWeek !== null && selectedWeek < currentWeek;
```

`currentWeek` is already a prop (`number`, not `number | null` per the interface).
Check the prop type — if it is `number` (not nullable), use:
```typescript
const canGoForward = selectedWeek < currentWeek;
```

---

### Frontend Change 3 — `components/weekly/WeeklyValue.tsx`

Update the destructuring of `useCurrentWeek()` to include `source`:
```typescript
const { week: currentWeek, season: currentYear, source } = useCurrentWeek();
```

Add an admin override badge inline next to the `<h1>` week header. This shows
whenever `source === 'admin_override'` — visible to all users, not just admins
(it's just a small informational indicator):

```tsx
<h1 className="text-xl md:text-3xl font-semibold text-white mb-1">
  Week {selectedWeek} — ATTD Targets
  {source === 'admin_override' && (
    <span className="ml-2 text-xs font-medium text-amber-400 border border-amber-400/40 rounded px-1.5 py-0.5 align-middle">
      admin override
    </span>
  )}
</h1>
```

No other changes to `WeeklyValue.tsx`. Do not add a "limbo" banner or
"pipeline pending" state — the `PlayerWeekToggle` forward cap handles
preventing navigation to weeks without data.

---

## Part 2 — Pre-Season Setup

### Context

This is a single sequenced admin action run once per year after the NFL Draft
(~late April) to initialize a new season. It runs four services in order:

**Step 1 — Season State** (`SeasonStateService.run(prior_season)`)
Computes end-of-season carry-forward features from `prior_season` game logs.
Writes `player_season_state` rows with `join_season = new_season`.
Must run before roster sync — reads `player_game_logs` for `prior_season`
and matches against `players`. Running first ensures the full prior-season
player set is used before any roster changes.

**Step 2 — Roster Sync** (`RosterSyncService.run()`)
Fetches all 32 current rosters from Tank01. Upserts WR/TE players.
Post-draft rookies appear on rosters within days of the draft.
Must run before draft sync — draft sync only updates players already in `players`.

**Step 3 — Draft Sync** (`DraftSyncService.run(force_update=True)`)
Populates `players.draft_round` from nflverse. Uses `force_update=True` here
(unlike the weekly call which uses `force_update=False`) to refresh all players
including new rookies. Requires a cache bust first (see below).
Depends on roster sync — skipped if roster sync failed entirely.

**Step 4 — Rookie Bucket Seed** (`RookieBucketSeedService.run()`)
Re-seeds `rookie_buckets` from hardcoded training data.
No dependencies — always runs regardless of prior step outcomes.

### nflverse Cache Bust

`DraftSyncService` calls `nflreadpy.load_players()`. The cache may have stale
pre-draft data (new rookies not yet included). Before running draft sync, delete
the `load_players.parquet` file from `settings.NFLVERSE_CACHE_DIR` to force a
fresh download. Only delete this one file — not PBP or snap count files.

Define this as a module-level function in `admin_users.py`:

```python
def _bust_players_cache() -> None:
    """Delete nflverse load_players cache to force fresh post-draft download."""
    import os
    import logging
    from pathlib import Path
    from app.config import settings
    logger = logging.getLogger(__name__)
    cache_path = Path(settings.NFLVERSE_CACHE_DIR) / "load_players.parquet"
    if cache_path.exists():
        os.remove(cache_path)
        logger.info("Busted nflverse players cache: %s", cache_path)
    else:
        logger.info("nflverse players cache not found (will download fresh): %s", cache_path)
```

### Failure Behavior

- Season state failure → log it, continue. Steps 2–4 do not depend on step 1.
- Roster sync failure → log it, skip draft sync (draft sync needs players to exist),
  still attempt rookie bucket seed.
- Draft sync failure → log it, still attempt rookie bucket seed.
- Rookie bucket seed failure → log it.
- Each step has its own try/except. One step failing does not raise and kill the request.
- `await db.commit()` after each successful step.
- `await db.rollback()` in each except block.
- Overall status: "ok" if all steps are "ok", "partial" if any are partial/failed/skipped
  but at least one succeeded, "failed" if everything failed or zero steps succeeded.

---

### Backend Change 4 — `app/api/admin_users.py` — Pre-season setup endpoint

Add the following at the end of `admin_users.py`. The required service imports
(`SeasonStateService`, `RookieBucketSeedService`) are not yet in this file —
add them. `DraftSyncService`, `RosterSyncService`, and `Tank01Client` are
already imported.

```python
# ---------------------------------------------------------------------------
# Pre-season setup
# ---------------------------------------------------------------------------

class PreSeasonSetupRequest(BaseModel):
    new_season: int = Field(..., ge=2020, le=2035, description="Season being set up e.g. 2026")
    prior_season: int = Field(..., ge=2019, le=2034, description="Season that just ended e.g. 2025")


class PreSeasonStepResult(BaseModel):
    step: str
    status: str   # "ok" | "partial" | "failed" | "skipped"
    n_written: int
    n_updated: int
    n_failed: int
    events: list[str]


class PreSeasonSetupResponse(BaseModel):
    new_season: int
    prior_season: int
    overall_status: str  # "ok" | "partial" | "failed"
    steps: list[PreSeasonStepResult]
    errors: list[str]


@router.post("/pipeline/preseason-setup", response_model=PreSeasonSetupResponse)
async def preseason_setup(
    body: PreSeasonSetupRequest,
    _admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PreSeasonSetupResponse:
    """
    Full pre-season setup sequence for a new NFL season.
    Run once per year after the NFL Draft (~late April).

    Steps (in order):
      1. Season state  — carry-forward from prior_season
      2. Roster sync   — current rosters including drafted rookies
      3. Draft sync    — populate draft_round from nflverse (cache busted)
      4. Rookie buckets — re-seed feature buckets

    new_season must equal prior_season + 1. Both are required explicitly.
    Safe to re-run — all steps are idempotent.
    """
    from app.services.season_state_service import SeasonStateService
    from app.services.rookie_bucket_seed import RookieBucketSeedService
    import logging
    logger = logging.getLogger(__name__)

    steps: list[PreSeasonStepResult] = []
    errors: list[str] = []

    if body.prior_season != body.new_season - 1:
        return PreSeasonSetupResponse(
            new_season=body.new_season,
            prior_season=body.prior_season,
            overall_status="failed",
            steps=[],
            errors=[
                f"prior_season must equal new_season - 1. "
                f"Expected {body.new_season - 1}, got {body.prior_season}."
            ],
        )

    roster_sync_ok = False

    # ── Step 1: Season State ────────────────────────────────────────────────
    try:
        result = await SeasonStateService(db).run(body.prior_season)
        await db.commit()
        ok = result.n_written + result.n_updated
        step_status = "ok" if result.n_failed == 0 else ("partial" if ok > 0 else "failed")
        if step_status == "failed":
            errors.append(f"Season state failed: {result.events}")
        steps.append(PreSeasonStepResult(
            step="season_state", status=step_status,
            n_written=result.n_written, n_updated=result.n_updated,
            n_failed=result.n_failed, events=result.events,
        ))
    except Exception as exc:
        await db.rollback()
        msg = f"Season state exception: {exc}"
        errors.append(msg)
        logger.error(msg, exc_info=True)
        steps.append(PreSeasonStepResult(
            step="season_state", status="failed",
            n_written=0, n_updated=0, n_failed=1, events=[msg],
        ))

    # ── Step 2: Roster Sync ─────────────────────────────────────────────────
    try:
        async with Tank01Client() as tank01:
            result = await RosterSyncService(db, tank01).run()
        await db.commit()
        ok = result.n_written + result.n_updated
        step_status = "ok" if result.n_failed == 0 else ("partial" if ok > 0 else "failed")
        if step_status == "failed":
            errors.append(f"Roster sync failed: {result.events}")
        roster_sync_ok = step_status in ("ok", "partial")
        steps.append(PreSeasonStepResult(
            step="roster_sync", status=step_status,
            n_written=result.n_written, n_updated=result.n_updated,
            n_failed=result.n_failed, events=result.events,
        ))
    except Exception as exc:
        await db.rollback()
        msg = f"Roster sync exception: {exc}"
        errors.append(msg)
        logger.error(msg, exc_info=True)
        steps.append(PreSeasonStepResult(
            step="roster_sync", status="failed",
            n_written=0, n_updated=0, n_failed=1, events=[msg],
        ))

    # ── Step 3: Draft Sync ──────────────────────────────────────────────────
    if not roster_sync_ok:
        steps.append(PreSeasonStepResult(
            step="draft_sync", status="skipped",
            n_written=0, n_updated=0, n_failed=0,
            events=["Skipped: roster sync did not succeed"],
        ))
    else:
        try:
            _bust_players_cache()
            result = await DraftSyncService(db).run(force_update=True)
            await db.commit()
            ok = result.n_written + result.n_updated
            step_status = "ok" if result.n_failed == 0 else ("partial" if ok > 0 else "failed")
            if step_status == "failed":
                errors.append(f"Draft sync failed: {result.events}")
            steps.append(PreSeasonStepResult(
                step="draft_sync", status=step_status,
                n_written=result.n_written, n_updated=result.n_updated,
                n_failed=result.n_failed, events=result.events,
            ))
        except Exception as exc:
            await db.rollback()
            msg = f"Draft sync exception: {exc}"
            errors.append(msg)
            logger.error(msg, exc_info=True)
            steps.append(PreSeasonStepResult(
                step="draft_sync", status="failed",
                n_written=0, n_updated=0, n_failed=1, events=[msg],
            ))

    # ── Step 4: Rookie Bucket Seed ──────────────────────────────────────────
    try:
        result = await RookieBucketSeedService(db).run()
        await db.commit()
        ok = result.n_written + result.n_updated
        step_status = "ok" if result.n_failed == 0 else ("partial" if ok > 0 else "failed")
        steps.append(PreSeasonStepResult(
            step="rookie_bucket_seed", status=step_status,
            n_written=result.n_written, n_updated=result.n_updated,
            n_failed=result.n_failed, events=result.events,
        ))
    except Exception as exc:
        await db.rollback()
        msg = f"Rookie bucket seed exception: {exc}"
        errors.append(msg)
        logger.error(msg, exc_info=True)
        steps.append(PreSeasonStepResult(
            step="rookie_bucket_seed", status="failed",
            n_written=0, n_updated=0, n_failed=1, events=[msg],
        ))

    # ── Overall status ──────────────────────────────────────────────────────
    statuses = {s.status for s in steps}
    if statuses <= {"failed", "skipped"}:
        overall = "failed"
    elif "failed" in statuses or "partial" in statuses or "skipped" in statuses:
        overall = "partial"
    else:
        overall = "ok"

    return PreSeasonSetupResponse(
        new_season=body.new_season,
        prior_season=body.prior_season,
        overall_status=overall,
        steps=steps,
        errors=errors,
    )


def _bust_players_cache() -> None:
    """Delete nflverse load_players cache to force fresh post-draft download."""
    import os
    import logging
    from pathlib import Path
    from app.config import settings
    _log = logging.getLogger(__name__)
    cache_path = Path(settings.NFLVERSE_CACHE_DIR) / "load_players.parquet"
    if cache_path.exists():
        os.remove(cache_path)
        _log.info("Busted nflverse players cache: %s", cache_path)
    else:
        _log.info("nflverse players cache not found (fresh download on next call): %s", cache_path)
```

**Add these imports** at the top of `admin_users.py`:
```python
from pydantic import BaseModel, Field  # Field already present? check
from app.services.season_state_service import SeasonStateService
from app.services.rookie_bucket_seed import RookieBucketSeedService
```

---

### Frontend Change 4 — Admin panel Pipeline tab — Pre-Season Setup section

The admin panel pipeline tab (`admin/page.tsx` → `PipelinePanel` component) uses
a two-column layout: left column has ghost buttons + section labels, right column
is an append-only run log. Read the existing `PipelinePanel` implementation
carefully before making any changes — match its patterns exactly.

**Left column — add a new SETUP section** below the existing SYNC section:

```tsx
{/* SETUP section */}
<div className="space-y-2">
  <p className={SECTION_LABEL}>Setup</p>
  <div className="border-t border-sr-border" />

  {/* Season inputs */}
  <div className="space-y-1.5 py-0.5">
    <div className="flex items-center gap-2">
      <span className="text-xs text-sr-text-muted font-mono w-20">New season</span>
      <input
        type="number"
        value={preSeasonNewSeason}
        onChange={(e) => setPreSeasonNewSeason(Number(e.target.value))}
        min={2020}
        max={2035}
        className={INPUT_CLS}
      />
    </div>
    <div className="flex items-center gap-2">
      <span className="text-xs text-sr-text-muted font-mono w-20">Prior season</span>
      <input
        type="number"
        value={preSeasonPriorSeason}
        onChange={(e) => setPreSeasonPriorSeason(Number(e.target.value))}
        min={2019}
        max={2034}
        className={INPUT_CLS}
      />
    </div>
    {preSeasonPriorSeason !== preSeasonNewSeason - 1 && (
      <p className="text-[10px] text-red-400 font-mono">
        Prior must equal new − 1
      </p>
    )}
  </div>

  {/* Pre-Season Setup button */}
  <div className="flex items-center gap-2 py-0.5">
    <button
      disabled={busy || preSeasonPriorSeason !== preSeasonNewSeason - 1}
      onClick={() => triggerPreSeason()}
      className={GHOST_BTN}
      aria-label="Run Pre-Season Setup"
    >
      {runningAction === 'Pre-Season Setup' ? (
        <span className="inline-block w-2 h-2 rounded-full bg-current animate-pulse" />
      ) : (
        '▶ run'
      )}
    </button>
    <span className="text-sm text-white flex-1">Pre-Season Setup</span>
    <span className="text-[10px] text-sr-text-dim">ext. API</span>
  </div>
</div>
```

**Add state variables** to `PipelinePanel`:
```typescript
const [preSeasonNewSeason, setPreSeasonNewSeason] = useState(2026);
const [preSeasonPriorSeason, setPreSeasonPriorSeason] = useState(2025);
```

**Add `triggerPreSeason` function** to `PipelinePanel`. This is separate from
the existing `trigger` function because the response shape is different
(`PreSeasonSetupResponse` with `steps[]` instead of a flat `ActionResult`):

```typescript
async function triggerPreSeason() {
  const id = crypto.randomUUID();
  const entry: RunEntry = {
    id,
    action: 'Pre-Season Setup',
    season: preSeasonNewSeason,
    status: 'running',
    startedAt: new Date(),
  };
  setRuns((prev) => [entry, ...prev]);
  setRunningAction('Pre-Season Setup');
  try {
    const token = getToken();
    const res = await fetch(`${API_URL}/api/admin-ui/pipeline/preseason-setup`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        new_season: preSeasonNewSeason,
        prior_season: preSeasonPriorSeason,
      }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({})) as { detail?: string };
      throw new Error(body.detail ?? `Request failed: ${res.status}`);
    }
    const data = await res.json() as PreSeasonSetupResponse;
    const resolved: RunEntry['status'] =
      data.overall_status === 'ok' ? 'completed'
      : data.overall_status === 'partial' ? 'partial'
      : 'failed';
    setRuns((prev) =>
      prev.map((r) =>
        r.id === id
          ? { ...r, status: resolved, preSeasonResult: data, completedAt: new Date() }
          : r
      )
    );
  } catch (err) {
    setRuns((prev) =>
      prev.map((r) =>
        r.id === id
          ? {
              ...r,
              status: 'error',
              errorMessage: err instanceof Error ? err.message : 'Failed',
              completedAt: new Date(),
            }
          : r
      )
    );
  } finally {
    setRunningAction(null);
  }
}
```

**Add TypeScript type** for the pre-season response:
```typescript
interface PreSeasonStepResult {
  step: string;
  status: 'ok' | 'partial' | 'failed' | 'skipped';
  n_written: number;
  n_updated: number;
  n_failed: number;
  events: string[];
}

interface PreSeasonSetupResponse {
  new_season: number;
  prior_season: number;
  overall_status: 'ok' | 'partial' | 'failed';
  steps: PreSeasonStepResult[];
  errors: string[];
}
```

**Update `RunEntry` interface** to include the optional pre-season result:
```typescript
interface RunEntry {
  id: string;
  action: string;
  season?: number;
  week?: number;
  status: 'running' | 'completed' | 'partial' | 'failed' | 'error';
  result?: ActionResult;
  preSeasonResult?: PreSeasonSetupResponse;  // ADD THIS
  errorMessage?: string;
  startedAt: Date;
  completedAt?: Date;
}
```

**Update `RunLogEntry` component** to render pre-season step results when
`run.preSeasonResult` is present. After the existing status line, add:

```tsx
{run.preSeasonResult && (
  <div className="space-y-0.5 mt-1">
    {run.preSeasonResult.steps.map((step) => {
      const stepColor =
        step.status === 'ok' ? 'text-green-400'
        : step.status === 'partial' ? 'text-yellow-400'
        : step.status === 'skipped' ? 'text-sr-text-dim'
        : 'text-red-400';
      return (
        <div key={step.step} className="flex items-baseline gap-2">
          <span className={`text-xs font-mono ${stepColor}`}>{step.status}</span>
          <span className="text-xs font-mono text-sr-text-muted">{step.step.replace(/_/g, ' ')}</span>
          <span className="text-xs font-mono text-sr-text-dim">
            +{step.n_written} ~{step.n_updated} ✗{step.n_failed}
          </span>
        </div>
      );
    })}
    {run.preSeasonResult.errors.length > 0 && (
      <ul className="space-y-0.5 mt-1">
        {run.preSeasonResult.errors.map((e, i) => (
          <li key={i} className="text-xs font-mono text-red-400 truncate">· {e}</li>
        ))}
      </ul>
    )}
  </div>
)}
```

**Also add** the Week Override panel section for `active_display_week`. In
`WeekOverridePanel`, after the existing "Current Week" section, add a read-only
display of the pipeline-set week:

```tsx
{/* Pipeline week */}
<div>
  <p className={SECTION_LABEL}>Pipeline Set</p>
  <div className="border-t border-sr-border my-2" />
  <PipelineWeekStatus />
</div>
```

Implement `PipelineWeekStatus` as a small sub-component within the same file:

```tsx
function PipelineWeekStatus() {
  const { getToken } = useAuth();
  const [data, setData] = useState<{ active: boolean; season: number | null; week: number | null; updated_at: string | null } | null>(null);
  const [clearing, setClearing] = useState(false);

  useEffect(() => {
    async function fetch_() {
      const token = getToken();
      const res = await fetch(`${API_URL}/api/admin-ui/active-display-week`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setData(await res.json());
    }
    fetch_();
  }, [getToken]);

  async function handleClear() {
    setClearing(true);
    const token = getToken();
    const res = await fetch(`${API_URL}/api/admin-ui/active-display-week`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) setData(await res.json());
    setClearing(false);
  }

  if (!data) return <p className="text-xs font-mono text-sr-text-dim">Loading...</p>;

  if (!data.active) {
    return <p className="text-xs font-mono text-sr-text-muted">Not set (pipeline hasn't run)</p>;
  }

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span className="text-sm font-mono text-white">S{data.season} W{data.week}</span>
      {data.updated_at && (
        <span className="text-[10px] text-sr-text-dim font-mono">
          {new Date(data.updated_at).toLocaleString()}
        </span>
      )}
      <button
        onClick={handleClear}
        disabled={clearing}
        className="text-xs text-sr-text-dim hover:text-red-400 underline transition-colors disabled:opacity-50 ml-1"
      >
        {clearing ? 'clearing...' : 'clear'}
      </button>
    </div>
  );
}
```

---

## Files to Modify

- `backend_new/app/api/public.py`
- `backend_new/app/services/week_resolver.py`
- `backend_new/app/api/admin_users.py`
- `frontend/hooks/useCurrentWeek.ts`
- `frontend/components/weekly/PlayerWeekToggle.tsx`
- `frontend/components/weekly/WeeklyValue.tsx`
- `frontend/app/admin/page.tsx`

## Files to Leave Untouched

- Any migration file — `system_config` table already exists (migration 0009)
- `usePredictions.ts`
- `admin.py` (the X-Admin-Key router — separate from admin_users.py)
- All service files
- All model files
- All test files

---

## Correctness Checklist

- [ ] `/api/status/week` queries ONLY `system_config` — no games, predictions, or
      player_game_logs tables
- [ ] Resolution order is exactly: `current_week_override` → `active_display_week` → default
- [ ] `week_resolver.py` returns `(week, season)` — NOT `(season, week)`
- [ ] `WeekStatusResponse` has `source` field with exact values: "admin_override" |
      "pipeline" | "default"
- [ ] `useCurrentWeek` returns `source: null` during loading
- [ ] `PlayerWeekToggle` forward navigation capped at `currentWeek`, null-safe
- [ ] Admin override badge shows only when `source === 'admin_override'`
- [ ] `active_display_week` GET and DELETE endpoints added to `admin_users.py`
- [ ] `_bust_players_cache()` only deletes `load_players.parquet`, not other files
- [ ] `DraftSyncService.run(force_update=True)` in preseason endpoint (not False)
- [ ] `prior_season == new_season - 1` validation returns immediately with clear error
- [ ] Step order: season_state → roster_sync → draft_sync → rookie_bucket_seed
- [ ] `draft_sync` is status="skipped" (not "failed") when roster_sync fails
- [ ] `rookie_bucket_seed` always attempts regardless of prior steps
- [ ] Each step has its own try/except with `db.commit()` on success, `db.rollback()` on failure
- [ ] `RunEntry` interface updated with optional `preSeasonResult` field
- [ ] Pre-season run log displays per-step results using the existing run log aesthetic
- [ ] `PipelineWeekStatus` component added to `WeekOverridePanel`
- [ ] Old `_DEFAULT_SEASON = 2025` constant removed from `public.py`
- [ ] No new migrations required
