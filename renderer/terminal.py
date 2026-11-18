"""Terminal control: VT setup/restore, changed-cell diffing, keyboard input."""
import atexit
import os
import shutil
import sys
import time

import numpy as np

ESC = "\x1b"
IS_WIN = os.name == "nt"
if IS_WIN:
    import ctypes
    import msvcrt


class Terminal:
    """Context manager: alt screen, hidden cursor, UTF-8, VT sequences.

    Guarantees restoration on normal exit, exceptions, Ctrl+C and interpreter
    shutdown.
    """

    def __init__(self):
        self.out = sys.stdout.buffer
        self.active = False
        self._old_mode = None
        self._old_cp = None

    # -- lifecycle ---------------------------------------------------------
    def __enter__(self):
        if IS_WIN:
            k32 = ctypes.windll.kernel32
            h = k32.GetStdHandle(-11)
            mode = ctypes.c_uint32()
            if k32.GetConsoleMode(h, ctypes.byref(mode)):
                self._old_mode = (h, mode.value)
                k32.SetConsoleMode(h, mode.value | 0x0004 | 0x0001)   # VT processing
            self._old_cp = k32.GetConsoleOutputCP()
            k32.SetConsoleOutputCP(65001)
            try:
                ctypes.windll.winmm.timeBeginPeriod(1)                # 1 ms sleep granularity
            except OSError:
                pass
        self.active = True
        atexit.register(self.restore)
        # pure-black background everywhere (erase uses the current bg colour)
        self.write(f"{ESC}[?1049h{ESC}[?25l{ESC}[48;2;0;0;0m{ESC}[2J{ESC}[0m")
        return self

    def __exit__(self, *exc):
        self.restore()
        return False

    def restore(self):
        if not self.active:
            return
        self.active = False
        try:
            self.write(f"{ESC}[0m{ESC}[?2026l{ESC}[?25h{ESC}[?1049l")
        finally:
            if IS_WIN:
                k32 = ctypes.windll.kernel32
                if self._old_mode:
                    k32.SetConsoleMode(*self._old_mode)
                if self._old_cp:
                    k32.SetConsoleOutputCP(self._old_cp)
                try:
                    ctypes.windll.winmm.timeEndPeriod(1)
                except OSError:
                    pass

    # -- output ------------------------------------------------------------
    def write(self, s):
        self.out.write(s.encode("utf-8") if isinstance(s, str) else s)
        self.out.flush()

    @staticmethod
    def size():
        s = shutil.get_terminal_size((120, 40))
        return s.columns, s.lines

    # -- input -------------------------------------------------------------
    @staticmethod
    def poll_key():
        """Non-blocking key read; returns a lowercase str or None."""
        if IS_WIN and msvcrt.kbhit():
            ch = msvcrt.getwch()
            if ch in ("\x00", "\xe0"):
                msvcrt.getwch()
                return "special"
            return ch.lower()
        return None

    def wait_key(self):
        while True:
            k = self.poll_key()
            if k:
                return k
            time.sleep(0.03)


def sgr(fg=None, bg=None):
    s = ""
    if fg is not None:
        s += f"38;2;{fg[0]};{fg[1]};{fg[2]}"
    if bg is not None:
        s += (";" if s else "") + f"48;2;{bg[0]};{bg[1]};{bg[2]}"
    return f"{ESC}[{s}m"


class Display:
    """Draws Cells into a rows x cols region at (row0, col0), writing only the
    cells that changed since the previous frame."""

    def __init__(self, term: Terminal, rows, cols, row0=0, col0=0, threshold=3):
        self.term, self.rows, self.cols = term, rows, cols
        self.row0, self.col0, self.thr = row0, col0, threshold
        self.prev_chars = np.full((rows, cols), 0xFFFF, np.uint32)   # force first paint
        self.prev_fg = np.zeros((rows, cols, 3), np.int16)
        self.prev_bg = np.zeros((rows, cols, 3), np.int16)
        self.bytes_last = 0

    def invalidate(self):
        self.prev_chars[:] = 0xFFFF

    def present(self, cells):
        chars = cells.chars
        fg = cells.fg.astype(np.int16)
        bg = cells.bg.astype(np.int16)
        glyph = chars != 32                                          # fg only matters for glyphs
        # adaptive: when the previous frame was huge (e.g. the white-out), tolerate slightly
        # larger colour error per cell so the terminal is never flooded
        thr = self.thr + (3 if self.bytes_last > 100_000 else 0)
        d_fg = (np.abs(fg - self.prev_fg).max(-1) > thr) & glyph
        d_bg = np.abs(bg - self.prev_bg).max(-1) > thr
        dirty = (chars != self.prev_chars) | d_fg | d_bg
        rr, cc = np.nonzero(dirty)
        if len(rr) == 0:
            self.bytes_last = 0
            return
        self.prev_chars[rr, cc] = chars[rr, cc]
        self.prev_fg[rr, cc] = fg[rr, cc]
        self.prev_bg[rr, cc] = bg[rr, cc]

        ch_l = chars[rr, cc].tolist()
        fg_l = fg[rr, cc].tolist()
        bg_l = bg[rr, cc].tolist()
        rr_l, cc_l = rr.tolist(), cc.tolist()
        parts = [f"{ESC}[?2026h"]
        last_r = last_c = -9
        cur_fg = cur_bg = None
        r0, c0 = self.row0, self.col0
        for i in range(len(rr_l)):
            r, c = rr_l[i], cc_l[i]
            if r != last_r or c != last_c + 1:
                parts.append(f"{ESC}[{r + r0 + 1};{c + c0 + 1}H")
            ch = ch_l[i]
            f, b = fg_l[i], bg_l[i]
            codes = []
            if b != cur_bg:
                codes.append(f"48;2;{b[0]};{b[1]};{b[2]}")
                cur_bg = b
            if ch != 32 and f != cur_fg:
                codes.append(f"38;2;{f[0]};{f[1]};{f[2]}")
                cur_fg = f
            if codes:
                parts.append(f"{ESC}[{';'.join(codes)}m")
            parts.append(chr(ch))
            last_r, last_c = r, c
        parts.append(f"{ESC}[0m{ESC}[?2026l")
        data = "".join(parts)
        self.bytes_last = len(data)
        self.term.write(data)

    def clear(self, rgb=(0, 0, 0)):
        self.term.write(f"{ESC}[48;2;0;0;0m{ESC}[2J{ESC}[0m")
        self.invalidate()
        self.prev_bg[:] = 0
