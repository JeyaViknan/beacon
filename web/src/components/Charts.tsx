import { Area, Bar, CartesianGrid, ComposedChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { stripColor } from "../lib/status";
import { formatClockIST, formatDayIST, formatIST } from "../lib/time";
import type { SeriesPoint } from "../lib/types";
import { useCssVar } from "../lib/useCssVar";

/** 24h response time in 5-minute buckets; buckets with any failed check get a red band. */
export function LatencyChart({ points }: { points: SeriesPoint[] }) {
  const line = useCssVar("--focus", "#93c5fd");
  const down = useCssVar("--down", "#ef4444");
  const grid = useCssVar("--line", "#22324a");
  const muted = useCssVar("--muted", "#8a9bb3");
  const data = points.map((p) => ({
    t: p.t,
    lat: p.latAvg,
    failed: p.uptime !== null && p.uptime < 1 ? 1 : null,
  }));
  const failedBuckets = data.filter((d) => d.failed).length;
  return (
    <figure>
      <div className="h-44 w-full" role="img" aria-label={`Response time over 24 hours; ${failedBuckets} five-minute buckets had failures`}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 6, right: 4, bottom: 0, left: 0 }} barCategoryGap={0}>
            <CartesianGrid stroke={grid} strokeDasharray="2 4" vertical={false} />
            <XAxis
              dataKey="t"
              tickFormatter={formatClockIST}
              interval={71}
              tick={{ fill: muted, fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              yAxisId="ms"
              tick={{ fill: muted, fontSize: 11 }}
              tickFormatter={(v: number) => (v >= 1000 ? `${(v / 1000).toFixed(v % 1000 ? 1 : 0)}s` : String(v))}
              axisLine={false}
              tickLine={false}
              width={36}
            />
            <YAxis yAxisId="band" hide domain={[0, 1]} />
            <Tooltip
              cursor={{ stroke: muted, strokeWidth: 1 }}
              contentStyle={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 12, fontSize: 12 }}
              labelFormatter={(t: string) => formatIST(t)}
              formatter={(value: number, name: string) =>
                name === "lat" ? [`${value} ms`, "Avg latency"] : ["failed checks", "Bucket"]
              }
            />
            <Bar yAxisId="band" dataKey="failed" fill={down} fillOpacity={0.35} isAnimationActive={false} />
            <Area
              yAxisId="ms"
              dataKey="lat"
              type="monotone"
              stroke={line}
              strokeWidth={1.75}
              fill={line}
              fillOpacity={0.12}
              connectNulls={false}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-1 flex items-center gap-3 text-xs text-muted">
        <span className="inline-flex items-center gap-1">
          <span className="inline-block h-0.5 w-3 rounded" style={{ background: line }} /> avg latency (ms)
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: down, opacity: 0.45 }} /> failed checks
        </span>
      </figcaption>
    </figure>
  );
}

/** One bar per IST day for 30 days, coloured by that day's uptime. */
export function DailyBars({ points }: { points: SeriesPoint[] }) {
  const last = points[points.length - 1];
  const first = points[0];
  return (
    <div>
      <div className="flex h-10 items-stretch gap-[2px]" role="list" aria-label="Daily uptime, last 30 days">
        {points.map((p) => (
          <span
            key={p.t}
            role="listitem"
            title={`${formatDayIST(p.t)}: ${p.uptime === null ? "no data" : `${(p.uptime * 100).toFixed(2)}%`}`}
            aria-label={`${formatDayIST(p.t)}: ${p.uptime === null ? "no data" : `${(p.uptime * 100).toFixed(2)}% up`}`}
            className="flex-1 rounded-[2px]"
            style={{ background: stripColor(p.uptime), opacity: p.uptime === null ? 0.5 : 1 }}
          />
        ))}
      </div>
      {first && last ? (
        <div className="mt-1 flex justify-between text-xs text-muted">
          <span>{formatDayIST(first.t)}</span>
          <span>Today</span>
        </div>
      ) : null}
    </div>
  );
}
