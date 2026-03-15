// Backend API response types — shapes returned by the FastAPI server

export interface TeaserCounts {
  high_conviction: number;
  value_play: number;
  fade: number;
}

export type PredictionTier =
  | 'high_conviction'
  | 'value_play'
  | 'on_the_radar'
  | 'fade_volume_trap'
  | 'fade_overpriced'
  | null;

export interface WeekStatusResponse {
  season: number;
  week: number;
  is_early_season: boolean;
}

export interface PlayerResponse {
  player_id: string;
  full_name: string;
  team: string | null;
  position: string;
  headshot_url: string | null;
}

export interface PredictionResponse {
  player_id: string;
  full_name: string;
  position: string | null;
  team: string | null;
  headshot_url: string | null;
  final_prob: number | null;
  model_odds: number | null;
  sportsbook_odds: number | null;
  implied_prob: number | null;
  favor: number | null;
  is_low_confidence: boolean;
  model_version: string;
  tier: PredictionTier;
  completeness_score: number | null;
}

export interface PredictionsApiResponse {
  season: number;
  week: number;
  count: number;
  predictions: PredictionResponse[];
  teaser: TeaserCounts;
}

export interface GameLogEntry {
  week: number;
  opponent: string | null;
  targets: number | null;
  rec_yards: number | null;
  rec_tds: number | null;
}

export interface GameLogsResponse {
  player_id: string;
  season: number;
  game_logs: GameLogEntry[];
}

export interface PredictionHistoryEntry {
  week: number;
  final_prob: number | null;
  model_odds: number | null;
  season: number;
}

export interface SeasonStatsResponse {
  player_id: string;
  season: number;
  games_played: number;
  tds_this_season: number;
  targets: number;
  td_rate: number;   // 0.0–1.0
}
