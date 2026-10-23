import type { Status } from "./types";

export interface StatusMeta {
  label: string;
  /** CSS custom properties: dot/bar colour and readable text colour. */
  color: string;
  ink: string;
}

export const STATUS: Record<Status, StatusMeta> = {
  DOWN: { label: "Down", color: "var(--down)", ink: "var(--down-ink)" },
  DEGRADED: { label: "Degraded", color: "var(--degraded)", ink: "var(--degraded-ink)" },
  UP: { label: "Up", color: "var(--up)", ink: "var(--up-ink)" },
  UNKNOWN: { label: "Waiting", color: "var(--unknown)", ink: "var(--unknown-ink)" },
  PAUSED: { label: "Paused", color: "var(--paused)", ink: "var(--paused-ink)" },
};

const ORDER: Record<Status, number> = { DOWN: 0, DEGRADED: 1, UP: 2, UNKNOWN: 3, PAUSED: 4 };

/** Down -> Degraded -> Up -> Waiting -> Paused, then sortOrder, then name. */
export function sortProducts<T extends { status: Status; sortOrder: number; name: string }>(items: readonly T[]): T[] {
  return [...items].sort(
    (a, b) =>
      ORDER[a.status] - ORDER[b.status] ||
      a.sortOrder - b.sortOrder ||
      a.name.localeCompare(b.name, undefined, { sensitivity: "base" }),
  );
}

/** Colour for one hour of the 24h strip, from that hour's uptime ratio. */
export function stripColor(ratio: number | null): string {
  if (ratio === null) return "var(--line)";
  if (ratio >= 0.999) return "var(--up)";
  if (ratio >= 0.95) return "var(--degraded)";
  return "var(--down)";
}

export function formatUptime(percent: number | null): string {
  return percent === null ? "—" : `${percent.toFixed(2)}%`;
}

export function formatLatency(ms: number | null): string {
  if (ms === null) return "—";
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${ms} ms`;
}
