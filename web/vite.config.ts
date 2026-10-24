import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { defineConfig, type PluginOption } from "vite";
import { VitePWA } from "vite-plugin-pwa";

// BEACON_NATIVE=1 builds the screens for the native iOS app: no service worker or web manifest
// (Capacitor's WKWebView doesn't use them), output in dist-native/ for `cap sync`.
const native = process.env.BEACON_NATIVE === "1";

// The iPhone app draws real SF Symbols when scripts/export_sf_symbols.sh has exported them on
// this Mac; everything else uses Beacon's look-alikes (ADR 0016).
const sfSymbols = fileURLToPath(new URL("./.symbols/sf.generated.ts", import.meta.url));
const symbols = native && existsSync(sfSymbols) ? sfSymbols : fileURLToPath(new URL("./src/symbols/fallback.ts", import.meta.url));

const pwa: PluginOption = VitePWA({
  strategies: "injectManifest",
  srcDir: "src",
  filename: "sw.ts",
  injectRegister: false, // registered in main.tsx (production web build only)
  manifestFilename: "manifest.webmanifest",
  manifest: {
    name: "Beacon",
    short_name: "Beacon",
    description: "Uptime and incidents for everything you've shipped.",
    id: "/",
    start_url: "/",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    theme_color: "#000000",
    background_color: "#000000",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  },
  injectManifest: {
    globPatterns: ["**/*.{js,css,html,svg,png,webmanifest}"],
  },
  devOptions: { enabled: false },
});

export default defineConfig({
  resolve: { alias: { "@symbols": symbols } },
  build: native ? { outDir: "dist-native", emptyOutDir: true } : undefined,
  plugins: [react(), tailwindcss(), ...(native ? [] : [pwa])],
  server: {
    // Local dev against a deployed stack: BEACON_API_ORIGIN=https://dxxxx.cloudfront.net npm run dev
    // Or with fake data and no backend: VITE_MOCK=1 npm run dev
    proxy: { "/api": { target: process.env.BEACON_API_ORIGIN ?? "http://localhost:3000", changeOrigin: true } },
  },
});
