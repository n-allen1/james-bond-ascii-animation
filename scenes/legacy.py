"""Scenes 4-5: complete darkness, then one point of light becomes 007."""
import math

import numpy as np

from effects import lighting as L
from effects.particles import DigitParticles, glow, splat
from effects.transitions import smoothstep
from scenes.base import Stage

SILVER = np.array([0.82, 0.90, 1.0], np.float32)


class LegacyScene:
    def __init__(self, st: Stage):
        self.st = st
        n = int(min(1600, max(500, st.pw * st.ph * 0.085)))
        self.parts = DigitParticles(st.ph, st.pw, "007", n=n)

    def render(self, t):
        st = self.st
        ph, pw = st.ph, st.pw
        ba, bb = st.window("blackout")
        la, lb = st.window("legacy_007")
        img = np.zeros((ph, pw, 3), np.float32)
        D = lb - la

        # a faint point of silver-white light, only at the very end of the blackout
        pt = smoothstep(bb - 1.5, bb - 0.15, t)
        if pt > 0:
            emit_b = la + 0.30 * D
            form_b = la + 0.55 * D
            pt *= 1 - smoothstep(emit_b, form_b, t)         # the emitter burns out as 007 assembles
            pulse = 0.85 + 0.15 * math.sin(t * 2.4)
            o = self.parts.origin
            buf = np.zeros((3, ph, pw), np.float32)
            splat(buf, np.array([o[0]], np.float32), np.array([o[1]], np.float32), SILVER[None] * pt * pulse * 1.3)
            img += glow(buf, 1, 1.4)
            img += L.radial(ph, pw, 0.0, (o[1] - ph / 2) / ph, 0.035, power=1.6)[..., None] * SILVER * pt * 0.22

        if t >= la - 0.05:
            buf = self.parts.draw(t, la + 0.04 * D, la + 0.30 * D, la + 0.55 * D, la + 0.72 * D, lb)
            glowing = glow(buf, 2, 0.9)
            img += glowing
            # slow halo behind the assembled digits
            form = smoothstep(la + 0.45 * D, la + 0.58 * D, t) * (1 - smoothstep(la + 0.72 * D, la + 0.90 * D, t))
            if form > 0:
                halo = L.box_blur(L.box_blur(np.moveaxis(buf, 0, -1), max(2, ph // 24)), max(2, ph // 24))
                img += halo * 2.2 * form
        return img
