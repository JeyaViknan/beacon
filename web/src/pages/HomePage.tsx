import { useState } from "react";
import { Link } from "react-router-dom";
import { ErrorNote, Skeleton } from "../components/Feedback";
import { PlusIcon, RefreshIcon, StatusIcon } from "../components/Icons";
import { InstallTip } from "../components/InstallTip";
import { Lamp } from "../components/Lamp";
import { ProductCard } from "../components/ProductCard";
import { RelativeTime } from "../components/RelativeTime";
import { tapFeedback } from "../lib/platform";
import { useProducts, useSummary } from "../lib/queries";
import { STATUS, sortProducts } from "../lib/status";
import type { Kind, Status } from "../lib/types";

const FILTERS: { value: Kind | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "personal", label: "Personal" },
  { value: "client", label: "Client work" },
];

const CHIPS: { status: Status; key: "up" | "degraded" | "down" | "paused" }[] = [
  { status: "UP", key: "up" },
  { status: "DEGRADED", key: "degraded" },
  { status: "DOWN", key: "down" },
  { status: "PAUSED", key: "paused" },
];

export default function HomePage() {
  const [kind, setKind] = useState<Kind | "all">("all");
  const products = useProducts(kind === "all" ? undefined : kind);
  const summary = useSummary();
  const refreshing = products.isFetching || summary.isFetching;
  const updatedAt = products.dataUpdatedAt ? new Date(products.dataUpdatedAt).toISOString() : null;
  const list = products.data ? sortProducts(products.data) : [];

  return (
    <div className="space-y-5">
      <header className="flex min-h-14 items-center justify-between pt-2">
        <span className="font-display text-xl font-bold tracking-tight">Beacon</span>
        <div className="flex items-center gap-1">
          <button
            type="button"
            aria-label="Refresh"
            onClick={() => {
              void tapFeedback();
              void products.refetch();
              void summary.refetch();
            }}
            className="flex h-11 w-11 items-center justify-center rounded-full text-muted"
          >
            <RefreshIcon className={`h-5 w-5 ${refreshing ? "animate-spin motion-reduce:animate-none" : ""}`} />
          </button>
          <Link
            to="/new"
            aria-label="Add product"
            className="flex h-11 w-11 items-center justify-center rounded-full bg-text text-bg"
          >
            <PlusIcon className="h-5 w-5" />
          </Link>
        </div>
      </header>

      <section className="flex items-center gap-5 pl-3" aria-live="polite">
        <Lamp state={summary.data?.state ?? "unknown"} />
        <div className="min-w-0">
          {summary.data ? (
            <p className="font-display text-[26px] leading-tight font-bold tracking-tight">{summary.data.label}</p>
          ) : (
            <Skeleton className="h-7 w-52" />
          )}
          <p className="mt-1 text-sm text-muted">
            <RelativeTime iso={updatedAt} prefix="Updated " /> · every minute
          </p>
        </div>
      </section>

      {summary.data ? (
        <ul className="grid grid-cols-4 gap-2" aria-label="Products by status">
          {CHIPS.map(({ status, key }) => (
            <li
              key={key}
              className="flex flex-col items-center rounded-xl border border-line bg-surface py-2"
              style={{ color: summary.data[key] > 0 ? STATUS[status].ink : "var(--muted)" }}
            >
              <span className="flex items-center gap-1 font-display text-lg font-bold tabular">
                <StatusIcon status={status} className="h-4 w-4" />
                {summary.data[key]}
              </span>
              <span className="text-[11px] font-medium">{STATUS[status].label}</span>
            </li>
          ))}
        </ul>
      ) : null}

      <div role="tablist" aria-label="Filter products" className="flex rounded-xl border border-line bg-surface p-1">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            type="button"
            role="tab"
            aria-selected={kind === f.value}
            onClick={() => setKind(f.value)}
            className={`min-h-9 flex-1 rounded-lg text-sm font-semibold ${
              kind === f.value ? "bg-surface-2 text-text" : "text-muted"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <InstallTip />

      {products.isError ? <ErrorNote error={products.error} /> : null}

      {products.isPending ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-40 w-full rounded-2xl" />
          ))}
        </div>
      ) : list.length === 0 && !products.isError ? (
        <p className="rounded-2xl border border-dashed border-line px-6 py-10 text-center text-muted">
          {kind === "all" ? "No products yet — tap + to add your first one." : "No products of this kind yet."}
        </p>
      ) : (
        <ul className="space-y-3">
          {list.map((p) => (
            <ProductCard key={p.id} product={p} />
          ))}
        </ul>
      )}
    </div>
  );
}
