'use client';

import React, { useEffect, useRef, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { useAuthModal } from '../../contexts/AuthModalContext';

export function UserPill() {
  const { user, logout } = useAuth();
  const { openRegister } = useAuthModal();
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    function handleMouseDown(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleMouseDown);
    return () => document.removeEventListener('mousedown', handleMouseDown);
  }, []);

  // Close on Escape key
  useEffect(() => {
    if (!isOpen) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') setIsOpen(false);
    }
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen]);

  if (!user) return null;

  const avatarLetter = user.email.charAt(0).toUpperCase();
  const isPro = user.is_subscriber;

  async function handleSignOut() {
    setIsOpen(false);
    await logout();
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        className="flex items-center gap-2 rounded-lg px-2 py-1 hover:bg-sr-border/30 transition-colors"
        aria-expanded={isOpen}
        aria-haspopup="true"
        aria-label="Account menu"
      >
        {/* Avatar */}
        <div
          className="w-8 h-8 rounded-full bg-sr-border flex items-center justify-center text-white text-sm font-semibold flex-shrink-0"
          aria-hidden="true"
        >
          {avatarLetter}
        </div>

        {/* Tier badge */}
        {isPro ? (
          <span className="bg-emerald-900/50 text-sr-success text-xs rounded-full px-2 py-0.5 font-medium">
            Pro
          </span>
        ) : (
          <span className="bg-sr-border text-sr-text-muted text-xs rounded-full px-2 py-0.5 font-medium">
            Free
          </span>
        )}

        <ChevronDown
          size={14}
          className={[
            'text-sr-text-muted transition-transform duration-150',
            isOpen ? 'rotate-180' : '',
          ].join(' ')}
          aria-hidden="true"
        />
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div
          className="absolute right-0 top-full mt-1.5 bg-sr-surface border border-sr-border rounded-card shadow-xl min-w-[180px] py-1 z-50"
          role="menu"
          aria-orientation="vertical"
        >
          {/* Email + tier */}
          <div className="px-4 py-2" role="none">
            <p
              className="text-sm text-white font-medium truncate max-w-[160px]"
              title={user.email}
            >
              {user.email}
            </p>
            <p className="text-xs text-sr-text-muted mt-0.5">
              {isPro ? 'Pro member' : 'Free tier'}
            </p>
          </div>

          <div className="border-t border-sr-border my-1" role="none" />

          {/* Upgrade (free tier only) */}
          {!isPro && (
            <>
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setIsOpen(false);
                  openRegister();
                }}
                className="w-full text-left text-sm text-sr-primary px-4 py-2 hover:bg-sr-border/30 cursor-pointer transition-colors"
              >
                Upgrade to Pro
              </button>
              <div className="border-t border-sr-border my-1" role="none" />
            </>
          )}

          {/* Sign Out */}
          <button
            type="button"
            role="menuitem"
            onClick={handleSignOut}
            className="w-full text-left text-sm text-white px-4 py-2 hover:text-sr-danger hover:bg-sr-border/30 cursor-pointer transition-colors"
          >
            Sign Out
          </button>
        </div>
      )}
    </div>
  );
}
