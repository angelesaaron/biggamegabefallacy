import { useState, useEffect } from 'react';
import { useAuth } from '@/hooks/useAuth';
import type { PredictionResponse, TeaserCounts, PredictionsApiResponse } from '@/types/backend';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? '';

interface PredictionsState {
  predictions: PredictionResponse[];
  teaser: TeaserCounts | null;
  loading: boolean;
  error: string | null;
}

export function usePredictions(season: number, week: number | null): PredictionsState {
  const { user, getToken } = useAuth();
  const [state, setState] = useState<PredictionsState>({
    predictions: [],
    teaser: null,
    loading: true,
    error: null,
  });

  useEffect(() => {
    // Don't fetch until week is resolved from the API
    if (week === null) return;

    async function load() {
      setState((prev) => ({ ...prev, loading: true, error: null }));
      try {
        const token = getToken();
        const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
        const resp = await fetch(`${API_URL}/api/predictions/${season}/${week}`, { headers });
        if (!resp.ok) throw new Error('Failed to fetch predictions');
        const data = await resp.json() as PredictionsApiResponse;
        setState({
          predictions: data.predictions ?? [],
          teaser: data.teaser ?? null,
          loading: false,
          error: null,
        });
      } catch (err) {
        setState({
          predictions: [],
          teaser: null,
          loading: false,
          error: err instanceof Error ? err.message : 'Failed to load predictions',
        });
      }
    }
    load();
  // Re-fetch when auth state changes (login/logout delivers different payload)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [season, week, user]);

  return state;
}
