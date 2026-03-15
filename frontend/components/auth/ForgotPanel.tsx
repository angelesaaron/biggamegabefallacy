'use client';

import React, { useEffect, useRef, useState } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface ForgotPanelProps {
  onBack: () => void;
}

export function ForgotPanel({ onBack }: ForgotPanelProps) {
  const [email, setEmail] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const emailRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      emailRef.current?.focus();
    }, 50);
    return () => clearTimeout(timer);
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const res = await fetch(`${API_URL}/api/auth/forgot-password`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });

      // Always show the same success message — never reveal if the email exists
      if (res.ok || res.status === 404 || res.status === 400) {
        setSubmitted(true);
      } else {
        let message = 'Something went wrong. Please try again.';
        try {
          const body = await res.json();
          if (body?.detail && typeof body.detail === 'string') {
            message = body.detail;
          }
        } catch { /* ignore */ }
        setError(message);
      }
    } catch {
      setError('Unable to send the request. Check your connection and try again.');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="px-6 pb-6 pt-4">
      {/* Back navigation */}
      <button
        type="button"
        onClick={onBack}
        className="flex items-center gap-1.5 text-sm text-sr-text-muted hover:text-white transition-colors mb-4"
        aria-label="Back to Sign In"
      >
        <span aria-hidden="true">&#8592;</span>
        Back to Sign In
      </button>

      <h2 className="text-white font-semibold text-base mb-1">Reset your password</h2>
      <p className="text-sr-text-muted text-sm mb-4">
        Enter your email and we&apos;ll send you a reset link if an account exists.
      </p>

      {submitted ? (
        <div
          className="rounded-lg bg-emerald-900/30 border border-sr-success/30 px-4 py-3 text-sm text-sr-success"
          role="status"
          aria-live="polite"
        >
          Check your email for a reset link.
        </div>
      ) : (
        <form onSubmit={handleSubmit} noValidate>
          <div>
            <label
              htmlFor="forgot-panel-email"
              className="block text-sm text-sr-text-muted mb-1.5"
            >
              Email
            </label>
            <input
              id="forgot-panel-email"
              ref={emailRef}
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="bg-sr-bg border border-sr-border rounded-lg px-3 py-2 text-sr-text-primary w-full focus:outline-none focus:ring-2 focus:ring-sr-primary focus:border-sr-primary transition-colors"
              placeholder="you@example.com"
              disabled={isSubmitting}
            />
          </div>

          {error && (
            <p
              className="text-sr-danger text-sm mt-3"
              role="alert"
              aria-live="polite"
            >
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={isSubmitting || !email}
            className="bg-sr-primary text-white px-6 py-2.5 rounded-card font-semibold hover:bg-sr-primary-muted transition-colors w-full mt-5 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {isSubmitting ? 'Sending...' : 'Send Reset Link'}
          </button>
        </form>
      )}
    </div>
  );
}
