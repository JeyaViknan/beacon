"""Render Beacon's app icons (PNG) with no image libraries: signed-distance shapes + zlib.

    python scripts/gen_icons.py

The mark is a lamp with two beams sweeping out to the sides, on the app's night-navy
background. Writes web/public/icons/*.png. The SVG favicon is drawn by hand (web/public).
"""

import math
import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "web" / "public" / "icons"

BG = (12, 20, 32)
BEAM = (255, 233, 176)
CORE = (255, 247, 226)
RING = (255, 214, 138)


def clamp(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def blend(dst: list[float], color: tuple[int, int, int], alpha: float) -> None:
    for i in range(3):
        dst[i] = dst[i] * (1 - alpha) + color[i] * alpha


def render(size: int, scale: float = 1.0, transparent_bg: bool = False) -> bytes:
    """``scale`` < 1 shrinks the mark towards the centre (maskable safe zone)."""
    px = 1.0 / size
    cx, cy = 0.5, 0.53
    core_r = 0.092 * scale
    ring_in, ring_out = 0.108 * scale, 0.132 * scale
    half_angle = math.radians(13)
    beam_len = 0.47 * scale
    rows = bytearray()
    for j in range(size):
        rows.append(0)  # PNG filter: none
        y = (j + 0.5) * px
        for i in range(size):
            x = (i + 0.5) * px
            color = [float(c) for c in BG]
            alpha_out = 0.0 if transparent_bg else 1.0
            dx, dy = x - cx, cy - y
            d = math.hypot(dx, dy)

            # Beams: wedges to the left and right, fading with distance.
            theta = abs(math.atan2(dy, dx))
            off = min(theta, math.pi - theta)  # angle from the horizontal axis
            edge = (half_angle - off) * d / px  # ~pixels inside the wedge edge
            if d > core_r and d < beam_len:
                fade = 1 - (d - core_r) / (beam_len - core_r)
                a = 0.78 * fade * fade * clamp(edge + 0.5)
                if a > 0:
                    blend(color, BEAM, a)
                    alpha_out = max(alpha_out, a)

            # Soft glow around the lamp.
            glow = 0.35 * math.exp(-max(0.0, d - core_r) / (0.05 * scale))
            blend(color, RING, glow)
            alpha_out = max(alpha_out, glow)

            # Lens ring and core (anti-aliased by signed distance).
            ring_cov = clamp(
                0.5 - (abs(d - (ring_in + ring_out) / 2) - (ring_out - ring_in) / 2) / px
            )
            if ring_cov:
                blend(color, RING, ring_cov * 0.9)
                alpha_out = max(alpha_out, ring_cov)
            core_cov = clamp(0.5 - (d - core_r) / px)
            if core_cov:
                blend(color, CORE, core_cov)
                alpha_out = max(alpha_out, core_cov)

            rows += bytes(round(c) for c in color) + bytes([round(alpha_out * 255)])
    return bytes(rows)


def render_badge(size: int) -> bytes:
    """Monochrome notification badge: white lamp + beams on transparent."""
    px = 1.0 / size
    rows = bytearray()
    for j in range(size):
        rows.append(0)
        y = (j + 0.5) * px
        for i in range(size):
            x = (i + 0.5) * px
            dx, dy = x - 0.5, 0.5 - y
            d = math.hypot(dx, dy)
            theta = abs(math.atan2(dy, dx))
            off = min(theta, math.pi - theta)
            a = clamp(0.5 - (d - 0.16) / px)
            if 0.2 < d < 0.48:
                a = max(a, clamp((math.radians(16) - off) * d / px + 0.5) * (1 - (d - 0.2) / 0.28))
            rows += bytes([255, 255, 255, round(a * 255)])
    return bytes(rows)


def png(size: int, raw: bytes) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)  # 8-bit RGBA
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    targets = {
        "apple-touch-icon.png": (180, 1.0),
        "icon-192.png": (192, 1.0),
        "icon-512.png": (512, 1.0),
        "maskable-512.png": (512, 0.78),
    }
    for name, (size, scale) in targets.items():
        (OUT / name).write_bytes(png(size, render(size, scale)))
    (OUT / "badge-72.png").write_bytes(png(72, render_badge(72)))
    print(f"Wrote {len(targets) + 1} icons to {OUT}")


if __name__ == "__main__":
    main()
