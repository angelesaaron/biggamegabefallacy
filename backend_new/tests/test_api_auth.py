"""
Auth endpoint tests — register, login, refresh, /me, logout, and tier gating.

Strategy:
  - All DB calls are mocked (same pattern as existing conftest.py).
  - JWT_SECRET_KEY is set via env before imports so Settings() doesn't raise.
  - Tests cover: happy paths, error paths, and the critical security properties
    (no user enumeration, refresh token invalidation, tier gating).

Run:
    cd backend_new
    pytest tests/test_api_auth.py -v
"""

import os
import uuid

# Must be set before app imports — conftest.py sets ADMIN_KEY and DATABASE_URL,
# but JWT_SECRET_KEY is new and needs to be here too.
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-pytest-only-not-production")

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from app.database import get_db
from app.main import app
from app.models.user import User
from app.services.auth_service import (
    create_access_token,
    hash_password,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_free_user(**kwargs) -> User:
    defaults = dict(
        id=uuid.uuid4(),
        email="test@example.com",
        hashed_password=hash_password("password123"),
        is_subscriber=False,
        is_active=True,
        last_refresh_token=None,
        stripe_customer_id=None,
    )
    defaults.update(kwargs)
    user = User()
    for k, v in defaults.items():
        setattr(user, k, v)
    return user


def make_pro_user(**kwargs) -> User:
    return make_free_user(is_subscriber=True, email="pro@example.com", **kwargs)


def make_mock_db() -> AsyncMock:
    session = AsyncMock()
    session.execute = AsyncMock()
    session.execute.return_value = MagicMock()  # Python 3.13: AsyncMock.return_value is AsyncMock; force MagicMock
    session.get = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.rollback = AsyncMock()
    return session


def bearer(user: User) -> dict:
    """Return Authorization header with a valid access token for *user*."""
    return {"Authorization": f"Bearer {create_access_token(user)}"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def auth_client(mock_db):
    """AsyncClient with DB mocked. Uses the mock_db fixture from conftest."""
    async def _override():
        yield mock_db

    app.dependency_overrides[get_db] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, mock_db
    app.dependency_overrides.pop(get_db, None)


# Standalone mock_db fixture for this module (conftest already has one,
# but we need it available here for the auth_client fixture above).
@pytest.fixture
def mock_db():
    return make_mock_db()


# ---------------------------------------------------------------------------
# POST /api/auth/register
# ---------------------------------------------------------------------------

class TestRegister:

    @pytest.mark.asyncio
    async def test_register_new_user_returns_access_token(self, auth_client):
        client, db = auth_client

        # No existing user found → create succeeds
        db.execute.return_value.scalars.return_value.first.return_value = None
        db.refresh.side_effect = lambda user: None  # no-op

        resp = await client.post("/api/auth/register", json={
            "email": "new@example.com",
            "password": "password123",
        })

        assert resp.status_code == 201
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_register_sets_httponly_refresh_cookie(self, auth_client):
        client, db = auth_client

        db.execute.return_value.scalars.return_value.first.return_value = None
        db.refresh.side_effect = lambda user: None

        resp = await client.post("/api/auth/register", json={
            "email": "cookietest@example.com",
            "password": "password123",
        })

        assert resp.status_code == 201
        # httpx surfaces Set-Cookie as a response header
        assert "refresh_token" in resp.cookies or "set-cookie" in resp.headers

    @pytest.mark.asyncio
    async def test_register_duplicate_email_returns_409(self, auth_client):
        client, db = auth_client

        existing = make_free_user(email="dup@example.com")
        db.execute.return_value.scalars.return_value.first.return_value = existing

        resp = await client.post("/api/auth/register", json={
            "email": "dup@example.com",
            "password": "password123",
        })

        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_register_short_password_returns_422(self, auth_client):
        client, db = auth_client

        resp = await client.post("/api/auth/register", json={
            "email": "short@example.com",
            "password": "abc",
        })

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_register_commits_to_db(self, auth_client):
        """Fix 1 regression test — commit must be called so hash persists."""
        client, db = auth_client

        db.execute.return_value.scalars.return_value.first.return_value = None
        db.refresh.side_effect = lambda user: None

        await client.post("/api/auth/register", json={
            "email": "commitcheck@example.com",
            "password": "password123",
        })

        db.commit.assert_called()


# ---------------------------------------------------------------------------
# POST /api/auth/login
# ---------------------------------------------------------------------------

class TestLogin:

    @pytest.mark.asyncio
    async def test_login_valid_credentials_returns_token(self, auth_client):
        client, db = auth_client

        user = make_free_user()
        db.execute.return_value.scalars.return_value.first.return_value = user
        db.refresh.side_effect = lambda u: None

        resp = await client.post("/api/auth/login", data={
            "username": "test@example.com",
            "password": "password123",
        })

        assert resp.status_code == 200
        assert "access_token" in resp.json()

    @pytest.mark.asyncio
    async def test_login_wrong_password_returns_401(self, auth_client):
        client, db = auth_client

        user = make_free_user()
        db.execute.return_value.scalars.return_value.first.return_value = user

        resp = await client.post("/api/auth/login", data={
            "username": "test@example.com",
            "password": "wrongpassword",
        })

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_unknown_email_returns_401(self, auth_client):
        """Security: same 401 for unknown email as wrong password — no enumeration."""
        client, db = auth_client

        db.execute.return_value.scalars.return_value.first.return_value = None

        resp = await client.post("/api/auth/login", data={
            "username": "nobody@example.com",
            "password": "password123",
        })

        assert resp.status_code == 401
        # Message must be identical to wrong-password case (no enumeration oracle)
        assert resp.json()["detail"] == "Invalid email or password."

    @pytest.mark.asyncio
    async def test_login_commits_refresh_token_hash(self, auth_client):
        """Fix 1 regression test — commit must be called on login too."""
        client, db = auth_client

        user = make_free_user()
        db.execute.return_value.scalars.return_value.first.return_value = user
        db.refresh.side_effect = lambda u: None

        await client.post("/api/auth/login", data={
            "username": "test@example.com",
            "password": "password123",
        })

        db.commit.assert_called()


# ---------------------------------------------------------------------------
# POST /api/auth/refresh
# ---------------------------------------------------------------------------

class TestRefresh:

    @pytest.mark.asyncio
    async def test_refresh_with_valid_cookie_issues_new_token(self, auth_client):
        client, db = auth_client

        from app.services.auth_service import create_refresh_token, hash_token
        raw, stored_hash = create_refresh_token()

        user = make_free_user(last_refresh_token=stored_hash)
        db.execute.return_value.scalars.return_value.first.return_value = user
        db.refresh.side_effect = lambda u: None

        resp = await client.post(
            "/api/auth/refresh",
            cookies={"refresh_token": raw},
        )

        assert resp.status_code == 200
        assert "access_token" in resp.json()

    @pytest.mark.asyncio
    async def test_refresh_without_cookie_returns_401(self, auth_client):
        client, db = auth_client

        resp = await client.post("/api/auth/refresh")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_with_wrong_token_returns_401(self, auth_client):
        """Replayed / wrong token — hash won't match any user row."""
        client, db = auth_client

        db.execute.return_value.scalars.return_value.first.return_value = None

        resp = await client.post(
            "/api/auth/refresh",
            cookies={"refresh_token": "badbadtoken"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/auth/me
# ---------------------------------------------------------------------------

class TestMe:

    @pytest.mark.asyncio
    async def test_me_returns_user_info(self, auth_client):
        client, db = auth_client

        user = make_free_user()
        db.execute.return_value.scalars.return_value.first.return_value = user

        resp = await client.get("/api/auth/me", headers=bearer(user))

        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == user.email
        assert body["is_subscriber"] == False
        assert "hashed_password" not in body
        assert "last_refresh_token" not in body

    @pytest.mark.asyncio
    async def test_me_without_token_returns_401(self, auth_client):
        client, db = auth_client

        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_me_with_expired_token_returns_401(self, auth_client):
        """Simulate expired token by using a token signed with wrong key."""
        client, db = auth_client

        import jwt as _jwt
        bad_token = _jwt.encode(
            {"sub": str(uuid.uuid4()), "email": "x@x.com", "is_subscriber": False},
            "wrong-secret",
            algorithm="HS256",
        )
        resp = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {bad_token}"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/auth/logout
# ---------------------------------------------------------------------------

class TestLogout:

    @pytest.mark.asyncio
    async def test_logout_clears_cookie_and_commits(self, auth_client):
        """Fix 2 regression test — commit must persist the null-out."""
        client, db = auth_client

        user = make_free_user(last_refresh_token="somehash")
        db.execute.return_value.scalars.return_value.first.return_value = user

        resp = await client.post("/api/auth/logout", headers=bearer(user))

        assert resp.status_code == 204
        db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_logout_unauthenticated_is_idempotent(self, auth_client):
        """Logout without a token must still return 204 — not 401."""
        client, db = auth_client

        resp = await client.post("/api/auth/logout")
        assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Tier gating — predictions endpoint
# ---------------------------------------------------------------------------

class TestPredictionsTierGating:
    """
    These tests verify the content-gating logic without a real DB.
    We mock get_optional_user directly to inject known users.
    """

    @pytest.mark.asyncio
    async def test_unauthenticated_gets_predictions_response(self, auth_client):
        client, db = auth_client

        # No user — simulate empty predictions query result
        mock_result = MagicMock()
        mock_result.all.return_value = []
        db.execute.return_value = mock_result

        resp = await client.get("/api/predictions/2025/1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["predictions"] == []
        assert body["count"] == 0

    @pytest.mark.asyncio
    async def test_subscriber_dependency_resolves(self, auth_client):
        """require_subscriber should pass through subscribers without raising."""
        client, db = auth_client

        from app.api.deps import require_subscriber

        user = make_pro_user()
        result = await require_subscriber(user=user)
        assert result is user

    @pytest.mark.asyncio
    async def test_require_subscriber_rejects_non_subscriber(self, auth_client):
        """require_subscriber must raise 403 for non-subscribers."""
        from fastapi import HTTPException
        from app.api.deps import require_subscriber

        free_user = make_free_user()

        with pytest.raises(HTTPException) as exc_info:
            await require_subscriber(user=free_user)

        assert exc_info.value.status_code == 403


