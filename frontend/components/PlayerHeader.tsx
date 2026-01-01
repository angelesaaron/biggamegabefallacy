interface Player {
  id: string;
  name: string;
  team: string;
  position: string;
  jersey: number;
  imageUrl: string;
  tdsThisSeason: number;
  gamesPlayed: number;
  targets: number;
  tdRate: string;
}

interface PlayerHeaderProps {
  player: Player;
}

export function PlayerHeader({ player }: PlayerHeaderProps) {
  return (
    <div className="bg-gray-900/40 backdrop-blur-sm border border-gray-800 rounded-2xl p-6 max-md:p-4">
      <div className="flex items-start gap-6 max-md:flex-col max-md:items-center max-md:gap-4">
        {/* Player Image */}
        <img
          src={player.imageUrl}
          alt={player.name}
          className="w-24 h-24 max-md:w-20 max-md:h-20 rounded-full object-cover border-2 border-purple-600"
        />

        {/* Player Info */}
        <div className="flex-1 max-md:text-center">
          <h2 className="text-3xl max-md:text-2xl text-white mb-2">{player.name}</h2>
          <div className="flex items-center gap-4 max-md:justify-center max-md:gap-3 text-gray-400 max-md:text-sm mb-4">
            <span>{player.team}</span>
            <span>•</span>
            <span>{player.position}</span>
          </div>

          {/* Quick Stats */}
          <div className="grid grid-cols-4 gap-6 max-md:grid-cols-2 max-md:gap-4">
            <div>
              <div className="text-2xl max-md:text-xl text-white">{player.tdsThisSeason}</div>
              <div className="text-sm max-md:text-xs text-gray-500">TDs This Season</div>
            </div>
            <div>
              <div className="text-2xl max-md:text-xl text-white">{player.gamesPlayed}</div>
              <div className="text-sm max-md:text-xs text-gray-500">Games Played</div>
            </div>
            <div>
              <div className="text-2xl max-md:text-xl text-white">{player.targets}</div>
              <div className="text-sm max-md:text-xs text-gray-500">Targets</div>
            </div>
            <div>
              <div className="text-2xl max-md:text-xl text-white">{player.tdRate}</div>
              <div className="text-sm max-md:text-xs text-gray-500">TD Rate</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
