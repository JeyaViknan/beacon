import { Link } from "react-router-dom";
import { STATUS, formatLatency, formatUptime } from "../lib/status";
import type { ProductSummary } from "../lib/types";
import { Icon } from "./Icon";
import { RelativeTime } from "./RelativeTime";
import { Strip24h } from "./Strip24h";

/** One product in the Status list: symbol, name, 30-day uptime, latest result and the 24h strip. */
export function ProductRow({ product }: { product: ProductSummary }) {
  const meta = STATUS[product.status];
  const failing = product.status === "DOWN" || product.status === "DEGRADED";
  return (
    <li style={{ "--separator-inset": "56px" } as React.CSSProperties}>
      <Link to={`/p/${product.id}`} className="pressable flex gap-3 px-4 py-3" aria-label={`${product.name}: ${meta.label}`}>
        <span style={{ color: meta.color }}>
          <Icon name={meta.symbol} className="size-7" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2">
            <h3 className="min-w-0 flex-1 truncate text-headline">{product.name}</h3>
            <span className="text-subhead text-label-2 tabular">{formatUptime(product.uptime30d)}</span>
          </div>
          <p className="truncate text-subhead text-label-2">
            {failing && product.lastError ? (
              <span style={{ color: meta.ink }}>{product.lastError}</span>
            ) : (
              <span>
                {meta.label} · {formatLatency(product.lastLatencyMs)}
              </span>
            )}
            {" · "}
            <RelativeTime iso={product.lastCheckAt} />
          </p>
          <div className="mt-2.5">
            <Strip24h ratios={product.strip24h} />
          </div>
        </div>
        <span className="-mr-1 self-center text-label-3">
          <Icon name="chevron.right" className="size-5" />
        </span>
      </Link>
    </li>
  );
}
