"""Walk several screens in one go (pad only) on the running emulator (EMU_PORT, DW_SYMS) and log (time, x, z, screen) every ~0.15 s for the overlay video.
Usage: tour.py TOUR.json  -> [[screen, MAP_FILE, [[[u, v], pause], ...]], ...]; writes TOUR.json.poslog.json.
Each segment waits until the game is on its screen, then walks its background-pixel waypoints (BFS over free tiles)."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import sys, os, time, threading, json, subprocess, math
from collections import deque
ROOT = _DEV_ROOT
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import dwmap; from tools.dev import emulator as emu
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from maps import reach

def show(*keys):
    out = subprocess.run(['python3', os.path.join(ROOT, 'tools/dev/game_state.py'), 'show', *keys],
                         capture_output=True, text=True).stdout.strip().splitlines()
    return out

def state():
    out = show('tamer.location', 'current_screen')
    loc = [int(v) for v in out[0].split('[')[1].split(']')[0].split(',')]
    return loc[0], loc[2], int(out[1].split()[-1])

LOG = []; T0 = time.time(); STOP = False
def logger():
    while not STOP:
        try: LOG.append((time.time() - T0, *state()))
        except Exception: pass
        time.sleep(0.15)

def pos():
    for _ in range(30):
        try: x, z, _ = state(); return x, z
        except Exception: time.sleep(0.1)
    raise RuntimeError('no position')

def screen():
    for _ in range(30):
        try: return state()[2]
        except Exception: time.sleep(0.1)

_battle_toggle = False
_dialog_count = 0

def handle_events():
    """A wild Digimon's line, a battle, its result: close dialogs with X and wait battles out. True while something held the pad."""
    try:
        out = show('tamer.state', 'game_state', 'in_menu'); st = int(out[0].split()[-1]); gs = int(out[1].split()[-1]); menu = int(out[2].split()[-1])
    except Exception: return False
    if menu and gs == 0: emu.press('CIRCLE', 8); time.sleep(0.8); return True   # a menu opened by an X pressed at the partner's side: close it
    if gs != 0:                                       # a battle runs (1 fight, 2 result): "FINISH!! PUSH" wants CIRCLE, the result panel's
        global _battle_toggle                         # boxes want X (a third box, e.g. a learned technique, stalled a walk for 4 min on CIRCLE alone)
        _battle_toggle = not _battle_toggle
        emu.press('CIRCLE' if _battle_toggle else 'CROSS', 6); time.sleep(1.2); return True
    if st in (6, 7, 20):                              # a dialog: a wild Digimon's line, the result, a care event (7 poop, 20 sick)
        global _dialog_count
        _dialog_count += 1
        emu.press('CIRCLE' if _dialog_count % 4 == 0 else 'CROSS', 12); time.sleep(0.6); return True   # every fourth press CIRCLE, in case X is not what it wants
    _dialog_count = 0
    return False

class Seg:
    def __init__(self, mapfile):
        self.m = dwmap.MapFile(open(mapfile, 'rb').read()); self.vp, self.bx, self.by, self.bz = dwmap.camera_basis(self.m)
        self.R = reach.from_spawn_coordinates(self.m)
    def wp(self, u, v):
        m = self.m; cx = (u - m.width * 64) / m.projection; cy = (v - m.height * 64) / m.projection
        d = [self.bx[i] * cx + self.by[i] * cy + self.bz[i] for i in range(3)]; t = -self.vp[1] / d[1]
        return self.vp[0] + t * d[0], self.vp[2] + t * d[2]
    def free(self, tx, tz): return 0 <= tx < 100 and 0 <= tz < 100 and self.m.collision[tz * 100 + tx] == 0
    def path(self, a, b):                   # over the engine's reachable lattice (reach.py), every 6th point
        snap = lambda p: min(self.R, key=lambda q: (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2)
        sa, sb = snap(a), snap(b); prev = {sa: None}; q = deque([sa])
        while q:
            c = q.popleft()
            if c == sb: break
            for d in ((10, 0), (-10, 0), (0, 10), (0, -10), (10, 10), (10, -10), (-10, 10), (-10, -10)):
                n = (c[0] + d[0], c[1] + d[1])
                if n in self.R and n not in prev: prev[n] = c; q.append(n)
        if sb not in prev: return [b]
        out = []; c = sb
        while c: out.append(c); c = prev[c]
        out = out[::-1]
        return out[30::30] + [b]

    def path_tiles(self, a, b):
        tile = lambda x, z: (int(x / 100) + 50 - (1 if x < 0 else 0), 50 - int(z / 100) - (1 if z > 0 else 0))
        sa, sb = tile(*a), tile(*b)
        if not self.free(*sb):
            sb = min((abs(i - sb[0]) + abs(j - sb[1]), (i, j)) for i in range(100) for j in range(100) if self.free(i, j))[1]
        prev = {sa: None}; q = deque([sa])
        while q:
            c = q.popleft()
            if c == sb: break
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                n = (c[0] + d[0], c[1] + d[1])
                if n not in prev and self.free(*n) and self.free(c[0] + d[0], c[1]) and self.free(c[0], c[1] + d[1]):
                    prev[n] = c; q.append(n)
        if sb not in prev: return [b]
        out = []; c = sb
        while c: out.append(((c[0] - 50) * 100 + 50, (49 - c[1]) * 100 + 50)); c = prev[c]
        return out[::-1][1:]

import struct as _struct
from tools.dev import game_state as _gs
def move_partner_behind(x, z, tx, tz, dist=380):
    """Puts the partner DIST units behind the tamer (away from the target): on a narrow terrace it stands in the way and
    the tamer pushes against it for minutes (a narrow zigzag strip)."""
    try:
        _gs.read_ram()
        dx, dz = tx - x, tz - z; d = math.hypot(dx, dz) or 1.0
        px, pz = int(x - dx / d * dist), int(z - dz / d * dist)
        _gs.poke(_gs.A('PARTNER_POSITION_DATA+0x78'), _struct.pack('<3i', px, 0, pz))
        _gs.poke(_gs.A('PARTNER_ENTITY+0x10'), _struct.pack('<3i', px << 15, 0, pz << 15))
        print(f'  partner moved behind to ({px}, {pz})', flush=True)
    except Exception as e: print('  partner move failed', e, flush=True)

def freeze_clock():
    subprocess.run(['python3', os.path.join(ROOT, 'tools/dev/game_state.py'), 'set', 'gametime_running=0', 'hour=10',
                    'partner.para.condition=0', 'partner.para.poopingTimer=-1', 'partner.para.poopLevel=2000', 'partner.para.tiredness=0',
                    'partner.stats.currentMP=3000', 'partner.stats.currentHP=5100'], capture_output=True)   # no begging, and MP for the
    # next fight: five fights drained 3000 MP and the sixth never ended (with MP too low for any technique the finisher prompt waits forever)

def go(target, scr, seg, tol=70, max_steps=60):
    # the pad moves the player in screen directions (the engine turns the input by the camera's yaw), so the buttons
    # come from the on-screen delta between the player and the target, not from the world delta; the hold time is
    # proportional to the distance (the tamer walks about 900 units/s), so a long leg is one long press
    tx, tz = target; stuck = 0; last = None
    basis = (seg.vp, seg.bx, seg.by, seg.bz)
    for _ in range(max_steps):
        had_event = False
        for _k in range(150):                           # up to about three minutes of dialogs and battle per step
            if not handle_events(): break
            had_event = True
        if had_event: freeze_clock()                    # a battle starts the clock again
        if screen() != scr: return 'left'
        x, z = pos(); dx, dz = tx - x, tz - z; d = math.hypot(dx, dz)
        if d < tol: return True
        pa, pb = dwmap.project(seg.m, basis, (x, 0, z)), dwmap.project(seg.m, basis, (tx, 0, tz))
        if pa and pb: du, dv = pb[0] - pa[0], pb[1] - pa[1]
        else: du, dv = dx, -dz
        px_tol = tol * seg.m.projection / 6000 * 0.6
        btn = []
        if abs(du) > px_tol: btn.append('RIGHT' if du > 0 else 'LEFT')
        if abs(dv) > px_tol: btn.append('DOWN' if dv > 0 else 'UP')
        hold = max(0.05, min(0.35, d / 900 * 0.7))
        for b in btn: emu.api(f'/api/v1/lua/press?button={b}')
        time.sleep(hold)
        for b in btn: emu.api(f'/api/v1/lua/release?button={b}')
        if last and math.hypot(x - last[0], z - last[1]) < 25:         # 25, not 5: a tamer pushed against the partner jitters by 20
            stuck += 1
            if stuck == 2: time.sleep(0.8)          # the partner often stands in the way: give it a moment to move
            if stuck in (3, 6):
                for b in (['UP', 'DOWN'] if 'LEFT' in btn or 'RIGHT' in btn else ['LEFT', 'RIGHT'])[::1 if stuck == 3 else -1]:
                    emu.press(b, 8)
            if stuck == 5: move_partner_behind(x, z, tx, tz)   # the partner in the way on a narrow strip
            if stuck > 8: return d < 150 or False      # within 150 units of the target: arrived (the last short presses move it < 25 units)
        else: stuck = 0
        last = (x, z)
    return False

def release_all():
    for b in emu.BUTTONS:
        try: emu.api(f'/api/v1/lua/release?button={b}')
        except Exception: pass

def walk_tour(tour, logfile):
    """Walk every segment; a missed screen or unreachable waypoint fails the run."""
    for scr, mapfile, route in tour:
        t0 = time.time()
        while screen() != scr and time.time() - t0 < 20: time.sleep(0.2)
        if screen() != scr:
            raise RuntimeError(f'expected screen {scr}, still on {screen()} after 20 seconds')
        time.sleep(1.0)
        print(f'== screen {scr} (now {screen()})', flush=True)
        freeze_clock()                                          # the screen load restarts the clock
        s = Seg(mapfile)
        for (u, v), pause in route:
            t = s.wp(u, v); r = None; fails = 0
            for _guard in range(80):                        # re-plan from the live position after every step: a battle moves the player
                steps = s.path(pos(), t)
                if len(steps) <= 1: r = go(t, scr, s, tol=45); break
                r = go(steps[0], scr, s, tol=60)
                if r == 'left': break
                fails = fails + 1 if r is False else 0
                if fails >= 3: break                        # three stuck steps in a row: give the waypoint up
            with open(logfile, 'w') as f:
                json.dump(LOG, f)
            print(f'  {(u, v)} -> {tuple(round(c) for c in t)} {r}', flush=True)
            if r is False or r is None:
                raise RuntimeError(f'screen {scr}: could not reach waypoint {(u, v)}')
            if r == 'left': break
            if pause: time.sleep(pause)
        else:
            # the last waypoint of a segment is its exit: if the screen did not change, walk on past it along the last leg
            # (the exit boxes sit at the very edge, beyond the pixel the route names)
            if len(route) >= 2 and screen() == scr:
                a, b = s.wp(*route[-2][0]), s.wp(*route[-1][0]); d = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
                beyond = (b[0] + (b[0] - a[0]) / d * 500, b[1] + (b[1] - a[1]) / d * 500)
                r = go(beyond, scr, s, tol=30, max_steps=14)
                print(f'  past the exit -> {tuple(round(c) for c in beyond)} {r}', flush=True)


def main():
    import signal, atexit
    global STOP
    atexit.register(release_all)
    signal.signal(signal.SIGTERM, lambda *a: sys.exit(1))
    logfile = sys.argv[1] + '.poslog.json'
    tour = json.load(open(sys.argv[1]))
    worker = threading.Thread(target=logger, daemon=True)
    worker.start()
    try:
        walk_tour(tour, logfile)
        time.sleep(3)
    finally:
        STOP = True
        worker.join(timeout=3)
        with open(logfile, 'w') as f:
            json.dump(LOG, f)
        release_all()
    print('logged', len(LOG), 'final screen', screen())


if __name__ == '__main__':
    main()
