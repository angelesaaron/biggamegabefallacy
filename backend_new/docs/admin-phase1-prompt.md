# Admin Dashboard — Phase 1 Implementation Prompt

## Context

This is the Big Game Gabe Fallacy (BGGTF) NFL ATTD prediction app. Stack: FastAPI backend, PostgreSQL, Next.js frontend. Auth is fully implemented with JWT access tokens + httpOnly refresh cookie. The existing `X-Admin-Key` header approach gates all `/api/admin/*` routes.

**Goal:** Build a superuser admin experience — a 4th tab in the frontend nav that appears only for the admin user, with a vertical panel nav and 2 panels in Phase 1. The admin is identified by a new `is_admin` boolean on the `User` model.

---

## Phase 1 Scope

### Panel 1 — Account Management
- List all users (email, is_subscriber, stripe_customer_id presence, created_at, is_active)
- Search/filter by email
- Toggle `is_subscriber` on any user
- Toggle `is_active` (soft disable without delete)
- Grant access flow: type email → if account exists flip `is_subscriber=True`; if not, create stub account with a random password and `is_subscriber=True`, return the temp password to display once
- **No hard deletes** — only soft disable via `is_active=False`

### Panel 2 — DB Health
Read-only dashboard showing:
- Record counts: users, player_game_logs, player_features, predictions, players (or whatever the actual table names are — check models)
- Players missing game logs this season (players in roster but no game log rows for current season)
- Predictions count for current week vs. total eligible players
- Recent DataQualityEvent rows (last 10, if that table exists)
- Last ingestion timestamps per stage (last `updated_at` for each major table)
- All queries are read-only, no side effects

---

## Backend Changes

### 1. Migration — add `is_admin` to users

Create a new Alembic migration (next in sequence after the latest existing one). Check `alembic/versions/` to find the latest revision number and use it as the `down_revision`.

```python
# Add is_admin boolean, default false, non-nullable
op.add_column('users', sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='false'))
```

### 2. Update User model

In `app/models/user.py`, add:
```python
is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
```

### 3. Update auth token — include `is_admin` in JWT claims

In `app/services/auth_service.py`, wherever `create_access_token` builds the claims dict, add `"is_admin": user.is_admin`. Check the existing claim structure (likely has `sub`, `is_subscriber`) and follow the same pattern.

### 4. Update `/api/auth/me` response

In `app/api/auth.py`, add `is_admin: bool` to `MeResponse` and populate it from `current_user.is_admin`.

### 5. New admin dep — `require_admin_user`

In `app/api/deps.py`, add a new dependency (separate from the existing `X-Admin-Key` header approach):

```python
async def require_admin_user(user: User = Depends(require_auth)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    return user
```

### 6. New router — `app/api/admin_users.py`

Mount at `/api/admin-ui` (distinct from the existing `/api/admin` pipeline routes which use X-Admin-Key). This router uses `require_admin_user` dep.

Endpoints:

```
GET    /api/admin-ui/users              # list all users, optional ?search=email
PATCH  /api/admin-ui/users/{user_id}/subscriber   # toggle is_subscriber
PATCH  /api/admin-ui/users/{user_id}/active       # toggle is_active
POST   /api/admin-ui/users/grant                  # grant access by email (create or flip)
```

For the `POST /grant` endpoint:
- Accept `{ email: str }`
- If user exists: set `is_subscriber=True`, return `{ created: false, user_id, email }`
- If user does not exist: create with `secrets.token_urlsafe(12)` as password, `is_subscriber=True`, return `{ created: true, user_id, email, temp_password }` — this is the only time temp_password is returned

**Important:** `is_admin` is never toggled via API — only set manually in DB.

```
GET    /api/admin-ui/health             # DB health stats (Panel 2)
```

For the health endpoint, run these queries and return a single JSON object:
- COUNT(*) for each major table (check actual model `__tablename__` values)
- Players missing game logs: players in the current season's roster who have zero rows in `player_game_logs` for the current season — use the same current-season logic the rest of the app uses
- Prediction coverage: count of predictions for the current week vs. count of players who should have predictions
- Last 10 `DataQualityEvent` rows if that table exists, ordered by `created_at DESC`
- Max `updated_at` per major table as "last updated" timestamps

### 7. Register new router in `main.py`

```python
from app.api.admin_users import router as admin_ui_router
app.include_router(admin_ui_router, prefix="/api")
```

Add `"X-Admin-Key"` is already in CORS allowed headers — no change needed there.

---

## Frontend Changes

### 1. Extend `AuthContext`

The JWT already carries `is_subscriber`. Add `is_admin` decode alongside it. In `contexts/AuthContext.tsx`, wherever `isSubscriber` is derived from the token, also derive `isAdmin: boolean` the same way. Expose it from the context.

Update `hooks/useAuth.ts` to also export `useIsAdmin()` following the same pattern as `useIsSubscriber()`.

### 2. 4th Nav Tab — "Admin"

In the main nav component (wherever the existing tabs live), add a 4th tab labeled "Admin" that only renders when `isAdmin === true`. Follow the exact same tab pattern as the existing tabs — no special styling needed.

### 3. Admin Page — `app/admin/page.tsx` (or equivalent route)

Layout: two-column. Left side: vertical panel nav with two items for Phase 1 — "Accounts" and "DB Health". Right side: panel content area. Panel nav items are just buttons that swap the active panel — no routing needed, local state is fine.

**Accounts Panel:**
- Search input (filter by email, client-side on the fetched list is fine)
- Table: email | subscriber (toggle switch) | active (toggle switch) | stripe (yes/no) | joined date
- Toggle switches call PATCH endpoints immediately on change with optimistic update + revert on error
- "Grant Access" section below table: email input + button → POST /api/admin-ui/users/grant → on success show result inline (show temp_password if created=true, warn it's only shown once)

**DB Health Panel:**
- Simple stat cards / table layout showing all the counts and timestamps from `GET /api/admin-ui/health`
- Auto-refreshes every 60 seconds
- "Refresh" button for manual refresh
- No actions — read only

### 4. Auth headers

All `/api/admin-ui/*` requests must include `Authorization: Bearer <access_token>` — use the same pattern as other authenticated hooks in the codebase (check `hooks/usePredictions.ts` for the pattern).

---

## What NOT to touch

- The existing `/api/admin/*` pipeline routes and `X-Admin-Key` auth — leave completely untouched
- The existing subscriber gating logic (`require_subscriber`, `PaywallGate`, `TeaserBanner`)
- Any ML pipeline code
- Stripe fields on the User model (`stripe_customer_id`) — read-only display only

---

## Constraints & patterns to follow

- All new backend endpoints return consistent error shapes matching the existing API (detail string)
- Follow the existing `async def` + `AsyncSession` + `select()` SQLAlchemy pattern — no raw SQL strings
- Pydantic response models for every endpoint — no dict returns
- Migration file must set `down_revision` to the actual latest revision in `alembic/versions/`
- Frontend: follow existing component/hook patterns exactly — check `hooks/usePredictions.ts` and `contexts/AuthContext.tsx` before writing new code
- No new npm packages unless strictly necessary
- TypeScript strict — no `any` types

---

## Suggested implementation order

1. Migration + User model update
2. `create_access_token` + `MeResponse` update  
3. `require_admin_user` dep
4. `admin_users.py` router (accounts endpoints first, health second)
5. Register router in `main.py`
6. Frontend: AuthContext + useIsAdmin
7. Frontend: Admin tab in nav
8. Frontend: Admin page with Accounts panel
9. Frontend: DB Health panel
