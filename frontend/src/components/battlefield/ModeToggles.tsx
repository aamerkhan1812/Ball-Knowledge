"use client";

import { motion } from "framer-motion";
import type { Dispatch, SetStateAction } from "react";
import type { UiMode } from "@/components/battlefield/types";

type ModeTogglesProps = {
  mode: UiMode;
  setMode: Dispatch<SetStateAction<UiMode>>;
};

function toggleBaseStyles(isActive: boolean): string {
  return isActive
    ? "border-white/50 bg-white/18 text-white shadow-[0_0_30px_rgba(66,213,255,0.22)]"
    : "border-white/20 bg-white/[0.04] text-white/70 hover:border-white/35 hover:text-white";
}

export function ModeToggles({ mode, setMode }: ModeTogglesProps) {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-2xl border border-white/12 bg-black/30 p-2 backdrop-blur-md">
      <motion.button
        type="button"
        whileTap={{ scale: 0.97 }}
        onClick={() => setMode("chaos")}
        className={`rounded-xl border px-4 py-2 text-sm font-semibold transition ${toggleBaseStyles(mode === "chaos")}`}
      >
        Chaos Mode
      </motion.button>
      <motion.button
        type="button"
        whileTap={{ scale: 0.97 }}
        onClick={() => setMode("tactical")}
        className={`rounded-xl border px-4 py-2 text-sm font-semibold transition ${toggleBaseStyles(mode === "tactical")}`}
      >
        Tactical Mode
      </motion.button>
    </div>
  );
}
