'use client';

import React, { useEffect, useRef, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Eye, EyeOff } from 'lucide-react';
import { NavBar } from '../../components/shared/NavBar';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const inputCls =
  'bg-sr-bg border border-sr-border rounded-lg px-3 py-2 text-sr-text-primary w-full focus:outline-none focus:ring-2 focus:ring-sr-primary focus:border-sr-primary transition-colors disabled:opacity-50';

type Tab = 'weekly' | 'player' | 'track';
type PageState = 'form' | 'success' | 'no-token';

// ---------------------------------------------------------------------------
// Inner component — uses useSearchParams, must be inside Suspense
// ---------------------------------------------------------------------------

function ResetPasswordContent() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const rawToken = searchParams.get('token');

  const [currentWeek, setCurrentWeek] = useState<number | null>(null);
  const [pageState, setPageState] = useState<PageState>(rawToken ? 'form' : 'no-token');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const passwordRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    async function fetchWeek() {
      try {
        const resp = await fetch(`${API_URL}/api/status/week`);
        if (!resp.ok) return;
        const data = await resp.json();
        setCurrentWeek(data.week ?? null);
      } catch {
        // currentWeek handles null gracefully
      }
    }
    fetchWeek();
  }, []);

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
    <div className="min-h-screen bg-sr-bg">
      <NavBar activeTab="weekly" onTabChange={(tab) => router.push(`/?tab=${tab}`)} currentWeek={currentWeek} />
      <div className="flex items-center justify-center px-4 py-16">
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
