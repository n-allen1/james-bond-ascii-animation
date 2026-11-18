"""Scene 7 typography: native terminal text, letter-spaced, silver, slow tracking."""
import numpy as np

from effects.transitions import lerp, smoothstep
from scenes.base import Stage

SILVER = (0.86, 0.90, 0.96)
BRIGHT = (1.0, 1.0, 1.0)


def _layout(text, spacing, cols, row, centre_col=None):
    """Return [(row, col, char, is_digit)] with fractional letter-spacing."""
    words = text.split(" ")
    advances = []
    for wi, word in enumerate(words):
        for ch in word:
            advances.append((ch, spacing))
        if wi < len(words) - 1:
            advances.append((" ", spacing * 2.2))
    total = sum(a for _, a in advances) - spacing
    x = (cols if centre_col is None else centre_col * 2) / 2 - total / 2
    out = []
    for ch, adv in advances:
        if ch != " ":
            out.append((row, int(round(x)), ch))
        x += adv
    return out


class TitleScene:
    def __init__(self, st: Stage):
        self.st = st
        rng = np.random.default_rng(5)
        self.rnd = rng.random(64)

    def overlay(self, t):
        """Native-text overlay.  All times come from the ending cue table (st.ending, seconds from the
        start of the final_title window), so the ending can be retimed from config/settings.py alone."""
        st = self.st
        fa, _ = st.window("final_title")
        c = st.ending
        T = t - fa                                      # seconds into scene 7
        items = []
        row = st.rows // 2 - 1

        # --- NO TIME TO DIE -------------------------------------------------------
        (i0, i1), (o0, o1) = c["t1_in"], c["t1_out"]
        a1 = smoothstep(i0, i1, T)
        out1 = (T - o0) / (o1 - o0)                     # dissolve progress 0..1
        if T > i0 - 0.24 and out1 < 1:
            sp = lerp(1.7, 2.05, smoothstep(i0, o1 - 0.24, T))
            glyphs = _layout("NO TIME TO DIE", sp, st.cols, row)
            for i, (r, cc, ch) in enumerate(glyphs):
                keep = 1.0 if out1 <= 0 else float(np.clip(1 - (out1 * 1.7 - self.rnd[i] * 0.7), 0, 1))
                items.append((r, cc, ch, SILVER, a1 * keep))
            w = glyphs[-1][1] - glyphs[0][1] + 1
            rule = lerp(0.2, 1.0, smoothstep(i0 + 0.48, i1 + 0.72, T))
            half = int(w * rule / 2 + 4)
            mid = (glyphs[0][1] + glyphs[-1][1]) // 2
            ra = a1 * 0.45 * (1 - np.clip(out1, 0, 1))
            for dc in range(-half, half + 1):
                items.append((row - 2, mid + dc, "─", (0.55, 0.62, 0.72), ra))
                items.append((row + 2, mid + dc, "─", (0.55, 0.62, 0.72), ra))

        # --- 007 WILL RETURN ------------------------------------------------------
        (j0, j1), (k0, k1) = c["t2_in"], c["t2_out"]
        a2 = smoothstep(j0, j1, T) * (1 - smoothstep(k0, k1, T))
        if a2 > 0:
            sp = lerp(1.7, 1.95, smoothstep(j0, k1, T))
            glyphs = _layout("007 WILL RETURN", sp, st.cols, row)
            for i, (r, cc, ch) in enumerate(glyphs):
                items.append((r, cc, ch, BRIGHT if i < 3 else SILVER, a2 * (1.0 if i < 3 else 0.85)))
        return items
