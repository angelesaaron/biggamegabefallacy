# Admin DB Health Panel — Week Navigation Enhancement

## Phase 1 Verification

Phase 1 is fully implemented and correct:
- `is_admin` column on `User` model ✅ (migration `0008`, `down_revision="0007"`)
- `require_admin_user` dep in `deps.py` ✅
- `is_admin` in JWT claims (`auth_service.py`) and `MeResponse` (`auth.py`) ✅
- `admin_users.py` router with all account + health endpoints ✅
- `AuthContext` exposes `isAdmin`, `useIsAdmin()` hook ✅
- Admin nav tab (router.push to `/admin`) ✅
- `/app/admin/page.tsx` with sidebar + AccountsPanel + HealthPanel ✅

**Latest migration:** `0008_add_is_admin.py` (`revision="0008"`, `down_revision="0007"`). Any new migration must use `down_revision="0008"`.

---

## What to Change

The DB Health panel currently shows aggregate counts for the current season/week only. The requirement is to make it **week-navigable**: show data for a specific season+week, with prev/next controls to step through history.

The counts panel (total record counts per table) stays as-is — those are season-wide aggregates and don't need to be week-scoped. Everything else should be week-scoped and navigable.

---

## Backend Changes

### 1. Update `GET /api/admin-ui/health` to accept `season` and `week` query params

In `app/api/admin_users.py`, update the health endpoint signature:

```python
@router.get("/health", response_model=HealthResponse)
async def db_health(
    season: int | None = Query(default=None, ge=2020, le=2035),
    week: int | None = Query(default=None, ge=1, le=22),
    _admin: User = Depends(require_admin_user),
    db: AsyncSession = Depends(get_db),
) -> HealthResponse:
```

When `season`/`week` are not provided, fall back to the current detected season/week (same logic as before — max season from `player_game_logs`, max week for that season).

### 2. Return the resolved `season` and `week` in the response

Add `season` and `week` to the top-level `HealthResponse` model so the frontend knows what was actually resolved:

```python
class HealthResponse(BaseModel):
    season: int
    week: int
    counts: TableCounts          # unchanged — total counts, not week-scoped
    last_updated: LastUpdated    # unchanged
    week_summary: WeekSummary    # NEW — replaces prediction_coverage
    missing_game_log_players: list[MissingGameLogPlayer]  # now week-scoped
    recent_data_quality_events: list[DataQualityRow]      # unchanged (last 10 overall)
```

### 3. Replace `PredictionCoverage` with `WeekSummary`

Remove `PredictionCoverage`. Add:

```python
class WeekSummary(BaseModel):
    game_logs_ingested: int        # count of player_game_logs rows for this season+week
    features_computed: int         # count of player_features rows for this season+week
    predictions_generated: int     # count of predictions rows for this season+week
    odds_available: int            # count of sportsbook_odds rows for this season+week (if that table has season/week columns — check actual model)
    players_with_game_logs: int    # distinct player_ids in player_game_logs for this week
    players_missing_game_logs: int # count of active WR/TE players NOT in game_logs for this week
```

### 4. Update `missing_game_log_players` to be week-scoped

Currently it queries players missing game logs **for the entire season**. Change it to query players missing game logs **for the specific week being viewed**.

The query should find active players (WR or TE, if position filtering exists on the Player model — check `Player.position`) who have zero rows in `player_game_logs` where `season == resolved_season AND week == resolved_week`. If the Player model doesn't have a position filter available, just filter to active players.

Cap at 100 rows (up from 50) since week-level missing is more actionable.

### 5. Add `available_weeks` to the response

Add a field to `HealthResponse`:

```python
available_weeks: list[dict]  # [{season: int, week: int}, ...] sorted desc
```

Query the distinct `(season, week)` combinations from `player_game_logs` ordered by `season DESC, week DESC`. This tells the frontend which weeks actually have data so it can populate the navigation correctly. Cap at 50 results.

---

## Frontend Changes

All changes are in `frontend/app/admin/page.tsx` within the `HealthPanel` component. Do not touch `AccountsPanel`.

### 1. Add week navigation state

```typescript
const [selectedSeason, setSelectedSeason] = useState<number | null>(null);
const [selectedWeek, setSelectedWeek] = useState<number | null>(null);
const [availableWeeks, setAvailableWeeks] = useState<{season: number, week: number}[]>([]);
```

On first load, `selectedSeason` and `selectedWeek` are `null` — the backend resolves to current. After first load, populate from `data.season` and `data.week` so subsequent nav is explicit.

### 2. Update `fetchHealth` to pass season/week params

```typescript
const fetchHealth = useCallback(async (season?: number, week?: number) => {
  // build URL with ?season=X&week=Y if provided
  const params = new URLSearchParams();
  if (season !== undefined) params.set('season', String(season));
  if (week !== undefined) params.set('week', String(week));
  const url = `${API_URL}/api/admin-ui/health${params.size ? '?' + params.toString() : ''}`;
  // ... rest of fetch unchanged
}, [getToken, selectedSeason, selectedWeek]);
```

After a successful fetch, update `availableWeeks` from `data.available_weeks` and update `selectedSeason`/`selectedWeek` from `data.season`/`data.week`.

### 3. Add week navigation UI

Above the health content, replace the current "Database Health" heading + refresh button row with:

```
[← Prev Week]  Season 2024, Week 14  [Next Week →]  [Refresh]  [Last refresh: ...]
```

- **Prev Week / Next Week** buttons navigate through `availableWeeks` array (find current index, step backward/forward)
- Disable **Next Week** when already at the most recent week (index 0)
- Disable **Prev Week** when at the oldest week (last index)
- Clicking prev/next calls `fetchHealth(newSeason, newWeek)` and updates `selectedSeason`/`selectedWeek`
- Show the resolved season+week from `data.season` and `data.week` in the heading, not from local state, to avoid display lag

### 4. Replace Prediction Coverage section with Week Summary

Remove the existing "Prediction Coverage" section. Add a "Week Summary" section using the same stat card grid pattern as Record Counts:

Display these stats as labeled cards:
- Game Logs Ingested
- Features Computed  
- Predictions Generated
- Odds Available
- Players w/ Game Logs
- Players Missing Logs

Use `data.week_summary` fields. Follow the exact same card styling as the existing counts grid.

### 5. Update missing players section header

Change the section header from:
```
Players Missing Game Logs This Season (N)
```
to:
```
Players Missing Game Logs — Week {data.week} (N)
```

No other changes to the missing players section.

### 6. Auto-refresh behavior

Keep the existing 60-second auto-refresh. On auto-refresh, use the currently selected season/week (not null) so it doesn't reset to current week while you're browsing history.

---

## What NOT to change

- `AccountsPanel` — untouched
- Record Counts section — stays as total counts, not week-scoped
- Last Updated section — stays as-is
- Recent Data Quality Events section — stays as-is (last 10 overall)
- All existing backend endpoint signatures other than `/health`
- Auth, deps, migrations — no changes needed

---

## Patterns to follow

- Backend: same async SQLAlchemy pattern as existing health endpoint — `select(func.count()).select_from(Model).where(...)` 
- Backend: check actual column names on `SportsbookOdds` model before querying — it may not have `season`/`week` columns, in which case set `odds_available` to `-1` or omit it
- Frontend: follow existing card/section styling exactly — `border border-sr-border rounded-lg`, `text-sr-text-muted text-xs uppercase tracking-wide mb-3` for section headers
- No new npm packages
- TypeScript strict — no `any`
