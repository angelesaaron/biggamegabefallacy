'use client';

import { useState, useEffect } from 'react';
import { NavBar } from '@/components/shared/NavBar';
import { WeeklyValue } from '@/components/weekly/WeeklyValue';
import { PlayerModel } from '@/components/player-lookup/PlayerModel';
import { TrackRecord } from '@/components/track-record/TrackRecord';

type Tab = 'weekly' | 'player' | 'track';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? '';

export default function Home() {
  const [activeTab, setActiveTab] = useState<Tab>('weekly');
  const [currentWeek, setCurrentWeek] = useState<number | null>(null);
  const [currentYear, setCurrentYear] = useState<number | null>(null);
  const [selectedPlayerId, setSelectedPlayerId] = useState<string | null>(null);

  useEffect(() => {
    const fetchWeek = async () => {
      try {
        const response = await fetch(`${API_URL}/api/status/week`);
        if (!response.ok) return;
        const data = await response.json();
        setCurrentWeek(data.week ?? null);
        setCurrentYear(data.season ?? null);
      } catch {
        // silent — week badge just won't render
      }
    };
    fetchWeek();
  }, []);

  const handlePlayerClick = (playerId: string) => {
    setSelectedPlayerId(playerId);
    setActiveTab('player');
  };

  return (
    <div className="min-h-screen bg-sr-bg">
      <NavBar activeTab={activeTab} onTabChange={setActiveTab} currentWeek={currentWeek} />
      <main>
        {activeTab === 'weekly' && (
          <WeeklyValue
            currentWeek={currentWeek}
            currentYear={currentYear}
            onPlayerClick={handlePlayerClick}
          />
        )}
        {activeTab === 'player' && (
          <PlayerModel
            initialPlayerId={selectedPlayerId}
            currentWeek={currentWeek}
            currentYear={currentYear}
          />
        )}
        {activeTab === 'track' && (
          <TrackRecord />
        )}
      </main>
    </div>
  );
}
