'use client';

import { useEffect, useState } from 'react';
import { ValuePlayerCard } from '@/components/ValuePlayerCard';
import { GamblingDisclaimer } from '@/components/GamblingDisclaimer';
import { PlayerWeekToggle } from '@/components/PlayerWeekToggle';
import { SurfaceCard } from '@/components/ui/SurfaceCard';
import { ConsensusBadge } from '@/components/ui/ConsensusBadge';
import { Checkbox } from '@/components/ui/checkbox';
import { TrendingUp, TrendingDown, AlertTriangle } from 'lucide-react';

interface Prediction {
  player_id: string;
  full_name: string;
  position: string | null;
  team: string | null;
  headshot_url: string | null;
  final_prob: number;
  model_odds: number;
  sportsbook_odds: number | null;
  implied_prob: number | null;
  favor: number | null;
  is_low_confidence: boolean;
  model_version: string;
}

interface ValuePick extends Prediction {
  expected_value: number;
  has_edge: boolean;
}

interface WeeklyValueProps {
  currentWeek: number | null;
  currentYear: number | null;
  onPlayerClick: (playerId: string) => void;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? '';

export function WeeklyValue({ currentWeek, currentYear, onPlayerClick }: WeeklyValueProps) {
  const [predictions, setPredictions] = useState<ValuePick[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showOnlyEdge, setShowOnlyEdge] = useState(true);
  const [selectedWeek, setSelectedWeek] = useState<number>(18);

  // Sync selectedWeek when currentWeek prop arrives
  useEffect(() => {
    if (currentWeek !== null) {
      setSelectedWeek(currentWeek);
    }
  }, [currentWeek]);

  const effectiveYear = currentYear ?? 2025;

  // Load predictions when week changes
  useEffect(() => {
    async function loadPredictions() {
      try {
        setLoading(true);
        setError(null);

        const url = `${API_URL}/api/predictions/${effectiveYear}/${selectedWeek}`;

        const response = await fetch(url);
        if (!response.ok) throw new Error('Failed to fetch predictions');

        const data = await response.json();
        const preds: Prediction[] = data.predictions || [];

        if (!preds || preds.length === 0) {
          setPredictions([]);
          setLoading(false);
          return;
        }

        const predsWithValues: ValuePick[] = preds.map((pred: Prediction) => {
          const hasEdge = pred.favor !== null && pred.favor > 0;
          const ev = pred.favor ?? 0;
          return {
            ...pred,
            expected_value: ev,
            has_edge: hasEdge,
          };
        });

        const sorted = predsWithValues.sort((a, b) => b.expected_value - a.expected_value);
        setPredictions(sorted);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load predictions');
      } finally {
        setLoading(false);
      }
    }

    loadPredictions();
  }, [selectedWeek, effectiveYear]);

  const filteredPredictions = predictions.filter((p) => {
    if (showOnlyEdge && !p.has_edge) return false;
    return true;
  });

  return (
    <div className="relative">
      {/* Hero gradient background */}
      <div
        className="absolute top-0 left-0 w-full hidden md:block"
        style={{
          height: 384,
          background: 'linear-gradient(135deg, #1a0533 0%, #0d1117 40%, #0a0a0a 100%)',
        }}
      />

      {/* Content */}
      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <SurfaceCard className="mb-4 p-4 md:p-6">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
            <div className="flex-1">
              <h1 className="text-xl md:text-3xl font-semibold text-white mb-1">
                Week {selectedWeek} Value Plays
              </h1>
              <p className="text-sm text-sr-text-muted">
                Players with the highest model edge vs consensus odds
              </p>
            </div>
            <PlayerWeekToggle
              currentWeek={currentWeek ?? 18}
              currentYear={effectiveYear}
              selectedWeek={selectedWeek}
              onWeekChange={setSelectedWeek}
            />
          </div>
        </SurfaceCard>

        {/* Loading State */}
        {loading && (
          <div className="flex flex-col gap-2 mb-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-16 rounded-card bg-sr-surface animate-pulse" />
            ))}
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="mb-4 bg-sr-danger/10 border border-sr-danger/30 rounded-card p-4 text-sr-danger flex items-center gap-2">
            <AlertTriangle size={16} />
            <span>Error: {error}</span>
          </div>
        )}

        {/* No Predictions */}
        {!loading && !error && predictions.length === 0 && (
          <SurfaceCard className="p-12 text-center mb-4">
            <div className="flex items-center justify-center gap-2 mb-2">
              <AlertTriangle size={24} className="text-yellow-500" />
              <h2 className="text-lg text-yellow-500">Predictions Not Available</h2>
            </div>
            <p className="text-sr-text-muted mb-1">
              Week {selectedWeek} predictions haven&apos;t been generated yet.
            </p>
            <p className="text-sm text-sr-text-dim">
              Check back after the weekly batch job completes or try viewing a previous week.
            </p>
          </SurfaceCard>
        )}

        {/* Filters */}
        {!loading && !error && predictions.length > 0 && (
          <SurfaceCard className="mb-4 p-4">
            <div className="flex items-center gap-4 flex-wrap">
              {/* Consensus badge — replaces sportsbook toggle */}
              <ConsensusBadge />

              {/* EV filter */}
              <label className="flex items-center gap-2 cursor-pointer">
                <Checkbox
                  checked={showOnlyEdge}
                  onCheckedChange={setShowOnlyEdge}
                />
                <span className="text-sm text-sr-text-muted">+EV only</span>
              </label>
            </div>
          </SurfaceCard>
        )}

        {/* Value Player Cards */}
        {!loading && !error && predictions.length > 0 && (
          <>
            {filteredPredictions.length === 0 ? (
              <SurfaceCard className="p-12 text-center mb-4">
                <p className="text-sr-text-muted">
                  No positive EV plays found for this week
                </p>
              </SurfaceCard>
            ) : (
              <div className="flex flex-col gap-2">
                {filteredPredictions.map((prediction, index) => (
                  <ValuePlayerCard
                    key={prediction.player_id}
                    player_id={prediction.player_id}
                    player_name={prediction.full_name}
                    team_name={prediction.team}
                    position={prediction.position}
                    headshot_url={prediction.headshot_url}
                    td_likelihood={prediction.final_prob}
                    model_odds={String(prediction.model_odds)}
                    sportsbook_odds={prediction.sportsbook_odds ?? undefined}
                    edge_value={prediction.expected_value}
                    rank={index + 1}
                    onClick={onPlayerClick}
                  />
                ))}
              </div>
            )}
          </>
        )}

        {/* Legend */}
        {!loading && predictions.length > 0 && (
          <SurfaceCard className="mt-4 p-4">
            <div className="flex flex-col md:flex-row gap-4 text-sm">
              <div className="flex items-center gap-2">
                <TrendingUp size={16} className="text-sr-success" />
                <span className="text-sr-text-muted">Positive Edge (Model favored)</span>
              </div>
              <div className="flex items-center gap-2">
                <TrendingDown size={16} className="text-sr-danger" />
                <span className="text-sr-text-muted">Negative Edge (Sportsbook favored)</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sr-text-muted">Edge = Expected Value vs. Consensus</span>
              </div>
            </div>
          </SurfaceCard>
        )}

        {/* Gambling Disclaimer */}
        <GamblingDisclaimer />
      </div>
    </div>
  );
}
