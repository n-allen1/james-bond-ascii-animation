"""Shared scene context."""
from dataclasses import dataclass, field

import numpy as np

from config import settings
from effects.lighting import NoiseField


@dataclass
class Stage:
    pw: int                 # stage width in sub-pixels
    ph: int                 # stage height in sub-pixels
    cols: int
    rows: int
    portraits: dict         # name -> Portrait
    timings: dict = field(default_factory=lambda: dict(settings.SCENE_TIMINGS))
    peak: float = settings.EXPLOSION_PEAK
    duration: float = settings.ANIMATION_DURATION
    noise: NoiseField = field(default_factory=lambda: NoiseField(seed=4))

    @property
    def aspect(self):
        return self.pw / self.ph

    def window(self, name):
        return self.timings[name]


def noise_scale(ph, feature=0.4):
    """Texture pixels per output pixel for noise features ~`feature` frame heights."""
    return 70.0 / (feature * ph)
