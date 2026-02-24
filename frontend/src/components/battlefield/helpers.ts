import type { Match } from "@/components/battlefield/types";

export function toBadgeText(name: string, maxLength = 3): string {
  const tokens = name.trim().match(/[A-Za-z0-9]+/g) ?? [];
  if (tokens.length === 0) {
    return "?";
  }

  if (tokens.length === 1) {
    const single = tokens[0].slice(0, Math.max(2, Math.min(3, maxLength)));
    return single.toUpperCase() || "?";
  }

  const initials = tokens
    .slice(0, Math.max(2, maxLength))
    .map((token) => token[0]?.toUpperCase() ?? "")
    .join("");

  if (initials.length > 0) {
    return initials;
  }

  const firstToken = tokens[0] ?? "";
  return firstToken.slice(0, 2).toUpperCase() || "?";
}

export function formatKickoff(kickoff: string): { dateText: string; timeText: string } {
  const kickoffDate = new Date(kickoff);
  if (Number.isNaN(kickoffDate.getTime())) {
    return { dateText: "Kickoff TBD", timeText: "" };
  }

  return {
    dateText: kickoffDate.toLocaleDateString([], {
      weekday: "short",
      month: "short",
      day: "numeric",
    }),
    timeText: kickoffDate.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    }),
  };
}

export function rankLabel(index: number): string {
  if (index === 0) {
    return "Must Watch";
  }
  if (index === 1) {
    return "Backup Pick";
  }
  if (index === 2) {
    return "Solid Pick";
  }
  return "Watchlist";
}

export function parseProbabilityToPercent(probability: string, fallback: number): number {
  const numeric = probability.match(/\d+/)?.[0];
  if (!numeric) {
    return clampScore(fallback);
  }
  const parsed = Number(numeric);
  if (!Number.isFinite(parsed)) {
    return clampScore(fallback);
  }
  return clampScore(parsed);
}

export function splitReasoning(reason: string): string[] {
  const pieces = reason
    .split(/[,;|]/g)
    .map((part) => part.trim())
    .filter(Boolean);
  return pieces.length > 0 ? pieces : ["Pattern confidence is still calibrating."];
}

export function clampScore(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.max(0, Math.min(100, Math.round(value)));
}

export function nextKickoffFromMatches(matches: Match[]): Date | null {
  const now = Date.now();
  let closest: number | null = null;

  for (const match of matches) {
    const kickoff = new Date(match.kickoff).getTime();
    if (!Number.isFinite(kickoff) || kickoff < now) {
      continue;
    }
    if (closest === null || kickoff < closest) {
      closest = kickoff;
    }
  }

  return closest === null ? null : new Date(closest);
}
