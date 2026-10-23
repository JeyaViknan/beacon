import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      strategies: "injectManifest",
      srcDir: "src",
      filename: "sw.ts",
      injectRegister: false, // registered in main.tsx (production only)
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
        theme_color: "#0c1420",
        background_color: "#0c1420",
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
    }),
  ],
  server: {
    // Local dev against a deployed stack: BEACON_API_ORIGIN=https://dxxxx.cloudfront.net npm run dev
    // Or with fake data and no backend: VITE_MOCK=1 npm run dev
    proxy: { "/api": { target: process.env.BEACON_API_ORIGIN ?? "http://localhost:3000", changeOrigin: true } },
  },
});
