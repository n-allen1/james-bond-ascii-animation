# 007 — NO TIME TO DIE
### A cinematic, terminal-native tribute (Python, true-colour ANSI, braille characters)

One Bond dies. Another emerges. The legacy continues.

The whole ~60 s sequence is rendered **as terminal characters** — no video, GIF, audio or GUI.
You screen-record it with your phone and lay the song over it afterwards.

---

## Quick start (Windows 10/11, Windows Terminal, Python 3.11+)

```powershell
cd E:\dev-projects\bond-python
py -3.12 -m venv .venv                 # a regular python.org Python (see note below)
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python main.py --record
```

> **Note:** on this machine plain `python` resolves to the MSYS2/MinGW build, which has no
> NumPy/Pillow wheels. Use the venv above (or `py -3.12`).

Reference photographs live in `assets/` (see `assets/README.md`): `daniel_craig.avif`,
`daniel_craig_full_shot.png` (the wide shot), `robert_pattinson.webp`.

### Recording checklist
1. Windows Terminal, **maximise / F11**, font **Cascadia Mono** (it has the Braille block; Consolas
   does too in recent Windows builds). If dots look wrong or missing: `--style blocks` is a fallback.
2. Font size ≈ 14–20. The picture is a centred 3:4 stage; everything else is pure black.
3. `python main.py --record` → start phone recording → press any key → countdown (not part of the 60 s) → animation.
4. Phone shows banding/flicker? `--fps 24`. Looks dim? `--brightness 1.15`. Want more detail? `--quality high`.

**Music cues** (`python main.py --cues` prints this from config)

| Scene | Animation | Song (start 3:02) |
|---|---|---|
| 1 The Last Look (Craig close-up emerges) | 0:00–0:07 | 3:02–3:09 |
| 2 The Final Stand (pullback → dissolve → wide shot) | 0:07–0:17 | 3:09–3:19 |
| 3 No Time To Die (strike, white-out, collapse) | 0:17–0:21 | 3:19–3:23 |
| 4 Darkness | 0:21–0:27 | 3:23–3:29 |
| 5 The Legacy (007 assembles) | 0:27–0:33 | 3:29–3:35 |
| 6 A New Bond (Pattinson emerges) | 0:33–0:48 | 3:35–3:50 |
| 7 The Name Lives On (titles) | 0:48–1:00 | 3:50–4:02 |

**Suggested music start: 3:02 · Explosion peak: animation 0:19 / music 3:21.**
Peak = `EXPLOSION_PEAK`, windows = `SCENE_TIMINGS` in `config/settings.py`; every internal cue is derived from them.

---

## The look (and why it changed)

The first version converted each cell to two coloured background blocks (`▀`), i.e. a pixel mosaic.
That was the wrong tool. It has been replaced.

* **Braille stippling** is the primary renderer. Each character cell holds a 2×4 dot pattern, so a 72×48
  stage has 144×192 addressable dots (4× the detail of half-blocks) and every visible mark is a *character*
  on a black background. Dots are chosen by a static ordered threshold (clean tonal steps, no shimmer on
  camera) and coloured from the picture under the lit dots, so **light decides how many characters appear**:
  Craig's face literally builds out of scattered amber dots; Pattinson's highlights appear first.
  Very bright cells (the flash, the sun) melt into a solid glow instead of a dot grid.
* **Photographs are references, processed for the medium**: tone equalisation, face-weighted local contrast
  and sharpening, and *dim-outside-the-subject* lighting so the figure separates from the scenery
  (`config/settings.py → PORTRAITS`).
* **Craig's wide shot is the real film still** you supplied (no invented body): sunset sky, mountains,
  coast, the concrete platform, Bond small at the left third with his head tilted to the sky. The close-up
  and wide shot are different camera set-ups, so they are joined by a **smoke-noise dissolve with a brief dip
  in brightness**, not by stretching one image into the other. The wide shot then pulls back from Bond's upper
  body to the full composition while the sunset glow swells toward the strike.
* An **ASCII-letter glyph-matching engine** (real font bitmaps, ramp + contour glyphs) is also included
  (`--style glyph`, stills only). It was evaluated against braille on the same frames and rejected: at ~70
  columns the likeness dissolves into symbols. `previews/CHECKPOINT_all.png` shows the comparison
  (top row braille, middle row simulated phone view, bottom row glyph engine).

### Style options
| `--style` | Use |
|---|---|
| `braille` (default) | The look above. Real-time, ~13–26 ms/frame at the default size |
| `blocks` | Legacy half-block fallback if your font lacks Braille glyphs |
| `glyph` | ASCII letters; slow, for `--dump`/`--preview` comparison only |

---

## Commands

| Command | What it does |
|---|---|
| `python main.py` | Full sequence |
| `python main.py --record` | Instructions → key press → countdown → exact t=0 start |
| `--countdown N` / `--no-countdown` | Countdown length / skip countdown and key wait |
| `--preview craig\|wide\|pattinson` | Viewer: **space** next state, **s** style (braille/glyph/blocks), **g** guides, **q** quit |
| `--preview X --compare` | Auto-cycle the styles |
| `--quality low\|balanced\|high` | Max stage height 34 / 48 rows / whole terminal |
| `--fps 30` · `--no-color` · `--aspect 0.75` · `--scale 0.8` | Frame rate · mono · stage shape (1.78 = 16:9) · size |
| `--brightness` `--contrast` `--sharpen` | Final grade |
| `--song-offset S` · `--scene NAME` · `--start T` | Cue display shift · play one scene · start at T s |
| `--dump 6.6,16.6 [--style S] [--size 120x50]` | Write font-rendered PNG frames to `dumps/` |
| `--stats` | Print frames drawn / slow frames after playback |
| `--cues` · `--placeholder` | Print the cue table · test-only stand-ins if photos are missing |

`Q`/`Esc` aborts playback; the terminal is always restored.

---

## How it works

```
photo → crop/frame → tone, equalise, face-weighted detail, dim-outside   (renderer/portraits.py)
      → camera re-samples the SOURCE image (mip-mapped affine)           (renderer/camera.py)
      → light masks, smoke, particles, explosion in screen space         (effects/, scenes/)
      → grade + sharpen                                                  (scenes/timeline.py)
      → braille stippling to characters                                  (renderer/glyphs.py, ascii.py)
      → changed-cell diff, batched ANSI, synchronized output             (renderer/terminal.py)
```
`t = perf_counter() − t0` is read every frame and every scene is a pure function of `t`, so dropped frames
never cause drift.

```
main.py              CLI, preview, playback loop
config/settings.py   timings, presets, portrait tuning (face, eyes, focus, feather, dim_outside, closeup_w…)
renderer/            terminal, ascii (style registry), glyphs (braille + glyph engines), portraits, camera, dump
effects/             lighting, particles (007), explosion, transitions (easing)
scenes/              craig (1-3), legacy (4-5), pattinson (6), titles (7), timeline
previews/            quality checkpoint renders
```

### Tuning
Wide-shot framing is at the top of `scenes/craig.py` (`WIDE_START`, `WIDE_END`, `SUN_UV`); the dissolve
timing is `dissolve_window()`. Craig's close-up width is `closeup_w`; Pattinson's window slides with
`anchor`. `--preview X --guides` draws eye/face/focus marks.

---

## What was and was not validated

**Verified here**
* Complete 60 s sequence run in real time with output captured: **1800 frames, 30 fps, 2 slow frames, worst
  36 ms** (the explosion); ~8.8 MB of terminal output in total; restore sequences present.
* Every scene rendered to PNG with a real monospace font and inspected, including a simulated phone view
  (downscaled to camera resolution): Craig's eyes/brow/scars, Bond's tilted-head stance, Pattinson's face
  and collar remain legible; the dissolve, strike, 007 and titles read correctly.
* Frame cost: braille 13–26 ms at 72×48 (default), ~23 ms average at 92×60 (`--quality high`).

**Not verified — please check on your machine**
* **Live playback in Windows Terminal / phone footage.** I could not watch a real terminal. Braille dot size
  and spacing depend on your font; dumps approximate it. If the dots look too small/faint, raise the font size.
* **Interactive keys** in `--preview` and the `--record` key-wait started without errors, but no key presses
  were sent.
* **Likeness is judged from ~72×48-cell renders**; recognisability is your call. `--quality high` in a
  maximised window gives more dots.
* Optional OpenCV auto-framing is implemented but untested (not needed with the supplied photos).
