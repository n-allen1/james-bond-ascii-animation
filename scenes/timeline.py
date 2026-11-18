"""Master timeline: layout, scene selection, final grade, quantisation."""
from dataclasses import dataclass

import numpy as np

from config import settings
from effects import lighting as L
from renderer import ascii as A
from scenes.base import Stage
from scenes.craig import CraigScene
from scenes.legacy import LegacyScene
from scenes.pattinson import PattinsonScene
from scenes.titles import TitleScene


@dataclass
class Layout:
    rows: int
    cols: int
    row0: int
    col0: int
    style: str
    sx: int
    sy: int

    @property
    def pw(self):
        return self.cols * self.sx

    @property
    def ph(self):
        return self.rows * self.sy


def compute_layout(term_cols, term_rows, style, quality, aspect, cell_aspect=None, full=False):
    cell_aspect = cell_aspect or settings.CELL_ASPECT
    max_rows = settings.QUALITY[quality]["max_rows"]
    R = term_rows - 1                                   # never touch the last line (no scroll)
    if max_rows:
        R = min(R, max_rows)
    C = round(R * cell_aspect * aspect)
    if C > term_cols:
        C = term_cols
        R = int(C / (cell_aspect * aspect))
    sx, sy = A.STYLES[style]
    R -= R % 2
    C -= C % 2
    return Layout(R, C, (term_rows - R) // 2, (term_cols - C) // 2, style, sx, sy)


_BAYER4 = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], np.float32) + 0.5) / 16


class Timeline:
    def __init__(self, layout: Layout, portraits, brightness=1.0, contrast=1.0, sharpen=0.35,
                 timings=None, peak=None, mono=False):
        kw = {}
        if timings:
            kw["timings"] = timings
        if peak is not None:
            kw["peak"] = peak
        self.st = Stage(layout.pw, layout.ph, layout.cols, layout.rows, portraits, **kw)
        self.layout = layout
        self.brightness, self.contrast, self.sharpen, self.mono = brightness, contrast, sharpen, mono
        self.craig = CraigScene(self.st)
        self.legacy = LegacyScene(self.st)
        self.pattinson = PattinsonScene(self.st)
        self.titles = TitleScene(self.st)
        ph, pw = layout.ph, layout.pw
        self.dither = np.tile(_BAYER4, (ph // 4 + 1, pw // 4 + 1))[:ph, :pw, None]

    def frame(self, t):
        """Float frame (ph, pw, 3) for animation time t."""
        st = self.st
        craig_end = st.window("explosion")[1]
        pat_start = st.window("pattinson_reveal")[0]
        if t < craig_end:
            f = self.craig.render(t)
        elif t < pat_start:
            f = self.legacy.render(t)
        else:
            f = self.pattinson.render(t)
        return f

    def finish(self, f):
        """Sharpen, user brightness/contrast, ordered dither, quantise -> uint8."""
        if self.sharpen > 0 and f.max() > 0.02:
            f = L.sharpen(f, self.sharpen, 1)
        f = np.clip(f, 0, 1)
        if self.brightness != 1.0:
            f = f * self.brightness
        f = L.contrast_curve(np.clip(f, 0, 1), self.contrast - 1.0)
        if self.layout.style == "braille":
            return np.clip(f * 255.0 + 0.5, 0, 255).astype(np.uint8)
        return np.clip(f * 255.0 + self.dither, 0, 255).astype(np.uint8)

    def cells(self, t):
        f8 = self.finish(self.frame(t))
        c = A.encode(f8, self.layout.style)
        A.apply_text(c, self.titles.overlay(t))
        if self.mono:
            c = A.to_mono(c)
        return c
