import { TrendingUp, TrendingDown, Minus, AlertCircle } from 'lucide-react';

interface Prediction {
  playerId: string;
  modelProbability: number;
  modelImpliedOdds: string;
  sportsbookOdds: string;
  edge: 'positive' | 'neutral' | 'negative';
  edgeValue: number;
  week?: number;
  year?: number;
}

interface PredictionSummaryProps {
  prediction: Prediction;
}

export function PredictionSummary({ prediction }: PredictionSummaryProps) {
  // Check if prediction data is missing/invalid
  const isPredictionMissing =
    isNaN(prediction.modelProbability) ||
    prediction.modelImpliedOdds === 'NaN' ||
    prediction.modelImpliedOdds === 'N/A';

  const getEdgeColor = () => {
    if (prediction.edge === 'positive') return 'text-green-500';
    if (prediction.edge === 'negative') return 'text-red-500';
    return 'text-gray-500';
  };

  const getEdgeIcon = () => {
    if (prediction.edge === 'positive') return <TrendingUp className="w-6 h-6" />;
    if (prediction.edge === 'negative') return <TrendingDown className="w-6 h-6" />;
    return <Minus className="w-6 h-6" />;
  };

  const getEdgeBg = () => {
    if (prediction.edge === 'positive') return 'bg-green-500/10 border-green-500/20';
    if (prediction.edge === 'negative') return 'bg-red-500/10 border-red-500/20';
    return 'bg-gray-500/10 border-gray-500/20';
  };

  // Show unavailable state if prediction data is missing
  if (isPredictionMissing) {
    return (
      <div className="border border-gray-800 rounded-2xl p-8 max-md:p-4 bg-gray-900/40">
        <div className="text-center">
          <div className="flex items-center justify-center gap-2 mb-4">
            <AlertCircle className="w-6 h-6 text-yellow-500" />
            <h3 className="text-xl text-yellow-500">Prediction Not Available</h3>
          </div>
          <p className="text-gray-400 mb-2">
            {prediction.week && prediction.year
              ? `Week ${prediction.week} predictions haven't been generated yet.`
              : 'Prediction data is not available for this player.'}
          </p>
          <p className="text-sm text-gray-500">
            Check back after the weekly batch job completes or try viewing a previous week.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={`border rounded-2xl p-8 max-md:p-4 ${getEdgeBg()}`}>
      <div className="text-center mb-6 max-md:mb-4">
        <div className="flex items-center justify-center gap-2 mb-3 max-md:mb-2">
          <h3 className="text-gray-400 max-md:text-sm">Model TD Probability</h3>
          {prediction.week && prediction.year && (
            <span className="text-xs text-gray-500 px-2 py-0.5 bg-gray-800/50 rounded-md">
              {prediction.year} Week {prediction.week}
            </span>
          )}
        </div>
        <div className="text-7xl max-md:text-5xl text-white mb-2">{prediction.modelProbability}%</div>
        <div className="text-xl max-md:text-base text-gray-400">Implied Odds: {prediction.modelImpliedOdds}</div>
      </div>

      {/* Probability Bar */}
      <div className="mb-8 max-md:mb-6">
        <div className="h-3 max-md:h-2 bg-gray-800 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-purple-600 to-purple-400 rounded-full transition-all"
            style={{ width: `${prediction.modelProbability}%` }}
          />
        </div>
      </div>

      {/* Odds Comparison */}
      <div className="grid grid-cols-3 gap-6 max-md:gap-3 mb-6 max-md:mb-4">
        <div className="text-center">
          <div className="text-sm max-md:text-xs text-gray-500 mb-2 max-md:mb-1">Model Odds</div>
          <div className="text-2xl max-md:text-lg text-purple-400">{prediction.modelImpliedOdds}</div>
        </div>
        <div className="text-center flex flex-col items-center justify-center">
          <div className={`${getEdgeColor()} flex items-center gap-2 max-md:gap-1`}>
            {getEdgeIcon()}
            <span className="text-xl max-md:text-base">
              {prediction.edge === 'positive' ? '+' : ''}
              {prediction.edgeValue.toFixed(1)}%
            </span>
          </div>
          <div className="text-xs text-gray-500 mt-1">Edge</div>
        </div>
        <div className="text-center">
          <div className="text-sm max-md:text-xs text-gray-500 mb-2 max-md:mb-1">Sportsbook Odds</div>
          <div className="text-2xl max-md:text-lg text-white">{prediction.sportsbookOdds}</div>
        </div>
      </div>

      {/* Edge Indicator */}
      <div className={`text-center p-4 max-md:p-3 rounded-xl ${getEdgeBg()}`}>
        <span className={`${getEdgeColor()} max-md:text-xs`}>
          {prediction.edge === 'positive' && '✓ Model shows value - Consider this bet'}
          {prediction.edge === 'negative' && '⚠ Sportsbook favored - Avoid this bet'}
          {prediction.edge === 'neutral' && '○ Neutral value - No clear edge'}
        </span>
      </div>
    </div>
  );
}
