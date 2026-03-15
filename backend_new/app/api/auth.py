"""
Auth router — registration, login, token refresh, /me, and logout.

Mounted at /api by main.py (prefix=""), so all paths below resolve as:
  POST /api/auth/register
  POST /api/auth/login
  POST /api/auth/refresh
  GET  /api/auth/me
  POST /api/auth/logout

Refresh token flow:
  1. /login or /register: issue access token (short-lived JWT) + set httpOnly
     refresh-token cookie (single-use UUID4 hex; SHA-256 hash stored in DB).
  2. /refresh: read cookie, compare SHA-256 against DB, issue new pair, rotate
     DB hash atomically.  Cookie is cleared first so a double-submission
     cannot reuse the old token.
  3. /logout: clear cookie + null out DB hash.

Security notes:
  - Login always returns the same 401 message regardless of whether the email
    exists or the password is wrong — no user-enumeration oracle.
  - hashed_password and last_refresh_token are never included in any response.
  - Email is normalised to lowercase before any store or comparison.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_optional_user, require_auth
from app.config import settings
from app.database import get_db
from app.limiter import limiter
from app.models.user import User
from app.services import account_service
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    create_user,
    get_user_by_email,
    hash_token,
)
from app.services.email_service import email_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

# ---------------------------------------------------------------------------
# Cookie configuration
# ---------------------------------------------------------------------------

_REFRESH_COOKIE_NAME = "refresh_token"
_REFRESH_COOKIE_PATH = "/api/auth/refresh"
_REFRESH_COOKIE_MAX_AGE = 7 * 24 * 3600  # 7 days in seconds


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    # secure=False in DEBUG mode so the httpOnly cookie works over plain HTTP (localhost).
    # Always True in production — Render enforces TLS.
    response.set_cookie(
        key=_REFRESH_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=_REFRESH_COOKIE_MAX_AGE,
        path=_REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=_REFRESH_COOKIE_NAME,
        path=_REFRESH_COOKIE_PATH,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
    )


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    id: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    is_subscriber: bool
    is_active: bool
    member_since: str  # ISO date string, e.g. "2025-01-14"


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)


# ---------------------------------------------------------------------------
# Helper: issue tokens, persist hash, set cookie
# ---------------------------------------------------------------------------

async def _issue_tokens(
    user: User,
    response: Response,
    db: AsyncSession,
) -> TokenResponse:
    """Mint access + refresh tokens, persist the refresh hash, set cookie."""
    access_token = create_access_token(user)
    raw_refresh, refresh_hash = create_refresh_token()

    user.last_refresh_token = refresh_hash
    db.add(user)
    await db.flush()
    await db.commit()
    await db.refresh(user)

    _set_refresh_cookie(response, raw_refresh)
    return TokenResponse(access_token=access_token)


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------

@router.post(
    "/auth/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new account",
)
@limiter.limit("5/minute")
async def register(
    request: Request,
    body: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Create a new free-tier account and return a token pair.

    Returns 409 Conflict if the email is already registered.
    Returns 422 Unprocessable Entity if the password is shorter than 8 chars.
    """
    try:
        user = await create_user(
            email=body.email,
            password=body.password,
            db=db,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        )

    logger.info("New user registered: %s", user.id)
    return await _issue_tokens(user, response, db)


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------

@router.post(
    "/auth/login",
    response_model=TokenResponse,
    summary="Authenticate and receive tokens",
)
@limiter.limit("5/minute")
async def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Accepts OAuth2 password-grant form fields (username + password).

    Returns 401 for any credential failure — intentionally the same message
    whether the email does not exist or the password is wrong.
    """
    user = await authenticate_user(
        email=form_data.username,
        password=form_data.password,
        db=db,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await _issue_tokens(user, response, db)


# ---------------------------------------------------------------------------
# POST /auth/refresh
# ---------------------------------------------------------------------------

@router.post(
    "/auth/refresh",
    response_model=TokenResponse,
    summary="Rotate refresh token and issue new access token",
)
async def refresh_tokens(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=_REFRESH_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Single-use refresh token rotation.

    Reads the httpOnly cookie, validates the SHA-256 hash against the DB,
    clears the old cookie immediately, issues a new token pair and persists
    the new hash.  A replayed cookie is rejected because the DB hash has
    already been rotated.
    """
    _invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not refresh_token:
        raise _invalid

    incoming_hash = hash_token(refresh_token)

    # Find the user whose stored hash matches
    from sqlalchemy import select as _select
    result = await db.execute(
        _select(User).where(User.last_refresh_token == incoming_hash)
    )
    user = result.scalars().first()

    if user is None or not user.is_active:
        # Clear any stale cookie to prevent the client from looping
        _clear_refresh_cookie(response)
        raise _invalid

    # Invalidate old cookie before issuing new pair (defence-in-depth)
    _clear_refresh_cookie(response)
    return await _issue_tokens(user, response, db)


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------

@router.get(
    "/auth/me",
    response_model=MeResponse,
    summary="Return the currently authenticated user",
)
async def me(
    current_user: User = Depends(require_auth),
) -> MeResponse:
    """
    Requires a valid Bearer access token in the Authorization header.

    Returns 401 when the token is absent, malformed, or expired.
    Never returns hashed_password or last_refresh_token.
    """
    return MeResponse(
        id=str(current_user.id),
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        is_subscriber=current_user.is_subscriber,
        is_active=current_user.is_active,
        member_since=current_user.created_at.date().isoformat(),
    )


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------

@router.post(
    "/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Invalidate the current refresh token and clear the cookie",
)
async def logout(
    response: Response,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Clears the refresh cookie and nulls out last_refresh_token in the DB.

    Accepts unauthenticated requests gracefully (idempotent) so the client
    can always call logout without worrying about whether the token is valid.
    """
    _clear_refresh_cookie(response)

    if current_user is not None:
        current_user.last_refresh_token = None
        db.add(current_user)
        await db.commit()


# ---------------------------------------------------------------------------
# POST /auth/forgot-password
# ---------------------------------------------------------------------------

@router.post(
    "/auth/forgot-password",
    summary="Request a password-reset email",
)
@limiter.limit("5/minute")
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Send a password-reset link to the given email address if it is registered.

    Always returns 200 with the same message regardless of whether the email
    exists — never reveals user-enumeration information.

    Rate-limited to 5 requests per minute per IP.
    """
    await account_service.initiate_password_reset(str(body.email), db, email_service)
    return {"detail": "If that email is registered, you'll receive a reset link shortly."}


# ---------------------------------------------------------------------------
# POST /auth/reset-password
# ---------------------------------------------------------------------------

@router.post(
    "/auth/reset-password",
    summary="Complete a password reset using a one-time token",
)
@limiter.limit("5/minute")
async def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Consume the one-time reset token from the reset link and set a new password.

    On success, all existing refresh tokens are invalidated.

    Returns 400 if the token is invalid, expired, or already used, or if the
    new password is shorter than 8 characters.

    Rate-limited to 5 requests per minute per IP.
    """
    try:
        await account_service.confirm_password_reset(body.token, body.new_password, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"detail": "Password reset successfully."}
