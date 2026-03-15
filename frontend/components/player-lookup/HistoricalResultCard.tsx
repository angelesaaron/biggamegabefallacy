interface HistoricalResultCardProps {
  week: number;
  year: number;
  tier: string | null;
  modelProbability: number | null; // 0-100
  td: boolean; // did the player score a TD that week?
  edge: 'positive' | 'neutral' | 'negative';
  edgeValue: number | null; // percentage, e.g. 8.4
}

const TIER_CONFIG: Record<string, { label: string; className: string }> = {
  high_conviction: { label: 'High Conviction', className: 'bg-sr-success/20 text-sr-success border border-sr-success/30' },
  value_play: { label: 'Value Play', className: 'bg-amber-500/20 text-amber-400 border border-amber-500/30' },
  on_the_radar: { label: 'On the Radar', className: 'bg-sr-surface text-sr-text-muted border border-sr-border' },
  fade_volume_trap: { label: 'Fade — Volume Trap', className: 'bg-sr-danger/20 text-sr-danger border border-sr-danger/30' },
  fade_overpriced: { label: 'Fade — Overpriced', className: 'bg-sr-danger/20 text-sr-danger border border-sr-danger/30' },
};

function getVerdictConfig(
  td: boolean,
  edge: 'positive' | 'neutral' | 'negative'
): { label: string; className: string } {
  if (edge === 'neutral') {
    return { label: 'No Clear Edge', className: 'text-sr-text-muted' };
  }
  const modelWasRight =
    (td && edge === 'positive') || (!td && edge === 'negative');
  return modelWasRight
    ? { label: 'Edge + Right', className: 'text-sr-success' }
    : { label: 'Edge + Wrong', className: 'text-sr-danger' };
}

export function HistoricalResultCard({
  week,
  year,
  tier,
  modelProbability,
  td,
  edge,
  edgeValue,
}: HistoricalResultCardProps) {
  const verdict = getVerdictConfig(td, edge);

  const edgeDisplay =
    edgeValue !== null
      ? `${edge === 'positive' ? '+' : ''}${edgeValue.toFixed(1)}%`
      : '--';

  return (
    <div className="bg-sr-surface/40 border border-sr-border rounded-card p-6 max-md:p-4">
      {/* Header row */}
      <div className="flex items-center justify-between mb-4 max-md:mb-3">
        <span className="text-xs text-sr-text-dim nums">
          Week {week} · {year}
        </span>
        {tier && TIER_CONFIG[tier] && (
          <span className={`text-xs font-semibold px-3 py-1 rounded-badge ${TIER_CONFIG[tier].className}`}>
            {TIER_CONFIG[tier].label}
          </span>
        )}
      </div>

      {/* Two-column body */}
      <div className="grid grid-cols-2 gap-4 max-md:gap-3 mb-4 max-md:mb-3">
        {/* Model Predicted */}
        <div className="bg-sr-surface/60 rounded-xl p-4 max-md:p-3 flex flex-col items-center justify-center text-center">
          <div className="text-xs text-sr-text-dim mb-2">Model Predicted</div>
          <span className="text-4xl max-md:text-3xl text-white nums">
            {modelProbability !== null ? `${modelProbability}%` : '--'}
          </span>
        </div>

        {/* Outcome */}
        <div className="bg-sr-surface/60 rounded-xl p-4 max-md:p-3 flex flex-col items-center justify-center text-center">
          <div className="text-xs text-sr-text-dim mb-2">Outcome</div>
          {td ? (
            <div className="text-sr-success font-semibold text-lg max-md:text-base">
              ✔ TD Scored
            </div>
          ) : (
            <div className="text-sr-text-muted font-semibold text-lg max-md:text-base">
              ✘ No TD
            </div>
          )}
        </div>
      </div>

      {/* Bottom strip — edge verdict */}
      <div className="flex items-center gap-2 text-sm max-md:text-xs text-sr-text-dim">
        <span>vs. Book:</span>
        <span className="nums font-medium">{edgeDisplay}</span>
        <span>—</span>
        <span className={`font-semibold ${verdict.className}`}>{verdict.label}</span>
      </div>
    </div>
  );
}
