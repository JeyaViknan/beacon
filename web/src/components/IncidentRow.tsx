import { Link } from "react-router-dom";
import { formatDuration, formatIST, since } from "../lib/time";
import type { Incident } from "../lib/types";
import { StatusIcon } from "./Icons";

const INCIDENT_STATE = {
  OPEN: { label: "Open", status: "DOWN", ink: "var(--down-ink)" },
  ACKNOWLEDGED: { label: "Acknowledged", status: "DEGRADED", ink: "var(--degraded-ink)" },
  RESOLVED: { label: "Resolved", status: "UP", ink: "var(--up-ink)" },
} as const;

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
      <span className="mt-0.5" style={{ color: meta.ink }}>
        <StatusIcon status={meta.status} />
      </span>
      <div className="min-w-0 flex-1">
        {showProduct ? <p className="truncate font-semibold">{incident.productName || "Deleted product"}</p> : null}
        <p className="truncate font-mono text-sm">{incident.cause}</p>
        <p className="text-xs text-muted">
          {formatIST(incident.startedAt)} · {duration}
        </p>
      </div>
      <span className="self-start text-xs font-semibold" style={{ color: meta.ink }}>
        {meta.label}
      </span>
    </>
  );
  return (
    <li className="border-b border-line last:border-b-0">
      {to ? (
        <Link to={to} className="flex min-h-11 gap-3 py-3">
          {body}
        </Link>
      ) : (
        <div className="flex gap-3 py-3">{body}</div>
      )}
    </li>
  );
}
