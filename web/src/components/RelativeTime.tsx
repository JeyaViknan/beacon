import { useEffect, useState } from "react";
import { formatIST, timeAgo } from "../lib/time";

/** "23s ago", with the exact IST time as its tooltip. Re-renders every 5 s so it stays honest. */
export function RelativeTime({ iso, prefix = "" }: { iso: string | null | undefined; prefix?: string }) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = window.setInterval(() => setNow(new Date()), 5000);
    return () => window.clearInterval(t);
  }, []);
  if (!iso) return <span>{prefix}never</span>;
  return (
    <time dateTime={iso} title={formatIST(iso)} className="tabular">
      {prefix}
      {timeAgo(iso, now)}
    </time>
  );
}
