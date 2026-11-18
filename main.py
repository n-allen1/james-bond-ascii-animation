#!/usr/bin/env python
"""007 - NO TIME TO DIE.  A cinematic, terminal-native tribute.

    python main.py --record          clean, recording-friendly run
    python main.py --preview craig   inspect a portrait (see --help for keys)
"""
import argparse
import sys
import time
from pathlib import Path

from config import settings
from renderer import ascii as A
from renderer.portraits import MissingPhoto, load_portrait
from renderer.terminal import Display, Terminal
from scenes.timeline import Timeline, compute_layout

ROOT = Path(__file__).resolve().parent


def fmt(sec):
    return f"{int(sec // 60)}:{sec % 60:04.1f}"


def print_cues(timings, peak, song_start):
    print("\nScene                 anim time        song time")
    for name, (a, b) in timings.items():
        print(f"  {name:<18} {fmt(a):>6} - {fmt(b):<6}   {fmt(song_start + a)} - {fmt(song_start + b)}")
    print(f"\n  Explosion peak: animation {fmt(peak)}  /  song {fmt(song_start + peak)}")
    print(f"  Suggested music start: {fmt(song_start)}\n")


def parse_args():
    p = argparse.ArgumentParser(description="007 - NO TIME TO DIE: cinematic terminal tribute")
    p.add_argument("--record", action="store_true", help="recording mode: wait for a key, countdown, then play")
    p.add_argument("--countdown", type=int, default=None, metavar="N", help="countdown seconds (record mode; default %d)" % settings.COUNTDOWN_SECONDS)
    p.add_argument("--no-countdown", action="store_true", help="skip countdown and key wait")
    p.add_argument("--preview", choices=("craig", "wide", "pattinson"), help="portrait preview (keys: space=next state, s=style, g=guides, q=quit)")
    p.add_argument("--compare", action="store_true", help="with --preview: cycle through every rendering style")
    p.add_argument("--guides", action="store_true", help="with --preview: start with eye/face/focus guides shown")
    p.add_argument("--style", choices=list(A.STYLES), default=settings.DEFAULT_STYLE)
    p.add_argument("--quality", choices=list(settings.QUALITY), default=settings.DEFAULT_QUALITY)
    p.add_argument("--fps", type=int, default=settings.FPS)
    p.add_argument("--no-color", action="store_true", help="monochrome rendering")
    p.add_argument("--aspect", type=float, default=settings.STAGE_ASPECT, help="stage width/height (0.75 = 3:4 portrait, 1.78 = 16:9)")
    p.add_argument("--cell-aspect", type=float, default=settings.CELL_ASPECT, help="terminal cell height/width (default 2.0)")
    p.add_argument("--scale", type=float, default=1.0, help="multiply the stage size (e.g. 0.8 smaller, 1.2 larger when it fits)")
    p.add_argument("--brightness", type=float, default=1.0)
    p.add_argument("--contrast", type=float, default=1.0)
    p.add_argument("--sharpen", type=float, default=0.35, help="output sharpening (0 = off)")
    p.add_argument("--song-offset", type=float, default=0.0, help="shift the song start used in printed cues (seconds)")
    p.add_argument("--scene", choices=list(settings.SCENE_TIMINGS), help="play only this scene")
    p.add_argument("--start", type=float, default=0.0, help="start playback at this animation time (seconds)")
    p.add_argument("--cues", action="store_true", help="print the scene/music cue table and exit")
    p.add_argument("--pattinson", choices=("refined", "baseline"), default=None, help="Pattinson reveal version (default from config; baseline = v1 look)")
    p.add_argument("--ending", choices=("early", "original"), default=None, help="ending version: early (default, config) or original (60 s)")
    p.add_argument("--ending-advance", type=float, default=None, metavar="S", help="with --ending early: finish S seconds earlier than the original (default 2.5)")
    p.add_argument("--stats", action="store_true", help="print frame statistics after playback")
    p.add_argument("--placeholder", action="store_true", help="TEST ONLY: use abstract stand-ins if photos are missing")
    p.add_argument("--dump", metavar="T[,T...]", help="write PNG frames at these animation times and exit")
    p.add_argument("--dump-dir", default=str(ROOT / "dumps"))
    p.add_argument("--size", metavar="COLSxROWS", help="virtual terminal size (for --dump / headless use)")
    return p.parse_args()


def load_all(args, names=("craig", "craig_wide", "pattinson")):
    out = {}
    for n in names:
        out[n] = load_portrait(n, allow_placeholder=args.placeholder)
    if any(p.placeholder for p in out.values()):
        print("NOTE: using abstract PLACEHOLDER portraits (test only - not likenesses). "
              "Add your photos to assets/.", file=sys.stderr)
    return out


def make_timeline(args, term_size, portraits):
    cols, rows = term_size
    if args.scale != 1.0:
        rows = max(10, int((rows - 1) * args.scale) + 1)
        cols = max(10, int(cols * args.scale)) if args.scale < 1 else cols
    layout = compute_layout(cols, rows, args.style, args.quality, args.aspect, args.cell_aspect)
    if args.scale != 1.0:      # re-centre in the real terminal
        layout.row0 = (term_size[1] - layout.rows) // 2
        layout.col0 = (term_size[0] - layout.cols) // 2
    return Timeline(layout, portraits, args.brightness, args.contrast, args.sharpen, mono=args.no_color,
                    pattinson=getattr(args, "pattinson", None))


def virtual_size(args):
    if args.size:
        c, r = args.size.lower().split("x")
        return int(c), int(r)
    return Terminal.size()


# ---------------------------------------------------------------- dump
def do_dump(args):
    from renderer.dump import cells_to_image
    portraits = load_all(args)
    tl = make_timeline(args, virtual_size(args), portraits)
    out = Path(args.dump_dir)
    out.mkdir(parents=True, exist_ok=True)
    print(f"stage {tl.layout.cols}x{tl.layout.rows} cells, style={args.style}, pixels {tl.layout.pw}x{tl.layout.ph}")
    for ts in args.dump.split(","):
        t = float(ts)
        t0 = time.perf_counter()
        cells = tl.cells(t)
        dt = (time.perf_counter() - t0) * 1000
        path = out / f"frame_{args.style}_{t:06.2f}.png"
        cells_to_image(cells).save(path)
        print(f"  t={t:6.2f}s  render+encode {dt:6.1f} ms  -> {path}")


# ---------------------------------------------------------------- preview
def preview_states(name, st):
    if name == "craig":
        ra, rb = st.window("craig_reveal")
        D = rb - ra
        return [("Craig - in darkness (eyes first)", ra + 0.27 * D), ("Craig - light spreading", ra + 0.50 * D),
                ("Craig - fully revealed", rb - 0.2)]
    if name == "wide":
        pa, pb = st.window("camera_pullback")
        D = pb - pa
        return [("Craig wide - tight on Bond after the dissolve", pa + 0.60 * D), ("Craig wide - pulling back", pa + 0.80 * D),
                ("Craig wide - full composition", pb - 0.05), ("Craig wide - the glow swells", st.peak - 0.5)]
    pa, pb = st.window("pattinson_reveal")
    D = pb - pa
    return [("Pattinson - partial shadow", pa + 0.30 * D), ("Pattinson - light across the face", pa + 0.55 * D),
            ("Pattinson - identity emerging", pa + 0.70 * D), ("Pattinson - peak recognisability", pa + 0.86 * D),
            ("Pattinson - completed reveal", pb - 0.01)]


def guides_cells(tl, name, portraits):
    """Flat 'cover' view of the processed portrait with eye/face/focus marks."""
    import numpy as np
    from renderer.camera import Camera, VIEW_UNITS
    p = portraits["craig_wide" if name == "wide" else name]
    st = tl.st
    s = max(VIEW_UNITS * st.aspect / p.w, VIEW_UNITS / p.h)
    fx, fy = max(p.w * s - VIEW_UNITS * st.aspect, 0), max(p.h * s - VIEW_UNITS, 0)
    cam = Camera((p.anchor[0] - .5) * fx, (p.anchor[1] - .5) * fy, 1.0)
    img = p.photo.render(cam, st.pw, st.ph, (0, 0), s)

    def scr(u, v):
        x, y = cam.world_to_screen((u - .5) * p.w * s, (v - .5) * p.h * s, st.pw, st.ph)
        return x, y
    ex, ey = scr(*p.eyes)
    fcx, fcy = scr(*p.face)
    yy, xx = np.mgrid[0:st.ph, 0:st.pw]
    for cx, cy, col in ((ex, ey, (0.2, 1.0, 1.0)), (fcx, fcy, (1.0, 0.9, 0.2))):
        m = ((np.abs(xx - cx) < 0.6) & (np.abs(yy - cy) < 4)) | ((np.abs(yy - cy) < 0.6) & (np.abs(xx - cx) < 4))
        img[m] = col
    rx = p.face_w * 0.5 * p.w * s / (VIEW_UNITS / st.ph)
    d = np.hypot((xx - fcx) / rx, (yy - fcy) / (rx * 1.3))
    img[np.abs(d - 1) < 0.04] = (1.0, 0.9, 0.2)
    return A.encode(tl.finish(img), tl.layout.style)


def do_preview(args):
    name = args.preview
    portraits = load_all(args)
    term = Terminal()
    styles = ["braille", "glyph", "blocks"]
    with term:
        style_i = styles.index(args.style)
        guides = args.guides
        state_i = 0
        redraw = True
        auto_t = 0.0
        tl = disp = None
        while True:
            if redraw or tl is None:
                args.style = styles[style_i]
                size = term.size()
                term.write("\x1b[48;2;0;0;0m\x1b[2J\x1b[0m\x1b[1;1H\x1b[38;2;120;120;120mbuilding...\x1b[0m")
                tl = make_timeline(args, size, portraits)
                disp = Display(term, tl.layout.rows, tl.layout.cols, tl.layout.row0, tl.layout.col0, settings.DIRTY_THRESHOLD)
                states = preview_states(name, tl.st)
                label, t = states[state_i % len(states)]
                cells = guides_cells(tl, name, portraits) if guides else tl.cells(t)
                disp.present(cells)
                tag = f" {label}  |  style: {args.style}  |  {'guides ' if guides else ''}[space] state  [s] style  [g] guides  [q] quit "
                if any(p.placeholder for p in portraits.values()):
                    tag += " | PLACEHOLDER (not a likeness)"
                term.write(f"\x1b[{term.size()[1]};1H\x1b[0m\x1b[38;2;130;130;130m{tag[:term.size()[0] - 1]}\x1b[0m")
                redraw = False
                auto_t = time.perf_counter()
            k = term.poll_key()
            if k in ("q", "\x1b"):
                break
            elif k in (" ", "n"):
                state_i += 1
                redraw = True
            elif k == "s":
                style_i = (style_i + 1) % len(styles)
                redraw = True
            elif k == "g":
                guides = not guides
                redraw = True
            elif args.compare and time.perf_counter() - auto_t > 4.0:
                style_i = (style_i + 1) % len(styles)
                redraw = True
            time.sleep(0.03)


# ---------------------------------------------------------------- playback
def countdown(term, args, song_start):
    n = settings.COUNTDOWN_SECONDS if args.countdown is None else args.countdown
    cols, rows = term.size()
    grey = "\x1b[38;2;150;150;150m"
    lines = [
        "007 - NO TIME TO DIE",
        "",
        f"Suggested music start: {fmt(song_start)}",
        f"Explosion peak: animation {fmt(settings.EXPLOSION_PEAK)} / music {fmt(song_start + settings.EXPLOSION_PEAK)}",
        "",
        "Start your phone recording, then press any key.",
    ]
    term.write("\x1b[48;2;0;0;0m\x1b[2J\x1b[0m")
    for i, ln in enumerate(lines):
        term.write(f"\x1b[{rows // 2 - 3 + i};{max(1, (cols - len(ln)) // 2)}H{grey}{ln}\x1b[0m")
    term.wait_key()
    term.write("\x1b[48;2;0;0;0m\x1b[2J\x1b[0m")
    for sec in range(n, 0, -1):
        term.write(f"\x1b[{rows // 2};{cols // 2}H\x1b[38;2;70;70;70m{sec}\x1b[0m")
        time.sleep(1.0)
        term.write("\x1b[48;2;0;0;0m\x1b[2J\x1b[0m")
    time.sleep(0.4)


def play(term, tl, disp, fps, t_start, t_end):
    dt = 1.0 / fps
    clock = time.perf_counter
    t0 = clock() - t_start                 # animation time == clock() - t0, never a frame counter
    late = frames = 0
    worst = 0.0
    while True:
        now = clock() - t0
        if now >= t_end:
            break
        disp.present(tl.cells(now))
        frames += 1
        worst = max(worst, clock() - t0 - now)
        k = term.poll_key()
        if k in ("q", "\x1b"):
            return False
        nxt = (int(now / dt) + 1) * dt     # next frame boundary in animation time
        wait = nxt - (clock() - t0)
        if wait > 0:
            time.sleep(wait)
        else:
            late += 1
    play.stats = dict(frames=frames, late=late, worst_ms=worst * 1000)
    return True


def main():
    args = parse_args()
    if args.ending or args.ending_advance is not None:
        settings.apply_ending(args.ending, args.ending_advance)
    timings = dict(settings.SCENE_TIMINGS)
    if args.cues:
        print_cues(timings, settings.EXPLOSION_PEAK, settings.SONG_START_SECONDS + args.song_offset)
        return 0
    try:
        if args.dump:
            do_dump(args)
            return 0
        if args.preview:
            cols, rows = Terminal.size()
            do_preview(args)
            return 0
        cols, rows = Terminal.size()
        if cols < settings.MIN_TERMINAL[0] or rows < settings.MIN_TERMINAL[1]:
            print(f"Terminal too small ({cols}x{rows}); need at least "
                  f"{settings.MIN_TERMINAL[0]}x{settings.MIN_TERMINAL[1]}. Maximise the window "
                  f"or reduce the font size (Ctrl+scroll) and try again.")
            return 1
        portraits = load_all(args)
        print("Preparing scenes...", flush=True)
        tl = make_timeline(args, (cols, rows), portraits)
    except MissingPhoto as e:
        print(f"\n{e}\n", file=sys.stderr)
        return 2

    t_start, t_end = args.start, settings.ANIMATION_DURATION
    if args.scene:
        t_start, t_end = timings[args.scene]
    song_start = settings.SONG_START_SECONDS + args.song_offset
    term = Terminal()
    done = False
    with term:
        disp = Display(term, tl.layout.rows, tl.layout.cols, tl.layout.row0, tl.layout.col0, settings.DIRTY_THRESHOLD)
        if args.record and not args.no_countdown:
            countdown(term, args, song_start)
        else:
            time.sleep(0.6)
        disp.clear()
        done = play(term, tl, disp, args.fps, t_start, t_end)
        disp.clear()
        time.sleep(0.5)
    print("Done." if done else "Stopped.")
    if args.stats and hasattr(play, "stats"):
        s = play.stats
        print(f"frames drawn: {s['frames']}  slow frames (> 1/{args.fps}s): {s['late']}  worst frame: {s['worst_ms']:.0f} ms")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
