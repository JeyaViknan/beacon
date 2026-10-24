import { describe, expect, it } from "vitest";
import { STATUS, formatLatency, formatUptime, sortProducts, stripColor } from "./status";
import type { Status } from "./types";

const p = (name: string, status: Status, sortOrder = 100) => ({ name, status, sortOrder });

describe("sortProducts", () => {
  it("puts Down first, then Degraded, Up, Waiting, Paused", () => {
    const sorted = sortProducts([
      p("paused", "PAUSED"),
      p("up", "UP"),
      p("waiting", "UNKNOWN"),
      p("down", "DOWN"),
      p("slow", "DEGRADED"),
    ]);
    expect(sorted.map((x) => x.name)).toEqual(["down", "slow", "up", "waiting", "paused"]);
  });

  it("breaks ties by sortOrder, then by name (case-insensitive)", () => {
    const sorted = sortProducts([p("beta", "UP", 100), p("Alpha", "UP", 100), p("zulu", "UP", 1)]);
    expect(sorted.map((x) => x.name)).toEqual(["zulu", "Alpha", "beta"]);
  });

  it("does not mutate the input", () => {
    const input = [p("b", "UP"), p("a", "DOWN")];
    sortProducts(input);
    expect(input[0]?.name).toBe("b");
  });
});

describe("status presentation", () => {
  it("has a text label for every status (never colour alone)", () => {
    for (const meta of Object.values(STATUS)) {
      expect(meta.label.length).toBeGreaterThan(0);
      expect(meta.color).toMatch(/^var\(--/);
    }
  });

  it.each([
    [null, "var(--fill)"],
    [1, "var(--green)"],
    [0.9995, "var(--green)"],
    [0.97, "var(--orange)"],
    [0.5, "var(--red)"],
  ])("strip colour for %s is %s", (ratio, color) => {
    expect(stripColor(ratio)).toBe(color);
  });

  it("formats uptime and latency", () => {
    expect(formatUptime(99.94)).toBe("99.94%");
    expect(formatUptime(null)).toBe("—");
    expect(formatLatency(312)).toBe("312 ms");
    expect(formatLatency(3400)).toBe("3.4 s");
    expect(formatLatency(null)).toBe("—");
  });
});
