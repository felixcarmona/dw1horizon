#!/usr/bin/env python3
"""duckstation.py: drive DuckStation headless (second emulator, accurate GPU timing; docs/developing.md).

  duckstation.py start [CUE] [--oc PCT] [--icache] [--state FILE] [--hq]
                                                boot under a private Xvfb (:117); --oc sets CPU overclock,
                                                --icache emulates the instruction cache's timing,
                                                --hq draws like a handheld setup (OpenGL on the GPU, 3x,
                                                xBR texture filter, PGXP) under a private Xorg
  duckstation.py stop                                    stop DuckStation and the Xvfb started by `start`
  duckstation.py press BUTTON [FRAMES]                   hold a pad button (keyboard binding) for FRAMES/60 s
  duckstation.py seq "CROSS 8, wait 3, ..." | FILE.seq   same syntax as tools/dev/emulator.py seq (buttons and waits only)
  duckstation.py peek ADDR|SYMBOL [LEN] / poke ADDR|SYMBOL HEX
  duckstation.py shot OUT.png                            screenshot of the game window
  duckstation.py savestate                               DuckStation state to slot 1 (savestates/SLUS-01032_1.sav)
  duckstation.py measure SECONDS                         vblanks, logic ticks and presented frames over SECONDS
  duckstation.py warp SCREEN [EXIT]                      like game_state.py warp

Memory goes through DuckStation's GDB stub (127.0.0.1:2345, or DS_GDB_PORT): connecting halts the
emulator, the request runs, and `c` resumes it. Symbols come from DS_MAP (default:
the map copied next to the disc in .tools/duckstation/disc/)."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import os, re, socket, struct, subprocess, sys, time, json, glob

R = _DEV_ROOT
D = os.path.join(R, '.tools/duckstation')
BIN = os.path.join(D, 'squashfs-root/usr/bin')
INI = os.path.join(BIN, 'settings.ini')
RUN = os.path.join(D, 'run.json')
DISPLAY = os.environ.get('DS_DISPLAY', ':117')   # DS_DISPLAY=:139: a private X display, so two instances can run side by side
MAP = os.environ.get('DS_MAP', os.path.join(D, 'disc/full.map'))
GDB_PORT = int(os.environ.get('DS_GDB_PORT', '2345'))   # DS_GDB_PORT=38201: the stub on another port (set at start)
KEYS = {'CROSS': 'k', 'CIRCLE': 'l', 'SQUARE': 'j', 'TRIANGLE': 'i', 'START': 'Return', 'SELECT': 'BackSpace',
        'UP': 'Up', 'DOWN': 'Down', 'LEFT': 'Left', 'RIGHT': 'Right', 'L1': 'q', 'R1': 'e', 'L2': '1', 'R2': '3'}
ENV = dict(os.environ, DISPLAY=DISPLAY, SDL_AUDIODRIVER='dummy',
           VK_DRIVER_FILES='/nonexistent.json', VK_ICD_FILENAMES='/nonexistent.json')   # no Vulkan: OpenGL (radeonsi under --hq's Xorg, llvmpipe under Xvfb)
ENV.pop('LD_LIBRARY_PATH', None)


def sym(name):
    if re.match(r'^(0x)?[0-9a-fA-F]{8}$', name): return int(name, 16)
    base, off = (name.split('+') + ['0'])[:2]
    for l in open(MAP):
        m = re.match(r'\s+(0x[0-9a-f]+)\s+' + re.escape(base) + r'\s*$', l)
        if m: return int(m.group(1), 16) + int(off, 0)
    sys.exit('unknown symbol ' + name)


class GDB:
    def __init__(self):
        for _ in range(50):
            try: self.s = socket.create_connection(('127.0.0.1', GDB_PORT), timeout=5); break
            except OSError: time.sleep(0.2)
        else: sys.exit('no GDB stub on 127.0.0.1:%d' % GDB_PORT)
        self.buf = b''
        self.cmd('?')

    def cmd(self, p, reply=True):
        p = p.encode()
        self.s.sendall(b'$' + p + b'#%02x' % (sum(p) & 255))
        if not reply: return None
        while True:
            m = re.search(rb'\$([^#]*)#..', self.buf)
            if m: self.buf = self.buf[m.end():]; return m.group(1).decode()
            chunk = self.s.recv(65536)
            if not chunk: raise ConnectionError('GDB stub disconnected')
            self.buf += chunk

    def read(self, addr, n):
        out = b''
        while n:
            k = min(n, 0x800); out += bytes.fromhex(self.cmd('m%x,%x' % (addr, k))); addr += k; n -= k
        return out

    def write(self, addr, data):
        r = self.cmd('M%x,%x:%s' % (addr, len(data), data.hex()))
        if r != 'OK': sys.exit('write failed: ' + r)

    def close(self):
        self.cmd('c', reply=False); time.sleep(0.05); self.s.close()


def setini(sec, k, v):
    s = open(INI).read()
    m = re.search(r'(?ms)^\[' + sec + r'\]\n(.*?)(?=^\[|\Z)', s)
    body = m.group(1)
    if re.search(r'(?m)^' + k + ' = ', body): body = re.sub(r'(?m)^' + k + ' = .*$', k + ' = ' + v, body)
    else: body = k + ' = ' + v + '\n' + body
    open(INI, 'w').write(s[:m.start(1)] + body + s[m.end(1):])


def window():
    out = subprocess.run(['xdotool', 'search', '--name', '^Digimon World'], env=ENV, capture_output=True, text=True).stdout.split()
    if not out: sys.exit('game window not found')
    return out[-1]


def focus(w):
    # without a window manager Qt only takes keys after a click in the window
    subprocess.run(['xdotool', 'windowfocus', '--sync', w, 'mousemove', '--window', w, '20', '20', 'click', '1'], env=ENV)


def press(btn, frames=8):
    w = window(); k = KEYS[btn.upper()]
    focus(w)
    subprocess.run(['xdotool', 'keydown', k], env=ENV); time.sleep(int(frames) / 60)
    subprocess.run(['xdotool', 'keyup', k], env=ENV)


def load_run():
    try: return json.load(open(RUN))
    except (OSError, ValueError): return {}


def alive(pid):
    try: os.kill(pid, 0); return True
    except OSError: return False


def stop_xorg():
    try: pid = open('/tmp/.X117-lock').read().strip()
    except OSError: return
    subprocess.run(['sudo', '-n', 'kill', pid]); time.sleep(1)


def main(a):
    if a[0] == 'start':
        cue = os.path.abspath(a[1]) if len(a) > 1 and not a[1].startswith('--') else os.path.join(D, 'disc/full.cue')
        oc = int(a[a.index('--oc') + 1]) if '--oc' in a else 100
        setini('CPU', 'OverclockEnable', 'true' if oc != 100 else 'false')
        setini('CPU', 'OverclockNumerator', str(oc)); setini('CPU', 'OverclockDenominator', '100')
        setini('CPU', 'RecompilerICache', 'true' if '--icache' in a else 'false')   # instruction cache timing
        setini('Debug', 'GDBServerPort', str(GDB_PORT))
        hq = '--hq' in a   # a handheld's typical graphics settings; without it the software renderer
        for k, v in (('Renderer', 'OpenGL' if hq else 'Software'), ('ResolutionScale', '3' if hq else '1'),
                     ('TextureFilter', 'xBR' if hq else 'Nearest'), ('DitheringMode', 'TrueColor'),
                     ('PGXPEnable', 'true' if hq else 'false'), ('PGXPTextureCorrection', 'true'), ('PGXPCulling', 'true')):
            setini('GPU', k, v)
        setini('Display', 'ScreenshotMode', 'InternalResolution' if hq else 'ScreenResolution')
        run = load_run(); run['hq'] = hq
        if (hq or os.environ.get('DS_XORG')) and not os.path.exists('/tmp/.X117-lock'):
            # a real X server on the GPU (modesetting + glamor, no monitor): DRI3, so Mesa uses the hardware driver, not llvmpipe
            subprocess.Popen(['sudo', '-n', 'Xorg', DISPLAY, '-config', os.path.join(D, 'xorg.conf'), '-noreset', '-ac', '-nolisten', 'tcp',
                              '-sharevts', '-novtswitch', '-logfile', os.path.join(D, 'xorg.log'), 'vt1'],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(4); run['xorg'] = True
        elif not (hq or os.environ.get('DS_XORG')) and run.get('xorg'): stop_xorg(); run.pop('xorg')
        if hq or os.environ.get('DS_XORG'):
            # With no physical keyboard, Xorg defaults to legacy "base" XKB rules.
            # DuckStation converts Qt nativeScanCode using evdev/XKB codes: legacy
            # Down=104 becomes NumpadEnter, whereas evdev Down=116 is DownArrow.
            # Set the map before Qt starts (also when reusing the private server).
            subprocess.run(['setxkbmap', '-rules', 'evdev', '-model', 'pc105', '-layout', 'us'],
                           env=ENV, check=True)
        if not (hq or os.environ.get('DS_XORG')) and not (run.get('xvfb') and alive(run['xvfb'])):
            run['xvfb'] = subprocess.Popen(['Xvfb', DISPLAY, '-screen', '0', '1024x768x24', '-nolisten', 'tcp'],
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).pid
            time.sleep(2)
        args = [os.path.join(BIN, 'duckstation-qt'), '-nogui', '-batch']
        if '--state' in a: args += ['-statefile', os.path.abspath(a[a.index('--state') + 1])]
        log = open(os.path.join(D, 'ds.log'), 'w')
        run['ds'] = subprocess.Popen(args + ['--', cue], env=ENV, cwd=D, stdout=log, stderr=log).pid
        json.dump(run, open(RUN, 'w')); print('started', run, 'overclock %d%%' % oc)
        if '--state' not in a and '--movies' not in a: skip_movies()
    elif a[0] == 'stop':
        run = load_run()
        for k in ('ds', 'xvfb'):
            if run.get(k) and alive(run[k]):
                os.kill(run[k], 15); time.sleep(1)
                if alive(run[k]): os.kill(run[k], 9)
        if run.get('xorg'): stop_xorg()
        if os.path.exists(RUN): os.remove(RUN)
        print('stopped')
    elif a[0] == 'press': press(a[1], a[2] if len(a) > 2 else 8)
    elif a[0] == 'seq':
        src = open(a[1]).read() if os.path.exists(a[1]) else a[1]
        for line in src.splitlines():
            line = line.split('#')[0]
            for step in filter(None, (x.strip() for x in line.split(','))):
                w = step.split()
                if w[0] == 'wait': time.sleep(float(w[1]))
                else: press(w[0], w[1] if len(w) > 1 else 8)
    elif a[0] == 'peek':
        g = GDB(); b = g.read(sym(a[1]), int(a[2], 0) if len(a) > 2 else 4); g.close(); print(b.hex())
    elif a[0] == 'poke':
        g = GDB(); g.write(sym(a[1]), bytes.fromhex(a[2])); g.close()
    elif a[0] == 'shot' and load_run().get('hq'):
        # the OpenGL window grabs black under Xvfb: DuckStation's own screenshot (F10), at the internal resolution
        import shutil
        w = window(); focus(w)
        shots = os.path.join(BIN, 'screenshots')
        before = set(glob.glob(shots + '/*.png'))
        subprocess.run(['xdotool', 'key', 'F10'], env=ENV)
        for _ in range(50):
            new = set(glob.glob(shots + '/*.png')) - before
            if new: time.sleep(0.3); shutil.move(new.pop(), a[1]); break
            time.sleep(0.2)
        else: sys.exit('no screenshot from F10')
    elif a[0] == 'shot':
        w = window()
        geo = subprocess.run(['xdotool', 'getwindowgeometry', '--shell', w], env=ENV, capture_output=True, text=True).stdout
        v = dict(l.split('=') for l in geo.split())
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'x11grab', '-video_size', '%sx%s' % (v['WIDTH'], v['HEIGHT']),
                        '-i', '%s+%s,%s' % (DISPLAY, v['X'], v['Y']), '-frames:v', '1', a[1]], env=ENV)
    elif a[0] == 'savestate':
        w = window(); focus(w)
        subprocess.run(['xdotool', 'keydown', 'F2'], env=ENV); time.sleep(0.2); subprocess.run(['xdotool', 'keyup', 'F2'], env=ENV)
        time.sleep(2); print(sorted(glob.glob(os.path.join(BIN, 'savestates/*')), key=os.path.getmtime)[-1:])
    elif a[0] == 'warp':
        screen, ex = int(a[1], 0), int(a[2], 0) if len(a) > 2 else 0
        g = GDB()
        g.write(sym('TAMER_SUB_STATE'), bytes([0]))
        g.write(sym('TARGET_MAP'), struct.pack('<h', screen) if wide_ids() else bytes([screen]))
        g.write(sym('CURRENT_EXIT'), bytes([ex])); g.write(sym('TAMER_STATE'), bytes([5, 0])); g.close()
    elif a[0] == 'approach':
        # approach SLOT [DIST]: as game_state.py approach (player DIST units in front of NPC slot SLOT, facing it)
        import math
        slot, dist = int(a[1], 0), int(a[2], 0) if len(a) > 2 else 180
        g = GDB()
        pd = struct.unpack('<I', g.read(sym('NPC_ENTITIES') + slot * 0x68 + 4, 4))[0]
        if not 0x80000000 < pd < 0x801FFF00: g.close(); sys.exit(f'slot {slot}: no NPC')
        nx, _, nz = struct.unpack('<3i', g.read(pd + 0x78, 12))
        tx, _, tz = struct.unpack('<3i', g.read(sym('TAMER_POSITION_DATA') + 0x78, 12))
        d = math.hypot(tx - nx, tz - nz) or 1.0
        x, z = round(nx + (tx - nx) * dist / d), round(nz + (tz - nz) * dist / d)
        loc = struct.pack('<3i', x, 0, z)
        g.write(sym('TAMER_POSITION_DATA') + 0x78, loc); g.write(sym('STORED_TAMER_POS'), loc)
        g.write(sym('TAMER_ENTITY') + 0x10, struct.pack('<3i', x << 15, 0, z << 15))
        rot = round(math.atan2(nz - z, nx - x) * 4096 / (2 * math.pi)) & 0xFFF   # entityLookAtLocation: _atan(dz, dx)
        g.write(sym('TAMER_POSITION_DATA') + 0x72, struct.pack('<h', rot)); g.close()
        print(f'player at x={x} z={z} facing {rot}, NPC at {nx} {nz}')
    elif a[0] == 'measure':
        print(json.dumps(measure(float(a[1]))))
    elif a[0] == 'perf':
        print(json.dumps(perf(int(a[1]), float(a[2]))))
    else: sys.exit(__doc__)


def skip_movies():
    """GCC builds hang in the first STR movie under DuckStation (StGetNext never gets a
    frame; the original executable plays it): as soon as the executable is in RAM, turn
    startMovie's `jal MOV_playMovie` into a nop (the MOV overlay is reloaded per movie,
    so the patch goes into the resident caller)."""
    a = sym('startMovie'); jal = struct.pack('<I', 0x0C000000 | ((sym('MOV_playMovie') >> 2) & 0x3FFFFFF))
    for _ in range(300):
        g = GDB(); code = g.read(a, 0x80); k = code.find(jal)
        if k >= 0 and k % 4 == 0:
            g.write(a + k, bytes(4)); g.close(); print('movies skipped (nop at %#x)' % (a + k)); return
        g.close(); time.sleep(0.1)
    sys.exit('executable not seen in RAM')


def wide_ids():
    sys.path.insert(0, os.path.join(R, 'tools'))
    from tools.dev import symbols as dwsyms
    return dwsyms.wide_ids(os.environ.get('DS_BUILD', 'int'))   # worktree the disc was built from


def snap():
    g = GDB()
    v = struct.unpack('<I', g.read(sym('Vcount'), 4))[0]
    t, r = struct.unpack('<II', g.read(sym('MOD_FPS_RENDERS'), 8))[::-1]   # RENDERS at +0, TICKS at +4
    pl = struct.unpack('<I', g.read(sym('MOD_PERF_LAST'), 4))[0]
    g.close(); return v, t, r, time.time()


PERF = 'PERIOD XPASSES XGPU_MAX XGPU_SUM XRENDER_MAX XRENDER_SUM GPU_MAX GPU_SUM RENDER_MAX RENDER_SUM TICK_MAX TICK_SUM FRAMES SUM MAX'.split()


def perf(mode, secs):
    """On a build of that frame rate (mode 0/1/2 = FPS 20/30/60: a build parameter, checked against
    MOD_FPS_BUILD), reset the MOD_PERF counters, then measure() and the per-tick costs in hblank
    lines (as tools/dev/fps/frame_cost.py)."""
    g = GDB(); fps = struct.unpack('<i', g.read(sym('MOD_FPS_BUILD'), 4))[0]; g.close()
    if fps != (20, 30, 60)[mode]:
        sys.exit('the disc runs FPS=%d, not mode %d: build it with FPS=%d' % (fps, mode, (20, 30, 60)[mode]))
    g = GDB(); g.write(sym('MOD_PERF_RESET'), struct.pack('<I', 1)); g.close(); time.sleep(0.5)
    out = measure(secs)
    g = GDB(); base = sym('MOD_PERF_PERIOD'); raw = g.read(base, 4 * len(PERF)); g.close()
    v = dict(zip(PERF, struct.unpack('<%di' % len(PERF), raw)))
    assert all(sym('MOD_PERF_' + k) == base + 4 * i for i, k in enumerate(PERF))
    f = max(v['FRAMES'], 1); x = max(v['XPASSES'], 1)
    out.update(mode=mode, perf_ticks=v['FRAMES'], tick=round(v['TICK_SUM'] / f), tick_max=v['TICK_MAX'],
               render=round(v['RENDER_SUM'] / f), render_max=v['RENDER_MAX'], gpu=round(v['GPU_SUM'] / f),
               gpu_max=v['GPU_MAX'], xpasses=v['XPASSES'], xrender=round(v['XRENDER_SUM'] / x),
               xgpu=round(v['XGPU_SUM'] / x), xgpu_max=v['XGPU_MAX'], busy=round(v['SUM'] / f), busy_max=v['MAX'])
    return out


def measure(secs):
    v0, t0, r0, w0 = snap(); time.sleep(secs); v1, t1, r1, w1 = snap()
    dv = (v1 - v0) or 1
    return {'vblanks': dv, 'ticks': t1 - t0, 'frames': r1 - r0, 'wall_s': round(w1 - w0, 2),
            'emu_speed': round(dv / 59.83 / (w1 - w0), 3),
            'fps': round((r1 - r0) * 60 / dv, 2), 'ticks_per_s': round((t1 - t0) * 60 / dv, 2)}


if __name__ == '__main__':
    main(sys.argv[1:] or ['help'])
