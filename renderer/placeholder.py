"""TEST-ONLY stand-ins used when the real photographs are missing.

These are deliberately abstract shaded mannequins - they are NOT likenesses of
anyone and exist purely so the pipeline, camera and timing can be exercised.
Use  --placeholder  to opt in; the real photos always take precedence.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def _blob(x, y, cx, cy, rx, ry):
    return np.exp(-(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2))


def _head(w, h, cx, cy, a, b, light, key, fill, ambient, rim=None):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    nx, ny = (x - cx) / a, (y - cy) / b
    r2 = nx ** 2 + ny ** 2
    inside = r2 < 1
    nz = np.sqrt(np.clip(1 - r2, 0, 1))
    n = np.stack([nx, ny, nz], -1)
    l = np.asarray(light, np.float32)
    l /= np.linalg.norm(l)
    lam = np.clip((n * l).sum(-1), 0, 1)
    col = ambient[None, None, :] + key[None, None, :] * lam[..., None] ** 1.2
    # features
    dark = (0.55 * _blob(x, y, cx - a * 0.40, cy - b * 0.10, a * 0.22, b * 0.075) +
            0.55 * _blob(x, y, cx + a * 0.40, cy - b * 0.10, a * 0.22, b * 0.075) +
            0.35 * _blob(x, y, cx, cy - b * 0.28, a * 0.85, b * 0.06) +
            0.30 * _blob(x, y, cx, cy + b * 0.52, a * 0.28, b * 0.03) +
            0.25 * _blob(x, y, cx + a * 0.1, cy + b * 0.28, a * 0.12, b * 0.20))
    col = col * (1 - np.clip(dark, 0, 0.85))[..., None]
    col += fill[None, None, :] * _blob(x, y, cx - a * 0.12, cy + b * 0.05, a * 0.10, b * 0.25)[..., None] * 0.25
    return col, inside.astype(np.float32)


def craig_placeholder(w=900, h=1100):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    bg = np.stack([0.02 + 0.03 * y / h, 0.07 + 0.05 * y / h, 0.07 + 0.04 * y / h], -1)
    cx, cy = w * 0.5, h * 0.47
    col, m = _head(w, h, cx, cy, 215, 285, (0.7, -0.3, 0.8),
                   np.array([0.95, 0.62, 0.38]), np.array([0.9, 0.5, 0.3]), np.array([0.06, 0.12, 0.12]))
    img = bg * (1 - m[..., None]) + col * m[..., None]
    # neck + shirt
    sh = np.clip((y - h * 0.80) / 40, 0, 1)[..., None] * np.array([0.45, 0.40, 0.33]) * (0.6 + 0.4 * (x / w))[..., None]
    img = np.where((y > h * 0.80)[..., None], sh, img)
    pil = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    d = ImageDraw.Draw(pil)
    for ex in (cx - 86, cx + 86):                       # blue irises
        d.ellipse([ex - 15, cy - 28 - 9, ex + 15, cy - 28 + 9], fill=(110, 170, 220))
    d.line([(cx - 120, cy - 110), (cx - 70, cy - 75)], fill=(150, 30, 25), width=5)    # "injuries"
    d.line([(cx + 60, cy + 40), (cx + 110, cy + 95)], fill=(130, 25, 20), width=6)
    d.line([(cx - 80, cy + 120), (cx - 40, cy + 150)], fill=(110, 20, 20), width=4)
    return pil.filter(ImageFilter.GaussianBlur(1.2))


def pattinson_placeholder(w=900, h=1100):
    cx, cy = w * 0.5, h * 0.36
    col, m = _head(w, h, cx, cy, 190, 255, (-0.8, -0.3, 0.6),
                   np.array([0.65, 0.72, 0.85]), np.array([0.3, 0.4, 0.55]), np.array([0.015, 0.02, 0.035]))
    img = col * m[..., None]
    pil = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    d = ImageDraw.Draw(pil)
    d.polygon([(cx - 90, cy + 230), (cx + 90, cy + 230), (cx + 420, h * 0.82), (cx + 440, h), (cx - 440, h), (cx - 420, h * 0.82)], fill=(8, 9, 12))
    d.polygon([(cx - 80, cy + 240), (cx + 80, cy + 240), (cx, h * 0.72)], fill=(205, 212, 225))        # collar
    d.polygon([(cx - 70, h * 0.66), (cx, h * 0.69), (cx + 70, h * 0.66), (cx + 70, h * 0.73), (cx, h * 0.70), (cx - 70, h * 0.73)], fill=(22, 24, 30))  # bow tie
    d.rounded_rectangle([cx + 40, h * 0.74, cx + 330, h * 0.80], 18, fill=(38, 42, 52), outline=(120, 135, 160))   # pistol
    d.ellipse([cx + 300, h * 0.745, cx + 345, h * 0.795], fill=(15, 16, 20), outline=(150, 165, 190))
    return pil.filter(ImageFilter.GaussianBlur(1.2))


def craig_wide_placeholder(w=1588, h=741):
    """Abstract sunset gradient with a dark upright bar - NOT a depiction of anyone."""
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    sky = np.stack([0.75 - 0.3 * y / h, 0.55 - 0.25 * y / h, 0.45 - 0.1 * y / h], -1)
    img = sky * (0.6 + 0.4 * np.exp(-(((x - w * 0.8) / 300) ** 2 + ((y - h * 0.5) / 120) ** 2)))[..., None]
    img[int(h * 0.22):int(h * 0.95), int(w * 0.17):int(w * 0.23)] = 0.08
    return Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))


PLACEHOLDERS = {"craig": craig_placeholder, "craig_wide": craig_wide_placeholder, "pattinson": pattinson_placeholder}
