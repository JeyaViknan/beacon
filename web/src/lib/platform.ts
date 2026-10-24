// Runtime platform: the same React app runs as the web app (PWA) and inside the native iOS app
// (Capacitor). Native-only plugins are loaded lazily so the web bundle never pays for them.
import { Capacitor } from "@capacitor/core";

export function isNativeApp(): boolean {
  return Capacitor.isNativePlatform();
}

/** Base for API calls: "" for the web app (same origin), the CloudFront URL in the native app. */
export const API_BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

/** A light haptic tap on native; nothing on the web. Never throws. */
export async function tapFeedback(style: "light" | "medium" = "light"): Promise<void> {
  if (!isNativeApp()) return;
  try {
    const { Haptics, ImpactStyle } = await import("@capacitor/haptics");
    await Haptics.impact({ style: style === "medium" ? ImpactStyle.Medium : ImpactStyle.Light });
  } catch {
    // Haptics are a nicety; ignore devices or simulators without them.
  }
}

/** Native shell setup: light status-bar text over the app's dark header, then hide the splash. */
export async function initNativeShell(): Promise<void> {
  if (!isNativeApp()) return;
  try {
    const [{ StatusBar, Style }, { SplashScreen }] = await Promise.all([
      import("@capacitor/status-bar"),
      import("@capacitor/splash-screen"),
    ]);
    const light = window.matchMedia?.("(prefers-color-scheme: light)").matches ?? false;
    await StatusBar.setStyle({ style: light ? Style.Light : Style.Dark });
    await SplashScreen.hide({ fadeOutDuration: 200 });
  } catch {
    // If a plugin is unavailable the app still works; the splash auto-hides on its own timeout.
  }
}
