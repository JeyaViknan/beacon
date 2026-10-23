/// <reference lib="webworker" />
// Service worker (vite-plugin-pwa injectManifest): app-shell precache, network-first API cache
// for an offline view, and Web Push display + click handling.
import { clientsClaim } from "workbox-core";
import { cleanupOutdatedCaches, createHandlerBoundToURL, precacheAndRoute, type PrecacheEntry } from "workbox-precaching";
import { NavigationRoute, registerRoute } from "workbox-routing";
import { NetworkFirst } from "workbox-strategies";

declare const self: ServiceWorkerGlobalScope & { __WB_MANIFEST: (string | PrecacheEntry)[] };

interface PushPayload {
  title: string;
  body: string;
  url: string;
  tag: string;
}

void self.skipWaiting();
clientsClaim();
cleanupOutdatedCaches();
precacheAndRoute(self.__WB_MANIFEST);

// Client-side routes (/p/123, /settings) load the precached shell, even offline.
registerRoute(new NavigationRoute(createHandlerBoundToURL("/index.html"), { denylist: [/^\/api\//] }));

// API reads: always try the network; fall back to the last good response when offline.
// Only 200 responses are cached (Workbox default), so errors and 401s never stick.
registerRoute(
  ({ url, request }) => url.origin === self.location.origin && url.pathname.startsWith("/api/") && request.method === "GET",
  new NetworkFirst({ cacheName: "beacon-api", networkTimeoutSeconds: 8 }),
);

function parse(event: PushEvent): PushPayload {
  const fallback: PushPayload = { title: "Beacon", body: "", url: "/", tag: "beacon" };
  try {
    return { ...fallback, ...(event.data?.json() as Partial<PushPayload>) };
  } catch {
    return { ...fallback, body: event.data?.text() ?? "" };
  }
}

// iOS revokes push permission from apps that receive a push without showing a notification,
// so every push shows one.
self.addEventListener("push", (event) => {
  const data = parse(event);
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      tag: data.tag, // a RECOVERED replaces the DOWN for the same product
      data: { url: data.url },
      icon: "/icons/icon-192.png",
      badge: "/icons/badge-72.png",
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = new URL((event.notification.data as { url?: string } | null)?.url ?? "/", self.location.origin).href;
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      for (const client of windows) {
        await client.focus();
        await client.navigate(target);
        return;
      }
      await self.clients.openWindow(target);
    })(),
  );
});
