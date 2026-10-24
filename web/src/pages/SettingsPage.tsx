import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Card, ErrorNote, SectionTitle, Skeleton } from "../components/Feedback";
import { StatusIcon } from "../components/Icons";
import { ConfirmDialog, PageHeader } from "../components/Layout";
import { clearToken } from "../lib/auth";
import { isNativeApp, tapFeedback } from "../lib/platform";
import { enablePush, notificationPermission, pushSupport } from "../lib/push";
import { useDemo, useHealth, usePatchSettings, useSettings, useTestNotification } from "../lib/queries";
import type { SettingsResponse } from "../lib/types";

const VAPID_PUBLIC_KEY = import.meta.env.VITE_VAPID_PUBLIC_KEY ?? "";
const APP_VERSION = import.meta.env.VITE_APP_VERSION ?? "dev";

export default function SettingsPage() {
  const settings = useSettings();
  return (
    <div className="space-y-6 pb-6">
      <PageHeader title="Settings" />
      <Notifications settings={settings.data} />
      {settings.isError ? <ErrorNote error={settings.error} /> : null}
      {settings.isPending ? <Skeleton className="h-40 w-full rounded-2xl" /> : null}
      {settings.data ? (
        <>
          <Channels data={settings.data} />
          <Demo data={settings.data} />
        </>
      ) : null}
      <About />
    </div>
  );
}

function Notifications({ settings }: { settings: SettingsResponse | undefined }) {
  const qc = useQueryClient();
  const support = pushSupport();
  const [permission, setPermission] = useState(notificationPermission);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const test = useTestNotification();

  async function onEnable() {
    setBusy(true);
    setError(null);
    try {
      // Called straight from the tap: iOS only shows the permission prompt for user gestures.
      setPermission(await enablePush(VAPID_PUBLIC_KEY));
      await qc.invalidateQueries({ queryKey: ["settings"] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not enable notifications.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <SectionTitle>Notifications</SectionTitle>
      <Card className="space-y-3">
        {isNativeApp() ? (
          <p className="text-sm">
            This app shows Beacon's live status. Alerts reach you by <strong>email</strong> and through the{" "}
            <strong>Beacon web app</strong> on your Home Screen, which has push notifications. Native push in this app
            would need Apple's paid Developer Program.
          </p>
        ) : support === "needs-install" ? (
          <p className="text-sm">
            iPhone only sends notifications to installed apps. Tap <strong>Share</strong> →{" "}
            <strong>Add to Home Screen</strong>, open Beacon from the Home Screen, then come back here.
          </p>
        ) : support === "unsupported" ? (
          <p className="text-sm text-muted">This browser can't receive Web Push notifications.</p>
        ) : (
          <>
            <p className="text-sm text-muted">
              {permission === "granted"
                ? "This device gets DOWN and RECOVERED alerts."
                : permission === "denied"
                  ? "Notifications are blocked. Allow them for Beacon in iOS Settings → Notifications."
                  : "Get an alert on this device when a product goes down or recovers."}
            </p>
            <Button tone="primary" className="w-full" disabled={busy || permission === "denied"} onClick={onEnable}>
              {busy ? "Enabling…" : permission === "granted" ? "Re-register this device" : "Enable notifications"}
            </Button>
          </>
        )}
        <Button className="w-full" disabled={test.isPending} onClick={() => test.mutate()}>
          {test.isPending ? "Sending…" : "Send test notification"}
        </Button>
        {test.isSuccess ? (
          <p role="status" className="text-sm text-muted">
            Test sent to {settings?.channels.pushDevices ?? 0} device(s) and email. It should arrive within a few seconds.
          </p>
        ) : null}
        {test.isError ? <ErrorNote error={test.error} /> : null}
        {error ? <ErrorNote error={new Error(error)} /> : null}
      </Card>
    </section>
  );
}

function Channels({ data }: { data: SettingsResponse }) {
  const patch = usePatchSettings();
  const { channels, settings } = data;
  const rows: {
    key: "pushEnabled" | "emailEnabled" | "pagerdutyEnabled";
    label: string;
    detail: string;
    ready: boolean;
  }[] = [
    {
      key: "pushEnabled",
      label: "Push",
      detail: channels.vapid ? `${channels.pushDevices} device${channels.pushDevices === 1 ? "" : "s"}` : "VAPID key not set",
      ready: channels.vapid && channels.pushDevices > 0,
    },
    { key: "emailEnabled", label: "Email", detail: channels.email ? "Configured" : "Not set up", ready: channels.email },
    {
      key: "pagerdutyEnabled",
      label: "PagerDuty",
      detail: channels.pagerduty ? "Configured" : "Not set up",
      ready: channels.pagerduty,
    },
  ];
  return (
    <section>
      <SectionTitle>Alert channels</SectionTitle>
      <Card className="divide-y divide-line py-1">
        {rows.map((row) => (
          <div key={row.key} className="flex min-h-14 items-center gap-3 py-2">
            <span style={{ color: row.ready ? "var(--up-ink)" : "var(--unknown-ink)" }}>
              <StatusIcon status={row.ready ? "UP" : "UNKNOWN"} />
            </span>
            <span className="flex-1">
              <span className="block font-semibold">{row.label}</span>
              <span className="block text-sm text-muted">{row.detail}</span>
            </span>
            <Switch
              checked={settings[row.key]}
              disabled={patch.isPending}
              onChange={(checked) => patch.mutate({ [row.key]: checked })}
              label={`${row.label} alerts`}
            />
          </div>
        ))}
        <div className="flex min-h-14 items-center gap-3 py-2">
          <span style={{ color: channels.healthchecks ? "var(--up-ink)" : "var(--unknown-ink)" }}>
            <StatusIcon status={channels.healthchecks ? "UP" : "UNKNOWN"} />
          </span>
          <span className="flex-1">
            <span className="block font-semibold">Dead-man's switch</span>
            <span className="block text-sm text-muted">
              {channels.healthchecks ? "healthchecks.io gets a ping every minute" : "healthchecks.io not set up"}
            </span>
          </span>
        </div>
      </Card>
      {patch.isError ? <ErrorNote error={patch.error} /> : null}
    </section>
  );
}

function Switch({
  checked,
  disabled,
  onChange,
  label,
}: {
  checked: boolean;
  disabled?: boolean;
  onChange: (checked: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className="relative inline-flex h-[31px] w-[51px] flex-none items-center rounded-full transition-colors disabled:opacity-60"
      style={{ background: checked ? "var(--up)" : "var(--line)" }}
    >
      <span
        className="absolute h-[27px] w-[27px] rounded-full bg-white shadow transition-transform motion-reduce:transition-none"
        style={{ transform: `translateX(${checked ? 22 : 2}px)` }}
      />
    </button>
  );
}

function Demo({ data }: { data: SettingsResponse }) {
  const demo = useDemo();
  const broken = data.demo === "broken";
  return (
    <section>
      <SectionTitle>Demo</SectionTitle>
      <Card className="space-y-3">
        <p className="flex items-center gap-2 text-sm">
          <span style={{ color: broken ? "var(--down-ink)" : "var(--up-ink)" }}>
            <StatusIcon status={broken ? "DOWN" : "UP"} />
          </span>
          <span>
            Demo target is <strong>{broken ? "returning 503." : "healthy."}</strong>
            {broken ? " Expect a DOWN alert within 1–2 minutes." : ""}
          </span>
        </p>
        <div className="grid gap-3">
          <Button
            tone="danger"
            disabled={demo.isPending || broken}
            onClick={() => {
              void tapFeedback("medium");
              demo.mutate("break");
            }}
          >
            Break demo target
          </Button>
          <Button
            disabled={demo.isPending || !broken}
            onClick={() => {
              void tapFeedback("medium");
              demo.mutate("fix");
            }}
          >
            Fix demo target
          </Button>
        </div>
        {demo.isError ? <ErrorNote error={demo.error} /> : null}
      </Card>
    </section>
  );
}

function About() {
  const health = useHealth();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [confirming, setConfirming] = useState(false);
  return (
    <section>
      <SectionTitle>About</SectionTitle>
      <Card className="space-y-3">
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
          <dt className="text-muted">App version</dt>
          <dd className="font-mono">{APP_VERSION}</dd>
          <dt className="text-muted">API</dt>
          <dd className="flex items-center gap-1.5 font-mono">
            {health.data ? (
              <>
                <span style={{ color: "var(--up-ink)" }}>
                  <StatusIcon status="UP" className="h-3.5 w-3.5" />
                </span>
                healthy · {health.data.version}
              </>
            ) : health.isError ? (
              <>
                <span style={{ color: "var(--down-ink)" }}>
                  <StatusIcon status="DOWN" className="h-3.5 w-3.5" />
                </span>
                unreachable
              </>
            ) : (
              "checking…"
            )}
          </dd>
        </dl>
        <Button className="w-full" onClick={() => setConfirming(true)}>
          Log out
        </Button>
      </Card>
      {confirming ? (
        <ConfirmDialog
          title="Log out of Beacon?"
          body="You'll need the password to see your products again. Notifications keep arriving on this device."
          confirmLabel="Log out"
          onCancel={() => setConfirming(false)}
          onConfirm={() => {
            clearToken();
            qc.clear();
            if ("caches" in window) void caches.delete("beacon-api");
            navigate("/login", { replace: true });
          }}
        />
      ) : null}
    </section>
  );
}
