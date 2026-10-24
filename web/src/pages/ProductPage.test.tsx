import { screen } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import type { ProductDetail } from "../lib/types";
import { mockApi, renderWithApp } from "../test/render";
import ProductPage from "./ProductPage";

const now = new Date().toISOString();

const detail: ProductDetail = {
  product: {
    id: "NEW1",
    name: "myapp.vercel.app",
    kind: "personal",
    note: "",
    checkUrl: "https://myapp.vercel.app",
    method: "GET",
    expectedStatus: "200-399",
    keyword: null,
    timeoutMs: 10000,
    intervalMin: 1,
    latencyWarnMs: 2000,
    openAfter: 2,
    resolveAfter: 2,
    sloTarget: 99.5,
    liveUrl: null,
    githubUrl: null,
    stack: [],
    sortOrder: 100,
    enabled: true,
    createdAt: now,
    updatedAt: now,
    status: "UNKNOWN",
    statusSince: now,
    lastCheckAt: null,
    lastLatencyMs: null,
    lastHttpCode: null,
    lastError: null,
    regions: {},
    openIncidentSk: null,
    recentLatencies: [],
    certExpiresAt: null,
  },
  stats: {
    uptime24h: null,
    uptime7d: null,
    uptime30d: null,
    avgLatency24h: null,
    p95Latency1h: null,
    sloTarget: 99.5,
    errorBudget: { budgetMin: 216, consumedMin: 0, remainingMin: 216, remainingRatio: null, monitoredMin: 0 },
  },
  openIncident: null,
};

const testResult = {
  productId: "NEW1",
  ok: true,
  httpCode: 200,
  latencyMs: 184,
  error: null,
  keywordOk: null,
  checkedAt: now,
  region: "ap-south-1",
};

function renderPage(state?: unknown) {
  return renderWithApp(
    <Routes>
      <Route path="/p/:id" element={<ProductPage />} />
    </Routes>,
    { pathname: "/p/NEW1", state },
  );
}

describe("ProductPage", () => {
  it("checks a just-added product at once and says what happens next", async () => {
    const calls = mockApi({ "GET /products/NEW1": [200, detail], "POST /products/NEW1/test": [200, testResult] });
    renderPage({ justAdded: true });
    expect(await screen.findByText("OK · HTTP 200")).toBeInTheDocument();
    expect(screen.getByText(/checks it every minute from now on/)).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "POST" && c.path === "/products/NEW1/test")).toHaveLength(1);
  });

  it("doesn't run a check on a normal visit", async () => {
    const calls = mockApi({ "GET /products/NEW1": [200, detail] });
    renderPage();
    expect(await screen.findByRole("button", { name: "Test now" })).toBeInTheDocument();
    expect(screen.queryByText(/from now on/)).not.toBeInTheDocument();
    expect(calls.some((c) => c.method === "POST")).toBe(false);
  });
});
