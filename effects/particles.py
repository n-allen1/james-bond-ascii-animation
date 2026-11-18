"""Particle helpers: sub-pixel splatting and the 007 assembly system."""
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from effects.lighting import box_blur

FONT_CANDIDATES = (
    "C:/Windows/Fonts/bahnschrift.ttf", "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/consolab.ttf", "DejaVuSans-Bold.ttf", "Arial Bold.ttf",
)


def load_font(size):
    for f in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def splat(buf, x, y, rgb):
    """Additively splat points with bilinear weights into planar buf (3, H, W)."""
    _, h, w = buf.shape
    if len(x) == 0:
        return
    x0 = np.floor(x).astype(np.int64)
    y0 = np.floor(y).astype(np.int64)
    fx = x - x0
    fy = y - y0
    idx_all, w_all = [], []
    for dx, dy, wt in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)),
                       (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
        xi, yi = x0 + dx, y0 + dy
        ok = (xi >= 0) & (xi < w) & (yi >= 0) & (yi < h)
        idx_all.append(yi[ok] * w + xi[ok])
        w_all.append((wt[ok], ok))
    idx = np.concatenate(idx_all)
    for c in range(3):
        wts = np.concatenate([wt * rgb[ok, c] for wt, ok in w_all])
        buf[c] += np.bincount(idx, weights=wts, minlength=h * w).reshape(h, w).astype(np.float32)


def glow(planar, radius=2, strength=0.8):
    """Planar (3,H,W) -> HWC with a cheap two-scale glow added."""
    img = np.moveaxis(planar, 0, -1)
    return img + box_blur(img, radius) * strength + box_blur(img, radius * 3) * strength * 0.5


class DigitParticles:
    """Particles that are born at a point, fly along curved paths, assemble
    into text, hold, then dissolve.  Fully deterministic function of time."""

    def __init__(self, ph, pw, text="007", n=900, seed=7, origin=(0.0, -0.06)):
        rng = np.random.default_rng(seed)
        self.ph, self.pw, self.n = ph, pw, n
        # --- target points from rendered text -------------------------------
        size = 100
        font = load_font(size)
        probe = Image.new("L", (10, 10))
        l, t, r, b = ImageDraw.Draw(probe).textbbox((0, 0), text, font=font)
        img = Image.new("L", (r - l + 8, b - t + 8), 0)
        ImageDraw.Draw(img).text((4 - l, 4 - t), text, fill=255, font=font)
        target_w = pw * 0.72
        img = img.resize((int(target_w), max(1, int(target_w * img.height / img.width))), Image.LANCZOS)
        mask = np.asarray(img) > 90
        ys, xs = np.nonzero(mask)
        pick = rng.choice(len(xs), size=n, replace=len(xs) < n)
        jitter = rng.uniform(-0.45, 0.45, size=(n, 2))
        self.target = np.stack([xs[pick] + jitter[:, 0] + (pw - img.width) / 2,
                                ys[pick] + jitter[:, 1] + (ph - img.height) / 2], 1).astype(np.float32)
        # --- origin & per-particle randomness --------------------------------
        self.origin = np.array([pw / 2 + origin[0] * ph, ph / 2 + origin[1] * ph], np.float32)
        self.start = rng.uniform(0.0, 1.0, n).astype(np.float32)      # launch delay (0..1)
        self.dur = rng.uniform(0.55, 0.95, n).astype(np.float32)      # flight length (0..1)
        span = self.target - self.origin
        perp = np.stack([-span[:, 1], span[:, 0]], 1)
        self.ctrl = (self.origin + span * rng.uniform(0.2, 0.6, (n, 1)) +
                     perp * rng.uniform(-0.55, 0.55, (n, 1))).astype(np.float32)
        ang = rng.uniform(0, 2 * np.pi, n)
        self.drift = np.stack([np.cos(ang), np.sin(ang)], 1).astype(np.float32) * rng.uniform(0.08, 0.5, (n, 1)).astype(np.float32) * ph
        self.dissolve_delay = rng.uniform(0, 0.7, n).astype(np.float32)
        self.bright = rng.uniform(0.55, 1.0, n).astype(np.float32)
        self.phase = rng.uniform(0, 6.28, n).astype(np.float32)

    def draw(self, t, emit_a, emit_b, form_b, hold_b, end):
        """Planar (3,H,W) particle light at time t.  emit_a..emit_b: launches are
        spread over this window; form_b: all assembled by here; hold_b: dissolve
        starts; end: everything gone."""
        ph, pw = self.ph, self.pw
        buf = np.zeros((3, ph, pw), np.float32)
        # flight progress
        launch = emit_a + self.start * (emit_b - emit_a)
        u = np.clip((t - launch) / np.maximum(self.dur * (form_b - emit_a), 1e-3), 0, 1)
        u = u * u * (3 - 2 * u)
        om = 1 - u
        pos = (om ** 2)[:, None] * self.origin + (2 * om * u)[:, None] * self.ctrl + (u ** 2)[:, None] * self.target
        alive = (t >= launch).astype(np.float32)
        # dissolve
        d = np.clip((t - hold_b - self.dissolve_delay * (end - hold_b) * 0.6) / ((end - hold_b) * 0.55), 0, 1)
        d = d * d
        centre = np.array([pw / 2, ph / 2], np.float32)
        radial = (pos - centre)
        pos = pos + self.drift * d[:, None] + radial * (1.6 * d[:, None])  # flows outward / toward camera
        fade = (1 - d) ** 1.2
        shimmer = 0.85 + 0.15 * np.sin(t * 5.0 + self.phase)
        # glow flare as particles settle onto their target
        settle = 1 + 0.8 * np.exp(-((u - 0.94) / 0.08) ** 2) * (u < 1)
        inten = alive * fade * self.bright * shimmer * settle
        col = np.array([0.80, 0.88, 1.0], np.float32)
        rgb = inten[:, None] * col[None, :] * 0.9
        splat(buf, pos[:, 0], pos[:, 1], rgb)
        return buf
