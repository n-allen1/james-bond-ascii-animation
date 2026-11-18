"""Portrait loading and the still-image processing passes.

Pipeline (see README):  photo -> crop/frame -> tone + local contrast ->
structural detail (face-weighted) -> masks.  Character mapping happens later,
in renderer.ascii, after the camera has re-sampled the processed image.
"""
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from config import settings
from effects.lighting import box_blur, luma, sharpen
from renderer.camera import MipImage

ASSETS = Path(__file__).resolve().parent.parent / "assets"
MAX_SOURCE = 1800


class MissingPhoto(Exception):
    pass


@dataclass
class Portrait:
    name: str
    photo: MipImage          # processed RGB
    masks: MipImage          # R: rect alpha  G: head-ellipse alpha  B: face focus
    w: int
    h: int
    face: tuple
    eyes: tuple
    face_w: float
    anchor: tuple
    placeholder: bool
    source: str
    closeup_w: float = 0.0
    closeup_eye_y: float = 0.4
    photo_detail: object = None   # MipImage: photo with extra definition inside the feature regions
    weapon_img: object = None     # MipImage: capped, cool-tinted weapon rim layer (additive)
    feat: object = None           # MipImage: R = feature mask


def find_photo(name):
    for stem in settings.PORTRAITS[name]["files"]:
        for ext in settings.ASSET_EXTENSIONS:
            p = ASSETS / f"{stem}{ext}"
            if p.exists():
                return p
    return None


def _autoframe(img):
    """Optional OpenCV Haar face detection (pip install opencv-python-headless).
    Returns (face_cx, face_cy, face_w, eyes_y) in source-normalised units or None."""
    try:
        import cv2
    except ImportError:
        return None
    g = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2GRAY)
    cas = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = cas.detectMultiScale(g, 1.1, 5, minSize=(g.shape[1] // 8, g.shape[0] // 8))
    if len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    H, W = g.shape
    return (x + w / 2) / W, (y + h / 2) / H, w / W, (y + h * 0.40) / H


def _smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def load_portrait(name, allow_placeholder=False, verbose=True):
    cfg = settings.PORTRAITS[name]
    path = find_photo(name)
    placeholder = False
    if path is None:
        if not allow_placeholder:
            want = " / ".join(f"assets/{s}.png" for s in cfg["files"])
            raise MissingPhoto(
                f"Reference photo for '{name}' not found.\n"
                f"  Place it at: {want}  (any of: {" ".join(settings.ASSET_EXTENSIONS)})\n"
                f"  Or run with --placeholder to test with an abstract stand-in "
                f"(NOT a likeness).")
        from renderer.placeholder import PLACEHOLDERS
        img = PLACEHOLDERS[name]()
        placeholder, source = True, "placeholder"
    else:
        img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
        source = str(path)
    if max(img.size) > MAX_SOURCE:
        s = MAX_SOURCE / max(img.size)
        img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)

    face, eyes, face_w = cfg["face"], cfg["eyes"], cfg["face_w"]
    crop = cfg["crop"]
    if crop is None and not placeholder:
        det = _autoframe(img)
        if det:
            fx, fy, fw, ey = det
            cw = min(1.0, fw / 0.5)                 # face ~50% of crop width
            ch = min(1.0, cw * img.width / img.height * 1.25)
            l = min(max(fx - cw / 2, 0), 1 - cw)
            t = min(max(fy - ch * 0.46, 0), 1 - ch)
            crop = (l, t, l + cw, t + ch)
            face = ((fx - l) / cw, (fy - t) / ch)
            eyes = (face[0], (ey - t) / ch)
            face_w = fw / cw
            if verbose:
                print(f"[{name}] face auto-detected; framing crop {tuple(round(c, 2) for c in crop)}")
    if crop:
        W, H = img.size
        img = img.crop((round(crop[0] * W), round(crop[1] * H), round(crop[2] * W), round(crop[3] * H)))
    w, h = img.size

    # ---- pass 1+2: tone, local contrast, face-weighted detail ---------------
    arr = np.asarray(img, np.float32) / 255.0
    arr = arr ** cfg["gamma"]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    fcx, fcy, frx, fry = cfg["focus"]
    focus = np.exp(-((((xx / w) - fcx) / frx) ** 2 + (((yy / h) - fcy) / fry) ** 2) ** 1.5).astype(np.float32)
    lum = luma(arr)
    r = max(8, int(max(w, h) / 14))
    base = box_blur(box_blur(lum, r), r)
    wmap = 0.55 + 0.9 * focus
    lum2 = lum + cfg["local_contrast"] * wmap * (lum - base)
    ratio = np.clip((lum2 + 0.02) / (lum + 0.02), 0.45, 2.6)
    arr = np.clip(arr * ratio[..., None], 0, 1)
    eq = cfg.get("equalize", 0.0)
    if eq > 0:                                  # spread tones over the full glyph-density range
        lum = luma(arr)
        wgt = 0.25 + focus
        hist, edges = np.histogram(lum, bins=256, range=(0, 1), weights=wgt)
        cdf = np.cumsum(hist)
        cdf = cdf / cdf[-1]
        lum_eq = np.interp(lum, edges[1:], cdf).astype(np.float32)
        lum2 = lum + eq * (lum_eq - lum)
        arr = np.clip(arr * np.clip((lum2 + 0.02) / (lum + 0.02), 0.4, 3.0)[..., None], 0, 1)
    rad = max(1, int(max(w, h) / 450))
    detail = sharpen(arr, cfg["sharpen"], rad) - arr
    arr = np.clip(arr + detail * (0.5 + 1.0 * focus[..., None]), 0, 1)
    dim = cfg.get("dim_outside", 1.0)
    if dim < 1.0:             # lighting separates the subject: everything away from the focus region is quieter
        wide_focus = np.exp(-((((xx / w) - fcx) / (frx * 1.9)) ** 2 + (((yy / h) - fcy) / (fry * 1.9)) ** 2) ** 1.5)
        arr = arr * (dim + (1 - dim) * wide_focus)[..., None]
    gray = luma(arr)[..., None]
    arr = np.clip(gray + (arr - gray) * cfg["saturation"], 0, 1)
    photo = Image.fromarray((arr * 255 + 0.5).astype(np.uint8))

    # ---- optional refinement: feature-local detail + a subordinate weapon layer -------------------
    detail_img = weapon_img = feat_img = None
    if cfg.get("features"):
        uu, vv = xx / w, yy / h

        def region(spec):
            m = np.zeros((h, w), np.float32)
            for cx, cy, rx, ry, wt in spec.values():
                g = np.exp(-((((uu - cx) / rx) ** 2 + ((vv - cy) / ry) ** 2) ** 1.4)) * wt
                m = 1 - (1 - m) * (1 - g)
            return m
        Fm = region(cfg["features"])
        lum0 = luma(arr)
        # lift the shadow side (left eye, brow, nose) just inside the features, then sharpen them
        lift = np.clip(((lum0 + 0.03) ** 0.70) / (lum0 + 0.03), 1.0, 2.6)
        arr_d = arr * (1 + Fm * 0.9 * (lift - 1))[..., None]
        # tonal room: compress the very top of the lit face so brow / eye / nostril / mouth can separate
        # from the cheek and forehead (this LOWERS highlights; overall exposure is not raised)
        hi = np.clip((luma(arr_d) - 0.50) / 0.50, 0, 1)
        arr_d = arr_d * (1 - 0.40 * focus * hi)[..., None]
        lum1 = luma(arr_d)
        rad2 = max(2, int(max(w, h) / 330))
        dog = lum1 - box_blur(lum1, rad2 * 2)                      # fine definition (features)
        dogb = lum1 - box_blur(lum1, max(6, int(max(w, h) / 70)))  # facial planes: cheekbone, jaw, nose bridge
        arr_d = np.clip(arr_d + (dog * 2.0 * Fm + dogb * 0.9 * focus)[..., None], 0, 1)
        detail_img = Image.fromarray((arr_d * 255 + 0.5).astype(np.uint8))

        if cfg.get("weapon"):
            Wm = region(cfg["weapon"])
            ll = luma(arr) ** 0.45                                  # drag the near-black gun out of the dark
            edge = np.abs(ll - box_blur(ll, max(4, int(max(w, h) / 90))))
            wl = np.clip(0.22 * ll + 0.75 * np.clip(edge * 3.6, 0, 1), 0, 1) * Wm
            ref = np.percentile(wl[Wm > 0.5], 99) if (Wm > 0.5).any() else 1.0
            wl = np.clip(wl / max(ref, 1e-3), 0, 1) * cfg.get("weapon_cap", 0.4)
            steel = np.array([0.72, 0.84, 1.0], np.float32)         # cool steel
            weapon_img = Image.fromarray((np.clip(wl[..., None] * steel, 0, 1) * 255 + 0.5).astype(np.uint8))
            feat_img = Image.fromarray((np.stack([Fm, Wm, np.zeros_like(Fm)], -1) * 255 + 0.5).astype(np.uint8))
        else:
            feat_img = Image.fromarray((np.stack([Fm, np.zeros_like(Fm), np.zeros_like(Fm)], -1) * 255 + 0.5).astype(np.uint8))

    # ---- masks ---------------------------------------------------------------
    u, v = xx / w, yy / h
    fs, ft, fb = cfg.get("feather", (0.05, 0.05, 0.05))      # fade widths (fraction of image width): sides, top, bottom
    ar = h / w
    rect = np.minimum(np.minimum(u / fs, (1 - u) / fs), np.minimum(v * ar / ft, (1 - v) * ar / fb))
    rect = _smooth(rect, 0.0, 1.0)
    rx = face_w * 0.62
    ry = rx * (w / h) * cfg.get("head_ratio", 1.3)      # head height / width in pixels
    d = np.sqrt(((u - face[0]) / rx) ** 2 + ((v - face[1]) / ry) ** 2)
    ell = 1 - _smooth(d, 0.75, 1.15)
    masks = np.stack([rect, ell, focus], -1)
    masks_img = Image.fromarray((masks * 255 + 0.5).astype(np.uint8))

    return Portrait(name, MipImage(photo), MipImage(masks_img), w, h, face, eyes, face_w,
                    cfg["anchor"], placeholder, source,
                    cfg.get("closeup_w", 0.0), cfg.get("closeup_eye_y", 0.4),
                    MipImage(detail_img) if detail_img else None, MipImage(weapon_img) if weapon_img else None,
                    MipImage(feat_img) if feat_img else None)
