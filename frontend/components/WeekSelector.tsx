'use client';

import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

interface Week {
  season_year: number;
  week: number;
  label: string;
  has_odds: boolean;
  has_predictions: boolean;
  is_complete: boolean;
  game_count: number;
  odds_count: number;
  prediction_count: number;
}

interface WeekSelectorProps {
  onWeekChange?: (week: number, year: number) => void;
}

export default function WeekSelector({ onWeekChange }: WeekSelectorProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [weeks, setWeeks] = useState<Week[]>([]);
  const [selectedWeek, setSelectedWeek] = useState<number | null>(null);
  const [selectedYear, setSelectedYear] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

    fetch(`${apiUrl}/api/weeks/available`)
      .then(res => res.json())
      .then(data => {
        setWeeks(data.weeks);

        // Check URL params first
        const urlWeek = searchParams.get('week');
        const urlYear = searchParams.get('year');

        if (urlWeek && urlYear) {
          setSelectedWeek(parseInt(urlWeek));
          setSelectedYear(parseInt(urlYear));
        } else if (data.current_week) {
          // Default to current week
          setSelectedWeek(data.current_week.week);
          setSelectedYear(data.current_week.season_year);
        }

        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load weeks:', err);
        setLoading(false);
      });
  }, [searchParams]);

  const handleWeekChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const value = event.target.value;
    const [year, week] = value.split('-').map(Number);

    setSelectedWeek(week);
    setSelectedYear(year);

    // Update URL without page reload
    const params = new URLSearchParams(searchParams.toString());
    params.set('week', week.toString());
    params.set('year', year.toString());
    router.push(`?${params.toString()}`, { scroll: false });

    // Notify parent component
    if (onWeekChange) {
      onWeekChange(week, year);
    }

    // Trigger custom event for other components to listen
    window.dispatchEvent(new CustomEvent('weekChanged', {
      detail: { week, year }
    }));
  };

  if (loading) {
    return (
      <div className="animate-pulse h-10 w-48 bg-gray-700 rounded"></div>
    );
  }

  if (weeks.length === 0) {
    return (
      <div className="text-sm text-gray-400">
        No data available
      </div>
    );
  }

  const selectedValue = selectedYear && selectedWeek
    ? `${selectedYear}-${selectedWeek}`
    : '';

  return (
    <div className="flex items-center gap-3">
      <label htmlFor="week-selector" className="text-sm font-medium text-gray-300">
        Week:
      </label>
      <select
        id="week-selector"
        value={selectedValue}
        onChange={handleWeekChange}
        className="bg-gray-800 border border-gray-700 text-white rounded-lg px-4 py-2
                   focus:ring-2 focus:ring-blue-500 focus:border-transparent
                   hover:bg-gray-750 transition-colors cursor-pointer"
      >
        {weeks.map(week => (
          <option
            key={`${week.season_year}-${week.week}`}
            value={`${week.season_year}-${week.week}`}
            disabled={!week.is_complete}
          >
            {week.label} {week.season_year}
            {!week.is_complete && ' (No data)'}
          </option>
        ))}
      </select>

      {/* Show data status indicator */}
      {selectedYear && selectedWeek && (
        <div className="flex items-center gap-2 text-xs text-gray-400">
          {weeks.find(w => w.week === selectedWeek && w.season_year === selectedYear)?.is_complete ? (
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 bg-green-500 rounded-full"></span>
              Data available
            </span>
          ) : (
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 bg-yellow-500 rounded-full"></span>
              Incomplete
            </span>
          )}
        </div>
      )}
    </div>
  );
}
