'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';

interface LoginPanelProps {
  onSuccess: () => void;
  onSwitchToRegister: () => void;
  onForgotPassword: () => void;
}

export function LoginPanel({ onSuccess, onSwitchToRegister, onForgotPassword }: LoginPanelProps) {
  const { login } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const emailRef = useRef<HTMLInputElement>(null);

  // Focus email on mount
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
      await login(email, password);
      onSuccess();
    } catch (err) {
      setError((err as Error).message || 'Login failed. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="px-6 pb-6 pt-4">
      <form onSubmit={handleSubmit} noValidate>
        <div className="space-y-4">
          <div>
            <label
              htmlFor="login-panel-email"
              className="block text-sm text-sr-text-muted mb-1.5"
            >
              Email
            </label>
            <input
              id="login-panel-email"
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

          <div>
            <label
              htmlFor="login-panel-password"
              className="block text-sm text-sr-text-muted mb-1.5"
            >
              Password
            </label>
            <div className="relative">
              <input
                id="login-panel-password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="bg-sr-bg border border-sr-border rounded-lg px-3 py-2 pr-10 text-sr-text-primary w-full focus:outline-none focus:ring-2 focus:ring-sr-primary focus:border-sr-primary transition-colors"
                placeholder="Password"
                disabled={isSubmitting}
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="absolute inset-y-0 right-0 flex items-center px-3 text-sr-text-muted hover:text-sr-text-primary transition-colors"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                tabIndex={-1}
              >
                {showPassword ? (
                  <EyeOff size={16} aria-hidden="true" />
                ) : (
                  <Eye size={16} aria-hidden="true" />
                )}
              </button>
            </div>
          </div>

          {/* Forgot password link */}
          <div className="flex justify-end mt-1.5">
            <button
              type="button"
              onClick={onForgotPassword}
              className="text-xs text-sr-text-muted hover:text-sr-primary transition-colors"
            >
              Forgot your password?
            </button>
          </div>
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
          disabled={isSubmitting}
          className="bg-sr-primary text-white px-6 py-2.5 rounded-card font-semibold hover:bg-sr-primary-muted transition-colors w-full mt-5 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {isSubmitting ? 'Signing in...' : 'Sign In'}
        </button>
      </form>

      <p className="text-center text-sm text-sr-text-muted mt-4">
        Don&apos;t have an account?{' '}
        <button
          type="button"
          onClick={onSwitchToRegister}
          className="text-sr-primary hover:text-sr-primary-muted transition-colors font-medium"
        >
          Create one
        </button>
      </p>
    </div>
  );
}
