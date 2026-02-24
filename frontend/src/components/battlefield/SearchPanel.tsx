"use client";

import { useState } from "react";

type SearchPanelProps = {
  searchInput: string;
  setSearchInput: (value: string) => void;
  onApply: () => void;
};

const TEAM_SUGGESTIONS = [
  "Arsenal",
  "Aston Villa",
  "Chelsea",
  "Everton",
  "Liverpool",
  "Manchester City",
  "Manchester United",
  "Newcastle",
  "Tottenham",
  "Real Madrid",
  "Barcelona",
  "Atletico Madrid",
  "Bayern Munich",
  "Borussia Dortmund",
  "Bayer Leverkusen",
  "Inter",
  "AC Milan",
  "Juventus",
  "Napoli",
  "PSG",
];

export function SearchPanel({
  searchInput,
  setSearchInput,
  onApply,
}: SearchPanelProps) {
  const [focused, setFocused] = useState(false);

  return (
    <section id="search-zone" className="rounded-2xl border border-white/12 bg-black/30 p-3 backdrop-blur-md md:p-4">
      <label htmlFor="team-search" className="text-xs font-semibold uppercase tracking-[0.22em] text-white/65">
        Favorite Team
      </label>

      <div className="mt-2 flex flex-col gap-2 md:flex-row">
        <div className={`spark-frame ${focused ? "spark-frame-active" : ""}`}>
          <input
            id="team-search"
            list="team-options"
            value={searchInput}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            onChange={(event) => setSearchInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                onApply();
              }
            }}
            placeholder="Search your team (e.g. Alaves, Chelsea)"
            className="w-full rounded-xl border border-white/15 bg-black/45 px-4 py-3 text-sm text-white placeholder:text-white/40 focus:border-white/45 focus:outline-none md:text-base"
          />
          <span className="spark-trail" />
        </div>

        <button
          type="button"
          onClick={onApply}
          className="rounded-xl border border-cyan-300/40 bg-gradient-to-r from-cyan-400/40 via-blue-400/30 to-emerald-300/40 px-5 py-3 text-sm font-semibold text-white transition hover:border-cyan-200/70 hover:shadow-[0_0_28px_rgba(66,213,255,0.35)] md:min-w-36 md:text-base"
        >
          Engage Search
        </button>
      </div>

      <datalist id="team-options">
        {TEAM_SUGGESTIONS.map((team) => (
          <option key={team} value={team} />
        ))}
      </datalist>
    </section>
  );
}
