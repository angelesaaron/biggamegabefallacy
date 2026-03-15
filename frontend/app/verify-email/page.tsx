'use client';

import React, { useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '../../hooks/useAuth';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const TOKEN_KEY = 'bggtdm_access_token';

interface TokenResponse {
  access_token: string;
  token_type: string;
}

type VerifyState = 'loading' | 'success' | 'error' | 'no-token';

export default function VerifyEmailPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { refreshUser } = useAuth();

  const [state, setState] = useState<VerifyState>('loading');
  const [errorMessage, setErrorMessage] = useState<string>('');

  // Guard against double-run in React StrictMode
  const hasRun = useRef(false);

  useEffect(() => {
    if (hasRun.current) return;
    hasRun.current = true;

    const token = searchParams.get('token');

    if (!token) {
      setState('no-token');
      return;
    }

    async function verify() {
      try {
        // Read any existing access token for the auth header
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
          body: JSON.stringify({ token }),
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

        // The endpoint returns a new JWT — store it, then refresh user state
        try {
          const data = await res.json() as TokenResponse;
          if (data?.access_token) {
            try {
              localStorage.setItem(TOKEN_KEY, data.access_token);
            } catch { /* ignore */ }
          }
        } catch { /* ignore — response may be 204 */ }

        await refreshUser();
        setState('success');

        // Redirect to account after 2 seconds
        setTimeout(() => {
          router.replace('/account');
        }, 2000);
      } catch {
        setErrorMessage('An unexpected error occurred. Please try again.');
        setState('error');
      }
    }

    verify();
  }, [searchParams, refreshUser, router]);

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
