# Auth Bug Fix — Claude Code Prompt

Paste this directly into Claude Code.

---

## Context

Auth was implemented in `backend_new/`. The structure is correct but there are 5 bugs/gaps to fix. Do not refactor anything else — surgical fixes only.

Files to touch:
- `app/api/auth.py`
- `app/api/public.py`
- `app/config.py`
- `app/main.py` (startup guard only)
- `tests/test_api_auth.py` (new file — create it)

---

## Fix 1 — `_issue_tokens` missing `db.commit()` (auth.py)

**Location:** `app/api/auth.py`, function `_issue_tokens`

**Problem:** `db.flush()` sends SQL to the DB within the open transaction but never commits. The refresh token hash is never durably persisted. Login and register appear to work (no error) but the refresh token is lost when the session closes.

**Current code:**
```python
async def _issue_tokens(user, response, db) -> TokenResponse:
    access_token = create_access_token(user)
    raw_refresh, refresh_hash = create_refresh_token()
    user.last_refresh_token = refresh_hash
    db.add(user)
    await db.flush()
    _set_refresh_cookie(response, raw_refresh)
    return TokenResponse(access_token=access_token)
```

**Fixed code:**
```python
async def _issue_tokens(user, response, db) -> TokenResponse:
    access_token = create_access_token(user)
    raw_refresh, refresh_hash = create_refresh_token()
    user.last_refresh_token = refresh_hash
    db.add(user)
    await db.flush()
    await db.commit()
    await db.refresh(user)
    _set_refresh_cookie(response, raw_refresh)
    return TokenResponse(access_token=access_token)
```

---

## Fix 2 — `logout` missing `db.commit()` (auth.py)

**Location:** `app/api/auth.py`, function `logout`

**Problem:** The null-out of `last_refresh_token` is never committed. A captured refresh token remains valid after logout.

**Current code:**
```python
async def logout(...) -> None:
    _clear_refresh_cookie(response)
    if current_user is not None:
        current_user.last_refresh_token = None
        db.add(current_user)
```

**Fixed code:**
```python
async def logout(...) -> None:
    _clear_refresh_cookie(response)
    if current_user is not None:
        current_user.last_refresh_token = None
        db.add(current_user)
        await db.commit()
```

---

## Fix 3 — Empty `JWT_SECRET_KEY` startup guard (config.py + main.py)

**Problem:** `JWT_SECRET_KEY: str = ""` default means if the env var is missing, tokens are signed with an empty key — forgeable by anyone who notices.

**In `app/config.py`**, add a validator after the existing `parse_cors_origins` validator:

```python
from pydantic import field_validator, model_validator

@model_validator(mode="after")
def check_jwt_secret(self) -> "Settings":
    # Only enforce in non-test environments (tests set JWT_SECRET_KEY via env)
    import os
    if not self.JWT_SECRET_KEY and os.environ.get("PYTEST_CURRENT_TEST") is None:
        raise ValueError(
            "JWT_SECRET_KEY must be set. Generate one with: openssl rand -hex 32"
        )
    return self
```

---

## Fix 4 — Rate limiting on auth routes (auth.py)

**Problem:** `slowapi` is wired up in `main.py` but `/auth/login` and `/auth/register` have no `@limiter.limit()` decorator. Credential stuffing is unrestricted.

**In `app/api/auth.py`**, import the limiter and add decorators:

At the top of the file, add:
```python
from app.main import limiter
```

Add `@limiter.limit("5/minute")` and `request: Request` parameter to `login` and `register`:

```python
from fastapi import ..., Request

@router.post("/auth/register", ...)
@limiter.limit("5/minute")
async def register(
    request: Request,   # ← add this (slowapi requires it)
    body: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    ...

@router.post("/auth/login", ...)
@limiter.limit("5/minute")
async def login(
    request: Request,   # ← add this
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    ...
```

> Note: `request: Request` must be the **first** parameter for slowapi to inject the rate limit key correctly.

---

## Fix 5 — Gate `game-logs` and `history` endpoints (public.py)

**Problem:** `require_free` and `require_pro` are imported in `public.py` but not applied to the `/players/{id}/game-logs` or `/players/{id}/history` endpoints. Both are still fully open.

**For `/players/{player_id}/history`** — add `require_free` dependency and limit seasons for free users:

```python
@router.get("/players/{player_id}/history", ...)
async def get_player_history(
    player_id: str,
    season: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),   # ← add
) -> list[HistoryRow]:
    ...
    preds = (await db.execute(q)).scalars().all()

    # Free tier: last 2 seasons only. Unauthenticated: empty.
    if current_user is None:
        return []
    if current_user.tier == "free":
        available_seasons = sorted({p.season for p in preds}, reverse=True)[:2]
        preds = [p for p in preds if p.season in available_seasons]

    return [HistoryRow(...) for p in preds]
```

**For `/players/{player_id}/game-logs`** — require pro:

```python
@router.get("/players/{player_id}/game-logs", ...)
async def get_player_game_logs(
    player_id: str,
    season: Optional[int] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_pro),   # ← change from get_db-only to require_pro
) -> GameLogsResponse:
    ...
```

---

## After making all fixes, run:

```bash
cd backend_new
pytest tests/test_api_auth.py -v
pytest tests/ -v
```

All existing tests should still pass. The new auth tests should pass too.
