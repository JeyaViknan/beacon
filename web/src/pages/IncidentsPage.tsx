import { useState } from "react";
import { Card, ErrorNote, Skeleton } from "../components/Feedback";
import { IncidentRow } from "../components/IncidentRow";
import { PageHeader } from "../components/Layout";
import { useIncidentFeed } from "../lib/queries";

export default function IncidentsPage() {
  const [state, setState] = useState<"open" | "all">("open");
  const feed = useIncidentFeed(state);
  return (
    <div className="space-y-4">
      <PageHeader title="Incidents" />
      <div role="tablist" aria-label="Filter incidents" className="flex rounded-xl border border-line bg-surface p-1">
        {(["open", "all"] as const).map((s) => (
          <button
            key={s}
            type="button"
            role="tab"
            aria-selected={state === s}
            onClick={() => setState(s)}
            className={`min-h-9 flex-1 rounded-lg text-sm font-semibold ${state === s ? "bg-surface-2 text-text" : "text-muted"}`}
          >
            {s === "open" ? "Open" : "All"}
          </button>
        ))}
      </div>
      {feed.isError ? <ErrorNote error={feed.error} /> : null}
      {feed.isPending ? <Skeleton className="h-48 w-full rounded-2xl" /> : null}
      {feed.data && feed.data.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-line px-6 py-10 text-center text-muted">
          {state === "open" ? "Nothing is down right now." : "No incidents recorded yet."}
        </p>
      ) : null}
      {feed.data && feed.data.length > 0 ? (
        <Card className="py-1">
          <ul>
            {feed.data.map((incident) => (
              <IncidentRow key={incident.sk} incident={incident} showProduct to={`/p/${incident.productId}`} />
            ))}
          </ul>
        </Card>
      ) : null}
    </div>
  );
}
