# Phase 3: UI Redesign - Next Steps

**Status**: Ready to Begin
**Estimated Time**: 6-8 hours
**Priority**: High (Backend is complete, now need frontend visibility)

---

## What We Just Completed (Phase 1 & 2) ✅

### Phase 1: Critical Fixes
- ✅ Fixed destructive odds deletion → atomic upsert
- ✅ Added Tuesday week boundary logic
- ✅ Added fallback warning logging
- ✅ Implemented rate limiting (5 req/min per IP)

### Phase 2: Observability Backend
- ✅ Created `batch_execution_steps` table
- ✅ Added `BatchExecutionStep` model with relationships
- ✅ Enhanced `BatchTracker` with step tracking methods
- ✅ Integrated step tracking into `update_weekly.py`
- ✅ Integrated step tracking into `generate_predictions.py`
- ✅ Created API endpoints:
  - `GET /api/admin/batch-runs/{id}` - Get batch run details
  - `GET /api/admin/batch-runs/{id}/steps` - Get step-level execution data

**Backend Status**: 🎉 Fully instrumented with enterprise-level observability!

---

## Phase 3: Frontend UI Redesign

### Goal
Build a comprehensive System Status page with tabs, real-time monitoring, and batch history.

### Current Frontend Location
`frontend/app/system-status/page.tsx` - Needs complete redesign

### New Component Structure

```
frontend/
├── app/system-status/page.tsx          (Main container with tabs)
├── components/system-status/
    ├── OverviewTab.tsx                 (Health dashboard)
    ├── ActionsTab.tsx                  (Quick actions + batch triggers)
    ├── BatchHistoryTab.tsx             (Historical runs with step details)
    ├── LiveBatchViewer.tsx             (Real-time progress)
    └── BatchStepTimeline.tsx           (Visual step progression)
```

---

## Immediate Next Steps

### Step 1: Create Tab-Based Layout (30 mins)

**File**: `frontend/app/system-status/page.tsx`

Add Material-UI tabs:
- 📊 Overview (health, current week, data readiness)
- ⚡ Actions (trigger batches, quick actions)
- 📜 Batch History (last 50 runs with step drill-down)
- 🔧 Scripts (admin scripts: roster refresh, backfill odds)

### Step 2: Build OverviewTab Component (1.5 hours)

**File**: `frontend/components/system-status/OverviewTab.tsx`

Display:
- Current NFL week (2025 Week 18)
- Health score (healthy/partial/incomplete)
- Latest batch status with live indicator
- Data completeness bars:
  - Schedule: 16/16 games ✅
  - Predictions: 245/320 players 🟡
  - Odds: DraftKings ✅, FanDuel ✅

API Calls:
- `GET /api/admin/health/summary`
- `GET /api/admin/batch-runs/latest`

### Step 3: Build ActionsTab Component (2 hours)

**File**: `frontend/components/system-status/ActionsTab.tsx`

Quick Actions (1-click):
```typescript
[Run Full Batch Update] → triggers update_weekly.py + generate_predictions.py
[Refresh Odds Only] → update_weekly.py --mode odds_only
[Generate Predictions] → generate_predictions.py
```

Advanced Actions (with parameters):
```typescript
Week: [dropdown] Year: [dropdown]
[Update Schedule Only]
[Fetch Game Logs Only]
[Force Regenerate Predictions] ⚠️
```

API Calls:
- `POST /api/admin/actions/run-batch-update` (with body: {password, week, year, mode})

### Step 4: Build BatchHistoryTab Component (2.5 hours)

**File**: `frontend/components/system-status/BatchHistoryTab.tsx`

Features:
- Table showing last 50 batch runs
- Filters: Status (all/success/failed), Type (all/weekly_update/predictions)
- Expandable rows showing step-by-step breakdown
- Click step to view output logs

Columns:
- ID | Type | Week | Status | Started | Duration | Steps | Actions

Expandable Detail:
```
Step 1: schedule     [✅ success]  8s   16 records
Step 2: game_logs    [✅ success]  22s  156 records
Step 3: odds         [✅ success]  15s  320 records
[View Logs] button → shows last 100 lines of output
```

API Calls:
- `GET /api/admin/batch-runs/history?limit=50`
- `GET /api/admin/batch-runs/{id}?include_steps=true`
- `GET /api/admin/batch-runs/{id}/steps`

### Step 5: Build LiveBatchViewer Component (1.5 hours)

**File**: `frontend/components/system-status/LiveBatchViewer.tsx`

Shows currently running batch (if any):
```
Batch #123: weekly_update (RUNNING)
⏱️ Started: 2 minutes ago

Step 1: schedule      ✅ Complete (8s, 16 records)
Step 2: game_logs     🔄 Running... (14s elapsed)
Step 3: odds          ⏸️ Pending
```

Implementation:
- Poll `GET /api/admin/batch-runs/latest` every 3 seconds
- If status='running', fetch step details
- Display progress bar based on completed steps

### Step 6: Add Step Output Log Viewer (1 hour)

**File**: `frontend/components/system-status/LogViewerModal.tsx`

Modal dialog showing:
```
Step: game_logs (batch_run_id: 123)
Status: success
Duration: 22s
Records Processed: 156

Output Log:
[10:42:15] Starting game logs sync...
[10:42:18] Fetching box scores for Week 17...
[10:42:25] Found 156 new game logs
[10:42:37] Game logs sync complete
```

API Call:
- `GET /api/admin/batch-runs/{id}/steps` → extract `output_log` field

---

## Implementation Order (Recommended)

1. **Start with Actions Tab** (easiest, immediate value)
   - Add trigger buttons for existing endpoints
   - Test batch execution via UI

2. **Build Overview Tab** (health dashboard)
   - Show current status
   - Display latest batch run

3. **Implement Batch History Tab** (most complex)
   - Table with expandable rows
   - Step detail drill-down

4. **Add Live Batch Viewer** (polish)
   - Real-time progress indicator
   - Auto-refresh when batch running

---

## Key API Endpoints (Already Built)

```typescript
// Health & Status
GET /api/admin/health/summary
GET /api/admin/data-readiness/current
GET /api/admin/batch-runs/latest

// Batch Execution
POST /api/admin/actions/run-batch-update
POST /api/admin/actions/refresh-rosters
POST /api/admin/actions/backfill-odds

// Batch History
GET /api/admin/batch-runs/history?limit=50&batch_type=weekly_update
GET /api/admin/batch-runs/{id}?include_steps=true
GET /api/admin/batch-runs/{id}/steps
```

---

## Testing Checklist

After building UI:
- [ ] Trigger batch from UI → verify step tracking works
- [ ] Check batch history table → verify expandable rows show steps
- [ ] View output logs → verify last 100 lines are saved
- [ ] Test filters → verify status/type filtering works
- [ ] Test live viewer → verify polls and updates in real-time
- [ ] Test error handling → trigger failed batch, verify error message shows

---

## Design Guidelines

**Colors** (match existing app):
- Background: `bg-gray-900`
- Cards: `bg-gray-800`
- Text: `text-white`, `text-gray-300`
- Success: `text-green-400`
- Error: `text-red-400`
- Warning: `text-yellow-400`
- Primary: `text-purple-600` (buttons)

**Components to Use**:
- Material-UI Tabs
- Material-UI Table (for batch history)
- Material-UI Accordion (for expandable rows)
- Material-UI LinearProgress (for progress bars)
- Material-UI Chip (for status badges)

---

## Questions to Answer Before Starting

1. **Do you want to build all 4 tabs, or prioritize specific ones?**
   - Suggested: Start with Actions + Overview, then add History later

2. **Do you want real-time SSE streaming, or is 3-second polling okay?**
   - Polling is simpler and already works
   - SSE requires additional backend endpoint

3. **Should we add authentication to admin actions?**
   - Currently uses password in request body
   - Could add API key or session token

---

## Ready to Begin?

The backend is **fully ready**. All endpoints are built and tested. We just need to wire up the frontend to display the data and trigger batch executions.

Let me know which tab you'd like to start with, or if you want me to build them all in sequence!
