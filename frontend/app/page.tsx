'use client';

import { Suspense, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { NavBar } from '@/components/shared/NavBar';
import { WeeklyValue } from '@/components/weekly/WeeklyValue';
import { PlayerModel } from '@/components/player-lookup/PlayerModel';
import { TrackRecord } from '@/components/track-record/TrackRecord';
import { useCurrentWeek } from '@/hooks/useCurrentWeek';

type Tab = 'weekly' | 'player' | 'track';

const VALID_TABS: Tab[] = ['weekly', 'player', 'track'];

function HomeContent() {
  const searchParams = useSearchParams();
  const tabParam = searchParams.get('tab') as Tab | null;
  const initialTab: Tab = tabParam && VALID_TABS.includes(tabParam) ? tabParam : 'weekly';

  const [activeTab, setActiveTab] = useState<Tab>(initialTab);
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

export default function Home() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-sr-bg" />}>
      <HomeContent />
    </Suspense>
  );
}
