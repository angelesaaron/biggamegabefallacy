"""
Integration tests for the admin API router.

Services and Tank01Client are mocked — no real DB or external API calls.
Tests cover: auth enforcement, response schema, and success/failure status mapping.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.sync_result import SyncResult
from tests.conftest import ADMIN_HEADERS, ADMIN_KEY

# All admin tests share the admin_client fixture (DB mocked, ADMIN_KEY set).


# ── Auth enforcement ──────────────────────────────────────────────────────────

class TestRequireAdmin:
    async def test_no_header_returns_403(self, admin_client):
        resp = await admin_client.post("/admin/sync/roster")
        assert resp.status_code == 403

    async def test_wrong_key_returns_403(self, admin_client):
        resp = await admin_client.post("/admin/sync/roster", headers={"X-Admin-Key": "wrong"})
        assert resp.status_code == 403

    async def test_correct_key_passes_auth(self, admin_client):
        with patch("app.api.admin.Tank01Client") as MockClient, \
             patch("app.api.admin.RosterSyncService") as MockSvc:
            _setup_tank01_ctx(MockClient)
            MockSvc.return_value.run = AsyncMock(return_value=SyncResult())
            resp = await admin_client.post("/admin/sync/roster", headers=ADMIN_HEADERS)
        assert resp.status_code == 200

    async def test_unconfigured_admin_key_returns_503(self, admin_client):
        with patch("app.api.admin.settings") as mock_settings:
            mock_settings.ADMIN_KEY = ""
            resp = await admin_client.post("/admin/sync/roster", headers=ADMIN_HEADERS)
        assert resp.status_code == 503


# ── SyncResponse shape ────────────────────────────────────────────────────────

class TestSyncResponseSchema:
    async def test_response_has_all_fields(self, admin_client):
        with patch("app.api.admin.Tank01Client") as MockClient, \
             patch("app.api.admin.RosterSyncService") as MockSvc:
            _setup_tank01_ctx(MockClient)
            MockSvc.return_value.run = AsyncMock(
                return_value=SyncResult(n_written=3, n_updated=1, n_skipped=2, n_failed=0, events=["ok"])
            )
            resp = await admin_client.post("/admin/sync/roster", headers=ADMIN_HEADERS)

        assert resp.status_code == 200
        body = resp.json()
        for field in ("status", "n_written", "n_updated", "n_skipped", "n_failed", "events"):
            assert field in body

    async def test_status_completed_when_no_failures(self, admin_client):
        with patch("app.api.admin.Tank01Client") as MockClient, \
             patch("app.api.admin.RosterSyncService") as MockSvc:
            _setup_tank01_ctx(MockClient)
            MockSvc.return_value.run = AsyncMock(return_value=SyncResult(n_written=5))
            resp = await admin_client.post("/admin/sync/roster", headers=ADMIN_HEADERS)

        assert resp.json()["status"] == "completed"

    async def test_status_partial_on_mixed_results(self, admin_client):
        with patch("app.api.admin.Tank01Client") as MockClient, \
             patch("app.api.admin.RosterSyncService") as MockSvc:
            _setup_tank01_ctx(MockClient)
            MockSvc.return_value.run = AsyncMock(
                return_value=SyncResult(n_written=3, n_failed=2)
            )
            resp = await admin_client.post("/admin/sync/roster", headers=ADMIN_HEADERS)

        assert resp.json()["status"] == "partial"

    async def test_status_failed_when_all_fail(self, admin_client):
        with patch("app.api.admin.Tank01Client") as MockClient, \
             patch("app.api.admin.RosterSyncService") as MockSvc:
            _setup_tank01_ctx(MockClient)
            MockSvc.return_value.run = AsyncMock(return_value=SyncResult(n_failed=5))
            resp = await admin_client.post("/admin/sync/roster", headers=ADMIN_HEADERS)

        assert resp.json()["status"] == "failed"


# ── Roster sync ───────────────────────────────────────────────────────────────

class TestSyncRoster:
    async def test_success(self, admin_client):
        with patch("app.api.admin.Tank01Client") as MockClient, \
             patch("app.api.admin.RosterSyncService") as MockSvc:
            _setup_tank01_ctx(MockClient)
            MockSvc.return_value.run = AsyncMock(return_value=SyncResult(n_written=45))
            resp = await admin_client.post("/admin/sync/roster", headers=ADMIN_HEADERS)

        assert resp.status_code == 200
        assert resp.json()["n_written"] == 45


# ── Draft sync ────────────────────────────────────────────────────────────────

class TestSyncDraft:
    async def test_success_default_force(self, admin_client):
        with patch("app.api.admin.DraftSyncService") as MockSvc:
            MockSvc.return_value.run = AsyncMock(return_value=SyncResult(n_updated=30))
            resp = await admin_client.post("/admin/sync/draft", headers=ADMIN_HEADERS)

        assert resp.status_code == 200
        assert resp.json()["n_updated"] == 30
        MockSvc.return_value.run.assert_awaited_once_with(force_update=False)

    async def test_force_update_param_passed(self, admin_client):
        with patch("app.api.admin.DraftSyncService") as MockSvc:
            MockSvc.return_value.run = AsyncMock(return_value=SyncResult(n_updated=50))
            await admin_client.post(
                "/admin/sync/draft?force_update=true", headers=ADMIN_HEADERS
            )
        MockSvc.return_value.run.assert_awaited_once_with(force_update=True)


# ── Schedule sync ─────────────────────────────────────────────────────────────

class TestSyncSchedule:
    async def test_success(self, admin_client):
        with patch("app.api.admin.Tank01Client") as MockClient, \
             patch("app.api.admin.ScheduleSyncService") as MockSvc:
            _setup_tank01_ctx(MockClient)
            MockSvc.return_value.run = AsyncMock(return_value=SyncResult(n_written=18))
            resp = await admin_client.post("/admin/sync/schedule/2025", headers=ADMIN_HEADERS)

        assert resp.status_code == 200
        assert resp.json()["n_written"] == 18

    async def test_season_below_range_rejected(self, admin_client):
        resp = await admin_client.post("/admin/sync/schedule/2019", headers=ADMIN_HEADERS)
        assert resp.status_code == 422

    async def test_season_above_range_rejected(self, admin_client):
        resp = await admin_client.post("/admin/sync/schedule/2036", headers=ADMIN_HEADERS)
        assert resp.status_code == 422


# ── Game log ingest ───────────────────────────────────────────────────────────

class TestIngestGameLogs:
    async def test_success(self, admin_client):
        with patch("app.api.admin.Tank01Client") as MockClient, \
             patch("app.api.admin.GameLogIngestService") as MockSvc:
            _setup_tank01_ctx(MockClient)
            MockSvc.return_value.run = AsyncMock(
                return_value=SyncResult(n_written=120, n_updated=5)
            )
            resp = await admin_client.post(
                "/admin/ingest/gamelogs/2025/7", headers=ADMIN_HEADERS
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["n_written"] == 120
        assert body["n_updated"] == 5

    async def test_week_out_of_range_rejected(self, admin_client):
        resp = await admin_client.post(
            "/admin/ingest/gamelogs/2025/19", headers=ADMIN_HEADERS
        )
        assert resp.status_code == 422

    async def test_week_zero_rejected(self, admin_client):
        resp = await admin_client.post(
            "/admin/ingest/gamelogs/2025/0", headers=ADMIN_HEADERS
        )
        assert resp.status_code == 422


# ── Odds sync ─────────────────────────────────────────────────────────────────

class TestSyncOdds:
    async def test_success(self, admin_client):
        with patch("app.api.admin.Tank01Client") as MockClient, \
             patch("app.api.admin.OddsSyncService") as MockSvc:
            _setup_tank01_ctx(MockClient)
            MockSvc.return_value.run = AsyncMock(return_value=SyncResult(n_written=60))
            resp = await admin_client.post(
                "/admin/sync/odds/2025/7", headers=ADMIN_HEADERS
            )

        assert resp.status_code == 200
        assert resp.json()["n_written"] == 60


# ── Seeds ─────────────────────────────────────────────────────────────────────

class TestSeedRookieBuckets:
    async def test_success(self, admin_client):
        with patch("app.api.admin.RookieBucketSeedService") as MockSvc:
            MockSvc.return_value.run = AsyncMock(return_value=SyncResult(n_written=15))
            resp = await admin_client.post("/admin/seed/rookie-buckets", headers=ADMIN_HEADERS)

        assert resp.status_code == 200
        assert resp.json()["n_written"] == 15


class TestSeedAliases:
    async def test_success(self, admin_client):
        with patch("app.api.admin.AliasSeedService") as MockSvc:
            MockSvc.return_value.run = AsyncMock(return_value=SyncResult(n_written=9))
            resp = await admin_client.post("/admin/aliases/seed", headers=ADMIN_HEADERS)

        assert resp.status_code == 200
        assert resp.json()["n_written"] == 9


# ── Feature computation ───────────────────────────────────────────────────────

class TestComputeFeatures:
    async def test_success(self, admin_client):
        with patch("app.api.admin.FeatureComputeService") as MockSvc:
            MockSvc.return_value.run = AsyncMock(
                return_value=SyncResult(n_written=180, n_skipped=5)
            )
            resp = await admin_client.post(
                "/admin/compute/features/2025/7", headers=ADMIN_HEADERS
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["n_written"] == 180
        assert body["n_skipped"] == 5

    async def test_season_and_week_passed_to_service(self, admin_client):
        with patch("app.api.admin.FeatureComputeService") as MockSvc:
            MockSvc.return_value.run = AsyncMock(return_value=SyncResult())
            await admin_client.post(
                "/admin/compute/features/2024/12", headers=ADMIN_HEADERS
            )
        MockSvc.return_value.run.assert_awaited_once_with(2024, 12)


class TestComputeSeasonState:
    async def test_success(self, admin_client):
        with patch("app.api.admin.SeasonStateService") as MockSvc:
            MockSvc.return_value.run = AsyncMock(return_value=SyncResult(n_written=200))
            resp = await admin_client.post(
                "/admin/compute/season-state/2025", headers=ADMIN_HEADERS
            )

        assert resp.status_code == 200
        assert resp.json()["n_written"] == 200

    async def test_season_passed_to_service(self, admin_client):
        with patch("app.api.admin.SeasonStateService") as MockSvc:
            MockSvc.return_value.run = AsyncMock(return_value=SyncResult())
            await admin_client.post(
                "/admin/compute/season-state/2024", headers=ADMIN_HEADERS
            )
        MockSvc.return_value.run.assert_awaited_once_with(2024)


# ── Inference ─────────────────────────────────────────────────────────────────

class TestRunPredictions:
    async def test_success(self, admin_client):
        with patch("app.api.admin.InferenceService") as MockSvc:
            MockSvc.return_value.run = AsyncMock(
                return_value=SyncResult(n_written=175, events=["week_scalar=1.0000 calibration=beta n_players=175 snap_nan=8"])
            )
            resp = await admin_client.post(
                "/admin/run/predictions/2025/7", headers=ADMIN_HEADERS
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["n_written"] == 175
        assert len(body["events"]) == 1

    async def test_season_week_passed_to_service(self, admin_client):
        with patch("app.api.admin.InferenceService") as MockSvc:
            MockSvc.return_value.run = AsyncMock(return_value=SyncResult())
            await admin_client.post(
                "/admin/run/predictions/2025/3", headers=ADMIN_HEADERS
            )
        MockSvc.return_value.run.assert_awaited_once_with(2025, 3)


# ── Unresolved aliases ────────────────────────────────────────────────────────

class TestListUnresolvedAliases:
    async def test_returns_empty_list_when_none(self, admin_client, mock_db):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        resp = await admin_client.get(
            "/admin/aliases/unresolved?season=2025", headers=ADMIN_HEADERS
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 0
        assert body["events"] == []

    async def test_returns_events_when_present(self, admin_client, mock_db):
        from types import SimpleNamespace
        from datetime import datetime

        event = SimpleNamespace(
            id=1,
            week=7,
            detail="nflverse_snap name unresolved: 'Gabe Davis'",
            created_at=datetime(2025, 11, 7, 12, 0, 0),
            resolved_at=None,
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [event]
        mock_db.execute = AsyncMock(return_value=mock_result)

        resp = await admin_client.get(
            "/admin/aliases/unresolved?season=2025", headers=ADMIN_HEADERS
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        assert body["events"][0]["id"] == 1
        assert body["events"][0]["week"] == 7

    async def test_week_filter_passed(self, admin_client, mock_db):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        resp = await admin_client.get(
            "/admin/aliases/unresolved?season=2025&week=7", headers=ADMIN_HEADERS
        )
        assert resp.status_code == 200


# ── Helpers ───────────────────────────────────────────────────────────────────

def _setup_tank01_ctx(mock_client_cls) -> None:
    """Configure a Tank01Client mock to work as an async context manager."""
    mock_instance = AsyncMock()
    mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)
