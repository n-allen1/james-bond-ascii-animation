"""Central configuration: timing, music cues, rendering presets, portrait tuning.

Everything you are likely to tweak lives here.  Scene code never hard-codes a
time in seconds - it derives every cue from SCENE_TIMINGS / EXPLOSION_PEAK.
"""

# --------------------------------------------------------------------------
# Timing  (all values are ANIMATION seconds, measured from frame 0)
# --------------------------------------------------------------------------
SONG_START_SECONDS = 182.0          # 3:02 of the official recording
ANIMATION_DURATION = 60.0

# Pattinson reveal: "refined" (feature detail + legible weapon) or "baseline" (the v1 look, kept for A/B)
PATTINSON_STYLE = "refined"

SCENE_TIMINGS = {
    "craig_reveal":     (0.0, 7.0),    # Scene 1 - the last look
    "camera_pullback":  (7.0, 17.0),   # Scene 2 - the final stand
    "explosion":        (17.0, 21.0),  # Scene 3 - no time to die
    "blackout":         (21.0, 27.0),  # Scene 4 - darkness
    "legacy_007":       (27.0, 33.0),  # Scene 5 - the legacy
    "pattinson_reveal": (33.0, 48.0),  # Scene 6 - a new Bond
    "final_title":      (48.0, 60.0),  # Scene 7 - the name lives on
}
EXPLOSION_PEAK = 19.0               # animation seconds (== song 3:21 by default)

# --------------------------------------------------------------------------
# Presentation
# --------------------------------------------------------------------------
FPS = 30
COUNTDOWN_SECONDS = 5               # --record only; NOT part of the 60 s runtime
CELL_ASPECT = 2.0                   # terminal cell height / width (most fonts ~2.0)

# The animation is composed inside a centred "stage" with this width/height
# pixel ratio, so a vertical phone frame can capture everything important.
STAGE_ASPECT = 0.75                 # 3:4 portrait.  Use --aspect 1.78 for 16:9.

# Rendering style: braille (stippled dot characters, default) | blocks (legacy fallback)
DEFAULT_STYLE = "braille"

# Quality presets: maximum stage height in terminal rows (None = use all rows)
QUALITY = {
    "low":      {"max_rows": 34},
    "balanced": {"max_rows": 48},   # recording preset: big, readable cells
    "high":     {"max_rows": None}, # as dense as the terminal allows
}
DEFAULT_QUALITY = "balanced"
MIN_TERMINAL = (60, 30)             # (cols, rows) below which we refuse to start

# Cells whose colour changes by less than this (0-255 per channel) are not
# rewritten.  Cuts terminal traffic a lot; 2-3 is invisible in practice.
DIRTY_THRESHOLD = 3

# --------------------------------------------------------------------------
# Portraits.  Coordinates are normalised (0..1) inside the CROPPED image.
#   crop       (l, t, r, b) in the source photo, or None = auto/full image
#   face       centre of the face            eyes   midpoint between the eyes
#   face_w     face width / cropped image width
#   anchor     where a "cover" fit is centred when the photo's aspect differs
#                from the stage (Pattinson: keep the gun in frame)
# Use  python main.py --preview craig --guides  to see these as overlays.
# --------------------------------------------------------------------------
PORTRAITS = {
    # Coordinates below were set by eye from the supplied reference photos
    # (assets/daniel_craig.avif 1600x800, assets/robert_pattinson.webp 1000x667).
    # closeup_w     fraction of the photo's width visible in the opening close-up
    # closeup_eye_y where the eyes sit vertically in that close-up (0 top .. 1 bottom)
    "craig": {
        "files": ("daniel_craig",),
        "crop": None,
        "face": (0.46, 0.45), "eyes": (0.42, 0.29), "face_w": 0.40,
        "anchor": (0.5, 0.5), "head_ratio": 0.9, "closeup_w": 0.53, "closeup_eye_y": 0.36,
        "gamma": 1.0, "local_contrast": 0.45, "sharpen": 0.5,
        "saturation": 1.08, "focus": (0.45, 0.40, 0.26, 0.40),   # cx, cy, rx, ry
        "feather": (0.05, 0.09, 0.07), "dim_outside": 0.55,
    },
    "pattinson": {
        "files": ("robert_pattinson",),
        "crop": None,
        "face": (0.65, 0.40), "eyes": (0.62, 0.43), "face_w": 0.30,
        "anchor": (0.70, 0.5),      # window slides right so the sight, hand and face are framed
        "gamma": 0.92, "local_contrast": 0.55, "sharpen": 0.65,
        "saturation": 0.95, "focus": (0.66, 0.42, 0.17, 0.32),
        # --- refined reveal (scenes/pattinson.py).  Regions are soft ellipses in photo coordinates
        #     (cx, cy, rx, ry, weight), read off the shadow-lifted reference photograph.
        "features": {
            "eye_r":   (0.665, 0.415, 0.042, 0.022, 1.0),
            "eye_l":   (0.560, 0.470, 0.040, 0.021, 0.9),
            "brow_r":  (0.675, 0.375, 0.064, 0.020, 0.9),
            "brow_l":  (0.560, 0.435, 0.052, 0.018, 0.8),
            "nose":    (0.625, 0.540, 0.032, 0.095, 0.8),
            "cheek_r": (0.735, 0.500, 0.056, 0.078, 0.6),
            "mouth":   (0.695, 0.655, 0.062, 0.022, 0.7),
            "jaw":     (0.705, 0.725, 0.110, 0.040, 0.7),
            "hair":    (0.660, 0.120, 0.185, 0.090, 0.6),
            "ear":     (0.780, 0.370, 0.030, 0.075, 0.4),
        },
        "weapon": {                      # suppressor, slide + sight, weapon light, gripping hand
            "suppressor": (0.160, 0.600, 0.175, 0.085, 1.0),
            "slide":      (0.400, 0.580, 0.110, 0.150, 1.0),
            "light":      (0.335, 0.780, 0.036, 0.046, 0.5),
            "hand":       (0.540, 0.800, 0.095, 0.230, 1.0),
        },
        "weapon_cap": 0.55,              # max luminance of the weapon layer (the face stays brighter)
    },
    # Craig's wide shot (assets/daniel_craig_full_shot.png, 1588x741).  Bond stands at the left third.
    "craig_wide": {
        "files": ("daniel_craig_full_shot",),
        "crop": None,
        "face": (0.20, 0.27), "eyes": (0.20, 0.26), "face_w": 0.035,
        "anchor": (0.0, 0.5),
        "gamma": 1.0, "local_contrast": 0.8, "sharpen": 0.5, "equalize": 0.2,
        "saturation": 1.0, "focus": (0.20, 0.58, 0.10, 0.40),
        "feather": (0.04, 0.16, 0.025), "dim_outside": 0.30,
    },
}
ASSET_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".avif", ".bmp", ".tif", ".tiff")

# --------------------------------------------------------------------------
# The ending (scene 7).  All cues are SECONDS relative to the start of the "final_title" window
# (48.0 s).  Pattinson's reveal itself (33-48 s) is not touched by any of this.
#
#   portrait_fade  Pattinson fades to black
#   t1_in/t1_out   "NO TIME TO DIE" fades in / dissolves
#   t2_in/t2_out   "007 WILL RETURN" fades in / fades to black (t2_out end == end of the animation)
#
# ENDING = "original"  the 60 s ending exactly as first delivered
# ENDING = "early"     finishes ENDING_ADVANCE seconds earlier (default 2.5 s -> 57.5 s total).  The
#                      transition between the reveal and the title is shortened and the title cues
#                      are shifted earlier; the title animations themselves are not sped up, and
#                      "007 WILL RETURN" holds at full brightness for ~2.3 s.  Sensible range 1.0-3.5 s.
# CLI:  --ending original|early   --ending-advance SECONDS
# --------------------------------------------------------------------------
ENDING = "early"
ENDING_ADVANCE = 2.5

ORIGINAL_ENDING = dict(duration=12.0, portrait_fade=(0.36, 5.04), t1_in=(3.6, 5.52), t1_out=(7.44, 8.88),
                       t2_in=(8.4, 9.96), t2_out=(10.8, 12.0))


def resolve_ending(name=None, advance=None):
    """Return the cue table (seconds from the start of the final_title window) for an ending."""
    name = name or ENDING
    if name == "original":
        return dict(ORIGINAL_ENDING)
    adv = ENDING_ADVANCE if advance is None else advance
    D = ORIGINAL_ENDING["duration"] - adv
    t2_in0 = D - 4.5                                   # "007 WILL RETURN": 1.0 s in, ~2.3 s full, 1.2 s out
    return dict(duration=D, portrait_fade=(0.3, 2.9), t1_in=(1.9, 2.9),
                t1_out=(t2_in0 - 0.4, t2_in0 + 0.5), t2_in=(t2_in0, t2_in0 + 1.0), t2_out=(D - 1.2, D))


def apply_ending(name=None, advance=None):
    """(Re)compute ENDING_CUES, the final_title window and the total duration."""
    global ENDING_CUES, ANIMATION_DURATION
    ENDING_CUES = resolve_ending(name, advance)
    start = SCENE_TIMINGS["final_title"][0]
    SCENE_TIMINGS["final_title"] = (start, start + ENDING_CUES["duration"])
    ANIMATION_DURATION = start + ENDING_CUES["duration"]


apply_ending()
