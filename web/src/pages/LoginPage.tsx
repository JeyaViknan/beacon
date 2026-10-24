import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { Button } from "../components/Feedback";
import { Icon } from "../components/Icon";
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
      <div className="mb-9 flex flex-col items-center text-center">
        <img src="/icons/icon-192.png" alt="" width={88} height={88} className="size-[88px] rounded-[20px]" />
        <h1 className="mt-5 text-title1">Beacon</h1>
        <p className="mt-1 text-subhead text-label-2">Uptime for everything you've shipped.</p>
      </div>
      <form onSubmit={submit} className="space-y-4">
        <label className="list flex min-h-[52px] items-center gap-3 px-4">
          <span className="text-label-3">
            <Icon name="lock.fill" className="size-6" />
          </span>
          <input
            type="password"
            aria-label="Password"
            placeholder="Password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="min-w-0 flex-1 bg-transparent text-body outline-none placeholder:text-label-3"
          />
        </label>
        {error ? (
          <p role="alert" className="px-4 text-footnote text-red">
            {error}
          </p>
        ) : null}
        <Button type="submit" tone="prominent" className="w-full" disabled={busy || !password}>
          {busy ? "Logging In…" : "Log In"}
        </Button>
      </form>
    </main>
  );
}
