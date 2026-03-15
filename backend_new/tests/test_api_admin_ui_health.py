"""
Tests for GET /api/admin-ui/health.

Strategy:
  - DB is fully mocked — no real PostgreSQL required.
  - JWT auth is bypassed by overriding get_optional_user to return a mock admin user.
  - The mock_db.execute return value is set up to handle all call patterns the endpoint
    uses: .scalar_one(), .scalar_one_or_none(), .scalars().all(), and .all().

Run:
    cd backend_new
    pytest tests/test_api_admin_ui_health.py -v
"""

import os

# Must be set before app imports — conftest sets ADMIN_KEY and DATABASE_URL
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-pytest-only-not-production")

from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_optional_user
from app.database import get_db
from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_admin_user():
    user = MagicMock()
    user.is_admin = True
    user.is_active = True
    user.is_subscriber = True
    return user


def _make_non_admin_user():
    user = MagicMock()
    user.is_admin = False
    user.is_active = True
    user.is_subscriber = False
    return user


def _make_scalar_result(value=0):
    """
    Build a MagicMock that handles every result-access pattern the health endpoint uses:
      - .scalar_one()            — table counts and week-level counts
      - .scalar_one_or_none()    — season/week resolution queries
      - .scalars().all()         — data_quality_events rows
      - .all()                   — missing_game_log_players rows + available_weeks rows
    """
    result = MagicMock()
    result.scalar_one.return_value = value
    result.scalar_one_or_none.return_value = value
    result.scalars.return_value.all.return_value = []
    result.all.return_value = []
    return result


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def admin_ui_client():
    """
    AsyncClient with:
      - get_db overridden with a mock that returns sensible scalar defaults
      - get_optional_user overridden to return a mock admin user

    This bypasses both the JWT decode path and the DB user lookup inside
    get_optional_user, while still exercising require_auth → require_admin_user.
    """
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=_make_scalar_result(0))
    admin_user = _make_admin_user()

    async def _db_override():
        yield mock_db

    async def _auth_override():
        return admin_user

    app.dependency_overrides[get_db] = _db_override
    app.dependency_overrides[get_optional_user] = _auth_override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_optional_user, None)


@pytest_asyncio.fixture
async def no_auth_client():
    """AsyncClient with get_db mocked but NO auth override — simulates anonymous requests."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=_make_scalar_result(0))

    async def _db_override():
        yield mock_db

    app.dependency_overrides[get_db] = _db_override
    # Do NOT override get_optional_user so it runs its real path (returns None → 401)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def non_admin_client():
    """AsyncClient where get_optional_user returns a non-admin user — expects 403."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=_make_scalar_result(0))
    non_admin = _make_non_admin_user()

    async def _db_override():
        yield mock_db

    async def _auth_override():
        return non_admin

    app.dependency_overrides[get_db] = _db_override
    app.dependency_overrides[get_optional_user] = _auth_override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_optional_user, None)


# ---------------------------------------------------------------------------
# TestHealthEndpointAuth
# ---------------------------------------------------------------------------

class TestHealthEndpointAuth:

    @pytest.mark.asyncio
    async def test_no_auth_returns_401(self, no_auth_client):
        """Unauthenticated request (no Authorization header) must return 401."""
        resp = await no_auth_client.get("/api/admin-ui/health")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_non_admin_returns_403(self, non_admin_client):
        """Authenticated user with is_admin=False must receive 403."""
        resp = await non_admin_client.get("/api/admin-ui/health")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# TestHealthEndpointResponseShape
# ---------------------------------------------------------------------------

class TestHealthEndpointResponseShape:

    @pytest.mark.asyncio
    async def test_default_response_shape(self, admin_ui_client):
        """
        With mocked DB (all scalars=0, all lists=[]) the endpoint must return 200
        and include every required top-level field.
        """
        resp = await admin_ui_client.get("/api/admin-ui/health")
        assert resp.status_code == 200, resp.text
        body = resp.json()

        required_fields = {
            "season",
            "week",
            "counts",
            "last_updated",
            "week_summary",
            "missing_game_log_players",
            "recent_data_quality_events",
            "available_weeks",
        }
        for field in required_fields:
            assert field in body, f"Missing top-level field: {field!r}"

    @pytest.mark.asyncio
    async def test_week_summary_fields(self, admin_ui_client):
        """week_summary must contain all 6 defined fields."""
        resp = await admin_ui_client.get("/api/admin-ui/health")
        assert resp.status_code == 200, resp.text
        week_summary = resp.json()["week_summary"]

        required = {
            "game_logs_ingested",
            "features_computed",
            "predictions_generated",
            "odds_available",
            "players_with_game_logs",
            "players_missing_game_logs",
        }
        for field in required:
            assert field in week_summary, f"Missing week_summary field: {field!r}"

    @pytest.mark.asyncio
    async def test_counts_has_all_tables(self, admin_ui_client):
        """counts must expose a key for every tracked table."""
        resp = await admin_ui_client.get("/api/admin-ui/health")
        assert resp.status_code == 200, resp.text
        counts = resp.json()["counts"]

        expected_keys = {
            "users",
            "players",
            "games",
            "player_game_logs",
            "player_features",
            "player_season_state",
            "predictions",
            "sportsbook_odds",
            "data_quality_events",
            "rookie_buckets",
            "team_game_stats",
        }
        for key in expected_keys:
            assert key in counts, f"Missing counts key: {key!r}"

    @pytest.mark.asyncio
    async def test_available_weeks_is_list(self, admin_ui_client):
        """available_weeks must be a list (possibly empty when DB is mocked)."""
        resp = await admin_ui_client.get("/api/admin-ui/health")
        assert resp.status_code == 200, resp.text
        assert isinstance(resp.json()["available_weeks"], list)

    @pytest.mark.asyncio
    async def test_no_prediction_coverage_field(self, admin_ui_client):
        """prediction_coverage must NOT appear in the response (it was removed)."""
        resp = await admin_ui_client.get("/api/admin-ui/health")
        assert resp.status_code == 200, resp.text
        assert "prediction_coverage" not in resp.json()


# ---------------------------------------------------------------------------
# TestHealthEndpointQueryParams
# ---------------------------------------------------------------------------

class TestHealthEndpointQueryParams:

    @pytest.mark.asyncio
    async def test_accepts_season_and_week_params(self, admin_ui_client):
        """Valid season and week query params must be accepted (200, not 422)."""
        resp = await admin_ui_client.get("/api/admin-ui/health?season=2024&week=14")
        assert resp.status_code == 200, resp.text

    @pytest.mark.asyncio
    async def test_rejects_invalid_season(self, admin_ui_client):
        """season=2019 is below the ge=2020 constraint — must return 422."""
        resp = await admin_ui_client.get("/api/admin-ui/health?season=2019")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_rejects_invalid_week(self, admin_ui_client):
        """week=23 exceeds the le=22 constraint — must return 422."""
        resp = await admin_ui_client.get("/api/admin-ui/health?week=23")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_rejects_week_zero(self, admin_ui_client):
        """week=0 is below the ge=1 constraint — must return 422."""
        resp = await admin_ui_client.get("/api/admin-ui/health?week=0")
        assert resp.status_code == 422
