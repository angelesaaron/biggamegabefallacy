"""
Admin API Endpoints

System status, batch run history, and data readiness indicators.
"""
from fastapi import APIRouter, Depends, Query, HTTPException, Body, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import subprocess
import os
from pathlib import Path

from app.database import get_db
from app.models.batch_run import BatchRun, DataReadiness
from app.utils.nfl_calendar import get_current_nfl_week
from app.config import settings

# Rate limiting
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()

# Admin password - in production, use environment variable
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme123")


@router.get("/batch-runs/latest")
async def get_latest_batch_run(
    batch_type: Optional[str] = Query(None, description="Filter by batch type"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the most recent batch run.

    Optionally filter by batch_type: 'weekly_update', 'prediction_generation', 'roster_refresh'
    """
    query = select(BatchRun).order_by(BatchRun.started_at.desc()).limit(1)

    if batch_type:
        query = query.where(BatchRun.batch_type == batch_type)

    result = await db.execute(query)
    latest = result.scalar_one_or_none()

    if not latest:
        return {"batch_run": None}

    return {
        "batch_run": {
            "id": latest.id,
            "batch_type": latest.batch_type,
            "batch_mode": latest.batch_mode,
            "season_year": latest.season_year,
            "week": latest.week,
            "season_type": latest.season_type,
            "started_at": latest.started_at.isoformat() if latest.started_at else None,
            "completed_at": latest.completed_at.isoformat() if latest.completed_at else None,
            "duration_seconds": latest.duration_seconds,
            "status": latest.status,
            "api_calls_made": latest.api_calls_made,
            "games_processed": latest.games_processed,
            "game_logs_added": latest.game_logs_added,
            "predictions_generated": latest.predictions_generated,
            "predictions_skipped": latest.predictions_skipped,
            "odds_synced": latest.odds_synced,
            "errors_encountered": latest.errors_encountered,
            "warnings": latest.warnings,
            "error_message": latest.error_message,
            "triggered_by": latest.triggered_by
        }
    }


@router.get("/batch-runs/history")
async def get_batch_run_history(
    limit: int = Query(10, description="Number of recent runs to return"),
    batch_type: Optional[str] = Query(None, description="Filter by batch type"),
    db: AsyncSession = Depends(get_db)
):
    """Get recent batch run history"""
    query = select(BatchRun).order_by(BatchRun.started_at.desc()).limit(limit)

    if batch_type:
        query = query.where(BatchRun.batch_type == batch_type)

    result = await db.execute(query)
    runs = result.scalars().all()

    return {
        "batch_runs": [
            {
                "id": run.id,
                "batch_type": run.batch_type,
                "batch_mode": run.batch_mode,
                "season_year": run.season_year,
                "week": run.week,
                "season_type": run.season_type,
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                "duration_seconds": run.duration_seconds,
                "status": run.status,
                "api_calls_made": run.api_calls_made,
                "games_processed": run.games_processed,
                "game_logs_added": run.game_logs_added,
                "predictions_generated": run.predictions_generated,
                "predictions_skipped": run.predictions_skipped,
                "odds_synced": run.odds_synced,
                "errors_encountered": run.errors_encountered,
                "warnings": run.warnings,
                "triggered_by": run.triggered_by
            }
            for run in runs
        ],
        "total": len(runs)
    }


@router.get("/data-readiness/current")
async def get_current_data_readiness(
    db: AsyncSession = Depends(get_db)
):
    """Get data readiness for current NFL week"""
    year, week, season_type = get_current_nfl_week()

    # Normalize season_type to abbreviated format used in data_readiness table
    season_type_map = {
        'Regular Season': 'reg',
        'Post Season': 'post',
        'reg': 'reg',
        'post': 'post'
    }
    normalized_season_type = season_type_map.get(season_type, 'reg')

    result = await db.execute(
        select(DataReadiness)
        .where(
            DataReadiness.season_year == year,
            DataReadiness.week == week,
            DataReadiness.season_type == normalized_season_type
        )
    )
    readiness = result.scalar_one_or_none()

    if not readiness:
        # Return default object with zeros instead of None
        return {
            "data_readiness": {
                "season_year": year,
                "week": week,
                "season_type": normalized_season_type,
                "schedule_complete": False,
                "game_logs_available": False,
                "predictions_available": False,
                "draftkings_odds_available": False,
                "fanduel_odds_available": False,
                "games_count": 0,
                "game_logs_count": 0,
                "predictions_count": 0,
                "draftkings_odds_count": 0,
                "fanduel_odds_count": 0,
                "last_updated": None
            },
            "current_week": {"year": year, "week": week, "season_type": season_type}
        }

    return {
        "data_readiness": {
            "season_year": readiness.season_year,
            "week": readiness.week,
            "season_type": readiness.season_type,
            "schedule_complete": readiness.schedule_complete,
            "game_logs_available": readiness.game_logs_available,
            "predictions_available": readiness.predictions_available,
            "draftkings_odds_available": readiness.draftkings_odds_available,
            "fanduel_odds_available": readiness.fanduel_odds_available,
            "games_count": readiness.games_count,
            "game_logs_count": readiness.game_logs_count,
            "predictions_count": readiness.predictions_count,
            "draftkings_odds_count": readiness.draftkings_odds_count,
            "fanduel_odds_count": readiness.fanduel_odds_count,
            "last_updated": readiness.last_updated.isoformat() if readiness.last_updated else None
        },
        "current_week": {"year": year, "week": week, "season_type": season_type}
    }


@router.get("/data-readiness/{year}/{week}")
async def get_week_data_readiness(
    year: int,
    week: int,
    season_type: str = Query('reg', description="Season type: reg or post"),
    db: AsyncSession = Depends(get_db)
):
    """Get data readiness for a specific week"""
    result = await db.execute(
        select(DataReadiness)
        .where(
            DataReadiness.season_year == year,
            DataReadiness.week == week,
            DataReadiness.season_type == season_type
        )
    )
    readiness = result.scalar_one_or_none()

    if not readiness:
        return {"data_readiness": None}

    return {
        "data_readiness": {
            "season_year": readiness.season_year,
            "week": readiness.week,
            "season_type": readiness.season_type,
            "schedule_complete": readiness.schedule_complete,
            "game_logs_available": readiness.game_logs_available,
            "predictions_available": readiness.predictions_available,
            "draftkings_odds_available": readiness.draftkings_odds_available,
            "fanduel_odds_available": readiness.fanduel_odds_available,
            "games_count": readiness.games_count,
            "game_logs_count": readiness.game_logs_count,
            "predictions_count": readiness.predictions_count,
            "draftkings_odds_count": readiness.draftkings_odds_count,
            "fanduel_odds_count": readiness.fanduel_odds_count,
            "last_updated": readiness.last_updated.isoformat() if readiness.last_updated else None
        }
    }


@router.get("/health/summary")
async def get_system_health_summary(
    db: AsyncSession = Depends(get_db)
):
    """
    Get overall system health summary.

    Combines latest batch run status with current week data readiness.
    """
    year, week, season_type = get_current_nfl_week()

    # Get latest batch run
    latest_run_result = await db.execute(
        select(BatchRun).order_by(BatchRun.started_at.desc()).limit(1)
    )
    latest_run = latest_run_result.scalar_one_or_none()

    # Get current week readiness
    readiness_result = await db.execute(
        select(DataReadiness)
        .where(
            DataReadiness.season_year == year,
            DataReadiness.week == week,
            DataReadiness.season_type == season_type
        )
    )
    readiness = readiness_result.scalar_one_or_none()

    # Calculate health score
    health_score = "unknown"
    if readiness:
        core_data_ready = (
            readiness.schedule_complete and
            readiness.predictions_available
        )
        odds_ready = (
            readiness.draftkings_odds_available or
            readiness.fanduel_odds_available
        )

        if core_data_ready and odds_ready:
            health_score = "healthy"
        elif core_data_ready:
            health_score = "partial"
        else:
            health_score = "incomplete"

    return {
        "current_week": {
            "year": year,
            "week": week,
            "season_type": season_type
        },
        "health_score": health_score,
        "latest_batch": {
            "type": latest_run.batch_type if latest_run else None,
            "status": latest_run.status if latest_run else None,
            "started_at": latest_run.started_at.isoformat() if latest_run and latest_run.started_at else None,
            "duration_seconds": latest_run.duration_seconds if latest_run else None
        } if latest_run else None,
        "data_readiness": {
            "schedule": readiness.schedule_complete if readiness else False,
            "predictions": readiness.predictions_available if readiness else False,
            "odds": (readiness.draftkings_odds_available or readiness.fanduel_odds_available) if readiness else False,
            "games_count": readiness.games_count if readiness else 0,
            "predictions_count": readiness.predictions_count if readiness else 0
        } if readiness else None
    }


def verify_admin_password(password: str):
    """Verify admin password"""
    if password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password")


@router.post("/actions/refresh-rosters")
@limiter.limit("5/minute")
async def trigger_refresh_rosters(
    request: Request,
    password: str = Body(..., embed=True)
):
    """
    Trigger the refresh_rosters.py script
    Requires admin password
    Rate limited: 5 requests per minute per IP
    """
    verify_admin_password(password)

    try:
        # Get the backend directory path
        backend_dir = Path(__file__).parent.parent.parent
        script_path = backend_dir / "refresh_rosters.py"

        if not script_path.exists():
            raise HTTPException(status_code=404, detail="refresh_rosters.py script not found")

        # Get the Python executable from the current environment (venv)
        python_exec = os.path.join(backend_dir, "venv", "bin", "python")
        if not os.path.exists(python_exec):
            python_exec = "python3"

        # Set environment variables for the subprocess
        env = os.environ.copy()
        env['CI'] = 'true'  # Skip confirmation prompts

        # Run the script in the background
        process = subprocess.Popen(
            [python_exec, str(script_path)],
            cwd=str(backend_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )

        return {
            "message": "Roster refresh initiated",
            "process_id": process.pid,
            "status": "running"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start roster refresh: {str(e)}")


@router.post("/actions/backfill-complete")
@limiter.limit("5/minute")
async def trigger_backfill_complete(
    request: Request,
    password: str = Body(..., embed=True),
    weeks: Optional[int] = Body(None),
    week: Optional[int] = Body(None),
    year: Optional[int] = Body(None)
):
    """
    Trigger the backfill_complete.py script (game logs, predictions, odds)
    Requires admin password
    Rate limited: 5 requests per minute per IP

    Optional parameters:
    - weeks: Backfill last N weeks (e.g., weeks=5 for last 5 weeks)
    - week: Specific week to backfill
    - year: Season year (defaults to current season)
    """
    verify_admin_password(password)

    try:
        # Get the backend directory path
        backend_dir = Path(__file__).parent.parent.parent
        script_path = backend_dir / "backfill_complete.py"

        if not script_path.exists():
            raise HTTPException(status_code=404, detail="backfill_complete.py script not found")

        # Get the Python executable from the current environment (venv)
        python_exec = os.path.join(backend_dir, "venv", "bin", "python")
        if not os.path.exists(python_exec):
            python_exec = "python3"

        # Build command with optional parameters
        cmd = [python_exec, str(script_path)]
        if weeks is not None:
            cmd.extend(["--weeks", str(weeks)])
        elif week is not None:
            cmd.extend(["--week", str(week)])
        if year is not None:
            cmd.extend(["--year", str(year)])

        # Set environment variables for the subprocess
        env = os.environ.copy()
        env['CI'] = 'true'  # Skip confirmation prompts

        # Run the script in the background
        process = subprocess.Popen(
            cmd,
            cwd=str(backend_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )

        if weeks:
            message = f"Complete backfill initiated for last {weeks} weeks"
        elif week:
            message = f"Complete backfill initiated for {year or 'current season'} Week {week}"
        else:
            message = "Complete backfill initiated for last 5 weeks (default)"

        return {
            "message": message,
            "process_id": process.pid,
            "status": "running",
            "weeks": weeks,
            "week": week,
            "year": year
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start complete backfill: {str(e)}")


@router.post("/actions/run-batch-update")
@limiter.limit("5/minute")
async def trigger_batch_update(
    request: Request,
    password: str = Body(..., embed=True),
    week: Optional[int] = Body(None),
    year: Optional[int] = Body(None)
):
    """
    Trigger the weekly batch update script
    Requires admin password
    Rate limited: 5 requests per minute per IP

    Runs update_weekly.py followed by generate_predictions.py
    (same as GitHub Actions workflow)
    """
    verify_admin_password(password)

    try:
        # Get the backend directory path
        backend_dir = Path(__file__).parent.parent.parent

        # Look for the main update script
        update_script = backend_dir / "update_weekly.py"
        predictions_script = backend_dir / "generate_predictions.py"

        if not update_script.exists():
            raise HTTPException(
                status_code=404,
                detail=f"update_weekly.py script not found at {update_script}"
            )

        # Get the Python executable from the current environment (venv)
        python_exec = os.path.join(backend_dir, "venv", "bin", "python")
        if not os.path.exists(python_exec):
            # Fallback to system python if venv doesn't exist
            python_exec = "python3"

        # Build command for update_weekly.py with optional week/year parameters
        cmd = [python_exec, str(update_script)]
        if week is not None:
            cmd.extend(["--week", str(week)])
        if year is not None:
            cmd.extend(["--year", str(year)])

        # Set environment variables for the subprocess
        env = os.environ.copy()
        env['CI'] = 'true'  # Skip confirmation prompts

        # Run update_weekly.py first
        update_process = subprocess.Popen(
            cmd,
            cwd=str(backend_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )

        # Run generate_predictions.py after (if it exists)
        # Note: This runs sequentially, but we return immediately to avoid timeout
        if predictions_script.exists():
            pred_cmd = [python_exec, str(predictions_script)]
            if week is not None:
                pred_cmd.extend(["--week", str(week)])
            if year is not None:
                pred_cmd.extend(["--year", str(year)])

            # Chain the prediction script to run after update completes
            # Using shell to run sequentially: update_weekly.py && generate_predictions.py
            combined_cmd = f"cd {backend_dir} && {' '.join(cmd)} && {' '.join(pred_cmd)}"

            process = subprocess.Popen(
                combined_cmd,
                shell=True,
                cwd=str(backend_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env
            )

            return {
                "message": "Batch update and predictions initiated",
                "process_id": process.pid,
                "status": "running",
                "week": week,
                "year": year,
                "scripts": ["update_weekly.py", "generate_predictions.py"]
            }
        else:
            return {
                "message": "Batch update initiated (predictions script not found)",
                "process_id": update_process.pid,
                "status": "running",
                "week": week,
                "year": year,
                "scripts": ["update_weekly.py"]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start batch update: {str(e)}")


@router.get("/batch-runs/{batch_run_id}/steps")
async def get_batch_run_steps(
    batch_run_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all steps for a specific batch run.

    Returns step-level execution details including:
    - Step name and order
    - Status (pending, running, success, failed, skipped)
    - Duration and records processed
    - Output logs for debugging
    """
    from app.models.batch_run import BatchExecutionStep

    result = await db.execute(
        select(BatchExecutionStep)
        .where(BatchExecutionStep.batch_run_id == batch_run_id)
        .order_by(BatchExecutionStep.step_order)
    )
    steps = result.scalars().all()

    if not steps:
        return {"steps": []}

    return {
        "batch_run_id": batch_run_id,
        "steps": [
            {
                "id": step.id,
                "step_name": step.step_name,
                "step_order": step.step_order,
                "status": step.status,
                "started_at": step.started_at.isoformat() if step.started_at else None,
                "completed_at": step.completed_at.isoformat() if step.completed_at else None,
                "duration_seconds": step.duration_seconds,
                "records_processed": step.records_processed,
                "error_message": step.error_message,
                "output_log": step.output_log
            }
            for step in steps
        ]
    }


@router.get("/batch-runs/{batch_run_id}")
async def get_batch_run_details(
    batch_run_id: int,
    include_steps: bool = Query(True, description="Include step details"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed information about a specific batch run.

    Includes batch metadata, metrics, and optionally step-level details.
    """
    from app.models.batch_run import BatchExecutionStep

    # Get batch run
    result = await db.execute(
        select(BatchRun).where(BatchRun.id == batch_run_id)
    )
    batch_run = result.scalar_one_or_none()

    if not batch_run:
        raise HTTPException(status_code=404, detail=f"Batch run {batch_run_id} not found")

    response = {
        "batch_run": {
            "id": batch_run.id,
            "batch_type": batch_run.batch_type,
            "batch_mode": batch_run.batch_mode,
            "season_year": batch_run.season_year,
            "week": batch_run.week,
            "season_type": batch_run.season_type,
            "started_at": batch_run.started_at.isoformat() if batch_run.started_at else None,
            "completed_at": batch_run.completed_at.isoformat() if batch_run.completed_at else None,
            "duration_seconds": batch_run.duration_seconds,
            "status": batch_run.status,
            "api_calls_made": batch_run.api_calls_made,
            "games_processed": batch_run.games_processed,
            "game_logs_added": batch_run.game_logs_added,
            "predictions_generated": batch_run.predictions_generated,
            "predictions_skipped": batch_run.predictions_skipped,
            "odds_synced": batch_run.odds_synced,
            "errors_encountered": batch_run.errors_encountered,
            "warnings": batch_run.warnings,
            "error_message": batch_run.error_message,
            "triggered_by": batch_run.triggered_by
        }
    }

    # Include steps if requested
    if include_steps:
        step_result = await db.execute(
            select(BatchExecutionStep)
            .where(BatchExecutionStep.batch_run_id == batch_run_id)
            .order_by(BatchExecutionStep.step_order)
        )
        steps = step_result.scalars().all()

        response["steps"] = [
            {
                "id": step.id,
                "step_name": step.step_name,
                "step_order": step.step_order,
                "status": step.status,
                "started_at": step.started_at.isoformat() if step.started_at else None,
                "completed_at": step.completed_at.isoformat() if step.completed_at else None,
                "duration_seconds": step.duration_seconds,
                "records_processed": step.records_processed,
                "error_message": step.error_message
            }
            for step in steps
        ]

    return response
