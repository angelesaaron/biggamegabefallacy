# Email Verification Pages — Fix

Read every section before writing a single line of code. Scope is precise.

---

## What's broken and why

Both `/verify-email` and `/reset-password` pages exist and the code logic is correct. The pages fail because **Next.js 14 App Router requires any component using `useSearchParams()` to be wrapped in a `<Suspense>` boundary**. Without it, Next.js throws during rendering — the page either shows a blank screen or a build error depending on the environment.

This is not optional in Next.js 14. `useSearchParams()` is a dynamic API that opts the page into client-side rendering. Without Suspense, Next.js cannot statically render a fallback shell and the route breaks.

The fix is the same pattern for both pages: extract the component body into an inner component, wrap it in Suspense at the page export level.

There is one additional bug in `verify-email/page.tsx`: the `useEffect` dependency array includes `searchParams` as an object, which changes reference on every render and can cause the effect to re-fire. Use `searchParams.get('token')` as a stable string dependency instead.

---

## Fix 1 — `app/verify-email/page.tsx`

Full rewrite using the Suspense pattern. The logic is unchanged — only the structure changes.

```tsx
'use client';

import React, { useEffect, useRef, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '../../hooks/useAuth';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const TOKEN_KEY = 'bggtdm_access_token';

interface TokenResponse {
  access_token: string;
  token_type: string;
}

type VerifyState = 'loading' | 'success' | 'error' | 'no-token';

// ---------------------------------------------------------------------------
// Inner component — uses useSearchParams, must be inside Suspense
// ---------------------------------------------------------------------------

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { refreshUser } = useAuth();

  const rawToken = searchParams.get('token');

  const [state, setState] = useState<VerifyState>(rawToken ? 'loading' : 'no-token');
  const [errorMessage, setErrorMessage] = useState<string>('');

  // Guard against double-run in React StrictMode
  const hasRun = useRef(false);

  useEffect(() => {
    if (!rawToken) {
      setState('no-token');
      return;
    }

    if (hasRun.current) return;
    hasRun.current = true;

    async function verify() {
      try {
        let authToken: string | null = null;
        try {
          authToken = localStorage.getItem(TOKEN_KEY);
        } catch { /* localStorage unavailable */ }

        const headers: Record<string, string> = {
          'Content-Type': 'application/json',
        };
        if (authToken) {
          headers['Authorization'] = `Bearer ${authToken}`;
        }

        const res = await fetch(`${API_URL}/api/users/me/verify-email`, {
          method: 'POST',
          credentials: 'include',
          headers,
          body: JSON.stringify({ token: rawToken }),
        });

        if (!res.ok) {
          let message = 'Verification failed. The link may have expired or already been used.';
          try {
            const body = await res.json();
            if (body?.detail && typeof body.detail === 'string') {
              message = body.detail;
            }
          } catch { /* ignore */ }
          setErrorMessage(message);
          setState('error');
          return;
        }

        try {
          const data = await res.json() as TokenResponse;
          if (data?.access_token) {
            try {
              localStorage.setItem(TOKEN_KEY, data.access_token);
            } catch { /* ignore */ }
          }
        } catch { /* 204 or non-JSON — ignore */ }

        await refreshUser();
        setState('success');

        setTimeout(() => {
          router.replace('/account');
        }, 2000);
      } catch {
        setErrorMessage('An unexpected error occurred. Please try again.');
        setState('error');
      }
    }

    verify();
  // rawToken is a stable string — safe as a dependency
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rawToken]);

  return (
    <div className="min-h-screen bg-sr-bg flex items-center justify-center px-4">
      <div className="bg-sr-surface border border-sr-border rounded-card p-8 w-full max-w-sm text-center">

        {state === 'loading' && (
          <>
            <div className="w-10 h-10 rounded-full border-2 border-sr-primary border-t-transparent animate-spin mx-auto mb-4" aria-hidden="true" />
            <p className="text-white font-semibold mb-1">Verifying your email</p>
            <p className="text-sm text-sr-text-muted">Just a moment&hellip;</p>
          </>
        )}

        {state === 'success' && (
          <>
            <div className="w-10 h-10 rounded-full bg-emerald-900/40 flex items-center justify-center mx-auto mb-4" aria-hidden="true">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                <path d="M4 10l4 4 8-8" stroke="#10b981" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <p className="text-white font-semibold mb-1">Email updated successfully!</p>
            <p className="text-sm text-sr-text-muted">Redirecting you to your account&hellip;</p>
          </>
        )}

        {state === 'error' && (
          <>
            <div className="w-10 h-10 rounded-full bg-red-900/30 flex items-center justify-center mx-auto mb-4" aria-hidden="true">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                <path d="M6 6l8 8M14 6l-8 8" stroke="#f43f5e" strokeWidth="2" strokeLinecap="round" />
              </svg>
            </div>
            <p className="text-white font-semibold mb-1">Verification failed</p>
            <p className="text-sm text-sr-text-muted mb-4">{errorMessage}</p>
            <button
              type="button"
              onClick={() => router.replace('/account')}
              className="text-sm text-sr-primary hover:text-sr-primary-muted transition-colors font-medium"
            >
              Go to My Account
            </button>
          </>
        )}

        {state === 'no-token' && (
          <>
            <p className="text-white font-semibold mb-1">Invalid link</p>
            <p className="text-sm text-sr-text-muted mb-4">
              This verification link is missing required information. Please use the link sent to your email.
            </p>
            <button
              type="button"
              onClick={() => router.replace('/')}
              className="text-sm text-sr-primary hover:text-sr-primary-muted transition-colors font-medium"
            >
              Go home
            </button>
          </>
        )}

      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page export — Suspense boundary required by Next.js 14 for useSearchParams
// ---------------------------------------------------------------------------

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-sr-bg flex items-center justify-center px-4">
        <div className="bg-sr-surface border border-sr-border rounded-card p-8 w-full max-w-sm text-center">
          <div className="w-10 h-10 rounded-full border-2 border-sr-primary border-t-transparent animate-spin mx-auto mb-4" aria-hidden="true" />
          <p className="text-white font-semibold mb-1">Loading&hellip;</p>
        </div>
      </div>
    }>
      <VerifyEmailContent />
    </Suspense>
  );
}
```

---

## Fix 2 — `app/reset-password/page.tsx`

Same Suspense pattern. The `token` is read from `useSearchParams` in the inner component.

One additional fix: the current code initialises `pageState` as `token ? 'form' : 'no-token'` at the module level before the component renders, which doesn't work correctly because `useSearchParams` can only be called inside a component. With the new structure, initialise state after reading `searchParams` inside the component.

```tsx
'use client';

import React, { useEffect, useRef, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Eye, EyeOff } from 'lucide-react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const inputCls =
  'bg-sr-bg border border-sr-border rounded-lg px-3 py-2 text-sr-text-primary w-full focus:outline-none focus:ring-2 focus:ring-sr-primary focus:border-sr-primary transition-colors disabled:opacity-50';

type PageState = 'form' | 'success' | 'no-token';

// ---------------------------------------------------------------------------
// Inner component — uses useSearchParams, must be inside Suspense
// ---------------------------------------------------------------------------

function ResetPasswordContent() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const rawToken = searchParams.get('token');

  const [pageState, setPageState] = useState<PageState>(rawToken ? 'form' : 'no-token');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const passwordRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (pageState === 'form') {
      const timer = setTimeout(() => passwordRef.current?.focus(), 50);
      return () => clearTimeout(timer);
    }
  }, [pageState]);

  useEffect(() => {
    if (pageState !== 'success') return;
    const timer = setTimeout(() => {
      router.replace('/');
    }, 2500);
    return () => clearTimeout(timer);
  }, [pageState, router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await fetch(`${API_URL}/api/auth/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: rawToken, new_password: newPassword }),
      });

      if (!res.ok) {
        let message = 'Password reset failed. The link may have expired or already been used.';
        try {
          const body = await res.json();
          if (body?.detail && typeof body.detail === 'string') {
            message = body.detail;
          }
        } catch { /* ignore */ }
        setError(message);
        return;
      }

      setPageState('success');
    } catch {
      setError('An unexpected error occurred. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-sr-bg flex items-center justify-center px-4">
      <div className="bg-sr-surface border border-sr-border rounded-card p-8 w-full max-w-sm">

        {pageState === 'no-token' && (
          <div className="text-center">
            <p className="text-white font-semibold mb-1">Invalid link</p>
            <p className="text-sm text-sr-text-muted mb-4">
              This reset link is missing required information. Please use the link sent to your email.
            </p>
            <button
              type="button"
              onClick={() => router.replace('/')}
              className="text-sm text-sr-primary hover:text-sr-primary-muted transition-colors font-medium"
            >
              Go home
            </button>
          </div>
        )}

        {pageState === 'success' && (
          <div className="text-center">
            <div className="w-10 h-10 rounded-full bg-emerald-900/40 flex items-center justify-center mx-auto mb-4" aria-hidden="true">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                <path d="M4 10l4 4 8-8" stroke="#10b981" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <p className="text-white font-semibold mb-1">Password reset!</p>
            <p className="text-sm text-sr-text-muted">
              Signing you in with your new password. Redirecting&hellip;
            </p>
          </div>
        )}

        {pageState === 'form' && (
          <>
            <h1 className="text-white font-semibold text-base mb-1">Set a new password</h1>
            <p className="text-sm text-sr-text-muted mb-5">
              Choose a new password for your account.
            </p>

            <form onSubmit={handleSubmit} noValidate>
              <div className="space-y-4">
                <div>
                  <label htmlFor="reset-new-pw" className="block text-sm text-sr-text-muted mb-1.5">
                    New password
                  </label>
                  <div className="relative">
                    <input
                      id="reset-new-pw"
                      ref={passwordRef}
                      type={showPassword ? 'text' : 'password'}
                      autoComplete="new-password"
                      required
                      minLength={8}
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      className={`${inputCls} pr-10`}
                      placeholder="Min. 8 characters"
                      disabled={isSubmitting}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((v) => !v)}
                      className="absolute inset-y-0 right-0 flex items-center px-3 text-sr-text-muted hover:text-sr-text-primary transition-colors"
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                      tabIndex={-1}
                    >
                      {showPassword ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}
                    </button>
                  </div>
                </div>

                <div>
                  <label htmlFor="reset-confirm-pw" className="block text-sm text-sr-text-muted mb-1.5">
                    Confirm new password
                  </label>
                  <div className="relative">
                    <input
                      id="reset-confirm-pw"
                      type={showConfirm ? 'text' : 'password'}
                      autoComplete="new-password"
                      required
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      className={`${inputCls} pr-10`}
                      placeholder="Repeat new password"
                      disabled={isSubmitting}
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirm((v) => !v)}
                      className="absolute inset-y-0 right-0 flex items-center px-3 text-sr-text-muted hover:text-sr-text-primary transition-colors"
                      aria-label={showConfirm ? 'Hide confirm password' : 'Show confirm password'}
                      tabIndex={-1}
                    >
                      {showConfirm ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}
                    </button>
                  </div>
                </div>
              </div>

              {error && (
                <p className="text-sm text-sr-danger mt-3" role="alert" aria-live="polite">
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={isSubmitting}
                className="bg-sr-primary text-white px-6 py-2.5 rounded-card font-semibold hover:bg-sr-primary-muted transition-colors w-full mt-5 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {isSubmitting ? 'Resetting...' : 'Reset Password'}
              </button>
            </form>
          </>
        )}

      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page export — Suspense boundary required by Next.js 14 for useSearchParams
// ---------------------------------------------------------------------------

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-sr-bg flex items-center justify-center px-4">
        <div className="bg-sr-surface border border-sr-border rounded-card p-8 w-full max-w-sm text-center">
          <div className="w-10 h-10 rounded-full border-2 border-sr-primary border-t-transparent animate-spin mx-auto mb-4" aria-hidden="true" />
          <p className="text-white font-semibold mb-1">Loading&hellip;</p>
        </div>
      </div>
    }>
      <ResetPasswordContent />
    </Suspense>
  );
}
```

---

## Fix 3 — `app/page.tsx` needs the same Suspense treatment

`app/page.tsx` will need `useSearchParams` added (per the nav fixes prompt) to read `?tab=`. Apply the same pattern there too when implementing that change — wrap the inner content in Suspense. The `page.tsx` rewrite should look like:

```tsx
'use client';

import { useState, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { NavBar } from '@/components/shared/NavBar';
import { WeeklyValue } from '@/components/weekly/WeeklyValue';
import { PlayerModel } from '@/components/player-lookup/PlayerModel';
import { TrackRecord } from '@/components/track-record/TrackRecord';
import { useCurrentWeek } from '@/hooks/useCurrentWeek';

type Tab = 'weekly' | 'player' | 'track';
const VALID_TABS: Tab[] = ['weekly', 'player', 'track'];

function HomeContent() {
  const searchParams = useSearchParams();
  const initialTab = (VALID_TABS.find(t => t === searchParams.get('tab')) ?? 'weekly') as Tab;

  const [activeTab, setActiveTab] = useState<Tab>(initialTab);
  const [selectedPlayerId, setSelectedPlayerId] = useState<string | null>(null);
  const { week: currentWeek, season: currentYear } = useCurrentWeek();

  const handlePlayerClick = (playerId: string) => {
    setSelectedPlayerId(playerId);
    setActiveTab('player');
  };

  return (
    <div className="min-h-screen bg-sr-bg">
      <NavBar activeTab={activeTab} onTabChange={setActiveTab} currentWeek={currentWeek} />
      <main>
        {activeTab === 'weekly' && (
          <WeeklyValue
            currentWeek={currentWeek}
            currentYear={currentYear}
            onPlayerClick={handlePlayerClick}
          />
        )}
        {activeTab === 'player' && (
          <PlayerModel
            initialPlayerId={selectedPlayerId}
            currentWeek={currentWeek}
            currentYear={currentYear}
          />
        )}
        {activeTab === 'track' && <TrackRecord />}
      </main>
    </div>
  );
}

export default function Home() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-sr-bg flex items-center justify-center">
        <div className="w-8 h-8 rounded-full border-2 border-sr-primary border-t-transparent animate-spin" />
      </div>
    }>
      <HomeContent />
    </Suspense>
  );
}
```

---

## Files to modify

```
frontend/app/verify-email/page.tsx      ← Suspense wrapper + rawToken dep fix
frontend/app/reset-password/page.tsx    ← Suspense wrapper
frontend/app/page.tsx                   ← Suspense wrapper + ?tab param reading
```

## Files to leave alone

Everything else. Backend is correct — `account_service`, `email_service`, `users.py`, `auth.py` are all fine. Do not touch them.

---

## Why the backend is not the problem

- `FRONTEND_URL` in config correctly drives the URL in the reset/verify emails
- `account_service.initiate_email_change` builds `{FRONTEND_URL}/verify-email?token={raw}` ✓
- `account_service.initiate_password_reset` builds `{FRONTEND_URL}/reset-password?token={raw}` ✓
- Token hashing, TTLs, single-use enforcement, and DB writes are all correct
- Email templates are complete and wired to Resend

The entire problem is the missing Suspense boundary on the frontend pages.

---

## Correctness checklist

- [ ] `next build` completes with no errors referencing `useSearchParams` or Suspense
- [ ] Navigating to `/verify-email` with no token shows the "Invalid link" state — not a blank page or error
- [ ] Navigating to `/reset-password` with no token shows the "Invalid link" state — not a blank page or error
- [ ] Clicking a password reset link from email → `/reset-password?token=X` → form renders → submit succeeds → redirects to `/`
- [ ] Clicking an email verification link → `/verify-email?token=X` → spinner → success → redirects to `/account`
- [ ] Expired or already-used token on either page → error state with clear message, not a crash
- [ ] `/?tab=player` loads the app with Player Lookup active
- [ ] `/?tab=track` loads the app with Track Record active
- [ ] `/` with no param loads with This Week active — unchanged default behavior
