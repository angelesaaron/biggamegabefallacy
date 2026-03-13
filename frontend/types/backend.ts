// Backend API response types — shapes returned by the FastAPI server

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
  final_prob: number;
  model_odds: number;
  sportsbook_odds: number | null;
  implied_prob: number | null;
  favor: number | null;
  is_low_confidence: boolean;
  model_version: string;
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
  final_prob: number;
  model_odds: number;
  season: number;
}
