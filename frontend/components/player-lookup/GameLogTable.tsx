import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import type { GameLogRow } from '@/types/ui';

interface GameLogTableProps {
  data: GameLogRow[];
  currentWeek: number;
}

export function GameLogTable({ data, currentWeek }: GameLogTableProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  return (
    <div className="bg-sr-surface/40 border border-sr-border rounded-card overflow-hidden">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-6 py-4 max-md:px-4 max-md:py-3 flex items-center justify-between hover:bg-sr-surface/60 transition-colors"
      >
        <h3 className="text-xl max-md:text-lg text-white">Game Log</h3>
        {isExpanded ? (
          <ChevronUp className="w-5 h-5 text-sr-text-muted" />
        ) : (
          <ChevronDown className="w-5 h-5 text-sr-text-muted" />
        )}
      </button>

      {isExpanded && (
        <div className="border-t border-sr-border">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[600px]">
              <thead className="bg-sr-surface/60">
                <tr>
                  <th className="px-6 py-3 max-md:px-3 max-md:py-2 text-left text-sm max-md:text-xs text-sr-text-muted">Week</th>
                  <th className="px-6 py-3 max-md:px-3 max-md:py-2 text-left text-sm max-md:text-xs text-sr-text-muted">Opp</th>
                  <th className="px-6 py-3 max-md:px-3 max-md:py-2 text-right text-sm max-md:text-xs text-sr-text-muted">Tgts</th>
                  <th className="px-6 py-3 max-md:px-3 max-md:py-2 text-right text-sm max-md:text-xs text-sr-text-muted">Yds</th>
                  <th className="px-6 py-3 max-md:px-3 max-md:py-2 text-right text-sm max-md:text-xs text-sr-text-muted">TD</th>
                  <th className="px-6 py-3 max-md:px-3 max-md:py-2 text-right text-sm max-md:text-xs text-sr-text-muted">Model %</th>
                </tr>
              </thead>
              <tbody>
                {data.map((game, index) => (
                  <tr
                    key={index}
                    className={`border-t border-sr-border/50 hover:bg-sr-surface/40 transition-colors ${
                      game.td > 0 ? 'bg-sr-success/5' : ''
                    }`}
                  >
                    <td className="px-6 py-4 max-md:px-3 max-md:py-3 max-md:text-sm text-white">
                      <div className="flex items-center gap-2">
                        {game.td > 0 && (
                          <div className="w-2 h-2 rounded-full bg-sr-success" />
                        )}
                        <span className="nums">{game.week}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 max-md:px-3 max-md:py-3 max-md:text-sm text-sr-text-muted">{game.opponent}</td>
                    <td className="px-6 py-4 max-md:px-3 max-md:py-3 text-right max-md:text-sm text-sr-text-muted">
                      <span className="nums">{game.targets}</span>
                    </td>
                    <td className="px-6 py-4 max-md:px-3 max-md:py-3 text-right max-md:text-sm text-sr-text-muted">
                      <span className="nums">{game.yards}</span>
                    </td>
                    <td className="px-6 py-4 max-md:px-3 max-md:py-3 text-right max-md:text-sm">
                      <span className={`nums ${game.td > 0 ? 'text-sr-success' : 'text-sr-text-dim'}`}>
                        {game.td}
                      </span>
                    </td>
                    <td className="px-6 py-4 max-md:px-3 max-md:py-3 text-right max-md:text-sm">
                      {game.modelProbability
                        ? <span className="nums text-sr-primary">{game.modelProbability}%</span>
                        : <span className="text-sr-text-dim">—</span>
                      }
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="px-4 py-2 text-xs text-sr-text-dim bg-sr-bg/50 md:hidden">
            Swipe to see all columns →
          </div>
        </div>
      )}
    </div>
  );
}
