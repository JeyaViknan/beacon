/**
 * Every symbol Beacon draws, by its SF Symbols name (ADR 0016).
 *
 * The iPhone app build exports these from the SF Symbols app on the Mac
 * (scripts/export_sf_symbols.sh -> web/.symbols/, never committed). Everything else
 * (the web app, tests, CI) uses the look-alikes in ./fallback.ts.
 */
export const SYMBOL_NAMES = [
  // Navigation and actions
  "plus",
  "arrow.clockwise",
  "chevron.left",
  "chevron.right",
  "chevron.down",
  "chevron.up.chevron.down",
  "xmark",
  "checkmark",
  "arrow.up.right",
  "square.and.arrow.up",
  "wifi.slash",
  // Tabs
  "waveform.path.ecg",
  "bell.fill",
  "gearshape.fill",
  // Status
  "checkmark.circle.fill",
  "exclamationmark.triangle.fill",
  "xmark.circle.fill",
  "pause.circle.fill",
  "clock.fill",
  // Product
  "bolt.fill",
  "pause.fill",
  "play.fill",
  "trash",
  "globe",
  "chevron.left.forwardslash.chevron.right",
  "link",
  "lock.fill",
  "globe.asia.australia.fill",
  // Settings
  "bell.badge.fill",
  "envelope.fill",
  "phone.fill",
  "timer",
  "paperplane.fill",
  "flask.fill",
  "rectangle.portrait.and.arrow.right",
  // Empty states
  "antenna.radiowaves.left.and.right",
  "checkmark.seal.fill",
] as const;

export type SymbolName = (typeof SYMBOL_NAMES)[number];

/** Inner SVG markup in its own coordinate box; drawn with fill = currentColor. */
export interface SymbolDef {
  viewBox: string;
  body: string;
}
