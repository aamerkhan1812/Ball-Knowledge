"use client";

import { useMemo, useSyncExternalStore } from "react";
import { nextKickoffFromMatches } from "@/components/battlefield/helpers";
import type { Match } from "@/components/battlefield/types";

function formatDuration(milliseconds: number): string {
  const seconds = Math.max(0, Math.floor(milliseconds / 1000));
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;

  if (days > 0) {
    return `${days}d ${hours}h ${minutes}m`;
  }
  return `${hours.toString().padStart(2, "0")}h ${minutes.toString().padStart(2, "0")}m ${secs.toString().padStart(2, "0")}s`;
}

export function NextKickoffClock({ matches }: { matches: Match[] }) {
  const now = useSyncExternalStore(
    (onStoreChange) => {
      const timer = window.setInterval(onStoreChange, 1000);
      return () => window.clearInterval(timer);
    },
    () => Date.now(),
    () => 0,
  );
  const nextKickoff = useMemo(() => nextKickoffFromMatches(matches), [matches]);

  let timerLabel = "Awaiting fixture signal";
  if (nextKickoff) {
    timerLabel = formatDuration(nextKickoff.getTime() - now);
  }

  return (
    <div className="rounded-2xl border border-white/12 bg-black/30 px-4 py-2.5 backdrop-blur-md">
      <p className="text-[0.64rem] uppercase tracking-[0.2em] text-white/55">Next Kickoff In:</p>
      <p className="mt-1 text-lg font-semibold text-white">{timerLabel}</p>
    </div>
  );
}
