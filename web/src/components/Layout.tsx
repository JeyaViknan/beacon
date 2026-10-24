import { useEffect, useRef, useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import type { SymbolName } from "../symbols/names";
import { OfflineBanner } from "./Feedback";
import { Icon } from "./Icon";

// Product pages belong to the Status tab, so it stays selected there.
const tabs: { to: string; label: string; symbol: SymbolName; owns: (path: string) => boolean }[] = [
  { to: "/", label: "Status", symbol: "waveform.path.ecg", owns: (p) => p === "/" || p.startsWith("/p/") },
  { to: "/incidents", label: "Incidents", symbol: "bell.fill", owns: (p) => p.startsWith("/incidents") },
  { to: "/settings", label: "Settings", symbol: "gearshape.fill", owns: (p) => p.startsWith("/settings") },
];

export function Layout() {
  // Forms behave like sheets: no tab bar underneath.
  const sheet = /\/(new|edit)$/.test(useLocation().pathname);
  return (
    <div className="mx-auto min-h-dvh max-w-xl">
      <OfflineBanner />
      <Outlet />
      {sheet ? null : (
        <>
          <div className="scroll-edge-bottom" />
          <TabBar />
        </>
      )}
    </div>
  );
}

/** iOS 26 tab bar: a floating Liquid Glass capsule; the selected tab sits on a lighter platter. */
function TabBar() {
  const path = useLocation().pathname;
  return (
    <nav
      aria-label="Main"
      className="fixed inset-x-0 bottom-0 z-30 flex justify-center px-6"
      style={{ paddingBottom: "max(var(--safe-bottom), 16px)" }}
    >
      <ul className="glass flex h-[62px] w-full max-w-[400px] gap-1 rounded-full p-1">
        {tabs.map(({ to, label, symbol, owns }) => {
          const selected = owns(path);
          return (
            <li key={to} className="flex-1">
              <Link
                to={to}
                aria-current={selected ? "page" : undefined}
                className={`flex h-full flex-col items-center justify-center rounded-full text-caption2 font-semibold ${
                  selected ? "bg-[var(--glass-selected)] text-tint" : "text-label"
                }`}
              >
                <Icon name={symbol} className="size-8" />
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/**
 * A screen with an iOS navigation bar. With `large`, the title starts as a Large Title in the
 * content and moves into the bar once it scrolls under it.
 */
export function Screen({
  title,
  large = true,
  back,
  leading,
  trailing,
  children,
}: {
  title: string;
  large?: boolean;
  back?: string;
  leading?: React.ReactNode;
  trailing?: React.ReactNode;
  children: React.ReactNode;
}) {
  const bar = useRef<HTMLElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const [inline, setInline] = useState(!large);
  useEffect(() => {
    const el = heading.current;
    if (!large || !el || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver(([entry]) => setInline(!entry?.isIntersecting), {
      rootMargin: `-${bar.current?.offsetHeight ?? 0}px 0px 0px 0px`,
    });
    io.observe(el);
    return () => io.disconnect();
  }, [large]);

  return (
    <>
      <div className="scroll-edge-top" />
      <header ref={bar} className="fixed inset-x-0 top-0 z-30 mx-auto max-w-xl px-4" style={{ paddingTop: "var(--safe-top)" }}>
        <div className="grid h-[var(--bar)] grid-cols-[1fr_auto_1fr] items-center gap-2">
          <div className="flex min-w-0 justify-start gap-2">{back ? <BackButton fallback={back} /> : leading}</div>
          <span
            aria-hidden="true"
            className={`max-w-[60vw] truncate text-headline transition-opacity duration-150 ${inline ? "opacity-100" : "opacity-0"}`}
          >
            {title}
          </span>
          <div className="flex min-w-0 justify-end gap-2">{trailing}</div>
        </div>
      </header>
      <main className="px-4" style={{ paddingTop: "calc(var(--safe-top) + var(--bar))", paddingBottom: "calc(var(--safe-bottom) + 112px)" }}>
        <h1 ref={heading} className={large ? "px-1 pt-1 pb-4 text-large-title break-words" : "sr-only"}>
          {title}
        </h1>
        {children}
      </main>
    </>
  );
}

type GlassButtonProps = {
  label: string;
  symbol?: SymbolName;
  text?: string;
  prominent?: boolean;
  disabled?: boolean;
} & ({ to: string; onClick?: never; type?: never } | { to?: never; onClick?: () => void; type?: "button" | "submit" });

/** A bar button: a glass circle with a symbol, or a glass capsule with text. Prominent = tinted. */
export function GlassButton({ label, symbol, text, prominent, disabled, to, onClick, type = "button" }: GlassButtonProps) {
  const cls = `flex h-11 items-center justify-center rounded-full active:opacity-60 disabled:opacity-40 ${
    text ? "px-4 text-headline" : "w-11"
  } ${prominent ? "bg-tint text-white" : "glass text-label"}`;
  const body = symbol ? <Icon name={symbol} className="size-7" /> : text;
  return to ? (
    <Link to={to} aria-label={label} className={cls}>
      {body}
    </Link>
  ) : (
    <button type={type} aria-label={label} onClick={onClick} disabled={disabled} className={cls}>
      {body}
    </button>
  );
}

function BackButton({ fallback }: { fallback: string }) {
  const navigate = useNavigate();
  return (
    <GlassButton
      label="Back"
      symbol="chevron.left"
      onClick={() => (window.history.length > 1 ? navigate(-1) : navigate(fallback))}
    />
  );
}

/** An iOS alert: title, message, Cancel and a destructive confirm, on a dimmed screen. */
export function ConfirmDialog({
  title,
  body,
  confirmLabel,
  onConfirm,
  onCancel,
  busy,
}: {
  title: string;
  body: string;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
  busy?: boolean;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-10" style={{ background: "var(--dim)" }} onClick={onCancel}>
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        aria-describedby="confirm-body"
        className="glass w-full max-w-[300px] rounded-[34px] p-5 text-center"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="confirm-title" className="text-headline">
          {title}
        </h2>
        <p id="confirm-body" className="mt-1.5 text-footnote text-label-2">
          {body}
        </p>
        <div className="mt-5 grid grid-cols-2 gap-2.5">
          <button type="button" onClick={onCancel} className="h-12 rounded-full bg-fill-3 text-headline active:opacity-60">
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className="h-12 rounded-full bg-fill-3 text-headline text-red active:opacity-60 disabled:opacity-40"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
