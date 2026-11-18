"""Controlled procedural explosion.  Everything is a closed-form function of
`tau` (seconds relative to the peak), so any frame can be rendered at random
access and nothing depends on previous frames.

Light curve (tau = 0 at EXPLOSION_PEAK):
    -0.45 .. 0.05   core blooms, screen lifts toward warm white   (~0.5 s rise)
     0.05 .. 0.30   near-white plateau  (the only 'flash'; brief and smooth)
     0.30 .. 1.20   white decays to an amber afterglow
"""
import numpy as np

from effects.lighting import box_blur, coords, radial
from effects.particles import splat
from effects.transitions import ease_out, prog, smoothstep

WHITE = np.array([1.0, 0.97, 0.90], np.float32)
AMBER = np.array([1.0, 0.58, 0.20], np.float32)
PALE = np.array([1.0, 0.82, 0.55], np.float32)


class Explosion:
    def __init__(self, ph, pw, noise, seed=21, n_debris=520):
        self.ph, self.pw, self.noise = ph, pw, noise
        rng = np.random.default_rng(seed)
        n = n_debris
        ang = rng.uniform(0, 2 * np.pi, n)
        spd = np.exp(rng.normal(-0.55, 0.55, n)).astype(np.float32)           # frame-heights / s
        self.v = np.stack([np.cos(ang) * spd, np.sin(ang) * spd * 0.8 - 0.18], 1).astype(np.float32)
        self.drag = rng.uniform(1.2, 3.0, n).astype(np.float32)
        self.t_off = rng.uniform(-0.05, 0.25, n).astype(np.float32)
        self.life = rng.uniform(0.7, 2.0, n).astype(np.float32)
        self.size = rng.uniform(0.5, 1.0, n).astype(np.float32)

    def light(self, tau):
        """Scalar summary used by scenes: how 'white' the frame currently is."""
        rise = smoothstep(-0.45, 0.05, tau)
        decay = 1 - smoothstep(0.22, 0.95, tau)
        return rise * decay

    def render(self, tau, origin, noise_t):
        """Returns (add: HxWx3, dark: HxW) for explosion centred at `origin`
        (frame-height units from screen centre)."""
        ph, pw = self.ph, self.pw
        ox, oy = origin
        add = np.zeros((ph, pw, 3), np.float32)
        if tau < -0.5:
            return add, np.zeros((ph, pw), np.float32)
        xs, ys = coords(ph, pw)
        d = np.sqrt((xs - ox) ** 2 + (ys - oy) ** 2)

        # core bloom + global lift
        r_core = 0.03 + 1.5 * ease_out(prog(tau, -0.45, 0.45), 2.2)
        E = self.light(tau)                               # 0..1..0 : the single bright swell
        core = np.exp(-(d / r_core) ** 1.4)
        add += (E * core)[..., None] * PALE * 0.75
        add += (E * 0.82) * WHITE
        add += (E * core ** 2)[..., None] * WHITE * 0.55

        # afterglow
        after = smoothstep(0.0, 0.5, tau) * (1 - smoothstep(0.9, 2.3, tau))
        add += (radial(ph, pw, ox, oy, 0.9, power=1.4) * after * 0.55)[..., None] * AMBER

        # shock rings
        for t0, speed, amp in ((-0.12, 1.9, 1.0), (0.05, 1.45, 0.75), (0.28, 1.05, 0.5)):
            age = tau - t0
            if age <= 0:
                continue
            r = speed * age
            w = 0.012 + 0.03 * age
            ring = np.exp(-((d - r) / w) ** 2) * np.exp(-age * 1.5) * amp
            add += ring[..., None] * WHITE * 0.9

        # debris
        t = np.maximum(tau + 0.05 - self.t_off, 0)
        if tau > -0.05:
            e = (1 - np.exp(-self.drag * t)) / self.drag
            x = ox + self.v[:, 0] * e
            y = oy + self.v[:, 1] * e + 0.35 * (t - e) / self.drag
            age = t / self.life
            br = np.clip(1 - age, 0, 1) ** 1.3 * (0.6 + 0.4 * self.size)
            col = WHITE[None] * (1 - age[:, None]) + AMBER[None] * age[:, None]
            buf = np.zeros((3, ph, pw), np.float32)
            splat(buf, x * ph + pw / 2, y * ph + ph / 2, col * br[:, None] * 1.4)
            deb = np.moveaxis(buf, 0, -1)
            add += deb + box_blur(deb, 1) * 1.2

        # smoke: dark plumes expanding behind the light
        dark = np.zeros((ph, pw), np.float32)
        if tau > 0.2:
            r_s = 0.12 + 0.95 * ease_out(prog(tau, 0.1, 2.4), 2.0)
            n = self.noise.sample(ph, pw, 70.0 / (0.4 * ph), noise_t * 9, noise_t * -5)
            blob = np.clip(1.15 - d / r_s + (n - 0.5) * 0.9, 0, 1)
            dark = blob ** 0.8 * smoothstep(0.25, 0.9, tau) * 0.88
        return add, dark


def streak(ph, pw, head, direction, length, width):
    """Bright comet: head at `head` (frame units), tail trailing opposite `direction`."""
    xs, ys = coords(ph, pw)
    dx, dy = direction
    n = np.hypot(dx, dy)
    dx, dy = dx / n, dy / n
    rx, ry = xs - head[0], ys - head[1]
    s = -(rx * dx + ry * dy)                  # distance behind the head
    p = np.abs(rx * (-dy) + ry * dx)          # distance from the path
    tail = np.clip(1 - s / length, 0, 1) ** 1.6 * (s > -0.01)
    return np.exp(-(p / width) ** 2) * tail + np.exp(-((rx ** 2 + ry ** 2) / (width * 2.2) ** 2)) * 0.9
