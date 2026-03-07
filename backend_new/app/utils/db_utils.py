"""
db_utils.py — Shared database helpers.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def execute_upsert(db: AsyncSession, stmt) -> tuple[int, int]:
    """
    Execute a pg_insert().on_conflict_do_update() statement.
    Returns (n_written, n_updated).

    Uses PostgreSQL's xmax system column to distinguish INSERT from UPDATE:
      xmax == 0  → row was freshly inserted
      xmax != 0  → row already existed and was updated in-place
    """
    result = await db.execute(stmt.returning(text("xmax")))
    row = result.fetchone()
    if row is None:
        return 0, 0
    return (1, 0) if int(row[0]) == 0 else (0, 1)
