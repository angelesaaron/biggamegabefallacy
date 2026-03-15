"""
Tests for Phase 2 admin-ui endpoints:
  - GET/POST/DELETE /api/admin-ui/week-override
  - POST /api/admin-ui/pipeline/* (auth + response shape)

Strategy:
  - DB is fully mocked — no real PostgreSQL required.
  - JWT auth is bypassed by overriding get_optional_user.
  - Pipeline services are patched at the module level so no Tank01 calls are made.

Run:
    cd backend_new
    pytest tests/test_api_admin_ui_pipeline.py -v
"""

import os

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-pytest-only-not-production")

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_optional_user
from app.database import get_db
from app.main import app
from app.services.sync_result import SyncResult


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


def _make_execute_result(scalars_first=None):
    """Build a mock db.execute() result that supports .scalars().first()."""
    result = MagicMock()
    result.scalars.return_value.first.return_value = scalars_first
    result.scalar_one.return_value = 0
    result.scalar_one_or_none.return_value = None
    return result


def _make_config_row(value: str):
    """Fake SystemConfig row."""
    row = MagicMock()
    row.value = value
    return row


def _make_sync_result(**kwargs) -> SyncResult:
    defaults = dict(n_written=1, n_updated=0, n_skipped=0, n_failed=0, events=[])
    defaults.update(kwargs)
    return SyncResult(**defaults)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def admin_client():
    """Admin-authenticated client with mocked DB."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=_make_execute_result())
    mock_db.commit = AsyncMock()
    admin_user = _make_admin_user()

    async def _db():
        yield mock_db

    async def _auth():
        return admin_user

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_optional_user] = _auth
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, mock_db
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_optional_user, None)


@pytest_asyncio.fixture
async def no_auth_client():
    """Unauthenticated client — get_optional_user returns None."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=_make_execute_result())

    async def _db():
        yield mock_db

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides.pop(get_optional_user, None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def non_admin_client():
    """Authenticated but non-admin client."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=_make_execute_result())
    non_admin = _make_non_admin_user()

    async def _db():
        yield mock_db

    async def _auth():
        return non_admin

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_optional_user] = _auth
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_optional_user, None)


# ---------------------------------------------------------------------------
# TestWeekOverrideAuth
# ---------------------------------------------------------------------------

class TestWeekOverrideAuth:

    @pytest.mark.asyncio
    async def test_get_no_auth_returns_401(self, no_auth_client):
        resp = await no_auth_client.get("/api/admin-ui/week-override")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_post_no_auth_returns_401(self, no_auth_client):
        resp = await no_auth_client.post(
            "/api/admin-ui/week-override", json={"season": 2025, "week": 14}
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_no_auth_returns_401(self, no_auth_client):
        resp = await no_auth_client.delete("/api/admin-ui/week-override")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_get_non_admin_returns_403(self, non_admin_client):
        resp = await non_admin_client.get("/api/admin-ui/week-override")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_post_non_admin_returns_403(self, non_admin_client):
        resp = await non_admin_client.post(
            "/api/admin-ui/week-override", json={"season": 2025, "week": 14}
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# TestWeekOverrideGet
# ---------------------------------------------------------------------------

class TestWeekOverrideGet:

    @pytest.mark.asyncio
    async def test_no_override_row_returns_inactive(self, admin_client):
        """When system_config has no row, override_active must be False."""
        client, mock_db = admin_client
        mock_db.execute.return_value = _make_execute_result(scalars_first=None)

        resp = await client.get("/api/admin-ui/week-override")
        assert resp.status_code == 200
        body = resp.json()
        assert body["override_active"] is False
        assert body["season"] is None
        assert body["week"] is None

    @pytest.mark.asyncio
    async def test_row_with_null_value_returns_inactive(self, admin_client):
        """Row exists but value is None/null — still inactive."""
        client, mock_db = admin_client
        row = _make_config_row(value=None)
        mock_db.execute.return_value = _make_execute_result(scalars_first=row)

        resp = await client.get("/api/admin-ui/week-override")
        assert resp.status_code == 200
        body = resp.json()
        assert body["override_active"] is False

    @pytest.mark.asyncio
    async def test_active_override_returns_season_and_week(self, admin_client):
        """Row with value '2025:14' must return override_active=True, season=2025, week=14."""
        client, mock_db = admin_client
        row = _make_config_row(value="2025:14")
        mock_db.execute.return_value = _make_execute_result(scalars_first=row)

        resp = await client.get("/api/admin-ui/week-override")
        assert resp.status_code == 200
        body = resp.json()
        assert body["override_active"] is True
        assert body["season"] == 2025
        assert body["week"] == 14

    @pytest.mark.asyncio
    async def test_malformed_value_falls_back_to_inactive(self, admin_client):
        """Malformed value in system_config must not crash — returns inactive."""
        client, mock_db = admin_client
        row = _make_config_row(value="not-valid")
        mock_db.execute.return_value = _make_execute_result(scalars_first=row)

        resp = await client.get("/api/admin-ui/week-override")
        assert resp.status_code == 200
        body = resp.json()
        assert body["override_active"] is False

    @pytest.mark.asyncio
    async def test_response_shape(self, admin_client):
        """Response must always include override_active, season, week keys."""
        client, mock_db = admin_client
        mock_db.execute.return_value = _make_execute_result(scalars_first=None)

        resp = await client.get("/api/admin-ui/week-override")
        assert resp.status_code == 200
        body = resp.json()
        assert {"override_active", "season", "week"} <= body.keys()


# ---------------------------------------------------------------------------
# TestWeekOverridePost
# ---------------------------------------------------------------------------

class TestWeekOverridePost:

    @pytest.mark.asyncio
    async def test_set_override_returns_active(self, admin_client):
        """POST with valid season/week must return override_active=True with echoed values."""
        client, mock_db = admin_client
        mock_db.execute.return_value = _make_execute_result()

        resp = await client.post(
            "/api/admin-ui/week-override", json={"season": 2025, "week": 14}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["override_active"] is True
        assert body["season"] == 2025
        assert body["week"] == 14

    @pytest.mark.asyncio
    async def test_rejects_season_below_2020(self, admin_client):
        client, _ = admin_client
        resp = await client.post(
            "/api/admin-ui/week-override", json={"season": 2019, "week": 1}
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_rejects_season_above_2035(self, admin_client):
        client, _ = admin_client
        resp = await client.post(
            "/api/admin-ui/week-override", json={"season": 2036, "week": 1}
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_rejects_week_zero(self, admin_client):
        client, _ = admin_client
        resp = await client.post(
            "/api/admin-ui/week-override", json={"season": 2025, "week": 0}
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_rejects_week_above_22(self, admin_client):
        client, _ = admin_client
        resp = await client.post(
            "/api/admin-ui/week-override", json={"season": 2025, "week": 23}
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_body_returns_422(self, admin_client):
        client, _ = admin_client
        resp = await client.post("/api/admin-ui/week-override")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# TestWeekOverrideDelete
# ---------------------------------------------------------------------------

class TestWeekOverrideDelete:

    @pytest.mark.asyncio
    async def test_clear_returns_inactive(self, admin_client):
        """DELETE must return override_active=False with null season/week."""
        client, mock_db = admin_client
        mock_db.execute.return_value = _make_execute_result()

        resp = await client.delete("/api/admin-ui/week-override")
        assert resp.status_code == 200
        body = resp.json()
        assert body["override_active"] is False
        assert body["season"] is None
        assert body["week"] is None


# ---------------------------------------------------------------------------
# TestPipelineAuth
# ---------------------------------------------------------------------------

class TestPipelineAuth:
    """Auth guard tests for pipeline endpoints — one representative per auth scenario."""

    @pytest.mark.asyncio
    async def test_roster_no_auth_returns_401(self, no_auth_client):
        resp = await no_auth_client.post("/api/admin-ui/pipeline/roster")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_roster_non_admin_returns_403(self, non_admin_client):
        resp = await non_admin_client.post("/api/admin-ui/pipeline/roster")
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_features_no_auth_returns_401(self, no_auth_client):
        resp = await no_auth_client.post("/api/admin-ui/pipeline/features/2025/14")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_predictions_non_admin_returns_403(self, non_admin_client):
        resp = await non_admin_client.post("/api/admin-ui/pipeline/predictions/2025/14")
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# TestPipelinePathValidation
# ---------------------------------------------------------------------------

class TestPipelinePathValidation:

    @pytest.mark.asyncio
    async def test_features_rejects_season_below_2020(self, admin_client):
        client, _ = admin_client
        resp = await client.post("/api/admin-ui/pipeline/features/2019/14")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_features_rejects_week_above_18(self, admin_client):
        client, _ = admin_client
        resp = await client.post("/api/admin-ui/pipeline/features/2025/19")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_features_rejects_week_zero(self, admin_client):
        client, _ = admin_client
        resp = await client.post("/api/admin-ui/pipeline/features/2025/0")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_schedule_rejects_season_above_2035(self, admin_client):
        client, _ = admin_client
        resp = await client.post("/api/admin-ui/pipeline/schedule/2036")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# TestPipelineResponseShape — DB-only actions (no Tank01 patching needed)
# ---------------------------------------------------------------------------

class TestPipelineDBOnlyResponseShape:

    @pytest.mark.asyncio
    async def test_features_returns_sync_response(self, admin_client):
        """Compute Features must return a valid SyncResponse."""
        client, _ = admin_client
        result = _make_sync_result(n_written=5, events=["computed 5 rows"])
        with patch(
            "app.api.admin_users.FeatureComputeService"
        ) as mock_svc:
            mock_svc.return_value.run = AsyncMock(return_value=result)
            resp = await client.post("/api/admin-ui/pipeline/features/2025/14")

        assert resp.status_code == 200
        body = resp.json()
        assert {"status", "n_written", "n_updated", "n_skipped", "n_failed", "events"} <= body.keys()
        assert body["n_written"] == 5
        assert body["events"] == ["computed 5 rows"]

    @pytest.mark.asyncio
    async def test_predictions_returns_sync_response(self, admin_client):
        """Run Predictions must return a valid SyncResponse."""
        client, _ = admin_client
        result = _make_sync_result(n_written=12)
        with patch(
            "app.api.admin_users.InferenceService"
        ) as mock_svc:
            mock_svc.return_value.run = AsyncMock(return_value=result)
            resp = await client.post("/api/admin-ui/pipeline/predictions/2025/14")

        assert resp.status_code == 200
        body = resp.json()
        assert body["n_written"] == 12
        assert body["status"] == "completed"

    @pytest.mark.asyncio
    async def test_status_is_partial_when_some_failed(self, admin_client):
        """status='partial' when n_failed > 0 but some rows succeeded."""
        client, _ = admin_client
        result = _make_sync_result(n_written=3, n_failed=2)
        with patch(
            "app.api.admin_users.FeatureComputeService"
        ) as mock_svc:
            mock_svc.return_value.run = AsyncMock(return_value=result)
            resp = await client.post("/api/admin-ui/pipeline/features/2025/14")

        assert resp.status_code == 200
        assert resp.json()["status"] == "partial"

    @pytest.mark.asyncio
    async def test_status_is_failed_when_all_failed(self, admin_client):
        """status='failed' when n_failed > 0 and nothing succeeded."""
        client, _ = admin_client
        result = _make_sync_result(n_written=0, n_updated=0, n_failed=5)
        with patch(
            "app.api.admin_users.InferenceService"
        ) as mock_svc:
            mock_svc.return_value.run = AsyncMock(return_value=result)
            resp = await client.post("/api/admin-ui/pipeline/predictions/2025/1")

        assert resp.status_code == 200
        assert resp.json()["status"] == "failed"


# ---------------------------------------------------------------------------
# TestPipelineResponseShape — External API actions (Tank01Client patched)
# ---------------------------------------------------------------------------

class TestPipelineExternalResponseShape:

    def _tank01_ctx(self):
        """Returns an async context manager mock for Tank01Client."""
        tank01 = MagicMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=tank01)
        ctx.__aexit__ = AsyncMock(return_value=False)
        return ctx

    @pytest.mark.asyncio
    async def test_roster_returns_sync_response(self, admin_client):
        client, _ = admin_client
        result = _make_sync_result(n_written=80)
        with (
            patch("app.api.admin_users.Tank01Client", return_value=self._tank01_ctx()),
            patch("app.api.admin_users.RosterSyncService") as mock_svc,
        ):
            mock_svc.return_value.run = AsyncMock(return_value=result)
            resp = await client.post("/api/admin-ui/pipeline/roster")

        assert resp.status_code == 200
        body = resp.json()
        assert {"status", "n_written", "n_updated", "n_skipped", "n_failed", "events"} <= body.keys()
        assert body["n_written"] == 80

    @pytest.mark.asyncio
    async def test_schedule_returns_sync_response(self, admin_client):
        client, _ = admin_client
        result = _make_sync_result(n_written=18)
        with (
            patch("app.api.admin_users.Tank01Client", return_value=self._tank01_ctx()),
            patch("app.api.admin_users.ScheduleSyncService") as mock_svc,
        ):
            mock_svc.return_value.run = AsyncMock(return_value=result)
            resp = await client.post("/api/admin-ui/pipeline/schedule/2025")

        assert resp.status_code == 200
        assert resp.json()["n_written"] == 18

    @pytest.mark.asyncio
    async def test_gamelogs_returns_sync_response(self, admin_client):
        client, _ = admin_client
        result = _make_sync_result(n_written=30, n_updated=5)
        with (
            patch("app.api.admin_users.Tank01Client", return_value=self._tank01_ctx()),
            patch("app.api.admin_users.GameLogIngestService") as mock_svc,
        ):
            mock_svc.return_value.run = AsyncMock(return_value=result)
            resp = await client.post("/api/admin-ui/pipeline/gamelogs/2025/14")

        assert resp.status_code == 200
        body = resp.json()
        assert body["n_written"] == 30
        assert body["n_updated"] == 5

    @pytest.mark.asyncio
    async def test_odds_returns_sync_response(self, admin_client):
        client, _ = admin_client
        result = _make_sync_result(n_written=25)
        with (
            patch("app.api.admin_users.Tank01Client", return_value=self._tank01_ctx()),
            patch("app.api.admin_users.OddsSyncService") as mock_svc,
        ):
            mock_svc.return_value.run = AsyncMock(return_value=result)
            resp = await client.post("/api/admin-ui/pipeline/odds/2025/14")

        assert resp.status_code == 200
        assert resp.json()["n_written"] == 25
