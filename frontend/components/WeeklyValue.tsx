'use client';

import { useEffect, useState } from 'react';
import { ValuePlayerCard } from '@/components/ValuePlayerCard';
import { GamblingDisclaimer } from '@/components/GamblingDisclaimer';
import { PlayerWeekToggle } from '@/components/PlayerWeekToggle';
import { TrendingUp, TrendingDown, AlertTriangle, AlertCircle, Loader2 } from 'lucide-react';

interface Prediction {
  player_id: string;
  player_name: string;
  team_name: string | null;
  position: string | null;
  headshot_url: string | null;
  season_year: number;
  week: number;
  td_likelihood: string;
  model_odds: string;
  favor: number;
  created_at: string | null;
}

interface ValuePick extends Prediction {
  sportsbook_odds?: number;
  expected_value?: number;
  has_edge?: boolean;
}

interface PredictionsMetadata {
  current_week: number;
  current_year: number;
  showing_week: number;
  showing_year: number;
  is_fallback: boolean;
}

interface WeeklyValueProps {
  onPlayerClick?: (playerId: string) => void;
}

export default function WeeklyValue({ onPlayerClick }: WeeklyValueProps) {
  const [predictions, setPredictions] = useState<ValuePick[]>([]);
  const [metadata, setMetadata] = useState<PredictionsMetadata | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSportsbook, setSelectedSportsbook] = useState<
    'draftkings' | 'fanduel'
  >('draftkings');
  const [showOnlyEdge, setShowOnlyEdge] = useState(true);
  const [currentWeek, setCurrentWeek] = useState(18);
  const [currentYear, setCurrentYear] = useState(2025);
  const [selectedWeek, setSelectedWeek] = useState(18);

  // Fetch current week on mount
  useEffect(() => {
    async function fetchCurrentWeek() {
      try {
        const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        const response = await fetch(`${API_URL}/api/admin/data-readiness/current`);
        const data = await response.json();
        const currentWeekData = data.current_week;

        if (currentWeekData) {
          setCurrentWeek(currentWeekData.week);
          setCurrentYear(currentWeekData.year);
          setSelectedWeek(currentWeekData.week);
        }
      } catch (error) {
        console.error('Failed to fetch current week:', error);
      }
    }

    fetchCurrentWeek();
  }, []);

  // Load predictions when week or sportsbook changes
  useEffect(() => {
    async function loadPredictions() {
      try {
        setLoading(true);
        setError(null);

        const API_URL =
          process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

        // Build URL with week/year params
        const params = new URLSearchParams();
        params.set('week', selectedWeek.toString());
        params.set('year', currentYear.toString());
        const url = `${API_URL}/api/predictions/current?${params.toString()}`;

        const response = await fetch(url);
        if (!response.ok) throw new Error('Failed to fetch predictions');

        const data = await response.json();
        const preds: Prediction[] = data.predictions || [];
        const meta: PredictionsMetadata = data.metadata;

        setMetadata(meta);

        // If no predictions at all, show error
        if (!preds || preds.length === 0) {
          setPredictions([]);
          setLoading(false);
          return;
        }

        // Fetch odds for each prediction
        const predsWithOdds = await Promise.all(
          preds.map(async (pred: Prediction, index: number) => {
            try {
              const oddsUrl = `${API_URL}/api/odds/comparison/${pred.player_id}?week=${pred.week}&year=${pred.season_year}`;
              const oddsData = await fetch(oddsUrl).then((r) => r.json());
              const modelProb = parseFloat(pred.td_likelihood);
              const sbOdds = oddsData.sportsbook_odds?.[selectedSportsbook];

              let ev = 0;
              let hasEdge = false;

              if (sbOdds) {
                const sbImpliedProb =
                  sbOdds > 0
                    ? 100 / (sbOdds + 100)
                    : Math.abs(sbOdds) / (Math.abs(sbOdds) + 100);

                const payout =
                  sbOdds > 0 ? sbOdds / 100 : 100 / Math.abs(sbOdds);
                ev = modelProb * payout - (1 - modelProb);
                hasEdge = ev > 0 && modelProb > sbImpliedProb;
              }

              return {
                ...pred,
                sportsbook_odds: sbOdds,
                expected_value: ev,
                has_edge: hasEdge,
              };
            } catch (err) {
              return {
                ...pred,
                sportsbook_odds: undefined,
                expected_value: 0,
                has_edge: false,
              };
            }
          })
        );

        // Sort by expected value descending
        const sorted = predsWithOdds.sort(
          (a, b) => (b.expected_value || 0) - (a.expected_value || 0)
        );
        setPredictions(sorted);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Failed to load predictions'
        );
      } finally {
        setLoading(false);
      }
    }

    loadPredictions();
  }, [selectedSportsbook, selectedWeek, currentYear]);

  const filteredPredictions = showOnlyEdge
    ? predictions.filter((p) => p.has_edge)
    : predictions;

  return (
    <div className="relative">
      {/* Hero Background */}
      <div
        className="absolute top-0 left-0 w-full h-96 bg-cover bg-center"
        style={{
          backgroundImage: 'url(/gabe-davis-background.jpg)',
          backgroundPosition: 'center 15%',
        }}
      >
        <div className="absolute inset-0 bg-gradient-to-b from-black/60 via-black/75 to-[#0a0a0a]" />
      </div>

      {/* Content */}
      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8 bg-gray-900/40 backdrop-blur-sm border border-gray-800 rounded-xl p-6 max-md:p-4">
          <div className="flex items-center justify-between gap-4 mb-2 max-md:flex-col max-md:items-start">
            <div className="flex-1">
              <h2 className="text-3xl max-md:text-2xl text-white mb-2">
                Week {selectedWeek} Value Plays
              </h2>
              <p className="text-gray-400 max-md:text-sm">
                Players with the highest model edge vs sportsbook odds
              </p>
            </div>
            <PlayerWeekToggle
              currentWeek={currentWeek}
              currentYear={currentYear}
              selectedWeek={selectedWeek}
              onWeekChange={setSelectedWeek}
            />
          </div>
        </div>

      {/* Loading Overlay */}
      {loading && (
        <div className="mb-6 bg-gray-900/40 backdrop-blur-sm border border-gray-800 rounded-xl p-8 flex items-center justify-center">
          <Loader2 className="w-8 h-8 text-purple-500 animate-spin mr-3" />
          <span className="text-white text-lg">Loading predictions...</span>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="mb-6 bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
          <p className="text-red-500 text-lg">Error: {error}</p>
        </div>
      )}

      {/* No Predictions Available */}
      {!loading && !error && predictions.length === 0 && (
        <div className="bg-gray-900/40 backdrop-blur-sm border border-gray-800 rounded-xl p-12 text-center">
          <div className="flex items-center justify-center gap-2 mb-4">
            <AlertCircle className="w-8 h-8 text-yellow-500" />
            <h3 className="text-2xl text-yellow-500">Predictions Not Available</h3>
          </div>
          <p className="text-gray-400 mb-2">
            Week {selectedWeek} predictions haven't been generated yet.
          </p>
          <p className="text-sm text-gray-500">
            Check back after the weekly batch job completes or try viewing a previous week.
          </p>
        </div>
      )}

      {/* Filters - only show when we have data */}
      {!loading && !error && predictions.length > 0 && (
        <div className="mb-6 flex items-center gap-4 max-md:flex-col max-md:items-stretch max-md:gap-3 bg-gray-900/40 backdrop-blur-sm border border-gray-800 rounded-xl p-4 max-md:p-3">
          <div className="flex gap-2 bg-gray-900/50 rounded-lg p-1 w-full md:w-auto">
            <button
              onClick={() => setSelectedSportsbook('draftkings')}
              className={`flex-1 md:flex-initial px-4 py-2 max-md:px-3 max-md:py-1.5 max-md:text-sm rounded-md transition-all ${
                selectedSportsbook === 'draftkings'
                  ? 'bg-purple-600 text-white'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              DraftKings
            </button>
            <button
              onClick={() => setSelectedSportsbook('fanduel')}
              className={`flex-1 md:flex-initial px-4 py-2 max-md:px-3 max-md:py-1.5 max-md:text-sm rounded-md transition-all ${
                selectedSportsbook === 'fanduel'
                  ? 'bg-purple-600 text-white'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              FanDuel
            </button>
          </div>

          <label className="flex items-center gap-2 text-sm max-md:text-xs text-gray-400 cursor-pointer">
            <input
              type="checkbox"
              checked={showOnlyEdge}
              onChange={(e) => setShowOnlyEdge(e.target.checked)}
              className="w-4 h-4 rounded bg-gray-800 border-gray-700 text-purple-600 focus:ring-purple-600"
            />
            Show only +EV plays
          </label>
        </div>
      )}

      {/* Value Player Cards */}
      {!loading && !error && predictions.length > 0 && (
        <>
          {filteredPredictions.length === 0 ? (
            <div className="bg-gray-900/40 backdrop-blur-sm border border-gray-800 rounded-xl p-12 text-center">
              <p className="text-gray-400 text-lg">
                No positive EV plays found for this sportsbook
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {filteredPredictions.map((prediction, index) => (
                <ValuePlayerCard
                  key={prediction.player_id}
                  player_id={prediction.player_id}
                  player_name={prediction.player_name}
                  team_name={prediction.team_name}
                  position={prediction.position}
                  headshot_url={prediction.headshot_url}
                  td_likelihood={parseFloat(prediction.td_likelihood)}
                  model_odds={prediction.model_odds}
                  sportsbook_odds={prediction.sportsbook_odds}
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
      <div className="mt-8 bg-gray-900/40 backdrop-blur-sm border border-gray-800 rounded-xl p-4">
        <div className="flex items-center gap-8 max-md:flex-col max-md:items-start max-md:gap-4 text-sm">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-green-500" />
            <span className="text-gray-400">Positive Edge (Model favored)</span>
          </div>
          <div className="flex items-center gap-2">
            <TrendingDown className="w-4 h-4 text-red-500" />
            <span className="text-gray-400">
              Negative Edge (Sportsbook favored)
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className="text-gray-400">
              Edge = Expected Value vs. Sportsbook
            </div>
          </div>
        </div>
      </div>

      {/* Gambling Disclaimer */}
      <GamblingDisclaimer />
      </div>
    </div>
  );
}
