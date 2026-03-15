'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { useAuthModal } from '@/contexts/AuthModalContext';
import { PlayerSelector } from './PlayerSelector';
import { PlayerHeader } from './PlayerHeader';
import { PredictionSummary } from './PredictionSummary';
import { HistoricalResultCard } from './HistoricalResultCard';
import { ProbabilityChart } from './ProbabilityChart';
import { GameLogTable } from './GameLogTable';
import { GamblingDisclaimer } from '@/components/shared/GamblingDisclaimer';
import { PaywallGate } from '@/components/shared/PaywallGate';
import { PlayerWeekToggle } from '@/components/weekly/PlayerWeekToggle';
import type { PlayerResponse, GameLogsResponse, GameLogEntry, PredictionHistoryEntry, SeasonStatsResponse } from '@/types/backend';
import type { Player, PlayerPrediction, GameLogRow, WeeklyChartPoint } from '@/types/ui';

interface PlayerModelProps {
  initialPlayerId?: string | null;
  currentWeek?: number | null;
  currentYear?: number | null;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? '';

export function PlayerModel({ initialPlayerId, currentWeek, currentYear }: PlayerModelProps) {
  const { isSubscriber, user, getToken } = useAuth();
  const { openLogin } = useAuthModal();
  const [players, setPlayers] = useState<Player[]>([]);
  const [selectedPlayerId, setSelectedPlayerId] = useState('');
  interface PlayerData {
    gameLogs?: GameLogRow[];
    weeklyData?: WeeklyChartPoint[];
    prediction?: PlayerPrediction | null;
  }
  const [selectedPlayerData, setSelectedPlayerData] = useState<PlayerData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedWeek, setSelectedWeek] = useState(currentWeek ?? 18);

  const effectiveWeek = currentWeek ?? 18;
  const effectiveYear = currentYear ?? 2025;

  // Sync selectedWeek when prop arrives
  useEffect(() => {
    if (currentWeek !== null && currentWeek !== undefined) {
      setSelectedWeek(currentWeek);
    }
  }, [currentWeek]);

  // Effect A: load player roster once on mount (no week dependency)
  useEffect(() => {
    async function loadPlayers() {
      try {
        const resp = await fetch(`${API_URL}/api/players`);
        if (!resp.ok) return;
        const playersData: PlayerResponse[] = await resp.json();

        const playerList: Player[] = playersData.map((p: PlayerResponse) => ({
          id: p.player_id,
          name: p.full_name,
          team: p.team ?? 'N/A',
          position: p.position,
          jersey: 0,
          imageUrl: p.headshot_url ?? '',
          tdsThisSeason: 0,
          gamesPlayed: 0,
          targets: 0,
          tdRate: '0%',
        }));

        setPlayers(playerList);
        if (initialPlayerId && playerList.find((p: Player) => p.id === initialPlayerId)) {
          setSelectedPlayerId(initialPlayerId);
        } else if (playerList.length > 0) {
          setSelectedPlayerId(playerList[0].id);
        }
        setLoading(false);
      } catch {
        setLoading(false);
      }
    }
    loadPlayers();
  }, [initialPlayerId]);

  // Effect B: season stats — public, always runs for any selected player
  useEffect(() => {
    async function loadSeasonStats() {
      if (!selectedPlayerId) return;
      try {
        const resp = await fetch(
          `${API_URL}/api/players/${selectedPlayerId}/season-stats?season=${effectiveYear}`
        );
        if (!resp.ok) return;
        const stats: SeasonStatsResponse = await resp.json();
        setPlayers((prev) =>
          prev.map((p) =>
            p.id === selectedPlayerId
              ? {
                  ...p,
                  tdsThisSeason: stats.tds_this_season,
                  gamesPlayed: stats.games_played,
                  targets: stats.targets,
                  tdRate: stats.games_played > 0
                    ? `${Math.round(stats.td_rate * 100)}%`
                    : '0%',
                }
              : p
          )
        );
      } catch {
        // silently handle — header stats stay at 0 if fetch fails
      }
    }
    loadSeasonStats();
  }, [selectedPlayerId, effectiveYear]);

  // Effect C: game logs + prediction history — subscriber only
  useEffect(() => {
    async function loadSubscriberData() {
      if (!selectedPlayerId || !isSubscriber) {
        setSelectedPlayerData((prev) => ({ ...prev, gameLogs: [], weeklyData: [] }));
        return;
      }
      try {
        const token = getToken();
        const authHeader: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
        const [logsResp, historyResp] = await Promise.all([
          fetch(`${API_URL}/api/players/${selectedPlayerId}/game-logs?season=${effectiveYear}&limit=30`, { headers: authHeader }),
          fetch(`${API_URL}/api/players/${selectedPlayerId}/history?season=${effectiveYear}`, { headers: authHeader }),
        ]);

        const logsData: GameLogsResponse = await logsResp.json();
        const historyData: PredictionHistoryEntry[] = await historyResp.json();
        const logs: GameLogEntry[] = logsData.game_logs ?? [];

        const predictionsByWeek = new Map<number, number>(
          historyData
            .filter((h) => h.final_prob !== null)
            .map((h) => [h.week, (h.final_prob as number) * 100] as [number, number])
        );

        const gameLogs = logs.map((log) => ({
          week: log.week,
          opponent: log.opponent ?? 'OPP',
          targets: log.targets ?? 0,
          yards: log.rec_yards ?? 0,
          td: log.rec_tds ?? 0,
          modelProbability: Math.round(predictionsByWeek.get(log.week) ?? 0),
        }));

        const weeklyData = logs.map((log) => ({
          week: log.week,
          probability: predictionsByWeek.get(log.week) ?? 0,
          scored: (log.rec_tds ?? 0) > 0,
        }));

        setSelectedPlayerData((prev) => ({ ...prev, gameLogs, weeklyData }));
      } catch {
        // silently handle
      }
    }
    loadSubscriberData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedPlayerId, effectiveYear, isSubscriber, user]);

  // Effect D: load this week's prediction when player OR week changes (null-safe)
  useEffect(() => {
    async function loadWeekPrediction() {
      if (!selectedPlayerId) return;
      try {
        const token = getToken();
        const authHeader: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
        const resp = await fetch(
          `${API_URL}/api/predictions/${effectiveYear}/${selectedWeek}?player_id=${selectedPlayerId}`,
          { headers: authHeader }
        );
        if (!resp.ok) {
          setSelectedPlayerData((prev) => ({ ...prev, prediction: null }));
          return;
        }
        const predData = await resp.json();
        const predRow = predData.predictions?.[0] ?? null;

        if (!predRow) {
          setSelectedPlayerData((prev) => ({ ...prev, prediction: null }));
          return;
        }

        const modelProb = predRow.final_prob !== null ? predRow.final_prob * 100 : null;
        const modelOdds = predRow.model_odds;
        const modelOddsStr = modelOdds !== null
          ? (modelOdds > 0 ? `+${modelOdds}` : `${modelOdds}`)
          : null;
        const sbOdds = predRow.sportsbook_odds;
        const sbOddsStr = sbOdds !== null ? (sbOdds > 0 ? `+${sbOdds}` : `${sbOdds}`) : 'N/A';

        let edge: 'positive' | 'neutral' | 'negative' = 'neutral';
        let edgeValue: number | null = null;
        if (predRow.favor !== null) {
          edgeValue = predRow.favor * 100;
          edge = edgeValue > 0 ? 'positive' : edgeValue < 0 ? 'negative' : 'neutral';
        }

        setSelectedPlayerData((prev) => ({
          ...prev,
          prediction: {
            playerId: selectedPlayerId,
            modelProbability: modelProb !== null ? Math.round(modelProb) : null,
            modelImpliedOdds: modelOddsStr,
            sportsbookOdds: sbOddsStr,
            edge,
            edgeValue,
            week: predRow.week,
            year: predRow.season,
            tier: predRow.tier ?? null,
          },
        }));
      } catch {
        setSelectedPlayerData((prev) => ({ ...prev, prediction: null }));
      }
    }
    loadWeekPrediction();
    // Re-fetch when auth state changes so pro users get full data on login/logout
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedPlayerId, selectedWeek, effectiveYear, user]);

  const isHistorical = selectedWeek < (currentWeek ?? 18);

  const selectedPlayer = players.find((p) => p.id === selectedPlayerId);

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-center text-white text-xl">Loading players...</div>
      </div>
    );
  }

  if (!selectedPlayer) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-center text-white text-xl">No players available</div>
      </div>
    );
  }

  return (
    <div className="relative">
      {/* Hero Background */}
      <div className="absolute top-0 left-0 w-full h-96 bg-gradient-to-b from-purple-900/20 via-[#0a0a0a]/80 to-[#0a0a0a]" />

      {/* Content */}
      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Player Selector and Week Toggle */}
        <div className="mb-8 flex items-center justify-between gap-4 max-md:flex-col max-md:items-stretch">
          <div className="flex-1">
            <PlayerSelector
              players={players}
              selectedPlayerId={selectedPlayerId}
              onSelectPlayer={setSelectedPlayerId}
            />
          </div>
          <PlayerWeekToggle
            currentWeek={effectiveWeek}
            currentYear={effectiveYear}
            selectedWeek={selectedWeek}
            onWeekChange={setSelectedWeek}
            lockedToCurrentWeek={!isSubscriber}
          />
        </div>

        {/* Player Header Card */}
        <div className="mb-8">
          <PlayerHeader player={selectedPlayer} />
        </div>

        {/* Prediction Summary / Historical Result */}
        {selectedPlayerData?.prediction && (
          <div className="mb-8">
            {isHistorical && (
              <div className="mb-3 flex items-center gap-2">
                <span className="text-xs px-3 py-1 rounded-badge bg-sr-primary/15 text-sr-primary/80">
                  Week {selectedWeek} — Historical
                </span>
              </div>
            )}
            {isHistorical ? (
              <HistoricalResultCard
                week={selectedPlayerData.prediction.week ?? selectedWeek}
                year={selectedPlayerData.prediction.year ?? effectiveYear}
                tier={selectedPlayerData.prediction.tier ?? null}
                modelProbability={selectedPlayerData.prediction.modelProbability}
                td={(() => {
                  const log = selectedPlayerData.gameLogs?.find((l) => l.week === selectedWeek);
                  return log ? log.td > 0 : false;
                })()}
                edge={selectedPlayerData.prediction.edge}
                edgeValue={selectedPlayerData.prediction.edgeValue}
              />
            ) : (
              <PredictionSummary prediction={selectedPlayerData.prediction} />
            )}
          </div>
        )}

        {/* Probability Chart — paid feature */}
        {selectedPlayerData?.weeklyData && (
          <div className="mb-8">
            <PaywallGate
              ctaTitle="Season probability trend"
              ctaBody="See how the model has rated this player week-by-week all season."
              onGetAccess={openLogin}
            >
              <ProbabilityChart data={selectedPlayerData.weeklyData} />
            </PaywallGate>
          </div>
        )}

        {/* Game Log */}
        {isSubscriber && selectedPlayerData?.gameLogs && selectedPlayerData.gameLogs.length > 0 && (
          <div className="mb-8">
            <GameLogTable
              data={selectedPlayerData.gameLogs}
              currentWeek={effectiveWeek}
            />
          </div>
        )}

        {/* Gambling Disclaimer */}
        <GamblingDisclaimer />
      </div>
    </div>
  );
}
