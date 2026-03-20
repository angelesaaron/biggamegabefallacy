# Claude Code Prompt — WeeklyValue Week Initialization Fix

## Problem
`WeeklyValue` has two issues:

1. **Prop-to-state sync resets user navigation.** The current `useEffect` copies
   `currentWeek` into `selectedWeek` every time `currentWeek` changes. If a user
   navigates to week 15 and then `currentWeek` re-resolves (e.g. tab refocus,
   re-render), `selectedWeek` silently resets back to the current week, discarding
   the user's navigation.

2. **Double `useCurrentWeek()` call.** `WeeklyValue` receives `currentWeek` and
   `currentYear` as props from `HomeContent` (which calls `useCurrentWeek()`), but
   also calls `useCurrentWeek()` directly to get `source` for the admin badge. This
   fires a second fetch to `/api/status/week` on every page load.

## Solution

**Fix 1 — `useRef` guard for one-time initialization.**
Replace the bare `useEffect` with a ref-guarded version that only sets
`selectedWeek` once — on the first time `currentWeek` resolves from null to a
value. Subsequent changes to `currentWeek` (re-renders, refocus) do not reset
the user's navigation.

**Fix 2 — Pass `source` as a prop instead of calling the hook twice.**
`HomeContent` already calls `useCurrentWeek()`. It should destructure `source`
from that call and pass it down to `WeeklyValue` as a prop. `WeeklyValue` removes
its direct `useCurrentWeek()` call entirely.

---

## Changes Required

### `frontend/app/page.tsx`

`HomeContent` already does:
```typescript
const { week: currentWeek, season: currentYear } = useCurrentWeek();
```

Change to also destructure `source`:
```typescript
const { week: currentWeek, season: currentYear, source: weekSource } = useCurrentWeek();
```

Pass it to `WeeklyValue`:
```tsx
<WeeklyValue
  currentWeek={currentWeek}
  currentYear={currentYear}
  weekSource={weekSource}
  onPlayerClick={handlePlayerClick}
/>
```

### `frontend/components/weekly/WeeklyValue.tsx`

**Update props interface** — add `weekSource`, remove reliance on the hook:
```typescript
interface WeeklyValueProps {
  currentWeek: number | null;
  currentYear: number | null;
  weekSource: 'admin_override' | 'pipeline' | 'default' | null;
  onPlayerClick: (playerId: string) => void;
}
```

**Update component signature** to accept `weekSource`:
```typescript
export function WeeklyValue({ currentWeek, currentYear, weekSource, onPlayerClick }: WeeklyValueProps) {
```

**Remove the direct hook call** — delete this line entirely:
```typescript
const { source } = useCurrentWeek();  // DELETE
```

**Replace `source` references** with `weekSource` — there is one usage in the
admin override badge:
```tsx
{source === 'admin_override' && (...)}
// becomes:
{weekSource === 'admin_override' && (...)}
```

**Replace the bare useEffect with a ref-guarded version:**

Remove:
```typescript
useEffect(() => {
  if (currentWeek !== null) setSelectedWeek(currentWeek);
}, [currentWeek]);
```

Add (requires importing `useRef`):
```typescript
import { useEffect, useRef, useState } from 'react';

const initialized = useRef(false);

useEffect(() => {
  if (!initialized.current && currentWeek !== null) {
    setSelectedWeek(currentWeek);
    initialized.current = true;
  }
}, [currentWeek]);
```

**Remove `useCurrentWeek` from the import** at the top of `WeeklyValue.tsx` —
it is no longer called in this file.

---

## Files to Modify
- `frontend/app/page.tsx` — destructure `source`, pass as `weekSource` prop
- `frontend/components/weekly/WeeklyValue.tsx` — add prop, remove hook call,
  add `useRef`, replace `useEffect`

## Files to Leave Untouched
- `hooks/useCurrentWeek.ts` — no changes
- `PlayerWeekToggle.tsx` — no changes
- Any backend file

---

## Correctness Checklist
- [ ] `useCurrentWeek()` is called exactly once in this component tree — in `HomeContent`
- [ ] `WeeklyValue` does NOT import or call `useCurrentWeek`
- [ ] `initialized.current` starts as `false` and is set to `true` after the first
      non-null `currentWeek` — never reset
- [ ] `selectedWeek` is only initialized once; user navigation is never overwritten
      by subsequent `currentWeek` changes
- [ ] `useRef` is imported alongside `useEffect` and `useState` in `WeeklyValue`
- [ ] `weekSource` prop is typed as `'admin_override' | 'pipeline' | 'default' | null`
      matching the `WeekStatus` interface in `useCurrentWeek.ts`
- [ ] The admin override badge condition uses `weekSource` not `source`
- [ ] `page.tsx` passes `weekSource` to `WeeklyValue` (not `source` — rename to
      avoid shadowing)
