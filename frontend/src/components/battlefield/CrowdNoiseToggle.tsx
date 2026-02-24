"use client";

import type { Dispatch, SetStateAction } from "react";

type CrowdNoiseToggleProps = {
  muted: boolean;
  setMuted: Dispatch<SetStateAction<boolean>>;
};

export function CrowdNoiseToggle({ muted, setMuted }: CrowdNoiseToggleProps) {
  return (
    <button
      type="button"
      onClick={() => setMuted((previous) => !previous)}
      className="group inline-flex items-center justify-between gap-3 rounded-2xl border border-white/12 bg-black/30 px-4 py-2.5 text-left text-sm text-white/80 transition hover:border-white/35 hover:text-white"
      aria-pressed={muted}
      title="Crowd ambience toggle"
    >
      <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-white/20 bg-white/[0.07]">
        <svg
          viewBox="0 0 24 24"
          className="h-4.5 w-4.5"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.9"
          aria-hidden="true"
        >
          <path d="M4 10h4l5-4v12l-5-4H4z" />
          {muted ? <path d="m17 9 4 6M21 9l-4 6" /> : <path d="M18 8.5a5 5 0 0 1 0 7" />}
        </svg>
      </span>

      <span className="leading-tight">
        <span className="block font-semibold">Crowd FX</span>
        <span className="block text-xs text-white/60">{muted ? "Muted" : "Live ambience"}</span>
      </span>
    </button>
  );
}
