import { STATUS } from "../lib/status";
import type { Status } from "../lib/types";
import { Icon } from "./Icon";

/** Status as symbol + text (never colour alone). */
export function StatusBadge({ status, size = "sm" }: { status: Status; size?: "sm" | "lg" }) {
  const meta = STATUS[status];
  return (
    <span
      className={`inline-flex items-center gap-1 font-semibold ${size === "lg" ? "text-title3" : "text-subhead"}`}
      style={{ color: meta.ink }}
      data-status={status}
    >
      <span style={{ color: meta.color }}>
        <Icon name={meta.symbol} className={size === "lg" ? "size-9" : "size-6"} />
      </span>
      {meta.label}
    </span>
  );
}
