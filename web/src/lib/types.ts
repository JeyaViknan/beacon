// Wire types for the Beacon API (HANDOVER §9). Times are UTC ISO-8601 strings.

export type Status = "UP" | "DEGRADED" | "DOWN" | "PAUSED" | "UNKNOWN";
export type Kind = "personal" | "client";
export type IncidentState = "OPEN" | "ACKNOWLEDGED" | "RESOLVED";

export interface ProductSummary {
  id: string;
  name: string;
  kind: Kind;
  note: string;
  status: Status;
  statusSince: string | null;
  enabled: boolean;
  lastCheckAt: string | null;
  lastLatencyMs: number | null;
  lastHttpCode: number | null;
  lastError: string | null;
  sortOrder: number;
  liveUrl: string | null;
  openIncident: boolean;
  uptime30d: number | null;
  strip24h: (number | null)[];
}

export interface Summary {
  up: number;
  degraded: number;
  down: number;
  paused: number;
  unknown: number;
  total: number;
  state: "operational" | "degraded" | "down";
  label: string;
}

export interface ProductInput {
  name: string;
  kind: Kind;
  note: string;
  checkUrl: string;
  method: "GET" | "HEAD";
  expectedStatus: string;
  keyword: string | null;
  timeoutMs: number;
  intervalMin: 1 | 5;
  latencyWarnMs: number;
  openAfter: number;
  resolveAfter: number;
  sloTarget: number;
  liveUrl: string | null;
  githubUrl: string | null;
  stack: string[];
  sortOrder: number;
}

export interface RegionState {
  ok: boolean;
  at: string;
  latencyMs: number | null;
  httpCode: number | null;
  error: string | null;
}

export interface Product extends ProductInput {
  id: string;
  enabled: boolean;
  createdAt: string;
  updatedAt: string;
  status: Status;
  statusSince: string | null;
  lastCheckAt: string | null;
  lastLatencyMs: number | null;
  lastHttpCode: number | null;
  lastError: string | null;
  regions: Record<string, RegionState>;
  openIncidentSk: string | null;
  recentLatencies: number[];
  certExpiresAt: string | null;
}

export interface TimelineEntry {
  at: string;
  event: string;
  detail: string | null;
}

export interface Incident {
  productId: string;
  productName: string;
  sk: string;
  id: string;
  state: IncidentState;
  startedAt: string;
  acknowledgedAt: string | null;
  resolvedAt: string | null;
  durationSec: number | null;
  cause: string;
  firstError: string | null;
  failingRegions: string[];
  timeline: TimelineEntry[];
}

export interface ErrorBudget {
  budgetMin: number;
  consumedMin: number;
  remainingMin: number;
  remainingRatio: number | null;
  monitoredMin: number;
}

export interface ProductDetail {
  product: Product;
  stats: {
    uptime24h: number | null;
    uptime7d: number | null;
    uptime30d: number | null;
    avgLatency24h: number | null;
    p95Latency1h: number | null;
    sloTarget: number;
    errorBudget: ErrorBudget;
  };
  openIncident: Incident | null;
}

export type Range = "24h" | "7d" | "30d";

export interface SeriesPoint {
  t: string;
  uptime: number | null;
  latAvg: number | null;
  latMax: number | null;
}

export interface CheckRow {
  at: string;
  region: string;
  ok: boolean;
  httpCode: number | null;
  latencyMs: number | null;
  error: string | null;
  manual: boolean;
}

export interface CheckResult {
  productId: string;
  ok: boolean;
  httpCode: number | null;
  latencyMs: number | null;
  error: string | null;
  keywordOk: boolean | null;
  checkedAt: string;
  region: string;
}

export interface SettingsResponse {
  settings: {
    quorum: number | null;
    pushEnabled: boolean;
    emailEnabled: boolean;
    pagerdutyEnabled: boolean;
  };
  channels: {
    pushDevices: number;
    email: boolean;
    pagerduty: boolean;
    vapid: boolean;
    healthchecks: boolean;
  };
  demo: "healthy" | "broken";
  version: string;
  region: string | null;
}

export interface Health {
  status: string;
  version: string;
  time: string;
}
