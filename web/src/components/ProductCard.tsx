import { Link } from "react-router-dom";
import { STATUS, formatLatency, formatUptime } from "../lib/status";
import type { ProductSummary } from "../lib/types";
import { RelativeTime } from "./RelativeTime";
import { KindBadge, StatusBadge } from "./StatusBadge";
import { Strip24h } from "./Strip24h";

export function ProductCard({ product }: { product: ProductSummary }) {
  const meta = STATUS[product.status];
  const failing = product.status === "DOWN" || product.status === "DEGRADED";
  return (
    <li>
      <Link
        to={`/p/${product.id}`}
        className="block rounded-2xl border border-line bg-surface p-4 transition-colors active:bg-surface-2"
        style={{ boxShadow: `inset 3px 0 0 ${meta.color}` }}
        aria-label={`${product.name}: ${meta.label}`}
      >
        <div className="flex items-center justify-between gap-3">
          <StatusBadge status={product.status} />
          <KindBadge kind={product.kind} />
        </div>
        <h3 className="mt-2 truncate text-[17px] font-semibold">{product.name}</h3>
        {failing && product.lastError ? (
          <p className="mt-0.5 truncate font-mono text-sm" style={{ color: meta.ink }}>
            {product.lastError}
          </p>
        ) : null}
        {product.note ? <p className="mt-0.5 truncate text-sm text-muted">{product.note}</p> : null}
        <div className="mt-3">
          <Strip24h ratios={product.strip24h} />
        </div>
        <dl className="mt-3 flex items-center gap-x-4 font-mono text-[13px] tabular text-muted">
          <div className="flex items-baseline gap-1">
            <dt className="sr-only">Uptime 30 days</dt>
            <dd className="text-text">{formatUptime(product.uptime30d)}</dd>
            <span aria-hidden="true">30d</span>
          </div>
          <div>
            <dt className="sr-only">Last latency</dt>
            <dd>{formatLatency(product.lastLatencyMs)}</dd>
          </div>
          <div className="ml-auto">
            <dt className="sr-only">Last checked</dt>
            <dd>
              <RelativeTime iso={product.lastCheckAt} prefix="checked " />
            </dd>
          </div>
        </dl>
      </Link>
    </li>
  );
}
