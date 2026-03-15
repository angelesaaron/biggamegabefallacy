# Account Management Sprint — Claude Code Prompt

Read every section before writing a single line of code. Scope is precise — do not touch anything outside what is listed. Spin up agents per the agent breakdown at the bottom.

---

## Guiding principles

- **No AI slop. No bandaid fixes.** If the clean solution requires a bigger lift, take it.
- **Backend is source of truth.** Never gate on client-side state alone.
- **One surface area.** Prefer one well-designed endpoint/component over two narrow ones.
- **Testable and injectable.** Services must be mockable — no tight coupling to external APIs.
- **Security by default.** Timing-safe comparisons, single-use tokens, short TTLs, httpOnly cookies where applicable.

---

## What this sprint adds

1. `first_name` / `last_name` fields on the User model
2. Account management page at `/account` (name, email, member since, cancel stub)
3. Nav dropdown (name → My Account / Log Out)
4. Change password flow (logged in — requires current password)
5. Forgot password / reset password flow (logged out — email token)
6. Email change with verification token (logged in — pending until confirmed)
7. Email infrastructure via Resend
8. Cancel subscription stub (flips `is_subscriber = false`, Stripe handles later)
9. One shared `user_tokens` table for all token types (reset, email verification)

---

## DATABASE CHANGES

### Migration 0007 — `user_tokens` table + name fields on users

Create `backend_new/alembic/versions/0007_account_management.py`:

```python
"""Add first_name/last_name to users. Add user_tokens table.

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    # Add name fields to users
    op.add_column("users", sa.Column("first_name", sa.String(100), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.String(100), nullable=True))

    # Token type enum
    token_type = postgresql.ENUM(
        "password_reset",
        "email_verification",
        name="tokentypeenum",
        create_type=True,
    )
    token_type.create(op.get_bind())

    op.create_table(
        "user_tokens",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),  # SHA-256 hex
        sa.Column("token_type", sa.Enum("password_reset", "email_verification", name="tokentypeenum"), nullable=False),
        sa.Column("new_email", sa.String(255), nullable=True),   # only for email_verification tokens
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_user_tokens_token_hash", "user_tokens", ["token_hash"])
    op.create_index("ix_user_tokens_user_id", "user_tokens", ["user_id"])


def downgrade():
    op.drop_index("ix_user_tokens_user_id", table_name="user_tokens")
    op.drop_index("ix_user_tokens_token_hash", table_name="user_tokens")
    op.drop_table("user_tokens")
    sa.Enum(name="tokentypeenum").drop(op.get_bind())
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
```

---

## BACKEND CHANGES

### 1. Update `app/models/user.py`

Add `first_name` and `last_name` as nullable string columns. Existing users get `None` — the account page prompts them to fill in on first visit.

```python
first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
```

Keep all existing fields exactly as they are.

### 2. Create `app/models/user_token.py`

Single model for all time-limited user tokens. Token type is an enum — never store raw tokens, only SHA-256 hashes.

```python
import hashlib
import secrets
from enum import Enum as PyEnum
from datetime import datetime, timezone, timedelta
from sqlalchemy import String, DateTime, ForeignKey, Enum as SAEnum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class TokenType(PyEnum):
    password_reset = "password_reset"
    email_verification = "email_verification"


class UserToken(Base):
    __tablename__ = "user_tokens"

    id: Mapped[str] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    token_type: Mapped[TokenType] = mapped_column(SAEnum(TokenType), nullable=False)
    new_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="now()")

    @staticmethod
    def generate() -> tuple[str, str]:
        """Returns (raw_token, hash). Store hash, send raw."""
        raw = secrets.token_urlsafe(32)
        hashed = hashlib.sha256(raw.encode()).hexdigest()
        return raw, hashed

    @staticmethod
    def hash(raw: str) -> str:
        return hashlib.sha256(raw.encode()).hexdigest()

    def is_valid(self) -> bool:
        return (
            self.used_at is None
            and self.expires_at > datetime.now(timezone.utc)
        )
```

### 3. Create `app/services/email_service.py`

Thin wrapper around Resend. Injectable — tests mock this, not Resend directly.

```python
import resend
from app.config import settings


class EmailService:
    def __init__(self):
        resend.api_key = settings.RESEND_API_KEY

    async def send_password_reset(self, to_email: str, reset_url: str) -> None:
        resend.Emails.send({
            "from": settings.EMAIL_FROM,
            "to": to_email,
            "subject": "Reset your Big Game Gabe password",
            "html": self._reset_template(reset_url),
        })

    async def send_email_verification(self, to_email: str, verify_url: str) -> None:
        resend.Emails.send({
            "from": settings.EMAIL_FROM,
            "to": to_email,
            "subject": "Confirm your new email — Big Game Gabe",
            "html": self._verify_email_template(verify_url),
        })

    def _reset_template(self, url: str) -> str:
        return f"""
        <p>You requested a password reset for your Big Game Gabe account.</p>
        <p><a href="{url}">Reset your password</a></p>
        <p>This link expires in 1 hour. If you didn't request this, ignore this email.</p>
        """

    def _verify_email_template(self, url: str) -> str:
        return f"""
        <p>Confirm your new email address for Big Game Gabe.</p>
        <p><a href="{url}">Confirm email change</a></p>
        <p>This link expires in 24 hours. If you didn't request this, ignore this email.</p>
        """


# Singleton — import and use directly in services
email_service = EmailService()
```

Add to `app/config.py`:
```python
RESEND_API_KEY: str = ""
EMAIL_FROM: str = "noreply@biggamegabe.com"
FRONTEND_URL: str = "http://localhost:3000"  # override in prod env
```

Add startup guard for `RESEND_API_KEY` (same pattern as `JWT_SECRET_KEY`).

### 4. Create `app/services/account_service.py`

All account mutation logic lives here. Auth routes handle auth; account_service handles profile/password/email/tokens.

Methods to implement:

**`update_name(user, first_name, last_name, db) -> User`**
- Validate: first/last max 100 chars, no empty strings
- Update and flush. Return updated user.

**`change_password(user, current_password, new_password, db) -> None`**
- Timing-safe verify `current_password` against `user.hashed_password`
- Validate new password meets policy (min 8 chars)
- Bcrypt hash at cost 12. Update user. Invalidate all refresh tokens (set `last_refresh_token = None` — existing rotation mechanism handles revocation).

**`initiate_email_change(user, new_email, db, email_service) -> None`**
- Normalize new_email (lowercase, strip)
- Check new_email not already taken by another user
- Generate `UserToken(token_type=email_verification, new_email=new_email, expires_at=now+24h)`
- Store token hash. Commit.
- Send verification email to `new_email` with link to `/verify-email?token=<raw>`

**`confirm_email_change(raw_token, db) -> User`**
- Hash the raw token. Look up `UserToken` by hash where `token_type=email_verification`.
- Guard: `token.is_valid()` — raise 400 if expired or used.
- Check `token.new_email` not already taken (race condition guard).
- Update `user.email = token.new_email`. Mark `token.used_at = now()`. Commit.
- Return updated user (caller will issue new JWT with updated email claim).

**`initiate_password_reset(email, db, email_service) -> None`**
- Look up user by email. **Always return success even if email not found** (prevents enumeration).
- If user found: generate token, store hash, send reset email to `/reset-password?token=<raw>`, TTL 1 hour.

**`confirm_password_reset(raw_token, new_password, db) -> None`**
- Hash token. Look up by hash where `token_type=password_reset`.
- Guard: `token.is_valid()`.
- Validate password policy.
- Hash and update. Mark token used. Invalidate refresh tokens. Commit.

**`cancel_subscription(user, db) -> User`**
- Set `user.is_subscriber = False`. Commit.
- Return updated user.
- Note: Stripe webhook will eventually own this. This stub handles direct cancellation until then.

**Token cleanup:** add a helper `purge_expired_tokens(db)` — call from a periodic task or admin endpoint. Deletes rows where `expires_at < now()` or `used_at IS NOT NULL`. Do not call inline on every request.

### 5. Update `app/api/auth.py`

**Update `MeResponse`** to include new fields:

```python
class MeResponse(BaseModel):
    id: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    is_subscriber: bool
    is_active: bool
    member_since: str   # ISO date string, e.g. "2025-01-14"
```

Update `/me` endpoint to populate these. `member_since` comes from `user.created_at.date().isoformat()`.

**Add forgot password routes** (unauthenticated):

```
POST /api/auth/forgot-password    { email }             → always 200
POST /api/auth/reset-password     { token, new_password } → 200 or 400
```

Apply `@limiter.limit("5/minute")` to both. No auth dependency.

### 6. Create `app/api/users.py`

New router mounted at `/api/users`. All routes require `require_auth`.

```
PATCH  /api/users/me              { first_name, last_name }    → MeResponse
PATCH  /api/users/me/email        { new_email }                → 200 (email sent)
POST   /api/users/me/verify-email { token }                    → MeResponse + new JWT
POST   /api/users/me/password     { current_password, new_password } → 200
POST   /api/users/me/cancel       {}                           → MeResponse
```

Mount in `app/main.py`:
```python
from app.api import users
app.include_router(users.router, prefix="/api")
```

**Schema pattern** — keep it clean:

```python
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
```

For `POST /api/users/me/verify-email`: on success, issue a new access token with the updated email claim and return it in the response body (same shape as `TokenResponse`). The frontend should update its stored token.

Rate limit email-initiating routes at `3/minute`.

---

## FRONTEND CHANGES

### 7. Update `types/auth.ts`

```typescript
export interface AuthUser {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  is_subscriber: boolean;
  member_since: string;  // ISO date e.g. "2025-01-14"
}
```

### 8. Update `contexts/AuthContext.tsx`

- Update `MeResponse` interface to match new backend shape
- Populate `first_name`, `last_name`, `member_since` in `hydrateUser`
- Add `refreshUser(): Promise<void>` to context — calls `/api/auth/me` and updates user state. Account page calls this after mutations.

```typescript
export interface AuthContextValue {
  user: AuthUser | null;
  isLoading: boolean;
  isSubscriber: boolean;
  login: ...
  register: ...
  logout: ...
  refreshToken: ...
  getToken: ...
  refreshUser: () => Promise<void>;   // new
}
```

### 9. Create `hooks/useAccount.ts`

Single hook that owns all account page data fetching and mutations. Components stay dumb.

```typescript
export function useAccount() {
  const { user, getToken, refreshUser } = useAuth();

  const updateName = async (firstName: string, lastName: string) => { ... };
  const changePassword = async (current: string, next: string) => { ... };
  const initiateEmailChange = async (newEmail: string) => { ... };
  const cancelSubscription = async () => { ... };

  return { user, updateName, changePassword, initiateEmailChange, cancelSubscription };
}
```

Each mutation: sends authenticated request, calls `refreshUser()` on success, throws on error (caller handles toast/error state).

### 10. Create `app/account/page.tsx`

Route: `/account`. Requires auth — redirect to `/` if not logged in (use `require_auth` pattern already established, or a simple `useEffect` redirect).

Page layout (top to bottom):

```
┌─────────────────────────────────────┐
│  Profile                            │
│  [first] [last]    [Save]           │
│  Email: user@email.com  [Change →]  │
│  Member since: Jan 14, 2025         │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  Change Password                    │
│  Current password [          ]      │
│  New password     [          ]      │
│  Confirm new      [          ]      │
│                   [Update Password] │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐ ← danger zone, visually separated
│  Subscription                       │
│  Status: Active subscriber          │
│  [Cancel Subscription]              │  ← destructive styling, confirmation gate
└─────────────────────────────────────┘
```

Rules:
- Name and password are separate forms — do not combine
- Email change opens an inline flow or modal (not a separate page) — user enters new email, sees "Verification email sent to X"
- Cancel subscription requires a confirmation step (e.g. "Type CANCEL to confirm") before firing the endpoint
- No page-level blur, no gating — `/account` is only reachable when logged in

### 11. Create `app/verify-email/page.tsx`

Landing page for email verification links. Reads `?token=` from URL. On mount, calls `POST /api/users/me/verify-email`. On success: updates auth token, shows success state, redirects to `/account` after 2s. On failure: shows clear error (expired, already used, etc.).

### 12. Create `app/reset-password/page.tsx`

Landing page for password reset links. Reads `?token=` from URL. Renders a form: new password + confirm. On submit: calls `POST /api/auth/reset-password`. On success: redirects to login with a success message. On failure: shows clear error.

### 13. Add "Forgot password?" to `AuthModal`

On the login form, add a small text link below the password field:

```
Forgot your password?
```

Clicking it transitions the modal to a forgot-password view (inline state change, not a new modal or page). The forgot-password view has one email input and a submit button. On success: show "Check your email for a reset link." On error: show generic message (never reveal whether email exists).

### 14. Create nav dropdown component

Create `components/shared/NavUserMenu.tsx`. This is a real dropdown with a proper outside-click handler using `useRef` + `useEffect` — not a CSS hover trick.

```typescript
// Trigger: user's display name or "Account" if name not set
// Dropdown items:
//   My Account  →  /account
//   ──────────
//   Log Out
```

Wire it into the existing `NavBar` component where the auth state is shown. When the user is not logged in, show the existing Sign In / Get Access buttons.

Future-proofing: items are driven by a typed array so "Billing" can be added as a third item without touching the component internals.

```typescript
interface NavMenuItem {
  label: string;
  href?: string;
  onClick?: () => void;
  isDivider?: boolean;
  isDanger?: boolean;
}
```

---

## Files to create

```
backend_new/alembic/versions/0007_account_management.py
backend_new/app/models/user_token.py
backend_new/app/services/email_service.py
backend_new/app/services/account_service.py
backend_new/app/api/users.py

frontend/app/account/page.tsx
frontend/app/verify-email/page.tsx
frontend/app/reset-password/page.tsx
frontend/hooks/useAccount.ts
frontend/components/shared/NavUserMenu.tsx
```

## Files to modify

```
backend_new/app/models/user.py                    ← add first_name, last_name
backend_new/app/api/auth.py                       ← update MeResponse, add forgot/reset routes
backend_new/app/config.py                         ← add RESEND_API_KEY, EMAIL_FROM, FRONTEND_URL
backend_new/app/main.py                           ← mount users router

frontend/types/auth.ts                            ← add first_name, last_name, member_since
frontend/contexts/AuthContext.tsx                 ← update MeResponse, add refreshUser
frontend/components/shared/NavBar.tsx             ← wire in NavUserMenu
frontend/components/auth/AuthModal.tsx            ← add forgot password view
```

## Files to leave alone

```
backend_new/app/api/deps.py                       ← no changes
backend_new/app/api/public.py                     ← no changes
backend_new/app/api/admin.py                      ← no changes
backend_new/app/services/auth_service.py          ← no changes (account_service handles account mutations)
frontend/contexts/AuthModalContext.tsx            ← no changes
frontend/hooks/useAuth.ts                         ← no changes
frontend/components/weekly/*                      ← no changes
frontend/components/player-lookup/*               ← no changes
```

---

## Environment variables to add

```
# backend_new/.env
RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxx
EMAIL_FROM=noreply@biggamegabe.com
FRONTEND_URL=https://biggamegabe.com   # localhost:3000 in dev
```

---

## Agent breakdown

Spin up the following agents in parallel where dependencies allow:

### Agent 1 — Backend: DB + Models + Service
Scope: migration 0007, `user_token.py` model, `user.py` updates, `account_service.py`, `email_service.py`, `config.py` additions.
Run `alembic upgrade head` and confirm clean.

### Agent 2 — Backend: API Routes
Depends on Agent 1 completing models/services.
Scope: `app/api/users.py` (full new router), `app/api/auth.py` updates (MeResponse + forgot/reset routes), `app/main.py` router mount.

### Agent 3 — Frontend: Auth + Hooks
Scope: `types/auth.ts`, `contexts/AuthContext.tsx` (refreshUser + new fields), `hooks/useAccount.ts`.
Can run in parallel with Agent 1.

### Agent 4 — Frontend: Pages + Nav
Depends on Agent 3.
Scope: `app/account/page.tsx`, `app/verify-email/page.tsx`, `app/reset-password/page.tsx`, `NavUserMenu.tsx`, `NavBar.tsx` wiring, `AuthModal.tsx` forgot-password view.

---

## Correctness checklist — verify after implementation

- [ ] `alembic upgrade head` runs clean — `users` has `first_name`, `last_name`; `user_tokens` table exists
- [ ] `GET /api/auth/me` returns `first_name`, `last_name`, `member_since` fields
- [ ] `PATCH /api/users/me` updates name and returns updated MeResponse
- [ ] `POST /api/users/me/password` with wrong current password → 400 (timing-safe)
- [ ] `POST /api/users/me/password` with correct current password → 200, refresh token invalidated
- [ ] `POST /api/auth/forgot-password` with unknown email → 200 (no enumeration leak)
- [ ] `POST /api/auth/forgot-password` with known email → email sent, token stored hashed
- [ ] `POST /api/auth/reset-password` with expired token → 400
- [ ] `POST /api/auth/reset-password` with used token → 400
- [ ] `POST /api/auth/reset-password` with valid token → 200, token marked used, refresh invalidated
- [ ] `PATCH /api/users/me/email` → verification email sent to new address
- [ ] `POST /api/users/me/verify-email` with valid token → email updated, new JWT returned
- [ ] `POST /api/users/me/cancel` → `is_subscriber` flips to false, reflected in next `/me` call
- [ ] `/account` page redirects to `/` if not logged in
- [ ] Nav dropdown renders correct display name (falls back gracefully if name not set)
- [ ] Outside-click closes nav dropdown
- [ ] Cancel subscription requires confirmation before firing endpoint
- [ ] Forgot password flow never reveals whether email exists in system
- [ ] No `console.log` with sensitive fields (tokens, passwords) anywhere
