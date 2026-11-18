"""Pixel frame -> terminal cells.

Primary renderer: BRAILLE.  Each cell carries a 2x4 dot pattern, so a 72x48 stage
has 144x192 addressable dots - 4x the positional detail of half-blocks - while
every visible mark is a *character* on a black background.  Dots are stippled with
a static low-discrepancy threshold (no lattice, no shimmer) and coloured from the
picture under the lit dots, so light literally decides how many characters appear.

  braille  (default)  2x4 stippled dots, true-colour foreground, black background
  blocks              legacy half-block fallback for fonts without Braille glyphs
  glyph               ASCII-letter shape matching (preview/comparison only)

(The ASCII-letter glyph matcher in renderer.glyphs is used by --preview --compare
 to document the comparison; it cannot carry enough likeness at ~70 columns.)
"""
import numpy as np

from renderer.glyphs import Cells, braille_cells

STYLES = {  # name: (sub-pixels across, sub-pixels down) per cell; all sub-pixels are square
    "braille": (2, 4),
    "blocks": (1, 2),
    "glyph": (6, 12),       # ASCII-letter shape matching: stills / comparison only (too slow for 30 fps)
}

_matcher = None


def encode_braille(frame, gamma=0.92):
    return braille_cells(frame.astype(np.float32) / 255.0, gamma=gamma)


def encode_blocks(frame):
    h, w, _ = frame.shape
    f = frame[: h // 2 * 2].reshape(h // 2, 2, w, 3)
    top, bot = f[:, 0], f[:, 1]
    same = (top == bot).all(-1)
    chars = np.where(same, 32, 0x2580).astype(np.uint32)
    return Cells(chars, np.where(same[..., None], bot, top), bot)


def encode_glyph(frame):
    global _matcher
    from renderer.glyphs import GlyphMatcher
    if _matcher is None:
        _matcher = GlyphMatcher(6, 12)
    return _matcher.match(frame.astype(np.float32) / 255.0, bg_mix=0.20, gamma=1.4, shape_w=5, edge_thr=0.008)


ENCODERS = {"braille": encode_braille, "blocks": encode_blocks, "glyph": encode_glyph}


def encode(frame, style="braille"):
    return ENCODERS[style](frame)


def to_mono(cells: Cells) -> Cells:
    """--no-color: collapse colours to greyscale."""
    def g(a):
        l = (a[..., 0] * 0.3 + a[..., 1] * 0.59 + a[..., 2] * 0.11).astype(np.uint8)
        return np.repeat(l[..., None], 3, -1)
    return Cells(cells.chars, g(cells.fg), g(cells.bg))


def apply_text(cells: Cells, items):
    """Blend native terminal text over cells (titles).

    items: iterable of (row, col, char, (r,g,b) 0..1, alpha 0..1).  Any dots under a glyph are
    removed so the lettering stays crisp."""
    for row, col, ch, rgb, alpha in items:
        if alpha <= 0.004 or ch == " ":
            continue
        if not (0 <= row < cells.chars.shape[0] and 0 <= col < cells.chars.shape[1]):
            continue
        base = cells.fg[row, col].astype(np.float32) * (0.35 if cells.chars[row, col] != 32 else 0.0)
        txt = np.asarray(rgb, np.float32) * 255
        cells.chars[row, col] = ord(ch)
        cells.bg[row, col] = 0
        cells.fg[row, col] = base * (1 - alpha) + txt * alpha
    return cells
