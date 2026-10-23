import { api } from "./api";

export type PushSupport = "supported" | "needs-install" | "unsupported";

/** VAPID public key (base64url) -> the bytes PushManager.subscribe expects. */
export function urlBase64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
  const padded = (base64 + "=".repeat((4 - (base64.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(padded);
  const bytes = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i);
  return bytes;
}

export function pushSupport(): PushSupport {
  const hasApis = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
  if (hasApis) return "supported";
  // iOS Safari only exposes Web Push inside an installed (home-screen) web app.
  const nav = navigator as Navigator & { standalone?: boolean };
  if (/iPhone|iPad|iPod/.test(nav.userAgent) && nav.standalone !== true) return "needs-install";
  return "unsupported";
}

export function notificationPermission(): NotificationPermission | "unsupported" {
  return "Notification" in window ? Notification.permission : "unsupported";
}

/**
 * Ask for permission, subscribe and register the device with the API.
 * Must be called directly from a tap: iOS rejects permission prompts that are not user-initiated,
 * so requestPermission() runs before any other await.
 */
export async function enablePush(vapidPublicKey: string): Promise<NotificationPermission> {
  const permission = await Notification.requestPermission();
  if (permission !== "granted") return permission;
  if (!vapidPublicKey) throw new Error("This build has no VAPID public key (VITE_VAPID_PUBLIC_KEY).");
  const registration = await navigator.serviceWorker.ready;
  const existing = await registration.pushManager.getSubscription();
  const subscription =
    existing ??
    (await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
    }));
  await api("/push/subscriptions", { method: "POST", body: subscription.toJSON() });
  return permission;
}
