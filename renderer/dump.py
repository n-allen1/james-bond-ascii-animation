"""Rasterise Cells to a PNG using a real monospace font, to inspect frames
without a live terminal (approximates what Windows Terminal draws).

Braille is drawn as dots and the half/quadrant blocks geometrically; every
other glyph is drawn with the same font the glyph matcher used.
"""
import numpy as np
from PIL import Image, ImageDraw

from renderer.glyphs import _font

_QUAD = {" ": 0, "▘": 1, "▝": 2, "▀": 3, "▖": 4, "▌": 5, "▞": 6, "▛": 7,
         "▗": 8, "▚": 9, "▐": 10, "▜": 11, "▄": 12, "▙": 13, "▟": 14, "█": 15}
_BR = [(0, 0, 1), (0, 1, 2), (0, 2, 4), (1, 0, 8), (1, 1, 16), (1, 2, 32), (0, 3, 64), (1, 3, 128)]


def cells_to_image(cells, cw=10, ch=20, font_size=None):
    R, C = cells.chars.shape
    px = np.repeat(np.repeat(cells.bg, ch, 0), cw, 1).astype(np.uint8)
    img = Image.fromarray(px)
    d = ImageDraw.Draw(img)
    size = font_size or int(round(ch * 0.82))
    font, _ = _font(size)
    asc, desc = font.getmetrics()
    ox = max(0, (cw - font.getlength("M")) / 2)
    oy = max(0, (ch - (asc + desc)) / 2)
    for r in range(R):
        for c in range(C):
            cp = int(cells.chars[r, c])
            if cp == 32:
                continue
            chr_ = chr(cp)
            fg = tuple(int(v) for v in cells.fg[r, c])
            x, y = c * cw, r * ch
            if chr_ in _QUAD:
                m = _QUAD[chr_]
                for bit, (qx, qy) in ((1, (0, 0)), (2, (1, 0)), (4, (0, 1)), (8, (1, 1))):
                    if m & bit:
                        d.rectangle([x + qx * cw // 2, y + qy * ch // 2, x + (qx + 1) * cw // 2 - 1, y + (qy + 1) * ch // 2 - 1], fill=fg)
            elif 0x2800 <= cp <= 0x28FF:
                code = cp - 0x2800
                rad = max(1.0, cw / 5.2)
                for dx, dy, bit in _BR:
                    if code & bit:
                        cx, cy = x + cw * (0.30 + 0.40 * dx), y + ch * (0.13 + 0.245 * dy)
                        d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=fg)
            else:
                d.text((x + ox, y + oy), chr_, fill=fg, font=font)
    return img
