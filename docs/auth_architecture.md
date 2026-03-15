# Authentication & Authorization Architecture

> **Status:** Pre-implementation brainstorm — reference before starting the auth sprint.
> **Context:** BGF is a paywall app targeting the 2026 NFL season. This doc covers the full auth design: JWT strategy, tier gating, endpoint reorganization, rate limiting, and cybersecurity requirements.

---

## Overview

Three principals, four access tiers:

| Principal | Mechanism | Tier |
|---|---|---|
| Anonymous visitor | No token | Unauthed public |
| Registered (free) | JWT · `tier: "free"` | Free |
| Paying subscriber | JWT · `tier: "pro"` | Pro |
| You (admin) | `X-Admin-Key` header | Admin — unchanged |

---

## Recommended Stack

**Backend auth:** `python-jose` (JWT) + `passlib` (bcrypt). No external auth service — Auth0/Clerk/Supabase add cost, vendor lock-in, and a data split that complicates Stripe webhooks. A custom JWT flow is ~150 lines and gives full control over the `tier` claim.

**Frontend auth:** No next-auth. You're not doing OAuth/social login. A simple `AuthContext` + React hook pattern with `localStorage` for the access token and an httpOnly cookie for the refresh token is cleaner and more transparent.

---

## New Files

```
backend_new/app/api/auth.py                    # /auth/* router
backend_new/app/services/auth_service.py       # JWT issue/verify, bcrypt, tier lookup
backend_new/app/models/user.py                 # User ORM model
backend_new/alembic/versions/xxx_add_users.py  # Migration
```

---

## Database: `users` Table

```sql
CREATE TABLE users (
    id                 UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    email              TEXT        NOT NULL UNIQUE,
    hashed_password    TEXT        NOT NULL,
    tier               TEXT        NOT NULL DEFAULT 'free',  -- 'free' | 'pro'
    stripe_customer_id TEXT,
    is_active          BOOLEAN     DEFAULT TRUE,
    created_at         TIMESTAMPTZ DEFAULT now(),
    updated_at         TIMESTAMPTZ DEFAULT now()
);
```

Tier is stored here. When Stripe confirms a subscription, update `users.tier = 'pro'`. The next token refresh picks it up automatically — no token invalidation needed (access tokens are 15 min TTL).

---

## JWT Design

**Access token** — short-lived, returned in JSON response body, stored in memory or localStorage:

```json
{
  "sub": "user-uuid",
  "email": "user@example.com",
  "tier": "pro",
  "exp": 1234567890
}
```

**Refresh token** — 7-day TTL, stored in an httpOnly cookie (XSS-resistant). Single-use: store `last_refresh_token` hash in the users table and invalidate on use to prevent refresh token replay.

| Token | TTL | Storage |
|---|---|---|
| Access | 15 minutes | localStorage / memory |
| Refresh | 7 days | httpOnly cookie |

---

## API Route Tiers

### Unauthed public — no token required

Safe to expose to anyone. Used for marketing, onboarding, and the auth flow itself.

```
GET  /health
GET  /api/status/week
GET  /api/track-record
GET  /api/players                    (list only — no detail)
POST /api/auth/login
POST /api/auth/register
POST /api/auth/refresh
```

### Free tier — JWT · `tier: "free"`

User is registered and logged in but has not subscribed. Predictions are gated by content (not a separate route) — top 5 returned, `favor` and `tier` label stripped from response.

```
GET /api/predictions/{season}/{week}   # top 5 rows, favor stripped, tiers blurred
GET /api/players/{id}                  # basic info
GET /api/players/{id}/history          # last 2 seasons only
GET /api/players/{id}/odds             # current week only
```

### Pro tier — JWT · `tier: "pro"`

Full access to all prediction data.

```
GET /api/predictions/{season}/{week}   # full payload — all tiers, favor, completeness
GET /api/players/{id}                  # full info
GET /api/players/{id}/history          # all seasons
GET /api/players/{id}/game-logs        # unlocked at pro
GET /api/players/{id}/odds             # all weeks
```

### Admin — `X-Admin-Key` header

**No changes.** The existing `require_admin` dependency in `admin.py` stays exactly as-is. All `/admin/*` pipeline endpoints remain admin-key gated.

---

## Dependency Functions

Four FastAPI dependency functions cover all cases:

```python
# Returns User | None — never raises, used for content gating
async def get_optional_user(token: str = ...) -> User | None: ...

# Raises 401 if no valid token
async def require_auth(user: User = Depends(get_optional_user)) -> User: ...

# Raises 403 if not logged in (tier check is implicit — any valid JWT passes)
async def require_free(user: User = Depends(require_auth)) -> User: ...

# Raises 403 if tier != 'pro'
async def require_pro(user: User = Depends(require_auth)) -> User: ...
```

### Content gating on predictions (not route gating)

The predictions endpoint stays at one route. The response shape changes based on tier:

```python
@router.get("/predictions/{season}/{week}")
async def get_predictions(
    ...,
    current_user: User | None = Depends(get_optional_user),
):
    rows = await fetch_all_predictions(...)

    if current_user is None:
        # Anonymous: return nothing useful, prompt to register
        return PredictionsResponse(count=0, predictions=[], auth_required=True)

    if current_user.tier == "free":
        # Return top 5, strip favor and tier labels
        rows = rows[:5]
        rows = [strip_pro_fields(r) for r in rows]

    # Pro: return full payload as-is
    return PredictionsResponse(...)
```

---

## Rate Limiting

Use `slowapi` (pip-installable, Redis-backed or in-memory, FastAPI-native).

| Endpoint group | Limit |
|---|---|
| Auth endpoints (`/auth/*`) | 5 req/min per IP — kills credential stuffing |
| Unauthed public | 30 req/min per IP |
| Free tier (authed) | 60 req/min per user |
| Pro tier (authed) | 120 req/min per user |

Add to `main.py`:

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

---

## Security Headers Middleware

Add to `main.py` via a small Starlette middleware:

```python
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response
```

---

## Cybersecurity Checklist

| Requirement | Implementation | Status |
|---|---|---|
| Password hashing | bcrypt cost 12 via passlib | To build |
| Brute force protection | slowapi 5 req/min on auth routes | To build |
| No raw passwords in logs | FastAPI exception handler already swallows internals | ✓ Already done |
| HTTPS enforced | Render handles TLS; add HSTS header | HSTS to add |
| Admin key never in JWT | Admin stays on X-Admin-Key header, separate from user JWT | ✓ Already done |
| Docs off in production | `docs_url="/docs" if settings.DEBUG else None` | ✓ Already done |
| CORS locked | `CORS_ORIGINS` in config.py; add prod frontend URL at deploy | ✓ / To update |
| SQL injection | SQLAlchemy ORM parameterizes everything | ✓ Already done |
| Token rotation | Refresh tokens single-use (store hash in DB, invalidate on use) | To build |
| XSS on refresh token | Refresh token in httpOnly cookie | To build |
| Stripe webhook validation | Verify `stripe-signature` header before updating tier | To build (Stripe sprint) |

---

## Frontend Components Needed

| Component | Purpose |
|---|---|
| `AuthContext` + `useAuth()` hook | Global auth state, login/logout, token storage |
| `LoginModal` | Login form — wire up to existing blurred UI |
| `RegisterModal` | Registration form |
| `UpgradePrompt` | Shown when free user hits pro-gated content |
| Token refresh interceptor | Auto-refreshes access token before 15 min expiry |
| Admin route guard | Protects any future `/admin` frontend page |

The blurred/hidden elements already in the frontend are the free-tier experience. Keep that toggle pattern — it becomes the `current_user.tier === 'free'` conditional in the component.

---

## Implementation Sequence

1. Alembic migration — `users` table
2. `app/models/user.py` — User ORM model
3. `app/services/auth_service.py` — bcrypt hashing, JWT issue/verify, tier lookup
4. `app/api/auth.py` — `POST /auth/login`, `/register`, `/refresh`, `GET /me`
5. Dependency functions — `get_optional_user`, `require_free`, `require_pro`
6. Gate `predictions` endpoint — content gating by tier (not route split)
7. Move `game-logs` and full `history` behind `require_free()`
8. `slowapi` rate limiting in `main.py`
9. Security headers middleware in `main.py`
10. Frontend — `AuthContext`, login/register modals, upgrade prompt, token refresh interceptor

**Stripe integration comes after step 9.** The `users.stripe_customer_id` column is already in the schema above so the migration does not need to change when Stripe is added.

---

## Config Additions Needed

Add to `app/config.py` and `.env`:

```env
JWT_SECRET_KEY=<long random secret — openssl rand -hex 32>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
```

`JWT_SECRET_KEY` must be a cryptographically random string. Rotating it invalidates all outstanding tokens (forces re-login for all users).

---

*Last updated: March 2026 — pre-implementation brainstorm.*
