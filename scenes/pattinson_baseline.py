"""BASELINE (v1) of Scene 6 - kept for A/B comparison and easy revert (git tag pattinson-baseline-v1).
Select with  --pattinson baseline.  Scene 6 (and the fade-out that opens scene 7): a new Bond emerges.

Reveal order, all driven by lighting on the processed photograph (no fake
animation of the face):
  1. highest-luminance pixels first  -> collar, shirt, gun-metal glints
  2. a blue-silver light band sweeps diagonally across the face
  3. a soft spot finds the eyes
  4. exposure settles to the photograph's own tonal range
The camera pushes in very slowly and keeps drifting while the portrait fades.
"""
import math

import numpy as np

from effects import lighting as L
from effects.particles import glow, splat
from effects.transitions import lerp, smootherstep, smoothstep
from renderer.camera import Camera, VIEW_UNITS
from scenes.base import Stage, noise_scale

STEEL = [(0.0, (0.0, 0.0, 0.0)), (0.10, (0.025, 0.05, 0.095)), (0.5, (0.36, 0.50, 0.68)), (1.0, (0.96, 0.98, 1.0))]


class PattinsonBaseline:
    def __init__(self, st: Stage):
        self.st = st
        p = st.portraits["pattinson"]
        self.p = p
        self.s = max(VIEW_UNITS * st.aspect / p.w, VIEW_UNITS / p.h)      # "cover" scale
        self.vig = L.vignette(st.ph, st.pw, 0.55, 0.95)
        rng = np.random.default_rng(31)
        n = 14
        self.dust = dict(x=rng.uniform(-0.4, 0.4, n), y=rng.uniform(-0.5, 0.5, n), v=rng.uniform(0.01, 0.03, n),
                         sw=rng.uniform(0, 6.28, n))

    def _camera(self, t, pa, pb, fb):
        p, s, st = self.p, self.s, self.st
        e = smootherstep(pa, pb + 3.0, t)          # push-in tail: fixed, independent of the ending length
        z = lerp(1.0, 1.07, e)
        W, H = p.w * s, p.h * s
        fx, fy = max(W - VIEW_UNITS * st.aspect, 0), max(H - VIEW_UNITS, 0)
        base = ((p.anchor[0] - 0.5) * fx, (p.anchor[1] - 0.5) * fy)
        face = ((p.face[0] - 0.5) * W, (p.face[1] - 0.5) * H)
        cx, cy = lerp(base[0], 0.5 * base[0] + 0.5 * face[0], e * 0.6), lerp(base[1], 0.5 * base[1] + 0.5 * face[1], e * 0.6)
        hw, hh = VIEW_UNITS * st.aspect / (2 * z), VIEW_UNITS / (2 * z)      # keep the view inside the photo
        cx = min(max(cx, -(W / 2 - hw)), W / 2 - hw) if W / 2 > hw else 0.0
        cy = min(max(cy, -(H / 2 - hh)), H / 2 - hh) if H / 2 > hh else 0.0
        return Camera(cx, cy, z)

    def render(self, t):
        st = self.st
        ph, pw = st.ph, st.pw
        pa, pb = st.window("pattinson_reveal")
        fa, fb = st.window("final_title")
        D = pb - pa
        T = t - pa
        cam = self._camera(t, pa, pb, fb)

        photo = self.p.photo.render(cam, pw, ph, (0, 0), self.s)
        masks = self.p.masks.render(cam, pw, ph, (0, 0), self.s)
        focus = masks[..., 2]
        lum = L.luma(photo)
        lum = L.box_blur(lum, 1) if ph >= 140 else lum

        # 1. highlights first
        thr = lerp(1.02, 0.50, smootherstep(0.04 * D, 0.32 * D, T))
        vis_h = np.clip((lum - thr) / 0.22, 0, 1)
        vis_h = vis_h * vis_h * (3 - 2 * vis_h)
        vis_h *= smoothstep(0.0, 0.08 * D, T)
        # faint shoulder/outline presence
        vis_a = 0.07 * smoothstep(0.10 * D, 0.30 * D, T)

        # 2. diagonal blue-silver light band across the face
        xs, ys = L.coords(ph, pw)
        axis = xs * 0.80 + ys * 0.60
        s = lerp(-0.55, 0.70, smootherstep(0.22 * D, 0.78 * D, T))
        band = np.exp(-(((axis - s) / 0.17) ** 2)) * smoothstep(0.20 * D, 0.30 * D, T) * (1 - smoothstep(0.78 * D, 0.92 * D, T))
        vis_b = band * (0.30 + 0.70 * focus) * 1.15

        # 3. the eyes
        ex_w = (self.p.eyes[0] - 0.5) * self.p.w * self.s
        ey_w = (self.p.eyes[1] - 0.5) * self.p.h * self.s
        sx, sy = cam.world_to_screen(ex_w, ey_w, pw, ph)
        spot = L.radial(ph, pw, (sx - pw / 2) / ph, (sy - ph / 2) / ph, 0.11, rx_scale=1.9, power=1.8)
        vis_e = spot * smoothstep(0.52 * D, 0.72 * D, T) * 0.9

        # 4. exposure settles
        lift = smoothstep(0.60 * D, 0.94 * D, T)
        vis = 1 - (1 - vis_h) * (1 - np.clip(vis_b, 0, 1)) * (1 - vis_e)
        vis = np.maximum(vis, np.maximum(vis_a, lift))

        warm = np.array([0.80, 0.90, 1.0], np.float32)
        light = vis[..., None] * (warm * (1 - lift) + lift)      # cool light that relaxes to neutral
        img = photo * light

        # grade: steel blue / silver, deep blacks, strong contrast
        img = L.lut_grade(img, STEEL, 0.42)
        img = L.contrast_curve(np.clip(img, 0, 1), 0.28)
        img = img * (0.35 + 0.65 * self.vig[..., None])

        # restrained atmosphere: faint cool haze + a few slow silver motes
        o = t * 2.0
        haze = st.noise.sample(ph, pw, noise_scale(ph, 0.6), o, -o * 0.6)
        img += (np.clip(haze - 0.45, 0, 1) * 0.07 * smoothstep(0.1 * D, 0.5 * D, T))[..., None] * np.array([0.5, 0.65, 0.9], np.float32)
        d = self.dust
        buf = np.zeros((3, ph, pw), np.float32)
        yy = ((d["y"] - t * d["v"] + 0.5) % 1.0 - 0.5)
        xx = d["x"] + 0.02 * np.sin(t * 0.7 + d["sw"])
        br = (0.5 + 0.5 * np.sin(t * 0.9 + d["sw"])) * 0.35 * smoothstep(0.3 * D, 0.7 * D, T)
        splat(buf, xx * ph + pw / 2, yy * ph + ph / 2, np.array([0.7, 0.82, 1.0], np.float32)[None] * br[:, None])
        img += glow(buf, 1, 0.6)

        # fade to black as the title scene begins
        pf0, pf1 = st.ending["portrait_fade"]
        fade = 1 - smoothstep(fa + pf0, fa + pf1, t)
        return img * fade
