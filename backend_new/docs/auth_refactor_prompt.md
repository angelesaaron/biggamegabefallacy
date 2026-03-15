# Auth Refactor — Claude Code Prompt

This prompt covers a full auth refactor across backend and frontend. Read every section before writing a single line of code. Scope is precise — do not touch anything outside what is listed.

---

## The core problem to fix

The current implementation has three issues to resolve together:

1. **CSS blur is security theater.** `PaywallGate` and `HistoricalResultCard` render real data and apply `filter: blur()` on top. Any user can remove that style in DevTools. The fix is: don't render restricted content at all — and more importantly, don't send it from the backend.

2. **Three tiers when we need two.** The current model has anonymous / free / pro. We want: **public** (no account) and **subscriber** (has account, future Stripe payment). Anonymous and "free account" are identical — there is no reason to distinguish them. One gate, one check.

3. **Backend sends data it shouldn't.** The predictions endpoint returns full rows to free/anonymous users with fields stripped client-side. Game logs and history are fetched regardless of auth state. The backend must be the source of truth — if the user shouldn't see it, don't return it.

---

## Tier model after this refactor

| State | Who | Gets |
|---|---|---|
| No account / not logged in | Public | On the Radar predictions only. Player list. Track record. Status. Teaser counts. |
| Logged in (any account) | Subscriber | Everything. Full predictions, all tiers, favor, game logs, full history. |

Stripe is a later phase. For now, every registered user with a valid account is a subscriber. The `is_subscriber` flag on User defaults to `true` on registration. Stripe will flip it later. Do not build Stripe logic now.

---

## BACKEND CHANGES

### 1. Update the User model (`app/models/user.py`)

Replace the `tier` string field with a boolean `is_subscriber`. Keep `stripe_customer_id` for the future Stripe sprint.

```python
# Remove:
tier: Mapped[str] = mapped_column(String(20), nullable=False, server_default="free")

# Add:
is_subscriber: Mapped[bool] = mapped_column(
    Boolean, nullable=False, server_default="true"
)
```

Keep all other fields exactly as they are. `stripe_customer_id` stays.

### 2. New Alembic migration

Create `alembic/versions/0006_users_tier_to_subscriber.py`:

```python
"""Replace users.tier with users.is_subscriber.

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("users", sa.Column(
        "is_subscriber", sa.Boolean(), nullable=False, server_default="true"
    ))
    op.drop_column("users", "tier")

def downgrade():
    op.add_column("users", sa.Column(
        "tier", sa.String(20), nullable=False, server_default="free"
    ))
    op.drop_column("users", "is_subscriber")
```

### 3. Update `app/services/auth_service.py`

**JWT claims:** replace `tier` with `is_subscriber` in the access token payload.

```python
# In create_access_token:
payload = {
    "sub": str(user.id),
    "email": user.email,
    "is_subscriber": user.is_subscriber,   # was: "tier": user.tier
    "exp": expire,
}
```

**`create_user`:** set `is_subscriber=True` on new users (default subscription on registration).

```python
user = User(
    email=normalised,
    hashed_password=hash_password(password),
    is_subscriber=True,   # was: tier="free"
)
```

### 4. Update `app/api/auth.py`

**`MeResponse` schema:** replace `tier: str` with `is_subscriber: bool`.

```python
class MeResponse(BaseModel):
    id: str
    email: str
    is_subscriber: bool   # was: tier: str
    is_active: bool
```

**`/me` endpoint:** update the response construction.

```python
return MeResponse(
    id=str(current_user.id),
    email=current_user.email,
    is_subscriber=current_user.is_subscriber,
    is_active=current_user.is_active,
)
```

No other changes to `auth.py`.

### 5. Update `app/api/deps.py`

Replace `require_free` / `require_pro` with a single `require_subscriber` dependency. Keep `get_optional_user` and `require_auth` exactly as they are — they are correct.

```python
async def require_subscriber(user: User = Depends(require_auth)) -> User:
    """
    Allow only active subscribers.
    Raises HTTP 403 for authenticated non-subscriber users.
    Raises HTTP 401 (via require_auth) for unauthenticated requests.
    """
    if not user.is_subscriber:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active subscription required.",
        )
    return user
```

Remove `require_free` and `require_pro` entirely. Update all imports across the codebase that reference them.

### 6. Refactor `app/api/public.py` — predictions endpoint

This is the most important backend change. The endpoint must return different data shapes based on auth state. No CSS blur — the backend controls what data leaves the server.

**Update `PredictionsResponse` schema** to include teaser counts:

```python
class TeaserCounts(BaseModel):
    high_conviction: int
    value_play: int
    fade: int

class PredictionsResponse(BaseModel):
    season: int
    week: int
    count: int
    predictions: list[PredictionRow]
    teaser: TeaserCounts          # always present — counts for CTA display
    auth_required: bool = False   # remove this field — no longer needed
```

**Update the endpoint logic** — remove the old free/anon gating block and replace with clean subscriber gate:

```python
@router.get("/predictions/{season}/{week}", response_model=PredictionsResponse)
async def get_predictions(
    ...,
    current_user: Optional[User] = Depends(get_optional_user),
) -> PredictionsResponse:
    # ... existing DB query and tier assignment logic unchanged ...

    # Build teaser counts from the full result set (always computed)
    teaser = TeaserCounts(
        high_conviction=sum(1 for r in result if r.tier == "high_conviction"),
        value_play=sum(1 for r in result if r.tier == "value_play"),
        fade=sum(1 for r in result if r.tier in ("fade_volume_trap", "fade_overpriced")),
    )

    # Non-subscribers: return only On the Radar rows. Strip pro fields.
    is_subscriber = current_user is not None and current_user.is_subscriber
    if not is_subscriber:
        public_rows = [r for r in result if r.tier == "on_the_radar"]
        public_rows = [
            r.model_copy(update={
                "favor": None,
                "completeness_score": None,
            })
            for r in public_rows
        ]
        return PredictionsResponse(
            season=season,
            week=week,
            count=len(public_rows),
            predictions=public_rows,
            teaser=teaser,
        )

    # Subscribers: full payload
    return PredictionsResponse(
        season=season,
        week=week,
        count=len(result),
        predictions=result,
        teaser=teaser,
    )
```

**Update game logs endpoint** — require subscriber:

```python
@router.get("/players/{player_id}/game-logs", ...)
async def get_player_game_logs(
    player_id: str,
    season: Optional[int] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_subscriber),   # was: no auth
) -> GameLogsResponse:
    # body unchanged
```

**Update history endpoint** — subscriber gets full history; public gets empty list. Do not blur, do not send partial data with null fields:

```python
@router.get("/players/{player_id}/history", ...)
async def get_player_history(
    player_id: str,
    season: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
) -> list[HistoryRow]:
    if current_user is None or not current_user.is_subscriber:
        return []

    # ... existing query and response logic unchanged ...
```

**Odds endpoint** — stays public. No change needed.

### 7. Update `app/config.py`

The `JWT_SECRET_KEY` empty-string default needs a startup guard. Add this after the existing validators:

```python
from pydantic import model_validator

@model_validator(mode="after")
def validate_secrets(self) -> "Settings":
    import os
    if not self.JWT_SECRET_KEY and os.environ.get("PYTEST_CURRENT_TEST") is None:
        raise ValueError(
            "JWT_SECRET_KEY must be set — generate one with: openssl rand -hex 32"
        )
    return self
```

### 8. Rate limiting on auth routes (`app/api/auth.py`)

Add `@limiter.limit("5/minute")` to login and register, with `request: Request` as the first parameter. This is required by slowapi.

```python
from fastapi import Request
from app.main import limiter

@router.post("/auth/register", ...)
@limiter.limit("5/minute")
async def register(
    request: Request,        # MUST be first for slowapi
    body: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    ...

@router.post("/auth/login", ...)
@limiter.limit("5/minute")
async def login(
    request: Request,        # MUST be first for slowapi
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    ...
```

---

## FRONTEND CHANGES

### 9. Update `AuthUser` type and `AuthContext` (`contexts/AuthContext.tsx`)

Replace `tier: 'free' | 'pro'` with `is_subscriber: boolean` throughout. This is the single source of truth for auth state across the entire frontend.

```typescript
// types/auth.ts — create this file
export interface AuthUser {
  id: string;
  email: string;
  is_subscriber: boolean;
}
```

In `AuthContext.tsx`:
- Import `AuthUser` from `types/auth.ts` instead of defining it inline
- In `MeResponse` interface: replace `tier: 'free' | 'pro'` with `is_subscriber: boolean`
- In `hydrateUser`: set `user` as `{ id: me.id, email: me.email, is_subscriber: me.is_subscriber }`
- Remove all references to `tier` from this file

Export a `isSubscriber` derived boolean from the context value for convenience:

```typescript
export interface AuthContextValue {
  user: AuthUser | null;
  isLoading: boolean;
  isSubscriber: boolean;       // derived: user !== null && user.is_subscriber
  login: ...
  register: ...
  logout: ...
  refreshToken: ...
  getToken: ...
}

// In the provider:
const value: AuthContextValue = {
  user,
  isLoading,
  isSubscriber: user !== null && user.is_subscriber,
  ...
};
```

### 10. Update `hooks/useAuth.ts`

No structural change — it just re-exports the context. But add a convenience selector:

```typescript
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

// Convenience — avoids drilling isSubscriber through props
export function useIsSubscriber(): boolean {
  return useAuth().isSubscriber;
}
```

### 11. Update `types/backend.ts`

Add `TeaserCounts` and update `PredictionsApiResponse`:

```typescript
export interface TeaserCounts {
  high_conviction: number;
  value_play: number;
  fade: number;
}

export interface PredictionsApiResponse {
  season: number;
  week: number;
  count: number;
  predictions: PredictionResponse[];
  teaser: TeaserCounts;
  // remove auth_required — no longer returned
}
```

Remove `locked?: boolean` from `PredictionResponse` — it was a workaround for the old blur system.

### 12. Rewrite `PaywallGate` (`components/shared/PaywallGate.tsx`)

**Kill all blur.** The new `PaywallGate` does not render children for non-subscribers. It renders a CTA instead. This is the correct pattern — no data in the DOM.

```typescript
'use client';

import React from 'react';
import { Lock } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { useAuthModal } from '@/contexts/AuthModalContext';

interface PaywallGateProps {
  ctaTitle: string;
  ctaBody?: string;
  onGetAccess?: () => void;
  children: React.ReactNode;
}

export function PaywallGate({ ctaTitle, ctaBody, onGetAccess, children }: PaywallGateProps) {
  const { isSubscriber, isLoading, user } = useAuth();
  const { openRegister, openLogin } = useAuthModal();

  if (isLoading) return null;

  // Subscriber: render content directly, no wrapper
  if (isSubscriber) return <>{children}</>;

  // Non-subscriber: render CTA — never render children
  return (
    <div className="border border-sr-primary/20 bg-sr-primary/5 rounded-card p-8 text-center">
      <div className="flex justify-center mb-4">
        <div className="w-12 h-12 rounded-full bg-sr-primary/10 border border-sr-primary/30 flex items-center justify-center">
          <Lock className="w-5 h-5 text-sr-primary" />
        </div>
      </div>
      <h3 className="text-white text-base font-semibold mb-2">{ctaTitle}</h3>
      {ctaBody && (
        <p className="text-sr-text-muted text-sm mb-5 max-w-xs mx-auto">{ctaBody}</p>
      )}
      {user ? (
        // Logged in but not subscribed (future state — post-Stripe)
        <button
          type="button"
          onClick={onGetAccess ?? openRegister}
          className="bg-sr-primary text-white px-6 py-2.5 rounded-card text-sm font-semibold hover:bg-sr-primary/80 transition-colors"
        >
          Upgrade to unlock
        </button>
      ) : (
        // Not logged in
        <div className="flex flex-col items-center gap-2">
          <button
            type="button"
            onClick={onGetAccess ?? openRegister}
            className="bg-sr-primary text-white px-6 py-2.5 rounded-card text-sm font-semibold hover:bg-sr-primary/80 transition-colors"
          >
            Get Access
          </button>
          <button
            type="button"
            onClick={openLogin}
            className="text-xs text-sr-text-muted hover:text-white underline underline-offset-2"
          >
            Already have an account? Sign in
          </button>
        </div>
      )}
    </div>
  );
}
```

### 13. Rewrite `TierSection` (`components/weekly/TierSection.tsx`)

Remove `isPaywalled` prop entirely. `TierSection` no longer handles gating — it just renders cards. Gating is handled at the `WeeklyValue` level using `TeaserBanner`.

Create a new `TeaserBanner` component (`components/weekly/TeaserBanner.tsx`):

```typescript
'use client';

import { Lock } from 'lucide-react';
import { useAuthModal } from '@/contexts/AuthModalContext';

interface TeaserBannerProps {
  label: string;
  count: number;
  noun: string;          // e.g. "play" | "player"
  accentClass: string;
  headerTextClass: string;
  descriptor: string;
}

export function TeaserBanner({ label, count, noun, accentClass, headerTextClass, descriptor }: TeaserBannerProps) {
  const { openRegister, openLogin } = useAuthModal();
  const plural = count !== 1 ? `${noun}s` : noun;

  return (
    <section className="mb-8">
      <div className={`flex items-baseline gap-3 mb-3 pb-2 border-b ${accentClass}`}>
        <h2 className={`text-base font-semibold ${headerTextClass}`}>{label}</h2>
        <span className="text-sr-text-dim text-xs">{descriptor}</span>
      </div>
      <div className="border border-sr-primary/20 bg-sr-primary/5 rounded-card p-6 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Lock className="w-4 h-4 text-sr-primary flex-shrink-0" />
          <span className="text-white text-sm font-medium">
            {count} {plural} identified this week
          </span>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          <button
            onClick={openLogin}
            className="text-xs text-sr-text-muted hover:text-white underline underline-offset-2"
          >
            Sign in
          </button>
          <button
            onClick={openRegister}
            className="bg-sr-primary text-white px-4 py-2 rounded-card text-xs font-semibold hover:bg-sr-primary/80 transition-colors"
          >
            Get Access
          </button>
        </div>
      </div>
    </section>
  );
}
```

Updated `TierSection` — simplified, no paywall logic:

```typescript
interface TierSectionProps {
  tier: PredictionTier;
  label: string;
  descriptor: string;
  accentClass: string;
  headerTextClass: string;
  predictions: PredictionResponse[];
  startRank?: number;
  onPlayerClick?: (playerId: string) => void;
  children?: React.ReactNode;
}
// No isPaywalled, no ctaTitle, no ctaBody, no onGetAccess
```

### 14. Rewrite `WeeklyValue` (`components/weekly/WeeklyValue.tsx`)

Key changes:
- Read `isSubscriber` from `useAuth()` instead of `auth?.user?.tier === 'pro'`
- Use `teaser` counts from the API response for TeaserBanners
- Do not pass `isPaywalled` to TierSection — render TeaserBanner instead for locked sections
- Remove the `NEXT_PUBLIC_DEV_BYPASS_PAYWALL` env var reference — dev bypass is handled via the dev auto-login in AuthContext

```typescript
const { isSubscriber } = useAuth();

// In the predictions fetch response:
const [predictions, setPredictions] = useState<PredictionResponse[]>([]);
const [teaser, setTeaser] = useState<TeaserCounts | null>(null);

// After fetch:
setPredictions(data.predictions ?? []);
setTeaser(data.teaser ?? null);

// In render — replace isPaywalled TierSection with TeaserBanner:
{isSubscriber ? (
  <TierSection tier="high_conviction" label="High Conviction" ... predictions={tier1} />
) : (
  <TeaserBanner
    label="High Conviction"
    count={teaser?.high_conviction ?? 0}
    noun="play"
    accentClass="border-sr-success/40"
    headerTextClass="text-sr-success"
    descriptor="Model's highest-confidence plays this week."
  />
)}

{isSubscriber ? (
  <TierSection tier="value_play" label="Value Plays" ... predictions={tier2} />
) : (
  <TeaserBanner
    label="Value Plays"
    count={teaser?.value_play ?? 0}
    noun="play"
    accentClass="border-amber-500/40"
    headerTextClass="text-amber-400"
    descriptor="Positive edge, meaningful model confidence."
  />
)}

{/* On the Radar — always visible to everyone */}
<TierSection tier="on_the_radar" label="On the Radar" ... predictions={tier3} />

{isSubscriber ? (
  <TierSection tier="fade_volume_trap" label="Fade List" ... predictions={[...fades]} />
) : (
  <TeaserBanner
    label="Fade List"
    count={teaser?.fade ?? 0}
    noun="player"
    accentClass="border-sr-danger/40"
    headerTextClass="text-sr-danger"
    descriptor="Players the model is cold on."
  />
)}
```

### 15. Update `TierPlayerCard` (`components/weekly/TierPlayerCard.tsx`)

Remove ALL blur logic. Remove the `isSubscribed` prop. Remove the `devBypass` env var check. Remove the `showPaidFields` conditional entirely.

The card now always renders what it receives. Since non-subscribers only receive On the Radar rows with `favor: null` from the backend, the edge pill simply won't render (it checks `favor !== null` already). No code change needed for that — it works by data shape.

Simplify:
- Remove `isSubscribed?: boolean` prop
- Remove `devBypass` and `showPaidFields` variables
- Remove the blur `span` fallbacks — replace with the real value unconditionally
- The `favor` and `tier` fields will be `null` for public rows naturally

### 16. Update `PlayerModel` (`components/player-lookup/PlayerModel.tsx`)

- Replace `auth?.user?.tier === 'pro'` with `isSubscriber` from `useAuth()`
- **Gate the game-logs fetch:** only call the `/game-logs` endpoint if `isSubscriber`. If not subscribed, skip the fetch entirely — don't render the GameLogTable.
- **Gate the history fetch:** only call `/history` if `isSubscriber`. The backend returns an empty array for non-subscribers anyway, but don't make the call.
- **Gate the probability chart:** use `PaywallGate` wrapper (which no longer blurs — it shows CTA instead)
- Remove the `locked` field handling in the prediction response processing — it's gone

```typescript
const { isSubscriber } = useAuth();

// In Effect B (season data):
if (!isSubscriber) {
  // Skip game logs and history fetch for non-subscribers
  setSelectedPlayerData(prev => ({ ...prev, gameLogs: [], weeklyData: [] }));
  return;
}
// ... existing fetch logic ...

// Conditional render for GameLogTable:
{isSubscriber && selectedPlayerData?.gameLogs && selectedPlayerData.gameLogs.length > 0 && (
  <GameLogTable ... />
)}

// ProbabilityChart stays wrapped in PaywallGate — now shows CTA instead of blur
```

### 17. Update `GameLogTable` (`components/player-lookup/GameLogTable.tsx`)

Remove `isAuthenticated` and `isProUser` props entirely. The component is only rendered for subscribers now (gated at PlayerModel level). Remove the `showModelProb` function. The Model % column always shows the value — no conditional hiding needed.

```typescript
interface GameLogTableProps {
  data: GameLogRow[];
  currentWeek: number;
  // Remove: isAuthenticated and isProUser
}
```

The Model % cell becomes simply:
```typescript
<td>
  {game.modelProbability
    ? <span className="nums text-sr-primary">{game.modelProbability}%</span>
    : <span className="text-sr-text-dim">—</span>
  }
</td>
```

### 18. Update `HistoricalResultCard` (`components/player-lookup/HistoricalResultCard.tsx`)

Remove `isProUser` prop. Remove all blur on `modelProbability`. Remove the `Lock` icon overlay. This component is only rendered inside `PlayerModel` which is already subscriber-gated at the fetch level — so if it renders, the user is a subscriber.

```typescript
interface HistoricalResultCardProps {
  week: number;
  year: number;
  tier: string | null;
  modelProbability: number | null;
  td: boolean;
  edge: 'positive' | 'neutral' | 'negative';
  edgeValue: number | null;
  // Remove: isProUser
}
```

The model probability cell becomes:
```typescript
<span className="text-4xl text-white nums">
  {modelProbability !== null ? `${modelProbability}%` : '--'}
</span>
```

### 19. Update `PredictionSummary` (`components/player-lookup/PredictionSummary.tsx`)

Remove the `isLocked` / `locked` handling. The locked state existed to handle the old blur system. Now: if the user isn't a subscriber, `PlayerModel` won't call the predictions endpoint for pro data — the summary card simply won't show. Remove the locked branch entirely.

Keep the `isPredictionMissing` null-check branch — that's legitimate.

### 20. Fix the `PlayerWeekToggle` subscriber gate

In `PlayerModel.tsx`, the week toggle has `lockedToCurrentWeek={!isProUser}`. Update to:
```typescript
lockedToCurrentWeek={!isSubscriber}
```

---

## Files to create

```
frontend/types/auth.ts                              (new — AuthUser type)
frontend/components/weekly/TeaserBanner.tsx         (new — replaces isPaywalled CTA)
```

## Files to modify

```
backend_new/app/models/user.py
backend_new/app/services/auth_service.py
backend_new/app/api/auth.py
backend_new/app/api/deps.py
backend_new/app/api/public.py
backend_new/app/config.py
backend_new/alembic/versions/0006_users_tier_to_subscriber.py  (new migration)

frontend/contexts/AuthContext.tsx
frontend/hooks/useAuth.ts
frontend/types/backend.ts
frontend/components/shared/PaywallGate.tsx
frontend/components/weekly/WeeklyValue.tsx
frontend/components/weekly/TierSection.tsx
frontend/components/weekly/TierPlayerCard.tsx
frontend/components/player-lookup/PlayerModel.tsx
frontend/components/player-lookup/GameLogTable.tsx
frontend/components/player-lookup/HistoricalResultCard.tsx
frontend/components/player-lookup/PredictionSummary.tsx
```

## Files to leave alone

```
backend_new/app/api/admin.py          — admin auth is correct, no changes
backend_new/app/database.py           — no changes
backend_new/app/main.py               — no changes beyond rate limit fix already in scope
frontend/app/layout.tsx               — no changes
frontend/contexts/AuthModalContext.tsx — no changes
frontend/components/auth/*            — no changes
frontend/components/track-record/*    — fully public, no gating needed
frontend/components/shared/NavBar.tsx — no changes
```

---

## Correctness checklist — verify after implementation

- [ ] `alembic upgrade head` runs clean — `users` table has `is_subscriber bool` not `tier varchar`
- [ ] `POST /api/auth/register` returns `{ access_token, token_type }` and sets refresh cookie
- [ ] JWT decoded at jwt.io shows `is_subscriber: true` claim, no `tier` claim
- [ ] `GET /api/auth/me` returns `{ id, email, is_subscriber, is_active }` — no `tier` field
- [ ] `GET /api/predictions/2025/1` with no token: returns only `on_the_radar` rows + teaser counts, no High Conviction data
- [ ] `GET /api/predictions/2025/1` with subscriber token: returns all tiers
- [ ] `GET /api/players/{id}/game-logs` with no token: 401
- [ ] `GET /api/players/{id}/game-logs` with subscriber token: 200 with data
- [ ] `GET /api/players/{id}/history` with no token: 200 empty array
- [ ] Frontend: DevTools inspection of DOM for non-subscriber — no prediction data in any element, blurred or otherwise
- [ ] Frontend: `useAuth().isSubscriber` is the only subscription check used across all components — no `tier === 'pro'` strings anywhere
- [ ] `NEXT_PUBLIC_DEV_BYPASS_PAYWALL` env var is removed from TierPlayerCard — dev testing uses `NEXT_PUBLIC_DEV_USER_EMAIL` / `NEXT_PUBLIC_DEV_USER_PASSWORD` auto-login in AuthContext instead

---

## Stripe note (do not implement now)

When Stripe is added later, the only change needed is:
1. Stripe webhook handler sets `user.is_subscriber = True/False` based on subscription status
2. JWT refresh picks up the new claim automatically on next `/auth/refresh` call
3. No frontend changes needed — `isSubscriber` already reads this claim

The column, the JWT claim, and the frontend hook are all already named correctly for this.
