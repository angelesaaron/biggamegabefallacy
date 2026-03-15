'use client';

import { TierPlayerCard } from '@/components/weekly/TierPlayerCard';
import type { PredictionResponse, PredictionTier } from '@/types/backend';

interface TierSectionProps {
  tier: PredictionTier;
  label: string;
  descriptor: string;
  accentClass: string;
  headerTextClass: string;
  predictions: PredictionResponse[];
  startRank?: number;
  onPlayerClick?: (playerId: string) => void;
  children?: React.ReactNode;
}

export function TierSection({
  label,
  descriptor,
  accentClass,
  headerTextClass,
  predictions,
  startRank = 1,
  onPlayerClick,
  children,
}: TierSectionProps) {
  const cards = (
    <div className="flex flex-col gap-2">
      {predictions.length === 0 && !children ? (
        <p className="text-sr-text-muted text-sm py-4 px-2">
          No {label.toLowerCase()} plays identified this week.
        </p>
      ) : predictions.length > 0 ? (
        predictions.map((pred, i) => (
          <TierPlayerCard
            key={pred.player_id}
            prediction={pred}
            rank={startRank + i}
            onClick={onPlayerClick}
          />
        ))
      ) : null}
      {children}
    </div>
  );

  return (
    <section className="mb-8">
      {/* Section header */}
      <div className={`flex items-baseline gap-3 mb-3 pb-2 border-b ${accentClass}`}>
        <h2 className={`text-base font-semibold ${headerTextClass}`}>{label}</h2>
        <span className="text-sr-text-dim text-xs">{descriptor}</span>
      </div>

      {cards}
    </section>
  );
}
