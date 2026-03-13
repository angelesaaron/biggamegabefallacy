import Image from 'next/image';
import { TrendingUp, TrendingDown, Minus, AlertCircle } from 'lucide-react';
import { SurfaceCard } from '@/components/ui/SurfaceCard';
import type { PlayerPrediction } from '@/types/ui';

interface PredictionSummaryProps {
  prediction: PlayerPrediction;
}

export function PredictionSummary({ prediction }: PredictionSummaryProps) {
  const isPredictionMissing =
    isNaN(prediction.modelProbability) ||
    prediction.modelImpliedOdds === 'NaN' ||
    prediction.modelImpliedOdds === 'N/A';

  const edgeColor =
    prediction.edge === 'positive'
      ? 'text-sr-success'
      : prediction.edge === 'negative'
      ? 'text-sr-danger'
      : 'text-sr-text-dim';

  const EdgeIcon =
    prediction.edge === 'positive'
      ? TrendingUp
      : prediction.edge === 'negative'
      ? TrendingDown
      : Minus;

  const edgeBorderClass =
    prediction.edge === 'positive'
      ? 'bg-sr-success/10 border-sr-success/20'
      : prediction.edge === 'negative'
      ? 'bg-sr-danger/10 border-sr-danger/20'
      : 'bg-sr-surface/40 border-sr-border';

  if (isPredictionMissing) {
    return (
      <SurfaceCard className="p-8 max-md:p-4">
        <div className="text-center">
          <div className="flex items-center justify-center gap-2 mb-4">
            <AlertCircle className="w-6 h-6 text-yellow-500" />
            <h3 className="text-xl text-yellow-500">Prediction Not Available</h3>
          </div>
          <p className="text-sr-text-muted mb-2">
            {prediction.week && prediction.year
              ? `Week ${prediction.week} predictions haven't been generated yet.`
              : 'Prediction data is not available for this player.'}
          </p>
          <p className="text-sm text-sr-text-dim">
            Check back after the weekly batch job completes or try viewing a previous week.
          </p>
        </div>
      </SurfaceCard>
    );
  }

  return (
    <div className={`border rounded-card p-8 max-md:p-4 ${edgeBorderClass}`}>
      <div className="text-center mb-6 max-md:mb-4">
        {prediction.week && prediction.year && (
          <div className="mb-2 max-md:mb-1">
            <span className="text-xs text-sr-text-dim nums">
              {prediction.year} Week {prediction.week}
            </span>
          </div>
        )}
        <h3 className="text-sr-text-muted max-md:text-sm mb-3 max-md:mb-2">Model TD Probability</h3>
        <div className="text-7xl max-md:text-5xl text-white mb-2 nums">{prediction.modelProbability}%</div>
        <div className="text-xl max-md:text-base text-sr-text-muted">
          Implied Odds: <span className="nums">{prediction.modelImpliedOdds}</span>
        </div>
      </div>

      {/* Probability Bar */}
      <div className="mb-8 max-md:mb-6">
        <div className="h-3 max-md:h-2 bg-sr-surface rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-sr-primary to-sr-primary/60 rounded-full transition-all"
            style={{ width: `${prediction.modelProbability}%` }}
          />
        </div>
      </div>

      {/* Odds Comparison */}
      <div className="grid grid-cols-3 gap-6 max-md:gap-3 mb-6 max-md:mb-4">
        <div className="text-center">
          <div className="text-sm max-md:text-xs text-sr-text-dim mb-2 max-md:mb-1">Model Odds</div>
          <div className="text-2xl max-md:text-lg text-sr-primary nums">{prediction.modelImpliedOdds}</div>
        </div>
        <div className="text-center flex flex-col items-center justify-center">
          <div className={`${edgeColor} flex items-center gap-2 max-md:gap-1`}>
            <EdgeIcon className="w-6 h-6" />
            <span className="text-xl max-md:text-base nums">
              {prediction.edge === 'positive' ? '+' : ''}
              {prediction.edgeValue.toFixed(1)}%
            </span>
          </div>
          <div className="text-xs text-sr-text-dim mt-1">Edge</div>
        </div>
        <div className="text-center">
          <div className="text-sm max-md:text-xs text-sr-text-dim mb-2 max-md:mb-1">Sportsbook Odds</div>
          <div className="flex items-center justify-center gap-2">
            <div className="text-2xl max-md:text-lg text-white nums">{prediction.sportsbookOdds}</div>
            {prediction.sportsbookOdds !== 'N/A' && (
              <Image src="/dk-logo-small.png" alt="DraftKings" width={16} height={16} className="ml-1" />
            )}
          </div>
        </div>
      </div>

      {/* Edge Indicator */}
      <div className={`text-center p-4 max-md:p-3 rounded-xl ${edgeBorderClass}`}>
        <span className={`${edgeColor} max-md:text-xs`}>
          {prediction.edge === 'positive' && '✓ Model shows value — Consider this bet'}
          {prediction.edge === 'negative' && '⚠ Sportsbook favored — Avoid this bet'}
          {prediction.edge === 'neutral' && '○ Neutral value — No clear edge'}
        </span>
      </div>
    </div>
  );
}
