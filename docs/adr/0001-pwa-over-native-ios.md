# ADR 0001 — PWA instead of a native iOS app

**Status:** accepted · **Date:** 2026-10-23

**Context.** Beacon must live on Jeya's iPhone and deliver push alerts, built and demoed within days, at zero cost.

**Decision.** An installable PWA (React + Vite + `vite-plugin-pwa`) served from CloudFront, using Web Push with VAPID keys.

**Why.** iOS 16.4+ supports Web Push for home-screen web apps. No Apple Developer Program fee ($99/yr), no App Store review, and every merge to `main` updates the app instantly through CI.

**Consequences.** Push only works after "Add to Home Screen" and a permission prompt triggered by a user tap. The installed app has its own storage, separate from Safari, so you log in once inside it. A Capacitor wrapper remains possible later (HANDOVER §21).
