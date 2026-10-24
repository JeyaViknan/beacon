# ADR 0015 — Native iOS app with Capacitor, on a free Apple ID (alongside the web app)

**Status:** accepted · **Date:** 2026-10-24 · Amends ADR 0001 and HANDOVER §1 (native app was a v1 non-goal; the owner asked for one)

## Context
After using the installed web app, Jeya wanted Beacon as a real native app on the iPhone. The constraints:
- **Native push on iOS means APNs,** which needs Apple's paid Developer Program ($99/year). Jeya chose **not** to pay.
- **Free Apple ID ("Personal Team") apps** can be installed from Xcode onto your own device, but they expire after **7 days**, and the *Push Notifications* capability isn't available to them.
- **Deadline:** the interview is on Monday, so a full SwiftUI rewrite isn't realistic.

## Decision
- **Capacitor 8** wraps the existing React app into a native iOS project (`web/ios/`, Swift Package Manager). Same screens and code; the web assets are bundled **inside** the app.
- **Native touches:** app icon and launch screen (rendered by `scripts/gen_icons.py`), status-bar styling, haptic taps on key actions, portrait only, no Safari UI.
- **API calls:** the app calls the live API cross-origin (`VITE_API_BASE`). The API allows exactly one extra CORS origin, `capacitor://localhost`.
  - Preflights still require CloudFront's secret header.
  - Every real request still needs the JWT.
  - CORS only controls which apps may *read* responses; it isn't authentication.
- **Alerts:** no native push. The native app's Settings says so plainly. Alerts arrive by **email**, and as push through the **installed web app**, which is kept.
- **Web app stays** as the push-capable client and the demo backup.

## Consequences
- The app is reinstalled from Xcode every 7 days: `./scripts/build_ios.sh`, then *Run*.
- Native push later = enrol ($99), add the Push Notifications capability, an APNs key in SSM, and an APNs sender in the notifier. The rest is unchanged.
- One codebase, two clients. Native-only behaviour lives in `web/src/lib/platform.ts` and is loaded lazily, so the web bundle doesn't carry the plugins.
