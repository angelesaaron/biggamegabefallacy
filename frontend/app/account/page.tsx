'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '../../hooks/useAuth';
import { useAccount } from '../../hooks/useAccount';
import { NavBar } from '../../components/shared/NavBar';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? '';
type Tab = 'weekly' | 'player' | 'track';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatMemberSince(iso: string): string {
  try {
    const date = new Date(iso);
    return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  } catch {
    return iso;
  }
}

// ---------------------------------------------------------------------------
// Shared style tokens
// ---------------------------------------------------------------------------

const inputCls =
  'bg-sr-bg border border-sr-border rounded-lg px-3 py-2 text-sr-text-primary w-full focus:outline-none focus:ring-2 focus:ring-sr-primary focus:border-sr-primary transition-colors disabled:opacity-50';

const primaryBtnCls =
  'bg-sr-primary text-white px-6 py-2.5 rounded-card font-semibold hover:bg-sr-primary-muted transition-colors disabled:opacity-60 disabled:cursor-not-allowed';

const dangerBtnCls =
  'bg-sr-danger text-white px-6 py-2.5 rounded-card font-semibold hover:opacity-90 transition-colors disabled:opacity-60 disabled:cursor-not-allowed';

// ---------------------------------------------------------------------------
// Card 1: Profile
// ---------------------------------------------------------------------------

function ProfileCard() {
  const { user } = useAuth();
  const { updateName, initiateEmailChange } = useAccount();

  const [firstName, setFirstName] = useState(user?.first_name ?? '');
  const [lastName, setLastName] = useState(user?.last_name ?? '');
  const [nameLoading, setNameLoading] = useState(false);
  const [nameSuccess, setNameSuccess] = useState(false);
  const [nameError, setNameError] = useState<string | null>(null);

  const [showEmailForm, setShowEmailForm] = useState(false);
  const [newEmail, setNewEmail] = useState('');
  const [emailLoading, setEmailLoading] = useState(false);
  const [emailSuccess, setEmailSuccess] = useState<string | null>(null);
  const [emailError, setEmailError] = useState<string | null>(null);

  // Keep fields in sync if user refreshes
  useEffect(() => {
    setFirstName(user?.first_name ?? '');
    setLastName(user?.last_name ?? '');
  }, [user]);

  async function handleSaveName(e: React.FormEvent) {
    e.preventDefault();
    setNameError(null);
    setNameSuccess(false);
    setNameLoading(true);
    try {
      await updateName(firstName, lastName);
      setNameSuccess(true);
    } catch (err) {
      setNameError((err as Error).message || 'Failed to update name.');
    } finally {
      setNameLoading(false);
    }
  }

  async function handleSendVerification(e: React.FormEvent) {
    e.preventDefault();
    setEmailError(null);
    setEmailSuccess(null);
    setEmailLoading(true);
    try {
      await initiateEmailChange(newEmail);
      setEmailSuccess(newEmail);
      setNewEmail('');
      setShowEmailForm(false);
    } catch (err) {
      setEmailError((err as Error).message || 'Failed to send verification email.');
    } finally {
      setEmailLoading(false);
    }
  }

  if (!user) return null;

  return (
    <section className="bg-sr-surface border border-sr-border rounded-card p-6">
      <h2 className="text-white font-semibold text-base mb-4">Profile</h2>

      <form onSubmit={handleSaveName} noValidate>
        {/* Name row */}
        <div className="flex flex-col sm:flex-row gap-3 mb-4">
          <div className="flex-1">
            <label htmlFor="acc-first-name" className="block text-sm text-sr-text-muted mb-1.5">
              First name
            </label>
            <input
              id="acc-first-name"
              type="text"
              autoComplete="given-name"
              value={firstName}
              onChange={(e) => { setFirstName(e.target.value); setNameSuccess(false); }}
              className={inputCls}
              disabled={nameLoading}
              placeholder="First"
            />
          </div>
          <div className="flex-1">
            <label htmlFor="acc-last-name" className="block text-sm text-sr-text-muted mb-1.5">
              Last name
            </label>
            <input
              id="acc-last-name"
              type="text"
              autoComplete="family-name"
              value={lastName}
              onChange={(e) => { setLastName(e.target.value); setNameSuccess(false); }}
              className={inputCls}
              disabled={nameLoading}
              placeholder="Last"
            />
          </div>
        </div>

        {/* Email row */}
        <div className="mb-4">
          <p className="text-sm text-sr-text-muted mb-1">Email</p>
          <div className="flex items-center gap-3">
            <span className="text-sm text-white truncate">{user.email}</span>
            <button
              type="button"
              onClick={() => { setShowEmailForm((v) => !v); setEmailError(null); setEmailSuccess(null); }}
              className="text-xs text-sr-primary hover:text-sr-primary-muted transition-colors font-medium flex-shrink-0"
            >
              {showEmailForm ? 'Cancel' : 'Change Email'}
            </button>
          </div>

          {showEmailForm && (
            <form onSubmit={handleSendVerification} noValidate className="mt-3 flex flex-col sm:flex-row gap-2">
              <input
                type="email"
                autoComplete="email"
                required
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                className={`${inputCls} flex-1`}
                placeholder="New email address"
                disabled={emailLoading}
                aria-label="New email address"
              />
              <button
                type="submit"
                disabled={emailLoading || !newEmail}
                className={`${primaryBtnCls} flex-shrink-0`}
              >
                {emailLoading ? 'Sending...' : 'Send Verification'}
              </button>
            </form>
          )}

          {emailSuccess && (
            <p className="text-sm text-sr-success mt-2" role="status" aria-live="polite">
              Verification email sent to {emailSuccess}. Check your inbox.
            </p>
          )}
          {emailError && (
            <p className="text-sm text-sr-danger mt-2" role="alert" aria-live="polite">
              {emailError}
            </p>
          )}
        </div>

        {/* Member since */}
        <p className="text-sm text-sr-text-muted mb-5">
          Member since{' '}
          <span className="text-white">{formatMemberSince(user.member_since)}</span>
        </p>

        {nameSuccess && (
          <p className="text-sm text-sr-success mb-3" role="status" aria-live="polite">
            Name updated successfully.
          </p>
        )}
        {nameError && (
          <p className="text-sm text-sr-danger mb-3" role="alert" aria-live="polite">
            {nameError}
          </p>
        )}

        <button
          type="submit"
          disabled={nameLoading}
          className={primaryBtnCls}
        >
          {nameLoading ? 'Saving...' : 'Save Changes'}
        </button>
      </form>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Card 2: Change Password
// ---------------------------------------------------------------------------

function ChangePasswordCard() {
  const { changePassword } = useAccount();

  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(false);

    if (next !== confirm) {
      setError('New passwords do not match.');
      return;
    }
    if (next.length < 8) {
      setError('New password must be at least 8 characters.');
      return;
    }

    setIsLoading(true);
    try {
      await changePassword(current, next);
      setSuccess(true);
      setCurrent('');
      setNext('');
      setConfirm('');
    } catch (err) {
      setError((err as Error).message || 'Failed to update password.');
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <section className="bg-sr-surface border border-sr-border rounded-card p-6">
      <h2 className="text-white font-semibold text-base mb-4">Change Password</h2>

      <form onSubmit={handleSubmit} noValidate>
        <div className="space-y-4">
          <div>
            <label htmlFor="acc-current-pw" className="block text-sm text-sr-text-muted mb-1.5">
              Current password
            </label>
            <input
              id="acc-current-pw"
              type="password"
              autoComplete="current-password"
              required
              value={current}
              onChange={(e) => { setCurrent(e.target.value); setSuccess(false); }}
              className={inputCls}
              disabled={isLoading}
              placeholder="Current password"
            />
          </div>

          <div>
            <label htmlFor="acc-new-pw" className="block text-sm text-sr-text-muted mb-1.5">
              New password
            </label>
            <input
              id="acc-new-pw"
              type="password"
              autoComplete="new-password"
              required
              minLength={8}
              value={next}
              onChange={(e) => { setNext(e.target.value); setSuccess(false); }}
              className={inputCls}
              disabled={isLoading}
              placeholder="Min. 8 characters"
            />
          </div>

          <div>
            <label htmlFor="acc-confirm-pw" className="block text-sm text-sr-text-muted mb-1.5">
              Confirm new password
            </label>
            <input
              id="acc-confirm-pw"
              type="password"
              autoComplete="new-password"
              required
              value={confirm}
              onChange={(e) => { setConfirm(e.target.value); setSuccess(false); }}
              className={inputCls}
              disabled={isLoading}
              placeholder="Repeat new password"
            />
          </div>
        </div>

        {success && (
          <p className="text-sm text-sr-success mt-3" role="status" aria-live="polite">
            Password updated successfully.
          </p>
        )}
        {error && (
          <p className="text-sm text-sr-danger mt-3" role="alert" aria-live="polite">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={isLoading}
          className={`${primaryBtnCls} mt-5`}
        >
          {isLoading ? 'Updating...' : 'Update Password'}
        </button>
      </form>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Card 3: Subscription
// ---------------------------------------------------------------------------

function SubscriptionCard() {
  const { user } = useAuth();
  const { cancelSubscription } = useAccount();

  const [confirmInput, setConfirmInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canConfirm = confirmInput === 'CANCEL';

  async function handleCancel(e: React.FormEvent) {
    e.preventDefault();
    if (!canConfirm) return;
    setError(null);
    setIsLoading(true);
    try {
      await cancelSubscription();
      setSuccess(true);
    } catch (err) {
      setError((err as Error).message || 'Failed to cancel subscription.');
    } finally {
      setIsLoading(false);
    }
  }

  if (!user) return null;

  return (
    <section className="bg-sr-surface border border-sr-danger/40 rounded-card p-6">
      <h2 className="text-sr-danger font-semibold text-base mb-1">Subscription</h2>
      <p className="text-sm text-sr-text-muted mb-4">
        Status:{' '}
        <span className={user.is_subscriber ? 'text-sr-success font-medium' : 'text-white'}>
          {user.is_subscriber ? 'Active subscriber' : 'Free tier'}
        </span>
      </p>

      {user.is_subscriber && !success && (
        <form onSubmit={handleCancel} noValidate>
          <p className="text-sm text-sr-text-muted mb-3">
            To cancel your subscription, type{' '}
            <span className="font-mono text-white font-semibold">CANCEL</span>{' '}
            in the box below and click the button.
          </p>
          <input
            type="text"
            value={confirmInput}
            onChange={(e) => setConfirmInput(e.target.value)}
            className={`${inputCls} mb-3`}
            placeholder="Type CANCEL to confirm"
            disabled={isLoading}
            aria-label="Type CANCEL to confirm cancellation"
          />

          {error && (
            <p className="text-sm text-sr-danger mb-3" role="alert" aria-live="polite">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={!canConfirm || isLoading}
            className={dangerBtnCls}
          >
            {isLoading ? 'Cancelling...' : 'Cancel Subscription'}
          </button>
        </form>
      )}

      {success && (
        <p className="text-sm text-sr-success" role="status" aria-live="polite">
          Subscription cancelled. Your access has been removed.
        </p>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function AccountPage() {
  const { user, isLoading } = useAuth();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<Tab>('weekly');
  const [currentWeek, setCurrentWeek] = useState<number | null>(null);

  useEffect(() => {
    if (!isLoading && !user) {
      router.replace('/');
    }
  }, [user, isLoading, router]);

  useEffect(() => {
    async function fetchWeek() {
      try {
        const resp = await fetch(`${API_URL}/api/status/week`);
        if (!resp.ok) return;
        const data = await resp.json();
        setCurrentWeek(data.week ?? null);
      } catch {
        // WeekBadge handles null gracefully
      }
    }
    fetchWeek();
  }, []);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-sr-bg flex items-center justify-center">
        <div className="w-8 h-8 rounded-full bg-sr-border animate-pulse" />
      </div>
    );
  }

  if (!user) {
    // Redirecting — render nothing
    return null;
  }

  return (
    <div className="min-h-screen bg-sr-bg">
      <NavBar
        activeTab={activeTab}
        onTabChange={(tab) => router.push(`/?tab=${tab}`)}
        currentWeek={currentWeek}
      />
      <div className="mx-auto max-w-2xl px-4 sm:px-6 lg:px-8 py-10">
        <h1 className="text-white font-bold text-2xl mb-8">My Account</h1>

        <div className="space-y-6">
          <ProfileCard />
          <ChangePasswordCard />
          <SubscriptionCard />
        </div>
      </div>
    </div>
  );
}
