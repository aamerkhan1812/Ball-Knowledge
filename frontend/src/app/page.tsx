"use client";

import Image from "next/image";
import { useCallback, useEffect, useMemo, useState } from "react";

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
  window_start?: string | null;
  window_end?: string | null;
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

function formatWindowLabel(
  windowStart?: string | null,
  windowEnd?: string | null,
): string {
  if (!windowStart || !windowEnd) {
    return `Next ${UPCOMING_WINDOW_HOURS} Hours`;
  }

  const start = new Date(windowStart);
  const end = new Date(windowEnd);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
    return `Next ${UPCOMING_WINDOW_HOURS} Hours`;
  }

  const startLabel = start.toLocaleString([], {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
  const endLabel = end.toLocaleString([], {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  return `${startLabel} to ${endLabel}`;
}

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

export default function Home() {
  const [matches, setMatches] = useState<Match[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [windowLabel, setWindowLabel] = useState(
    `Next ${UPCOMING_WINDOW_HOURS} Hours`,
  );

  const [favoriteTeamInput, setFavoriteTeamInput] = useState("");
  const [favoriteTeam, setFavoriteTeam] = useState("");

  const queryKey = useMemo(
    () => `${favoriteTeam}|${UPCOMING_WINDOW_HOURS}`,
    [favoriteTeam],
  );

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
      setWindowLabel(formatWindowLabel(data.window_start, data.window_end));
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
    const timerId = window.setTimeout(() => {
      void fetchMatches();
    }, 0);
    return () => window.clearTimeout(timerId);
  }, [fetchMatches, queryKey]);

  const applyFilters = useCallback(() => {
    setFavoriteTeam(favoriteTeamInput.trim());
  }, [favoriteTeamInput]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 text-white flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-8 font-sans transition-all duration-500">
      <div className="max-w-4xl mx-auto">
        <header className="mb-12 text-center">
          <h1 className="text-5xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-cyan-500 mb-4 tracking-tight">
            Top Matches ({windowLabel})
          </h1>
          <p className="text-gray-400 text-lg mb-8">
            AI-scored football matches you should not miss.
          </p>

          <div className="bg-gray-900/60 p-6 rounded-2xl border border-gray-800 backdrop-blur-md max-w-2xl mx-auto flex flex-col gap-4">
            <h3 className="text-xl font-semibold text-gray-200 text-left">
              Search your team
            </h3>

            <div className="flex gap-4 relative">
              <input
                list="team-options"
                placeholder="Search your team (e.g. Alaves, Chelsea)"
                className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-blue-500 transition-colors"
                value={favoriteTeamInput}
                onChange={(event) => setFavoriteTeamInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    applyFilters();
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
              <button
                onClick={applyFilters}
                className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-3 rounded-lg font-bold transition-all shadow-lg hover:shadow-blue-500/25"
              >
                Search
              </button>
            </div>
          </div>
        </header>

        {error ? (
          <div className="text-center p-10 bg-red-950/30 rounded-2xl border border-red-800">
            <p className="text-red-300 font-semibold">Failed to load matches.</p>
            <p className="text-red-200 text-sm mt-2">{error}</p>
          </div>
        ) : null}

        {!error && matches.length === 0 ? (
          <div className="text-center p-10 bg-gray-900/50 rounded-2xl border border-gray-800 backdrop-blur-md">
            <p className="text-xl text-gray-500">
              No upcoming matches found in the selected time window.
            </p>
          </div>
        ) : null}

        {matches.length > 0 ? (
          <div className="space-y-6">
            {matches.map((match, index) => {
              const kickoffDate = new Date(match.kickoff);
              const kickoff = kickoffDate.toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              });
              const kickoffDay = kickoffDate.toLocaleDateString([], {
                weekday: "short",
                month: "short",
                day: "numeric",
              });

              let badge = null;
              if (index === 0) {
                badge = (
                  <span className="text-2xl ml-2 font-black text-yellow-400">
                    #1 Must-Watch
                  </span>
                );
              } else if (index === 1) {
                badge = (
                  <span className="text-2xl ml-2 font-black text-gray-300">
                    #2 Backup
                  </span>
                );
              } else if (index === 2) {
                badge = (
                  <span className="text-2xl ml-2 font-black text-amber-600">
                    #3 Solid Choice
                  </span>
                );
              }

              return (
                <div
                  key={match.id}
                  className={`relative p-6 rounded-2xl border backdrop-blur-sm transition-all duration-300 hover:scale-[1.02] ${
                    index === 0
                      ? "bg-blue-900/20 border-blue-500/50 shadow-[0_0_30px_rgba(59,130,246,0.15)]"
                      : "bg-gray-900/40 border-gray-800 hover:border-gray-700"
                  }`}
                >
                  <div className="flex justify-between items-start mb-4">
                    <div className="flex items-center gap-3">
                      {match.league_logo ? (
                        <Image
                          src={match.league_logo}
                          alt="League"
                          width={32}
                          height={32}
                          className="rounded-full"
                          unoptimized
                        />
                      ) : (
                        <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-[10px] font-bold text-slate-200">
                          {toBadgeText(match.league, 3)}
                        </div>
                      )}
                      <span className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
                        {match.league}
                      </span>
                      <span className="text-sm px-3 py-1 rounded-full bg-gray-800 text-gray-300 border border-gray-700">
                        {kickoffDay} {kickoff}
                      </span>
                    </div>
                    <div className="flex items-center">{badge}</div>
                  </div>

                  <div className="flex justify-between items-center my-6 px-4">
                    <div className="flex flex-col items-center gap-3 w-1/3">
                      {match.home_logo ? (
                        <Image
                          src={match.home_logo}
                          alt={match.home_team}
                          width={80}
                          height={80}
                          className="object-contain drop-shadow-xl"
                          unoptimized
                        />
                      ) : (
                        <div className="w-20 h-20 bg-gray-800 rounded-full border border-gray-700 flex items-center justify-center text-xl font-black text-gray-200">
                          {toBadgeText(match.home_team, 3)}
                        </div>
                      )}
                      <span className="text-xl font-bold text-center">
                        {match.home_team}
                      </span>
                    </div>

                    <div className="flex flex-col items-center w-1/3">
                      <span className="text-3xl font-black text-gray-700">VS</span>
                      <div className="mt-4 flex flex-col items-center px-2 text-center">
                        <span className="text-xs text-gray-500 uppercase font-bold tracking-widest mb-2">
                          Hype Level
                        </span>
                        <span
                          className={`text-sm font-bold leading-snug ${
                            index === 0 ? "text-blue-400" : "text-gray-300"
                          }`}
                        >
                          {match.probability}
                        </span>
                      </div>
                    </div>

                    <div className="flex flex-col items-center gap-3 w-1/3">
                      {match.away_logo ? (
                        <Image
                          src={match.away_logo}
                          alt={match.away_team}
                          width={80}
                          height={80}
                          className="object-contain drop-shadow-xl"
                          unoptimized
                        />
                      ) : (
                        <div className="w-20 h-20 bg-gray-800 rounded-full border border-gray-700 flex items-center justify-center text-xl font-black text-gray-200">
                          {toBadgeText(match.away_team, 3)}
                        </div>
                      )}
                      <span className="text-xl font-bold text-center">
                        {match.away_team}
                      </span>
                    </div>
                  </div>

                  <div className="mt-4 pt-4 border-t border-gray-800/50 flex flex-col items-start justify-center text-left">
                    <span className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-1">
                      AI Reasoning
                    </span>
                    <p className="text-md text-blue-300 font-semibold bg-blue-900/30 px-3 py-1.5 rounded-md border border-blue-800/50">
                      {match.reason}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        ) : null}
      </div>
    </div>
  );
}
