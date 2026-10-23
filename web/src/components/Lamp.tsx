import type { Summary } from "../lib/types";

/** Beacon's signature: a lamp whose beam sweeps in the overall status colour. */
export function Lamp({ state }: { state: Summary["state"] | "unknown" }) {
  return <div className="lamp" data-state={state} aria-hidden="true" />;
}
