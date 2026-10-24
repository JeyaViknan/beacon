# ADR 0016 — iOS design language, and SF Symbols only in the iPhone app

**Status:** accepted · **Date:** 2026-10-24 · Replaces the "night watch" visual design (navy theme, lamp mark)

## Context
Jeya wanted Beacon to feel like an Apple product on the iPhone: Apple's own icons (SF Symbols, from the SF Symbols app installed on the Mac), the iOS 26 Liquid Glass look, and a dark mode that matches iOS exactly, with no decorative animation. Two constraints:
- **Licensing.** Apple licenses SF Symbols for apps on Apple platforms only, and never in app icons or logos. Beacon's repo and web app are public, so committing exported symbols would put Apple's artwork on a public website and in a public repo.
- **No system font trick.** iOS doesn't draw SF Symbols' private-use characters from its system font in Safari or WKWebView (tested in the iOS Simulator: it shows a placeholder glyph), so the symbols have to be shipped as shapes.

## Decision
- **Apple's system design, applied throughout:**
  - **Colours:** UIKit's dynamic system colours, light and dark. Dark is pure black with `#1C1C1E` cells, the system green/orange/red/blue, and Apple's increased-contrast variants for coloured text in light mode.
  - **Font:** the system font (`-apple-system`), sized to the iOS text styles.
  - **Layout:** inset grouped lists with hairline separators.
  - **Navigation:** large titles that move into the bar on scroll, glass circle bar buttons, and a floating glass tab bar with soft scroll edges.
  - **Controls:** iOS alerts, `UISwitch` and segmented controls.
  - **Motion:** placeholders are still shapes, not shimmer. The only motion left is what iOS itself has: switches, the inline title fading in, press highlights.
- **SF Symbols, iPhone app only.** `scripts/export_sf_symbols.sh` runs on the Mac during `build_ios.sh`:
  1. A small Swift program draws each symbol by name with AppKit and finds the matching glyph in the SF Symbols app's font by comparing renderings. Ties are identical glyphs.
  2. fontTools writes those outlines as SVG paths to `web/.symbols/` (gitignored).
  3. Vite uses them only for the native build.
  
  Everything else (the web app, tests, CI) uses Beacon's own look-alikes in `web/src/symbols/fallback.ts`. Both sets share the names in `names.ts`, so the code says `<Icon name="checkmark.circle.fill" />` either way.
- **App icon is Beacon's own drawing:** a live trace with one heartbeat, ending in the beacon dot. It has the three iOS 18+ appearances (default green, dark, tinted), all rendered by `scripts/gen_icons.py`. The launch screen is plain, in the app's light or dark background, as Apple's guidelines ask.

## Consequences
- The iPhone app shows genuine SF Symbols, and the repo and website stay clean. A Mac without the SF Symbols app still builds the app, with the look-alikes.
- Adding an icon means adding its name to `names.ts` and a look-alike to `fallback.ts`. TypeScript rejects a missing look-alike.
- The web app (still the push-capable client) looks almost the same as the native app; only the icons differ slightly.
