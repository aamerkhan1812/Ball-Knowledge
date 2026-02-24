"use client";

import Image from "next/image";
import { useCallback, useEffect, useState } from "react";

type Match = {
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

type MatchesResponse = {
  status: string;
  total_matches_checked: number;
  matches: Match[];
  warnings?: string[];
  source?: string;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const RAW_WINDOW_HOURS = Number(
  process.env.NEXT_PUBLIC_UPCOMING_WINDOW_HOURS ?? "20",
);
const UPCOMING_WINDOW_HOURS =
  Number.isFinite(RAW_WINDOW_HOURS) && RAW_WINDOW_HOURS > 0
    ? Math.min(48, Math.max(1, Math.round(RAW_WINDOW_HOURS)))
    : 20;

function toBadgeText(name: string, maxLength = 3): string {
  const tokens = name.trim().match(/[A-Za-z0-9]+/g) ?? [];
  if (tokens.length === 0) {
    return "?";
  }

  if (tokens.length === 1) {
    const single = tokens[0].slice(0, Math.max(2, Math.min(3, maxLength)));
    return single.toUpperCase() || "?";
  }

  const initials = tokens
    .slice(0, Math.max(2, maxLength))
    .map((token) => token[0]?.toUpperCase() ?? "")
    .join("");

  if (initials.length > 0) {
    return initials;
  }

  const firstToken = tokens[0] ?? "";
  return firstToken.slice(0, 2).toUpperCase() || "?";
}

function formatKickoff(kickoff: string): { dateText: string; timeText: string } {
  const kickoffDate = new Date(kickoff);
  if (Number.isNaN(kickoffDate.getTime())) {
    return { dateText: "Kickoff TBD", timeText: "" };
  }

  return {
    dateText: kickoffDate.toLocaleDateString([], {
      weekday: "short",
      month: "short",
      day: "numeric",
    }),
    timeText: kickoffDate.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    }),
  };
}

function rankLabelForIndex(index: number): string {
  if (index === 0) {
    return "#1 Must-Watch";
  }
  if (index === 1) {
    return "#2 Backup";
  }
  if (index === 2) {
    return "#3 Solid Choice";
  }
  return "Watchlist";
}

function rankToneForIndex(index: number): string {
  if (index === 0) {
    return "rank-gold";
  }
  if (index === 1) {
    return "rank-silver";
  }
  if (index === 2) {
    return "rank-bronze";
  }
  return "rank-plain";
}

function GoalLoader() {
  return (
    <div className="goal-loader" role="status" aria-live="polite">
      <div className="goal-frame">
        <div className="goal-net" />
        <div className="goal-ball" />
      </div>
      <p className="goal-loader-text">Whistling up your matchday feed...</p>
    </div>
  );
}

export default function Home() {
  const [matches, setMatches] = useState<Match[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [searchInput, setSearchInput] = useState("");
  const [favoriteTeam, setFavoriteTeam] = useState("");

  const fetchMatches = useCallback(async () => {
    setLoading(true);
    setError(null);

    const params = new URLSearchParams();
    params.append("user_id", "web_client_001");
    params.append("window_hours", String(UPCOMING_WINDOW_HOURS));
    params.append("favorite_team", favoriteTeam);
    params.append("prefers_goals", "false");
    params.append("prefers_tactical", "false");

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/matches/today?${params.toString()}`,
        {
          method: "GET",
          headers: { Accept: "application/json" },
          cache: "no-store",
        },
      );

      if (!response.ok) {
        let parsedMessage = "";
        try {
          const body = (await response.json()) as {
            detail?: { message?: string; upstream?: unknown } | string;
          };
          if (typeof body.detail === "string") {
            parsedMessage = body.detail;
          } else if (body.detail?.message) {
            parsedMessage = body.detail.message;
          } else if (body.detail?.upstream) {
            parsedMessage = JSON.stringify(body.detail.upstream);
          }
        } catch {
          parsedMessage = await response.text();
        }

        throw new Error(
          parsedMessage || `Request failed with status ${response.status}`,
        );
      }

      const data: MatchesResponse = await response.json();
      const deduped = Array.from(
        new Map((data.matches ?? []).map((match) => [match.id, match])).values(),
      );
      deduped.sort((a, b) => b.score - a.score);

      setMatches(deduped);
    } catch (fetchError) {
      const message =
        fetchError instanceof Error
          ? fetchError.message
          : "Unexpected request failure.";
      setError(message);
      setMatches([]);
    } finally {
      setLoading(false);
    }
  }, [favoriteTeam]);

  useEffect(() => {
    void fetchMatches();
  }, [fetchMatches]);

  const applySearch = useCallback(() => {
    setFavoriteTeam(searchInput.trim());
  }, [searchInput]);

  if (loading) {
    return (
      <div className="stadium-page">
        <div className="stadium-background" aria-hidden="true">
          <span className="bg-orb orb-a" />
          <span className="bg-orb orb-b" />
          <span className="bg-orb orb-c" />
          <span className="pitch-lines" />
          <span className="moving-ball" />
        </div>
        <div className="loading-center">
          <GoalLoader />
        </div>
      </div>
    );
  }

  return (
    <div className="stadium-page">
      <div className="stadium-background" aria-hidden="true">
        <span className="bg-orb orb-a" />
        <span className="bg-orb orb-b" />
        <span className="bg-orb orb-c" />
        <span className="pitch-lines" />
        <span className="moving-ball" />
      </div>

      <main className="stadium-content">
        <header className="hero-panel">
          <p className="hero-kicker">AI MATCHDAY ENGINE</p>
          <h1 className="hero-title font-display">Banger Radar</h1>
          <p className="hero-subtitle">
            AI-scored football matches you should not miss.
          </p>

          <div className="search-panel">
            <label className="search-label" htmlFor="team-search">
              Search your team
            </label>
            <div className="search-row">
              <input
                id="team-search"
                list="team-options"
                placeholder="Search your team (e.g. Alaves, Chelsea)"
                className="search-input"
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    applySearch();
                  }
                }}
              />
              <datalist id="team-options">
                <option value="Arsenal" />
                <option value="Aston Villa" />
                <option value="Chelsea" />
                <option value="Everton" />
                <option value="Liverpool" />
                <option value="Manchester City" />
                <option value="Manchester United" />
                <option value="Newcastle" />
                <option value="Tottenham" />
                <option value="Real Madrid" />
                <option value="Barcelona" />
                <option value="Atletico Madrid" />
                <option value="Bayern Munich" />
                <option value="Borussia Dortmund" />
                <option value="Bayer Leverkusen" />
                <option value="Inter" />
                <option value="AC Milan" />
                <option value="Juventus" />
                <option value="Napoli" />
                <option value="PSG" />
              </datalist>
              <button onClick={applySearch} className="search-button" type="button">
                Search
              </button>
            </div>
          </div>
        </header>

        {error ? (
          <section className="state-panel state-error">
            <p className="state-title">Failed to load matches.</p>
            <p className="state-text">{error}</p>
          </section>
        ) : null}

        {!error && matches.length === 0 ? (
          <section className="state-panel state-empty">
            <p className="state-title">No upcoming fixtures in your window.</p>
            <p className="state-text">
              Try searching another team or check again closer to kickoff.
            </p>
          </section>
        ) : null}

        {matches.length > 0 ? (
          <section className="cards-grid">
            {matches.map((match, index) => {
              const kickoff = formatKickoff(match.kickoff);
              const rankLabel = rankLabelForIndex(index);
              const rankTone = rankToneForIndex(index);

              return (
                <article
                  key={match.id}
                  className={`match-card ${index === 0 ? "match-card--prime" : ""}`}
                >
                  <div className="match-top">
                    <div className="league-wrap">
                      {match.league_logo ? (
                        <Image
                          src={match.league_logo}
                          alt={match.league}
                          width={32}
                          height={32}
                          className="league-logo"
                          unoptimized
                        />
                      ) : (
                        <span className="league-fallback">
                          {toBadgeText(match.league, 3)}
                        </span>
                      )}
                      <div className="league-meta">
                        <span className="league-name">{match.league}</span>
                        <span className="kickoff-text">
                          {kickoff.dateText}
                          {kickoff.timeText ? ` - ${kickoff.timeText}` : ""}
                        </span>
                      </div>
                    </div>
                    <span className={`rank-chip ${rankTone}`}>{rankLabel}</span>
                  </div>

                  <div className="match-teams">
                    <div className="team-block">
                      {match.home_logo ? (
                        <Image
                          src={match.home_logo}
                          alt={match.home_team}
                          width={84}
                          height={84}
                          className="team-logo"
                          unoptimized
                        />
                      ) : (
                        <span className="team-fallback">
                          {toBadgeText(match.home_team, 3)}
                        </span>
                      )}
                      <span className="team-name">{match.home_team}</span>
                    </div>

                    <div className="versus-block">
                      <span className="versus-text">VS</span>
                      <span className="hype-label">Hype Level</span>
                      <span className="hype-value">{match.probability}</span>
                    </div>

                    <div className="team-block">
                      {match.away_logo ? (
                        <Image
                          src={match.away_logo}
                          alt={match.away_team}
                          width={84}
                          height={84}
                          className="team-logo"
                          unoptimized
                        />
                      ) : (
                        <span className="team-fallback">
                          {toBadgeText(match.away_team, 3)}
                        </span>
                      )}
                      <span className="team-name">{match.away_team}</span>
                    </div>
                  </div>

                  <div className="reason-wrap">
                    <span className="reason-label">AI Reasoning</span>
                    <p className="reason-text">{match.reason}</p>
                  </div>
                </article>
              );
            })}
          </section>
        ) : null}
      </main>
    </div>
  );
}
