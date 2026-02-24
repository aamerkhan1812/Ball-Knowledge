"use client";

import Image from "next/image";
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo } from "react";
import {
  formatKickoff,
  parseProbabilityToPercent,
  splitReasoning,
  toBadgeText,
} from "@/components/battlefield/helpers";
import { ScoreMeter } from "@/components/battlefield/ScoreMeter";
import type { Match, UiMode } from "@/components/battlefield/types";

type MatchModalProps = {
  match: Match | null;
  mode: UiMode;
  onClose: () => void;
};

export function MatchModal({ match, mode, onClose }: MatchModalProps) {
  useEffect(() => {
    if (!match) {
      return;
    }
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [match]);

  const scorePercent = useMemo(() => {
    if (!match) {
      return 0;
    }
    return parseProbabilityToPercent(match.probability, match.score);
  }, [match]);

  const kickoff = useMemo(() => {
    if (!match) {
      return { dateText: "", timeText: "" };
    }
    return formatKickoff(match.kickoff);
  }, [match]);

  const reasons = useMemo(() => {
    if (!match) {
      return [];
    }
    return splitReasoning(match.reason);
  }, [match]);

  return (
    <AnimatePresence>
      {match ? (
        <motion.div
          className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-4 md:p-7"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <button
            type="button"
            aria-label="Close match details"
            className="absolute inset-0 bg-black/75 backdrop-blur-sm"
            onClick={onClose}
          />

          <motion.section
            initial={{ opacity: 0, y: 34, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.97 }}
            transition={{ duration: 0.28, ease: "easeOut" }}
            className="relative z-10 w-[min(980px,100%)] rounded-[1.8rem] border border-white/15 bg-[#0e1526]/95 p-4 shadow-[0_30px_80px_rgba(0,0,0,0.55)] backdrop-blur-xl md:p-7"
          >
            <div className="absolute inset-x-10 top-0 h-[2px] bg-gradient-to-r from-transparent via-cyan-300/80 to-transparent" />

            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[0.64rem] uppercase tracking-[0.24em] text-white/55">
                  Cinematic Match View
                </p>
                <h2 className="mt-2 text-2xl font-semibold text-white md:text-3xl">
                  {match.home_team} vs {match.away_team}
                </h2>
                <p className="mt-1 text-sm text-white/70">
                  {match.league} | {kickoff.dateText}
                  {kickoff.timeText ? ` ${kickoff.timeText}` : ""}
                </p>
              </div>

              <button
                type="button"
                className="rounded-xl border border-white/22 bg-white/[0.06] px-3 py-2 text-sm font-semibold text-white/80 transition hover:border-white/45 hover:text-white"
                onClick={onClose}
              >
                Close
              </button>
            </div>

            <div className="mt-5 grid gap-5 lg:grid-cols-[1fr_auto_1fr]">
              <div className="rounded-2xl border border-white/12 bg-black/30 p-4 text-center">
                {match.home_logo ? (
                  <Image
                    src={match.home_logo}
                    alt={match.home_team}
                    width={132}
                    height={132}
                    className="mx-auto h-28 w-28 rounded-full border border-white/15 bg-black/35 p-2 md:h-32 md:w-32"
                    unoptimized
                  />
                ) : (
                  <div className="mx-auto grid h-28 w-28 place-items-center rounded-full border border-white/15 bg-black/35 text-3xl font-bold md:h-32 md:w-32">
                    {toBadgeText(match.home_team, 3)}
                  </div>
                )}
                <p className="mt-3 text-lg font-semibold text-white">{match.home_team}</p>
              </div>

              <div className="grid place-items-center">
                <div className="text-center">
                  <span className="font-display text-5xl tracking-[0.2em] text-white/85">VS</span>
                  <div className="mt-2">
                    <ScoreMeter score={scorePercent} mode={mode} />
                  </div>
                </div>
              </div>

              <div className="rounded-2xl border border-white/12 bg-black/30 p-4 text-center">
                {match.away_logo ? (
                  <Image
                    src={match.away_logo}
                    alt={match.away_team}
                    width={132}
                    height={132}
                    className="mx-auto h-28 w-28 rounded-full border border-white/15 bg-black/35 p-2 md:h-32 md:w-32"
                    unoptimized
                  />
                ) : (
                  <div className="mx-auto grid h-28 w-28 place-items-center rounded-full border border-white/15 bg-black/35 text-3xl font-bold md:h-32 md:w-32">
                    {toBadgeText(match.away_team, 3)}
                  </div>
                )}
                <p className="mt-3 text-lg font-semibold text-white">{match.away_team}</p>
              </div>
            </div>

            <div className="mt-5 rounded-2xl border border-white/12 bg-black/32 p-4">
              <p className="text-[0.68rem] uppercase tracking-[0.22em] text-cyan-100/80">
                AI Tactical Insight
              </p>
              <ul className="mt-2 space-y-2">
                {reasons.map((reason, index) => (
                  <motion.li
                    key={`${reason}-${index}`}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.08 * index, duration: 0.24 }}
                    className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white/85"
                  >
                    {reason}
                  </motion.li>
                ))}
              </ul>
            </div>
          </motion.section>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
