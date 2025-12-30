'use client';

import { useState, useEffect } from 'react';
import { PlayerSelector } from './PlayerSelector';
import { PlayerHeader } from './PlayerHeader';
import { PredictionSummary } from './PredictionSummary';
import { ProbabilityChart } from './ProbabilityChart';
import { GameLogTable } from './GameLogTable';
import { GamblingDisclaimer } from './GamblingDisclaimer';

// Player type matching Figma components
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

interface PlayerModelProps {
  initialPlayerId?: string | null;
}

export function PlayerModel({ initialPlayerId }: PlayerModelProps) {
  const [players, setPlayers] = useState<Player[]>([]);
  const [selectedPlayerId, setSelectedPlayerId] = useState('');
  const [selectedPlayerData, setSelectedPlayerData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  // Load all players on mount
  useEffect(() => {
    async function loadPlayers() {
      try {
        const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        const response = await fetch(`${API_URL}/api/predictions/current`);
        const predictions = await response.json();

        // Transform to Player format
        const uniquePlayers = predictions.reduce((acc: Player[], pred: any) => {
          if (!acc.find(p => p.id === pred.player_id)) {
            acc.push({
              id: pred.player_id,
              name: pred.player_name,
              team: pred.team_name || 'N/A',
              position: pred.position || 'WR',
              jersey: parseInt(pred.jersey_number) || 0,
              imageUrl: pred.headshot_url || '',
              tdsThisSeason: 0,
              gamesPlayed: 0,
              targets: 0,
              tdRate: '0%',
            });
          }
          return acc;
        }, []);

        setPlayers(uniquePlayers);
        // Set initial player: use initialPlayerId if provided, otherwise first player
        if (initialPlayerId && uniquePlayers.find((p: Player) => p.id === initialPlayerId)) {
          setSelectedPlayerId(initialPlayerId);
        } else if (uniquePlayers.length > 0) {
          setSelectedPlayerId(uniquePlayers[0].id);
        }
        setLoading(false);
      } catch (err) {
        console.error('Failed to load players:', err);
        setLoading(false);
      }
    }

    loadPlayers();
  }, [initialPlayerId]);

  // Load selected player data when selection changes
  useEffect(() => {
    async function loadPlayerData() {
      if (!selectedPlayerId) return;

      try {
        const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

        // Fetch prediction, odds, game logs, and historical predictions in parallel
        const [predResp, oddsResp, logsResp, historyResp] = await Promise.all([
          fetch(`${API_URL}/api/predictions/${selectedPlayerId}`),
          fetch(`${API_URL}/api/predictions/${selectedPlayerId}`).then(r => r.json()).then(pred =>
            fetch(`${API_URL}/api/odds/comparison/${selectedPlayerId}?week=${pred.week}&year=${pred.season_year}`)
          ),
          fetch(`${API_URL}/api/game-logs/${selectedPlayerId}?season=2025&limit=20`),
          fetch(`${API_URL}/api/predictions/history/${selectedPlayerId}?season=2025&weeks=20`)
        ]);

        const predData = await predResp.json();
        const oddsData = await oddsResp.json();
        const logsData = await logsResp.json();
        const historyData = await historyResp.json();

        // Create a map of week -> prediction probability for quick lookup
        const predictionsByWeek = new Map<number, number>(
          historyData.map((pred: any) => [pred.week, pred.td_likelihood * 100] as [number, number])
        );

        // Transform prediction data to match Figma format
        const modelProb = parseFloat(predData.td_likelihood) * 100;
        const modelOdds = parseFloat(predData.model_odds);
        const modelOddsStr = modelOdds > 0 ? `+${Math.round(modelOdds)}` : `${Math.round(modelOdds)}`;

        const sbOdds = oddsData?.sportsbook_odds?.draftkings;
        const sbOddsStr = sbOdds ? (sbOdds > 0 ? `+${sbOdds}` : `${sbOdds}`) : 'N/A';

        let edge: 'positive' | 'neutral' | 'negative' = 'neutral';
        let edgeValue = 0;
        if (sbOdds) {
          const sbImpliedProb = sbOdds > 0 ? 100 / (sbOdds + 100) : Math.abs(sbOdds) / (Math.abs(sbOdds) + 100);
          const modelProbDecimal = parseFloat(predData.td_likelihood);
          edgeValue = ((modelProbDecimal - sbImpliedProb) * 100);
          edge = edgeValue > 0 ? 'positive' : edgeValue < 0 ? 'negative' : 'neutral';
        }

        const prediction = {
          playerId: selectedPlayerId,
          modelProbability: Math.round(modelProb),
          modelImpliedOdds: modelOddsStr,
          sportsbookOdds: sbOddsStr,
          edge,
          edgeValue,
        };

        // Transform game logs and calculate player stats
        const gameLogs = logsData.map((log: any) => {
          const modelProb = predictionsByWeek.get(log.week) ?? 0;
          return {
            week: log.week,
            opponent: log.opponent || 'OPP',
            targets: log.targets,
            yards: log.receiving_yards,
            td: log.receiving_touchdowns,
            modelProbability: Math.round(modelProb), // Use historical prediction
          };
        });

        // Calculate stats from game logs
        const tdsThisSeason = logsData.reduce((sum: number, log: any) => sum + log.receiving_touchdowns, 0);
        const totalTargets = logsData.reduce((sum: number, log: any) => sum + log.targets, 0);
        const gamesWithTD = logsData.filter((log: any) => log.receiving_touchdowns > 0).length;
        const tdRate = logsData.length > 0 ? `${Math.round((gamesWithTD / logsData.length) * 100)}%` : '0%';

        // Update player with stats
        const updatedPlayer = players.find(p => p.id === selectedPlayerId);
        if (updatedPlayer) {
          updatedPlayer.tdsThisSeason = tdsThisSeason;
          updatedPlayer.gamesPlayed = logsData.length;
          updatedPlayer.targets = totalTargets;
          updatedPlayer.tdRate = tdRate;
        }

        // Weekly predictions chart data using historical predictions
        const weeklyData = gameLogs.map((log: any) => ({
          week: log.week,
          probability: predictionsByWeek.get(log.week) ?? 0, // Use real historical predictions
          scored: log.td > 0,
        }));

        setSelectedPlayerData({ prediction, gameLogs, weeklyData });
      } catch (err) {
        console.error('Failed to load player data:', err);
      }
    }

    loadPlayerData();
  }, [selectedPlayerId, players]);

  const selectedPlayer = players.find(p => p.id === selectedPlayerId);

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
      <div
        className="absolute top-0 left-0 w-full h-96 bg-cover bg-center"
        style={{
          backgroundImage: 'url(/gabe-davis-background.jpg)',
          backgroundPosition: 'center 15%',
        }}
      >
        <div className="absolute inset-0 bg-gradient-to-b from-black/60 via-black/75 to-[#0a0a0a]" />
      </div>

      {/* Content */}
      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Player Selector */}
        <div className="mb-8">
          <PlayerSelector
            players={players}
            selectedPlayerId={selectedPlayerId}
            onSelectPlayer={setSelectedPlayerId}
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

        {/* Probability Chart */}
        {selectedPlayerData?.weeklyData && (
          <div className="mb-8">
            <ProbabilityChart data={selectedPlayerData.weeklyData} />
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
