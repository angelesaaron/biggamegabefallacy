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
    edge_value && edge_value > 0
      ? 'positive'
      : edge_value && edge_value < 0
      ? 'negative'
      : 'neutral';

  const getEdgeColor = () => {
    if (edgeType === 'positive') return 'text-green-500';
    if (edgeType === 'negative') return 'text-red-500';
    return 'text-gray-500';
  };

  const getEdgeIcon = () => {
    if (edgeType === 'positive')
      return <TrendingUp className="w-5 h-5" />;
    if (edgeType === 'negative')
      return <TrendingDown className="w-5 h-5" />;
    return <Minus className="w-5 h-5" />;
  };

  const getEdgeBg = () => {
    if (edgeType === 'positive') return 'bg-green-500/10 border-green-500/30';
    if (edgeType === 'negative') return 'bg-red-500/10 border-red-500/30';
    return 'bg-gray-500/10 border-gray-500/30';
  };

  // Format sportsbook odds to American odds string
  const formatSportsbookOdds = (odds?: number) => {
    if (!odds) return 'N/A';
    return odds > 0 ? `+${odds}` : `${odds}`;
  };

  // Format model odds to American odds string with + prefix and rounding
  const formatModelOdds = (odds: string) => {
    const numOdds = parseFloat(odds);
    if (isNaN(numOdds)) return odds;
    const rounded = Math.round(numOdds);
    return rounded > 0 ? `+${rounded}` : `${rounded}`;
  };

  return (
    <div
      onClick={() => onClick?.(player_id)}
      className="bg-gray-900/40 backdrop-blur-sm border border-gray-800 rounded-xl p-6 hover:border-purple-600/50 transition-all cursor-pointer group"
    >
      <div className="flex items-center gap-6">
        <div className="text-3xl text-gray-600 w-12 text-center shrink-0">#{rank}</div>
        <div className="flex items-center gap-4 flex-1 min-w-0">
          <img
            src={headshot_url || '/placeholder-player.png'}
            alt={player_name}
            className="w-16 h-16 rounded-full object-cover border-2 border-gray-700 group-hover:border-purple-600 transition-colors shrink-0"
            onError={(e) => {
              e.currentTarget.src =
                'https://via.placeholder.com/64/374151/9ca3af?text=' +
                (player_name?.[0] || 'P');
            }}
          />
          <div className="min-w-0 flex-1">
            <h3 className="text-xl text-white group-hover:text-purple-400 transition-colors truncate">
              {player_name}
            </h3>
            <div className="flex items-center gap-2 text-sm text-gray-400">
              <span>{team_name || 'N/A'}</span>
              <span>•</span>
              <span>{position || 'N/A'}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-6">
          <div className="text-center">
            <div className="text-sm text-gray-500 mb-1">Model %</div>
            <div className="text-2xl text-purple-400">{(td_likelihood * 100).toFixed(1)}%</div>
          </div>
          {edge_value !== undefined && (
            <div className={`text-center px-6 py-3 rounded-lg border ${getEdgeBg()}`}>
              <div className="text-sm text-gray-500 mb-1">Edge</div>
              <div className={`flex items-center justify-center gap-2 ${getEdgeColor()}`}>
                {getEdgeIcon()}
                <span className="text-xl">
                  {edgeType === 'positive' ? '+' : ''}
                  {(edge_value * 100).toFixed(1)}%
                </span>
              </div>
            </div>
          )}
          <div className="text-center">
            <div className="text-sm text-gray-500 mb-1">Model Odds</div>
            <div className="text-xl text-purple-400">{formatModelOdds(model_odds)}</div>
          </div>
          {sportsbook_odds !== undefined && (
            <div className="text-center">
              <div className="text-sm text-gray-500 mb-1">Sportsbook</div>
              <div className="text-xl text-white">{formatSportsbookOdds(sportsbook_odds)}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
