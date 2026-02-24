"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import type { UiMode } from "@/components/battlefield/types";

const loadingLines = [
  "Scanning tonight's battles...",
  "Analyzing title pressure...",
  "Calculating derby chaos...",
  "Mapping tactical fault lines...",
];

export function LoadingSequence({ mode }: { mode: UiMode }) {
  const [lineIndex, setLineIndex] = useState(0);
  const [progress, setProgress] = useState(16);

  useEffect(() => {
    const lineTicker = window.setInterval(() => {
      setLineIndex((previous) => (previous + 1) % loadingLines.length);
    }, 1300);
    return () => window.clearInterval(lineTicker);
  }, []);

  useEffect(() => {
    const progressTicker = window.setInterval(() => {
      setProgress((previous) => {
        if (previous > 94) {
          return 24;
        }
        return previous + 3;
      });
    }, 180);
    return () => window.clearInterval(progressTicker);
  }, []);

  return (
    <div className="loading-shell">
      <motion.section
        initial={{ opacity: 0, scale: 0.96, y: 18 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.42, ease: "easeOut" }}
        className="loading-panel"
      >
        <motion.div
          className={`ai-core-orb ${mode === "chaos" ? "core-chaos" : "core-tactical"}`}
          animate={{
            scale: [1, 1.12, 1],
            boxShadow: [
              "0 0 0 0 rgba(255,255,255,0.2)",
              "0 0 0 16px rgba(255,255,255,0)",
              "0 0 0 0 rgba(255,255,255,0)",
            ],
          }}
          transition={{ duration: 2.6, ease: "easeInOut", repeat: Number.POSITIVE_INFINITY }}
        />

        <motion.div
          className="loading-ball"
          animate={{ rotate: 360 }}
          transition={{ duration: 2.2, ease: "linear", repeat: Number.POSITIVE_INFINITY }}
        />

        <div className="loading-text-wrap">
          <AnimatePresence mode="wait">
            <motion.p
              key={lineIndex}
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.32, ease: "easeOut" }}
              className="loading-line"
            >
              {loadingLines[lineIndex]}
            </motion.p>
          </AnimatePresence>
        </div>

        <div className="heartbeat-track" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress}>
          <motion.div
            className="heartbeat-fill"
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.18, ease: "linear" }}
          />
          <div className="heartbeat-overlay" />
        </div>

        <p className="loading-subline">AI match engine calibrating pressure models</p>
      </motion.section>
    </div>
  );
}
