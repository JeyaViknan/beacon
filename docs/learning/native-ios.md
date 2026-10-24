# Native iOS app (Capacitor) — interview notes

**Built:** the existing React app packaged as a native iPhone app with Capacitor 8 (`web/ios`, Swift Package Manager): Beacon icon and launch screen, status bar styling, haptic taps, portrait only. The API allows the app's origin (`capacitor://localhost`) via CORS. Signed with a free Apple ID (ADR 0015).

**Why this design:**
- **One codebase, two clients:** the PWA (with Web Push) and the native app share every screen. Native-only code sits behind `isNativeApp()` and is lazy-loaded.
- **Bundled assets, not a remote URL:** the app opens instantly and works on a poor network; only API calls go out.
- **CORS done narrowly:** one extra origin. Preflights still need CloudFront's secret, and real requests still need the JWT. CORS isn't auth; it only lets the app *read* responses.
- **Apple's design language (ADR 0016):** system colours (pure black dark mode), system font, inset grouped lists, Liquid Glass bars, no decorative motion. SF Symbols are exported from the Mac's SF Symbols app at build time and never committed (Apple licenses them for Apple platforms only); the public web app uses look-alikes.
- **No paid program:** native push (APNs) needs Apple's $99/year Developer Program, so alerts come by email and through the web app's push. Adding APNs later is additive: capability + key in SSM + notifier sender.

**Interview questions**
1. *Why Capacitor instead of SwiftUI?* Reuse of a tested UI; a native shell in hours instead of a rewrite in weeks. SwiftUI is the path if native UX becomes the priority.
2. *How does the native app talk to your API?* Cross-origin HTTPS to CloudFront. The API's CORS allows only `capacitor://localhost`, and the JWT is still required.
3. *Why no push in the native app?* APNs requires the paid Apple Developer Program. The design keeps it a drop-in addition rather than a rewrite.
4. *What's the 7-day thing?* Apps signed with a free Personal Team expire after 7 days; reinstall from Xcode.
5. *How did you use SF Symbols without breaking Apple's licence?* Exported at build time on the Mac, only into the iPhone app, never into the public repo or website; the web app has look-alikes behind the same names.
