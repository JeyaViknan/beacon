import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { DailyBars, LatencyChart } from "../components/Charts";
import { Button, ErrorNote, Skeleton } from "../components/Feedback";
import { Icon } from "../components/Icon";
import { IncidentRow } from "../components/IncidentRow";
import { ConfirmDialog, GlassButton, Screen } from "../components/Layout";
import { Row, RowButton, RowExternal, Section } from "../components/List";
import { RelativeTime } from "../components/RelativeTime";
import { StatusBadge } from "../components/StatusBadge";
import { tapFeedback } from "../lib/platform";
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
import { formatDayIST, formatIST, formatTimeIST, since } from "../lib/time";
import type { CheckResult, Incident, Product, ProductDetail } from "../lib/types";
import type { SymbolName } from "../symbols/names";

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
  // Set by the Add product form: check the new product at once instead of waiting for the probe.
  const justAdded = (useLocation().state as { justAdded?: boolean } | null)?.justAdded === true;

  return (
    <Screen title={p?.name ?? "Product"} back="/" trailing={p ? <GlassButton label="Edit" text="Edit" to={`/p/${id}/edit`} /> : null}>
      {detail.isError ? <ErrorNote error={detail.error} /> : null}
      {detail.isPending ? <Skeleton className="h-64 w-full rounded-[26px]" /> : null}
      {detail.data ? <Detail detail={detail.data} justAdded={justAdded} /> : null}
    </Screen>
  );
}

function Detail({ detail, justAdded }: { detail: ProductDetail; justAdded: boolean }) {
  const { product: p, stats, openIncident } = detail;
  const now = useNow(10_000);
  return (
    <div className="space-y-7">
      <section className="-mt-2 space-y-1 px-1">
        <StatusBadge status={p.status} size="lg" />
        <p className="text-subhead text-label-2">
          {p.statusSince ? <span className="tabular">for {since(p.statusSince, now)} · </span> : null}
          {p.kind === "client" ? "Client work" : "Personal"}
        </p>
        {p.lastError && (p.status === "DOWN" || p.status === "DEGRADED") ? (
          <p className="text-subhead" style={{ color: "var(--red-ink)" }}>
            {p.lastError}
          </p>
        ) : null}
      </section>

      {openIncident ? <IncidentBanner incident={openIncident} /> : null}

      <Actions product={p} justAdded={justAdded} />

      <Section header="Uptime">
        <div className="p-4">
          <dl className="grid grid-cols-3 gap-y-4">
            <Stat label="24 hours" value={formatUptime(stats.uptime24h)} />
            <Stat label="7 days" value={formatUptime(stats.uptime7d)} />
            <Stat label="30 days" value={formatUptime(stats.uptime30d)} />
            <Stat label="Average, 24 h" value={formatLatency(stats.avgLatency24h)} />
            <Stat label="p95, last hour" value={formatLatency(stats.p95Latency1h)} />
            <Stat label="SLO target" value={`${stats.sloTarget}%`} />
          </dl>
          <ErrorBudget detail={detail} />
        </div>
      </Section>

      <ResponseTime id={p.id} />
      <ThirtyDays id={p.id} />
      <IncidentHistory id={p.id} />
      <RecentChecks id={p.id} />
      <Details product={p} />
      <DangerZone product={p} />
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <dt className="text-caption text-label-2">{label}</dt>
      <dd className="text-title3 tabular">{value}</dd>
    </div>
  );
}

function ErrorBudget({ detail }: { detail: ProductDetail }) {
  const b = detail.stats.errorBudget;
  if (b.monitoredMin <= 0) {
    return <p className="mt-4 text-footnote text-label-2">The error budget appears after the first checks.</p>;
  }
  const ratio = b.remainingRatio ?? 0;
  const clamped = Math.max(0, Math.min(1, ratio));
  const color = ratio <= 0 ? "var(--red)" : ratio < 0.25 ? "var(--orange)" : "var(--green)";
  return (
    <div className="mt-4 border-t-[0.5px] border-separator pt-3.5">
      <div className="flex items-baseline justify-between">
        <p className="text-subhead">Error budget, 30 days</p>
        <p className="text-subhead text-label-2 tabular">
          {ratio > 0
            ? `${b.remainingMin.toFixed(1)} of ${b.budgetMin.toFixed(1)} min left`
            : `Over by ${Math.abs(b.remainingMin).toFixed(1)} min`}
        </p>
      </div>
      <div
        className="mt-2 h-1.5 overflow-hidden rounded-full bg-fill-3"
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(clamped * 100)}
        aria-label="Error budget remaining"
      >
        <div className="h-full rounded-full" style={{ width: `${clamped * 100}%`, background: color }} />
      </div>
      {ratio <= 0 ? (
        <p className="mt-2 text-footnote" style={{ color: "var(--red-ink)" }}>
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
    <section className="rounded-[26px] bg-cell p-4" aria-label="Open incident">
      <div className="flex items-center gap-2 text-headline">
        <span style={{ color: acked ? "var(--orange)" : "var(--red)" }}>
          <Icon name={acked ? "exclamationmark.triangle.fill" : "xmark.circle.fill"} className="size-7" />
        </span>
        {acked ? "Incident Acknowledged" : "Incident Open"}
      </div>
      <p className="mt-2 text-body">{incident.cause}</p>
      <p className="mt-1 text-footnote text-label-2">
        Started {formatIST(incident.startedAt)} · down for <span className="tabular">{since(incident.startedAt, now)}</span>
      </p>
      {acked ? null : (
        <Button
          tone="prominent"
          className="mt-4 w-full"
          disabled={ack.isPending}
          onClick={() => {
            void tapFeedback("medium");
            ack.mutate(incident.id);
          }}
        >
          {ack.isPending ? "Acknowledging…" : "Acknowledge"}
        </Button>
      )}
      {ack.isError ? <p className="mt-2 text-footnote text-red">{ack.error.message}</p> : null}
    </section>
  );
}

function ActionTile({
  symbol,
  label,
  onClick,
  disabled,
}: {
  symbol: SymbolName;
  label: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="flex h-[68px] flex-col items-center justify-center gap-0.5 rounded-[18px] bg-cell text-tint active:bg-[var(--cell-pressed)] disabled:opacity-40"
    >
      <Icon name={symbol} className="size-8" />
      <span className="text-footnote font-semibold">{label}</span>
    </button>
  );
}

function Actions({ product, justAdded }: { product: Product; justAdded: boolean }) {
  const test = useTestNow(product.id);
  const toggle = usePauseResume(product.id);
  const autoTested = useRef(false);
  useEffect(() => {
    if (justAdded && !autoTested.current) {
      autoTested.current = true;
      test.mutate();
    }
  }, [justAdded, test]);
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <ActionTile
          symbol="bolt.fill"
          label={test.isPending ? "Checking…" : "Test Now"}
          disabled={test.isPending}
          onClick={() => {
            void tapFeedback();
            test.mutate();
          }}
        />
        <ActionTile
          symbol={product.enabled ? "pause.fill" : "play.fill"}
          label={product.enabled ? "Pause" : "Resume"}
          disabled={toggle.isPending}
          onClick={() => toggle.mutate(product.enabled ? "pause" : "resume")}
        />
      </div>
      {test.data ? <TestResult result={test.data} /> : null}
      {test.isError ? <ErrorNote error={test.error} /> : null}
      {justAdded ? (
        <p className="px-4 text-footnote text-label-2">
          Added. Beacon checks it every {product.intervalMin === 1 ? "minute" : `${product.intervalMin} minutes`} from
          now on and alerts you if it goes down.
        </p>
      ) : null}
      {toggle.isError ? <ErrorNote error={toggle.error} /> : null}
    </div>
  );
}

function TestResult({ result }: { result: CheckResult }) {
  return (
    <div className="list" role="status">
      <Row
        symbol={{ name: result.ok ? "checkmark.circle.fill" : "xmark.circle.fill", color: result.ok ? "var(--green)" : "var(--red)" }}
        title={result.ok ? `OK · HTTP ${result.httpCode}` : (result.error ?? "Failed")}
        value={formatLatency(result.latencyMs)}
      />
    </div>
  );
}

function ResponseTime({ id }: { id: string }) {
  const series = useSeries(id, "24h");
  return (
    <Section header="Response time · 24 hours">
      <div className="px-3 pt-4 pb-3">
        {series.data ? <LatencyChart points={series.data.points} /> : <Skeleton className="h-48 w-full" />}
      </div>
    </Section>
  );
}

function ThirtyDays({ id }: { id: string }) {
  const series = useSeries(id, "30d");
  return (
    <Section header="Daily uptime · 30 days">
      <div className="p-4">{series.data ? <DailyBars points={series.data.points} /> : <Skeleton className="h-10 w-full" />}</div>
    </Section>
  );
}

function IncidentHistory({ id }: { id: string }) {
  const incidents = useProductIncidents(id);
  return (
    <Section header="Incidents">
      {incidents.data && incidents.data.length === 0 ? (
        <Row title={<span className="text-label-2">No incidents</span>} />
      ) : (
        <ul>{incidents.data?.map((i) => <IncidentRow key={i.sk} incident={i} />)}</ul>
      )}
    </Section>
  );
}

function RecentChecks({ id }: { id: string }) {
  const checks = useChecks(id);
  return (
    <Section header="Recent checks">
      {checks.data?.length === 0 ? <Row title={<span className="text-label-2">No checks yet</span>} /> : null}
      {checks.data?.map((c) => (
        <Row
          key={`${c.at}-${c.region}-${c.manual}`}
          symbol={{ name: c.ok ? "checkmark.circle.fill" : "xmark.circle.fill", color: c.ok ? "var(--green)" : "var(--red)" }}
          title={c.ok ? `HTTP ${c.httpCode}` : (c.error ?? "Failed")}
          subtitle={
            <span className="tabular" title={formatIST(c.at)}>
              {formatTimeIST(c.at)} · {c.region}
              {c.manual ? " · manual" : ""}
            </span>
          }
          value={formatLatency(c.latencyMs)}
        />
      ))}
    </Section>
  );
}

function Details({ product: p }: { product: Product }) {
  const regions = Object.entries(p.regions);
  return (
    <>
      <Section header="Check">
        <Row title="Link" subtitle={<span className="break-all">{`${p.method} ${p.checkUrl}`}</span>} />
        <Row title="Expect" value={`HTTP ${p.expectedStatus}${p.keyword ? ` · “${p.keyword}”` : ""}`} />
        <Row title="Every" value={p.intervalMin === 1 ? "1 minute" : `${p.intervalMin} minutes`} />
        <Row title="Timeout" value={`${p.timeoutMs / 1000} s`} />
        <Row title="Slow over" value={formatLatency(p.latencyWarnMs)} />
        <Row title="Alerts" subtitle={`Down after ${p.openAfter} failed checks, recovered after ${p.resolveAfter} passed.`} />
        {p.certExpiresAt ? <Row title="TLS certificate" value={`Expires ${formatDayIST(p.certExpiresAt)}`} /> : null}
      </Section>

      {regions.length ? (
        <Section header="Regions">
          {regions.map(([region, r]) => (
            <Row
              key={region}
              symbol={{ name: r.ok ? "checkmark.circle.fill" : "xmark.circle.fill", color: r.ok ? "var(--green)" : "var(--red)" }}
              title={region}
              value={<RelativeTime iso={r.at} />}
            />
          ))}
        </Section>
      ) : null}

      {p.note || p.stack.length ? (
        <Section header="About">
          {p.note ? <Row title={<span className="text-body">{p.note}</span>} /> : null}
          {p.stack.length ? (
            <div className="px-4 py-3">
              <ul className="flex flex-wrap gap-1.5" aria-label="Stack">
                {p.stack.map((s) => (
                  <li key={s} className="rounded-full bg-fill-3 px-2.5 py-1 text-footnote">
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </Section>
      ) : null}

      {p.liveUrl || p.githubUrl ? (
        <Section>
          {p.liveUrl ? <RowExternal href={p.liveUrl} tile={{ name: "globe", color: "var(--blue)" }} title="Open Live Site" /> : null}
          {p.githubUrl ? (
            <RowExternal href={p.githubUrl} tile={{ name: "chevron.left.forwardslash.chevron.right", color: "var(--gray)" }} title="GitHub" />
          ) : null}
        </Section>
      ) : null}
    </>
  );
}

function DangerZone({ product }: { product: Product }) {
  const navigate = useNavigate();
  const del = useDeleteProduct(product.id);
  const [confirming, setConfirming] = useState(false);
  return (
    <section>
      <div className="list">
        <RowButton title="Delete Product" tone="destructive" center onClick={() => setConfirming(true)} />
      </div>
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
