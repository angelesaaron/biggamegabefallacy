"""
AuthService — password hashing, JWT lifecycle, and user CRUD.

Design rules:
  - Passwords are never logged; ValueError (not HTTPException) is raised for
    business-logic failures — let the router translate to HTTP status codes.
  - Email is normalised to lowercase before every store or lookup.
  - Refresh tokens: raw UUID4 hex is returned to the caller; only its
    SHA-256 digest is persisted in users.last_refresh_token.
  - Access tokens carry sub (UUID str), email, and tier so the caller does not
    need a DB round-trip on every authenticated request.
"""

import uuid
from datetime import datetime, timedelta, timezone
from hashlib import sha256

import bcrypt as _bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User

# ---------------------------------------------------------------------------
# Password helpers — bcrypt directly (cost factor 12)
# Pre-compute a dummy hash at import time for constant-time reject path.
# ---------------------------------------------------------------------------

_BCRYPT_ROUNDS = 12
_DUMMY_HASH: bytes = _bcrypt.hashpw(b"dummy", _bcrypt.gensalt(rounds=_BCRYPT_ROUNDS))


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    """Return a bcrypt hash of *plain*.  Never log the input."""
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time bcrypt comparison."""
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

def hash_token(raw_token: str) -> str:
    """Return the SHA-256 hex digest of *raw_token* for safe DB storage."""
    return sha256(raw_token.encode()).hexdigest()


def create_access_token(user: User) -> str:
    """
    Mint a signed JWT.

    Claims:
      sub   — str(user.id)  (standard JWT subject claim)
      email — user.email
      tier  — user.tier
      exp   — now + ACCESS_TOKEN_EXPIRE_MINUTES
    """
    expire = datetime.now(tz=timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "is_subscriber": user.is_subscriber,
        "is_admin": user.is_admin,
        "exp": expire,
    }
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token() -> tuple[str, str]:
    """
    Generate a single-use refresh token pair.

    Returns:
        (raw_token, token_hash)
        raw_token  — UUID4 hex string; set in the httpOnly cookie
        token_hash — SHA-256 digest; stored in users.last_refresh_token
    """
    raw = uuid.uuid4().hex
    return raw, hash_token(raw)


def decode_access_token(token: str) -> dict | None:
    """
    Decode and verify an access token.

    Returns the claims dict on success, or None if the token is missing,
    malformed, expired, or signed with the wrong key.
    """
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.PyJWTError:
        return None


# ---------------------------------------------------------------------------
# Async DB helpers
# ---------------------------------------------------------------------------

async def get_user_by_email(email: str, db: AsyncSession) -> User | None:
    """Look up a user by (normalised) email.  Returns None if not found."""
    normalised = email.strip().lower()
    result = await db.execute(select(User).where(User.email == normalised))
    return result.scalars().first()


async def authenticate_user(
    email: str, password: str, db: AsyncSession
) -> User | None:
    """
    Verify credentials.

    Returns the User on success, or None when the email does not exist or the
    password does not match.  Both failure modes return None so the caller
    cannot distinguish them — no user-enumeration oracle.
    """
    user = await get_user_by_email(email, db)
    if user is None:
        # Run a dummy verify against a pre-computed hash to equalise timing
        # between "user not found" and "wrong password" — prevents enumeration.
        _bcrypt.checkpw(b"dummy", _DUMMY_HASH)
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user


async def create_user(email: str, password: str, db: AsyncSession) -> User:
    """
    Insert a new user row.

    Raises:
        ValueError: if the email address is already registered.
    """
    normalised = email.strip().lower()

    existing = await get_user_by_email(normalised, db)
    if existing is not None:
        raise ValueError(f"Email already registered: {normalised}")

    user = User(
        email=normalised,
        hashed_password=hash_password(password),
        is_subscriber=True,
    )
    db.add(user)
    await db.flush()   # populate user.id without committing the outer transaction
    await db.refresh(user)
    return user
