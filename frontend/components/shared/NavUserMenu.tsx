'use client';

import React, { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { ChevronDown } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface NavMenuItem {
  label: string;
  href?: string;
  onClick?: () => void;
  isDivider?: boolean;
  isDanger?: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function NavUserMenu() {
  const { user, logout } = useAuth();
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

  const displayName =
    user.first_name || user.last_name
      ? [user.first_name, user.last_name].filter(Boolean).join(' ')
      : 'Account';

  const avatarLetter = (user.first_name ?? user.email).charAt(0).toUpperCase();

  async function handleLogout() {
    setIsOpen(false);
    await logout();
  }

  const menuItems: NavMenuItem[] = [
    { label: 'My Account', href: '/account' },
    { label: '', isDivider: true },
    { label: 'Log Out', onClick: handleLogout, isDanger: true },
  ];

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
        {/* Avatar circle */}
        <div
          className="w-8 h-8 rounded-full bg-sr-border flex items-center justify-center text-white text-sm font-semibold flex-shrink-0"
          aria-hidden="true"
        >
          {avatarLetter}
        </div>

        {/* Display name */}
        <span className="text-sm text-white font-medium hidden sm:block max-w-[120px] truncate">
          {displayName}
        </span>

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
          {/* Name + tier header */}
          <div className="px-4 py-2" role="none">
            <p className="text-sm text-white font-medium truncate max-w-[160px]" title={displayName}>
              {displayName}
            </p>
          </div>

          {menuItems.map((item, index) => {
            if (item.isDivider) {
              return (
                <div key={`divider-${index}`} className="border-t border-sr-border my-1" role="none" />
              );
            }

            if (item.href) {
              return (
                <Link
                  key={item.label}
                  href={item.href}
                  role="menuitem"
                  onClick={() => setIsOpen(false)}
                  className="block text-sm text-white px-4 py-2 hover:bg-sr-border/30 cursor-pointer transition-colors"
                >
                  {item.label}
                </Link>
              );
            }

            return (
              <button
                key={item.label}
                type="button"
                role="menuitem"
                onClick={item.onClick}
                className={[
                  'w-full text-left text-sm px-4 py-2 hover:bg-sr-border/30 cursor-pointer transition-colors',
                  item.isDanger
                    ? 'text-white hover:text-sr-danger'
                    : 'text-white',
                ].join(' ')}
              >
                {item.label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
