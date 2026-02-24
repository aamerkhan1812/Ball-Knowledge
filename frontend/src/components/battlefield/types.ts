export type Match = {
  id: number;
  home_team: string;
  home_logo?: string | null;
  away_team: string;
  away_logo?: string | null;
  kickoff: string;
  league: string;
  league_logo?: string | null;
  score: number;
  probability: string;
  reason: string;
};

export type MatchesResponse = {
  status: string;
  total_matches_checked: number;
  matches: Match[];
  warnings?: string[];
  source?: string;
};

export type UiMode = "chaos" | "tactical";
