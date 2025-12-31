'use client';

import { useState, useEffect } from 'react';
import WeeklyValue from '@/components/WeeklyValue';
import { PlayerModel } from '@/components/PlayerModel';
import SystemStatus from '@/components/SystemStatus';

export default function Home() {
  const [activeTab, setActiveTab] = useState<'player' | 'weekly' | 'status'>('player');
  const [selectedPlayerId, setSelectedPlayerId] = useState<string | null>(null);
  const [currentWeek, setCurrentWeek] = useState<number | null>(null);

  const handlePlayerClick = (playerId: string) => {
    setSelectedPlayerId(playerId);
    setActiveTab('player');
  };

  // Fetch current week on mount
  useEffect(() => {
    async function fetchCurrentWeek() {
      try {
        const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        // Use the same endpoint as System Status for consistency
        const response = await fetch(`${API_URL}/api/admin/data-readiness/current`);
        const data = await response.json();
        const currentWeekData = data.current_week;

        if (currentWeekData) {
          setCurrentWeek(currentWeekData.week);
        }
      } catch (error) {
        console.error('Failed to fetch current week:', error);
      }
    }

    fetchCurrentWeek();
  }, []);

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">
      {/* Top Navigation */}
      <nav className="border-b border-gray-800 bg-black/40 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16 gap-2">
            <div className="flex items-center gap-8">
              {/* Logo with Gabe Davis headshot */}
              <div className="flex items-center gap-3">
                <img
                  src="/gabe-davis-headshot.png"
                  alt="Gabe Davis"
                  className="w-12 h-12 rounded-full object-cover border-2 border-purple-600"
                />
                <h1 className="text-2xl tracking-tight text-white">BGGTDM</h1>
              </div>
              {/* Tab Buttons */}
              <div className="flex gap-1 bg-gray-900/50 rounded-lg p-1">
                <button
                  onClick={() => setActiveTab('player')}
                  className={`px-4 py-2 text-sm rounded-md transition-all ${
                    activeTab === 'player'
                      ? 'bg-purple-600 text-white'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  Player Model
                </button>
                <button
                  onClick={() => setActiveTab('weekly')}
                  className={`px-4 py-2 text-sm rounded-md transition-all ${
                    activeTab === 'weekly'
                      ? 'bg-purple-600 text-white'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  Weekly Value
                </button>
                <button
                  onClick={() => setActiveTab('status')}
                  className={`px-4 py-2 text-sm rounded-md transition-all ${
                    activeTab === 'status'
                      ? 'bg-purple-600 text-white'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  System Status
                </button>
              </div>
            </div>
            {/* Current Week Indicator - always show */}
            {currentWeek && (
              <div className="text-4xl font-bold text-white">
                {currentWeek}
              </div>
            )}
          </div>
        </div>
      </nav>

      {/* Main Content */}
      {activeTab === 'player' && <PlayerModel initialPlayerId={selectedPlayerId} />}
      {activeTab === 'weekly' && <WeeklyValue onPlayerClick={handlePlayerClick} />}
      {activeTab === 'status' && <SystemStatus />}
    </div>
  );
}
