# Local Auth Testing Guide

How to test the auth system locally — both automated (pytest) and manual (curl/httpie against the running server).

---

## 1. Environment setup

Create or update `backend_new/.env` with the new auth variables:

```bash
# Generate a real secret — do this once and save it
openssl rand -hex 32
```

Add to `.env`:
```env
JWT_SECRET_KEY=<paste output of openssl command above>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# Existing vars — make sure these are set too
DEBUG=true
ADMIN_KEY=your-admin-key
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/bggtdm_v2
```

---

## 2. Run the migration

```bash
cd backend_new
alembic upgrade head
```

Verify the table was created:
```bash
psql bggtdm_v2 -c "\d users"
```

Expected output: table with columns `id, email, hashed_password, tier, stripe_customer_id, last_refresh_token, is_active, created_at, updated_at`.

---

## 3. Run automated tests (no running server needed)

```bash
cd backend_new
source .venv/bin/activate

# Run only auth tests
pytest tests/test_api_auth.py -v

# Run full suite — make sure existing tests still pass
pytest tests/ -v

# Run with output on failure
pytest tests/test_api_auth.py -v -s
```

### What the test suite covers

| Test class | What it checks |
|---|---|
| `TestRegister` | Happy path, duplicate email 409, short password 422, cookie set, **commit called** |
| `TestLogin` | Valid creds, wrong password 401, unknown email 401, same error message (no enumeration), **commit called** |
| `TestRefresh` | Valid cookie → new token, no cookie → 401, wrong token → 401 |
| `TestMe` | Returns user info, no password/hash in response, no token → 401, wrong key → 401 |
| `TestLogout` | 204 + **commit called**, unauthenticated → 204 (idempotent) |
| `TestPredictionsTierGating` | Unauthed → empty + `auth_required: true`, pro dep passes, free → 403 on pro route |
| `TestGameLogsTierGating` | Unauthed → 401, free user → 403 |

Tests marked **commit called** are the Fix 1/2 regression tests — they fail before the fix and pass after.

---

## 4. Manual testing against the running server

Start the server:
```bash
cd backend_new
uvicorn app.main:app --reload --port 8000
```

Swagger UI (DEBUG=true): http://localhost:8000/docs

### Register

```bash
curl -s -c cookies.txt -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}' | jq
```

Expected:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

The `Set-Cookie: refresh_token=...` header should be in the response. `-c cookies.txt` saves it for subsequent curl calls.

### Login (OAuth2 form, not JSON)

```bash
curl -s -c cookies.txt -X POST http://localhost:8000/api/auth/login \
  -d "username=test@example.com&password=password123" | jq
```

Save the access token:
```bash
TOKEN=$(curl -s -c cookies.txt -X POST http://localhost:8000/api/auth/login \
  -d "username=test@example.com&password=password123" | jq -r .access_token)
echo $TOKEN
```

### /me

```bash
curl -s http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer $TOKEN" | jq
```

Expected:
```json
{
  "id": "...",
  "email": "test@example.com",
  "tier": "free",
  "is_active": true
}
```

### Refresh token (uses saved cookie)

```bash
curl -s -b cookies.txt -c cookies.txt -X POST \
  http://localhost:8000/api/auth/refresh | jq
```

Expected: new `access_token`. The cookie jar is updated with the new refresh token.

### Predictions — unauthed (should get empty + flag)

```bash
curl -s http://localhost:8000/api/predictions/2025/1 | jq .auth_required
```

Expected: `true`

### Predictions — free tier (top 5, no favor)

```bash
curl -s http://localhost:8000/api/predictions/2025/1 \
  -H "Authorization: Bearer $TOKEN" | jq '{count: .count, first_favor: .predictions[0].favor}'
```

Expected: `count` ≤ 5, `first_favor` = `null`

### Game logs — free tier (should 403)

```bash
curl -s http://localhost:8000/api/players/some-player-id/game-logs \
  -H "Authorization: Bearer $TOKEN" | jq
```

Expected:
```json
{"detail": "Pro subscription required."}
```
with HTTP 403.

### Logout

```bash
curl -s -b cookies.txt -c cookies.txt -X POST \
  http://localhost:8000/api/auth/logout \
  -H "Authorization: Bearer $TOKEN" -v
```

Expected: `204 No Content`. Try the refresh endpoint again — should 401 now since the DB hash was nulled.

### Test that logout actually nulled the hash (regression for Fix 2)

```bash
# After logout, this should fail:
curl -s -b cookies.txt -X POST http://localhost:8000/api/auth/refresh | jq
```

Expected: `{"detail": "Invalid or expired refresh token."}` with 401.

---

## 5. Manually upgrade a user to pro (for testing pro tier)

```bash
psql bggtdm_v2 -c "UPDATE users SET tier = 'pro' WHERE email = 'test@example.com';"
```

Then log in again to get a fresh token with `tier: "pro"` in the JWT claims. You can inspect the token at https://jwt.io — paste the access token and verify the `tier` claim.

```bash
TOKEN=$(curl -s -c cookies.txt -X POST http://localhost:8000/api/auth/login \
  -d "username=test@example.com&password=password123" | jq -r .access_token)

# Now game-logs should work
curl -s "http://localhost:8000/api/players/some-real-player-id/game-logs" \
  -H "Authorization: Bearer $TOKEN" | jq .season
```

---

## 6. Rate limit smoke test

```bash
# Hit login 6 times fast — 6th should 429
for i in {1..6}; do
  echo "Request $i:"
  curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/auth/login \
    -d "username=test@example.com&password=wrongpassword"
  echo
done
```

Expected: first 5 return `401`, 6th returns `429 Too Many Requests`.

> Note: Rate limit only applies after Fix 4 is implemented. Before that, all 6 return 401.

---

## 7. Security header check

```bash
curl -s -I http://localhost:8000/health
```

Expected headers present:
```
x-frame-options: DENY
x-content-type-options: nosniff
strict-transport-security: max-age=31536000; includeSubDomains
content-security-policy: default-src 'self'; ...
referrer-policy: strict-origin-when-cross-origin
permissions-policy: camera=(), ...
```

---

## Common errors and fixes

| Error | Cause | Fix |
|---|---|---|
| `RuntimeError: JWT_SECRET_KEY must be set` | Missing env var | Add `JWT_SECRET_KEY` to `.env` |
| `422 Unprocessable Entity` on login | Sending JSON instead of form data | Use `-d "username=...&password=..."` not `-d '{"email":...}'` |
| Refresh token → 401 after restart | In-memory session lost (SQLite dev) | This is correct behavior — use real Postgres locally |
| `alembic upgrade head` fails | Migration chain broken | Check `down_revision` in `0005_add_users.py` matches revision of `0004` |
| Tests fail with `JWT_SECRET_KEY` error | Env var not set before import | The test file sets it via `os.environ.setdefault` at top — make sure it's not imported before that line |
