'use client';

import { ChevronLeft, ChevronRight } from 'lucide-react';

interface PlayerWeekToggleProps {
  currentWeek: number;
  currentYear: number;
  selectedWeek: number;
  onWeekChange: (week: number) => void;
  lockedToCurrentWeek?: boolean;
}

export function PlayerWeekToggle({
  currentWeek,
  currentYear,
  selectedWeek,
  onWeekChange,
  lockedToCurrentWeek = false,
}: PlayerWeekToggleProps) {
  const canGoBack = selectedWeek > 1;
  const canGoForward = selectedWeek < currentWeek;
  const backIsLocked = lockedToCurrentWeek && selectedWeek <= currentWeek;
  const backDisabled = !canGoBack || backIsLocked;

  function handleBack() {
    if (backDisabled) return;
    onWeekChange(selectedWeek - 1);
  }

  function handleForward() {
    if (!canGoForward) return;
    onWeekChange(selectedWeek + 1);
  }

  return (
    <div className="flex items-center gap-2 bg-sr-surface/60 border border-sr-border/50 rounded-lg p-1">
      <button
        onClick={handleBack}
        disabled={backDisabled}
        className={`p-2 rounded-md transition-all ${
          backDisabled
            ? 'text-sr-text-dim cursor-not-allowed'
            : 'text-sr-text-muted hover:text-white hover:bg-sr-border/30'
        }`}
        aria-label="Previous week"
      >
        <ChevronLeft className="w-4 h-4" />
      </button>

      <div className="px-4 py-1 text-sm text-white min-w-[80px] text-center">
        <span className="text-sr-text-muted">Week</span>{' '}
        <span className="font-semibold nums">{selectedWeek}</span>
        <span className="text-xs text-sr-text-dim ml-1 nums">'{String(currentYear).slice(-2)}</span>
      </div>

      <button
        onClick={handleForward}
        disabled={!canGoForward}
        className={`p-2 rounded-md transition-all ${
          canGoForward
            ? 'text-sr-text-muted hover:text-white hover:bg-sr-border/30'
            : 'text-sr-text-dim cursor-not-allowed'
        }`}
        aria-label="Next week"
      >
        <ChevronRight className="w-4 h-4" />
      </button>
    </div>
  );
}
