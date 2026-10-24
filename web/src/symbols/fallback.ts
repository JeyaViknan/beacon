import type { SymbolDef, SymbolName } from "./names";

/**
 * Beacon's own look-alikes for the SF Symbols it uses. These ship in
 * the public web app and the repo; the iPhone app swaps in the real SF Symbols (ADR 0016).
 */

// Drawn on 0..24, framed at 30 so a 20-unit circle fills 2/3 of the box, as SF Symbols do in
// the exported frame: the two sets render at the same size.
const BOX = "-3 -3 30 30";
const stroke = (d: string, width = 1.8) =>
  `<path d="${d}" fill="none" stroke="currentColor" stroke-width="${width}" stroke-linecap="round" stroke-linejoin="round"/>`;
const fill = (d: string) => `<path d="${d}"/>`;
/** Filled shape with the inner shapes cut out. */
const cut = (d: string) => `<path d="${d}" fill-rule="evenodd"/>`;

const CIRCLE = "M12 2a10 10 0 1 0 0 20a10 10 0 1 0 0-20Z";
const BELL =
  "M12 3a1.5 1.5 0 0 1 1.5 1.5v.3A6 6 0 0 1 18 10.6v3.6l1.6 2.4c.4.7-.1 1.4-.9 1.4H5.3c-.8 0-1.3-.7-.9-1.4L6 14.2v-3.6a6 6 0 0 1 4.5-5.8v-.3A1.5 1.5 0 0 1 12 3ZM9.8 19.3h4.4a2.2 2.2 0 0 1-4.4 0Z";
const GLOBE =
  "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18ZM3 12h18M12 3c2.5 2.6 3.7 5.6 3.7 9s-1.2 6.4-3.7 9M12 3c-2.5 2.6-3.7 5.6-3.7 9s1.2 6.4 3.7 9";
const def = (body: string): SymbolDef => ({ viewBox: BOX, body });

export const SYMBOLS: Record<SymbolName, SymbolDef> = {
  plus: def(stroke("M12 5v14M5 12h14", 2)),
  "arrow.clockwise": def(stroke("M12 4.5a7.5 7.5 0 1 0 7.5 7.5M9.8 2.3 12 4.5 9.8 6.7")),
  "chevron.left": def(stroke("M15 4.5 7.5 12l7.5 7.5", 2.2)),
  "chevron.right": def(stroke("M9 4.5l7.5 7.5L9 19.5", 2.2)),
  "chevron.down": def(stroke("M4.5 9l7.5 7.5L19.5 9", 2.2)),
  "chevron.up.chevron.down": def(stroke("M8 9.5l4-4 4 4M8 14.5l4 4 4-4", 2)),
  xmark: def(stroke("M6 6l12 12M18 6 6 18", 2)),
  checkmark: def(stroke("M5 12.5l4.5 4.5L19 7", 2.2)),
  "arrow.up.right": def(stroke("M7 17 17 7M9 7h8v8")),
  "square.and.arrow.up": def(
    stroke("M12 3v12M8.5 6.5 12 3l3.5 3.5M8.5 10H7a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7a2 2 0 0 0-2-2h-1.5"),
  ),
  "wifi.slash": def(
    stroke("M2.5 9.5a14 14 0 0 1 19 0M5.5 12.8a9.5 9.5 0 0 1 13 0M8.6 16a5 5 0 0 1 6.8 0M12 19.2h.01M4 4l16 16"),
  ),
  "waveform.path.ecg": def(stroke("M2 12h4l2-5 4 11 3-8 2 2h5")),
  "bell.fill": def(fill(BELL)),
  "gearshape.fill": def(
    cut(
      "M22.06 10.33 22.06 13.67 19.68 14.25 19.02 15.84 20.3 17.93 17.93 20.3 15.84 19.02 14.25 19.68 13.67 22.06 10.33 22.06 9.75 19.68 8.16 19.02 6.07 20.3 3.7 17.93 4.98 15.84 4.32 14.25 1.94 13.67 1.94 10.33 4.32 9.75 4.98 8.16 3.7 6.07 6.07 3.7 8.16 4.98 9.75 4.32 10.33 1.94 13.67 1.94 14.25 4.32 15.84 4.98 17.93 3.7 20.3 6.07 19.02 8.16 19.68 9.75ZM12 8.6a3.4 3.4 0 1 0 0 6.8a3.4 3.4 0 1 0 0-6.8Z",
    ),
  ),
  "checkmark.circle.fill": def(cut(`${CIRCLE}M6.7 13.1l1.6-1.6 2.3 2.3 5.2-5.4 1.6 1.6-6.8 7z`)),
  "exclamationmark.triangle.fill": def(
    cut(
      "M12 3.2c.6 0 1.1.3 1.4.8l8 13.9c.6 1-.1 2.3-1.3 2.3H3.9c-1.2 0-1.9-1.3-1.3-2.3l8-13.9c.3-.5.8-.8 1.4-.8ZM11.1 8.6h1.8l-.2 5.9h-1.4zM12 15.6a1.1 1.1 0 1 0 0 2.2a1.1 1.1 0 1 0 0-2.2Z",
    ),
  ),
  "xmark.circle.fill": def(
    cut(
      `${CIRCLE}M9.77 15.85 12 13.63 14.23 15.85 15.85 14.23 13.63 12 15.85 9.77 14.23 8.15 12 10.37 9.77 8.15 8.15 9.77 10.37 12 8.15 14.23Z`,
    ),
  ),
  "pause.circle.fill": def(cut(`${CIRCLE}M9 8h2v8H9zM13 8h2v8h-2z`)),
  "clock.fill": def(cut(`${CIRCLE}M11.2 6.5h1.6v5.2h3.5v1.6h-5.1z`)),
  "bolt.fill": def(fill("M13.5 2.5 5.5 13.5h5.5l-1 8 8-11H12.5z")),
  "pause.fill": def(fill("M7.5 5h2.5a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H7.5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1ZM14 5h2.5a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H14a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Z")),
  "play.fill": def(fill("M8 4.8v14.4c0 .8.9 1.3 1.6.8l11-7.2c.6-.4.6-1.2 0-1.6l-11-7.2C8.9 3.5 8 4 8 4.8Z")),
  trash: def(
    stroke(
      "M4 6.5h16M9.5 6.5V4.8c0-.7.5-1.3 1.2-1.3h2.6c.7 0 1.2.6 1.2 1.3v1.7M6 6.5l1 12.6c.1 1 .9 1.9 2 1.9h6c1.1 0 1.9-.9 2-1.9l1-12.6M10 10.5v6.5M14 10.5v6.5",
      1.6,
    ),
  ),
  globe: def(stroke(GLOBE, 1.5)),
  "chevron.left.forwardslash.chevron.right": def(stroke("M7.5 7 2.5 12l5 5M16.5 7l5 5-5 5M14 4.5l-4 15")),
  link: def(stroke("M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1")),
  "lock.fill": def(
    fill("M6 10.5h12a1.5 1.5 0 0 1 1.5 1.5v7.5A1.5 1.5 0 0 1 18 21H6a1.5 1.5 0 0 1-1.5-1.5V12A1.5 1.5 0 0 1 6 10.5Z") +
      stroke("M8 10.5V7.5a4 4 0 0 1 8 0v3", 2),
  ),
  "globe.asia.australia.fill": def(stroke(GLOBE, 1.5)),
  "bell.badge.fill": def(fill(BELL) + fill("M19 2a2.6 2.6 0 1 0 0 5.2A2.6 2.6 0 1 0 19 2Z")),
  "envelope.fill": def(
    cut(
      "M4 5.5h16A1.5 1.5 0 0 1 21.5 7v10a1.5 1.5 0 0 1-1.5 1.5H4A1.5 1.5 0 0 1 2.5 17V7A1.5 1.5 0 0 1 4 5.5ZM3.4 7.4 12 13.4l8.6-6v1.8L12 15.2 3.4 9.2z",
    ),
  ),
  "phone.fill": def(
    fill(
      "M6.6 3.3l2.2-.3c.6-.1 1.1.2 1.3.8l1 2.9c.2.5 0 1.1-.4 1.4L9.3 9.3a12 12 0 0 0 5.4 5.4l1.2-1.4c.3-.4.9-.6 1.4-.4l2.9 1c.6.2.9.7.8 1.3l-.3 2.2c-.1.8-.8 1.3-1.6 1.3A15.5 15.5 0 0 1 5.3 4.9c0-.8.5-1.5 1.3-1.6Z",
    ),
  ),
  timer: def(stroke("M12 3.5a8.5 8.5 0 1 1-6 2.5M12 3.5V7M12 12 8 8")),
  "paperplane.fill": def(fill("M20.6 3.4 2.9 10.6c-.7.3-.6 1.2.1 1.4l6.6 2 2 6.6c.2.7 1.1.8 1.4.1l7.6-17.3Z")),
  "flask.fill": def(
    stroke("M9 3h6M10 3v6.2L4.6 18.4c-.6 1.1.2 2.6 1.5 2.6h11.8c1.3 0 2.1-1.5 1.5-2.6L14 9.2V3", 1.6) +
      fill("M7 15.5h10l1.7 2.9c.3.6-.1 1.3-.8 1.3H6.1c-.7 0-1.1-.7-.8-1.3Z"),
  ),
  "rectangle.portrait.and.arrow.right": def(stroke("M14 4.5H7a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h7M11 12h10M18 8.5l3.5 3.5-3.5 3.5")),
  "antenna.radiowaves.left.and.right": def(
    stroke("M12 13.5V21M9 8.5a5 5 0 0 0 0 7M15 8.5a5 5 0 0 1 0 7M6 5.5a9 9 0 0 0 0 13M18 5.5a9 9 0 0 1 0 13", 1.6) +
      fill("M12 10.3a1.7 1.7 0 1 0 0 3.4a1.7 1.7 0 1 0 0-3.4Z"),
  ),
  "checkmark.seal.fill": def(
    cut(
      "M12 1.8 14.3 3.4 17.1 3.17 18.29 5.71 20.83 6.9 20.6 9.7 22.2 12 20.6 14.3 20.83 17.1 18.29 18.29 17.1 20.83 14.3 20.6 12 22.2 9.7 20.6 6.9 20.83 5.71 18.29 3.17 17.1 3.4 14.3 1.8 12 3.4 9.7 3.17 6.9 5.71 5.71 6.9 3.17 9.7 3.4ZM6.7 13.1l1.6-1.6 2.3 2.3 5.2-5.4 1.6 1.6-6.8 7z",
    ),
  ),
};
