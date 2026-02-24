"use client";

import Image from "next/image";
import { motion, useMotionTemplate, useMotionValue, useSpring } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import {
  formatKickoff,
  parseProbabilityToPercent,
  rankLabel,
  splitReasoning,
  toBadgeText,
} from "@/components/battlefield/helpers";
import { ScoreMeter } from "@/components/battlefield/ScoreMeter";
import type { Match, UiMode } from "@/components/battlefield/types";

type MatchCardProps = {
  match: Match;
  index: number;
  mode: UiMode;
  onOpen: (match: Match) => void;
};

function rankStyles(index: number): string {
  if (index === 0) {
    return "border-amber-300/50 bg-amber-300/15 text-amber-100";
  }
  if (index === 1) {
    return "border-cyan-300/45 bg-cyan-300/15 text-cyan-100";
  }
  if (index === 2) {
    return "border-emerald-300/45 bg-emerald-300/15 text-emerald-100";
  }
  return "border-white/20 bg-white/8 text-white/80";
}

export function MatchCard({ match, index, mode, onOpen }: MatchCardProps) {
  const [supportsTilt, setSupportsTilt] = useState(false);
  const rotateX = useMotionValue(0);
  const rotateY = useMotionValue(0);
  const cursorX = useMotionValue(50);
  const cursorY = useMotionValue(50);
  const smoothX = useSpring(rotateX, { stiffness: 170, damping: 22 });
  const smoothY = useSpring(rotateY, { stiffness: 170, damping: 22 });
  const spotlight = useMotionTemplate`radial-gradient(560px circle at ${cursorX}% ${cursorY}%, rgba(124, 216, 255, 0.2), transparent 50%)`;

  const { dateText, timeText } = useMemo(
    () => formatKickoff(match.kickoff),
    [match.kickoff],
  );
  const scorePercent = useMemo(
    () => parseProbabilityToPercent(match.probability, match.score),
    [match.probability, match.score],
  );
  const reasons = useMemo(() => splitReasoning(match.reason), [match.reason]);
  const isHot = scorePercent >= 70;

  useEffect(() => {
    const mediaQuery = window.matchMedia("(min-width: 1024px) and (hover: hover)");
    const update = () => setSupportsTilt(mediaQuery.matches);
    update();

    mediaQuery.addEventListener("change", update);
    return () => mediaQuery.removeEventListener("change", update);
  }, []);

  const handleMouseMove = (event: React.MouseEvent<HTMLElement>) => {
    if (!supportsTilt) {
      return;
    }
    const target = event.currentTarget.getBoundingClientRect();
    const x = event.clientX - target.left;
    const y = event.clientY - target.top;
    const centerX = target.width / 2;
    const centerY = target.height / 2;

    rotateY.set(((x - centerX) / centerX) * 5.5);
    rotateX.set(((centerY - y) / centerY) * 5.5);
    cursorX.set((x / target.width) * 100);
    cursorY.set((y / target.height) * 100);
  };

  const resetTilt = () => {
    rotateX.set(0);
    rotateY.set(0);
    cursorX.set(50);
    cursorY.set(50);
  };

  return (
    <motion.article
      onClick={() => onOpen(match)}
      onMouseMove={handleMouseMove}
      onMouseLeave={resetTilt}
      whileHover={{ y: -6, scale: 1.01 }}
      transition={{ duration: 0.22, ease: "easeOut" }}
      style={
        supportsTilt
          ? { rotateX: smoothX, rotateY: smoothY, transformPerspective: 1000 }
          : undefined
      }
      className={`group relative overflow-hidden rounded-[1.5rem] border border-white/15 bg-white/[0.07] p-4 shadow-[0_16px_40px_rgba(0,0,0,0.35)] backdrop-blur-xl md:p-5 ${isHot ? "match-hot" : ""}`}
      role="button"
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen(match);
        }
      }}
    >
      <motion.div className="pointer-events-none absolute inset-0 opacity-0 transition duration-300 group-hover:opacity-100" style={{ background: spotlight }} />

      <div className="relative z-10 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            {match.league_logo ? (
              <Image
                src={match.league_logo}
                alt={match.league}
                width={28}
                height={28}
                className="h-7 w-7 rounded-full border border-white/20 bg-black/35 p-0.5"
                unoptimized
              />
            ) : (
              <span className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-white/20 bg-black/35 text-[10px] font-bold">
                {toBadgeText(match.league, 3)}
              </span>
            )}
            <p className="truncate text-xs uppercase tracking-[0.14em] text-white/70">
              {match.league}
            </p>
          </div>
          <p className="mt-1 text-sm text-white/75">
            {dateText}
            {timeText ? ` ${timeText}` : ""}
          </p>
        </div>

        <span className={`rounded-full border px-3 py-1 text-[0.67rem] font-semibold uppercase tracking-[0.15em] ${rankStyles(index)}`}>
          {rankLabel(index)}
        </span>
      </div>

      <div className="relative z-10 mt-4 grid grid-cols-[1fr_auto_1fr] items-center gap-3 md:gap-4">
        <div className="flex flex-col items-center text-center">
          {match.home_logo ? (
            <Image
              src={match.home_logo}
              alt={match.home_team}
              width={88}
              height={88}
              className="h-20 w-20 rounded-full border border-white/15 bg-black/40 p-1.5 shadow-[0_0_26px_rgba(66,213,255,0.22)] md:h-24 md:w-24"
              unoptimized
            />
          ) : (
            <div className="grid h-20 w-20 place-items-center rounded-full border border-white/15 bg-black/40 text-lg font-bold md:h-24 md:w-24">
              {toBadgeText(match.home_team, 3)}
            </div>
          )}
          <p className="mt-2 text-sm font-semibold text-white md:text-base">{match.home_team}</p>
        </div>

        <div className="flex flex-col items-center gap-2">
          <span className="font-display text-3xl tracking-[0.16em] text-white/85 md:text-4xl">
            VS
          </span>
          <ScoreMeter score={scorePercent} mode={mode} />
          <p className="text-[0.68rem] uppercase tracking-[0.18em] text-white/60">
            Hype Score
          </p>
        </div>

        <div className="flex flex-col items-center text-center">
          {match.away_logo ? (
            <Image
              src={match.away_logo}
              alt={match.away_team}
              width={88}
              height={88}
              className="h-20 w-20 rounded-full border border-white/15 bg-black/40 p-1.5 shadow-[0_0_26px_rgba(66,213,255,0.22)] md:h-24 md:w-24"
              unoptimized
            />
          ) : (
            <div className="grid h-20 w-20 place-items-center rounded-full border border-white/15 bg-black/40 text-lg font-bold md:h-24 md:w-24">
              {toBadgeText(match.away_team, 3)}
            </div>
          )}
          <p className="mt-2 text-sm font-semibold text-white md:text-base">{match.away_team}</p>
        </div>
      </div>

      <div className="relative z-10 mt-4 rounded-xl border border-white/12 bg-black/30 p-3">
        <p className="text-[0.62rem] uppercase tracking-[0.2em] text-cyan-100/80">
          AI Tactical Insight
        </p>
        <ul className="mt-2 space-y-1.5">
          {reasons.map((reason, reasonIndex) => (
            <motion.li
              key={`${reason}-${reasonIndex}`}
              initial={{ opacity: 0, y: 7 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.08 * reasonIndex, duration: 0.26 }}
              className="text-sm text-white/80"
            >
              {reason}
            </motion.li>
          ))}
        </ul>
      </div>
    </motion.article>
  );
}
