'use client';

import { useState } from 'react';
import WeeklyValue from '@/components/WeeklyValue';
import { PlayerModel } from '@/components/PlayerModel';

export default function Home() {
  const [activeTab, setActiveTab] = useState<'player' | 'weekly'>('player');
  const [selectedPlayerId, setSelectedPlayerId] = useState<string | null>(null);

  const handlePlayerClick = (playerId: string) => {
    setSelectedPlayerId(playerId);
    setActiveTab('player');
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">
      {/* Top Navigation */}
      <nav className="border-b border-gray-800 bg-black/40 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-8">
              <h1 className="text-2xl tracking-tight text-white">BGGTDM</h1>
              <div className="flex gap-1 bg-gray-900/50 rounded-lg p-1">
                <button
                  onClick={() => setActiveTab('player')}
                  className={`px-6 py-2 rounded-md transition-all ${
                    activeTab === 'player'
                      ? 'bg-purple-600 text-white'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  Player Model
                </button>
                <button
                  onClick={() => setActiveTab('weekly')}
                  className={`px-6 py-2 rounded-md transition-all ${
                    activeTab === 'weekly'
                      ? 'bg-purple-600 text-white'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  Weekly Value
                </button>
              </div>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      {activeTab === 'player' ? (
        <PlayerModel initialPlayerId={selectedPlayerId} />
      ) : (
        <WeeklyValue onPlayerClick={handlePlayerClick} />
      )}
    </div>
  );
}
