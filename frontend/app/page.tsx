'use client';

import { useState, useEffect } from 'react';
import WeeklyValue from '@/components/WeeklyValue';
import { PlayerModel } from '@/components/PlayerModel';
import { Calendar } from 'lucide-react';

export default function Home() {
  const [activeTab, setActiveTab] = useState<'player' | 'weekly'>('player');
  const [selectedPlayerId, setSelectedPlayerId] = useState<string | null>(null);
  const [currentWeek, setCurrentWeek] = useState<{year: number; week: number} | null>(null);

  const handlePlayerClick = (playerId: string) => {
    setSelectedPlayerId(playerId);
    setActiveTab('player');
  };

  // Fetch current NFL week on mount
  useEffect(() => {
    async function fetchCurrentWeek() {
      try {
        const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        const response = await fetch(`${API_URL}/api/predictions/current`);
        if (response.ok) {
          const data = await response.json();
          if (data && data.metadata) {
            setCurrentWeek({
              year: data.metadata.current_year,
              week: data.metadata.current_week
            });
          } else if (data && Array.isArray(data)) {
            // Old API format fallback
            if (data.length > 0 && data[0].week) {
              setCurrentWeek({
                year: data[0].season_year,
                week: data[0].week
              });
            }
          }
        }
      } catch (err) {
        // Silently fail - week indicator is optional
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
              </div>
            </div>
            {/* Week Indicator */}
            {currentWeek && (
              <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-900/50 rounded-lg border border-gray-800">
                <Calendar className="w-4 h-4 text-purple-400" />
                <span className="text-sm text-gray-300">
                  Week {currentWeek.week}
                </span>
              </div>
            )}
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
