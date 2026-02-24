"use client";

import { animate, motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import { clampScore } from "@/components/battlefield/helpers";
import type { UiMode } from "@/components/battlefield/types";

const RADIUS = 42;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export function ScoreMeter({
  score,
  mode,
}: {
  score: number;
  mode: UiMode;
}) {
  const percent = useMemo(() => clampScore(score), [score]);
  const [displayValue, setDisplayValue] = useState(0);

  useEffect(() => {
    const controls = animate(0, percent, {
      duration: 1.05,
      ease: "easeOut",
      onUpdate: (value) => {
        setDisplayValue(Math.round(value));
      },
    });
    return () => controls.stop();
  }, [percent]);

  const strokeOffset = CIRCUMFERENCE * (1 - displayValue / 100);
  const isHot = percent >= 70;
  const gradientId = `score-gradient-${mode}`;

  return (
    <div className="relative flex flex-col items-center gap-2">
      <div className="relative">
        {isHot ? <span className="flame-aura" /> : null}
        <svg width="108" height="108" viewBox="0 0 108 108" aria-hidden="true">
          <defs>
            <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor={mode === "chaos" ? "#ff4e63" : "#3ed8ff"} />
              <stop offset="50%" stopColor={mode === "chaos" ? "#ff923a" : "#7b9dff"} />
              <stop offset="100%" stopColor={mode === "chaos" ? "#ffe078" : "#6effcb"} />
            </linearGradient>
          </defs>

          <circle
            cx="54"
            cy="54"
            r={RADIUS}
            stroke="rgba(255,255,255,0.14)"
            strokeWidth="8"
            fill="none"
          />
          <motion.circle
            cx="54"
            cy="54"
            r={RADIUS}
            stroke={`url(#${gradientId})`}
            strokeWidth="8"
            strokeLinecap="round"
            fill="none"
            strokeDasharray={CIRCUMFERENCE}
            animate={{ strokeDashoffset: strokeOffset }}
            transition={{ duration: 0.25, ease: "linear" }}
            transform="rotate(-90 54 54)"
            className="drop-shadow-[0_0_10px_rgba(72,214,255,0.55)]"
          />
        </svg>

        <div className="absolute inset-0 grid place-items-center">
          <span className="text-2xl font-bold text-white">{displayValue}</span>
        </div>
      </div>

      <div className="h-2.5 w-24 overflow-hidden rounded-full border border-white/15 bg-black/35">
        <motion.span
          className={`block h-full ${mode === "chaos" ? "bg-gradient-to-r from-red-500 via-orange-400 to-amber-300" : "bg-gradient-to-r from-sky-400 via-blue-400 to-emerald-300"}`}
          animate={{ width: `${percent}%` }}
          transition={{ duration: 0.95, ease: "easeOut" }}
          style={{ width: 0 }}
        />
      </div>
    </div>
  );
}
