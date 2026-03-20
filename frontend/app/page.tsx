'use client';

import { useState, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { NavBar } from '@/components/shared/NavBar';
import { WeeklyValue } from '@/components/weekly/WeeklyValue';
import { PlayerModel } from '@/components/player-lookup/PlayerModel';
import { TrackRecord } from '@/components/track-record/TrackRecord';
import AdminPage from '@/app/admin/page';
import { useCurrentWeek } from '@/hooks/useCurrentWeek';

type Tab = 'weekly' | 'player' | 'track' | 'admin';
const VALID_TABS: Tab[] = ['weekly', 'player', 'track', 'admin'];

function HomeContent() {
  const searchParams = useSearchParams();
  const initialTab = (VALID_TABS.find(t => t === searchParams.get('tab')) ?? 'weekly') as Tab;

  const [activeTab, setActiveTab] = useState<Tab>(initialTab);
  const [selectedPlayerId, setSelectedPlayerId] = useState<string | null>(null);
  const { week: currentWeek, season: currentYear, source: weekSource } = useCurrentWeek();

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
            weekSource={weekSource}
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
        {activeTab === 'track' && <TrackRecord />}
        {activeTab === 'admin' && (
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-6">
            <AdminPage />
          </div>
        )}
      </main>
    </div>
  );
}

export default function Home() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-sr-bg flex items-center justify-center">
        <div className="w-8 h-8 rounded-full border-2 border-sr-primary border-t-transparent animate-spin" />
      </div>
    }>
      <HomeContent />
    </Suspense>
  );
}
