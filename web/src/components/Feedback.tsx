import { useEffect, useState } from "react";

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
    <div role="status" className="bg-degraded px-4 py-2 text-center text-sm font-semibold text-black">
      You're offline. Showing the last data Beacon received.
    </div>
  );
}

export function Skeleton({ className }: { className: string }) {
  return <div className={`skeleton ${className}`} aria-hidden="true" />;
}

export function ErrorNote({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : "Something went wrong.";
  return (
    <p role="alert" className="rounded-xl border border-down/40 bg-down/10 px-4 py-3 text-sm" style={{ color: "var(--down-ink)" }}>
      {message}
    </p>
  );
}

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <section className={`rounded-2xl border border-line bg-surface p-4 ${className}`}>{children}</section>;
}

export function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h2 className="mb-2 px-1 text-xs font-semibold tracking-wider text-muted uppercase">{children}</h2>;
}

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & { tone?: "primary" | "plain" | "danger" };

export function Button({ tone = "plain", className = "", ...props }: ButtonProps) {
  const tones = {
    primary: "bg-text text-bg",
    plain: "border border-line bg-surface-2 text-text",
    danger: "border border-down/50 bg-down/10",
  } as const;
  return (
    <button
      type="button"
      {...props}
      className={`inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-4 text-[15px] font-semibold transition-opacity active:opacity-70 disabled:opacity-50 ${tones[tone]} ${className}`}
      style={tone === "danger" ? { color: "var(--down-ink)", ...props.style } : props.style}
    />
  );
}
