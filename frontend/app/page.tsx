'use client';

import { useState } from 'react';
import { NavBar } from '@/components/shared/NavBar';
import { WeeklyValue } from '@/components/weekly/WeeklyValue';
import { PlayerModel } from '@/components/player-lookup/PlayerModel';
import { TrackRecord } from '@/components/track-record/TrackRecord';
import { useCurrentWeek } from '@/hooks/useCurrentWeek';

type Tab = 'weekly' | 'player' | 'track';

export default function Home() {
  const [activeTab, setActiveTab] = useState<Tab>('weekly');
  const [selectedPlayerId, setSelectedPlayerId] = useState<string | null>(null);
  const { week: currentWeek, season: currentYear } = useCurrentWeek();

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
