"""
Users router — authenticated account-management endpoints.

Mounted at /api by main.py, so all paths resolve as:
  PATCH  /api/users/me
  PATCH  /api/users/me/email
  POST   /api/users/me/verify-email
  POST   /api/users/me/password
  POST   /api/users/me/cancel

All routes require a valid Bearer access token (require_auth dependency).
Email-initiating routes (PATCH /me/email) are rate-limited to 3/minute.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import MeResponse
from app.api.deps import require_auth
from app.database import get_db
from app.limiter import limiter
from app.models.user import User
from app.services import account_service
from app.services.auth_service import create_access_token
from app.services.email_service import email_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["users"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class UpdateNameRequest(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)


class UpdateEmailRequest(BaseModel):
    new_email: EmailStr


class VerifyEmailRequest(BaseModel):
    token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class VerifyEmailResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: MeResponse


# ---------------------------------------------------------------------------
# Helper: build MeResponse from a User ORM object
# ---------------------------------------------------------------------------

def _me(user: User) -> MeResponse:
    return MeResponse(
        id=str(user.id),
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        is_subscriber=user.is_subscriber,
        is_active=user.is_active,
        member_since=user.created_at.date().isoformat(),
    )


# ---------------------------------------------------------------------------
# PATCH /users/me — update display name
# ---------------------------------------------------------------------------

@router.patch(
    "/users/me",
    response_model=MeResponse,
    summary="Update the authenticated user's display name",
)
async def update_name(
    body: UpdateNameRequest,
    current_user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    """
    Update first_name and last_name on the current user's account.

    Returns the updated user profile.
    """
    try:
        updated = await account_service.update_name(
            current_user, body.first_name, body.last_name, db
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _me(updated)


# ---------------------------------------------------------------------------
# PATCH /users/me/email — initiate email change
# ---------------------------------------------------------------------------

@router.patch(
    "/users/me/email",
    summary="Begin an email-change flow — sends a verification link to the new address",
)
@limiter.limit("3/minute")
async def initiate_email_change(
    request: Request,
    body: UpdateEmailRequest,
    current_user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Sends a verification email to the new address.

    The email address is NOT changed until the user follows the link and calls
    POST /users/me/verify-email with the token.

    Rate-limited to 3 requests per minute per IP.
    """
    try:
        await account_service.initiate_email_change(
            current_user, str(body.new_email), db, email_service
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"detail": "Verification email sent to your new address."}


# ---------------------------------------------------------------------------
# POST /users/me/verify-email — confirm email change
# ---------------------------------------------------------------------------

@router.post(
    "/users/me/verify-email",
    response_model=VerifyEmailResponse,
    summary="Complete an email-change flow and receive a fresh access token",
)
async def verify_email(
    body: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
) -> VerifyEmailResponse:
    """
    Consumes the one-time token from the verification link, updates the user's
    email address, and issues a new access token reflecting the updated email.

    Returns 400 if the token is missing, expired, or already used.
    Returns 409 if the new email was claimed by another account in the interim.
    """
    try:
        updated_user = await account_service.confirm_email_change(body.token, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    new_access_token = create_access_token(updated_user)
    return VerifyEmailResponse(
        access_token=new_access_token,
        user=_me(updated_user),
    )


# ---------------------------------------------------------------------------
# POST /users/me/password — change password (authenticated)
# ---------------------------------------------------------------------------

@router.post(
    "/users/me/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change the authenticated user's password",
)
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Changes the password for the currently authenticated user.

    Requires the current password for verification. On success, all existing
    refresh tokens are invalidated (other sessions are logged out).

    Returns 204 No Content on success.
    Returns 400 if the current password is incorrect or the new password is too short.
    """
    try:
        await account_service.change_password(
            current_user, body.current_password, body.new_password, db
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ---------------------------------------------------------------------------
# POST /users/me/cancel — cancel subscription
# ---------------------------------------------------------------------------

@router.post(
    "/users/me/cancel",
    response_model=MeResponse,
    summary="Cancel the authenticated user's subscription",
)
async def cancel_subscription(
    current_user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    """
    Marks the current user as no longer a subscriber.

    Note: This endpoint does not interact with Stripe — callers must handle
    Stripe-side cancellation separately before invoking this endpoint.

    Returns the updated user profile.
    """
    try:
        updated = await account_service.cancel_subscription(current_user, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return _me(updated)
