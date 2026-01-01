import { useState, useRef, useEffect } from 'react';
import { Search, ChevronDown } from 'lucide-react';

interface Player {
  id: string;
  name: string;
  team: string;
  position: string;
  jersey: number;
  imageUrl: string;
}

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
        className="w-full bg-gray-900/60 backdrop-blur-sm border border-gray-800 rounded-xl px-4 py-3 flex items-center justify-between hover:border-gray-700 transition-colors"
      >
        {selectedPlayer && (
          <div className="flex items-center gap-3">
            <img
              src={selectedPlayer.imageUrl}
              alt={selectedPlayer.name}
              className="w-10 h-10 rounded-full object-cover"
            />
            <div className="text-left">
              <div className="text-white">{selectedPlayer.name}</div>
              <div className="text-sm text-gray-400">
                {selectedPlayer.team} • {selectedPlayer.position}
              </div>
            </div>
          </div>
        )}
        <ChevronDown className={`w-5 h-5 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute top-full mt-2 w-full bg-gray-900 border border-gray-800 rounded-xl overflow-hidden z-50 shadow-2xl">
          <div className="p-3 border-b border-gray-800">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
              <input
                type="text"
                placeholder="Search players..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-10 pr-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-purple-600"
                autoFocus
              />
            </div>
          </div>
          <div className="max-h-96 overflow-y-auto">
            {filteredPlayers.map(player => (
              <button
                key={player.id}
                onClick={() => handleSelectPlayer(player.id)}
                className="w-full px-4 py-3 flex items-center gap-3 hover:bg-gray-800 transition-colors"
              >
                <img
                  src={player.imageUrl}
                  alt={player.name}
                  className="w-10 h-10 rounded-full object-cover"
                />
                <div className="text-left flex-1">
                  <div className="text-white">{player.name}</div>
                  <div className="text-sm text-gray-400">
                    {player.team} • {player.position}
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
