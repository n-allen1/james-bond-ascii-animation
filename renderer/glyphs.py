"""Glyph-matching renderer: pictures become *characters*, not coloured blocks.

For every terminal cell we look at a high-resolution patch of the image
(PX x PY pixels) and choose the glyph whose bitmap best explains it:

    patch  ~=  bg  +  s * glyph_bitmap          (least squares, 0 <= s <= 1-bg)

Glyph bitmaps are rasterised from a real monospace font, so strokes such as
| / \\ ( ) _ - o are chosen *because they follow the contour* under the cell,
while dense glyphs (# % @ 8 B) carry shadows and light glyphs (. : ' `) carry
highlights.  Foreground colour is taken from the picture under the ink; the
background stays near black (a faint, smooth tint at most), so no grid of
colour tiles is ever visible.

Two engines share the same interface:
  GlyphMatcher  ASCII/Unicode shape matching (default look)
  braille_cells high-density dot rendering for fine linework
"""
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = (
    "C:/Windows/Fonts/CascadiaMono.ttf", "C:/Windows/Fonts/consola.ttf",
    "DejaVuSansMono.ttf", "Menlo.ttc", "Courier New.ttf",
)
ASCII_SET = "".join(chr(c) for c in range(33, 127))
# a few non-block Unicode strokes that extend the contour vocabulary (only used if the font has them)
EXTRA_SET = "╱╲│─·•"
# Flat / smoothly-shaded areas use a clean tonal ramp...
RAMP_CHARS = " .,:;~-=+*ox%#&8MW@B"
# ...and strong local structure may additionally use contour glyphs that follow the edge.
CONTOUR_CHARS = "|/\\_()[]{}<>^!'`\"1lIiLTJ7?╱╲│─"


@dataclass
class Cells:
    chars: np.ndarray   # (R, C) uint32
    fg: np.ndarray      # (R, C, 3) uint8
    bg: np.ndarray      # (R, C, 3) uint8


def _font(size):
    for f in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(f, size), f
        except OSError:
            continue
    return ImageFont.load_default(size), "default"


@lru_cache(maxsize=4)
def build_atlas(px, py, charset=ASCII_SET + EXTRA_SET, ss=6):
    """Rasterise `charset` into (G, py*px) coverage bitmaps (index 0 = space)."""
    # pick a font size whose line box has the cell's aspect (py/px)
    size = 40
    for _ in range(12):
        font, name = _font(size)
        asc, desc = font.getmetrics()
        w = font.getlength("M")
        ratio = (asc + desc) / w
        if abs(ratio - py / px) < 0.02:
            break
        size = max(8, int(size * 0.5 + size * 0.5 * (py / px) / ratio)) if ratio else size
    asc, desc = font.getmetrics()
    cw, ch = int(round(font.getlength("M"))), asc + desc
    chars = [" "]
    maps = [np.zeros(px * py, np.float32)]
    for c in charset:
        if c in chars:
            continue
        img = Image.new("L", (cw, ch), 0)
        ImageDraw.Draw(img).text((0, 0), c, fill=255, font=font)
        a = np.asarray(img, np.float32)
        if c in EXTRA_SET and a.max() == 0:        # glyph missing in this font
            continue
        small = Image.fromarray(a.astype(np.uint8)).resize((px, py), Image.BOX)
        maps.append(np.asarray(small, np.float32).reshape(-1) / 255.0)
        chars.append(c)
    return "".join(chars), np.stack(maps), name


class GlyphMatcher:
    def __init__(self, px=6, py=12, charset=ASCII_SET + EXTRA_SET, ink_norm=True):
        self.px, self.py = px, py
        self.chars, atlas, self.font_name = build_atlas(px, py, charset)
        self.codes = np.array([ord(c) for c in self.chars], np.uint32)
        if ink_norm:
            # model units: the densest glyph delivers ~0.92 of a full cell.  (A real font's densest
            # glyph covers ~30% of the cell; the backdrop tint in match() supplies the rest.)
            atlas = atlas / (atlas.mean(1).max() / 0.92)
        self.atlas = atlas.astype(np.float32)                    # (G, P)
        self.gg = (atlas ** 2).sum(1).astype(np.float32) + 1e-6
        self.cov = atlas.mean(1).astype(np.float32)
        self.is_ramp = np.array([c in RAMP_CHARS for c in self.chars])
        self.is_contour = np.array([c in CONTOUR_CHARS for c in self.chars])

    # ------------------------------------------------------------------ match
    def match(self, img, bg_mix=0.0, gamma=1.3, a_min=0.85, fg_gain=1.0, exposure=1.0, shape_w=8.0, edge_thr=0.012):
        """img: float (R*py, C*px, 3) in 0..1  ->  Cells.

        Displayed brightness of a glyph pixel = ink * a  (a = foreground brightness, a_min..1).
        For every candidate glyph we set a so that the cell's *mean* tone is reproduced
        (a = mean / coverage, clipped), then score the residual of the whole patch.
        Result: tone comes from coverage x brightness, contours from glyph shape."""
        px, py = self.px, self.py
        H, W, _ = img.shape
        R, C = H // py, W // px
        img = img[: R * py, : C * px]
        lum = img @ np.array([0.2126, 0.7152, 0.0722], np.float32)
        t = np.clip(lum * exposure, 0, 1.2) ** gamma
        tb = t.reshape(R, py, C, px).transpose(0, 2, 1, 3).reshape(R * C, py * px)
        cb = img.reshape(R, py, C, px, 3).transpose(0, 2, 1, 3, 4).reshape(R * C, py * px, 3)
        m = tb.mean(1, keepdims=True)
        if bg_mix > 0:
            mb = m.reshape(R, C)
            k = np.array([0.25, 0.5, 0.25], np.float32)           # 1-cell blur: smooth, never tile-like
            for ax in (0, 1):
                p = np.pad(mb, [(1, 1) if i == ax else (0, 0) for i in range(2)], mode="edge")
                mb = (np.take(p, np.arange(0, mb.shape[ax]), ax) * k[0] + np.take(p, np.arange(1, mb.shape[ax] + 1), ax) * k[1]
                      + np.take(p, np.arange(2, mb.shape[ax] + 2), ax) * k[2])
            b = bg_mix * mb.reshape(-1, 1)
        else:
            b = bg_mix * m
        u = np.clip(tb - b, 0, None)
        mu = np.clip(m - b, 0, None)
        cov = self.cov[None, :]                                    # (1, G) mean ink of each glyph
        a = np.clip(mu / np.maximum(cov, 1e-4), a_min, 1.0)        # (N, G)
        dot = u @ self.atlas.T
        score = -2.0 * a * dot + a * a * self.gg[None, :]
        # penalise tone error explicitly (brightness the glyph can really deliver vs mean target)
        deliver = a * cov
        score = score + shape_w * u.shape[1] * (deliver - mu) ** 2
        var = tb.var(1, keepdims=True)                              # local structure under the cell
        allowed = self.is_ramp[None, :] | (self.is_contour[None, :] & (var > edge_thr))
        score = np.where(allowed, score, 1e9)
        idx = score.argmin(1)
        a_sel = a[np.arange(len(idx)), idx][:, None]

        w = self.atlas[idx]
        wsum = w.sum(1, keepdims=True)
        col_all = cb.mean(1)
        col_ink = (cb * w[..., None]).sum(1) / np.maximum(wsum, 1e-3)
        col = np.where(wsum > 0.05, col_ink, col_all)
        peak = np.maximum(col.max(1, keepdims=True), 1e-3)
        hue = col / peak
        sat_boost = np.clip(peak ** 0.2 * 1.1, 0, 1.15)
        fg = np.clip(hue * a_sel * fg_gain * sat_boost, 0, 1)
        bgc = np.clip(col_all / np.maximum(col_all.max(1, keepdims=True), 1e-3) * b * (0.55 + 0.45 * peak), 0, 1)
        fg = np.where((idx == 0)[:, None], 0, fg)
        chars = self.codes[idx].reshape(R, C)
        return Cells(chars, (fg.reshape(R, C, 3) * 255).astype(np.uint8), (bgc.reshape(R, C, 3) * 255).astype(np.uint8))


# ------------------------------------------------------------------------ braille
_BR = np.array([[1, 8], [2, 16], [4, 32], [64, 128]], np.int32)


@lru_cache(maxsize=1)
def _bayer8():
    m = np.array([[0]])
    while m.shape[0] < 8:
        m = np.block([[4 * m, 4 * m + 2], [4 * m + 3, 4 * m + 1]])
    return ((m + 0.5) / 64).astype(np.float32)


@lru_cache(maxsize=1)
def _blue_noise(n=128, seed=11):
    """Periodic blue-noise-like threshold tile: high-passed white noise, rank-normalised to uniform."""
    rng = np.random.default_rng(seed)
    x = rng.random((n, n))
    for _ in range(3):                                   # a few relaxation passes sharpen the spectrum
        F = np.fft.fft2(x - x.mean())
        fy = np.fft.fftfreq(n)[:, None]
        fx = np.fft.fftfreq(n)[None, :]
        f = np.sqrt(fx * fx + fy * fy)
        F *= np.clip(f / 0.25, 0, 1) ** 1.0              # suppress low frequencies
        x = np.real(np.fft.ifft2(F))
        r = np.argsort(np.argsort(x.ravel())).reshape(n, n)
        x = (r + 0.5) / (n * n)
    return x.astype(np.float32)


def braille_cells(img, gamma=0.8, bg_mix=0.0, fg_gain=1.25):
    """img float (R*4, C*2, 3).  Floyd-Steinberg-free: ordered + local-contrast thresholding."""
    H, W, _ = img.shape
    R, C = H // 4, W // 2
    img = img[: R * 4, : C * 2]
    lum = np.clip(img @ np.array([0.2126, 0.7152, 0.0722], np.float32), 0, 1) ** gamma
    # blue-noise-ish ordered threshold, static (no shimmering between frames)
    # static ordered threshold (Bayer 8x8): clean tonal steps and crisp edges, perfectly stable between
    # frames (error diffusion / noise would twinkle on camera); a faint blue-noise jitter breaks the lattice
    bm = _bayer8()
    thr = np.tile(bm, (H // 8 + 1, W // 8 + 1))[:H, :W]
    bn = _blue_noise()
    thr = np.clip(thr * 0.82 + np.tile(bn, (H // bn.shape[0] + 1, W // bn.shape[1] + 1))[:H, :W] * 0.18, 0, 1)
    dots = (lum > thr * 0.95 + 0.02).astype(np.int32)
    d = dots.reshape(R, 4, C, 2).transpose(0, 2, 1, 3)
    code = (d * _BR).sum((2, 3))
    cb = img.reshape(R, 4, C, 2, 3).transpose(0, 2, 1, 3, 4).reshape(R, C, 8, 3)
    w = d.reshape(R, C, 8, 1).astype(np.float32)
    lit = (cb * w).sum(2) / np.maximum(w.sum(2), 1)
    peak = np.maximum(lit.max(-1, keepdims=True), 1e-3)
    fg = np.clip(lit / peak * np.clip(peak ** 0.35 * 1.1 * fg_gain, 0, 1), 0, 1)
    fg = np.where((code > 0)[..., None], fg, 0)
    chars = np.where(code == 0, 32, 0x2800 + code).astype(np.uint32)
    # Very bright cells (the flash of an explosion, the sun) melt into a solid glow instead of a dot
    # lattice: a backdrop fill that ramps in smoothly above ~72% brightness.  Everything else stays black.
    lm = lum.reshape(R, 4, C, 2).mean((1, 3))
    glowk = np.clip((lm - 0.72) / 0.28, 0, 1) ** 1.6
    cm = cb.mean(2)
    bg = np.clip(cm * glowk[..., None] * 0.95, 0, 1)
    return Cells(chars, (fg * 255).astype(np.uint8), (bg * 255).astype(np.uint8))
