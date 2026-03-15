'use client';

import Image from 'next/image';
import { WeekBadge } from './WeekBadge';
import { NavUserMenu } from './NavUserMenu';
import { useAuth, useIsAdmin } from '../../hooks/useAuth';
import { useAuthModal } from '../../contexts/AuthModalContext';

type Tab = 'weekly' | 'player' | 'track' | 'admin';

interface NavBarProps {
  activeTab: Tab;
  onTabChange: (tab: Tab) => void;
  currentWeek: number | null;
}

const TABS: { id: Tab; label: string }[] = [
  { id: 'weekly', label: 'This Week' },
  { id: 'player', label: 'Player Lookup' },
  { id: 'track', label: 'Track Record' },
];

export function NavBar({ activeTab, onTabChange, currentWeek }: NavBarProps) {
  const { user, isLoading } = useAuth();
  const { openLogin } = useAuthModal();
  const isAdmin = useIsAdmin();

  return (
    <nav className="sticky top-0 z-50 h-16 bg-sr-bg/80 backdrop-blur-md border-b border-sr-border">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 h-full flex items-center justify-between">
        {/* Wordmark */}
        <div className="flex items-center gap-2">
          <Image
            src="/biggamegabeicon.png"
            alt="Big Game Gabe"
            width={32}
            height={32}
            className="rounded-sm"
          />
          <span className="text-white font-bold text-lg tracking-tight">
            Big Game Gabe
          </span>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-1">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={
                activeTab === tab.id
                  ? 'px-4 py-2 text-sm font-medium text-white border-b-2 border-sr-primary transition-colors'
                  : 'px-4 py-2 text-sm font-medium text-sr-text-muted hover:text-white transition-colors'
              }
            >
              {tab.label}
            </button>
          ))}
          {isAdmin && (
            <button
              onClick={() => onTabChange('admin')}
              className={
                activeTab === 'admin'
                  ? 'px-4 py-2 text-sm font-medium text-white border-b-2 border-sr-primary transition-colors'
                  : 'px-4 py-2 text-sm font-medium text-sr-text-muted hover:text-white transition-colors'
              }
            >
              Admin
            </button>
          )}
        </div>

        {/* Right zone: week badge + auth */}
        <div className="flex items-center gap-3">
          <WeekBadge week={currentWeek} />
          {isLoading ? (
            <div className="w-8 h-8 rounded-full bg-sr-border animate-pulse" />
          ) : user ? (
            <NavUserMenu />
          ) : (
            <button
              type="button"
              onClick={() => openLogin()}
              className="border border-sr-border text-sm font-medium text-white px-4 py-1.5 rounded-lg hover:border-sr-primary hover:text-sr-primary transition-colors"
            >
              Sign In
            </button>
          )}
        </div>
      </div>
    </nav>
  );
}
