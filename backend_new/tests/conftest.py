"""
Shared test fixtures.

Sets env vars before any app imports so Settings() picks them up.
The DB is always mocked — no real PostgreSQL required to run tests.
"""

import os

# Must be set before app imports so pydantic Settings() sees them
os.environ.setdefault("ADMIN_KEY", "test-admin-key")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://test:test@localhost:5432/test_db",
)

from unittest.mock import AsyncMock, MagicMock  # noqa: E402

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402

ADMIN_KEY = "test-admin-key"
ADMIN_HEADERS = {"X-Admin-Key": ADMIN_KEY}


def make_mock_session() -> AsyncMock:
    """Return a fresh AsyncMock that quacks like an AsyncSession."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.get = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def mock_db():
    return make_mock_session()


@pytest_asyncio.fixture
async def public_client(mock_db):
    """AsyncClient wired to the app with get_db mocked out."""
    async def _override():
        yield mock_db

    app.dependency_overrides[get_db] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def admin_client(mock_db):
    """AsyncClient wired to the app with get_db mocked and ADMIN_KEY set."""
    async def _override():
        yield mock_db

    app.dependency_overrides[get_db] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_db, None)
