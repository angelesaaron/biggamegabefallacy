import Image from 'next/image';
import { SurfaceCard } from '@/components/ui/SurfaceCard';
import type { Player } from '@/types/ui';

interface PlayerHeaderProps {
  player: Player;
}

const STATS = [
  { key: 'tdsThisSeason', label: 'TDs This Season' },
  { key: 'gamesPlayed', label: 'Games Played' },
  { key: 'targets', label: 'Targets' },
  { key: 'tdRate', label: 'TD Rate' },
] as const;

export function PlayerHeader({ player }: PlayerHeaderProps) {
  return (
    <SurfaceCard className="p-4 md:p-6">
      <div className="flex flex-col md:flex-row items-center md:items-start gap-4 md:gap-6">
        {/* Player Image */}
        {player.imageUrl ? (
          <Image
            src={player.imageUrl}
            alt={player.name}
            width={96}
            height={96}
            className="w-20 h-20 md:w-24 md:h-24 rounded-full object-cover border-2 border-sr-primary flex-shrink-0"
          />
        ) : (
          <div className="w-20 h-20 md:w-24 md:h-24 rounded-full bg-sr-surface border-2 border-sr-primary flex-shrink-0 flex items-center justify-center">
            <span className="text-sr-text-muted text-2xl font-bold">
              {player.name.charAt(0)}
            </span>
          </div>
        )}

        {/* Player Info */}
        <div className="flex-1 w-full text-center md:text-left">
          <h2 className="text-lg font-medium text-white mb-1">{player.name}</h2>
          <div className="flex items-center gap-2 text-sr-text-muted text-sm mb-4 justify-center md:justify-start">
            <span>{player.team}</span>
            <span>•</span>
            <span>{player.position}</span>
          </div>

          {/* Quick Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {STATS.map(({ key, label }) => (
              <div key={key} className="text-center">
                <p className="text-xs text-sr-text-muted uppercase tracking-wide mb-1">
                  {label}
                </p>
                <p className="text-base font-semibold text-white nums">
                  {player[key]}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </SurfaceCard>
  );
}
