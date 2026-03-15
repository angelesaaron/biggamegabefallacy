# Admin Phase 2 — UI Redesign: Pipeline Actions + Week Override

## Phase 2 Backend Verification: Fully Correct ✅

Do not touch any of these — they are complete and correct:
- `0009_system_config.py` migration (`revision="0009"`, `down_revision="0008"`) ✅
- `app/models/system_config.py` ✅
- `app/services/week_resolver.py` ✅
- All pipeline endpoints in `admin_users.py` — roster, schedule, gamelogs, odds, features, predictions ✅
- `SyncResponse` + `_to_response()` copied into `admin_users.py` ✅
- Week override GET/POST/DELETE endpoints ✅
- Panel type updated, all four panels rendering in `AdminPage` ✅

## What's Wrong With the Current Frontend

The Pipeline and Week Override panels (`PipelinePanel` and `WeekOverridePanel` in `frontend/app/admin/page.tsx`) are functional but the UI is bad:

- Big filled `bg-sr-primary` purple buttons feel childish and out of place for an ops tool
- No status tracking — you trigger an action and the result card appears below but there's no sense of history, run state, or sequencing
- Layout is a flat vertical list of form rows — no information hierarchy
- Week Override is two disconnected boxes with no sense of state
- No "pipeline dashboard" feel — it just looks like a simple form page

**Do not redesign AccountsPanel or HealthPanel — those are fine.**

---

## What to Build

Completely rewrite `PipelinePanel` and `WeekOverridePanel` in `frontend/app/admin/page.tsx`. The backend API contracts are fixed — only the frontend components change.

### Design Direction

This is an **internal ops dashboard** used by a single admin. The aesthetic should feel like a professional devops/monitoring tool — think Vercel deployment dashboard, Railway, or Linear's command palette. Not a marketing page. Not a form wizard.

Key qualities:
- **Dense but readable** — pack information efficiently, this isn't a consumer UI
- **State-aware** — every pipeline action has a visible run history/status within the session
- **Monospace for data** — counts, timestamps, status codes are mono
- **Minimal chrome** — borders and backgrounds should recede; data and status should pop
- **Muted action triggers** — buttons should be small, ghost/outline style, not filled purple. Actions are confirmations, not calls-to-action.
- **Status is the hero** — after running an action, the result should feel like a log entry, not a form response

The design system is dark (`#0a0a0a` bg, `#1f2937` borders, `#9ca3af` muted text, `#a855f7` primary/accent only for meaningful state). Use the existing Tailwind classes and CSS variables. Do not introduce new colors or fonts.

---

## PipelinePanel Redesign

### Layout

Two-column layout:
- **Left column (~280px)**: Action controls — the "trigger" side
- **Right column (flex-1)**: Run log — session history of results, newest at top

The two columns are separated by a vertical divider (`border-r border-sr-border`).

### Left Column — Action Controls

At the top: a shared season/week selector that applies to all actions that need it. Small, compact, inline:

```
Season [2025] Week [14]   ← compact number inputs, no labels needed once context is clear
```

Below that: two sections separated by a thin divider.

**Section: Compute (DB Only)**
Label: `COMPUTE` in `text-sr-text-dim text-[10px] tracking-widest uppercase` — treat these like terminal section headers.

Actions listed as rows:
```
[▶ run]  Compute Features       DB only
[▶ run]  Run Predictions        DB only
```

Each row:
- Small ghost/outline trigger button on the left: `px-2 py-1 text-xs border border-sr-border text-sr-text-muted rounded hover:border-sr-primary hover:text-white transition-colors` — no fill, no purple background
- Action name in `text-sm text-white`
- Subtle badge on right: `text-[10px] text-sr-text-dim` saying `DB only` or `ext. API`
- While loading: button shows a tiny inline spinner (3-4px dot animation or just `...`), stays disabled, text dims

**Section: Sync (External API)**
Label: `SYNC`

```
[▶ run]  Roster                 ext. API
[▶ run]  Schedule               ext. API
[▶ run]  Game Logs              ext. API
[▶ run]  Odds                   ext. API
```

Roster takes no params (uses shared season/week is ignored for it). Schedule uses season only. Gamelogs and Odds use both.

No section needs a warning banner — the `ext. API` badge is sufficient.

### Right Column — Run Log

Header row: `RUN LOG` label + a small `Clear` ghost button to clear the session log.

Each completed run appends a log entry at the top (newest first). Think of it like a terminal output panel.

**Log entry structure:**
```
── Compute Features  S2025 W14  ──────────────────── 2:34:07 PM
   status: completed
   written 0  updated 47  skipped 0  failed 0
   [events list if non-empty, as small mono lines prefixed with ·]
```

Styling:
- Top rule: `border-t border-sr-border pt-2 mt-2` for visual separation between entries
- Action name: `text-sm text-white font-medium`
- Season/week: `text-xs text-sr-text-dim font-mono`
- Timestamp: `text-xs text-sr-text-dim font-mono` right-aligned
- Status: color-coded `text-xs font-mono` — green for `completed`, yellow for `partial`, red for `failed`
- Counts: `text-xs font-mono text-sr-text-muted` — all on one line: `written 0  updated 47  skipped 0  failed 0`
- Events: `text-xs font-mono text-sr-text-dim` each prefixed with `·`

**In-progress state:** While an action is running, show a "pending" entry at the top with an animated pulse or blinking cursor — `text-sr-text-dim text-xs font-mono animate-pulse`.

**Empty state:** When no actions have been run yet, show `No runs this session.` in `text-sr-text-dim text-xs font-mono` centered in the panel.

### State management

```typescript
interface RunEntry {
  id: string;           // crypto.randomUUID() or Date.now()
  action: string;       // e.g. "Compute Features"
  season?: number;
  week?: number;
  status: 'running' | 'completed' | 'partial' | 'failed' | 'error';
  result?: ActionResult;
  errorMessage?: string;
  startedAt: Date;
  completedAt?: Date;
}

const [runs, setRuns] = useState<RunEntry[]>([]);
const [season, setSeason] = useState(2025);
const [week, setWeek] = useState(1);
const [runningAction, setRunningAction] = useState<string | null>(null);
```

On trigger: append a `status: 'running'` entry, set `runningAction`. On complete: update that entry with result. Only one action at a time — all buttons disabled while `runningAction !== null`.

---

## WeekOverridePanel Redesign

This panel is small and focused. Think of it as a system config terminal entry.

### Layout

Single column, compact. No separate card boxes.

**Current state display** (top, always visible):

```
CURRENT WEEK
──────────────────────────────────────────
Auto-detected (no override active)
                                    [clear]   ← only visible when override is active
```

Or when active:
```
CURRENT WEEK
──────────────────────────────────────────
Override active  ·  S2025 W14
                                    [clear]
```

Styling:
- `CURRENT WEEK` label: `text-[10px] tracking-widest uppercase text-sr-text-dim`
- Divider: `border-t border-sr-border my-2`
- State text: `text-sm font-mono text-white` for the value, `text-sm font-mono text-sr-text-muted` for "Auto-detected"
- `Override active` dot and S/W: `text-xs font-mono` — the `·` separator is `text-sr-text-dim`
- `[clear]` button: `text-xs text-sr-text-dim hover:text-red-400 underline transition-colors` — no border, no fill, just a text link style

**Set override** (below the divider):

```
SET OVERRIDE
──────────────────────────────────────────
Season [____]  Week [__]   [apply]
```

- `SET OVERRIDE` same label style as above
- Inputs: `bg-transparent border-b border-sr-border px-1 py-0.5 text-sm font-mono text-white w-16 focus:outline-none focus:border-sr-primary` — bottom-border-only style, no box, feels like a terminal input
- `[apply]` button: same ghost outline style as pipeline action buttons — `px-3 py-1 text-xs border border-sr-border text-sr-text-muted rounded hover:border-sr-primary hover:text-white transition-colors`

**Info note** below everything:
```
· Overrides the week the app and pipeline consider "current".
```
`text-[10px] text-sr-text-dim font-mono mt-4`

---

## Implementation Notes

- All existing logic (fetch calls, state management, token auth) stays the same — only JSX and styling changes
- The `ActionResult` and `WeekOverrideData` types are already defined in the file — keep them
- `getToken()` from `useAuth()` — same as before
- The run log is session-only (in component state) — no persistence needed
- Only one action runs at a time — disable all trigger buttons while `runningAction !== null`
- Inline spinner while running: a simple `inline-block w-2 h-2 rounded-full bg-current animate-pulse` next to the button label is sufficient — don't reach for a library
- `crypto.randomUUID()` for run entry IDs (available in modern browsers)
- No new npm packages
- TypeScript strict — no `any`
- Do not touch `AccountsPanel`, `HealthPanel`, the sidebar, or `AdminPage` layout
