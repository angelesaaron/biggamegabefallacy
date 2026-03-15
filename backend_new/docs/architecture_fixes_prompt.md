# Architecture Fixes & Remaining Issues — Claude Code Prompt

Read this entire document before writing any code. Every change here is grounded in a specific architectural reason. The goal is not just to fix bugs — it is to ensure each layer owns exactly its responsibility and nothing more.

---

## Architectural principle driving all changes

**Each layer owns its own concern:**
- The database owns data.
- The backend owns what data each caller is allowed to receive.
- API endpoints are organized by what they represent (a resource), not by who is allowed to call them.
- The frontend owns display and user interaction only — it never makes authorization decisions, never hides data that shouldn't have been sent, and never fetches data it isn't going to show.

Any time the frontend is making a decision like "should I show this value or not," that decision belongs in the backend. Any time a component does two unrelated things (display + gating, fetch + transform + gate), it should be split.

---

## BACKEND CHANGES

### Change 1 — New public endpoint: `GET /api/players/{player_id}/season-stats`

**Why:** The player header stats (TDs this season, games played, targets, TD rate) are public box score facts — not premium model data. They currently live inside the `/game-logs` response which is subscriber-only. This means non-subscribers see all zeros in the player header. That is wrong both logically and from a product perspective.

The fix is a dedicated public endpoint that aggregates stats from game logs. This is the correct architecture: the resource (`season-stats`) is separate from the detailed log table (`game-logs`). Public gets the summary. Subscribers get the full table.

**Add to `app/api/public.py`:**

```python
class SeasonStatsResponse(BaseModel):
    player_id: str
    season: int
    games_played: int
    tds_this_season: int
    targets: int
    td_rate: float          # 0.0–1.0, e.g. 0.25 = 25%

@router.get(
    "/players/{player_id}/season-stats",
    response_model=SeasonStatsResponse,
    summary="Season stat totals for a player — public",
)
@limiter.limit("60/minute")
async def get_player_season_stats(
    request: Request,
    player_id: str,
    season: Optional[int] = Query(default=None, description="Season year. Defaults to most recent."),
    db: AsyncSession = Depends(get_db),
) -> SeasonStatsResponse:
    """
    Aggregated season stats from game logs. No auth required.
    Returns totals for display in player header (TDs, games, targets, TD rate).
    If no logs exist, returns zeros rather than 404 — the player exists, they just have no data.
    """
    if await db.get(Player, player_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found.")

    # Resolve season
    if season is not None:
        resolved_season = season
    else:
        max_q = select(func.max(PlayerGameLog.season)).where(PlayerGameLog.player_id == player_id)
        result = (await db.execute(max_q)).scalar_one_or_none()
        resolved_season = int(result) if result is not None else 2025

    q = (
        select(
            func.count(PlayerGameLog.id).label("games_played"),
            func.coalesce(func.sum(PlayerGameLog.rec_tds), 0).label("tds"),
            func.coalesce(func.sum(PlayerGameLog.targets), 0).label("targets"),
            func.coalesce(
                func.sum(case((PlayerGameLog.rec_tds > 0, 1), else_=0)), 0
            ).label("games_with_td"),
        )
        .where(PlayerGameLog.player_id == player_id)
        .where(PlayerGameLog.season == resolved_season)
    )
    row = (await db.execute(q)).one()

    games_played = int(row.games_played)
    td_rate = (int(row.games_with_td) / games_played) if games_played > 0 else 0.0

    return SeasonStatsResponse(
        player_id=player_id,
        season=resolved_season,
        games_played=games_played,
        tds_this_season=int(row.tds),
        targets=int(row.targets),
        td_rate=round(td_rate, 4),
    )
```

### Change 2 — Clean up `PredictionRow` in `app/api/public.py`

**Why:** `locked: bool` was a workaround for the old CSS blur system. It is dead code. `final_prob` and `model_odds` were changed to `Optional` to support locking — but locking is gone. A prediction row always has a `final_prob` and `model_odds`. Keeping them optional introduces a null guard burden in `_assign_tiers` that doesn't need to exist and could cause a `TypeError` if `None` slips through the `>=` comparison.

```python
# Change these fields in PredictionRow:
final_prob: float           # was: Optional[float]
model_odds: int             # was: Optional[int]
# Remove this field entirely:
# locked: bool = False      ← delete
```

Also update `_assign_tiers` — the function currently operates on `PredictionRow` objects but `final_prob` is referenced without a null guard. With the type fixed to `float` this is safe. No other changes needed to `_assign_tiers`.

### Change 3 — Clean up stale docstring in `app/api/deps.py`

**Why:** The module-level docstring still refers to `require_free` and `require_pro` which were removed. Stale documentation is a maintenance hazard.

Replace the entire module docstring with:

```python
"""
FastAPI dependency functions for authentication and authorization.

Dependency hierarchy:

    get_optional_user   — extracts + validates Bearer token; returns User | None
         └── require_auth      — enforces authentication; raises 401 if absent
                  └── require_subscriber  — active subscribers only; raises 403 otherwise

Usage:

    # Optional auth — used for content gating (endpoint returns different shapes)
    async def view(user: Optional[User] = Depends(get_optional_user)): ...

    # Hard gate — endpoint is subscriber-only
    async def pro_view(user: User = Depends(require_subscriber)): ...
"""
```

---

## FRONTEND CHANGES

### Change 4 — Add `SeasonStatsResponse` type to `types/backend.ts`

```typescript
export interface SeasonStatsResponse {
  player_id: string;
  season: number;
  games_played: number;
  tds_this_season: number;
  targets: number;
  td_rate: number;   // 0.0–1.0
}
```

### Change 5 — Split `PlayerModel` Effect B into two independent effects

**Why:** Effect B currently does two unrelated things — fetch stats (public, should always run) and fetch game logs + history (subscriber-only). These are different concerns with different auth requirements and different lifecycles. They should be separate effects.

**Effect B — stats only, runs for everyone:**

```typescript
// Effect B: season stats — public, always runs for any selected player
useEffect(() => {
  async function loadSeasonStats() {
    if (!selectedPlayerId) return;
    try {
      const resp = await fetch(
        `${API_URL}/api/players/${selectedPlayerId}/season-stats?season=${effectiveYear}`
      );
      if (!resp.ok) return;
      const stats: SeasonStatsResponse = await resp.json();
      setPlayers((prev) =>
        prev.map((p) =>
          p.id === selectedPlayerId
            ? {
                ...p,
                tdsThisSeason: stats.tds_this_season,
                gamesPlayed: stats.games_played,
                targets: stats.targets,
                tdRate: stats.games_played > 0
                  ? `${Math.round(stats.td_rate * 100)}%`
                  : '0%',
              }
            : p
        )
      );
    } catch {
      // silently handle — header stats stay at 0 if fetch fails
    }
  }
  loadSeasonStats();
}, [selectedPlayerId, effectiveYear]);
```

**Effect C — subscriber data only, runs only for subscribers:**

```typescript
// Effect C: game logs + prediction history — subscriber only
useEffect(() => {
  async function loadSubscriberData() {
    if (!selectedPlayerId || !isSubscriber) {
      setSelectedPlayerData((prev) => ({ ...prev, gameLogs: [], weeklyData: [] }));
      return;
    }
    try {
      const token = getToken();
      const authHeader: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
      const [logsResp, historyResp] = await Promise.all([
        fetch(`${API_URL}/api/players/${selectedPlayerId}/game-logs?season=${effectiveYear}&limit=30`, { headers: authHeader }),
        fetch(`${API_URL}/api/players/${selectedPlayerId}/history?season=${effectiveYear}`, { headers: authHeader }),
      ]);

      const logsData: GameLogsResponse = await logsResp.json();
      const historyData: PredictionHistoryEntry[] = await historyResp.json();
      const logs: GameLogEntry[] = logsData.game_logs ?? [];

      const predictionsByWeek = new Map<number, number>(
        historyData
          .filter((h) => h.final_prob !== null)
          .map((h) => [h.week, (h.final_prob as number) * 100] as [number, number])
      );

      const gameLogs = logs.map((log) => ({
        week: log.week,
        opponent: log.opponent ?? 'OPP',
        targets: log.targets ?? 0,
        yards: log.rec_yards ?? 0,
        td: log.rec_tds ?? 0,
        modelProbability: Math.round(predictionsByWeek.get(log.week) ?? 0),
      }));

      const weeklyData = logs.map((log) => ({
        week: log.week,
        probability: predictionsByWeek.get(log.week) ?? 0,
        scored: (log.rec_tds ?? 0) > 0,
      }));

      setSelectedPlayerData((prev) => ({ ...prev, gameLogs, weeklyData }));
    } catch {
      // silently handle
    }
  }
  loadSubscriberData();
  // eslint-disable-next-line react-hooks/exhaustive-deps
}, [selectedPlayerId, effectiveYear, isSubscriber, user]);
```

Remove the `setPlayers()` call from any subscriber-only effect — player stats are now handled by Effect B above.

Also add `SeasonStatsResponse` to the imports from `@/types/backend`.

### Change 6 — Remove orphaned modal state from `PlayerModel`

**Why:** The app has a single global `AuthModal` wired up in `layout.tsx` via `AuthModalContext`. `PlayerModel` also has its own local `showLogin` / `showRegister` state and renders `LoginModal` / `RegisterModal` inline. This creates two separate modal systems that can conflict. The local modals are redundant — remove them and route through the global context.

**Delete from `PlayerModel`:**
- `const [showLogin, setShowLogin] = useState(false)`
- `const [showRegister, setShowRegister] = useState(false)`
- The `LoginModal` and `RegisterModal` JSX blocks and their imports

**Add to imports:**
```typescript
import { useAuthModal } from '@/contexts/AuthModalContext';
```

**Add inside component:**
```typescript
const { openLogin } = useAuthModal();
```

**Update the PaywallGate call:**
```tsx
<PaywallGate
  ctaTitle="Season probability trend"
  ctaBody="See how the model has rated this player week-by-week all season."
  onGetAccess={openLogin}
>
  <ProbabilityChart data={selectedPlayerData.weeklyData} />
</PaywallGate>
```

### Change 7 — `page.tsx`: move `fetchWeek` to a shared utility or custom hook

**Why:** `page.tsx` currently does an inline `fetchWeek` in a `useEffect` directly in the page component. This is fine for now, but the status/week fetch is a shared data dependency — `WeeklyValue`, `PlayerModel`, and the NavBar badge all depend on it. As the app grows, duplicating this fetch or threading `currentWeek`/`currentYear` as props will get unwieldy.

Create `hooks/useCurrentWeek.ts`:

```typescript
import { useState, useEffect } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? '';

interface WeekStatus {
  week: number | null;
  season: number | null;
  isEarlySeason: boolean;
}

export function useCurrentWeek(): WeekStatus {
  const [status, setStatus] = useState<WeekStatus>({
    week: null,
    season: null,
    isEarlySeason: false,
  });

  useEffect(() => {
    async function fetchWeek() {
      try {
        const resp = await fetch(`${API_URL}/api/status/week`);
        if (!resp.ok) return;
        const data = await resp.json();
        setStatus({
          week: data.week ?? null,
          season: data.season ?? null,
          isEarlySeason: data.is_early_season ?? false,
        });
      } catch {
        // silent — components handle null week gracefully
      }
    }
    fetchWeek();
  }, []);

  return status;
}
```

Update `page.tsx` to use it:
```typescript
import { useCurrentWeek } from '@/hooks/useCurrentWeek';

// Replace the inline useEffect + useState for week/year with:
const { week: currentWeek, season: currentYear } = useCurrentWeek();
```

This is a small change now but sets the correct pattern — data fetching for shared app state belongs in a hook, not inline in a page component.

### Change 8 — `WeeklyValue`: extract the predictions fetch into a custom hook

**Why:** `WeeklyValue` currently does its data fetching inline in a `useEffect`. This mixes display logic (what to render) with data logic (how to fetch and transform). The same pattern will appear in every tab. Custom hooks for data fetching are the right Next.js/React pattern.

Create `hooks/usePredictions.ts`:

```typescript
import { useState, useEffect } from 'react';
import { useAuth } from '@/hooks/useAuth';
import type { PredictionResponse, TeaserCounts } from '@/types/backend';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? '';

interface PredictionsState {
  predictions: PredictionResponse[];
  teaser: TeaserCounts | null;
  loading: boolean;
  error: string | null;
}

export function usePredictions(season: number, week: number): PredictionsState {
  const { user, getToken } = useAuth();
  const [state, setState] = useState<PredictionsState>({
    predictions: [],
    teaser: null,
    loading: true,
    error: null,
  });

  useEffect(() => {
    async function load() {
      setState((prev) => ({ ...prev, loading: true, error: null }));
      try {
        const token = getToken();
        const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
        const resp = await fetch(`${API_URL}/api/predictions/${season}/${week}`, { headers });
        if (!resp.ok) throw new Error('Failed to fetch predictions');
        const data = await resp.json();
        setState({
          predictions: data.predictions ?? [],
          teaser: data.teaser ?? null,
          loading: false,
          error: null,
        });
      } catch (err) {
        setState({
          predictions: [],
          teaser: null,
          loading: false,
          error: err instanceof Error ? err.message : 'Failed to load predictions',
        });
      }
    }
    load();
  // Re-fetch when auth state changes (login/logout delivers different payload)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [season, week, user]);

  return state;
}
```

Update `WeeklyValue` to use it:
```typescript
import { usePredictions } from '@/hooks/usePredictions';

// Replace the inline useState + useEffect for predictions with:
const { predictions, teaser, loading, error } = usePredictions(effectiveYear, selectedWeek);
// Remove: setPredictions, setTeaser, setLoading, setError state vars
// Remove: the inline loadPredictions useEffect
```

---

## FILES TO CREATE

```
backend_new/app/api/public.py              (modified — new endpoint added)
frontend/hooks/useCurrentWeek.ts           (new)
frontend/hooks/usePredictions.ts           (new)
frontend/types/backend.ts                  (modified — SeasonStatsResponse added)
```

## FILES TO MODIFY

```
backend_new/app/api/public.py              — Change 1, Change 2
backend_new/app/api/deps.py                — Change 3 (docstring only)
frontend/types/backend.ts                  — Change 4
frontend/components/player-lookup/PlayerModel.tsx  — Changes 5, 6
frontend/app/page.tsx                      — Change 7
frontend/components/weekly/WeeklyValue.tsx — Change 8
```

## FILES TO LEAVE ALONE

```
backend_new/app/api/auth.py
backend_new/app/api/admin.py
backend_new/app/models/user.py
backend_new/app/services/auth_service.py
backend_new/app/limiter.py
backend_new/app/config.py
frontend/contexts/AuthContext.tsx
frontend/contexts/AuthModalContext.tsx
frontend/hooks/useAuth.ts
frontend/components/shared/PaywallGate.tsx
frontend/components/weekly/TierSection.tsx
frontend/components/weekly/TierPlayerCard.tsx
frontend/components/weekly/TeaserBanner.tsx
frontend/components/track-record/TrackRecord.tsx
frontend/components/player-lookup/GameLogTable.tsx
frontend/components/player-lookup/PlayerHeader.tsx
frontend/components/player-lookup/HistoricalResultCard.tsx
frontend/components/player-lookup/PredictionSummary.tsx
frontend/types/auth.ts
```

---

## Correctness checklist — verify after implementation

- [ ] Non-subscriber loads Player tab → header shows real TDs/games/targets/TD rate (not zeros)
- [ ] `GET /api/players/{id}/season-stats` returns 200 with no auth header
- [ ] Subscriber loads Player tab → game log table renders, probability chart renders
- [ ] Non-subscriber loads Player tab → game log table absent, probability chart replaced by PaywallGate CTA
- [ ] `usePredictions` hook is used in `WeeklyValue` — no inline useEffect for predictions fetch
- [ ] `useCurrentWeek` hook is used in `page.tsx` — no inline useEffect for week fetch
- [ ] `PlayerModel` has no `showLogin`/`showRegister` state — no `LoginModal`/`RegisterModal` rendered inside it
- [ ] Opening auth modal from PlayerModel's PaywallGate opens the global `AuthModal` (not a second modal)
- [ ] `PredictionRow` in `public.py` has no `locked` field and `final_prob`/`model_odds` are non-optional
- [ ] `deps.py` docstring references only `get_optional_user`, `require_auth`, `require_subscriber`
- [ ] `_assign_tiers` has no type errors — `final_prob` is `float`, comparisons are safe

---

## What this does NOT include (future phases)

- Stripe webhook handler to flip `is_subscriber`
- Email verification on registration
- Password reset flow
- Account settings / profile page

These are all correct next phases. The architecture established here (single `is_subscriber` boolean, JWT carries the claim, `require_subscriber` dependency, `useAuth().isSubscriber` as the frontend single source of truth) supports all of them without structural changes.
