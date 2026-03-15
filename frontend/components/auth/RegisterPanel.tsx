'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';

interface RegisterPanelProps {
  onSuccess: () => void;
  onSwitchToLogin: () => void;
}

export function RegisterPanel({ onSuccess, onSwitchToLogin }: RegisterPanelProps) {
  const { register } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isEmailExists, setIsEmailExists] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const emailRef = useRef<HTMLInputElement>(null);

  // Focus email on mount
  useEffect(() => {
    const timer = setTimeout(() => {
      emailRef.current?.focus();
    }, 50);
    return () => clearTimeout(timer);
  }, []);

  function validateClientSide(): string | null {
    if (!email) return 'Email is required.';
    if (!/\S+@\S+\.\S+/.test(email)) return 'Please enter a valid email address.';
    if (password.length < 8) return 'Password must be at least 8 characters.';
    if (password !== confirmPassword) return 'Passwords do not match.';
    return null;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsEmailExists(false);

    const clientError = validateClientSide();
    if (clientError) {
      setError(clientError);
      return;
    }

    setIsSubmitting(true);
    try {
      await register(email, password);
      onSuccess();
    } catch (err) {
      const msg = (err as Error).message || 'Registration failed. Please try again.';
      if (msg.toLowerCase().includes('already') || msg.toLowerCase().includes('exists')) {
        setIsEmailExists(true);
        setError('An account with this email already exists.');
      } else {
        setError(msg);
      }
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
              htmlFor="register-panel-email"
              className="block text-sm text-sr-text-muted mb-1.5"
            >
              Email
            </label>
            <input
              id="register-panel-email"
              ref={emailRef}
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                if (isEmailExists) {
                  setIsEmailExists(false);
                  setError(null);
                }
              }}
              className="bg-sr-bg border border-sr-border rounded-lg px-3 py-2 text-sr-text-primary w-full focus:outline-none focus:ring-2 focus:ring-sr-primary focus:border-sr-primary transition-colors"
              placeholder="you@example.com"
              disabled={isSubmitting}
            />
          </div>

          <div>
            <label
              htmlFor="register-panel-password"
              className="block text-sm text-sr-text-muted mb-1.5"
            >
              Password
            </label>
            <div className="relative">
              <input
                id="register-panel-password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="new-password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="bg-sr-bg border border-sr-border rounded-lg px-3 py-2 pr-10 text-sr-text-primary w-full focus:outline-none focus:ring-2 focus:ring-sr-primary focus:border-sr-primary transition-colors"
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
                {showPassword ? (
                  <EyeOff size={16} aria-hidden="true" />
                ) : (
                  <Eye size={16} aria-hidden="true" />
                )}
              </button>
            </div>
          </div>

          <div>
            <label
              htmlFor="register-panel-confirm-password"
              className="block text-sm text-sr-text-muted mb-1.5"
            >
              Confirm Password
            </label>
            <div className="relative">
              <input
                id="register-panel-confirm-password"
                type={showConfirmPassword ? 'text' : 'password'}
                autoComplete="new-password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="bg-sr-bg border border-sr-border rounded-lg px-3 py-2 pr-10 text-sr-text-primary w-full focus:outline-none focus:ring-2 focus:ring-sr-primary focus:border-sr-primary transition-colors"
                placeholder="Repeat password"
                disabled={isSubmitting}
              />
              <button
                type="button"
                onClick={() => setShowConfirmPassword((v) => !v)}
                className="absolute inset-y-0 right-0 flex items-center px-3 text-sr-text-muted hover:text-sr-text-primary transition-colors"
                aria-label={showConfirmPassword ? 'Hide confirm password' : 'Show confirm password'}
                tabIndex={-1}
              >
                {showConfirmPassword ? (
                  <EyeOff size={16} aria-hidden="true" />
                ) : (
                  <Eye size={16} aria-hidden="true" />
                )}
              </button>
            </div>
          </div>
        </div>

        {error && (
          <div
            className="text-sr-danger text-sm mt-3"
            role="alert"
            aria-live="polite"
          >
            <p>{error}</p>
            {isEmailExists && (
              <button
                type="button"
                onClick={onSwitchToLogin}
                className="text-sr-primary hover:text-sr-primary-muted transition-colors font-medium underline underline-offset-2 mt-1"
              >
                Sign in instead?
              </button>
            )}
          </div>
        )}

        <button
          type="submit"
          disabled={isSubmitting}
          className="bg-sr-primary text-white px-6 py-2.5 rounded-card font-semibold hover:bg-sr-primary-muted transition-colors w-full mt-5 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {isSubmitting ? 'Creating account...' : 'Create Account'}
        </button>
      </form>

      <p className="text-center text-sm text-sr-text-muted mt-4">
        Already have an account?{' '}
        <button
          type="button"
          onClick={onSwitchToLogin}
          className="text-sr-primary hover:text-sr-primary-muted transition-colors font-medium"
        >
          Sign in
        </button>
      </p>
    </div>
  );
}
