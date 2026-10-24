import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ErrorNote, Skeleton } from "../components/Feedback";
import { ConfirmDialog, Screen } from "../components/Layout";
import { Row, RowButton, Section, Switch } from "../components/List";
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
    <Screen title="Settings">
      <div className="space-y-7">
        <Notifications settings={settings.data} />
        {settings.isError ? <ErrorNote error={settings.error} /> : null}
        {settings.isPending ? <Skeleton className="h-56 w-full rounded-[26px]" /> : null}
        {settings.data ? (
          <>
            <Channels data={settings.data} />
            <Demo data={settings.data} />
          </>
        ) : null}
        <About />
      </div>
    </Screen>
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

  const footer = test.isSuccess ? (
    `Test sent to ${settings?.channels.pushDevices ?? 0} device(s) and email. It should arrive within a few seconds.`
  ) : isNativeApp() ? (
    <>
      This app shows Beacon's live status. Alerts reach you by <strong>email</strong> and through the{" "}
      <strong>Beacon web app</strong> on your Home Screen, which has push notifications. Native push in this app would
      need Apple's paid Developer Program.
    </>
  ) : support === "needs-install" ? (
    <>
      iPhone only sends notifications to installed apps. Tap <strong>Share</strong>, then{" "}
      <strong>Add to Home Screen</strong>, open Beacon from the Home Screen and come back here.
    </>
  ) : support === "unsupported" ? (
    "This browser can't receive Web Push notifications."
  ) : permission === "granted" ? (
    "This device gets DOWN and RECOVERED alerts."
  ) : permission === "denied" ? (
    "Notifications are blocked. Allow them for Beacon in iOS Settings → Notifications."
  ) : (
    "Get an alert on this device when a product goes down or recovers."
  );

  return (
    <div className="space-y-3">
      <Section header="Notifications" footer={footer}>
        {!isNativeApp() && support === "supported" ? (
          <RowButton
            tile={{ name: "bell.badge.fill", color: "var(--red)" }}
            title={busy ? "Enabling…" : permission === "granted" ? "Re-register This Device" : "Enable Notifications"}
            tone="action"
            disabled={busy || permission === "denied"}
            onClick={() => void onEnable()}
          />
        ) : null}
        <RowButton
          tile={{ name: "paperplane.fill", color: "var(--blue)" }}
          title={test.isPending ? "Sending…" : "Send Test Notification"}
          tone="action"
          disabled={test.isPending}
          onClick={() => test.mutate()}
        />
      </Section>
      {test.isError ? <ErrorNote error={test.error} /> : null}
      {error ? <ErrorNote error={new Error(error)} /> : null}
    </div>
  );
}

function Channels({ data }: { data: SettingsResponse }) {
  const patch = usePatchSettings();
  const { channels, settings } = data;
  const rows = [
    {
      key: "pushEnabled",
      label: "Push",
      tile: { name: "bell.badge.fill", color: "var(--red)" },
      detail: channels.vapid ? `${channels.pushDevices} device${channels.pushDevices === 1 ? "" : "s"}` : "VAPID key not set",
    },
    {
      key: "emailEnabled",
      label: "Email",
      tile: { name: "envelope.fill", color: "var(--blue)" },
      detail: channels.email ? "Configured" : "Not set up",
    },
    {
      key: "pagerdutyEnabled",
      label: "PagerDuty",
      tile: { name: "phone.fill", color: "var(--green)" },
      detail: channels.pagerduty ? "Configured" : "Not set up",
    },
  ] as const;
  return (
    <div className="space-y-3">
      <Section header="Alert channels">
        {rows.map((row) => (
          <Row
            key={row.key}
            tile={row.tile}
            title={row.label}
            subtitle={row.detail}
            trailing={
              <Switch
                checked={settings[row.key]}
                disabled={patch.isPending}
                onChange={(checked) => patch.mutate({ [row.key]: checked })}
                label={`${row.label} alerts`}
              />
            }
          />
        ))}
        <Row
          tile={{ name: "timer", color: "var(--gray)" }}
          title="Dead-man's switch"
          subtitle={channels.healthchecks ? "healthchecks.io gets a ping every minute" : "healthchecks.io not set up"}
        />
      </Section>
      {patch.isError ? <ErrorNote error={patch.error} /> : null}
    </div>
  );
}

function Demo({ data }: { data: SettingsResponse }) {
  const demo = useDemo();
  const broken = data.demo === "broken";
  return (
    <div className="space-y-3">
      <Section
        header="Demo"
        footer={
          broken
            ? "The demo target returns 503. Expect a DOWN alert within 1–2 minutes."
            : "Break the demo target to watch Beacon detect, alert and recover, live."
        }
      >
        <Row
          symbol={{
            name: broken ? "xmark.circle.fill" : "checkmark.circle.fill",
            color: broken ? "var(--red)" : "var(--green)",
          }}
          title="Demo target"
          value={broken ? "Returning 503" : "Healthy"}
        />
        <RowButton
          title="Break Demo Target"
          tone="destructive"
          disabled={demo.isPending || broken}
          onClick={() => {
            void tapFeedback("medium");
            demo.mutate("break");
          }}
        />
        <RowButton
          title="Fix Demo Target"
          tone="action"
          disabled={demo.isPending || !broken}
          onClick={() => {
            void tapFeedback("medium");
            demo.mutate("fix");
          }}
        />
      </Section>
      {demo.isError ? <ErrorNote error={demo.error} /> : null}
    </div>
  );
}

function About() {
  const health = useHealth();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [confirming, setConfirming] = useState(false);
  return (
    <>
      <Section header="About">
        <Row title="App version" value={APP_VERSION} />
        <Row
          title="API"
          value={health.data ? `Healthy · ${health.data.version}` : health.isError ? "Unreachable" : "Checking…"}
        />
      </Section>
      <Section>
        <RowButton title="Log Out" tone="destructive" center onClick={() => setConfirming(true)} />
      </Section>
      {confirming ? (
        <ConfirmDialog
          title="Log out of Beacon?"
          body="You'll need the password to see your products again. Notifications keep arriving on this device."
          confirmLabel="Log Out"
          onCancel={() => setConfirming(false)}
          onConfirm={() => {
            clearToken();
            qc.clear();
            if ("caches" in window) void caches.delete("beacon-api");
            navigate("/login", { replace: true });
          }}
        />
      ) : null}
    </>
  );
}
