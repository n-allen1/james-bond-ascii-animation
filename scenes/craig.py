"""Scenes 1-3: the last look, the final stand, no time to die (t = 0 .. 21).

  Scene 1  Craig's close-up emerges from darkness (eyes first), near-imperceptible push-in.
  Scene 2  The close-up slowly pulls back into the dark; a smoke-noise dissolve (with a brief dip
           in brightness) carries us to the real wide shot, which then pulls back from Bond's
           upper body to the full composition - sky, mountains, coast and platform.  Two
           different camera set-ups are bridged by a cinematic dissolve, NOT by stretching one
           image into the other.
  Scene 3  The sunset glow swells, missiles streak in, blast, white-out, collapse to black.

Camera zoom/pan is applied to the SOURCE photographs and the result is re-stippled into braille
characters every frame (renderer.ascii), so detail is never magnified after the fact.
"""
import math

import numpy as np

from effects import lighting as L
from effects.explosion import AMBER, Explosion, streak
from effects.particles import glow, splat
from effects.transitions import ease_in, lerp, log_lerp, prog, smootherstep, smoothstep
from renderer.camera import Camera, VIEW_UNITS
from scenes.base import Stage, noise_scale

SMOKE_COL = np.array([0.55, 0.42, 0.30], np.float32)
SPARK_COL = np.array([1.0, 0.50, 0.14], np.float32)

# Wide-shot framing, in fractions of assets/daniel_craig_full_shot.png (1588x741)
WIDE_START = dict(vw=0.17, u=0.205, v=0.40)       # tight on Bond, head tilted to the sky
WIDE_END = dict(vw=0.64, u=0.31, cy_px=-150.0)    # whole composition; Bond on the left third, sky above
SUN_UV = (0.80, 0.52)                              # where the sunset glow sits in the photo
BOND_CHEST_UV = (0.20, 0.48)                       # explosion origin


class CraigScene:
    def __init__(self, st: Stage):
        self.st = st
        self.p = st.portraits["craig"]
        self.w = st.portraits["craig_wide"]
        self.expl = Explosion(st.ph, st.pw, st.noise)
        rng = np.random.default_rng(9)
        n = 9
        self.sp = dict(x=rng.uniform(-0.32, 0.32, n), y=rng.uniform(0.05, 0.45, n),
                       rate=rng.uniform(0.07, 0.15, n), off=rng.uniform(0, 1, n), sw=rng.uniform(0, 6.28, n))

    # ------------------------------------------------------------------ timing
    def _w(self):
        st = self.st
        ra, rb = st.window("craig_reveal")
        pa, pb = st.window("camera_pullback")
        ea, eb = st.window("explosion")
        return ra, rb, pa, pb, ea, eb

    def dissolve_window(self):
        _, _, pa, pb, _, _ = self._w()
        D = pb - pa
        return pa + 0.33 * D, pa + 0.55 * D

    def master_light(self, t):
        ra, rb, *_ = self._w()
        D, T = rb - ra, t - ra
        return 0.20 * smoothstep(0.04 * D, 0.30 * D, T) + 0.80 * smoothstep(0.28 * D, 0.70 * D, T)

    # ------------------------------------------------------------------ cameras
    def cam_portrait(self, t):
        p, st = self.p, self.st
        ra, rb, pa, pb, ea, eb = self._w()
        D = pb - pa
        if t < pa:
            vwf = lerp(p.closeup_w * 1.05, p.closeup_w, smoothstep(ra, pa, t))     # near-imperceptible push-in
            e = 0.0
        else:
            e = smootherstep(pa, pa + 0.45 * D, t)
            vwf = log_lerp(p.closeup_w, 0.95, e)
        vh = vwf * p.w / st.aspect
        ex, ey = (p.eyes[0] - 0.5) * p.w, (p.eyes[1] - 0.5) * p.h
        fx = ((p.face[0] + p.eyes[0]) / 2 - 0.5) * p.w
        cy_close = ey + (0.5 - p.closeup_eye_y) * vh
        cx, cy = lerp(fx, 0.0, e * 0.7), lerp(cy_close, 0.0, e * 0.8)
        return Camera(cx, cy, VIEW_UNITS / vh), (ex, ey), e

    def cam_wide(self, t):
        w, st = self.w, self.st
        ra, rb, pa, pb, ea, eb = self._w()
        da, db = self.dissolve_window()
        e = smootherstep(da, pb, t)
        vwf = log_lerp(WIDE_START["vw"], WIDE_END["vw"], e)
        if t > pb:
            vwf *= 1 + 0.012 * (t - pb)                        # keeps drifting back through the strike
        cx = lerp(WIDE_START["u"], WIDE_END["u"], e) * w.w - w.w / 2
        cy = lerp((WIDE_START["v"] - 0.5) * w.h, WIDE_END["cy_px"], e)
        vh = vwf * w.w / st.aspect
        return Camera(cx, cy, VIEW_UNITS / vh)

    def _uv_to_screen(self, cam, p, u, v):
        sx, sy = cam.world_to_screen((u - 0.5) * p.w, (v - 0.5) * p.h, self.st.pw, self.st.ph)
        return (sx - self.st.pw / 2) / self.st.ph, (sy - self.st.ph / 2) / self.st.ph

    # ------------------------------------------------------------------ layers
    def _portrait(self, t, I):
        st, p = self.st, self.p
        ph, pw = st.ph, st.pw
        ra, rb, pa, pb, ea, eb = self._w()
        cam, (ex_w, ey_w), e = self.cam_portrait(t)
        photo = p.photo.render(cam, pw, ph, (0, 0), 1.0)
        alpha = p.masks.render(cam, pw, ph, (0, 0), 1.0)[..., 0:1]
        sx, sy = cam.world_to_screen(ex_w, ey_w, pw, ph)
        ex, ey = (sx - pw / 2) / ph, (sy - ph / 2) / ph
        D, T = rb - ra, t - ra
        R = lerp(0.085, 1.30, smootherstep(0.10 * D, 0.72 * D, T))
        aniso = lerp(2.5, 1.2, smootherstep(0.10 * D, 0.72 * D, T))
        M = L.radial(ph, pw, ex, ey, R, rx_scale=aniso, power=1.8)
        amb = 0.55 * smoothstep(0.45 * D, 0.80 * D, T)
        flick = 1 + 0.035 * math.sin(2 * math.pi * 0.31 * t) + 0.02 * math.sin(2 * math.pi * 0.83 * t + 1.7)
        Lm = (amb + (1 - amb) * M) * I * flick
        k = smoothstep(0.3 * D, 1.0 * D, T)
        tint = np.array([1.0, 0.80, 0.55], np.float32) * (1 - k) + k
        return photo * alpha * tint * Lm[..., None] * (1 - 0.30 * e)

    def _wide(self, t):
        st, w = self.st, self.w
        ph, pw = st.ph, st.pw
        ra, rb, pa, pb, ea, eb = self._w()
        peak = st.peak
        cam = self.cam_wide(t)
        img = w.photo.render(cam, pw, ph, (0, 0), 1.0) * w.masks.render(cam, pw, ph, (0, 0), 1.0)[..., 0:1]
        sil = smoothstep(peak - 1.6, peak - 0.3, t)                # backlit before the blast
        img = img * (0.85 - 0.30 * sil)
        # the sunset glow swells toward the strike
        sd = smoothstep(pa + 0.55 * (pb - pa), peak - 1.3, t)
        if sd > 0:
            gx, gy = self._uv_to_screen(cam, w, *SUN_UV)
            img = img + L.radial(ph, pw, gx, gy, 0.35 + 0.30 * sd, power=1.5)[..., None] * AMBER * sd * 0.65
        return img, cam

    # ------------------------------------------------------------------ render
    def render(self, t):
        st = self.st
        ph, pw = st.ph, st.pw
        ra, rb, pa, pb, ea, eb = self._w()
        peak = st.peak
        tau = t - peak
        if t >= eb:
            return np.zeros((ph, pw, 3), np.float32)
        I = self.master_light(t)
        da, db = self.dissolve_window()
        dis = smoothstep(da, db, t)

        img = None
        if dis < 1:
            img = self._portrait(t, I)
        cam_w = None
        if dis > 0:
            wide, cam_w = self._wide(t)
            if img is None:
                img = wide
            else:   # smoke-noise dissolve with a brief dip in brightness
                nz = st.noise.sample(ph, pw, noise_scale(ph, 0.30), t * 4.0, -t * 3.0)
                mix = np.clip(dis * 1.7 - 0.35 + (nz - 0.5) * 1.1, 0, 1)
                mix = mix * mix * (3 - 2 * mix)
                dip = 1 - 0.45 * math.sin(math.pi * dis)
                img = (img * (1 - mix[..., None]) + wide * mix[..., None]) * dip
        if cam_w is None:
            cam_w = self.cam_wide(t)

        # grade: warm highlights, teal shadows
        img = L.split_tone(img, (0.00, 0.10, 0.09), (0.12, 0.06, 0.0), 0.16 * min(1.0, I * 1.3))

        # atmosphere: drifting smoke, thicker around the dissolve
        lit = np.clip(L.luma(img) * 1.8, 0, 1)
        sm_a = 0.14 + 0.40 * math.sin(math.pi * dis) + 0.06 * smoothstep(pa, pb, t)
        o = t * 3.2
        n1 = st.noise.sample(ph, pw, noise_scale(ph, 0.45), o * 1.1, -o * 0.9)
        n2 = st.noise.sample(ph, pw, noise_scale(ph, 0.22), -o * 1.7 + 40, -o * 1.3 + 90)
        smoke = np.clip((n1 * 0.65 + n2 * 0.35 - 0.40) * 2.6, 0, 1)
        img = img + (smoke * sm_a * (0.30 + 0.70 * lit) * min(1.0, I * 1.5))[..., None] * SMOKE_COL

        spark_fade = smoothstep(ra + 1.6, ra + 3.0, t) * (1 - smoothstep(db, db + 1.5, t))
        if spark_fade > 0:
            sp = self.sp
            phs = (t * sp["rate"] + sp["off"]) % 1.0
            x = sp["x"] + 0.05 * np.sin(2 * np.pi * (phs * 1.5) + sp["sw"])
            y = sp["y"] - 0.62 * phs
            br = np.sin(np.pi * phs) ** 2 * (0.65 + 0.35 * np.sin(t * 2.3 + sp["sw"]))
            buf = np.zeros((3, ph, pw), np.float32)
            splat(buf, x * ph + pw / 2, y * ph + ph / 2, SPARK_COL[None] * (br * spark_fade * 1.2)[:, None])
            img = img + glow(buf, 1, 0.9)

        # scene 3: missiles, blast, collapse
        if tau > -2.0:
            ox, oy = self._uv_to_screen(cam_w, self.w, *BOND_CHEST_UV)
            for S, delay in (((-0.62, -0.80), 0.0), ((-0.48, -0.88), 0.14), ((-0.75, -0.62), 0.27)):
                u = prog(t, peak - 1.45 + delay, peak - 0.06)
                if 0 < u < 1:
                    hx = S[0] + (ox - S[0]) * u ** 1.8
                    hy = S[1] + (oy - S[1]) * u ** 1.8
                    s_ = streak(ph, pw, (hx, hy), (ox - S[0], oy - S[1]), 0.18 + 0.30 * u, 0.007 + 0.006 * u)
                    img = img + s_[..., None] * np.array([1.0, 0.86, 0.66], np.float32) * (0.5 + 0.9 * u)
            add, dark = self.expl.render(tau, (ox, oy), t)
            amp = 1.5 * smoothstep(-0.6, 0.0, tau) * (1 - smoothstep(0.1, 1.3, tau))   # screen shake, px
            if amp > 0:
                sx = int(round(amp * (math.sin(t * 38.0) * 0.6 + math.sin(t * 53.0 + 1.3) * 0.4)))
                sy = int(round(amp * (math.sin(t * 45.0 + 0.7) * 0.6 + math.sin(t * 31.0) * 0.4)))
                img = np.roll(img, (sy, sx), axis=(0, 1))
            img = img * (1 - dark[..., None]) + add
        img = img * (1 - ease_in(prog(t, eb - 0.75, eb - 0.12), 2.0))
        return img
