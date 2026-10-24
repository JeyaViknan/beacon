import { stripColor } from "../lib/status";

/** 24 capsules, one per hour (oldest left), coloured by that hour's uptime. */
export function Strip24h({ ratios }: { ratios: (number | null)[] }) {
  const measured = ratios.filter((r): r is number => r !== null);
  const bad = measured.filter((r) => r < 0.999).length;
  const label = measured.length
    ? `Last 24 hours: ${bad === 0 ? "no failed checks" : `${bad} of ${measured.length} hours with failures`}`
    : "Last 24 hours: no data yet";
  return (
    <div className="flex h-4 items-end gap-[2px]" role="img" aria-label={label}>
      {ratios.map((ratio, i) => (
        <span
          // Positions are fixed hour slots, so the index is the identity.
          key={i}
          className="flex-1 rounded-full"
          style={{ background: stripColor(ratio), height: ratio === null ? "40%" : "100%" }}
        />
      ))}
    </div>
  );
}
