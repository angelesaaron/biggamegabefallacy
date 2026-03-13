import Image from 'next/image';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface ValuePlayerCardProps {
  player_id: string;
  player_name: string;
  team_name: string | null;
  position: string | null;
  headshot_url: string | null;
  td_likelihood: number;
  model_odds: string;
  sportsbook_odds?: number;
  edge_value?: number;
  rank: number;
  onClick?: (playerId: string) => void;
}

export function ValuePlayerCard({
  player_id,
  player_name,
  team_name,
  position,
  headshot_url,
  td_likelihood,
  model_odds,
  sportsbook_odds,
  edge_value,
  rank,
  onClick,
}: ValuePlayerCardProps) {
  const edgeType =
    edge_value !== undefined && edge_value > 0
      ? 'positive'
      : edge_value !== undefined && edge_value < 0
      ? 'negative'
      : 'neutral';

  const edgePillClass =
    edgeType === 'positive'
      ? 'text-sr-success bg-sr-success/10'
      : edgeType === 'negative'
      ? 'text-sr-danger bg-sr-danger/10'
      : 'text-sr-text-dim bg-sr-surface/40';

  const EdgeIcon =
    edgeType === 'positive'
      ? TrendingUp
      : edgeType === 'negative'
      ? TrendingDown
      : Minus;

  // Format model odds to American odds string
  const formatModelOdds = (odds: string) => {
    const n = parseFloat(odds);
    if (isNaN(n)) return odds;
    const r = Math.round(n);
    return r > 0 ? `+${r}` : `${r}`;
  };

  const sbOdds = sportsbook_odds;
  const sbOddsStr =
    sbOdds !== undefined && sbOdds !== null
      ? sbOdds > 0
        ? `+${sbOdds}`
        : `${sbOdds}`
      : null;

  return (
    <div
      className="flex items-center gap-3 p-4 bg-sr-surface/40 border border-sr-border rounded-card hover:border-sr-primary/40 transition-colors cursor-pointer"
      onClick={() => onClick?.(player_id)}
    >
      {/* Rank */}
      <span className="text-sr-text-dim text-sm w-6 text-center nums flex-shrink-0">
        {rank}
      </span>

      {/* Avatar */}
      {headshot_url ? (
        <Image
          src={headshot_url}
          alt={player_name}
          width={40}
          height={40}
          className="rounded-full object-cover flex-shrink-0"
        />
      ) : (
        <div className="w-10 h-10 rounded-full bg-sr-surface flex-shrink-0 flex items-center justify-center">
          <span className="text-sr-text-muted text-sm font-bold">
            {player_name.charAt(0)}
          </span>
        </div>
      )}

      {/* Name + team */}
      <div className="flex-1 min-w-0">
        <p className="text-white font-medium text-sm truncate">{player_name}</p>
        <p className="text-sr-text-muted text-xs">
          {team_name ?? 'N/A'} · {position ?? 'N/A'}
        </p>
      </div>

      {/* Edge pill */}
      {edge_value !== undefined && (
        <span
          className={`text-xs font-semibold px-2 py-0.5 rounded-badge nums flex items-center gap-1 flex-shrink-0 ${edgePillClass}`}
        >
          <EdgeIcon size={12} />
          {edgeType === 'positive' ? '+' : ''}
          {(edge_value * 100).toFixed(1)}%
        </span>
      )}

      {/* Odds block: fixed-width columns prevent digit-count shifting */}
      <div className="grid gap-x-6 flex-shrink-0" style={{ gridTemplateColumns: '3rem 3rem' }}>
        {/* Row 1: odds */}
        <span className="text-sr-primary font-semibold text-sm nums text-right">{formatModelOdds(model_odds)}</span>
        <span className="text-white font-semibold text-sm nums text-right hidden sm:block">{sbOddsStr ?? 'N/A'}</span>
        {/* Row 2: secondary */}
        <span className="text-sr-text-muted text-xs nums text-right leading-4">{(td_likelihood * 100).toFixed(0)}%</span>
        <div className="hidden sm:flex w-full justify-end pr-2">
          <Image src="/dk-logo-small.png" alt="DraftKings" width={16} height={16} />
        </div>
      </div>
    </div>
  );
}
