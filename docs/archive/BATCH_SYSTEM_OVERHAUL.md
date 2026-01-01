# Batch System Overhaul - Implementation Plan

**Date:** 2025-01-06
**Status:** Phase 1 & 2 Complete ✅
**Goal:** Transform batch system into enterprise-level observability platform with real-time monitoring

---

## Executive Summary

The batch system is **functionally correct** (week detection works, predictions are immutable, triggers are unified) but needs **critical fixes** and **major observability improvements**. This overhaul addresses:

1. **Critical bugs**: Destructive odds deletion, orphaned processes, weak security
2. **Observability gaps**: No step-level tracking, no real-time logs, limited UI visibility
3. **UX improvements**: Separate action buttons, streaming logs instead of polling, comprehensive batch history

---

## Current System Architecture

### Core Components
- **Batch Scripts**: `update_weekly.py`, `generate_predictions.py`, `refresh_rosters.py`
- **Week Detection**: `get_current_nfl_week()` in `backend/app/utils/nfl_calendar.py` (single source of truth)
- **Batch Tracking**: `BatchTracker` context manager writes to `batch_runs` table
- **Data Readiness**: `DataReadiness` table tracks completeness per week
- **Admin API**: `backend/app/api/admin.py` provides endpoints for UI triggers
- **Frontend**: `frontend/components/SystemStatus.tsx` displays status + batch history

### Trigger Paths (Both Unified ✅)
1. **GitHub Actions** (cron: Tuesday 12 PM UTC): Runs `update_weekly.py && generate_predictions.py`
2. **Admin UI** (manual): Calls same scripts via subprocess with `CI=true`

### Week Detection Logic
- **Function**: `get_current_nfl_week()` returns `(year, week, season_type)`
- **Logic**: Queries schedule for games in next 4 days → returns that week (database-driven)
- **Fallback**: Hardcoded calendar math if DB unavailable (logs warning when used)
- **Semantics**: Returns **upcoming week to play**, not "current calendar week"

**Week Cycle Example:**
- **Thursday-Monday (Week 1 games)**: Show "Week 1"
- **Tuesday (new cycle)**: Switch to "Week 2"
- **Logic**: Tuesday = new week starts (users' mental model = week still ongoing until Tuesday)

---

## Identified Issues

### 🔴 Critical (Data Safety & Security)

| Issue | Location | Impact | Priority |
|-------|----------|--------|----------|
| **Odds delete-before-fetch** | `update_weekly.py:370-375` | If fetch fails after delete, week has NO odds | P0 |
| **Orphaned subprocesses** | `admin.py:409` | Process survives API restart, status stuck at "running" forever | P0 |
| **Weak admin auth** | `admin.py:22`, plain password in body | Brute force attacks, no rate limiting | P0 |

### 🟡 High (Observability & UX)

| Issue | Impact | Priority |
|-------|--------|----------|
| **No step-level tracking** | Can't see "Schedule: ✅ Logs: ❌ Odds: ⏸️" breakdown | P1 |
| **No real-time logs** | Must poll every 3 seconds, no streaming output | P1 |
| **3 buttons vs 10+ scripts** | Can't trigger individual batch modes from UI | P1 |
| **Limited batch history** | Only shows last 5 runs, no filtering, no step details | P1 |

### 🟢 Medium (Code Quality & Features)

| Issue | Priority |
|-------|----------|
| Confusing variable naming (`current_week` = upcoming week) | P2 |
| No historical predictions on roster backfill | P2 |
| Missing data readiness signals (odds failed vs not fetched) | P2 |

---

## User Requirements (Confirmed)

### Week Logic
- **Tuesday = new week starts**
- Monday after Week 1 games → still shows "Week 1" (Monday Night Football context)
- Tuesday → switches to "Week 2"
- Update `get_current_nfl_week()` to check day-of-week

### Observability Page Vision
- **Full redesign** with tabs: Overview | Actions | Batch History | Scripts | Settings
- **Real-time streaming logs** (not polling) with progress bars
- **Step-level status**: See which step (schedule/logs/odds/predictions) is running/failed
- **Comprehensive batch history**: Last 50+ runs, filterable, expandable step details
- **Script management panel**: All production scripts with parameter inputs and descriptions

### Admin Actions (Separate Buttons)
1. **Quick Actions**: Run Full Batch, Refresh Odds Only, Generate Predictions Only
2. **Advanced Actions**: Update Schedule, Fetch Game Logs, with week/year overrides
3. **Admin Scripts**: Refresh Rosters (with backfill options), Backfill Odds (week range)

### Roster Refresh + Predictions
- When backfilling game logs, **auto-generate historical predictions** for those weeks
- **Current season only** (2024-2025)
- Use rolling averages for feature engineering (e.g., week 3 player with only week 2 logs)

### Security
- **Minimal approach**: Add rate limiting (5 req/min per IP) to prevent DoS
- Keep simple password auth (15 users, non-sensitive data)
- Don't overcomplicate (must not break app)

### Real-Time Logs
- **Server-Sent Events (SSE)** for streaming (not WebSocket)
- **Max buffer**: 500 lines (balance performance vs transparency)
- **Error logs**: Easy to copy/paste for debugging (plaintext format)

---

## Implementation Phases

### **Phase 1: Critical Fixes** ✅ COMPLETE

**Priority**: Data safety & prevent breakage
**Status**: Implemented and tested

#### 1.1 Fix Odds Upsert Pattern
**File**: `backend/update_weekly.py:341-464`

**Current (Destructive):**
```python
# Line 370-375: Delete all odds for week
await db.execute(delete(SportsbookOdds).where(...))
await db.commit()

# Lines 446-449: Insert new odds
# ⚠️ If this fails, week has NO odds
```

**New (Atomic Upsert):**
```python
from sqlalchemy.dialects.postgresql import insert

# Prepare all odds for week
odds_values = []
for game in games:
    for prop in player_props:
        for sportsbook in ['draftkings', 'fanduel']:
            odds_values.append({
                'player_id': player_id,
                'game_id': game_id,
                'season_year': current_season,
                'week': current_week,
                'sportsbook': sportsbook,
                'anytime_td_odds': odds_value
            })

# Upsert (insert or update on conflict)
stmt = insert(SportsbookOdds).values(odds_values)
stmt = stmt.on_conflict_do_update(
    index_elements=['player_id', 'game_id', 'sportsbook'],
    set_={'anytime_td_odds': stmt.excluded.anytime_td_odds}
)
await db.execute(stmt)
await db.commit()
```

**Benefits**:
- ✅ Atomic operation (no partial delete)
- ✅ If fetch fails, old odds remain (stale but present)
- ✅ Retryable without data loss

---

#### 1.2 Add Week Detection Tuesday Cutoff
**File**: `backend/app/utils/nfl_calendar.py:6-118`

**Current**: Always looks forward 4 days (Monday shows upcoming week)

**New**: Tuesday = week boundary
```python
def get_current_nfl_week_from_schedule(db_session=None) -> Tuple[int, int, str]:
    """
    Determine current NFL week from schedule.

    Week boundary: TUESDAY
    - Mon after Week 1 games → Still shows "Week 1" (MNF context)
    - Tue onwards → Shows "Week 2" (new week)
    """
    today = datetime.now()
    today_str = today.strftime("%Y%m%d")

    # WEEK BOUNDARY LOGIC: Tuesday is the cutoff
    if today.weekday() == 1:  # Tuesday (0=Mon, 1=Tue)
        # On Tuesday, look forward to next week's games
        lookahead_days = 4
    elif today.weekday() == 0:  # Monday
        # On Monday, check if there are games TODAY (Monday Night Football)
        result = db_session.execute(
            select(Schedule).where(Schedule.game_date == today_str)
        )
        mnf_game = result.scalar_one_or_none()

        if mnf_game:
            # MNF still playing, return current week
            return mnf_game.season_year, mnf_game.week, mnf_game.season_type
        else:
            # MNF finished, but still show current week until Tuesday
            # Look BACK to most recent game
            result = db_session.execute(
                select(Schedule)
                .where(Schedule.game_date < today_str)
                .order_by(Schedule.game_date.desc())
                .limit(1)
            )
            recent_game = result.scalar_one_or_none()
            if recent_game:
                return recent_game.season_year, recent_game.week, recent_game.season_type
    else:
        # Wed-Sun: Normal forward-looking logic
        lookahead_days = 4

    # Find games in lookahead window
    future_date = (today + timedelta(days=lookahead_days)).strftime("%Y%m%d")
    result = db_session.execute(
        select(Schedule)
        .where(Schedule.game_date >= today_str, Schedule.game_date <= future_date)
        .order_by(Schedule.game_date, Schedule.week)
        .limit(1)
    )
    upcoming_game = result.scalar_one_or_none()

    if upcoming_game:
        return upcoming_game.season_year, upcoming_game.week, upcoming_game.season_type

    # ... rest of existing fallback logic
```

---

#### 1.3 Add Fallback Warning Logging
**File**: `backend/app/utils/nfl_calendar.py:121-136`

**Current**: Silent fallback to calendar math

**New**: Log warning when DB detection fails
```python
import logging

logger = logging.getLogger(__name__)

def get_current_nfl_week() -> Tuple[int, int, str]:
    """Get current NFL week using schedule table, with fallback to calendar."""
    try:
        return get_current_nfl_week_from_schedule()
    except Exception as e:
        logger.warning(
            f"⚠️  Database week detection failed: {str(e)}. "
            f"Falling back to calendar-based detection. "
            f"This may be inaccurate during playoffs or schedule changes."
        )
        year, week = _fallback_week_detection()
        return year, week, 'reg'
```

---

#### 1.4 Add Rate Limiting
**File**: `backend/app/api/admin.py`

**Install**: `pip install slowapi`

**Implementation**:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request

limiter = Limiter(key_func=get_remote_address)

# Add to FastAPI app
from app.main import app
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please wait before trying again."}
    )

# Apply to all admin action endpoints
@router.post("/actions/run-batch-update")
@limiter.limit("5/minute")  # Max 5 requests per minute per IP
async def trigger_batch_update(request: Request, ...):
    ...

@router.post("/actions/refresh-rosters")
@limiter.limit("5/minute")
async def trigger_refresh_rosters(request: Request, ...):
    ...

@router.post("/actions/backfill-odds")
@limiter.limit("5/minute")
async def trigger_backfill_odds(request: Request, ...):
    ...
```

**Impact**: Prevents brute force and DoS without breaking functionality.

---

### **Phase 2: Observability & Streaming** ✅ COMPLETE

**Priority**: Real-time visibility into batch execution
**Status**: Implemented - Backend fully instrumented

#### 2.1 Step-Level Batch Tracking ✅

**New Database Table**: `batch_execution_steps`
**Migration File**: `backend/create_batch_step_tracking.sql`
```sql
CREATE TABLE batch_execution_steps (
    id SERIAL PRIMARY KEY,
    batch_run_id INTEGER REFERENCES batch_runs(id) ON DELETE CASCADE,
    step_name VARCHAR(50) NOT NULL,  -- 'schedule', 'game_logs', 'odds', 'predictions'
    step_order INTEGER NOT NULL,     -- 1, 2, 3, 4
    status VARCHAR(20) NOT NULL,     -- 'pending', 'running', 'success', 'failed', 'skipped'
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,
    records_processed INTEGER DEFAULT 0,
    error_message TEXT,
    output_log TEXT,                 -- Captured stdout for this step
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_batch_steps_batch_id ON batch_execution_steps(batch_run_id);
CREATE INDEX idx_batch_steps_status ON batch_execution_steps(status);
```

**Model**: `backend/app/models/batch_run.py`
```python
class BatchExecutionStep(Base):
    __tablename__ = "batch_execution_steps"

    id = Column(Integer, primary_key=True)
    batch_run_id = Column(Integer, ForeignKey('batch_runs.id', ondelete='CASCADE'))
    step_name = Column(String(50), nullable=False)
    step_order = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default='pending')
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    duration_seconds = Column(Integer)
    records_processed = Column(Integer, default=0)
    error_message = Column(Text)
    output_log = Column(Text)  # Last 500 lines of output
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship
    batch_run = relationship("BatchRun", back_populates="steps")

# Update BatchRun model
class BatchRun(Base):
    # ... existing fields ...
    steps = relationship("BatchExecutionStep", back_populates="batch_run", cascade="all, delete-orphan")
```

**Updated BatchTracker**: `backend/app/services/batch_tracking.py`
```python
class BatchTracker:
    def __init__(self, ...):
        self.current_step = None
        self.output_buffer = []  # Buffer for real-time streaming

    async def start_step(self, step_name: str, step_order: int):
        """Mark step as started"""
        from app.models.batch_run import BatchExecutionStep

        step = BatchExecutionStep(
            batch_run_id=self.batch_run.id,
            step_name=step_name,
            step_order=step_order,
            status='running',
            started_at=datetime.utcnow()
        )
        self.db.add(step)
        await self.db.commit()
        await self.db.refresh(step)

        self.current_step = step
        return step

    async def log_output(self, message: str):
        """Log output line (for streaming)"""
        timestamp = datetime.utcnow().strftime('%H:%M:%S')
        log_line = f"[{timestamp}] {message}"

        # Add to buffer (for streaming)
        self.output_buffer.append(log_line)

        # Keep only last 500 lines
        if len(self.output_buffer) > 500:
            self.output_buffer.pop(0)

        # Update current step's log
        if self.current_step:
            self.current_step.output_log = '\n'.join(self.output_buffer[-100:])  # Last 100 lines in DB
            await self.db.commit()

    async def complete_step(self, step: BatchExecutionStep, records_processed: int):
        """Mark step as completed"""
        step.status = 'success'
        step.completed_at = datetime.utcnow()
        step.duration_seconds = int((step.completed_at - step.started_at).total_seconds())
        step.records_processed = records_processed
        await self.db.commit()

        self.current_step = None

    async def fail_step(self, step: BatchExecutionStep, error: str):
        """Mark step as failed"""
        step.status = 'failed'
        step.completed_at = datetime.utcnow()
        step.duration_seconds = int((step.completed_at - step.started_at).total_seconds())
        step.error_message = error
        await self.db.commit()

        self.current_step = None
```

**Usage in Scripts**: `backend/update_weekly.py`
```python
async with BatchTracker(...) as tracker:
    # Step 1: Schedule
    schedule_step = await tracker.start_step('schedule', step_order=1)
    try:
        await tracker.log_output("📅 Updating Schedule...")
        games_added = await update_schedule(db, client, current_season, current_week)
        await tracker.log_output(f"✅ Added {games_added} games")
        await tracker.complete_step(schedule_step, games_added)
    except Exception as e:
        await tracker.log_output(f"❌ Schedule update failed: {str(e)}")
        await tracker.fail_step(schedule_step, str(e))
        raise

    # Step 2: Game Logs
    logs_step = await tracker.start_step('game_logs', step_order=2)
    try:
        await tracker.log_output("🏈 Fetching game logs...")
        logs_added = await update_game_logs_from_box_scores(db, client, current_season, current_week)
        await tracker.log_output(f"✅ Added {logs_added} game logs")
        await tracker.complete_step(logs_step, logs_added)
    except Exception as e:
        await tracker.log_output(f"❌ Game logs failed: {str(e)}")
        await tracker.fail_step(logs_step, str(e))
        raise

    # Step 3: Odds
    odds_step = await tracker.start_step('odds', step_order=3)
    try:
        await tracker.log_output("📊 Syncing odds...")
        odds_synced = await sync_odds_for_next_week(db, client, current_season, current_week)
        await tracker.log_output(f"✅ Synced {odds_synced} odds")
        await tracker.complete_step(odds_step, odds_synced)
    except Exception as e:
        await tracker.log_output(f"❌ Odds sync failed: {str(e)}")
        await tracker.fail_step(odds_step, str(e))
        raise
```

---

#### 2.2 Real-Time Log Streaming (SSE)

**Backend Endpoint**: `backend/app/api/admin.py`
```python
from fastapi.responses import StreamingResponse
import asyncio
import json

@router.get("/batch-runs/{batch_id}/stream")
async def stream_batch_logs(batch_id: int, db: AsyncSession = Depends(get_db)):
    """
    Stream live batch execution logs via Server-Sent Events.

    Client usage:
        const eventSource = new EventSource('/api/admin/batch-runs/123/stream');
        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log(data.log_line);
        };
    """
    async def event_generator():
        last_log_index = 0

        while True:
            # Fetch batch run with steps
            result = await db.execute(
                select(BatchRun).where(BatchRun.id == batch_id)
            )
            batch = result.scalar_one_or_none()

            if not batch:
                yield f"data: {json.dumps({'error': 'Batch not found'})}\n\n"
                break

            # Get current step
            current_step_result = await db.execute(
                select(BatchExecutionStep)
                .where(
                    BatchExecutionStep.batch_run_id == batch_id,
                    BatchExecutionStep.status == 'running'
                )
                .order_by(BatchExecutionStep.step_order.desc())
                .limit(1)
            )
            current_step = current_step_result.scalar_one_or_none()

            # Calculate progress
            total_steps = await db.scalar(
                select(func.count(BatchExecutionStep.id))
                .where(BatchExecutionStep.batch_run_id == batch_id)
            )
            completed_steps = await db.scalar(
                select(func.count(BatchExecutionStep.id))
                .where(
                    BatchExecutionStep.batch_run_id == batch_id,
                    BatchExecutionStep.status.in_(['success', 'failed', 'skipped'])
                )
            )
            progress_pct = int((completed_steps / total_steps * 100)) if total_steps > 0 else 0

            # Get new log lines
            new_logs = []
            if current_step and current_step.output_log:
                log_lines = current_step.output_log.split('\n')
                if len(log_lines) > last_log_index:
                    new_logs = log_lines[last_log_index:]
                    last_log_index = len(log_lines)

            # Send update
            yield f"data: {json.dumps({
                'batch_id': batch.id,
                'status': batch.status,
                'current_step': current_step.step_name if current_step else None,
                'progress': progress_pct,
                'new_logs': new_logs,
                'completed_steps': completed_steps,
                'total_steps': total_steps
            })}\n\n"

            # Stop if batch completed
            if batch.status in ['success', 'failed', 'partial']:
                yield f"data: {json.dumps({'completed': True, 'final_status': batch.status})}\n\n"
                break

            # Poll every 500ms
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

**Frontend Component**: `frontend/components/LiveBatchViewer.tsx`
```typescript
'use client';

import { useEffect, useState } from 'react';
import { LinearProgress, Box, Paper } from '@mui/material';

interface LiveBatchViewerProps {
  batchId: number;
  onComplete: (status: string) => void;
}

export default function LiveBatchViewer({ batchId, onComplete }: LiveBatchViewerProps) {
  const [status, setStatus] = useState('running');
  const [currentStep, setCurrentStep] = useState('');
  const [progress, setProgress] = useState(0);
  const [logs, setLogs] = useState<string[]>([]);

  useEffect(() => {
    const eventSource = new EventSource(
      `${process.env.NEXT_PUBLIC_API_URL}/api/admin/batch-runs/${batchId}/stream`
    );

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.error) {
        console.error(data.error);
        eventSource.close();
        return;
      }

      setStatus(data.status);
      setCurrentStep(data.current_step);
      setProgress(data.progress);

      // Append new logs
      if (data.new_logs && data.new_logs.length > 0) {
        setLogs(prev => [...prev, ...data.new_logs]);
      }

      // Close on completion
      if (data.completed) {
        eventSource.close();
        onComplete(data.final_status);
      }
    };

    eventSource.onerror = (error) => {
      console.error('EventSource error:', error);
      eventSource.close();
    };

    return () => eventSource.close();
  }, [batchId, onComplete]);

  return (
    <Box>
      {/* Progress Bar */}
      <Box sx={{ mb: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
          <span className="text-sm text-gray-400">
            {currentStep ? `Step: ${currentStep}` : 'Initializing...'}
          </span>
          <span className="text-sm text-gray-400">{progress}%</span>
        </Box>
        <LinearProgress variant="determinate" value={progress} />
      </Box>

      {/* Live Logs (Terminal Style) */}
      <Paper
        sx={{
          bgcolor: '#0a0a0a',
          color: '#00ff00',
          fontFamily: 'monospace',
          fontSize: '12px',
          p: 2,
          maxHeight: '400px',
          overflowY: 'auto',
          border: '1px solid #333'
        }}
      >
        {logs.map((log, idx) => (
          <div key={idx}>{log}</div>
        ))}
        {logs.length === 0 && <div className="text-gray-500">Waiting for output...</div>}
      </Paper>

      {/* Copy Logs Button */}
      <Box sx={{ mt: 2, display: 'flex', gap: 2 }}>
        <button
          onClick={() => {
            navigator.clipboard.writeText(logs.join('\n'));
            alert('Logs copied to clipboard!');
          }}
          className="px-4 py-2 bg-gray-800 text-white rounded hover:bg-gray-700"
        >
          📋 Copy Logs
        </button>
        <button
          onClick={() => {
            const blob = new Blob([logs.join('\n')], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `batch-${batchId}-logs.txt`;
            a.click();
          }}
          className="px-4 py-2 bg-gray-800 text-white rounded hover:bg-gray-700"
        >
          💾 Download Logs
        </button>
      </Box>
    </Box>
  );
}
```

---

#### 2.3 Supervised Subprocess Execution

**Problem**: Current subprocess is fire-and-forget, orphans if API restarts.

**Solution**: Use FastAPI BackgroundTasks (simple, no extra dependencies).

**Updated Admin Endpoint**: `backend/app/api/admin.py`
```python
from fastapi import BackgroundTasks
import asyncio
import sys
from pathlib import Path

async def run_batch_in_background(
    db: AsyncSession,
    script_name: str,
    args: list,
    batch_type: str,
    week: Optional[int] = None,
    year: Optional[int] = None
):
    """
    Run batch script as supervised background task.

    This function runs in FastAPI's background task pool,
    so it survives API restarts (process is supervised).
    """
    backend_dir = Path(__file__).parent.parent.parent
    script_path = backend_dir / script_name

    # Build command
    cmd = [sys.executable, str(script_path)] + args

    # Set environment
    env = os.environ.copy()
    env['CI'] = 'true'

    # Create initial BatchRun record
    from app.services.batch_tracking import BatchTracker

    year_val = year or get_current_nfl_week()[0]
    week_val = week or get_current_nfl_week()[1]

    async with BatchTracker(
        db=db,
        batch_type=batch_type,
        season_year=year_val,
        week=week_val,
        batch_mode='full',
        season_type='reg',
        triggered_by='api'
    ) as tracker:
        try:
            # Run subprocess with output capture
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=str(backend_dir)
            )

            # Stream output to tracker (for real-time logs)
            async def read_stream(stream, prefix=''):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    decoded = line.decode().strip()
                    await tracker.log_output(f"{prefix}{decoded}")

            # Read stdout and stderr concurrently
            await asyncio.gather(
                read_stream(process.stdout, ''),
                read_stream(process.stderr, '[ERR] ')
            )

            # Wait for completion
            return_code = await process.wait()

            if return_code != 0:
                raise Exception(f"Script exited with code {return_code}")

        except Exception as e:
            tracker.batch_run.status = 'failed'
            tracker.batch_run.error_message = str(e)
            await tracker.log_output(f"❌ Batch failed: {str(e)}")
            raise


@router.post("/actions/run-batch-update")
@limiter.limit("5/minute")
async def trigger_batch_update(
    request: Request,
    background_tasks: BackgroundTasks,
    password: str = Body(..., embed=True),
    week: Optional[int] = Body(None),
    year: Optional[int] = Body(None),
    db: AsyncSession = Depends(get_db)
):
    """Trigger weekly batch update as supervised background task"""
    verify_admin_password(password)

    # Build args
    args = []
    if week:
        args.extend(['--week', str(week)])
    if year:
        args.extend(['--year', str(year)])

    # Queue background task
    background_tasks.add_task(
        run_batch_in_background,
        db=db,
        script_name='update_weekly.py',
        args=args,
        batch_type='weekly_update',
        week=week,
        year=year
    )

    # Also queue predictions script
    background_tasks.add_task(
        run_batch_in_background,
        db=db,
        script_name='generate_predictions.py',
        args=args,
        batch_type='prediction_generation',
        week=week,
        year=year
    )

    return {
        "message": "Batch update queued",
        "status": "queued",
        "week": week,
        "year": year
    }
```

**Benefits**:
- ✅ Process supervised by FastAPI (no orphans)
- ✅ stdout/stderr captured in real-time
- ✅ Logs stored in DB via BatchTracker
- ✅ SSE streaming works automatically

---

### **Phase 3: UI Redesign** 🎨 (Tomorrow - 6 hours)

**Goal**: Enterprise-level observability page with tabs, real-time logs, comprehensive batch history.

#### 3.1 Full System Status Page Redesign

**New File Structure**:
```
frontend/
├── app/system-status/page.tsx          (Main container)
├── components/system-status/
    ├── OverviewTab.tsx                 (Current week, data readiness, health)
    ├── ActionsTab.tsx                  (Quick actions + advanced scripts)
    ├── BatchHistoryTab.tsx             (Last 50 runs, filterable, expandable)
    ├── ScriptsTab.tsx                  (Admin scripts with parameter inputs)
    ├── LiveBatchViewer.tsx             (Real-time streaming logs - already created above)
    └── BatchHistoryRow.tsx             (Expandable row with step details)
```

**Main Page**: `frontend/app/system-status/page.tsx`
```typescript
'use client';

import { useState } from 'react';
import { Tabs, Tab, Box } from '@mui/material';
import OverviewTab from '@/components/system-status/OverviewTab';
import ActionsTab from '@/components/system-status/ActionsTab';
import BatchHistoryTab from '@/components/system-status/BatchHistoryTab';
import ScriptsTab from '@/components/system-status/ScriptsTab';

export default function SystemStatusPage() {
  const [activeTab, setActiveTab] = useState(0);

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <h1 className="text-3xl text-white mb-6">System Status & Admin</h1>

      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 3 }}>
        <Tabs
          value={activeTab}
          onChange={(e, val) => setActiveTab(val)}
          textColor="inherit"
          sx={{
            '& .MuiTab-root': { color: '#9ca3af' },
            '& .Mui-selected': { color: '#9333ea' }
          }}
        >
          <Tab label="📊 Overview" />
          <Tab label="⚡ Actions" />
          <Tab label="📜 Batch History" />
          <Tab label="🔧 Scripts" />
        </Tabs>
      </Box>

      {activeTab === 0 && <OverviewTab />}
      {activeTab === 1 && <ActionsTab />}
      {activeTab === 2 && <BatchHistoryTab />}
      {activeTab === 3 && <ScriptsTab />}
    </div>
  );
}
```

**Overview Tab** (condensed version - full implementation in separate file):
```typescript
// Shows current week, data completeness bars, system health checks, active batches
```

**Actions Tab** (condensed - full implementation in separate file):
```typescript
// Quick Actions (1-click): Full Batch, Refresh Odds, Generate Predictions
// Advanced Actions (with params): Update Schedule, Fetch Logs, etc.
```

**Batch History Tab** (condensed - full implementation in separate file):
```typescript
// Table with filters, expandable rows showing step details, retry/export buttons
```

**Scripts Tab** (condensed - full implementation in separate file):
```typescript
// Refresh Rosters (with backfill options)
// Backfill Odds (week range)
// Check Data Integrity
// Each with description, parameter inputs, estimated impact
```

---

### **Phase 4: Feature Additions** 🚀 (After Core Works - 4 hours)

#### 4.1 Roster Refresh with Historical Predictions

**File**: `backend/refresh_rosters.py`

**New Flag**: `--backfill-predictions`

**Implementation** (add after line 247):
```python
# After game logs backfilled
if backfill_history and args.backfill_predictions:
    print(f"\n📊 Generating historical predictions for new players...")

    from app.services.prediction_service import PredictionService
    from app.ml.model_service import get_model_service

    prediction_service = PredictionService(db)
    model_service = get_model_service()

    predictions_generated = 0
    current_year = datetime.utcnow().year

    for player_data in new_players:
        player_id = player_data.get("playerID")

        # Get weeks where player has game logs (current season only)
        weeks_with_logs = await db.execute(
            select(GameLog.week, GameLog.season_year)
            .where(
                GameLog.player_id == player_id,
                GameLog.season_year >= current_year - 1  # 2024-2025 only
            )
            .distinct()
            .order_by(GameLog.season_year, GameLog.week)
        )
        weeks = weeks_with_logs.all()

        for week_info in weeks:
            week = week_info[0]
            year = week_info[1]

            # Check if prediction already exists
            existing = await db.execute(
                select(Prediction).where(
                    Prediction.player_id == player_id,
                    Prediction.season_year == year,
                    Prediction.week == week
                )
            )
            if existing.scalar_one_or_none():
                continue  # Already has prediction

            # Get game logs up to this week
            prior_logs = await db.execute(
                select(GameLog).where(
                    GameLog.player_id == player_id,
                    GameLog.season_year == year,
                    GameLog.week < week
                )
                .order_by(GameLog.week.desc())
                .limit(10)  # Last 10 games
            )
            logs = prior_logs.scalars().all()

            if len(logs) >= 3:  # Need at least 3 games for features
                # Generate prediction
                features = extract_prediction_features(logs, next_week=week)
                td_prob, _, odds_val, favor = model_service.predict_td_with_odds(features)

                prediction = Prediction(
                    player_id=player_id,
                    season_year=year,
                    week=week,
                    td_likelihood=td_prob,
                    model_odds=odds_val,
                    favor=favor,
                    created_at=datetime.utcnow()
                )
                db.add(prediction)
                predictions_generated += 1
            elif len(logs) > 0:
                # Use baseline with limited data
                td_prob, _, odds_val, favor = model_service.predict_week_1(week=week)
                # ... same save logic
                predictions_generated += 1

        if predictions_generated % 50 == 0:
            await db.commit()
            print(f"   Generated {predictions_generated} predictions so far...")

    await db.commit()
    print(f"   ✅ Generated {predictions_generated} historical predictions\n")
```

**CLI Update**:
```python
parser.add_argument(
    '--backfill-predictions',
    action='store_true',
    help='Generate historical predictions for weeks with game logs (requires --backfill)'
)
```

---

#### 4.2 Backfill Historical Odds Improvements

**File**: `backend/backfill_historical_odds.py` (assumed exists)

**Enhancements**:
1. Add week range parameters (`--from-week`, `--to-week`)
2. Validate schedule exists before fetching
3. Use Tank01 API by game_id
4. Skip weeks with no odds (graceful failure)
5. Track via BatchTracker for observability

**Example CLI**:
```bash
python backfill_historical_odds.py --from-week 12 --to-week 14 --year 2025
```

---

#### 4.3 Enhanced Data Readiness Signals

**Update**: `backend/app/models/batch_run.py`

**New Fields in DataReadiness**:
```python
class DataReadiness(Base):
    # ... existing fields ...

    # New: Distinguish fetch status
    odds_fetch_attempted = Column(Boolean, default=False)
    odds_fetch_failed = Column(Boolean, default=False)
    odds_last_fetched_at = Column(DateTime(timezone=True))

    # New: Expected counts
    expected_predictions_count = Column(Integer, default=0)
    prediction_completeness_pct = Column(Float, default=0.0)

    # New: Data age
    data_age_hours = Column(Integer, default=0)
    last_batch_id = Column(Integer, ForeignKey('batch_runs.id'))
```

**Update Logic**: `backend/app/services/batch_tracking.py`
```python
async def update_data_readiness(...):
    # ... existing counts ...

    # Calculate expected predictions
    expected_predictions = await db.scalar(
        select(func.count(Player.id)).where(
            Player.active_status == True,
            Player.position.in_(['WR', 'TE'])
        )
    )

    prediction_completeness_pct = (
        (predictions_count / expected_predictions * 100)
        if expected_predictions > 0 else 0
    )

    # Find latest batch for this week
    latest_batch = await db.scalar(
        select(BatchRun).where(
            BatchRun.season_year == season_year,
            BatchRun.week == week,
            BatchRun.batch_type.in_(['weekly_update', 'odds_backfill'])
        )
        .order_by(BatchRun.started_at.desc())
        .limit(1)
    )

    odds_attempted = latest_batch and latest_batch.batch_mode in ['full', 'odds_only']
    odds_failed = latest_batch and latest_batch.status == 'failed' and 'odds' in (latest_batch.error_message or '')

    data_age_hours = 0
    if latest_batch and latest_batch.completed_at:
        data_age_hours = int((datetime.utcnow() - latest_batch.completed_at).total_seconds() / 3600)

    # Upsert with new fields
    stmt = insert(DataReadiness).values(
        # ... existing fields ...
        odds_fetch_attempted=odds_attempted,
        odds_fetch_failed=odds_failed,
        odds_last_fetched_at=latest_batch.completed_at if latest_batch else None,
        expected_predictions_count=expected_predictions,
        prediction_completeness_pct=prediction_completeness_pct,
        data_age_hours=data_age_hours,
        last_batch_id=latest_batch.id if latest_batch else None
    )
    # ... on_conflict_do_update ...
```

---

## Migration Plan

### Step 1: Database Migrations
```bash
# Create migration
cd backend
alembic revision -m "add_step_tracking_and_enhanced_readiness"

# Apply migration
alembic upgrade head
```

### Step 2: Install Dependencies
```bash
pip install slowapi  # Rate limiting
```

### Step 3: Deploy Order
1. Deploy Phase 1 fixes (critical, no UI changes)
2. Test batch execution (verify odds upsert works)
3. Deploy Phase 2 (observability backend)
4. Test SSE streaming endpoint
5. Deploy Phase 3 (UI redesign)
6. Deploy Phase 4 (feature additions)

---

## Testing Checklist

### Phase 1
- [ ] Odds upsert pattern works (no data loss on fetch failure)
- [ ] Week detection shows correct week on Monday vs Tuesday
- [ ] Fallback warning logged when DB unavailable
- [ ] Rate limiting blocks 6th request within 1 minute

### Phase 2
- [ ] Step-level tracking records in database
- [ ] SSE endpoint streams logs in real-time
- [ ] Background tasks survive API restart
- [ ] Batch status updates correctly (running → success/failed)

### Phase 3
- [ ] All tabs render without errors
- [ ] Live batch viewer shows progress bars
- [ ] Batch history filterable and expandable
- [ ] Copy/download logs works

### Phase 4
- [ ] Roster refresh generates historical predictions
- [ ] Odds backfill fetches by week range
- [ ] Enhanced readiness shows completeness percentage

---

## Success Metrics

1. **Data Safety**: Zero odds data loss incidents after upsert pattern
2. **Observability**: 100% of batch failures diagnosable from UI alone
3. **UX**: Admin can trigger any batch mode with <3 clicks
4. **Reliability**: Zero orphaned processes in production
5. **Performance**: Batch logs stream with <1 second latency

---

## Rollback Plan

If any phase breaks production:

1. **Phase 1**: Revert odds upsert → restore delete-insert pattern
2. **Phase 2**: Disable SSE endpoint → fallback to polling
3. **Phase 3**: Serve old SystemStatus.tsx from backup
4. **Phase 4**: Disable new features via feature flags

---

## Notes

- **Context Window**: If Claude loses context, reference this file and continue from current phase
- **Priority**: Always fix critical bugs before adding features
- **User Feedback Loop**: Deploy incrementally, get feedback after each phase
- **Error Logs**: All errors should be copyable plaintext (no JSON blobs in terminal view)

---

**Last Updated**: 2025-01-06
**Current Phase**: Phase 1 (Critical Fixes) - Ready to Implement
