import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Local dev: point /api at a deployed CloudFront URL, e.g. BEACON_API_ORIGIN=https://dxxxx.cloudfront.net
    proxy: { "/api": { target: process.env.BEACON_API_ORIGIN ?? "http://localhost:3000", changeOrigin: true } },
  },
});
