'use client';

import { useState, useEffect } from 'react';
import { PlayerSelector } from './PlayerSelector';
import { PlayerHeader } from './PlayerHeader';
import { PredictionSummary } from './PredictionSummary';
import { ProbabilityChart } from './ProbabilityChart';
import { GameLogTable } from './GameLogTable';
import { GamblingDisclaimer } from '@/components/shared/GamblingDisclaimer';
import { PaywallGate } from '@/components/shared/PaywallGate';
import { PlayerWeekToggle } from '@/components/weekly/PlayerWeekToggle';
import type { PlayerResponse, GameLogsResponse, GameLogEntry, PredictionHistoryEntry } from '@/types/backend';
import type { Player, PlayerPrediction, GameLogRow, WeeklyChartPoint } from '@/types/ui';

interface PlayerModelProps {
  initialPlayerId?: string | null;
  currentWeek?: number | null;
  currentYear?: number | null;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? '';

export function PlayerModel({ initialPlayerId, currentWeek, currentYear }: PlayerModelProps) {
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

  // Effect B: load season-level data when player changes (game logs + full history)
  // These are season-wide — not week-specific. Always render regardless of prediction.
  useEffect(() => {
    async function loadSeasonData() {
      if (!selectedPlayerId) return;
      try {
        const [logsResp, historyResp] = await Promise.all([
          fetch(`${API_URL}/api/players/${selectedPlayerId}/game-logs?season=${effectiveYear}&limit=30`),
          fetch(`${API_URL}/api/players/${selectedPlayerId}/history?season=${effectiveYear}`),
        ]);

        const logsData: GameLogsResponse = await logsResp.json();
        const historyData: PredictionHistoryEntry[] = await historyResp.json();

        // Backend returns GameLogsResponse: { player_id, season, game_logs: [] }
        const logs: GameLogEntry[] = logsData.game_logs ?? [];

        // Prediction history: flat array of { week, final_prob, model_odds, ... }
        const predictionsByWeek = new Map<number, number>(
          historyData.map((h) => [h.week, h.final_prob * 100] as [number, number])
        );

        // Season totals from game logs
        const tdsThisSeason = logs.reduce((s, l) => s + (l.rec_tds ?? 0), 0);
        const totalTargets = logs.reduce((s, l) => s + (l.targets ?? 0), 0);
        const gamesWithTD = logs.filter((l) => (l.rec_tds ?? 0) > 0).length;
        const tdRate = logs.length > 0
          ? `${Math.round((gamesWithTD / logs.length) * 100)}%`
          : '0%';

        setPlayers((prev) =>
          prev.map((p) =>
            p.id === selectedPlayerId
              ? { ...p, tdsThisSeason, gamesPlayed: logs.length, targets: totalTargets, tdRate }
              : p
          )
        );

        // Game log table rows (model probability overlaid from history)
        const gameLogs = logs.map((log) => ({
          week: log.week,
          opponent: log.opponent ?? 'OPP',
          targets: log.targets ?? 0,
          yards: log.rec_yards ?? 0,
          td: log.rec_tds ?? 0,
          modelProbability: Math.round(predictionsByWeek.get(log.week) ?? 0),
        }));

        // Probability chart data (week × predicted prob × actual outcome)
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
    loadSeasonData();
  }, [selectedPlayerId, effectiveYear]);

  // Effect C: load this week's prediction when player OR week changes (null-safe)
  useEffect(() => {
    async function loadWeekPrediction() {
      if (!selectedPlayerId) return;
      try {
        const resp = await fetch(
          `${API_URL}/api/predictions/${effectiveYear}/${selectedWeek}?player_id=${selectedPlayerId}`
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

        const modelProb = predRow.final_prob * 100;
        const modelOdds = predRow.model_odds;
        const modelOddsStr = modelOdds > 0 ? `+${modelOdds}` : `${modelOdds}`;
        const sbOdds = predRow.sportsbook_odds;
        const sbOddsStr = sbOdds !== null ? (sbOdds > 0 ? `+${sbOdds}` : `${sbOdds}`) : 'N/A';

        let edge: 'positive' | 'neutral' | 'negative' = 'neutral';
        let edgeValue = 0;
        if (predRow.favor !== null) {
          edgeValue = predRow.favor * 100;
          edge = edgeValue > 0 ? 'positive' : edgeValue < 0 ? 'negative' : 'neutral';
        }

        setSelectedPlayerData((prev) => ({
          ...prev,
          prediction: {
            playerId: selectedPlayerId,
            modelProbability: Math.round(modelProb),
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
        setSelectedPlayerData((prev: any) => ({ ...prev, prediction: null }));
      }
    }
    loadWeekPrediction();
  }, [selectedPlayerId, selectedWeek, effectiveYear]);

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
          />
        </div>

        {/* Player Header Card */}
        <div className="mb-8">
          <PlayerHeader player={selectedPlayer} />
        </div>

        {/* Prediction Summary */}
        {selectedPlayerData?.prediction && (
          <div className="mb-8">
            <PredictionSummary prediction={selectedPlayerData.prediction} />
          </div>
        )}

        {/* Probability Chart — paid feature */}
        {selectedPlayerData?.weeklyData && (
          <div className="mb-8">
            <PaywallGate
              feature="season-trend"
              ctaTitle="Season probability trend"
              ctaBody="See how the model has rated this player week-by-week all season."
            >
              <ProbabilityChart data={selectedPlayerData.weeklyData} />
            </PaywallGate>
          </div>
        )}

        {/* Game Log */}
        {selectedPlayerData?.gameLogs && (
          <div className="mb-8">
            <GameLogTable data={selectedPlayerData.gameLogs} />
          </div>
        )}

        {/* Gambling Disclaimer */}
        <GamblingDisclaimer />
      </div>
    </div>
  );
}
