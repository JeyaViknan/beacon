import { stripColor } from "../lib/status";

/** 24 bars, one per hour (oldest left), coloured by that hour's uptime. */
export function Strip24h({ ratios }: { ratios: (number | null)[] }) {
  const measured = ratios.filter((r): r is number => r !== null);
  const bad = measured.filter((r) => r < 0.999).length;
  const label = measured.length
    ? `Last 24 hours: ${bad === 0 ? "no failed checks" : `${bad} of ${measured.length} hours with failures`}`
    : "Last 24 hours: no data yet";
  return (
    <div className="flex h-5 items-end gap-[3px]" role="img" aria-label={label}>
      {ratios.map((ratio, i) => (
        <span
          // Positions are fixed hour slots, so the index is the identity.
          key={i}
          className="flex-1 rounded-[2px]"
          style={{
            background: stripColor(ratio),
            height: ratio === null ? "35%" : "100%",
            opacity: ratio === null ? 0.6 : 1,
          }}
        />
      ))}
    </div>
  );
}
