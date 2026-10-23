import { describe, expect, it } from "vitest";
import { formatDuration, formatIST, since, timeAgo } from "./time";

const NOW = new Date("2026-10-24T10:00:00Z");

describe("timeAgo", () => {
  it.each([
    ["2026-10-24T09:59:37Z", "23s ago"],
    ["2026-10-24T10:00:05Z", "0s ago"], // clock skew never shows negative
    ["2026-10-24T09:55:00Z", "5m ago"],
    ["2026-10-24T07:00:00Z", "3h ago"],
    ["2026-10-21T10:00:00Z", "3d ago"],
  ])("%s -> %s", (iso, expected) => {
    expect(timeAgo(iso, NOW)).toBe(expected);
  });

  it("handles missing timestamps", () => {
    expect(timeAgo(null, NOW)).toBe("never");
  });
});

describe("durations", () => {
  it.each([
    [45, "45s"],
    [372, "6m 12s"],
    [8040, "2h 14m"],
    [273600, "3d 4h"],
  ])("%i seconds -> %s", (s, expected) => {
    expect(formatDuration(s)).toBe(expected);
  });

  it("since() measures from a timestamp", () => {
    expect(since("2026-10-24T07:46:00Z", NOW)).toBe("2h 14m");
  });
});

describe("formatIST", () => {
  it("shows UTC timestamps in IST", () => {
    expect(formatIST("2026-10-24T10:15:07Z")).toBe("24 Oct, 15:45:07 IST");
    expect(formatIST("2026-10-24T18:45:00Z")).toBe("25 Oct, 00:15:00 IST");
  });
});
