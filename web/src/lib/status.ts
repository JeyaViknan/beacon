import type { SymbolName } from "../symbols/names";
import type { Status } from "./types";

export interface StatusMeta {
  label: string;
  /** One symbol per status, so status never relies on colour alone. */
  symbol: SymbolName;
  /** CSS custom properties: system colour for symbols and bars, and a text-safe version. */
  color: string;
  ink: string;
}

export const STATUS: Record<Status, StatusMeta> = {
  DOWN: { label: "Down", symbol: "xmark.circle.fill", color: "var(--red)", ink: "var(--red-ink)" },
  DEGRADED: { label: "Degraded", symbol: "exclamationmark.triangle.fill", color: "var(--orange)", ink: "var(--orange-ink)" },
  UP: { label: "Up", symbol: "checkmark.circle.fill", color: "var(--green)", ink: "var(--green-ink)" },
  UNKNOWN: { label: "Waiting", symbol: "clock.fill", color: "var(--gray)", ink: "var(--gray-ink)" },
  PAUSED: { label: "Paused", symbol: "pause.circle.fill", color: "var(--gray)", ink: "var(--gray-ink)" },
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
  if (ratio === null) return "var(--fill)";
  if (ratio >= 0.999) return "var(--green)";
  if (ratio >= 0.95) return "var(--orange)";
  return "var(--red)";
}

export function formatUptime(percent: number | null): string {
  return percent === null ? "—" : `${percent.toFixed(2)}%`;
}

export function formatLatency(ms: number | null): string {
  if (ms === null) return "—";
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)} s` : `${ms} ms`;
}
