# Admin Page — NavBar Fix

## Phase 2 UI Redesign: Verified Correct ✅

The Pipeline and Week Override panels are correctly redesigned:
- Two-column layout (action controls left, run log right) ✅
- Ghost/outline `▶ run` buttons, no filled purple ✅
- Terminal-style run log with per-entry status/counts/events ✅
- Week Override uses bottom-border inputs and text-link clear ✅
- `RunEntry` state pattern, `runningAction` mutex, session-only log ✅
- All four panels rendering, sidebar wired correctly ✅

## Bug: No NavBar on Admin Page

**Root cause:** `app/layout.tsx` only wraps providers (`AuthProvider`, `AuthModalProvider`). The `NavBar` component is instantiated inside `app/page.tsx` (the home page), so it only exists on the `/` route. When the admin tab does `router.push('/admin')`, the user lands on a completely bare page with no way to navigate back to the main app.

**Fix:** Add the `NavBar` to `app/admin/page.tsx`.

---

## What to Change

### 1. Update `app/admin/page.tsx`

**Add import:**
```typescript
import { NavBar } from '@/components/shared/NavBar';
import { useRouter } from 'next/navigation';
```

**Add state for the current week** (NavBar requires it for the WeekBadge):
```typescript
import { useCurrentWeek } from '@/hooks/useCurrentWeek';
```

Inside `AdminPage`, add:
```typescript
const router = useRouter();
const { week: currentWeek } = useCurrentWeek();
```

**Update the NavBar `onTabChange` handler** — when the admin clicks a main tab (weekly/player/track), navigate back to home with that tab as a query param:
```typescript
function handleTabChange(tab: 'weekly' | 'player' | 'track') {
  router.push(`/?tab=${tab}`);
}
```

**Wrap the admin page content with NavBar**, matching the same structure as `app/page.tsx`:

```tsx
return (
  <div className="min-h-screen bg-sr-bg">
    <NavBar
      activeTab={'weekly'}         // no tab is "active" on the admin page — weekly is fine as default
      onTabChange={handleTabChange}
      currentWeek={currentWeek}
    />
    <main className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-6">
      <div className="flex gap-6 min-h-[calc(100vh-8rem)]">
        {/* Sidebar */}
        <nav className="w-48 shrink-0">
          {/* ... existing sidebar ... */}
        </nav>
        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* ... existing panel renders ... */}
        </div>
      </div>
    </main>
  </div>
);
```

**Also update the non-admin fallback return** to include the NavBar so the page isn't completely blank if someone hits `/admin` without admin access:
```tsx
if (!isAdmin) {
  return (
    <div className="min-h-screen bg-sr-bg">
      <NavBar activeTab={'weekly'} onTabChange={handleTabChange} currentWeek={currentWeek} />
      <div className="flex items-center justify-center min-h-[50vh]">
        <p className="text-sr-text-muted">You do not have permission to view this page.</p>
      </div>
    </div>
  );
}
```

### 2. Check NavBar for active admin tab styling

In `components/shared/NavBar.tsx`, the Admin button currently always renders with `text-sr-text-muted` styling regardless of whether we're on the admin page. When on `/admin`, the Admin tab should appear active.

The NavBar's `activeTab` prop is typed as `'weekly' | 'player' | 'track'` — it doesn't include `'admin'`. Two options:

**Option A (simpler):** Pass a nullable/extended active tab. Update the NavBar prop type:
```typescript
type Tab = 'weekly' | 'player' | 'track';
interface NavBarProps {
  activeTab: Tab | 'admin';  // extend to allow 'admin'
  onTabChange: (tab: Tab) => void;
  currentWeek: number | null;
}
```
Then in the Admin button render:
```tsx
<button
  onClick={() => router.push('/admin')}
  className={
    activeTab === 'admin'
      ? 'px-4 py-2 text-sm font-medium text-white border-b-2 border-sr-primary transition-colors'
      : 'px-4 py-2 text-sm font-medium text-sr-text-muted hover:text-white transition-colors'
  }
>
  Admin
</button>
```

**Option B (no NavBar changes):** Pass `activeTab={'weekly'}` from the admin page and accept that no tab appears active. This is fine for an internal tool — choose whichever is cleaner.

Pick Option A — it's a small change and makes the active state correct.

### 3. No other files need to change

- `app/layout.tsx` — do not add NavBar here. The layout approach (NavBar per-page vs in layout) is an intentional pattern in this codebase.
- `app/page.tsx` — untouched
- `components/shared/NavBar.tsx` — only change is the `activeTab` type extension and the conditional class on the Admin button (if going with Option A)
- All backend files — untouched

---

## Patterns to follow

- Match the outer wrapper `div` + `main` structure exactly as in `app/page.tsx`
- `useCurrentWeek()` is already used in `app/page.tsx` — same import path
- TypeScript strict — if extending the NavBar prop type, make sure `onTabChange` still only accepts `Tab` (not `'admin'`), since clicking the admin button uses `router.push` directly and doesn't go through `onTabChange`
