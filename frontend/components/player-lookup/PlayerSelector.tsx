import { useState, useRef, useEffect } from 'react';
import Image from 'next/image';
import { Search, ChevronDown } from 'lucide-react';
import type { Player } from '@/types/ui';

interface PlayerSelectorProps {
  players: Player[];
  selectedPlayerId: string;
  onSelectPlayer: (playerId: string) => void;
}

export function PlayerSelector({ players, selectedPlayerId, onSelectPlayer }: PlayerSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const dropdownRef = useRef<HTMLDivElement>(null);

  const selectedPlayer = players.find(p => p.id === selectedPlayerId);

  const filteredPlayers = players
    .filter(player =>
      player.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      player.team.toLowerCase().includes(searchQuery.toLowerCase())
    )
    .sort((a, b) => a.name.localeCompare(b.name));

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelectPlayer = (playerId: string) => {
    onSelectPlayer(playerId);
    setIsOpen(false);
    setSearchQuery('');
  };

  return (
    <div ref={dropdownRef} className="relative max-w-md">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full bg-sr-surface/60 border border-sr-border rounded-xl px-4 py-3 flex items-center justify-between hover:border-sr-text-dim transition-colors"
      >
        {selectedPlayer && (
          <div className="flex items-center gap-3">
            {selectedPlayer.imageUrl ? (
              <Image
                src={selectedPlayer.imageUrl}
                alt={selectedPlayer.name}
                width={40}
                height={40}
                className="rounded-full object-cover"
              />
            ) : (
              <div className="w-10 h-10 rounded-full bg-sr-surface flex items-center justify-center">
                <span className="text-sr-text-muted text-sm font-bold">
                  {selectedPlayer.name.charAt(0)}
                </span>
              </div>
            )}
            <div className="text-left">
              <div className="text-white">{selectedPlayer.name}</div>
              <div className="text-sm text-sr-text-muted">
                {selectedPlayer.team} · {selectedPlayer.position}
              </div>
            </div>
          </div>
        )}
        <ChevronDown className={`w-5 h-5 text-sr-text-muted transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute top-full mt-2 w-full max-w-[calc(100vw-2rem)] bg-sr-surface border border-sr-border rounded-xl overflow-hidden z-50 shadow-2xl">
          <div className="p-3 border-b border-sr-border">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-sr-text-dim" />
              <input
                type="text"
                placeholder="Search players..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-sr-bg border border-sr-border rounded-lg pl-10 pr-4 py-2 text-white placeholder-sr-text-dim focus:outline-none focus:border-sr-primary"
              />
            </div>
          </div>
          <div className="max-h-96 overflow-y-auto">
            {filteredPlayers.map(player => (
              <button
                key={player.id}
                onClick={() => handleSelectPlayer(player.id)}
                className="w-full px-4 py-3 flex items-center gap-3 hover:bg-sr-surface/80 transition-colors"
              >
                {player.imageUrl ? (
                  <Image
                    src={player.imageUrl}
                    alt={player.name}
                    width={40}
                    height={40}
                    className="rounded-full object-cover"
                  />
                ) : (
                  <div className="w-10 h-10 rounded-full bg-sr-bg flex items-center justify-center flex-shrink-0">
                    <span className="text-sr-text-muted text-sm font-bold">
                      {player.name.charAt(0)}
                    </span>
                  </div>
                )}
                <div className="text-left flex-1">
                  <div className="text-white">{player.name}</div>
                  <div className="text-sm text-sr-text-muted">
                    {player.team} · {player.position}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
