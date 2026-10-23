// Dev-only fake API (VITE_MOCK=1 npm run dev): realistic data for previews and screenshots.
// Never bundled into production builds (main.tsx imports it only when import.meta.env.DEV).

import type {
  CheckRow,
  Incident,
  Product,
  ProductDetail,
  ProductSummary,
  SeriesPoint,
  SettingsResponse,
  Status,
} from "../lib/types";

const MIN = 60_000;
const now = () => Date.now();
const iso = (ms: number) => new Date(ms).toISOString().replace(/\.\d{3}Z$/, "Z");

let seed = 7;
function rand(): number {
  seed = (seed * 16807) % 2147483647;
  return seed / 2147483647;
}

interface Seed {
  id: string;
  name: string;
  kind: "personal" | "client";
  note: string;
  status: Status;
  latency: number;
  error?: string;
  badHours?: number[];
  stack: string[];
}

const SEEDS: Seed[] = [
  {
    id: "01JNANKIV",
    name: "Nankiv",
    kind: "personal",
    note: "Personal site and blog",
    status: "UP",
    latency: 312,
    stack: ["Next.js", "Vercel"],
  },
  {
    id: "01JCLINIC",
    name: "Clinic Booking",
    kind: "client",
    note: "Client work — appointment booking for a clinic chain",
    status: "DOWN",
    latency: 431,
    error: "HTTP 502",
    badHours: [22, 23],
    stack: ["Django", "Postgres", "AWS"],
  },
  {
    id: "01JMERIDIAN",
    name: "Meridian",
    kind: "client",
    note: "Client work — logistics dashboard for a regional distributor",
    status: "DEGRADED",
    latency: 3400,
    badHours: [9],
    stack: ["React", "Node.js"],
  },
  {
    id: "01JSNP",
    name: "Sorry No Proxy",
    kind: "personal",
    note: "Side project: a tiny proxy checker",
    status: "UP",
    latency: 188,
    stack: ["Go", "Fly.io"],
  },
  {
    id: "01JDEMO",
    name: "Beacon Demo Target",
    kind: "personal",
    note: "Used for live demos",
    status: "PAUSED",
    latency: 95,
    stack: ["AWS Lambda", "SSM"],
  },
];

let demoBroken = false;

function strip(s: Seed): (number | null)[] {
  if (s.status === "PAUSED") return Array.from({ length: 24 }, (_, i) => (i < 18 ? 1 : null));
  return Array.from({ length: 24 }, (_, i) => (s.badHours?.includes(i) ? (i === 23 ? 0.6 : 0.97) : 1));
}

function summary(s: Seed): ProductSummary {
  return {
    id: s.id,
    name: s.name,
    kind: s.kind,
    note: s.note,
    status: s.status,
    statusSince: iso(now() - (s.status === "DOWN" ? 6 * MIN + 12_000 : 2 * 60 * MIN + 14 * MIN)),
    enabled: s.status !== "PAUSED",
    lastCheckAt: iso(now() - 23_000),
    lastLatencyMs: s.latency,
    lastHttpCode: s.error ? 502 : 200,
    lastError: s.error ?? null,
    sortOrder: s.id === "01JDEMO" ? 999 : 100,
    liveUrl: `https://${s.name.toLowerCase().replace(/\s+/g, "")}.example`,
    openIncident: s.status === "DOWN",
    uptime30d: s.status === "DOWN" ? 99.41 : s.status === "DEGRADED" ? 99.87 : 99.98,
    strip24h: strip(s),
  };
}

function incident(s: Seed): Incident {
  const started = now() - 6 * MIN - 12_000;
  return {
    productId: s.id,
    productName: s.name,
    sk: `INC#${iso(started)}#01JINC${s.id}`,
    id: `01JINC${s.id}`,
    state: "OPEN",
    startedAt: iso(started),
    acknowledgedAt: null,
    resolvedAt: null,
    durationSec: null,
    cause: s.error ?? "HTTP 502",
    firstError: s.error ?? null,
    failingRegions: ["ap-south-1"],
    timeline: [{ at: iso(started), event: "opened", detail: "HTTP 502 (ap-south-1)" }],
  };
}

const resolvedIncidents: Incident[] = [
  {
    productId: "01JMERIDIAN",
    productName: "Meridian",
    sk: "INC#2026-10-21T04:10:00Z#01JOLD1",
    id: "01JOLD1",
    state: "RESOLVED",
    startedAt: "2026-10-21T04:10:00Z",
    acknowledgedAt: "2026-10-21T04:12:30Z",
    resolvedAt: "2026-10-21T04:18:00Z",
    durationSec: 480,
    cause: "Timeout after 10000 ms",
    firstError: "Timeout after 10000 ms",
    failingRegions: ["ap-south-1"],
    timeline: [],
  },
];

function product(s: Seed): Product {
  const sum = summary(s);
  return {
    ...sum,
    checkUrl: `https://${s.name.toLowerCase().replace(/\s+/g, "")}.example/health`,
    method: "GET",
    expectedStatus: "200-399",
    keyword: null,
    timeoutMs: 10000,
    intervalMin: 1,
    latencyWarnMs: 2000,
    openAfter: s.id === "01JDEMO" ? 1 : 2,
    resolveAfter: s.id === "01JDEMO" ? 1 : 2,
    sloTarget: 99.5,
    githubUrl: `https://github.com/JeyaViknan/${s.id.toLowerCase()}`,
    stack: s.stack,
    createdAt: "2026-10-01T00:00:00Z",
    updatedAt: "2026-10-23T00:00:00Z",
    regions: { "ap-south-1": { ok: !s.error, at: iso(now() - 23_000), latencyMs: s.latency, httpCode: s.error ? 502 : 200, error: s.error ?? null } },
    openIncidentSk: s.status === "DOWN" ? incident(s).sk : null,
    recentLatencies: Array.from({ length: 60 }, () => Math.round(s.latency * (0.8 + rand() * 0.5))),
    certExpiresAt: "2027-01-12T00:00:00Z",
  };
}

function detail(s: Seed): ProductDetail {
  const down = s.status === "DOWN";
  return {
    product: product(s),
    stats: {
      uptime24h: down ? 97.92 : s.status === "DEGRADED" ? 99.65 : 100,
      uptime7d: down ? 99.7 : 99.94,
      uptime30d: summary(s).uptime30d,
      avgLatency24h: s.latency,
      p95Latency1h: Math.round(s.latency * 1.4),
      sloTarget: 99.5,
      errorBudget: down
        ? { budgetMin: 216, consumedMin: 254, remainingMin: -38, remainingRatio: -0.18, monitoredMin: 43200 }
        : { budgetMin: 216, consumedMin: 9, remainingMin: 207, remainingRatio: 0.96, monitoredMin: 43200 },
    },
    openIncident: down ? incident(s) : null,
  };
}

function series(s: Seed, range: string): SeriesPoint[] {
  const n = range === "24h" ? 288 : range === "7d" ? 168 : 30;
  const step = range === "24h" ? 5 * MIN : range === "7d" ? 60 * MIN : 24 * 60 * MIN;
  return Array.from({ length: n }, (_, i) => {
    const failed = s.status === "DOWN" && range === "24h" && i > n - 4;
    const uptime = failed ? 0.4 : range === "30d" && s.status !== "UP" && i % 9 === 0 ? 0.985 : 1;
    const lat = Math.round(s.latency * (0.7 + rand() * 0.6) + (i % 48 === 0 ? s.latency : 0));
    return { t: iso(now() - (n - 1 - i) * step), uptime, latAvg: lat, latMax: Math.round(lat * 1.6) };
  });
}

function checks(s: Seed): CheckRow[] {
  return Array.from({ length: 20 }, (_, i) => ({
    at: iso(now() - i * MIN - 23_000),
    region: "ap-south-1",
    ok: !(s.error && i < 3),
    httpCode: s.error && i < 3 ? 502 : 200,
    latencyMs: Math.round(s.latency * (0.8 + rand() * 0.4)),
    error: s.error && i < 3 ? s.error : null,
    manual: i === 5,
  }));
}

function json(body: unknown, status = 200): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function find(id: string): Seed | undefined {
  return SEEDS.find((s) => s.id === id);
}

function route(method: string, path: string, query: URLSearchParams): Response {
  const parts = path.split("/").filter(Boolean); // ["products", id, ...]
  if (path === "/health") return json({ status: "ok", version: "mock", time: iso(now()) });
  if (path === "/auth/login") return json({ token: "mock-token", expiresAt: iso(now() + 30 * 24 * 60 * MIN) });
  if (path === "/summary") {
    const count = (st: Status) => SEEDS.filter((s) => s.status === st).length;
    const down = count("DOWN");
    return json({
      up: count("UP"),
      degraded: count("DEGRADED"),
      down,
      paused: count("PAUSED"),
      unknown: count("UNKNOWN"),
      total: SEEDS.length,
      state: down ? "down" : count("DEGRADED") ? "degraded" : "operational",
      label: down ? `${down} product${down === 1 ? "" : "s"} down` : "All systems operational",
    });
  }
  if (path === "/products" && method === "GET") {
    const kind = query.get("kind");
    return json(SEEDS.filter((s) => !kind || s.kind === kind).map(summary));
  }
  if (path === "/products" && method === "POST") return json(product(SEEDS[0] as Seed), 201);
  if (parts[0] === "products" && parts[1]) {
    const s = find(parts[1]);
    if (!s) return json({ error: { code: "not_found", message: "product not found" } }, 404);
    const sub = parts[2];
    if (!sub && method === "GET") return json(detail(s));
    if (!sub && method === "PATCH") return json(product(s));
    if (!sub && method === "DELETE") return json(null, 204);
    if (sub === "series") return json({ range: query.get("range") ?? "24h", points: series(s, query.get("range") ?? "24h") });
    if (sub === "checks") return json(checks(s));
    if (sub === "incidents" && parts[4] === "ack") return json({ ...incident(s), state: "ACKNOWLEDGED" });
    if (sub === "incidents") return json(s.status === "DOWN" ? [incident(s), ...resolvedIncidents] : resolvedIncidents.filter((i) => i.productId === s.id));
    if (sub === "test")
      return json({ productId: s.id, ok: !s.error, httpCode: s.error ? 502 : 200, latencyMs: s.latency, error: s.error ?? null, keywordOk: null, checkedAt: iso(now()), region: "ap-south-1" });
    if (sub === "pause" || sub === "resume") return json(product(s));
  }
  if (path === "/incidents") {
    const open = SEEDS.filter((s) => s.status === "DOWN").map(incident);
    return json(query.get("state") === "open" ? open : [...open, ...resolvedIncidents]);
  }
  if (path === "/settings" && method === "GET") {
    const body: SettingsResponse = {
      settings: { quorum: null, pushEnabled: true, emailEnabled: true, pagerdutyEnabled: true },
      channels: { pushDevices: 1, email: true, pagerduty: true, vapid: true, healthchecks: true },
      demo: demoBroken ? "broken" : "healthy",
      version: "mock",
      region: "ap-south-1",
    };
    return json(body);
  }
  if (path === "/settings" && method === "PATCH") return json({ quorum: null, pushEnabled: true, emailEnabled: true, pagerdutyEnabled: true });
  if (path === "/demo/break" || path === "/demo/fix") {
    demoBroken = path === "/demo/break";
    return json({ healthy: !demoBroken });
  }
  if (path === "/notifications/test") return json({ queued: true }, 202);
  if (path === "/push/subscriptions") return json({ subscribed: true }, method === "DELETE" ? 204 : 201);
  return json({ error: { code: "not_found", message: "no such route" } }, 404);
}

export function installMockApi(): void {
  const realFetch = window.fetch.bind(window);
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(typeof input === "string" ? input : input instanceof URL ? input.href : input.url, window.location.origin);
    if (!url.pathname.startsWith("/api/")) return realFetch(input, init);
    await new Promise((r) => setTimeout(r, 120));
    return route((init?.method ?? "GET").toUpperCase(), url.pathname.slice(4), url.searchParams);
  };
  console.info("[beacon] mock API installed");
}
