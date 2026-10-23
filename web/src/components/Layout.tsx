import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { BellIcon, ChevronLeftIcon, GearIcon, HomeIcon } from "./Icons";
import { OfflineBanner } from "./Feedback";

const tabs = [
  { to: "/", label: "Status", icon: HomeIcon, end: true },
  { to: "/incidents", label: "Incidents", icon: BellIcon, end: false },
  { to: "/settings", label: "Settings", icon: GearIcon, end: false },
];

export function Layout() {
  return (
    <div className="mx-auto flex min-h-dvh max-w-xl flex-col">
      <div className="sticky top-0 z-20" style={{ paddingTop: "var(--safe-top)", background: "var(--bg)" }}>
        <OfflineBanner />
      </div>
      <main className="flex-1 px-4 pb-28">
        <Outlet />
      </main>
      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 z-20 border-t border-line backdrop-blur-xl"
        style={{
          paddingBottom: "var(--safe-bottom)",
          background: "color-mix(in oklab, var(--bg) 82%, transparent)",
        }}
      >
        <ul className="mx-auto flex max-w-xl">
          {tabs.map(({ to, label, icon: Icon, end }) => (
            <li key={to} className="flex-1">
              <NavLink
                to={to}
                end={end}
                className={({ isActive }) =>
                  `flex min-h-14 flex-col items-center justify-center gap-0.5 text-[11px] font-medium ${
                    isActive ? "text-text" : "text-muted"
                  }`
                }
              >
                <Icon className="h-6 w-6" />
                {label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}

export function PageHeader({
  title,
  back,
  actions,
}: {
  title: string;
  back?: string;
  actions?: React.ReactNode;
}) {
  const navigate = useNavigate();
  return (
    <header className="flex min-h-14 items-center gap-2 pt-2">
      {back ? (
        <button
          type="button"
          onClick={() => (window.history.length > 1 ? navigate(-1) : navigate(back))}
          className="-ml-2 flex h-11 w-11 items-center justify-center rounded-full text-muted"
          aria-label="Back"
        >
          <ChevronLeftIcon className="h-6 w-6" />
        </button>
      ) : null}
      <h1 className="font-display min-w-0 flex-1 truncate text-2xl font-bold tracking-tight">{title}</h1>
      {actions}
    </header>
  );
}

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
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-4 sm:items-center" onClick={onCancel}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        className="w-full max-w-sm rounded-2xl border border-line bg-surface p-5"
        style={{ marginBottom: "var(--safe-bottom)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="confirm-title" className="font-display text-lg font-bold">
          {title}
        </h2>
        <p className="mt-2 text-sm text-muted">{body}</p>
        <div className="mt-5 flex gap-3">
          <button type="button" onClick={onCancel} className="min-h-11 flex-1 rounded-xl border border-line font-semibold">
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className="min-h-11 flex-1 rounded-xl bg-down font-semibold text-white disabled:opacity-50"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
