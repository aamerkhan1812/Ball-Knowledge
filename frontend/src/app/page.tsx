"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ActiveBackground } from "@/components/battlefield/ActiveBackground";
import { LoadingSequence } from "@/components/battlefield/LoadingSequence";
import { MatchCard } from "@/components/battlefield/MatchCard";
import { MatchModal } from "@/components/battlefield/MatchModal";
import { MobileBottomNav } from "@/components/battlefield/MobileBottomNav";
import { ModeToggles } from "@/components/battlefield/ModeToggles";
import { NextKickoffClock } from "@/components/battlefield/NextKickoffClock";
import { SearchPanel } from "@/components/battlefield/SearchPanel";
import type { Match, MatchesResponse, UiMode } from "@/components/battlefield/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const RAW_WINDOW_HOURS = Number(
  process.env.NEXT_PUBLIC_UPCOMING_WINDOW_HOURS ?? "20",
);
const UPCOMING_WINDOW_HOURS =
  Number.isFinite(RAW_WINDOW_HOURS) && RAW_WINDOW_HOURS > 0
    ? Math.min(48, Math.max(1, Math.round(RAW_WINDOW_HOURS)))
    : 20;

function modeClass(mode: UiMode): string {
  return mode === "chaos" ? "battle-mode-chaos" : "battle-mode-tactical";
}

export default function Home() {
  const [matches, setMatches] = useState<Match[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [searchInput, setSearchInput] = useState("");
  const [favoriteTeam, setFavoriteTeam] = useState("");
  const [mode, setMode] = useState<UiMode>("chaos");
  const [selectedMatch, setSelectedMatch] = useState<Match | null>(null);

  const fetchMatches = useCallback(async () => {
    setLoading(true);
    setError(null);

    const params = new URLSearchParams();
    params.append("user_id", "web_client_001");
    params.append("window_hours", String(UPCOMING_WINDOW_HOURS));
    params.append("favorite_team", favoriteTeam);
    params.append("prefers_goals", String(mode === "chaos"));
    params.append("prefers_tactical", String(mode === "tactical"));

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
  }, [favoriteTeam, mode]);

  useEffect(() => {
    void fetchMatches();
  }, [fetchMatches]);

  const applySearch = useCallback(() => {
    setFavoriteTeam(searchInput.trim());
  }, [searchInput]);

  const rootModeClass = useMemo(() => modeClass(mode), [mode]);

  if (loading) {
    return (
      <div className={`battlefield-shell ${rootModeClass}`}>
        <ActiveBackground mode={mode} />
        <LoadingSequence mode={mode} />
      </div>
    );
  }

  return (
    <div className={`battlefield-shell ${rootModeClass}`}>
      <ActiveBackground mode={mode} />

      <main id="battlefield-top" className="relative mx-auto max-w-[1320px] px-4 pb-32 pt-5 md:px-8 md:pb-12 md:pt-7">
        <motion.header
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, ease: "easeOut" }}
          className="relative overflow-hidden rounded-[1.75rem] border border-white/14 bg-white/[0.07] p-4 shadow-[0_24px_70px_rgba(0,0,0,0.42)] backdrop-blur-xl md:p-7"
        >
          <div className="pointer-events-none absolute -right-16 -top-20 h-48 w-48 rounded-full bg-[radial-gradient(circle_at_center,rgba(74,214,255,0.4),transparent_70%)] blur-2xl" />
          <div className="pointer-events-none absolute -bottom-24 left-0 h-56 w-56 rounded-full bg-[radial-gradient(circle_at_center,rgba(63,255,140,0.34),transparent_72%)] blur-2xl" />

          <h1 className="font-display mt-2 text-[2.05rem] uppercase leading-[0.84] tracking-[0.08em] text-white drop-shadow-[0_0_18px_rgba(66,213,255,0.45)] md:text-[4.4rem]">
            Tonight&apos;s Football Battlefield
          </h1>
          <p className="mt-4 max-w-[63ch] text-sm text-white/72 md:text-base">
            Enter the tunnel. Floodlights are live. The AI engine is mapping pressure swings, knockout stakes and momentum fractures across the next battles.
          </p>

          <div className="mt-5 grid gap-3 md:grid-cols-[minmax(220px,auto)_1fr]">
            <NextKickoffClock matches={matches} />
            <ModeToggles mode={mode} setMode={setMode} />
          </div>

          <div className="mt-5">
            <SearchPanel
              searchInput={searchInput}
              setSearchInput={setSearchInput}
              onApply={applySearch}
            />
          </div>
        </motion.header>

        <AnimatePresence mode="wait">
          {error ? (
            <motion.section
              key="error"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 12 }}
              className="mt-5 rounded-2xl border border-red-400/35 bg-red-900/25 p-4 text-red-100 backdrop-blur-md"
            >
              <p className="text-base font-semibold">Match feed unavailable.</p>
              <p className="mt-1 text-sm text-red-100/85">{error}</p>
            </motion.section>
          ) : null}
        </AnimatePresence>

        {!error && matches.length === 0 ? (
          <section className="mt-5 rounded-2xl border border-white/12 bg-slate-900/40 p-5 text-white/85 backdrop-blur-md">
            <p className="text-base font-semibold">No upcoming fixtures detected.</p>
            <p className="mt-1 text-sm text-white/70">
              Adjust the search team filter or refresh when kickoff windows are closer.
            </p>
          </section>
        ) : null}

        {matches.length > 0 ? (
          <section id="matches-feed" className="mt-6">
            <div className="mobile-swipe no-scrollbar flex snap-x snap-mandatory gap-4 overflow-x-auto pb-3 md:hidden">
              {matches.map((match, index) => (
                <div key={`mobile-${match.id}`} className="min-w-[88vw] snap-center">
                  <MatchCard
                    match={match}
                    index={index}
                    mode={mode}
                    onOpen={setSelectedMatch}
                  />
                </div>
              ))}
            </div>

            <div className="hidden gap-5 md:grid md:grid-cols-2">
              {matches.map((match, index) => (
                <div
                  key={`desktop-${match.id}`}
                  className={index === 0 ? "md:col-span-2" : undefined}
                >
                  <MatchCard
                    match={match}
                    index={index}
                    mode={mode}
                    onOpen={setSelectedMatch}
                  />
                </div>
              ))}
            </div>
          </section>
        ) : null}
      </main>

      <MatchModal match={selectedMatch} mode={mode} onClose={() => setSelectedMatch(null)} />
      <MobileBottomNav />
    </div>
  );
}
