'use client';

import { WeekBadge } from './WeekBadge';

type Tab = 'weekly' | 'player' | 'track';

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
  return (
    <nav className="sticky top-0 z-50 h-16 bg-sr-bg/80 backdrop-blur-md border-b border-sr-border">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 h-full flex items-center justify-between">
        {/* Wordmark */}
        <span className="text-white font-bold text-lg tracking-tight">
          Big Game Gabe
        </span>

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
        </div>

        {/* Week badge */}
        <WeekBadge week={currentWeek} />
      </div>
    </nav>
  );
}
