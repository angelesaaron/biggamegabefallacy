"""
FastAPI dependency functions for authentication and authorization.

Dependency hierarchy:

    get_optional_user   — extracts + validates Bearer token; returns User | None
         └── require_auth      — enforces authentication; raises 401 if absent
                  └── require_subscriber  — active subscribers only; raises 403 otherwise

Usage:

    # Optional auth — used for content gating (endpoint returns different shapes)
    async def view(user: Optional[User] = Depends(get_optional_user)): ...

    # Hard gate — endpoint is subscriber-only
    async def pro_view(user: User = Depends(require_subscriber)): ...
"""

import uuid

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.auth_service import decode_access_token


# ---------------------------------------------------------------------------
# Optional auth — never raises; used for content-gating logic
# ---------------------------------------------------------------------------

async def get_optional_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """
    Extract a User from the Authorization: Bearer <token> header.

    Returns None (without raising) when:
      - The header is absent or malformed
      - The JWT is expired, invalid, or signed with the wrong key
      - The sub claim does not correspond to an active user in the DB
    """
    if authorization is None:
        return None

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    claims = decode_access_token(parts[1])
    if claims is None:
        return None

    user_id: str | None = claims.get("sub")
    if not user_id:
        return None

    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        return None

    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalars().first()

    if user is None or not user.is_active:
        return None

    return user


# ---------------------------------------------------------------------------
# Required auth — raises 401 when no valid token is present
# ---------------------------------------------------------------------------

async def require_auth(
    user: User | None = Depends(get_optional_user),
) -> User:
    """Raise HTTP 401 if the request carries no valid access token."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


# ---------------------------------------------------------------------------
# Subscriber gate
# ---------------------------------------------------------------------------

async def require_subscriber(user: User = Depends(require_auth)) -> User:
    """
    Allow only active subscribers.
    Raises HTTP 403 for authenticated non-subscriber users.
    Raises HTTP 401 (via require_auth) for unauthenticated requests.
    """
    if not user.is_subscriber:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active subscription required.",
        )
    return user
