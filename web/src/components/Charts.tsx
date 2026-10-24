import { Area, Bar, CartesianGrid, ComposedChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { stripColor } from "../lib/status";
import { formatClockIST, formatDayIST, formatIST } from "../lib/time";
import type { SeriesPoint } from "../lib/types";
import { useCssVar } from "../lib/useCssVar";

/** 24h response time in 5-minute buckets, Swift Charts style; buckets with a failed check get a red band. */
export function LatencyChart({ points }: { points: SeriesPoint[] }) {
  const line = useCssVar("--tint", "#0a84ff");
  const down = useCssVar("--red", "#ff453a");
  const grid = useCssVar("--separator", "rgba(84,84,88,0.65)");
  const muted = useCssVar("--label-2", "rgba(235,235,245,0.6)");
  const data = points.map((p) => ({
    t: p.t,
    lat: p.latAvg,
    failed: p.uptime !== null && p.uptime < 1 ? 1 : null,
  }));
  const failedBuckets = data.filter((d) => d.failed).length;
  return (
    <figure>
      <div className="h-48 w-full" role="img" aria-label={`Response time over 24 hours; ${failedBuckets} five-minute buckets had failures`}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 0, bottom: 0, left: 0 }} barCategoryGap={0}>
            <defs>
              <linearGradient id="latency-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={line} stopOpacity={0.28} />
                <stop offset="100%" stopColor={line} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke={grid} strokeDasharray="2 3" vertical={false} />
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
              orientation="right"
              tick={{ fill: muted, fontSize: 11 }}
              tickFormatter={(v: number) => (v >= 1000 ? `${(v / 1000).toFixed(v % 1000 ? 1 : 0)}s` : `${v}`)}
              axisLine={false}
              tickLine={false}
              width={34}
            />
            <YAxis yAxisId="band" hide domain={[0, 1]} />
            <Tooltip
              cursor={{ stroke: muted, strokeWidth: 1 }}
              contentStyle={{
                background: "var(--glass)",
                backdropFilter: "blur(24px)",
                border: "none",
                borderRadius: 14,
                boxShadow: "var(--glass-shadow)",
                fontSize: 13,
                color: "var(--label)",
              }}
              labelStyle={{ color: "var(--label-2)" }}
              labelFormatter={(t: string) => formatIST(t)}
              formatter={(value: number, name: string) =>
                name === "lat" ? [`${value} ms`, "Average"] : ["failed checks", "Bucket"]
              }
            />
            <Bar yAxisId="band" dataKey="failed" fill={down} fillOpacity={0.25} isAnimationActive={false} />
            <Area
              yAxisId="ms"
              dataKey="lat"
              type="monotone"
              stroke={line}
              strokeWidth={2}
              fill="url(#latency-fill)"
              connectNulls={false}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-2 flex items-center gap-4 text-caption text-label-2">
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-[3px] w-3.5 rounded-full" style={{ background: line }} /> Average (ms)
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block size-2.5 rounded-[3px]" style={{ background: down, opacity: 0.5 }} /> Failed checks
        </span>
      </figcaption>
    </figure>
  );
}

/** One capsule per IST day for 30 days, coloured by that day's uptime. */
export function DailyBars({ points }: { points: SeriesPoint[] }) {
  const last = points[points.length - 1];
  const first = points[0];
  return (
    <div>
      <div className="flex h-10 items-stretch gap-[3px]" role="list" aria-label="Daily uptime, last 30 days">
        {points.map((p) => (
          <span
            key={p.t}
            role="listitem"
            title={`${formatDayIST(p.t)}: ${p.uptime === null ? "no data" : `${(p.uptime * 100).toFixed(2)}%`}`}
            aria-label={`${formatDayIST(p.t)}: ${p.uptime === null ? "no data" : `${(p.uptime * 100).toFixed(2)}% up`}`}
            className="flex-1 rounded-full"
            style={{ background: stripColor(p.uptime) }}
          />
        ))}
      </div>
      {first && last ? (
        <div className="mt-2 flex justify-between text-caption text-label-2">
          <span>{formatDayIST(first.t)}</span>
          <span>Today</span>
        </div>
      ) : null}
    </div>
  );
}
