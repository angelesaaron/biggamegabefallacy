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
  const canGoForward = selectedWeek < 18;
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
    <div className="flex items-center gap-2 bg-gray-900/60 border border-gray-800/50 rounded-lg p-1">
      <button
        onClick={handleBack}
        disabled={backDisabled}
        className={`p-2 rounded-md transition-all ${
          backDisabled
            ? 'text-gray-700 cursor-not-allowed'
            : 'text-gray-300 hover:text-white hover:bg-gray-800'
        }`}
        aria-label="Previous week"
      >
        <ChevronLeft className="w-4 h-4" />
      </button>

      <div className="px-4 py-1 text-sm text-white min-w-[80px] text-center">
        <span className="text-gray-300">Week</span>{' '}
        <span className="font-semibold nums">{selectedWeek}</span>
      </div>

      <button
        onClick={handleForward}
        disabled={!canGoForward}
        className={`p-2 rounded-md transition-all ${
          canGoForward
            ? 'text-gray-300 hover:text-white hover:bg-gray-800'
            : 'text-gray-700 cursor-not-allowed'
        }`}
        aria-label="Next week"
      >
        <ChevronRight className="w-4 h-4" />
      </button>
    </div>
  );
}
