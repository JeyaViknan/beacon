import { useEffect, useState } from "react";
import { formatIST, timeAgo } from "../lib/time";

/** "23s ago"; tap to see the exact IST time. Re-renders every 5 s so it stays honest. */
export function RelativeTime({ iso, prefix = "" }: { iso: string | null | undefined; prefix?: string }) {
  const [exact, setExact] = useState(false);
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = window.setInterval(() => setNow(new Date()), 5000);
    return () => window.clearInterval(t);
  }, []);
  if (!iso) return <span className="text-muted">{prefix}never</span>;
  return (
    <button
      type="button"
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        setExact((v) => !v);
      }}
      className="font-mono tabular text-left"
      title={formatIST(iso)}
    >
      {prefix}
      {exact ? formatIST(iso) : timeAgo(iso, now)}
    </button>
  );
}
