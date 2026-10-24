import { useState } from "react";
import { Link } from "react-router-dom";
import { ErrorNote, EmptyState, Skeleton } from "../components/Feedback";
import { Icon } from "../components/Icon";
import { InstallTip } from "../components/InstallTip";
import { GlassButton, Screen } from "../components/Layout";
import { Segmented } from "../components/List";
import { ProductRow } from "../components/ProductCard";
import { RelativeTime } from "../components/RelativeTime";
import { tapFeedback } from "../lib/platform";
import { useProducts, useSummary } from "../lib/queries";
import { STATUS, sortProducts } from "../lib/status";
import type { Kind, Status, Summary } from "../lib/types";

const FILTERS = [
  { value: "all", label: "All" },
  { value: "personal", label: "Personal" },
  { value: "client", label: "Client Work" },
] as const;

const COUNTS: { status: Status; key: "up" | "degraded" | "down" | "paused" }[] = [
  { status: "UP", key: "up" },
  { status: "DEGRADED", key: "degraded" },
  { status: "DOWN", key: "down" },
  { status: "PAUSED", key: "paused" },
];

const OVERALL: Record<Summary["state"], Status> = { operational: "UP", degraded: "DEGRADED", down: "DOWN" };

export default function HomePage() {
  const [kind, setKind] = useState<Kind | "all">("all");
  const products = useProducts(kind === "all" ? undefined : kind);
  const summary = useSummary();
  const updatedAt = products.dataUpdatedAt ? new Date(products.dataUpdatedAt).toISOString() : null;
  const list = products.data ? sortProducts(products.data) : [];

  return (
    <Screen
      title="Status"
      trailing={
        <>
          <GlassButton
            label="Refresh"
            symbol="arrow.clockwise"
            onClick={() => {
              void tapFeedback();
              void products.refetch();
              void summary.refetch();
            }}
          />
          <GlassButton label="Add product" symbol="plus" to="/new" />
        </>
      }
    >
      <div className="space-y-6">
        <Overview summary={summary.data} updatedAt={updatedAt} />

        <Segmented label="Filter products" value={kind} options={FILTERS} onChange={setKind} />

        <InstallTip />

        {products.isError ? <ErrorNote error={products.error} /> : null}

        {products.isPending ? (
          <Skeleton className="h-64 w-full rounded-[26px]" />
        ) : list.length === 0 && !products.isError ? (
          kind === "all" ? (
            <EmptyState
              symbol="antenna.radiowaves.left.and.right"
              title="No Products Yet"
              action={
                <Link to="/new" className="inline-flex h-9 items-center rounded-full bg-tint px-4 text-subhead font-semibold text-white active:opacity-60">
                  Add Product
                </Link>
              }
            >
              Paste a site's link and Beacon checks it every minute.
            </EmptyState>
          ) : (
            <EmptyState symbol="antenna.radiowaves.left.and.right" title={kind === "client" ? "No Client Work" : "No Personal Products"} />
          )
        ) : (
          <section>
            <h2 className="mb-[7px] px-4 text-footnote text-label-2 uppercase">Products</h2>
            <ul className="list">
              {list.map((p) => (
                <ProductRow key={p.id} product={p} />
              ))}
            </ul>
          </section>
        )}
      </div>
    </Screen>
  );
}

/** The overall state, how fresh it is, and the count per status. */
function Overview({ summary, updatedAt }: { summary: Summary | undefined; updatedAt: string | null }) {
  const status = summary ? OVERALL[summary.state] : "UNKNOWN";
  const meta = STATUS[status];
  return (
    <section className="rounded-[26px] bg-cell p-5" aria-live="polite">
      <div className="flex items-center gap-3.5">
        <span style={{ color: meta.color }}>
          <Icon name={meta.symbol} className="size-[60px]" />
        </span>
        <div className="min-w-0">
          {summary ? <p className="text-title2">{summary.label}</p> : <Skeleton className="h-7 w-48" />}
          <p className="mt-0.5 text-subhead text-label-2">
            <RelativeTime iso={updatedAt} prefix="Updated " /> · every minute
          </p>
        </div>
      </div>
      {summary ? (
        <dl className="mt-4 grid grid-cols-4 border-t-[0.5px] border-separator pt-3.5" aria-label="Products by status">
          {COUNTS.map(({ status: s, key }) => (
            <div key={key} className="flex flex-col-reverse text-center">
              <dt className="text-caption text-label-2">{STATUS[s].label}</dt>
              <dd className="text-title2 tabular" style={{ color: summary[key] > 0 ? STATUS[s].ink : "var(--label-3)" }}>
                {summary[key]}
              </dd>
            </div>
          ))}
        </dl>
      ) : null}
    </section>
  );
}
