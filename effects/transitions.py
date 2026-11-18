"""Easing and timing helpers.  All functions are pure and time-driven."""
import math


def clamp01(x):
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def prog(t, a, b):
    """Normalised progress of t inside [a, b], clamped to 0..1."""
    if b <= a:
        return 1.0 if t >= b else 0.0
    return clamp01((t - a) / (b - a))


def smoothstep(a, b, t):
    x = prog(t, a, b)
    return x * x * (3 - 2 * x)


def smootherstep(a, b, t):
    x = prog(t, a, b)
    return x * x * x * (x * (x * 6 - 15) + 10)


def ease_in(x, p=2.0):
    return clamp01(x) ** p


def ease_out(x, p=3.0):
    return 1.0 - (1.0 - clamp01(x)) ** p


def ease_in_out(x):
    x = clamp01(x)
    return x * x * (3 - 2 * x)


def lerp(a, b, x):
    return a + (b - a) * x


def log_lerp(a, b, x):
    """Interpolate zooms so perceived speed is constant."""
    return math.exp(math.log(a) + (math.log(b) - math.log(a)) * x)
