import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';

interface GameLog {
  week: number;
  opponent: string;
  targets: number;
  yards: number;
  td: number;
  modelProbability: number;
}

interface GameLogTableProps {
  data: GameLog[];
}

export function GameLogTable({ data }: GameLogTableProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="bg-gray-900/40 backdrop-blur-sm border border-gray-800 rounded-2xl overflow-hidden">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-6 py-4 max-md:px-4 max-md:py-3 flex items-center justify-between hover:bg-gray-800/50 transition-colors"
      >
        <h3 className="text-xl max-md:text-lg text-white">Game Log</h3>
        {isExpanded ? (
          <ChevronUp className="w-5 h-5 text-gray-400" />
        ) : (
          <ChevronDown className="w-5 h-5 text-gray-400" />
        )}
      </button>

      {isExpanded && (
        <div className="border-t border-gray-800">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[600px]">
              <thead className="bg-gray-800/50">
                <tr>
                  <th className="px-6 py-3 max-md:px-3 max-md:py-2 text-left text-sm max-md:text-xs text-gray-400">Week</th>
                  <th className="px-6 py-3 max-md:px-3 max-md:py-2 text-left text-sm max-md:text-xs text-gray-400">Opp</th>
                  <th className="px-6 py-3 max-md:px-3 max-md:py-2 text-right text-sm max-md:text-xs text-gray-400">Tgts</th>
                  <th className="px-6 py-3 max-md:px-3 max-md:py-2 text-right text-sm max-md:text-xs text-gray-400">Yds</th>
                  <th className="px-6 py-3 max-md:px-3 max-md:py-2 text-right text-sm max-md:text-xs text-gray-400">TD</th>
                  <th className="px-6 py-3 max-md:px-3 max-md:py-2 text-right text-sm max-md:text-xs text-gray-400">Model %</th>
                </tr>
              </thead>
              <tbody>
                {data.map((game, index) => (
                  <tr
                    key={index}
                    className={`border-t border-gray-800/50 hover:bg-gray-800/30 transition-colors ${
                      game.td > 0 ? 'bg-green-500/5' : ''
                    }`}
                  >
                    <td className="px-6 py-4 max-md:px-3 max-md:py-3 max-md:text-sm text-white">
                      <div className="flex items-center gap-2">
                        {game.td > 0 && (
                          <div className="w-2 h-2 rounded-full bg-green-500" />
                        )}
                        {game.week}
                      </div>
                    </td>
                    <td className="px-6 py-4 max-md:px-3 max-md:py-3 max-md:text-sm text-gray-300">{game.opponent}</td>
                    <td className="px-6 py-4 max-md:px-3 max-md:py-3 text-right max-md:text-sm text-gray-300">{game.targets}</td>
                    <td className="px-6 py-4 max-md:px-3 max-md:py-3 text-right max-md:text-sm text-gray-300">{game.yards}</td>
                    <td className="px-6 py-4 max-md:px-3 max-md:py-3 text-right max-md:text-sm">
                      <span className={game.td > 0 ? 'text-green-400' : 'text-gray-500'}>
                        {game.td}
                      </span>
                    </td>
                    <td className="px-6 py-4 max-md:px-3 max-md:py-3 text-right max-md:text-sm text-purple-400">
                      {game.modelProbability}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="px-4 py-2 text-xs text-gray-500 bg-gray-900/50 md:hidden">
            Swipe to see all columns →
          </div>
        </div>
      )}
    </div>
  );
}
