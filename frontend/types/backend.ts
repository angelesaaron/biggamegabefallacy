// Backend data types
export interface Player {
  player_id: string;
  full_name: string;
  team_name: string;
  position: string;
  headshot_url: string;
}

export interface Prediction {
  player_id: string;
  season_year: number;
  week: number;
  td_likelihood: number;
  model_odds: number;
  favor: number;
  created_at: string;
}

export interface GameLog {
  id: number;
  player_id: string;
  game_id: string;
  season_year: number;
  week: number;
  team: string;
  receptions: number;
  receiving_yards: number;
  receiving_touchdowns: number;
  targets: number;
  long_reception: number | null;
  yards_per_reception: number | null;
}

export interface OddsComparison {
  sportsbook_odds: {
    draftkings?: number;
    fanduel?: number;
  };
}
