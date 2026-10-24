"""Render Beacon's app icons (PNG) with no image libraries: signed-distance shapes + zlib.

    python scripts/gen_icons.py

The mark is a live monitoring trace: a flat line, one heartbeat, and a bright dot where the
trace is "now" (the beacon). It is Beacon's own drawing; Apple doesn't allow SF Symbols in app
icons. Writes:
- web/public/icons/*.png: the web app's icons (white trace on iOS green);
- in the native project (web/ios/...): the iOS app icon in its three iOS 18+ appearances
  (default, dark, tinted), and plain launch images in the app's light and dark backgrounds.
The SVG favicon (web/public/favicon.svg) is the same mark, written by hand.
"""

import math
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "public" / "icons"
IOS_ASSETS = ROOT / "web" / "ios" / "App" / "App" / "Assets.xcassets"

# The trace, in 0..1 icon coordinates (y down), and the dot at its leading edge.
TRACE = [
    (0.17, 0.535),
    (0.36, 0.535),
    (0.435, 0.305),
    (0.525, 0.745),
    (0.595, 0.455),
    (0.64, 0.535),
    (0.725, 0.535),
]
DOT = (0.81, 0.535)
STROKE = 0.064  # line width
DOT_R = 0.052

GREEN_TOP, GREEN_BOTTOM = (92, 226, 124), (24, 166, 72)  # the default icon's background
DARK_TOP, DARK_BOTTOM = (44, 44, 46), (8, 8, 9)  # dark appearance background
TRACE_DARK_TOP, TRACE_DARK_BOTTOM = (122, 240, 150), (48, 209, 88)  # systemGreen, lit from above
LIGHT_BG, DARK_BG = (242, 242, 247), (0, 0, 0)  # systemGroupedBackground, for launch images


def clamp(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> list[float]:
    return [a[i] + (b[i] - a[i]) * t for i in range(3)]


def segment_distance(px: float, py: float, a: tuple[float, float], b: tuple[float, float]) -> float:
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    t = clamp(((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def mark_distance(x: float, y: float, scale: float) -> float:
    """Signed distance to the mark (negative inside), scaled about the centre by `scale`."""
    ux, uy = 0.5 + (x - 0.5) / scale, 0.5 + (y - 0.5) / scale
    line = (
        min(segment_distance(ux, uy, TRACE[i], TRACE[i + 1]) for i in range(len(TRACE) - 1))
        - STROKE / 2
    )
    dot = math.hypot(ux - DOT[0], uy - DOT[1]) - DOT_R
    return min(line, dot) * scale


def render(size: int, style: str, scale: float = 1.0) -> bytes:
    """RGBA rows in one style: "green" (the default icon), "dark", "tinted" (grayscale), or
    "badge" (white on clear)."""
    px = 1.0 / size
    rows = bytearray()
    for j in range(size):
        rows.append(0)  # PNG filter: none
        y = (j + 0.5) * px
        for i in range(size):
            x = (i + 0.5) * px
            if style == "green":
                bg = mix(GREEN_TOP, GREEN_BOTTOM, y)
                # A soft highlight across the top, as Apple's icons are lit from above.
                lift = 0.10 * clamp(1 - math.hypot((x - 0.5) * 1.1, y + 0.15) / 0.9)
                bg = [c + (255 - c) * lift for c in bg]
            elif style == "dark":
                bg = mix(DARK_TOP, DARK_BOTTOM, y)
            elif style == "tinted":
                bg = [0.0, 0.0, 0.0]
            else:
                bg = [255.0, 255.0, 255.0]
            alpha = 0.0 if style == "badge" else 1.0

            d = mark_distance(x, y, scale)
            if d < 0.08:
                if style == "green":
                    # Soft shadow under the white mark, a touch below it.
                    sd = mark_distance(x, y - 0.012 * scale, scale)
                    shade = 0.16 * clamp(1 - max(sd, 0.0) / (0.03 * scale))
                    bg = [c * (1 - shade) for c in bg]
                cover = clamp(0.5 - d / px)
                if cover:
                    if style == "dark":
                        ink = mix(TRACE_DARK_TOP, TRACE_DARK_BOTTOM, clamp((y - 0.28) / 0.5))
                    else:
                        ink = [255.0, 255.0, 255.0]
                    bg = [bg[k] * (1 - cover) + ink[k] * cover for k in range(3)]
                    alpha = max(alpha, cover)
            rows += bytes(round(c) for c in bg) + bytes([round(alpha * 255)])
    return bytes(rows)


def solid(size: int, color: tuple[int, int, int]) -> bytes:
    row = b"\x00" + bytes(color) * size
    return row * size


def png(size: int, raw: bytes, *, alpha: bool = True) -> bytes:
    """Encode filtered rows (RGBA, or RGB with alpha=False: iOS app icons must be opaque)."""
    if not alpha and len(raw) == size * (1 + size * 4):
        out = bytearray()
        stride = 1 + size * 4
        for j in range(size):
            row = raw[j * stride : (j + 1) * stride]
            out.append(row[0])
            for i in range(size):
                out += row[1 + i * 4 : 4 + i * 4]
        raw = bytes(out)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    color_type = 6 if alpha else 2  # 8-bit RGBA or RGB
    header = struct.pack(">IIBBBBB", size, size, 8, color_type, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    web = {
        "apple-touch-icon.png": (180, 1.0),
        "icon-192.png": (192, 1.0),
        "icon-512.png": (512, 1.0),
        "maskable-512.png": (512, 0.8),  # the mark inside the maskable safe zone
    }
    for name, (size, scale) in web.items():
        (OUT / name).write_bytes(png(size, render(size, "green", scale), alpha=False))
    (OUT / "badge-72.png").write_bytes(png(72, render(72, "badge", 1.1)))
    print(f"Wrote {len(web) + 1} icons to {OUT}")

    if IOS_ASSETS.exists():
        icons = IOS_ASSETS / "AppIcon.appiconset"
        for name, style in (
            ("AppIcon-1024.png", "green"),
            ("AppIcon-1024-dark.png", "dark"),
            ("AppIcon-1024-tinted.png", "tinted"),
        ):
            (icons / name).write_bytes(png(1024, render(1024, style), alpha=False))
        splash = IOS_ASSETS / "Splash.imageset"
        (splash / "splash-light.png").write_bytes(png(64, solid(64, LIGHT_BG), alpha=False))
        (splash / "splash-dark.png").write_bytes(png(64, solid(64, DARK_BG), alpha=False))
        print(f"Wrote the iOS app icon (default, dark, tinted) and launch images to {IOS_ASSETS}")


if __name__ == "__main__":
    main()
