import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { Lamp } from "../components/Lamp";
import { ApiError, api } from "../lib/api";
import { getToken, setToken } from "../lib/auth";

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const from = (location.state as { from?: string } | null)?.from ?? "/";

  if (getToken()) return <Navigate to={from} replace />;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api<{ token: string; expiresAt: string }>("/auth/login", {
        method: "POST",
        body: { password },
      });
      setToken(res.token, res.expiresAt);
      navigate(from, { replace: true });
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 401
          ? "Wrong password. After 5 wrong tries, login locks for 15 minutes."
          : err instanceof Error
            ? err.message
            : "Login failed.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main
      className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center px-6"
      style={{ paddingTop: "var(--safe-top)", paddingBottom: "var(--safe-bottom)" }}
    >
      <div className="mb-10 flex items-center gap-4">
        <Lamp state="unknown" />
        <div>
          <h1 className="font-display text-3xl font-bold tracking-tight">Beacon</h1>
          <p className="text-sm text-muted">Uptime for everything you've shipped.</p>
        </div>
      </div>
      <form onSubmit={submit} className="space-y-4">
        <label className="block">
          <span className="mb-1.5 block text-sm font-medium">Password</span>
          <input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="min-h-12 w-full rounded-xl border border-line bg-surface px-4 text-base"
          />
        </label>
        {error ? (
          <p role="alert" className="text-sm" style={{ color: "var(--down-ink)" }}>
            {error}
          </p>
        ) : null}
        <button
          type="submit"
          disabled={busy || !password}
          className="min-h-12 w-full rounded-xl bg-text text-base font-semibold text-bg disabled:opacity-50"
        >
          {busy ? "Logging in…" : "Log in"}
        </button>
      </form>
    </main>
  );
}
