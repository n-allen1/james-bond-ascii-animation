"""Lighting, grading and noise helpers operating on float32 frames (H, W, 3, 0..1)."""
from functools import lru_cache

import numpy as np


# ---------------------------------------------------------------- geometry
@lru_cache(maxsize=8)
def coords(ph, pw):
    """Pixel-centre coordinates in units of frame height, origin at centre."""
    xs = (np.arange(pw, dtype=np.float32) + 0.5 - pw / 2) / ph
    ys = (np.arange(ph, dtype=np.float32) + 0.5 - ph / 2) / ph
    return xs[None, :], ys[:, None]


def radial(ph, pw, cx, cy, radius, rx_scale=1.0, power=2.0):
    """Soft blob, 1 at (cx, cy) falling to ~0 at `radius` (frame-height units)."""
    xs, ys = coords(ph, pw)
    d = np.sqrt(((xs - cx) / rx_scale) ** 2 + (ys - cy) ** 2) / max(radius, 1e-4)
    return np.exp(-(d ** power)).astype(np.float32)


def vignette(ph, pw, strength=0.5, size=0.9):
    xs, ys = coords(ph, pw)
    d = np.sqrt((xs * 1.15) ** 2 + ys ** 2) / size
    return (1.0 - strength * np.clip(d, 0, 1.6) ** 2.4).clip(0, 1).astype(np.float32)


# ---------------------------------------------------------------- colour
def luma(img):
    return img[..., 0] * 0.2126 + img[..., 1] * 0.7152 + img[..., 2] * 0.0722


def lut_grade(img, stops, amount=1.0):
    """Map luminance through colour `stops` [(lum, (r,g,b)), ...] and blend."""
    lum = luma(img)
    xs = [s[0] for s in stops]
    mapped = np.stack([np.interp(lum, xs, [s[1][c] for s in stops]) for c in range(3)], -1)
    return img + (mapped.astype(np.float32) - img) * amount


def split_tone(img, shadow, highlight, amount=0.3):
    """Tint shadows toward `shadow` and highlights toward `highlight`."""
    lum = luma(img)[..., None]
    sh = np.asarray(shadow, np.float32)
    hi = np.asarray(highlight, np.float32)
    tint = sh * (1 - lum) ** 2 + hi * lum ** 2
    return img + tint * amount * (0.25 + 0.75 * (1 - np.abs(lum * 2 - 1)))


def contrast_curve(img, amount):
    """Black/white-preserving S-curve (amount > 0 more contrast)."""
    if abs(amount) < 1e-3:
        return img
    s = img * img * (3 - 2 * img)
    return img + amount * (s - img)


def box_blur(a, r):
    """Separable box blur on (H, W[, C]) arrays, edge-clamped."""
    if r < 1:
        return a
    out = a
    for axis in (0, 1):
        pad = [(0, 0)] * a.ndim
        pad[axis] = (r + 1, r)
        p = np.pad(out, pad, mode="edge")
        c = np.cumsum(p, axis=axis, dtype=np.float32)
        n = out.shape[axis]
        hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
        lo = np.take(c, np.arange(0, n), axis=axis)
        out = (hi - lo) / (2 * r + 1)
    return out


def sharpen(img, amount=0.4, radius=1):
    if amount <= 0:
        return img
    y = luma(img)
    target = y + (y - box_blur(y, radius)) * amount
    gain = np.clip((target + 0.02) / (y + 0.02), 0.5, 1.9)   # scale, don't add: hue is preserved
    return np.clip(img * gain[..., None], 0, 1.5)


def bloom(img, threshold=0.7, strength=0.35, radius=3):
    bright = np.clip(img - threshold, 0, None)
    return img + box_blur(box_blur(bright, radius), radius) * strength


# ---------------------------------------------------------------- noise
class NoiseField:
    """Periodic fractal noise texture sampled with bilinear filtering.

    Built from FFT-filtered white noise, so it tiles seamlessly and drifting
    through it is a pure function of time (scene rendering is random-access).
    """

    def __init__(self, seed=1, size=256, slope=1.7):
        rng = np.random.default_rng(seed)
        f = np.fft.fftfreq(size)[:, None] ** 2 + np.fft.rfftfreq(size)[None, :] ** 2
        f[0, 0] = 1
        spec = (rng.normal(size=f.shape) + 1j * rng.normal(size=f.shape)) / (f ** (slope / 2))
        spec[0, 0] = 0
        tex = np.fft.irfft2(spec, s=(size, size)).astype(np.float32)
        tex = (tex - tex.min()) / (tex.max() - tex.min())
        self.tex, self.n = tex, size

    def sample(self, ph, pw, scale, ox, oy):
        """`scale`: texture pixels per output pixel; (ox, oy): texture offset."""
        n, t = self.n, self.tex
        xs = ox + np.arange(pw) * scale
        ys = oy + np.arange(ph) * scale
        x0 = np.floor(xs).astype(int)
        y0 = np.floor(ys).astype(int)
        fx = (xs - x0).astype(np.float32)[None, :]
        fy = (ys - y0).astype(np.float32)[:, None]
        x0 %= n
        y0 %= n
        x1 = (x0 + 1) % n
        y1 = (y0 + 1) % n
        a = t[np.ix_(y0, x0)]
        b = t[np.ix_(y0, x1)]
        c = t[np.ix_(y1, x0)]
        d = t[np.ix_(y1, x1)]
        return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy
