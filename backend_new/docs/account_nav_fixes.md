# Account Page — Navigation, Copy & Stale Code Fixes

Read every section. Do not touch anything outside what is listed.

---

## Problem 1 — `/account` has no navbar

`app/account/page.tsx` renders a bare page with no navigation. The user has no way to get back to the main app once they land there. The fix is to render the shared navbar above the page content, with the tabs still functional.

The main `app/page.tsx` owns `activeTab` state and passes it to `NavBar`. The `/account` page is a separate route, so it needs its own navbar instance. The tab state should default to `'weekly'` (the home tab) so clicking any tab navigates back to the home page with that tab active.

**The desired behavior:** `/account` sits beneath the same navbar as the rest of the app. Clicking "This Week", "Player Lookup", or "Track Record" navigates back to `/` with that tab pre-selected. The nav feels continuous — not like a separate site.

### How to implement

Use `next/navigation`'s `useRouter` to push `/?tab=weekly` (or `player`, `track`) when a tab is clicked from the account page, and read that query param in `app/page.tsx` to set the initial active tab.

**Changes to `app/page.tsx`:**
- On mount, read the `?tab` query param using `useSearchParams`
- If a valid tab value is present (`'weekly' | 'player' | 'track'`), use it as the initial `activeTab` state instead of `'weekly'`
- Default behavior is unchanged — no param defaults to `'weekly'`
- Wrap the existing `useState` default in a lazy initializer or `useSearchParams` read

**Changes to `app/account/page.tsx`:**
- Import `NavBar` from `components/shared/NavBar`
- Import `useRouter` from `next/navigation`
- Add local `activeTab` state defaulting to `'weekly'`
- Fetch `currentWeek` from `/api/status/week` on mount (same pattern as `useCurrentWeek`) — pass `null` on failure, `WeekBadge` handles null gracefully
- Wire `NavBar` with `activeTab`, a tab-change handler that calls `router.push(`/?tab=${tab}`)`, and `currentWeek`
- Remove `min-h-screen` from the outer div and place it on a wrapper that sits beneath the navbar

```tsx
return (
  <div className="min-h-screen bg-sr-bg">
    <NavBar
      activeTab={activeTab}
      onTabChange={(tab) => router.push(`/?tab=${tab}`)}
      currentWeek={currentWeek}
    />
    <div className="mx-auto max-w-2xl px-4 sm:px-6 lg:px-8 py-10">
      <h1 className="text-white font-bold text-2xl mb-8">My Account</h1>
      <div className="space-y-6">
        <ProfileCard />
        <ChangePasswordCard />
        <SubscriptionCard />
      </div>
    </div>
  </div>
);
```

---

## Problem 2 — NavUserMenu shows stale tier badge

`NavUserMenu.tsx` renders a "Pro" or "Free" badge based on `user.is_subscriber`. Every registered user is currently a subscriber — "Free" will never show until Stripe lands. Dead UI.

**Fix:** Remove the tier badge entirely from the trigger button and the dropdown header.

Remove from the trigger button:
```tsx
// Delete this block entirely
{isPro ? (
  <span className="bg-emerald-900/50 text-sr-success text-xs rounded-full px-2 py-0.5 font-medium hidden sm:block">
    Pro
  </span>
) : (
  <span className="bg-sr-border text-sr-text-muted text-xs rounded-full px-2 py-0.5 font-medium hidden sm:block">
    Free
  </span>
)}
```

Remove from the dropdown header:
```tsx
// Delete this line
<p className="text-xs text-sr-text-muted mt-0.5">
  {isPro ? 'Pro member' : 'Free tier'}
</p>
```

Remove `const isPro = user.is_subscriber` — nothing will reference it.

---

## Problem 3 — Cancellation success copy implies Stripe billing

`SubscriptionCard` shows on successful cancellation:

> "Subscription cancelled. You'll retain access until the end of your billing period."

Stripe isn't wired up — there is no billing period. Replace with:

```tsx
<p className="text-sm text-sr-success" role="status" aria-live="polite">
  Subscription cancelled. Your access has been removed.
</p>
```

---

## Problem 4 — TeaserBanner missing Sign In link

`TeaserBanner.tsx` only has a "Get Access" button. A logged-out user who already has an account has no path to sign in from the teaser — they're forced to find the sign-in button elsewhere. The sprint spec called for both.

**Fix:** Add a "Sign in" text link alongside the "Get Access" button. Import `useAuthModal` (already imported), call `openLogin`.

```tsx
// Replace the single button with:
<div className="flex items-center gap-3 flex-shrink-0">
  <button
    onClick={openLogin}
    className="text-xs text-sr-text-muted hover:text-white underline underline-offset-2 transition-colors"
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
```

`openLogin` is already available on `useAuthModal()` — just destructure it alongside `openRegister`.

---

## Problem 5 — PlayerWeekToggle uses raw Tailwind grays instead of design tokens

`PlayerWeekToggle.tsx` uses hardcoded `gray-*` classes (`bg-gray-900/60`, `border-gray-800/50`, `text-gray-300`, `text-gray-700`) while every other component uses the `sr-*` design token system. This is visually inconsistent and will break if the theme changes.

**Fix:** Replace with token equivalents:

| Old class | Replacement |
|---|---|
| `bg-gray-900/60` | `bg-sr-surface/60` |
| `border-gray-800/50` | `border-sr-border/50` |
| `text-gray-300` | `text-sr-text-muted` |
| `text-gray-700` (disabled) | `text-sr-text-dim` |
| `hover:bg-gray-800` | `hover:bg-sr-border/30` |
| `hover:text-white` | `hover:text-white` (keep) |

Full updated component:

```tsx
<div className="flex items-center gap-2 bg-sr-surface/60 border border-sr-border/50 rounded-lg p-1">
  <button
    onClick={handleBack}
    disabled={backDisabled}
    className={`p-2 rounded-md transition-all ${
      backDisabled
        ? 'text-sr-text-dim cursor-not-allowed'
        : 'text-sr-text-muted hover:text-white hover:bg-sr-border/30'
    }`}
    aria-label="Previous week"
  >
    <ChevronLeft className="w-4 h-4" />
  </button>

  <div className="px-4 py-1 text-sm text-white min-w-[80px] text-center">
    <span className="text-sr-text-muted">Week</span>{' '}
    <span className="font-semibold nums">{selectedWeek}</span>
  </div>

  <button
    onClick={handleForward}
    disabled={!canGoForward}
    className={`p-2 rounded-md transition-all ${
      canGoForward
        ? 'text-sr-text-muted hover:text-white hover:bg-sr-border/30'
        : 'text-sr-text-dim cursor-not-allowed'
    }`}
    aria-label="Next week"
  >
    <ChevronRight className="w-4 h-4" />
  </button>
</div>
```

---

## Problem 6 — WeeklyValue doesn't pass lockedToCurrentWeek to PlayerWeekToggle

`WeeklyValue.tsx` renders a `PlayerWeekToggle` but never passes `lockedToCurrentWeek`. The prop defaults to `false`, so non-subscribers can freely browse historical weekly predictions. `PlayerModel` passes this correctly — `WeeklyValue` should too.

**Fix:** Pass `lockedToCurrentWeek={!isSubscriber}` on the `PlayerWeekToggle` in `WeeklyValue`:

```tsx
<PlayerWeekToggle
  currentWeek={currentWeek ?? 18}
  currentYear={effectiveYear}
  selectedWeek={selectedWeek}
  onWeekChange={setSelectedWeek}
  lockedToCurrentWeek={!isSubscriber}   // ← add this
/>
```

`isSubscriber` is already destructured from `useAuth()` at the top of `WeeklyValue` — no new imports needed.

---

## Files to modify

```
frontend/app/account/page.tsx               ← add NavBar, currentWeek fetch, tab routing
frontend/app/page.tsx                       ← read ?tab query param for initial tab state
frontend/components/shared/NavUserMenu.tsx  ← remove tier badge
frontend/components/weekly/TeaserBanner.tsx ← add Sign In link alongside Get Access
frontend/components/weekly/PlayerWeekToggle.tsx  ← replace gray-* classes with sr-* tokens
frontend/components/weekly/WeeklyValue.tsx  ← pass lockedToCurrentWeek to PlayerWeekToggle
```

## Files to leave alone

Everything else. Do not touch backend, hooks, context, or any other frontend component.

---

## Correctness checklist

- [ ] `/account` renders the navbar at the top — same visual style as the home page
- [ ] Clicking "This Week" from `/account` navigates to `/?tab=weekly` and that tab is active
- [ ] Clicking "Player Lookup" from `/account` navigates to `/?tab=player`
- [ ] Clicking "Track Record" from `/account` navigates to `/?tab=track`
- [ ] Direct navigation to `/?tab=player` opens the app with Player Lookup as the active tab
- [ ] Direct navigation to `/` (no param) defaults to "This Week" tab — unchanged behavior
- [ ] NavUserMenu trigger shows avatar + name + chevron only — no tier badge
- [ ] NavUserMenu dropdown shows name only — no "Pro member" / "Free tier" subtitle
- [ ] Cancellation success message reads "Your access has been removed" — no billing period language
- [ ] TeaserBanner has both a "Sign in" text link and a "Get Access" button
- [ ] Sign in link opens the login panel; Get Access opens the register panel
- [ ] PlayerWeekToggle uses sr-* design tokens — no hardcoded gray-* classes
- [ ] Non-subscribers on the weekly tab cannot navigate to historical weeks
- [ ] Subscribers on the weekly tab can navigate freely — lockedToCurrentWeek behavior is unchanged for them
