import { STATUS } from "../lib/status";
import type { Status } from "../lib/types";
import { StatusIcon } from "./Icons";

export function StatusBadge({ status, size = "sm" }: { status: Status; size?: "sm" | "lg" }) {
  const meta = STATUS[status];
  return (
    <span
      className={`inline-flex items-center gap-1.5 font-semibold ${size === "lg" ? "text-lg" : "text-sm"}`}
      style={{ color: meta.ink }}
      data-status={status}
    >
      <StatusIcon status={status} className={size === "lg" ? "h-5 w-5" : "h-4 w-4"} />
      {meta.label}
    </span>
  );
}

export function KindBadge({ kind }: { kind: "personal" | "client" }) {
  return (
    <span className="rounded-full border border-line px-2 py-0.5 text-[11px] font-medium tracking-wide text-muted uppercase">
      {kind === "client" ? "Client work" : "Personal"}
    </span>
  );
}
