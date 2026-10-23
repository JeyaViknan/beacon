// All times arrive as UTC ISO-8601 and are shown in IST.

const IST = "Asia/Kolkata";

export function timeAgo(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return "never";
  const seconds = Math.max(0, Math.round((now.getTime() - new Date(iso).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

/** "6m 12s", "2h 14m", "3d 4h" — same rules as the backend's alert text. */
export function formatDuration(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const days = Math.floor(s / 86_400);
  const hours = Math.floor((s % 86_400) / 3_600);
  const minutes = Math.floor((s % 3_600) / 60);
  const seconds = s % 60;
  if (days) return `${days}d ${hours}h`;
  if (hours) return `${hours}h ${minutes}m`;
  if (minutes) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

export function since(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return "";
  return formatDuration((now.getTime() - new Date(iso).getTime()) / 1000);
}

/** "24 Oct, 15:45:12 IST" */
export function formatIST(iso: string | null | undefined): string {
  if (!iso) return "—";
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: IST,
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(new Date(iso));
  const get = (type: Intl.DateTimeFormatPartTypes) => parts.find((p) => p.type === type)?.value ?? "";
  return `${get("day")} ${get("month")}, ${get("hour")}:${get("minute")}:${get("second")} IST`;
}

/** "15:45" in IST, for chart axes. */
export function formatClockIST(iso: string): string {
  return new Intl.DateTimeFormat("en-GB", { timeZone: IST, hour: "2-digit", minute: "2-digit", hour12: false }).format(
    new Date(iso),
  );
}

/** "15:45:12" in IST. */
export function formatTimeIST(iso: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: IST,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(iso));
}

/** "24 Oct" in IST. */
export function formatDayIST(iso: string): string {
  return new Intl.DateTimeFormat("en-GB", { timeZone: IST, day: "numeric", month: "short" }).format(new Date(iso));
}
