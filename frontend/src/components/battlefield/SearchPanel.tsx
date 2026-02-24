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
    <section
      id="search-zone"
      className="mx-auto w-full rounded-2xl border border-white/18 bg-black/35 p-4 backdrop-blur-md md:p-5"
    >
      <label
        htmlFor="team-search"
        className="block text-center text-[0.72rem] font-semibold uppercase tracking-[0.24em] text-white/72 md:text-xs"
      >
        Team Selection
      </label>

      <div className="mt-3 grid gap-3 md:grid-cols-[1fr_auto] md:items-center">
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
            className="w-full rounded-xl border border-white/20 bg-black/45 px-5 py-4 text-base text-white placeholder:text-white/42 focus:border-white/50 focus:outline-none md:text-lg"
          />
          <span className="spark-trail" />
        </div>

        <button
          type="button"
          onClick={onApply}
          className="w-full rounded-xl border border-cyan-300/45 bg-gradient-to-r from-cyan-400/45 via-blue-400/35 to-emerald-300/45 px-6 py-4 text-base font-semibold text-white transition hover:border-cyan-200/75 hover:shadow-[0_0_28px_rgba(66,213,255,0.35)] md:w-auto md:min-w-52 md:text-lg"
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
