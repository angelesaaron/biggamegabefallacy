# UI Polish + Minor Fixes — Claude Code Prompt

Four small targeted changes. Read all of them before touching any file.

---

## Fix 1 — `PaywallGate`: remove the "Already have an account? Sign in" secondary button

**File:** `frontend/components/shared/PaywallGate.tsx`

**Problem:** When a non-logged-in user sees the gate, it shows "Get Access" (primary button) and below it "Already have an account? Sign in" (secondary underline link). "Get Access" already opens the register modal which has a "sign in" link inside it. The secondary button is redundant and clutters the CTA.

**Change:** In the unauthenticated branch, replace the `<div>` with two buttons with just the single primary button. Keep the `user ?` branch (logged in, not subscribed) exactly as-is — that one correctly shows "Upgrade to unlock" and there's no duplicate there.

```tsx
// Remove this entire block:
{user ? (
  <button ...>Upgrade to unlock</button>
) : (
  <div className="flex flex-col items-center gap-2">
    <button onClick={onGetAccess ?? openRegister}>Get Access</button>
    <button onClick={openLogin}>Already have an account? Sign in</button>
  </div>
)}

// Replace with:
{user ? (
  <button
    type="button"
    onClick={onGetAccess ?? openRegister}
    className="bg-sr-primary text-white px-6 py-2.5 rounded-card text-sm font-semibold hover:bg-sr-primary/80 transition-colors"
  >
    Upgrade to unlock
  </button>
) : (
  <button
    type="button"
    onClick={onGetAccess ?? openRegister}
    className="bg-sr-primary text-white px-6 py-2.5 rounded-card text-sm font-semibold hover:bg-sr-primary/80 transition-colors"
  >
    Get Access
  </button>
)}
```

Also remove the `openLogin` destructure from `useAuthModal()` since it's no longer used in this component:
```tsx
// Change:
const { openRegister, openLogin } = useAuthModal();
// To:
const { openRegister } = useAuthModal();
```

---

## Fix 2 — `TeaserBanner`: remove the "Sign in" secondary button

**File:** `frontend/components/weekly/TeaserBanner.tsx`

**Same problem as Fix 1.** The banner has a "Sign in" underline link sitting next to "Get Access". Same reasoning — redundant. Remove it.

```tsx
// Remove:
<div className="flex items-center gap-3 flex-shrink-0">
  <button
    onClick={openLogin}
    className="text-xs text-sr-text-muted hover:text-white underline underline-offset-2"
  >
    Sign in
  </button>
  <button
    onClick={openRegister}
    className="bg-sr-primary text-white px-4 py-2 rounded-card text-xs font-semibold hover:bg-sr-primary/80 transition-colors"
  >
    Get Access
  </button>
</div>

// Replace with:
<button
  onClick={openRegister}
  className="bg-sr-primary text-white px-4 py-2 rounded-card text-xs font-semibold hover:bg-sr-primary/80 transition-colors flex-shrink-0"
>
  Get Access
</button>
```

Also remove the `openLogin` destructure since it's no longer used:
```tsx
// Change:
const { openRegister, openLogin } = useAuthModal();
// To:
const { openRegister } = useAuthModal();
```

---

## Fix 3 — `PlayerWeekToggle`: remove the upgrade hint message entirely

**File:** `frontend/components/weekly/PlayerWeekToggle.tsx`

**Problem:** When a non-subscriber clicks the back arrow (which is visually dimmed), it shows a small tooltip message "Unlock full season history — Upgrade to Pro". The preference is for the button to simply be unclickable with no message — it already looks disabled, which is sufficient.

**Changes:**

1. Remove all the `showUpgradeHint` state and timer logic
2. Remove the `useEffect` that manages the timer
3. Remove the `hintTimerRef`
4. Change `handleBack` to simply return early when locked — no `setShowUpgradeHint`
5. Remove the hint `<div>` at the bottom of the return
6. Remove the `useAuthModal` import entirely — it's only used for `openRegister` in the hint, which is being removed

```tsx
// Final component should look like this:
'use client';

import { ChevronLeft, ChevronRight } from 'lucide-react';

interface PlayerWeekToggleProps {
  currentWeek: number;
  currentYear: number;
  selectedWeek: number;
  onWeekChange: (week: number) => void;
  lockedToCurrentWeek?: boolean;
}

export function PlayerWeekToggle({
  currentWeek,
  currentYear,
  selectedWeek,
  onWeekChange,
  lockedToCurrentWeek = false,
}: PlayerWeekToggleProps) {
  const canGoBack = selectedWeek > 1;
  const canGoForward = selectedWeek < 18;
  const backIsLocked = lockedToCurrentWeek && selectedWeek <= currentWeek;
  const backDisabled = !canGoBack || backIsLocked;

  function handleBack() {
    if (backDisabled) return;
    onWeekChange(selectedWeek - 1);
  }

  function handleForward() {
    if (!canGoForward) return;
    onWeekChange(selectedWeek + 1);
  }

  return (
    <div className="flex items-center gap-2 bg-gray-900/60 border border-gray-800/50 rounded-lg p-1">
      <button
        onClick={handleBack}
        disabled={backDisabled}
        className={`p-2 rounded-md transition-all ${
          backDisabled
            ? 'text-gray-700 cursor-not-allowed'
            : 'text-gray-300 hover:text-white hover:bg-gray-800'
        }`}
        aria-label="Previous week"
      >
        <ChevronLeft className="w-4 h-4" />
      </button>

      <div className="px-4 py-1 text-sm text-white min-w-[80px] text-center">
        <span className="text-gray-300">Week</span>{' '}
        <span className="font-semibold nums">{selectedWeek}</span>
      </div>

      <button
        onClick={handleForward}
        disabled={!canGoForward}
        className={`p-2 rounded-md transition-all ${
          canGoForward
            ? 'text-gray-300 hover:text-white hover:bg-gray-800'
            : 'text-gray-700 cursor-not-allowed'
        }`}
        aria-label="Next week"
      >
        <ChevronRight className="w-4 h-4" />
      </button>
    </div>
  );
}
```

Note the outer wrapper also simplifies from `flex flex-col items-center gap-1` to just `flex items-center gap-2` — the `flex-col` and gap were only there to make room for the hint div below.

---

## Fix 4 — Move `SeasonStatsResponse` schema to top of `public.py`

**File:** `backend_new/app/api/public.py`

**Problem:** `SeasonStatsResponse` is defined inline just above its route endpoint, breaking the pattern of all other Pydantic schemas being grouped at the top of the file with `PredictionRow`, `PlayerRow`, `HistoryRow` etc.

**Change:** Cut `SeasonStatsResponse` from its current location (above `get_player_season_stats`) and paste it into the schema block at the top of the file, after `HistoryRow` and before the helpers section.

The schema block order should be:
```python
class PredictionRow(BaseModel): ...
class TeaserCounts(BaseModel): ...
class PredictionsResponse(BaseModel): ...
class PlayerRow(BaseModel): ...
class HistoryRow(BaseModel): ...
class SeasonStatsResponse(BaseModel): ...    # ← move here
class GameLogRow(BaseModel): ...
class GameLogsResponse(BaseModel): ...
class PlayerOddsResponse(BaseModel): ...
class WeekStatusResponse(BaseModel): ...
# ... track record schemas ...
```

No logic changes — just a move. The route function itself stays exactly where it is.

---

## Fix 5 — Use `PredictionsApiResponse` type in `usePredictions` hook

**File:** `frontend/hooks/usePredictions.ts`

**Problem:** `PredictionsApiResponse` is exported from `types/backend.ts` but not used anywhere — the hook accesses `data.predictions` and `data.teaser` from an untyped response object.

**Change:** Import and apply the type in the hook. Also extend it inline to cover the full response shape including `season`, `week`, and `count` which the backend also returns.

```typescript
import type { PredictionResponse, TeaserCounts, PredictionsApiResponse } from '@/types/backend';

// Inside the load() function, type the parsed response:
const data = await resp.json() as PredictionsApiResponse;
setState({
  predictions: data.predictions ?? [],
  teaser: data.teaser ?? null,
  loading: false,
  error: null,
});
```

Also update `PredictionsApiResponse` in `types/backend.ts` to match the full response shape the backend actually sends:

```typescript
// In frontend/types/backend.ts, replace:
export interface PredictionsApiResponse {
  predictions: PredictionResponse[];
  teaser: TeaserCounts;
}

// With:
export interface PredictionsApiResponse {
  season: number;
  week: number;
  count: number;
  predictions: PredictionResponse[];
  teaser: TeaserCounts;
}
```

---

## Files to modify

```
frontend/components/shared/PaywallGate.tsx         — Fix 1
frontend/components/weekly/TeaserBanner.tsx        — Fix 2
frontend/components/weekly/PlayerWeekToggle.tsx    — Fix 3
backend_new/app/api/public.py                      — Fix 4 (schema move only)
frontend/hooks/usePredictions.ts                   — Fix 5
frontend/types/backend.ts                          — Fix 5
```

## Files to leave alone

Everything else. These are the only six files touched.

---

## Verify after

- [ ] PaywallGate CTA shows one button only ("Get Access" for logged-out, "Upgrade to unlock" for logged-in non-subscriber)
- [ ] TeaserBanner shows one button only ("Get Access")
- [ ] Clicking the dimmed back arrow on PlayerWeekToggle does nothing, no message appears
- [ ] `PlayerWeekToggle` has no `useAuthModal` import
- [ ] `SeasonStatsResponse` is in the schema block at the top of `public.py`, not inline above its route
- [ ] `usePredictions` has no TypeScript type errors — `data` is typed as `PredictionsApiResponse`
