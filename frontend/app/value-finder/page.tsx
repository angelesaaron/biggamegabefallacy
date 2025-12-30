'use client';

import { useEffect, useState } from 'react';
import { ValuePlayerCard } from '@/components/ValuePlayerCard';
import { TrendingUp, TrendingDown } from 'lucide-react';

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

export default function ValueFinderPage() {
  const [predictions, setPredictions] = useState<ValuePick[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSportsbook, setSelectedSportsbook] = useState<
    'draftkings' | 'fanduel'
  >('draftkings');
  const [showOnlyEdge, setShowOnlyEdge] = useState(true);

  useEffect(() => {
    async function loadPredictions() {
      try {
        setLoading(true);
        setError(null);

        const API_URL =
          process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

        const response = await fetch(`${API_URL}/api/predictions/current`);
        if (!response.ok) throw new Error('Failed to fetch predictions');

        const preds: Prediction[] = await response.json();

        // Fetch odds for each prediction
        const predsWithOdds = await Promise.all(
          preds.map(async (pred: Prediction) => {
            try {
              const oddsData = await fetch(
                `${API_URL}/api/odds/comparison/${pred.player_id}?week=${pred.week}&year=${pred.season_year}`
              ).then((r) => r.json());

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
  }, [selectedSportsbook]);

  const filteredPredictions = showOnlyEdge
    ? predictions.filter((p) => p.has_edge)
    : predictions;

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <div className="text-white text-xl">Loading predictions...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <div className="text-red-500 text-xl">Error: {error}</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">
      {/* Top Navigation */}
      <nav className="border-b border-gray-800 bg-black/40 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-8">
              <h1 className="text-2xl tracking-tight text-white">BGGTDM</h1>
              <div className="flex gap-1 bg-gray-900/50 rounded-lg p-1">
                <button className="px-6 py-2 rounded-md bg-purple-600 text-white">
                  Weekly Value
                </button>
              </div>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <h2 className="text-3xl text-white mb-2">
            Week{' '}
            {predictions.length > 0 ? predictions[0].week : '?'} Value Plays
          </h2>
          <p className="text-gray-400">
            Players with the highest model edge vs sportsbook odds
          </p>
        </div>

        {/* Filters */}
        <div className="mb-6 flex items-center gap-4">
          <div className="flex gap-2 bg-gray-900/50 rounded-lg p-1">
            <button
              onClick={() => setSelectedSportsbook('draftkings')}
              className={`px-4 py-2 rounded-md transition-all ${
                selectedSportsbook === 'draftkings'
                  ? 'bg-purple-600 text-white'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              DraftKings
            </button>
            <button
              onClick={() => setSelectedSportsbook('fanduel')}
              className={`px-4 py-2 rounded-md transition-all ${
                selectedSportsbook === 'fanduel'
                  ? 'bg-purple-600 text-white'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              FanDuel
            </button>
          </div>

          <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
            <input
              type="checkbox"
              checked={showOnlyEdge}
              onChange={(e) => setShowOnlyEdge(e.target.checked)}
              className="w-4 h-4 rounded bg-gray-800 border-gray-700 text-purple-600 focus:ring-purple-600"
            />
            Show only +EV plays
          </label>
        </div>

        {/* Value Player Cards */}
        {filteredPredictions.length === 0 ? (
          <div className="bg-gray-900/40 backdrop-blur-sm border border-gray-800 rounded-xl p-12 text-center">
            <p className="text-gray-400 text-lg">
              {showOnlyEdge
                ? 'No positive EV plays found for this sportsbook'
                : 'No predictions available'}
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
              />
            ))}
          </div>
        )}

        {/* Legend */}
        <div className="mt-8 bg-gray-900/40 backdrop-blur-sm border border-gray-800 rounded-xl p-4">
          <div className="flex items-center gap-8 text-sm">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-green-500" />
              <span className="text-gray-400">
                Positive Edge (Model favored)
              </span>
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
      </div>
    </div>
  );
}
