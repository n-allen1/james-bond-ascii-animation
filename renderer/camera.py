"""Virtual camera.  Zoom/pan are applied to SOURCE images (via mip-mapped affine
resampling) and the result is re-rendered at terminal resolution - characters
are never enlarged after the fact.

World units: at zoom 1 the stage is VIEW_UNITS tall.
"""
import math
from dataclasses import dataclass

import numpy as np
from PIL import Image

VIEW_UNITS = 1000.0


@dataclass
class Camera:
    cx: float = 0.0
    cy: float = 0.0
    zoom: float = 1.0

    def units_per_pixel(self, ph, depth=1.0):
        return VIEW_UNITS / ((self.zoom ** depth) * ph)

    def world_to_screen(self, wx, wy, pw, ph, depth=1.0):
        k = self.units_per_pixel(ph, depth)
        return (wx - self.cx * depth) / k + pw / 2, (wy - self.cy * depth) / k + ph / 2


class MipImage:
    """Image pyramid (PIL).  Mode RGBA images must be premultiplied."""

    def __init__(self, img: Image.Image):
        self.levels = [img]
        while min(self.levels[-1].size) > 16:
            w, h = self.levels[-1].size
            if img.mode == "RGBA":
                # Pillow's resize() un-/re-premultiplies RGBA, which corrupts data that is
                # ALREADY premultiplied (colour > alpha at edges).  Exact 2x2 box filter instead.
                a = np.asarray(self.levels[-1], np.float32)[: h // 2 * 2, : w // 2 * 2]
                a = a.reshape(h // 2, 2, w // 2, 2, 4).mean((1, 3))
                self.levels.append(Image.fromarray(np.rint(a).astype(np.uint8), "RGBA"))
            else:
                self.levels.append(self.levels[-1].resize((max(1, w // 2), max(1, h // 2)), Image.LANCZOS))
        self.size = img.size
        self.mode = img.mode

    def render(self, cam: Camera, pw, ph, pos=(0.0, 0.0), scale=1.0, depth=1.0, resample=Image.BICUBIC):
        """Sample into a float32 (ph, pw, channels) array in 0..1.

        pos   world position of the image centre
        scale world units per source pixel
        """
        k = cam.units_per_pixel(ph, depth)
        a0 = k / scale                                  # source px per output px
        m = min(len(self.levels) - 1, max(0, int(math.floor(math.log2(max(a0, 1e-6))))))
        lvl = self.levels[m]
        f = 2.0 ** m
        a = a0 / f
        iw, ih = lvl.size
        cx = cam.cx * depth
        cy = cam.cy * depth
        c = ((cx - pos[0]) + (0.5 - pw / 2) * k) / (scale * f) + iw / 2
        d = ((cy - pos[1]) + (0.5 - ph / 2) * k) / (scale * f) + ih / 2
        out = lvl.transform((pw, ph), Image.AFFINE, (a, 0, c, 0, a, d), resample=resample)
        return np.asarray(out, dtype=np.float32) / 255.0


def over(dst, src_premul, alpha):
    """Premultiplied 'over' composite."""
    return src_premul + dst * (1.0 - alpha[..., None])
