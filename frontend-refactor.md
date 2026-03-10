# Signal Route — Frontend Refactor & Cutover Plan

**Date**: 2026-03-09
**Branch**: refactor
**Stack**: Next.js 14 + React 18 + TypeScript
**Goal**: Drop MUI → Tailwind-only + shadcn/ui. Keep "Big Game Gabe" brand. Remove Gabe Davis NIL assets (headshot, photos, full name). Add Track Record surface.

---

## Component Disposition Audit

| Component | MUI? | Action | Phase |
|---|---|---|---|
| `page.tsx` | Heavy (AppBar, Tabs, Box, Avatar, Typography, Container) | Rewrite | 1 |
| `WeeklyValue.tsx` | Heaviest (Box, Card, Tabs, ToggleButtonGroup, Checkbox, CircularProgress, icons) | Rewrite | 1 |
| `PlayerModel.tsx` | None | Edit (2 targeted changes) | 1 |
| `PlayerHeader.tsx` | Heavy (Card, Avatar, useTheme, useMediaQuery) | Rewrite | 1 |
| `ValuePlayerCard.tsx` | Heavy (Card, Avatar, useTheme, useMediaQuery) | Rewrite | 1 |
| `SystemStatus.tsx` | Medium | Move to `/admin` route | 1 |
| `system-status/*.tsx` | Mixed (read before migrating) | Move to `/admin` route | 1 |
| `PredictionSummary.tsx` | None | Edit (tabular-nums + sportsbook cleanup) | 0/1 |
| `GameLogTable.tsx` | None | Edit (default expanded) | 0 |
| `PlayerWeekToggle.tsx` | None | Edit (tabular-nums) | 0 |
| `ProbabilityChart.tsx` | None | No change | — |
| `PlayerSelector.tsx` | None | No change (shadcn Popover upgrade optional) | — |
| `GamblingDisclaimer.tsx` | None | No change | — |

### Critical Issues Found

1. **Admin endpoint called from 3 public components** — `page.tsx:25`, `WeeklyValue.tsx:72`, `PlayerModel.tsx:46` all call `/api/admin/data-readiness/current`. Must not ship to production.
2. **Sportsbook toggle is silently broken** — `WeeklyValue.tsx` defaults to `'draftkings'` and reads `oddsData.sportsbook_odds?.draftkings`. Backend_new stores `sportsbook='consensus'` only — all odds render "N/A", `has_edge` is always false.
3. **Gabe Davis likeness assets in 4 locations** — `WeeklyValue.tsx`, `PlayerModel.tsx`, `layout.tsx` (OG/favicon), `page.tsx` (Avatar src). Plus hardcoded name string `PlayerModel.tsx:87`. Remove assets and the "Gabe Davis" name string; keep "Big Game Gabe" / "BGGTDM" branding.
4. **Tailwind version mismatch** — `package.json` says `^3.3.0` but `globals.css` compiled output shows v4 syntax. Verify: `cd frontend && npx tailwindcss --version`. shadcn/ui init differs between v3 and v4 — check docs before running.
5. **globals.css split-brain** — `:root` at line 1308 defines `--background: #fff` (light mode). Never applied to visible UI. Must be replaced with Signal Route dark tokens.

---

## Brand System

### Identity
- **Brand name**: Big Game Gabe (keep — "Big Game Gabe" is the brand, not Gabe Davis' NIL)
- **What to remove**: Gabe Davis headshot, Gabe Davis background photo, the string "Gabe Davis" anywhere user-facing, any likeness-based assets
- **What to keep**: "Big Game Gabe", "BGGTDM", all existing brand copy
- **Tagline**: "Where the model points, the edge follows."
- **Sub-CTA**: "See every ATTD edge before Sunday."
- **Voice**: Precise, Confident-not-hyped, Sharp-but-accessible, Honest, Focused. Never "LOCKS", "GUARANTEED", "CAN'T MISS".

### Color Semantics
- **Purple** (`#a855f7`) = model data (model probability, model odds)
- **White** (`#ffffff`) = sportsbook data (sportsbook odds)
- **Green** (`#10b981`) = positive edge / value
- **Red** (`#f43f5e`) = negative edge / no value
- **Amber** (`#d97706`) = +EV indicator highlight (Pavlovian association: amber = value)

### Direction
- Dark/purple direction. Deepen primary range toward `#6d28d9–#7c3aed` for hover/active states.
- Add amber `#d97706` for +EV call-to-action highlights and "value play" indicators.

---

## Design Token System

### 1. `app/globals.css` — replace `:root` block

Remove the `.dark {}` block entirely. App is dark-only.

```css
:root {
  /* Brand palette */
  --color-bg:             #0a0a0a;
  --color-surface:        #111827;
  --color-surface-raised: #1a2332;   /* dropdowns, tooltips */
  --color-primary:        #a855f7;
  --color-primary-muted:  #7c3aed;   /* hover/active states */
  --color-success:        #10b981;
  --color-danger:         #f43f5e;
  --color-ev:             #d97706;   /* amber: +EV indicators */
  --color-border:         #1f2937;

  /* Surface alpha variants */
  --color-surface-40: rgba(17, 24, 39, 0.40);
  --color-surface-60: rgba(17, 24, 39, 0.60);

  /* Text hierarchy */
  --color-text-primary:   #f9fafb;
  --color-text:           #ffffff;
  --color-text-muted:     #9ca3af;
  --color-text-dim:       #6b7280;
  --color-text-disabled:  #374151;

  /* Semantic edge states */
  --color-edge-positive: #10b981;
  --color-edge-negative: #f43f5e;
  --color-edge-ev:       #d97706;

  /* Geometry */
  --radius-card:  1rem;
  --radius-badge: 9999px;

  /* shadcn compatibility — keep these pointing at dark values */
  --background: #0a0a0a;
  --foreground: #f9fafb;
  --card: #111827;
  --card-foreground: #f9fafb;
  --border: #1f2937;
  --ring: #a855f7;
  --radius: 0.625rem;
}

body {
  background-color: var(--color-bg);
  color: var(--color-text);
  -webkit-font-smoothing: antialiased;
}

@layer utilities {
  /* Apply to every element rendering odds, probabilities, or edge values */
  .nums {
    font-variant-numeric: tabular-nums;
    font-feature-settings: "tnum";
  }
}
```

### 2. `tailwind.config.ts` — full replacement

```typescript
import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        sr: {
          bg:             "#0a0a0a",
          surface:        "#111827",
          "surface-raised":"#1a2332",
          primary:        "#a855f7",
          "primary-muted":"#7c3aed",
          success:        "#10b981",
          danger:         "#f43f5e",
          ev:             "#d97706",
          border:         "#1f2937",
          text:           "#ffffff",
          "text-primary": "#f9fafb",
          "text-muted":   "#9ca3af",
          "text-dim":     "#6b7280",
          "text-disabled":"#374151",
        },
      },
      borderRadius: {
        card:  "1rem",
        badge: "9999px",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
```

### 3. Typography Scale

Font: Inter (keep). All odds and probability values must use `.nums` (tabular-nums).

| Role | Size | Weight | Usage |
|---|---|---|---|
| Display | `text-7xl` (4.5rem) | 700 | TD probability percentage |
| H1 | `text-3xl` (1.875rem) | 600 | Section titles |
| H2 | `text-2xl` (1.5rem) | 600 | Card headers |
| H3 | `text-lg` (1.125rem) | 500 | Player name |
| Body | `text-base` (1rem) | 400 | Table values |
| Label | `text-sm` (0.875rem) | 500 | Stat labels |
| Caption | `text-xs` (0.75rem) | 400 | Metadata, disclaimers |

### 4. Numbers Display Standards

Apply consistently across all components:

| Element | Classes |
|---|---|
| TD probability | `text-7xl font-bold text-white nums` — "%" in `text-3xl text-sr-text-muted` |
| Model odds | `text-2xl font-semibold text-sr-primary nums` |
| Sportsbook odds | `text-2xl font-semibold text-white nums` |
| Edge value | `text-xl font-bold nums` + `text-sr-success` or `text-sr-danger`, always show sign (`+4.2%` / `-1.8%`) |
| +EV highlight | `text-sr-ev font-semibold` (amber) for high-value indicator badges |

---

## Phase 0 — Quick Wins (No MUI Removal)

Ship immediately. All changes are independent. Zero MUI removal risk.

### 0.1 — Token Foundation
Apply CSS token system and Tailwind config above. Prerequisite for everything in Phase 1.

### 0.2 — AppBar Rebrand + Avatar Removal (`page.tsx`)

- Remove `Avatar` import and `<Avatar>` element (the Gabe Davis headshot)
- Keep `BGGTDM` wordmark text or update to `Big Game Gabe` — remove only the Gabe Davis Avatar image next to it
- Replace AppBar `bgcolor: 'rgba(0,0,0,0.4)'` → `background: 'linear-gradient(to bottom, #0a0a0a, rgba(10,10,10,0.85))'`
- Rename tabs: "Player Model" → "Player Lookup", "Weekly Value" → "This Week"
- Remove "System Status" tab (3rd tab). Update state type: `'player' | 'weekly'`. Remove `{activeTab === 'status' && <SystemStatus />}` render.
- Replace week `<Typography h3>` pill with Tailwind:
  ```jsx
  {currentWeek && (
    <div className="flex items-center gap-1 px-3 py-1 bg-[#111827] border border-[#1f2937] rounded-full">
      <span className="text-xs text-gray-400 uppercase tracking-wide">Wk</span>
      <span className="text-sm font-semibold text-white nums">{currentWeek}</span>
    </div>
  )}
  ```

### 0.3 — Admin API Fallback (3 components)

Add `if (!response.ok) return;` + silent catch to all three admin endpoint calls. Comment each with `// TODO Phase 1.5: replace with public /api/status/week`:
- `page.tsx` lines 21–38
- `PlayerModel.tsx` line ~46
- `WeeklyValue.tsx` line ~72

### 0.4 — GameLogTable Default Expanded

`GameLogTable.tsx` line 18: `useState(false)` → `useState(true)`

### 0.5 — Tabular Nums

After adding `.nums` utility to `globals.css`, apply class to:
- `PredictionSummary.tsx`: probability display, implied odds, edge value
- `GameLogTable.tsx`: all stat `<td>` cells (targets, yards, TDs, Model %)
- `PlayerWeekToggle.tsx`: week number span
- `ValuePlayerCard.tsx`: Model % and Edge values in both layout branches

Use `<span className="nums">` wrapper where `className` prop not available on MUI components.

### 0.6 — PlayerSelector Mobile Fix

`PlayerSelector.tsx`:
- Remove `autoFocus` (kills mobile UX — keyboard pops on load)
- Add `max-w-[calc(100vw-2rem)]` to the dropdown container to prevent overflow on small screens

### 0.7 — Hero Gradient + Metadata (`PlayerModel.tsx` + `layout.tsx`)

In `PlayerModel.tsx`, replace:
```jsx
// Before
<div style={{ backgroundImage: 'url(/gabe-davis-background.jpg)', ... }}>
  <div className="absolute inset-0 bg-gradient-to-b from-black/60 via-black/75 to-[#0a0a0a]" />
</div>

// After
<div className="absolute top-0 left-0 w-full h-96 bg-gradient-to-b from-purple-900/20 via-[#0a0a0a]/80 to-[#0a0a0a]" />
```

Same replacement for `WeeklyValue.tsx` hero: `background: linear-gradient(135deg, #1a0533 0%, #0d1117 40%, #0a0a0a 100%)`. Remove the overlay gradient that was blending a photo.

Also change `PlayerModel.tsx:87` default player lookup: `uniquePlayers.find(p => p.name === 'Gabe Davis')` → `uniquePlayers[0]`

In `layout.tsx` update metadata:
- `title`: `"Big Game Gabe — NFL TD Model"` (or keep `"BGGTDM - Big Game Gabe TD Model"`)
- `description`: keep existing or update to `"NFL anytime touchdown probability model for WR and TE"`
- `icons.icon`: replace `/gabe-davis-headshot.png` with a non-likeness icon (logo, football, etc.)
- Replace OG/Twitter `images` pointing to `gabe-davis-background.jpg` with a non-likeness brand image

---

## Phase 1 — MUI Removal + Tailwind Migration

**Prerequisite**: Phase 0 deployed. shadcn/ui initialized.

### 1.1 — shadcn/ui Setup

```bash
cd frontend
npx shadcn@latest init
# Select: TypeScript yes, app router yes, components dir: components/ui, dark theme, CSS variables yes
```

After init, shadcn will overwrite the `globals.css` `:root` block — re-apply the Signal Route token block from Phase 0.1.

Install components needed across all migrations:
```bash
npx shadcn@latest add button tabs badge card select alert checkbox input progress separator skeleton
```

Confirm `lib/utils.ts` exports `cn` helper (clsx + tailwind-merge). If not, add:
```ts
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)); }
```

**CSS specificity warning**: Never mix `sx` + Tailwind `className` on the same element during migration. MUI Emotion can win on specificity. Complete each component fully before moving to the next.

### 1.2 — Create Shared Primitives (before any component rewrites)

**`components/ui/SurfaceCard.tsx`**
Props: `{ children: ReactNode; className?: string }`
Classes: `bg-sr-surface/40 backdrop-blur-sm border border-sr-border rounded-card`
Replaces the identical `rgba(17,24,39,0.4)` + border + borderRadius pattern in 5+ MUI Card components.

**`components/ui/ConsensusBadge.tsx`**
Displays "Consensus" as read-only pill. Replaces DK/FanDuel toggle and logo images.
Classes: `px-2 py-0.5 rounded-badge bg-sr-surface border border-sr-border text-xs text-sr-text-muted`

**`components/NavBar.tsx`**
Replaces MUI AppBar + Tabs. Props: `{ activeTab, onTabChange, currentWeek }`.
- Height: 64px, sticky, `bg-sr-bg/80 backdrop-blur-md border-b border-sr-border`
- Wordmark: `Big Game Gabe` or `BGGTDM` text-only, no player photo/avatar
- Tabs: "This Week" | "Player Lookup" | "Track Record"
- Active tab style: `text-white border-b-2 border-sr-primary`
- Inactive tab: `text-sr-text-muted hover:text-white transition-colors`

**`components/WeekBadge.tsx`**
Props: `{ week: number | null }`. Renders null when week is null.
(Same pill as Phase 0.2 but as a proper component.)

### 1.3 — Rewrite `page.tsx`

Remove all MUI imports. Single fetch for current week (consolidate the 3 independent fetches).

```tsx
type Tab = 'weekly' | 'player' | 'track';
const [activeTab, setActiveTab] = useState<Tab>('weekly'); // default changed to weekly
```

Structure:
```tsx
<div className="min-h-screen bg-sr-bg">
  <NavBar activeTab={activeTab} onTabChange={setActiveTab} currentWeek={currentWeek} />
  <main>
    {activeTab === 'weekly' && <WeeklyValue currentWeek={currentWeek} currentYear={currentYear} onPlayerClick={handlePlayerClick} />}
    {activeTab === 'player' && <PlayerModel initialPlayerId={selectedPlayerId} currentWeek={currentWeek} currentYear={currentYear} />}
    {activeTab === 'track' && <div className="text-center text-sr-text-muted py-12">Track Record — coming soon</div>}
  </main>
</div>
```

Endpoint in the single fetch: `/api/status/week` (see Phase 1.5 blocker). Use fallback per Phase 0.3 until available.

### 1.4 — Rewrite `WeeklyValue.tsx`

Most complex migration. Read the full file before starting.

**Sportsbook removal** (non-negotiable before rewrite ships):
- Remove `selectedSportsbook` state and `ToggleButtonGroup`
- Update odds fetch to read `oddsData.sportsbook_odds?.consensus` (confirm key with backend first)
- Remove `dk-logo-small.png` and `fd-logo-small.svg` references
- Remove `sportsbook` field from `ValuePick` interface
- Replace with `<ConsensusBadge>`

**Remove independent current week fetch** — receive as props from `page.tsx`.

**MUI → Tailwind mapping**:
| MUI | Replacement |
|---|---|
| `<Box sx={{ position: 'relative' }}>` | `<div className="relative">` |
| `<Container maxWidth="xl">` | `<div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">` |
| `<Card sx={{ bgcolor, backdropFilter, border }}>` | `<SurfaceCard>` |
| `<CircularProgress>` | `<div className="animate-spin rounded-full h-8 w-8 border-2 border-sr-primary border-t-transparent">` |
| `<Alert severity="error">` | `<div className="bg-sr-danger/10 border border-sr-danger/30 rounded-card p-4 text-sr-danger">` |
| `<Stack spacing={2}>` | `<div className="flex flex-col gap-2">` |
| `<Checkbox>` + `<FormControlLabel>` | shadcn `<Checkbox>` |
| MUI icons (TrendingUp, TrendingDown, Warning) | lucide-react: TrendingUp, TrendingDown, AlertTriangle |
| Hero `backgroundImage: url(gabe-davis-background.jpg)` | `bg-gradient-to-b from-purple-900/20 via-sr-bg/80 to-sr-bg` |

### 1.5 — Rewrite `PlayerHeader.tsx`

Remove `useTheme`, `useMediaQuery`, all MUI imports.

Map MUI responsive to Tailwind:
- `flexDirection: { xs: 'column', md: 'row' }` → `flex-col md:flex-row`
- `textAlign: { xs: 'center', md: 'left' }` → `text-center md:text-left`
- `gridTemplateColumns: { xs: '2fr', md: '4fr' }` → `grid-cols-2 md:grid-cols-4`

Replace `<Avatar>`:
```tsx
<img src={player.imageUrl} alt={player.name}
  className="w-20 h-20 md:w-24 md:h-24 rounded-full object-cover border-2 border-sr-primary flex-shrink-0" />
```

Replace `<Card>` with `<SurfaceCard className="p-4 md:p-6">`.

### 1.6 — Rewrite `ValuePlayerCard.tsx`

Same `useTheme`/`useMediaQuery` pattern as PlayerHeader — same replacement approach. The entire `{isMobile ? (...) : (...)}` dual-layout branch becomes one responsive layout.

Replace MUI icons with lucide-react: `TrendingUp`, `TrendingDown`, `Minus`.
Replace `<Chip>` with Tailwind pill span.

All numeric values get `nums` class.

### 1.7 — Edit `PlayerModel.tsx` (2 changes only, no full rewrite)

1. Remove independent current week `useEffect` — receive `currentWeek`/`currentYear` as props
2. `PlayerModel.tsx:87` — remove `find(p => p.name === 'Gabe Davis')`, replace with `uniquePlayers[0]`

### 1.8 — Shared Types

Create `frontend/types/player.ts` for the `Player` interface duplicated between `PlayerModel.tsx` and `PlayerHeader.tsx`.

### 1.9 — `PredictionSummary.tsx` — Sportsbook Cleanup

Replace DK/FanDuel logo image block (lines 111–116) with:
```tsx
{prediction.sportsbookOdds !== 'N/A' && (
  <span className="text-xs text-sr-text-muted ml-1">Consensus</span>
)}
```
Remove `sportsbook?: 'draftkings' | 'fanduel'` from `Prediction` interface.

### 1.10 — Admin Subtree Migration

Read before migrating — full component set not yet audited:
- `system-status/OverviewTab.tsx` — Heavy MUI (Card, Chip, LinearProgress, icons)
- `system-status/ActionsTab.tsx` — Heavy MUI (TextField, Button, Select, Alert, etc.)
- `system-status/BatchHistoryTab.tsx` — needs read
- `system-status/LogViewerModal.tsx` — needs read

Pattern for all: `<Card>` → `<SurfaceCard>`, `<Chip>` → pill span, `<LinearProgress>` → shadcn `<Progress>`, MUI icons → lucide-react, `<Button>` → shadcn `<Button>`, `<TextField>` → shadcn `<Input>`, `<Select>` → shadcn `<Select>`, `<Divider>` → `<hr className="border-sr-border">`.

Create `/admin` route:
```
app/admin/
  layout.tsx    — minimal shell (no public NavBar), heading "System Admin"
  page.tsx      — renders <SystemStatus />
```

**Important**: uninstall MUI and create `/admin` route in the same commit — `SystemStatus` will not render if MUI is removed first.

### 1.11 — `ProbabilityChart.tsx` Fixes

No MUI, but needs corrections from brand review:
- Fix Y-axis domain: `domain={[0, 60]}` — never auto-scale, the range is misleading when auto
- Reduce grid line opacity: `stroke="rgba(255,255,255,0.06)"`
- Tooltip style: `contentStyle={{ background: 'rgba(15,15,20,0.95)', border: '1px solid rgba(147,51,234,0.4)' }}`

### 1.12 — `WeeklyValue.tsx` Mobile Layout

During the Phase 1 rewrite, apply mobile-specific layout decisions:
- **Remove hero section entirely on mobile** (hide with `hidden md:block`) — player cards should be above the fold on small screens
- **Sticky filter toolbar** on mobile — position filters at top when scrolling
- **Card layout order**: `[rank] [avatar] [name/team] [edge pill]` on top row, `[model%] [model odds] [consensus odds]` on second row
- Replace `<CircularProgress>` loading state with **skeleton cards** (4–5 `<ValuePlayerCard>`-shaped skeletons using `bg-sr-surface animate-pulse` blocks) — matches layout of real content so there's no layout shift on load

### 1.14 — Uninstall MUI

After all components pass build and `/admin` route is ready:
```bash
cd frontend
npm uninstall @mui/material @mui/icons-material @emotion/react @emotion/styled
npm run build
grep -r "@mui" components/ app/ --include="*.tsx" --include="*.ts"
# Must return zero matches
```

---

## Phase 1.5 — Backend Dependency (tracks separately)

**New endpoint required**: `GET /api/status/week`

Response:
```json
{ "season": 2025, "week": 14 }
```

Lives in `backend_new/app/api/public.py`. No auth required. Thin wrapper over the same data as `data-readiness/current.current_week`.

When available, update all three fetch calls in `page.tsx` (the consolidated single fetch):
```tsx
const response = await fetch(`${API_URL}/api/status/week`);
const { season, week } = await response.json();
```

Also confirm the `/api/odds/` response shape under backend_new before rewriting `WeeklyValue` — confirm what key holds consensus odds.

---

## Phase 2 — Track Record Surface + Paywall Prep

**Prerequisites**: Phase 1 deployed stable. Backend `/api/track-record` endpoint available.

### 2.1 — New Backend Endpoint

`GET /api/track-record?season=2025`

```typescript
{
  season: number;
  weeks: Array<{
    week: number;
    predictions_count: number;
    hits: number;
    misses: number;
    calibration_error: number;
    high_confidence_hits: number;
    high_confidence_total: number;
  }>;
  season_summary: {
    total_predictions: number;
    overall_hit_rate: number;
    high_confidence_hit_rate: number;
    mean_calibration_error: number;
  };
}
```

Computable from `predictions` + `player_game_logs` tables in backend_new.

### 2.2 — `components/ui/MetricCard.tsx`

Props: `{ label: string; value: string; sublabel?: string }`
Classes: `SurfaceCard p-6 text-center`. Value: `text-3xl font-bold text-white nums`.

### 2.3 — `components/TrackRecord.tsx`

Layout:
```
TrackRecord
  ├── Section 1: 4 MetricCards (grid-cols-2 md:grid-cols-4 gap-4)
  │     — Season Hit Rate, High Confidence Hit Rate, Weeks Tracked, Mean Calibration Error
  ├── Section 2: Week-by-Week BarChart (Recharts)
  │     — x = week, y = hit rate %; bars colored success/danger vs 33% baseline
  │     — Reference line at 33% "NFL avg anytime TD rate" (dashed, sr-text-muted)
  ├── Section 3: Calibration Curve
  │     — Scatter/line chart: x = predicted probability bucket, y = actual hit rate
  │     — Shows whether model is well-calibrated (diagonal = perfect)
  │     — If backtested data: must include visible "Backtested" label — no implied live performance
  ├── Section 4: Accuracy by Confidence Band table
  │     — 4 rows: <20%, 20-30%, 30-40%, >=40%
  │     — Columns: Band | Predictions | Hit Rate | vs. Baseline (+/-%)
  │     — "vs. Baseline" uses sr-success (green) or sr-danger (red) text
  ├── Section 5: PaywallGate (wraps current-week predictions preview)
  └── GamblingDisclaimer
```

**Disclosure requirement**: Any historical ROI figures must include a clearly visible "Backtested results" label inline with the stat — not in footnote only. Do not present backtested ROI as live performance.

Chart bar coloring:
```tsx
const chartData = weeks.map(w => ({
  week: w.week,
  hitRate: w.predictions_count > 0 ? Math.round((w.hits / w.predictions_count) * 100) : 0,
  aboveBaseline: (w.hits / w.predictions_count) >= 0.33,
}));
// Use <Cell> per bar: fill={d.aboveBaseline ? '#10b981cc' : '#f43f5ecc'}
```

Empty state when no data: `<SurfaceCard className="p-12 text-center"><p className="text-sr-text-muted text-sm">Track Record data will appear after the first full season of predictions.</p></SurfaceCard>`

### 2.4 — `components/PaywallGate.tsx`

```tsx
interface PaywallGateProps { feature: string; children: React.ReactNode; }

export function PaywallGate({ feature, children }: PaywallGateProps) {
  const isSubscribed = false; // TODO: replace with auth hook when JWT is wired (Phase 6)
  if (isSubscribed) return <>{children}</>;

  return (
    <div className="relative overflow-hidden rounded-card mt-8">
      {/* Real data, CSS blurred */}
      <div className="pointer-events-none select-none" style={{ filter: 'blur(6px)' }} aria-hidden="true">
        {children}
      </div>
      {/* Gate overlay */}
      <div className="absolute inset-0 flex flex-col items-center justify-end pb-12"
        style={{ background: 'linear-gradient(to bottom, transparent 0%, rgba(10,10,10,0.95) 35%)' }}>
        <div className="text-center px-6 max-w-md">
          <p className="text-sr-text-muted text-sm mb-2">Full breakdown</p>
          <h3 className="text-white text-xl font-semibold mb-3">Big Game Gabe Pro</h3>
          <p className="text-sr-text-muted text-sm mb-6">
            Per-player prediction history, calibration by position, and weekly edge reports
          </p>
          <button className="bg-sr-primary text-white px-8 py-3 rounded-card font-semibold hover:bg-purple-600 transition-colors">
            Get Access
          </button>
        </div>
      </div>
    </div>
  );
}
```

The blurred teaser must use real data (current week player predictions) — not placeholder text. Blur makes content unreadable but structure visible, which is correct conversion UX.

**Paywall UX rules** (from brand review):
- Gate at the data layer (blur odds/edge), not at component visibility — player names and ranks are always free
- The "This Week" tab header should show: `"3 positive EV plays this week — subscribe to see them"` when the user is not subscribed
- **No "No thanks" dismiss button** on the paywall overlay — only an X close to collapse it. No opt-out path that implies the gate is optional.
- `filter: blur(6px)` on the data, not `opacity` — opacity collapse is too readable

### 2.5 — Wire Track Record Tab

In `page.tsx`, replace the "coming soon" placeholder from Phase 1.3:
```tsx
{activeTab === 'track' && <TrackRecord isPremium={false} />}
```

---

## Execution Checklist

### Phase 0 (ship fast, zero risk)
- [ ] `globals.css` — replace `:root` block with Signal Route tokens, add `.nums` utility
- [ ] `tailwind.config.ts` — extend with `sr-` color tokens
- [ ] `app/layout.tsx` — update title, description, remove Gabe Davis OG images and favicon
- [ ] `page.tsx` — remove Avatar, update wordmark, rename tabs, remove System Status tab, pill badge
- [ ] `page.tsx` / `PlayerModel.tsx` / `WeeklyValue.tsx` — add admin API fallback
- [ ] `GameLogTable.tsx` — `useState(true)`
- [ ] `PredictionSummary.tsx` / `GameLogTable.tsx` / `PlayerWeekToggle.tsx` / `ValuePlayerCard.tsx` — add `.nums` class
- [ ] `PlayerModel.tsx` — replace hero `backgroundImage` with gradient
- [ ] `WeeklyValue.tsx` — replace hero `backgroundImage` with gradient (comment flag for full rewrite in Phase 1)
- [ ] `PlayerModel.tsx:87` — remove Gabe Davis name lookup
- [ ] `PlayerSelector.tsx` — remove `autoFocus`, add `max-w-[calc(100vw-2rem)]`

### Phase 1 (MUI removal)
- [ ] Verify Tailwind version (`npx tailwindcss --version`)
- [ ] `npx shadcn@latest init` + install components
- [ ] Re-apply Signal Route token block after shadcn overwrites globals.css
- [ ] Confirm `lib/utils.ts` exports `cn`
- [ ] Create `components/ui/SurfaceCard.tsx`
- [ ] Create `components/ui/ConsensusBadge.tsx`
- [ ] Create `components/NavBar.tsx`
- [ ] Create `components/WeekBadge.tsx`
- [ ] Rewrite `page.tsx` (single week fetch, NavBar, default tab `'weekly'`)
- [ ] Rewrite `WeeklyValue.tsx` (sportsbook removal, props week, MUI → Tailwind)
- [ ] Rewrite `PlayerHeader.tsx`
- [ ] Rewrite `ValuePlayerCard.tsx`
- [ ] Edit `PlayerModel.tsx` (remove fetch, remove Gabe Davis fallback)
- [ ] `PredictionSummary.tsx` — remove sportsbook logo, update interface
- [ ] Create `frontend/types/player.ts` shared interface
- [ ] `ProbabilityChart.tsx` — fix Y-axis domain, grid opacity, tooltip style
- [ ] `WeeklyValue.tsx` — mobile hero hidden, sticky filter toolbar, skeleton loading cards
- [ ] Read + migrate `system-status/OverviewTab.tsx`
- [ ] Read + migrate `system-status/ActionsTab.tsx`
- [ ] Read + migrate `system-status/BatchHistoryTab.tsx`
- [ ] Read + migrate `system-status/LogViewerModal.tsx`
- [ ] Create `app/admin/layout.tsx` + `app/admin/page.tsx`
- [ ] `npm uninstall @mui/material @mui/icons-material @emotion/react @emotion/styled`
- [ ] `npm run build` — verify clean
- [ ] Audit `public/` — remove `gabe-davis-background.jpg` and `gabe-davis-headshot.png`

### Phase 1.5 (backend dependency)
- [ ] Backend: add `GET /api/status/week` to `backend_new/app/api/public.py`
- [ ] Backend: confirm `/api/odds/` response key for consensus odds
- [ ] Frontend: update week fetch in `page.tsx` to `/api/status/week`
- [ ] Frontend: update odds key in `WeeklyValue.tsx`

### Phase 2 (Track Record + paywall)
- [ ] Backend: add `GET /api/track-record` endpoint
- [ ] Create `components/ui/MetricCard.tsx`
- [ ] Create `components/TrackRecord.tsx` (includes calibration curve + backtested disclosure)
- [ ] Create `components/PaywallGate.tsx` (blur gate, no "No thanks", header EV count CTA)
- [ ] Wire Track Record tab in `page.tsx`
- [ ] Add paywall EV count to "This Week" tab header in `WeeklyValue.tsx`

---

## File Change Summary

```
Phase 0:
  app/globals.css                      EDIT
  tailwind.config.ts                   REWRITE
  app/layout.tsx                       EDIT
  app/page.tsx                         EDIT
  components/GameLogTable.tsx          EDIT (1 line)
  components/PlayerModel.tsx           EDIT (hero gradient, Gabe Davis fallback)
  components/PredictionSummary.tsx     EDIT (nums class)
  components/PlayerWeekToggle.tsx      EDIT (nums class)
  components/ValuePlayerCard.tsx       EDIT (nums class)
  components/WeeklyValue.tsx           COMMENT ONLY (admin API flag)

Phase 1:
  app/page.tsx                         REWRITE
  app/admin/layout.tsx                 CREATE
  app/admin/page.tsx                   CREATE
  components/NavBar.tsx                CREATE
  components/WeekBadge.tsx             CREATE
  components/ui/SurfaceCard.tsx        CREATE
  components/ui/ConsensusBadge.tsx     CREATE
  components/WeeklyValue.tsx           REWRITE
  components/PlayerModel.tsx           EDIT
  components/PlayerHeader.tsx          REWRITE
  components/ValuePlayerCard.tsx       REWRITE
  components/PredictionSummary.tsx     EDIT
  components/SystemStatus.tsx          EDIT + MOVE
  components/system-status/*.tsx       REWRITE (4 files)
  types/player.ts                      CREATE
  lib/utils.ts                         EDIT (cn helper)
  package.json                         EDIT (MUI removal)
  public/gabe-davis-*.{png,jpg}        DELETE

Phase 2:
  components/TrackRecord.tsx           CREATE
  components/PaywallGate.tsx           CREATE
  components/ui/MetricCard.tsx         CREATE
  app/page.tsx                         EDIT (wire Track Record tab)

  components/PlayerSelector.tsx        EDIT (Phase 0 — autoFocus, max-w)
  components/ProbabilityChart.tsx      EDIT (Phase 1 — chart fixes)

Unchanged throughout:
  components/GamblingDisclaimer.tsx
```
