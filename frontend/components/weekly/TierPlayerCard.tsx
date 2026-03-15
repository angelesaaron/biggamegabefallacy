'use client';

import Image from 'next/image';
import type { PredictionResponse, PredictionTier } from '@/types/backend';

interface TierPlayerCardProps {
  prediction: PredictionResponse;
  rank?: number;
  onClick?: (playerId: string) => void;
}

const TIER_BADGE: Record<
  NonNullable<PredictionTier>,
  { label: string; className: string }
> = {
  high_conviction: {
    label: 'High Conv.',
    className: 'bg-sr-success/20 text-sr-success border border-sr-success/30',
  },
  value_play: {
    label: 'Value',
    className: 'bg-amber-500/20 text-amber-400 border border-amber-500/30',
  },
  on_the_radar: {
    label: 'Radar',
    className: 'bg-sr-surface text-sr-text-muted border border-sr-border',
  },
  fade_volume_trap: {
    label: 'Fade',
    className: 'bg-sr-danger/20 text-sr-danger border border-sr-danger/30',
  },
  fade_overpriced: {
    label: 'Fade',
    className: 'bg-sr-danger/20 text-sr-danger border border-sr-danger/30',
  },
};

function formatOdds(n: number | null): string {
  if (n === null) return '--';
  const r = Math.round(n);
  return r > 0 ? `+${r}` : `${r}`;
}

export function TierPlayerCard({
  prediction,
  rank,
  onClick,
}: TierPlayerCardProps) {
  const {
    player_id,
    full_name,
    team,
    position,
    headshot_url,
    final_prob,
    model_odds,
    sportsbook_odds,
    implied_prob,
    favor,
    tier,
  } = prediction;

  const isFade = tier === 'fade_volume_trap' || tier === 'fade_overpriced';

  const badge = tier ? TIER_BADGE[tier] : null;

  const edgeSign = favor !== null && favor > 0 ? '+' : '';
  const edgePct = favor !== null ? `${edgeSign}${(favor * 100).toFixed(1)}%` : null;
  const edgeColor =
    favor !== null && favor > 0
      ? 'text-sr-success'
      : favor !== null && favor < 0
      ? 'text-sr-danger'
      : 'text-sr-text-dim';

  const sbOddsStr =
    sportsbook_odds !== null && sportsbook_odds !== undefined
      ? formatOdds(sportsbook_odds)
      : null;

  const cardBg = isFade
    ? 'bg-sr-danger/5 border-sr-danger/20 hover:border-sr-danger/40'
    : 'bg-sr-surface/40 border-sr-border hover:border-sr-primary/40';

  return (
    <div
      className={`flex items-center gap-3 p-4 border rounded-card transition-colors cursor-pointer ${cardBg}`}
      onClick={() => onClick?.(player_id)}
    >
      {/* Rank — hidden for fades */}
      {!isFade && (
        <span className="text-sr-text-dim text-sm w-6 text-center nums flex-shrink-0">
          {rank ?? ''}
        </span>
      )}

      {/* Avatar */}
      {headshot_url ? (
        <Image
          src={headshot_url}
          alt={full_name}
          width={40}
          height={40}
          className="rounded-full object-cover flex-shrink-0"
        />
      ) : (
        <div className="w-10 h-10 rounded-full bg-sr-surface flex-shrink-0 flex items-center justify-center">
          <span className="text-sr-text-muted text-sm font-bold">{full_name.charAt(0)}</span>
        </div>
      )}

      {/* Name + team/position */}
      <div className="flex-1 min-w-0">
        <p className="text-white font-medium text-sm truncate">{full_name}</p>
        <p className="text-sr-text-muted text-xs">
          {team ?? 'N/A'} · {position ?? 'N/A'}
        </p>
      </div>

      {/* Tier badge */}
      {badge && (
        <span
          className={`text-xs font-semibold px-2 py-0.5 rounded-badge flex-shrink-0 ${badge.className}`}
        >
          {badge.label}
        </span>
      )}

      {/* Fade: book odds vs model odds */}
      {isFade && (
        <div className="grid gap-x-6 flex-shrink-0" style={{ gridTemplateColumns: '3.5rem 3.5rem' }}>
          <span className="text-sr-danger font-semibold text-sm nums text-right">
            {formatOdds(model_odds)}
          </span>
          <span className="text-white font-semibold text-sm nums text-right hidden sm:block">
            {sbOddsStr ?? '—'}
          </span>
          <span className="text-sr-text-dim text-xs nums text-right leading-4">Model</span>
          <div className="hidden sm:flex w-full justify-end pr-1 items-center">
            <Image src="/dk-logo-small.png" alt="DraftKings" width={14} height={14} />
          </div>
        </div>
      )}

      {/* Edge + model odds + model % */}
      {!isFade && (
        <>
          {/* Edge pill */}
          {edgePct !== null && (
            <span
              className={`text-xs font-semibold px-2 py-0.5 rounded-badge nums flex-shrink-0 ${edgeColor}`}
              title="Edge = model probability minus book's implied probability. Positive means model sees more value than the line offered."
            >
              {edgePct}
            </span>
          )}

          {/* Odds block */}
          <div
            className="grid gap-x-6 flex-shrink-0"
            style={{ gridTemplateColumns: '3.5rem 3.5rem' }}
          >
            {/* Model odds */}
            <span className="text-sr-primary font-semibold text-sm nums text-right">
              {formatOdds(model_odds)}
            </span>

            {/* Book odds — always visible */}
            <span className="text-white font-semibold text-sm nums text-right hidden sm:block">
              {sbOddsStr ?? '—'}
            </span>

            {/* Model % row */}
            <span className="text-sr-text-muted text-xs nums text-right leading-4">
              {final_prob !== null ? `${Math.round(final_prob * 100)}%` : '--'}
            </span>

            {/* DK logo row */}
            <div className="hidden sm:flex w-full justify-end pr-1 items-center">
              <Image src="/dk-logo-small.png" alt="DraftKings" width={14} height={14} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
