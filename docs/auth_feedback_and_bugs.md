# Auth Feedback & Bugs

Review findings from code review and security audit of Phase 6 auth/permissioning changes.
Date: 2026-03-14 | Branch: `refactor`

---

## Blockers — Fix Before Merge

### 1. Stale tests contradict the new implementation
**File:** `backend_new/tests/test_api_auth.py`

`TestGameLogsTierGating.test_game_logs_unauthenticated_returns_401` and `test_game_logs_free_user_returns_403` both assert 401/403 on the game-logs endpoint. The endpoint is now fully public (no auth dependency). These tests will either fail CI or pass by accident (mocked 404 ≠ 401/403) while asserting a false contract.

`test_unauthenticated_gets_empty_predictions_with_flag` asserts `auth_required is True` and `predictions == []` for anonymous users. The endpoint no longer injects `get_optional_user` and `auth_required` is never set to `True` anywhere in the codebase. This test cannot pass.

**Fix:** Delete `TestGameLogsTierGating` entirely. Rewrite the anonymous predictions test to assert `auth_required is False` and that predictions are returned.

---

### 2. `DEBUG=true` committed to `.env.example`
**File:** `backend_new/.env.example:26`

Changed from `DEBUG=false` to `DEBUG=true` in this branch. Any developer copying this file directly to `.env` gets:
- FastAPI `/docs` and `/redoc` Swagger UI publicly exposed (`main.py:37–38`)
- Refresh cookie loses `secure=True`, meaning it will be sent over plain HTTP (`auth.py:67`)

**Fix:** Revert to `DEBUG=false`. Developers who need debug mode locally already know to set it in their own `.env`.

---

## Important — Fix Before Launch

### 3. Effect C (week prediction fetch) missing `auth?.user` dependency
**File:** `frontend/components/player-lookup/PlayerModel.tsx:208`

Effect B (game logs + history) correctly re-fetches when auth state changes (`auth?.user` in dep array at line 151). Effect C (current week prediction card) does not — the prediction card stays stale after login/logout until the user manually changes the selected player or week. Effects B and C should have symmetrical re-fetch behavior.

**Fix:** Add `auth?.user` to the dependency array on line 208 alongside `[selectedPlayerId, selectedWeek, effectiveYear]`.

---

### 4. `auth_required` is dead code on `PredictionsResponse`
**File:** `backend_new/app/api/public.py:59`

The `auth_required: bool = False` field exists on the response schema but is never set to anything other than `False`. The anonymous-user gate that previously set it to `True` was removed. The field now misleads future developers about what the API does and causes incorrect test assertions (see Issue 1).

**Fix:** Remove `auth_required` from `PredictionsResponse`.

---

### 5. No rate limiting on public prediction and player endpoints
**File:** `backend_new/app/api/public.py`

`/api/predictions/{s}/{w}`, `/api/players`, `/api/players/{id}/game-logs`, and `/api/track-record` have no `@limiter.limit()` decorator. The limiter is already wired in `main.py` and used on auth endpoints. Public endpoints are exposed to bulk data scraping and DB resource exhaustion with no throttle.

**Fix:** Add `@limiter.limit("30/minute")` (or appropriate threshold) to all public GET endpoints. The infrastructure is already in place.

---

### 6. `require_free` on `/players/{id}/odds` is inconsistent with the open API design
**File:** `backend_new/app/api/public.py:552`

The odds endpoint requires authentication (`require_free`), but the predictions endpoint returns the same data — `sportsbook_odds`, `implied_prob`, and `favor` — to anonymous users with no auth. The guard protects nothing and breaks the stated design principle of gating at the UI layer.

**Fix:** Remove `require_free` from the odds endpoint to make it consistent, or document the reason it stays authenticated.

---

## Security Findings

### Critical (Pre-Revenue)

#### S1. Dev credentials compiled into production JS bundle
**File:** `frontend/contexts/AuthContext.tsx:251` / `frontend/.env.local`

`NEXT_PUBLIC_DEV_USER_EMAIL` and `NEXT_PUBLIC_DEV_USER_PASSWORD` are `NEXT_PUBLIC_*` variables. Next.js statically inlines every `NEXT_PUBLIC_*` var into the client JS bundle at build time. If either variable is ever set in Vercel (even in a preview environment by accident), the plaintext credentials ship to every browser. Anyone reading DevTools > Sources or running `strings` on the JS chunk gets working login credentials.

Current state: `.env.local` is gitignored and not committed. The risk is a deployment mistake, not an active exploit.

**Fix:** Gate the dev auto-login block on `process.env.NODE_ENV === 'development'` rather than a compiled env var — or remove the feature entirely now that real auth is wired. The auto-login served a pre-auth development purpose that no longer applies.

---

#### S2. Paywall is CSS blur only — full paid data is in every API response
**File:** `backend_new/app/api/public.py:296` / `frontend/components/shared/PaywallGate.tsx:33`

The predictions endpoint returns complete tier labels, `favor`, `final_prob`, and model odds to all callers including anonymous. `PaywallGate` renders real data into the DOM with `filter: blur(6px)`. Two trivial bypasses exist:
1. Open DevTools, remove the `style` attribute from the blurred div — instant unblur.
2. Call `GET /api/predictions/{season}/{week}` directly — full weekly picks with zero auth.

This was an intentional design decision (comment in diff: `// Access control is enforced at the UI layer`). The implication: the paywall is a UX nudge, not an access control boundary. Anyone with a browser can access all paid content for free.

**Acceptable for pre-revenue.** Must be addressed before the paywall is expected to drive actual subscriptions.

**Options when ready:**
- Hard gate: Restore server-side field stripping for anonymous/free users. `get_optional_user` already exists in `deps.py`.
- Soft gate: Return tier 1/2 rows as stubs (`final_prob: null`, `tier: "locked"`) for unauthenticated callers.

---

### High / Medium

#### S3. `require_free` on odds endpoint is inconsistent (see Issue 6 above)

#### S4. `sessionStorage` logout flag is tab-scoped
**File:** `frontend/contexts/AuthContext.tsx:356`

`sessionStorage` is per-tab. Opening a new tab after logout does not carry the `bggtdm_explicit_logout` flag, so dev auto-login fires again in the new tab. Not a production security issue (dev credentials should never be in prod), but a documented limitation: `sessionStorage` is not a reliable cross-tab logout signal. Server-side token revocation via `last_refresh_token` nulling is the authoritative signal for production logout scenarios.

---

### Accepted / Low Risk

| Finding | Notes |
|---|---|
| Access token in `localStorage` (XSS exposure) | Accepted tradeoff. Tokens are short-lived (15 min). Refresh token is httpOnly. Next.js has strong XSS defaults. |
| Refresh token entropy (UUID4, 122-bit) | SHA-256 hashed in DB, single-use rotation. No practical brute-force attack. |
| No CSRF on auth endpoints | Mitigated by SameSite=Lax on refresh cookie + access token in localStorage (not a cookie). |
| JWT `tier` claim not re-validated against DB claim | Downstream code reads `user.tier` from DB, not from JWT claims. Correct. Only an issue if future code reads tier directly from the token. |
| Security headers | `main.py` correctly sets `X-Frame-Options`, `X-Content-Type-Options`, HSTS, CSP, `Referrer-Policy`, `Permissions-Policy`. |
| `NEXT_PUBLIC_API_URL` exposes backend URL | Public by design. Not a secret. |

---

## Minor

- `PlayerModel.tsx:204` — `(prev: any)` cast is unnecessary. TypeScript infers `PlayerData | null` from the `useState` declaration. Replace with `(prev)`.
- `AuthContext.tsx:253` — `typeof sessionStorage !== 'undefined'` guard is dead in a `'use client'` component. Use `try/catch` for consistency with the existing `localStorage` helpers on lines 99–104.
- `/auth/login` and `/auth/register` are rate-limited at 5/minute per IP via slowapi. Confirm `X-Forwarded-For` is trusted on Render to avoid all requests sharing the same remote IP behind the reverse proxy.
