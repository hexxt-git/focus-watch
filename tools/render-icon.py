"""Rasterize the focus-watch app icon to a 1024px RGBA PNG.

This is the source of truth for the icon; everything in src-tauri/icons is
generated from its output with `pnpm tauri icon <png>`.

    python3 tools/render-icon.py [out.png]

The mark is a focus frame closing on one subject: Apple's 824pt superellipse on
a 1024pt canvas, four rounded brackets, one filled dot. Every shape is an
analytic signed distance field, so one sample per pixel still antialiases
cleanly and the script needs no imaging library.
"""

import math
import struct
import sys
import zlib

SIZE = 1024
CX = CY = 512.0
A = 412.0          # superellipse half-width (824pt shape on a 1024pt canvas)
N = 5.0            # superellipse exponent
STROKE = 62.0      # bracket stroke width
DOT_R = 86.0

BODY = (0x23, 0x26, 0x2B)
BONE = (0xF2, 0xEF, 0xE9)
AMBER = (0xE7, 0xAC, 0x4A)

# Top-left bracket: vertical segment, quarter arc, horizontal segment.
ARC_C = (312.0, 312.0)
ARC_R = 60.0
SEG_V = (252.0, 372.0, 252.0, 312.0)
SEG_H = (312.0, 252.0, 372.0, 252.0)


def seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    ex, ey = px - (x1 + t * dx), py - (y1 + t * dy)
    return math.hypot(ex, ey)


def bracket_dist(px, py):
    """Distance to the top-left bracket centerline."""
    d = seg_dist(px, py, *SEG_V)
    dh = seg_dist(px, py, *SEG_H)
    if dh < d:
        d = dh
    vx, vy = px - ARC_C[0], py - ARC_C[1]
    if vx <= 0.0 and vy <= 0.0:
        da = abs(math.hypot(vx, vy) - ARC_R)
        if da < d:
            d = da
    return d


def brackets_dist(px, py):
    """Distance to the nearest of the four mirrored brackets."""
    mx = px if px <= CX else 1024.0 - px
    my = py if py <= CY else 1024.0 - py
    return bracket_dist(mx, my)


def coverage(d):
    """Pixel coverage from a signed distance (negative = inside)."""
    a = 0.5 - d
    return 0.0 if a <= 0.0 else (1.0 if a >= 1.0 else a)


def blend(dst, src, alpha):
    return tuple(s * alpha + d * (1.0 - alpha) for d, s in zip(dst, src))


rows = []
half_stroke = STROKE / 2.0
for y in range(SIZE):
    py = y + 0.5
    row = bytearray()
    dy = abs(py - CY)
    sy = (dy / A) ** N
    for x in range(SIZE):
        px = x + 0.5
        # Body: superellipse radius in its own metric, read as a distance.
        sx = (abs(px - CX) / A) ** N
        g = (sx + sy) ** (1.0 / N)
        body_a = coverage((g - 1.0) * A)
        if body_a <= 0.0:
            row += b"\x00\x00\x00\x00"
            continue

        rgb = BODY
        if 190.0 < px < 834.0 and 190.0 < py < 834.0:
            mark_a = coverage(brackets_dist(px, py) - half_stroke)
            if mark_a > 0.0:
                rgb = blend(rgb, BONE, mark_a)
        if 420.0 < px < 604.0 and 420.0 < py < 604.0:
            dot_a = coverage(math.hypot(px - CX, py - CY) - DOT_R)
            if dot_a > 0.0:
                rgb = blend(rgb, AMBER, dot_a)

        row += bytes((int(rgb[0] + 0.5), int(rgb[1] + 0.5), int(rgb[2] + 0.5),
                      int(body_a * 255 + 0.5)))
    rows.append(row)


def chunk(tag, data):
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


raw = b"".join(b"\x00" + bytes(r) for r in rows)
png = (b"\x89PNG\r\n\x1a\n"
       + chunk(b"IHDR", struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0))
       + chunk(b"IDAT", zlib.compress(raw, 9))
       + chunk(b"IEND", b""))

out = sys.argv[1] if len(sys.argv) > 1 else "icon-1024.png"
with open(out, "wb") as fh:
    fh.write(png)
print("wrote", out, len(png), "bytes")
