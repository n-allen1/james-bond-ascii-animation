"""Scene 6 (and the fade-out that opens scene 7): a new Bond emerges.   [REFINED reveal]

Same artistic direction as the baseline (scenes/pattinson_baseline.py, git tag pattinson-baseline-v1):
sparse illuminated dots on black, cool steel light, highlights first.  Refinements:

  * IDENTITY EMERGES.  Early on the face keeps the baseline's mysterious low-detail look.  As the light
    band and a top-to-bottom feature sweep travel across him, detail is introduced *only* inside the
    facial-feature regions (eyes, brows, nose, cheekbone, mouth, jaw, hairline - see PORTRAITS in
    config/settings.py).  Around ~3/4 of the scene it peaks and holds ~3-4 s before the title fade.
  * THE WEAPON READS.  The camera starts slightly wider so the long suppressor is in frame while the
    scene is still dark, then pushes in on the face.  A separate, capped, cool-tinted rim layer lifts the
    suppressor, slide + sight, weapon light and gripping hand out of the black; the travelling light band
    "catches" it, it is most legible at the peak, then settles back so the face stays dominant.
  * Nothing else changes: background stays black, overall exposure is not raised.
"""
import math

import numpy as np

from effects import lighting as L
from effects.particles import glow, splat
from effects.transitions import lerp, smootherstep, smoothstep
from renderer.camera import Camera, VIEW_UNITS
from scenes.base import Stage, noise_scale

STEEL = [(0.0, (0.0, 0.0, 0.0)), (0.10, (0.025, 0.05, 0.095)), (0.5, (0.36, 0.50, 0.68)), (1.0, (0.96, 0.98, 1.0))]

# Window width as a fraction of the photo.  Starts wide enough to include the suppressor, ends on the face.
WINDOW_START = 0.68
WINDOW_END = 0.50
CENTER_U_START = 0.50
ANCHOR_U = 0.66          # where the final window sits horizontally (left edge = ANCHOR_U * (1 - WINDOW_END))


class PattinsonScene:
    def __init__(self, st: Stage):
        self.st = st
        p = st.portraits["pattinson"]
        self.p = p
        self.s = max(VIEW_UNITS * st.aspect / p.w, VIEW_UNITS / p.h)      # "cover" scale (units per photo px)
        self.vig = L.vignette(st.ph, st.pw, 0.55, 0.95)
        self.refined = p.photo_detail is not None
        rng = np.random.default_rng(31)
        n = 14
        self.dust = dict(x=rng.uniform(-0.4, 0.4, n), y=rng.uniform(-0.5, 0.5, n), v=rng.uniform(0.01, 0.03, n),
                         sw=rng.uniform(0, 6.28, n))

    # ------------------------------------------------------------------ camera
    def _camera(self, t, pa, pb, fb):
        p, s, st = self.p, self.s, self.st
        e = smootherstep(pa, pb + 3.0, t)          # push-in tail: fixed, independent of the ending length
        W, H = p.w * s, p.h * s
        f = lerp(WINDOW_START, WINDOW_END, e)                              # window width / photo width
        vh = f * W / st.aspect
        left_end = ANCHOR_U * (1 - WINDOW_END)
        u_end = left_end + WINDOW_END / 2
        cx = (lerp(CENTER_U_START, u_end, e) - 0.5) * W
        cy = lerp(0.0, (p.face[1] - 0.5) * H * 0.35, e)
        hw = f * W / 2
        if W / 2 > hw:                                                     # keep the view inside the photo (sideways)
            cx = min(max(cx, -(W / 2 - hw)), W / 2 - hw)
        return Camera(cx, cy, VIEW_UNITS / vh)

    # ------------------------------------------------------------------ render
    def render(self, t):
        st, p = self.st, self.p
        ph, pw = st.ph, st.pw
        pa, pb = st.window("pattinson_reveal")
        fa, fb = st.window("final_title")
        D = pb - pa
        T = t - pa
        cam = self._camera(t, pa, pb, fb)

        photo = p.photo.render(cam, pw, ph, (0, 0), self.s)
        masks = p.masks.render(cam, pw, ph, (0, 0), self.s)
        focus = masks[..., 2]
        feat = p.feat.render(cam, pw, ph, (0, 0), self.s)
        F = feat[..., 0]
        xs, ys = L.coords(ph, pw)

        # --- identity: introduce facial detail gradually, only inside the feature regions -----------
        b = smootherstep(0.42 * D, 0.78 * D, T)
        if b > 0:
            photo = photo * (1 - b) + p.photo_detail.render(cam, pw, ph, (0, 0), self.s) * b
        # the weapon stays subordinate: its specular glints (sight dot, weapon-light lens) and the hand's
        # highlights are held below the face's highlights
        Wm = feat[..., 1]
        hot = np.clip((L.luma(photo) - 0.40) / 0.45, 0, 1)
        photo = photo * (1 - 0.55 * Wm * hot)[..., None]
        lum = L.luma(photo)
        lum = L.box_blur(lum, 1) if ph >= 140 else lum

        # 1. highlights first
        thr = lerp(1.02, 0.50, smootherstep(0.04 * D, 0.32 * D, T))
        vis_h = np.clip((lum - thr) / 0.22, 0, 1)
        vis_h = vis_h * vis_h * (3 - 2 * vis_h)
        vis_h *= smoothstep(0.0, 0.08 * D, T)
        vis_a = 0.07 * smoothstep(0.10 * D, 0.30 * D, T)

        # 2. diagonal blue-silver light band across the face (and over the weapon first)
        axis = xs * 0.80 + ys * 0.60
        s = lerp(-0.55, 0.70, smootherstep(0.22 * D, 0.78 * D, T))
        band = np.exp(-(((axis - s) / 0.17) ** 2)) * smoothstep(0.20 * D, 0.30 * D, T) * (1 - smoothstep(0.78 * D, 0.92 * D, T))
        vis_b = band * (0.30 + 0.70 * focus) * 1.15

        # 3. the eyes
        ex_w = (p.eyes[0] - 0.5) * p.w * self.s
        ey_w = (p.eyes[1] - 0.5) * p.h * self.s
        sx, sy = cam.world_to_screen(ex_w, ey_w, pw, ph)
        spot = L.radial(ph, pw, (sx - pw / 2) / ph, (sy - ph / 2) / ph, 0.11, rx_scale=1.9, power=1.8)
        vis_e = spot * smoothstep(0.52 * D, 0.72 * D, T) * 0.9

        # 3b. feature sweep: a soft scan travels forehead -> jaw; features stay lit once passed
        _, y_top = cam.world_to_screen(0, (p.face[1] - 0.5 - 0.30) * p.h * self.s, pw, ph)
        _, y_bot = cam.world_to_screen(0, (p.face[1] - 0.5 + 0.37) * p.h * self.s, pw, ph)
        scan = lerp((y_top - ph / 2) / ph - 0.05, (y_bot - ph / 2) / ph + 0.06, smootherstep(0.46 * D, 0.76 * D, T))
        rev = np.clip((scan - ys) / 0.07, 0, 1)
        vis_f = F * rev * 0.58

        # 4. exposure settles
        lift = smoothstep(0.60 * D, 0.94 * D, T)
        vis = 1 - (1 - vis_h) * (1 - np.clip(vis_b, 0, 1)) * (1 - vis_e) * (1 - vis_f)
        vis = np.maximum(vis, np.maximum(vis_a, lift))

        warm = np.array([0.80, 0.90, 1.0], np.float32)
        light = vis[..., None] * (warm * (1 - lift) + lift)
        img = photo * light

        # --- the weapon: subordinate rim layer (capped far below the face), caught by the light band ------
        if p.weapon_img is not None:
            wimg = p.weapon_img.render(cam, pw, ph, (0, 0), self.s)
            # faint early silhouette (suppressor in frame) -> eases back as the face takes over ->
            # most legible with the face at the peak -> settles behind the portrait
            gw = 0.55 * smoothstep(0.12 * D, 0.30 * D, T) * (1 - 0.55 * smoothstep(0.48 * D, 0.68 * D, T))                 + 0.62 * smoothstep(0.62 * D, 0.82 * D, T)
            gw *= 1.0 - 0.25 * smoothstep(0.90 * D, 1.0 * D, T)
            catch = band * 0.9                                              # light sweeping across the metal
            img = img + wimg * (gw + catch)[..., None]

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
