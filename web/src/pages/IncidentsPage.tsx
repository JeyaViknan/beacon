import { useState } from "react";
import { EmptyState, ErrorNote, Skeleton } from "../components/Feedback";
import { IncidentRow } from "../components/IncidentRow";
import { Screen } from "../components/Layout";
import { Segmented } from "../components/List";
import { useIncidentFeed } from "../lib/queries";

const FILTERS = [
  { value: "open", label: "Open" },
  { value: "all", label: "All" },
] as const;

export default function IncidentsPage() {
  const [state, setState] = useState<"open" | "all">("open");
  const feed = useIncidentFeed(state);
  return (
    <Screen title="Incidents">
      <div className="space-y-6">
        <Segmented label="Filter incidents" value={state} options={FILTERS} onChange={setState} />
        {feed.isError ? <ErrorNote error={feed.error} /> : null}
        {feed.isPending ? <Skeleton className="h-48 w-full rounded-[26px]" /> : null}
        {feed.data && feed.data.length === 0 ? (
          state === "open" ? (
            <EmptyState symbol="checkmark.seal.fill" title="No Open Incidents">
              Everything Beacon checks is up.
            </EmptyState>
          ) : (
            <EmptyState symbol="checkmark.seal.fill" title="No Incidents">
              When a product goes down, its incident shows up here.
            </EmptyState>
          )
        ) : null}
        {feed.data && feed.data.length > 0 ? (
          <ul className="list">
            {feed.data.map((incident) => (
              <IncidentRow key={incident.sk} incident={incident} showProduct to={`/p/${incident.productId}`} />
            ))}
          </ul>
        ) : null}
      </div>
    </Screen>
  );
}
