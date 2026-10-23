import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { DailyBars, LatencyChart } from "../components/Charts";
import { Button, Card, ErrorNote, SectionTitle, Skeleton } from "../components/Feedback";
import { ExternalIcon, StatusIcon } from "../components/Icons";
import { IncidentRow } from "../components/IncidentRow";
import { ConfirmDialog, PageHeader } from "../components/Layout";
import { RelativeTime } from "../components/RelativeTime";
import { KindBadge, StatusBadge } from "../components/StatusBadge";
import {
  useAcknowledge,
  useChecks,
  useDeleteProduct,
  usePauseResume,
  useProduct,
  useProductIncidents,
  useSeries,
  useTestNow,
} from "../lib/queries";
import { formatLatency, formatUptime } from "../lib/status";
import { formatIST, formatTimeIST, since } from "../lib/time";
import type { CheckResult, Incident, Product, ProductDetail } from "../lib/types";

function useNow(intervalMs = 1000): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = window.setInterval(() => setNow(new Date()), intervalMs);
    return () => window.clearInterval(t);
  }, [intervalMs]);
  return now;
}

export default function ProductPage() {
  const { id = "" } = useParams();
  const detail = useProduct(id);
  const p = detail.data?.product;

  return (
    <div className="space-y-5">
      <PageHeader
        title={p?.name ?? "Product"}
        back="/"
        actions={
          p ? (
            <Link to={`/p/${id}/edit`} className="flex min-h-11 items-center px-2 font-semibold text-muted">
              Edit
            </Link>
          ) : null
        }
      />
      {detail.isError ? <ErrorNote error={detail.error} /> : null}
      {detail.isPending ? <Skeleton className="h-64 w-full rounded-2xl" /> : null}
      {detail.data ? <Detail detail={detail.data} /> : null}
    </div>
  );
}

function Detail({ detail }: { detail: ProductDetail }) {
  const { product: p, stats, openIncident } = detail;
  const now = useNow(10_000);
  return (
    <>
      <section className="space-y-2 px-1">
        <div className="flex items-center gap-3">
          <StatusBadge status={p.status} size="lg" />
          <KindBadge kind={p.kind} />
        </div>
        {p.statusSince ? (
          <p className="font-mono text-sm tabular text-muted">since {since(p.statusSince, now)}</p>
        ) : null}
        {p.lastError && (p.status === "DOWN" || p.status === "DEGRADED") ? (
          <p className="font-mono text-sm" style={{ color: "var(--down-ink)" }}>
            Last error: {p.lastError}
          </p>
        ) : null}
      </section>

      {openIncident ? <IncidentBanner incident={openIncident} /> : null}

      <Actions product={p} />

      <Card>
        <dl className="grid grid-cols-3 gap-y-4">
          <Stat label="Uptime 24h" value={formatUptime(stats.uptime24h)} />
          <Stat label="7 days" value={formatUptime(stats.uptime7d)} />
          <Stat label="30 days" value={formatUptime(stats.uptime30d)} />
          <Stat label="Avg latency 24h" value={formatLatency(stats.avgLatency24h)} />
          <Stat label="p95 last hour" value={formatLatency(stats.p95Latency1h)} />
          <Stat label="SLO target" value={`${stats.sloTarget}%`} />
        </dl>
        <ErrorBudgetBar detail={detail} />
      </Card>

      <ResponseTime id={p.id} />
      <ThirtyDays id={p.id} />
      <IncidentHistory id={p.id} />
      <RecentChecks id={p.id} />
      <Info product={p} />
      <DangerZone product={p} />
    </>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="font-display text-lg font-bold tabular">{value}</dd>
    </div>
  );
}

function ErrorBudgetBar({ detail }: { detail: ProductDetail }) {
  const b = detail.stats.errorBudget;
  if (b.monitoredMin <= 0) {
    return <p className="mt-4 text-sm text-muted">Error budget appears after the first checks.</p>;
  }
  const ratio = b.remainingRatio ?? 0;
  const clamped = Math.max(0, Math.min(1, ratio));
  const color = ratio <= 0 ? "var(--down)" : ratio < 0.25 ? "var(--degraded)" : "var(--up)";
  return (
    <div className="mt-4 border-t border-line pt-3">
      <p className="text-xs text-muted">Error budget · 30 days</p>
      <p className="mt-0.5 font-mono text-sm tabular">
        {ratio > 0
          ? `${b.remainingMin.toFixed(1)} of ${b.budgetMin.toFixed(1)} min left`
          : `Over by ${Math.abs(b.remainingMin).toFixed(1)} min (budget ${b.budgetMin.toFixed(1)})`}
      </p>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface-2" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(clamped * 100)} aria-label="Error budget remaining">
        <div className="h-full rounded-full" style={{ width: `${clamped * 100}%`, background: color }} />
      </div>
      {ratio <= 0 ? (
        <p className="mt-2 text-sm" style={{ color: "var(--down-ink)" }}>
          {b.consumedMin} min down in 30 days against a {detail.stats.sloTarget}% target.
        </p>
      ) : null}
    </div>
  );
}

function IncidentBanner({ incident }: { incident: Incident }) {
  const ack = useAcknowledge(incident.productId);
  const now = useNow(1000);
  const acked = incident.state === "ACKNOWLEDGED";
  return (
    <section
      className="rounded-2xl border p-4"
      style={{ borderColor: "color-mix(in oklab, var(--down) 50%, transparent)", background: "color-mix(in oklab, var(--down) 10%, transparent)" }}
      aria-label="Open incident"
    >
      <div className="flex items-center gap-2 font-semibold" style={{ color: "var(--down-ink)" }}>
        <StatusIcon status="DOWN" />
        {acked ? "Incident acknowledged" : "Incident open"}
      </div>
      <p className="mt-2 font-mono text-[15px]">{incident.cause}</p>
      <p className="mt-1 text-sm text-muted">
        Started {formatIST(incident.startedAt)} · down for{" "}
        <span className="font-mono tabular text-text">{since(incident.startedAt, now)}</span>
      </p>
      {acked ? null : (
        <Button tone="primary" className="mt-3 w-full" disabled={ack.isPending} onClick={() => ack.mutate(incident.id)}>
          {ack.isPending ? "Acknowledging…" : "Acknowledge"}
        </Button>
      )}
      {ack.isError ? <p className="mt-2 text-sm">{ack.error.message}</p> : null}
    </section>
  );
}

function Actions({ product }: { product: Product }) {
  const test = useTestNow(product.id);
  const toggle = usePauseResume(product.id);
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <Button onClick={() => test.mutate()} disabled={test.isPending}>
          {test.isPending ? "Checking…" : "Test now"}
        </Button>
        <Button onClick={() => toggle.mutate(product.enabled ? "pause" : "resume")} disabled={toggle.isPending}>
          {product.enabled ? "Pause" : "Resume"}
        </Button>
      </div>
      {test.data ? <TestResult result={test.data} /> : null}
      {test.isError ? <ErrorNote error={test.error} /> : null}
      {toggle.isError ? <ErrorNote error={toggle.error} /> : null}
    </div>
  );
}

function TestResult({ result }: { result: CheckResult }) {
  return (
    <p className="flex items-center gap-2 rounded-xl border border-line bg-surface px-3 py-2 font-mono text-sm" role="status">
      <StatusIcon status={result.ok ? "UP" : "DOWN"} />
      <span style={{ color: result.ok ? "var(--up-ink)" : "var(--down-ink)" }}>
        {result.ok ? `OK · HTTP ${result.httpCode}` : result.error}
      </span>
      <span className="ml-auto text-muted">{formatLatency(result.latencyMs)}</span>
    </p>
  );
}

function ResponseTime({ id }: { id: string }) {
  const series = useSeries(id, "24h");
  return (
    <section>
      <SectionTitle>Response time · 24 hours</SectionTitle>
      <Card>{series.data ? <LatencyChart points={series.data.points} /> : <Skeleton className="h-44 w-full" />}</Card>
    </section>
  );
}

function ThirtyDays({ id }: { id: string }) {
  const series = useSeries(id, "30d");
  return (
    <section>
      <SectionTitle>Daily uptime · 30 days</SectionTitle>
      <Card>{series.data ? <DailyBars points={series.data.points} /> : <Skeleton className="h-10 w-full" />}</Card>
    </section>
  );
}

function IncidentHistory({ id }: { id: string }) {
  const incidents = useProductIncidents(id);
  return (
    <section>
      <SectionTitle>Incidents</SectionTitle>
      <Card className="py-1">
        {incidents.data && incidents.data.length === 0 ? (
          <p className="py-3 text-sm text-muted">No incidents. Long may it last.</p>
        ) : (
          <ul>{incidents.data?.map((i) => <IncidentRow key={i.sk} incident={i} />)}</ul>
        )}
      </Card>
    </section>
  );
}

function RecentChecks({ id }: { id: string }) {
  const checks = useChecks(id);
  return (
    <section>
      <SectionTitle>Recent checks</SectionTitle>
      <Card className="overflow-x-auto p-0">
        <table className="w-full text-left font-mono text-[13px] tabular">
          <thead className="text-xs text-muted">
            <tr>
              <th className="px-4 py-2 font-medium">IST</th>
              <th className="py-2 font-medium">Result</th>
              <th className="py-2 pr-4 text-right font-medium">Latency</th>
            </tr>
          </thead>
          <tbody>
            {checks.data?.map((c) => (
              <tr key={`${c.at}-${c.region}-${c.manual}`} className="border-t border-line">
                <td className="px-4 py-2 whitespace-nowrap" title={formatIST(c.at)}>
                  {formatTimeIST(c.at)}
                  <span className="block text-[11px] text-muted">
                    {c.region}
                    {c.manual ? " · manual" : ""}
                  </span>
                </td>
                <td className="py-2" style={{ color: c.ok ? "var(--up-ink)" : "var(--down-ink)" }}>
                  <span className="inline-flex items-center gap-1">
                    <StatusIcon status={c.ok ? "UP" : "DOWN"} className="h-3.5 w-3.5" />
                    {c.ok ? c.httpCode : (c.error ?? "failed")}
                  </span>
                </td>
                <td className="py-2 pr-4 text-right">{formatLatency(c.latencyMs)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {checks.data?.length === 0 ? <p className="px-4 pb-3 text-sm text-muted">No checks yet.</p> : null}
      </Card>
    </section>
  );
}

function Info({ product: p }: { product: Product }) {
  const regions = Object.entries(p.regions);
  return (
    <section>
      <SectionTitle>About</SectionTitle>
      <Card className="space-y-4">
        {p.note ? <p className="text-[15px] leading-relaxed">{p.note}</p> : null}
        <div className="flex flex-wrap gap-2">
          {p.liveUrl ? <LinkOut href={p.liveUrl} label="Open live site" /> : null}
          {p.githubUrl ? <LinkOut href={p.githubUrl} label="GitHub" /> : null}
        </div>
        {p.stack.length ? (
          <ul className="flex flex-wrap gap-1.5" aria-label="Stack">
            {p.stack.map((s) => (
              <li key={s} className="rounded-full bg-surface-2 px-2.5 py-1 text-xs font-medium">
                {s}
              </li>
            ))}
          </ul>
        ) : null}
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 border-t border-line pt-3 text-sm">
          <dt className="text-muted">Checks</dt>
          <dd className="break-all font-mono">
            {p.method} {p.checkUrl}
          </dd>
          <dt className="text-muted">Expect</dt>
          <dd className="font-mono">
            HTTP {p.expectedStatus}
            {p.keyword ? ` · contains “${p.keyword}”` : ""}
          </dd>
          <dt className="text-muted">Every</dt>
          <dd>
            {p.intervalMin} min · timeout {p.timeoutMs / 1000} s · slow over {formatLatency(p.latencyWarnMs)}
          </dd>
          <dt className="text-muted">Alerts</dt>
          <dd>
            down after {p.openAfter} failed, recovered after {p.resolveAfter} passed
          </dd>
          {p.certExpiresAt ? (
            <>
              <dt className="text-muted">TLS cert</dt>
              <dd>expires {formatIST(p.certExpiresAt)}</dd>
            </>
          ) : null}
          {regions.length ? (
            <>
              <dt className="text-muted">Regions</dt>
              <dd className="space-y-0.5">
                {regions.map(([region, r]) => (
                  <div key={region} className="flex items-center gap-1.5 font-mono text-[13px]">
                    <span style={{ color: r.ok ? "var(--up-ink)" : "var(--down-ink)" }}>
                      <StatusIcon status={r.ok ? "UP" : "DOWN"} className="h-3.5 w-3.5" />
                    </span>
                    {region} · <RelativeTime iso={r.at} />
                  </div>
                ))}
              </dd>
            </>
          ) : null}
        </dl>
      </Card>
    </section>
  );
}

function LinkOut({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer noopener"
      className="inline-flex min-h-11 items-center gap-1.5 rounded-xl border border-line px-3 text-sm font-semibold"
    >
      {label}
      <ExternalIcon className="h-4 w-4 text-muted" />
    </a>
  );
}

function DangerZone({ product }: { product: Product }) {
  const navigate = useNavigate();
  const del = useDeleteProduct(product.id);
  const [confirming, setConfirming] = useState(false);
  return (
    <section className="pb-4">
      <Button tone="danger" className="w-full" onClick={() => setConfirming(true)}>
        Delete product
      </Button>
      {del.isError ? <ErrorNote error={del.error} /> : null}
      {confirming ? (
        <ConfirmDialog
          title={`Delete ${product.name}?`}
          body="Beacon stops checking it immediately. Its history expires on its own; incidents stay in the feed."
          confirmLabel={del.isPending ? "Deleting…" : "Delete"}
          busy={del.isPending}
          onCancel={() => setConfirming(false)}
          onConfirm={() =>
            del.mutate(undefined, {
              onSuccess: () => navigate("/", { replace: true }),
            })
          }
        />
      ) : null}
    </section>
  );
}
