import { ChevronLeft, ChevronRight } from 'lucide-react';

interface PlayerWeekToggleProps {
  currentWeek: number;
  currentYear: number;
  selectedWeek: number;
  onWeekChange: (week: number) => void;
}

export function PlayerWeekToggle({
  currentWeek,
  currentYear,
  selectedWeek,
  onWeekChange,
}: PlayerWeekToggleProps) {
  const canGoBack = selectedWeek > 1;
  const canGoForward = selectedWeek < 18; // Allow up to week 18

  return (
    <div className="flex items-center gap-2 bg-gray-900/50 rounded-lg p-1">
      <button
        onClick={() => onWeekChange(selectedWeek - 1)}
        disabled={!canGoBack}
        className={`p-2 rounded-md transition-all ${
          canGoBack
            ? 'text-gray-400 hover:text-white hover:bg-gray-800'
            : 'text-gray-700 cursor-not-allowed'
        }`}
        title="Previous week"
      >
        <ChevronLeft className="w-4 h-4" />
      </button>

      <div className="px-4 py-1 text-sm text-white min-w-[80px] text-center">
        <span className="text-gray-400">Week</span>{' '}
        <span className="font-semibold">{selectedWeek}</span>
      </div>

      <button
        onClick={() => onWeekChange(selectedWeek + 1)}
        disabled={!canGoForward}
        className={`p-2 rounded-md transition-all ${
          canGoForward
            ? 'text-gray-400 hover:text-white hover:bg-gray-800'
            : 'text-gray-700 cursor-not-allowed'
        }`}
        title="Next week"
      >
        <ChevronRight className="w-4 h-4" />
      </button>
    </div>
  );
}
