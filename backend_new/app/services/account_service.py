"""
AccountService — account mutation logic.

All methods operate on an AsyncSession supplied by the caller (FastAPI dep injection).
Password operations delegate to auth_service helpers to avoid reimplementing bcrypt.
"""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.models.user_token import UserToken, TokenType
from app.services.auth_service import verify_password, hash_password, get_user_by_email
from app.services.email_service import EmailService


# ---------------------------------------------------------------------------
# Name update
# ---------------------------------------------------------------------------

async def update_name(
    user: User,
    first_name: str,
    last_name: str,
    db: AsyncSession,
) -> User:
    """
    Update the display name on a user account.

    Raises:
        HTTPException 422: if either name is empty or exceeds 100 characters.
    """
    first_name = first_name.strip()
    last_name = last_name.strip()

    if not first_name or not last_name:
        raise HTTPException(status_code=422, detail="first_name and last_name must not be empty.")
    if len(first_name) > 100 or len(last_name) > 100:
        raise HTTPException(status_code=422, detail="Names must be 100 characters or fewer.")

    user.first_name = first_name
    user.last_name = last_name
    await db.flush()
    await db.commit()
    await db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Password change (authenticated user)
# ---------------------------------------------------------------------------

async def change_password(
    user: User,
    current_password: str,
    new_password: str,
    db: AsyncSession,
) -> None:
    """
    Change password for an already-authenticated user.

    Raises:
        HTTPException 400: if current_password is wrong or new_password < 8 chars.
    """
    if not verify_password(current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters.")

    user.hashed_password = hash_password(new_password)
    # Invalidate all active refresh tokens so other sessions are logged out.
    user.last_refresh_token = None
    await db.commit()


# ---------------------------------------------------------------------------
# Email change — two-step: initiate → confirm
# ---------------------------------------------------------------------------

async def initiate_email_change(
    user: User,
    new_email: str,
    db: AsyncSession,
    email_svc: EmailService,
) -> None:
    """
    Begin an email-change flow. Sends a verification link to *new_email*.

    Raises:
        HTTPException 409: if new_email is already registered to another account.
    """
    normalised = new_email.strip().lower()

    existing = await get_user_by_email(normalised, db)
    if existing is not None and existing.id != user.id:
        raise HTTPException(status_code=409, detail="Email address is already in use.")

    raw, token_hash = UserToken.generate()
    token = UserToken(
        user_id=user.id,
        token_hash=token_hash,
        token_type=TokenType.email_verification,
        new_email=normalised,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(token)
    await db.commit()

    verify_url = f"{settings.FRONTEND_URL}/verify-email?token={raw}"
    await email_svc.send_email_verification(normalised, verify_url)


async def confirm_email_change(raw_token: str, db: AsyncSession) -> User:
    """
    Complete an email-change flow using the raw token from the verification link.

    Raises:
        HTTPException 400: if token is missing, expired, or already used.
        HTTPException 409: if new_email was claimed by another account between
                           initiation and confirmation (race condition guard).
    """
    token_hash = UserToken.hash(raw_token)

    result = await db.execute(
        select(UserToken).where(
            UserToken.token_hash == token_hash,
            UserToken.token_type == TokenType.email_verification,
        )
    )
    token: UserToken | None = result.scalars().first()

    if token is None or not token.is_valid():
        raise HTTPException(status_code=400, detail="Token is invalid or has expired.")

    # Race-condition guard: re-check availability right before writing.
    existing = await get_user_by_email(token.new_email, db)
    if existing is not None and existing.id != token.user_id:
        raise HTTPException(status_code=409, detail="Email address is already in use.")

    user_result = await db.execute(select(User).where(User.id == token.user_id))
    user: User = user_result.scalars().first()

    user.email = token.new_email
    token.used_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Password reset — unauthenticated two-step: initiate → confirm
# ---------------------------------------------------------------------------

async def initiate_password_reset(
    email: str,
    db: AsyncSession,
    email_svc: EmailService,
) -> None:
    """
    Send a password-reset email if the address is registered.

    Always returns silently — callers must not reveal whether the address exists
    (anti-enumeration requirement).
    """
    normalised = email.strip().lower()
    user = await get_user_by_email(normalised, db)

    if user is None:
        # Silent return — do not leak whether the email is registered.
        return

    raw, token_hash = UserToken.generate()
    token = UserToken(
        user_id=user.id,
        token_hash=token_hash,
        token_type=TokenType.password_reset,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(token)
    await db.commit()

    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={raw}"
    await email_svc.send_password_reset(normalised, reset_url)


async def confirm_password_reset(
    raw_token: str,
    new_password: str,
    db: AsyncSession,
) -> None:
    """
    Complete a password-reset flow using the raw token from the reset link.

    Raises:
        HTTPException 400: if token is invalid/expired or password < 8 chars.
    """
    token_hash = UserToken.hash(raw_token)

    result = await db.execute(
        select(UserToken).where(
            UserToken.token_hash == token_hash,
            UserToken.token_type == TokenType.password_reset,
        )
    )
    token: UserToken | None = result.scalars().first()

    if token is None or not token.is_valid():
        raise HTTPException(status_code=400, detail="Token is invalid or has expired.")

    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    user_result = await db.execute(select(User).where(User.id == token.user_id))
    user: User = user_result.scalars().first()

    user.hashed_password = hash_password(new_password)
    # Invalidate all active refresh tokens so other sessions are logged out.
    user.last_refresh_token = None
    token.used_at = datetime.now(timezone.utc)
    await db.commit()


# ---------------------------------------------------------------------------
# Subscription management
# ---------------------------------------------------------------------------

async def cancel_subscription(user: User, db: AsyncSession) -> User:
    """
    Mark a user as no longer a subscriber. Does not interact with Stripe —
    that must be handled by the caller before invoking this.
    """
    user.is_subscriber = False
    await db.commit()
    await db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Token housekeeping (scheduled — do not call inline on requests)
# ---------------------------------------------------------------------------

async def purge_expired_tokens(db: AsyncSession) -> int:
    """
    Hard-delete user_tokens that are expired or have already been used.

    Returns the number of rows deleted. Intended to run as a scheduled job,
    not on the hot request path.
    """
    result = await db.execute(
        delete(UserToken).where(
            (UserToken.expires_at < datetime.now(timezone.utc))
            | (UserToken.used_at.is_not(None))
        )
    )
    await db.commit()
    return result.rowcount
