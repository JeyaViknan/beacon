import { Link } from "react-router-dom";
import { formatDuration, formatIST, since } from "../lib/time";
import type { Incident } from "../lib/types";
import type { SymbolName } from "../symbols/names";
import { Icon } from "./Icon";

const INCIDENT_STATE: Record<Incident["state"], { label: string; symbol: SymbolName; color: string; ink: string }> = {
  OPEN: { label: "Open", symbol: "xmark.circle.fill", color: "var(--red)", ink: "var(--red-ink)" },
  ACKNOWLEDGED: { label: "Acknowledged", symbol: "exclamationmark.triangle.fill", color: "var(--orange)", ink: "var(--orange-ink)" },
  RESOLVED: { label: "Resolved", symbol: "checkmark.circle.fill", color: "var(--green)", ink: "var(--green-ink)" },
};

export function IncidentRow({
  incident,
  showProduct = false,
  to,
}: {
  incident: Incident;
  showProduct?: boolean;
  to?: string;
}) {
  const meta = INCIDENT_STATE[incident.state];
  const duration =
    incident.durationSec !== null
      ? formatDuration(incident.durationSec)
      : `${since(incident.startedAt, new Date())} so far`;
  const body = (
    <>
      <span style={{ color: meta.color }}>
        <Icon name={meta.symbol} className="size-7" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <p className="min-w-0 flex-1 truncate text-headline">
            {showProduct ? incident.productName || "Deleted product" : incident.cause}
          </p>
          <span className="text-footnote font-semibold" style={{ color: meta.ink }}>
            {meta.label}
          </span>
        </div>
        {showProduct ? <p className="line-clamp-2 text-subhead text-label-2">{incident.cause}</p> : null}
        <p className="mt-0.5 text-footnote text-label-2 tabular">
          {formatIST(incident.startedAt)} · {duration}
        </p>
      </div>
      {to ? (
        <span className="-mr-1 self-center text-label-3">
          <Icon name="chevron.right" className="size-5" />
        </span>
      ) : null}
    </>
  );
  return (
    <li style={{ "--separator-inset": "56px" } as React.CSSProperties}>
      {to ? (
        <Link to={to} className="pressable flex gap-3 px-4 py-3">
          {body}
        </Link>
      ) : (
        <div className="flex gap-3 px-4 py-3">{body}</div>
      )}
    </li>
  );
}
