import { useState, useEffect } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? '';

interface WeekStatus {
  week: number | null;
  season: number | null;
  isEarlySeason: boolean;
  source: 'admin_override' | 'pipeline' | 'default' | null; // null = loading
}

export function useCurrentWeek(): WeekStatus {
  const [status, setStatus] = useState<WeekStatus>({
    week: null,
    season: null,
    isEarlySeason: false,
    source: null,
  });

  useEffect(() => {
    async function fetchWeek() {
      try {
        const resp = await fetch(`${API_URL}/api/status/week`);
        if (!resp.ok) return;
        const data = await resp.json();
        setStatus({
          week: data.week ?? null,
          season: data.season ?? null,
          isEarlySeason: data.is_early_season ?? false,
          source: data.source ?? null,
        });
      } catch {
        // silent — components handle null week gracefully
      }
    }
    fetchWeek();
  }, []);

  return status;
}
