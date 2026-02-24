"use client";

import { motion } from "framer-motion";
import type { CSSProperties } from "react";
import type { UiMode } from "@/components/battlefield/types";

type ParticleStyle = CSSProperties & {
  "--particle-delay": string;
  "--particle-duration": string;
  "--particle-scale": string;
};

const particles: ParticleStyle[] = Array.from({ length: 30 }, (_, index) => {
  const left = (index * 17) % 100;
  const top = (index * 31 + 13) % 100;
  const delay = `${-(index % 9)}s`;
  const duration = `${10 + (index % 6) * 1.2}s`;
  const scale = `${0.5 + (index % 5) * 0.16}`;

  return {
    left: `${left}%`,
    top: `${top}%`,
    "--particle-delay": delay,
    "--particle-duration": duration,
    "--particle-scale": scale,
  };
});

export function ActiveBackground({ mode }: { mode: UiMode }) {
  return (
    <div className={`cyber-battlefield-bg ${mode === "chaos" ? "mode-chaos" : "mode-tactical"}`} aria-hidden="true">
      <div className="bg-mesh-gradient" />
      <div className="fog-layer fog-layer-a" />
      <div className="fog-layer fog-layer-b" />
      <div className="stadium-vignette" />

      <motion.span
        className="floodlight-beam floodlight-left"
        animate={{
          x: [-36, 14, -20, -36],
          rotate: [-16, -8, -12, -16],
          opacity: [0.15, 0.46, 0.24, 0.15],
        }}
        transition={{ duration: 15, ease: "easeInOut", repeat: Number.POSITIVE_INFINITY }}
      />
      <motion.span
        className="floodlight-beam floodlight-right"
        animate={{
          x: [28, -16, 10, 28],
          rotate: [16, 8, 12, 16],
          opacity: [0.14, 0.44, 0.2, 0.14],
        }}
        transition={{ duration: 19, ease: "easeInOut", repeat: Number.POSITIVE_INFINITY }}
      />

      <div className="particle-field">
        {particles.map((particle, index) => (
          <span key={index} className="particle-node" style={particle} />
        ))}
      </div>

      <div className="bg-tracer-stream">
        <span className="bg-tracer tracer-a" />
        <span className="bg-tracer tracer-b" />
        <span className="bg-tracer tracer-c" />
        <span className="bg-tracer tracer-d" />
      </div>
      <div className="background-grid" />
    </div>
  );
}
