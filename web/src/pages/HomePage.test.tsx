import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ProductSummary, Summary } from "../lib/types";
import { mockApi, renderWithApp } from "../test/render";
import HomePage from "./HomePage";

function product(id: string, name: string, status: ProductSummary["status"]): ProductSummary {
  return {
    id,
    name,
    kind: "personal",
    note: `${name} note`,
    status,
    statusSince: null,
    enabled: status !== "PAUSED",
    lastCheckAt: new Date().toISOString(),
    lastLatencyMs: 312,
    lastHttpCode: status === "DOWN" ? 502 : 200,
    lastError: status === "DOWN" ? "HTTP 502" : null,
    sortOrder: 100,
    liveUrl: null,
    openIncident: status === "DOWN",
    uptime30d: 99.94,
    strip24h: Array.from({ length: 24 }, () => 1),
  };
}

const summary: Summary = {
  up: 1,
  degraded: 1,
  down: 1,
  paused: 1,
  unknown: 0,
  total: 4,
  state: "down",
  label: "1 product down",
};

describe("HomePage", () => {
  it("lists products Down first with status text, and shows the overall state", async () => {
    mockApi({
      "GET /products": [
        200,
        [
          product("a", "Alpha", "UP"),
          product("p", "Parked", "PAUSED"),
          product("d", "Delta", "DOWN"),
          product("s", "Slowpoke", "DEGRADED"),
        ],
      ],
      "GET /summary": [200, summary],
    });
    renderWithApp(<HomePage />);

    expect(await screen.findByText("1 product down")).toBeInTheDocument();
    const cards = await screen.findAllByRole("link", { name: /: / });
    expect(cards.map((c) => c.getAttribute("aria-label"))).toEqual([
      "Delta: Down",
      "Slowpoke: Degraded",
      "Alpha: Up",
      "Parked: Paused",
    ]);
    expect(within(cards[0] as HTMLElement).getByText("HTTP 502")).toBeInTheDocument();
    expect(within(cards[0] as HTMLElement).getByText("99.94%")).toBeInTheDocument();
  });

  it("shows the empty state", async () => {
    mockApi({
      "GET /products": [200, []],
      "GET /summary": [200, { ...summary, up: 0, degraded: 0, down: 0, paused: 0, total: 0, state: "operational", label: "All systems operational" }],
    });
    renderWithApp(<HomePage />);
    expect(await screen.findByText("No products yet — tap + to add your first one.")).toBeInTheDocument();
    expect(await screen.findByText("All systems operational")).toBeInTheDocument();
  });

  it("explains API errors instead of failing silently", async () => {
    mockApi({
      "GET /products": [500, { error: { code: "boom", message: "Something broke on the server" } }],
      "GET /summary": [200, summary],
    });
    renderWithApp(<HomePage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Something broke on the server");
  });
});
