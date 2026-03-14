// UI-layer types — shapes used by React components (enriched/transformed from backend data)

export interface Player {
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

export interface PlayerPrediction {
  playerId: string;
  modelProbability: number;
  modelImpliedOdds: string;
  sportsbookOdds: string;
  edge: 'positive' | 'neutral' | 'negative';
  edgeValue: number;
  week?: number;
  year?: number;
  tier?: string | null;
}

export interface GameLogRow {
  week: number;
  opponent: string;
  targets: number;
  yards: number;
  td: number;
  modelProbability: number;
}

export interface WeeklyChartPoint {
  week: number;
  probability: number;
  scored: boolean;
}
