import { useEffect, useState } from "react";
import type { SymbolName } from "../symbols/names";
import { Icon } from "./Icon";

export function OfflineBanner() {
  const [online, setOnline] = useState(() => navigator.onLine !== false);
  useEffect(() => {
    const up = () => setOnline(true);
    const down = () => setOnline(false);
    window.addEventListener("online", up);
    window.addEventListener("offline", down);
    return () => {
      window.removeEventListener("online", up);
      window.removeEventListener("offline", down);
    };
  }, []);
  if (online) return null;
  return (
    <div
      role="status"
      className="glass fixed left-1/2 z-40 flex -translate-x-1/2 items-center gap-1.5 rounded-full px-4 py-2 text-footnote font-semibold"
      style={{ top: "calc(var(--safe-top) + var(--bar) + 4px)" }}
    >
      <Icon name="wifi.slash" className="size-5" />
      Offline · showing the last data
    </div>
  );
}

export function Skeleton({ className }: { className: string }) {
  return <div className={`skeleton ${className}`} aria-hidden="true" />;
}

export function ErrorNote({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : "Something went wrong.";
  return (
    <p role="alert" className="flex items-start gap-2.5 rounded-[18px] bg-cell px-4 py-3 text-subhead">
      <span style={{ color: "var(--red)" }}>
        <Icon name="exclamationmark.triangle.fill" className="size-6" />
      </span>
      <span className="pt-0.5">{message}</span>
    </p>
  );
}

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  tone?: "prominent" | "gray" | "destructive";
  size?: "large" | "regular";
};

/** iOS capsule buttons: prominent (tinted), gray (tinted text on fill) and destructive. */
export function Button({ tone = "gray", size = "large", className = "", ...props }: ButtonProps) {
  // Disabled buttons turn grey, as in UIKit, rather than fading their tint.
  const tones = {
    prominent: "bg-tint text-white disabled:bg-fill-3 disabled:text-label-3",
    gray: "bg-fill-3 text-tint disabled:text-label-3",
    destructive: "bg-fill-3 text-red disabled:text-label-3",
  } as const;
  const sizes = { large: "h-[50px] px-6 text-headline", regular: "h-9 px-4 text-subhead font-semibold" } as const;
  return (
    <button
      type="button"
      {...props}
      className={`inline-flex items-center justify-center gap-2 rounded-full active:opacity-60 ${tones[tone]} ${sizes[size]} ${className}`}
    />
  );
}

/** Like ContentUnavailableView: a large symbol, a title and what to do next. */
export function EmptyState({
  symbol,
  title,
  children,
  action,
}: {
  symbol: SymbolName;
  title: string;
  children?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center px-8 py-14 text-center">
      <span className="text-label-3">
        <Icon name={symbol} className="size-20" />
      </span>
      <h2 className="mt-3 text-title2">{title}</h2>
      {children ? <p className="mt-1.5 text-subhead text-label-2">{children}</p> : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}
