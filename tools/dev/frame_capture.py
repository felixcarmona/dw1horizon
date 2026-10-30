#!/usr/bin/env python3
"""Frame-exact recorder for PCSX-Redux (tools/dev/emulator.py, EMU_PORT): the emulator is paused at every
vertical refresh (a GPU::Vsync Lua listener), so every displayed frame is captured (60 per emulated
second), with RAM ranges read at the same pause. The game's timing is counted in emulated refreshes,
so the pauses do not change what it shows. Slow: about 10 frames per real second.

Usage:
  frame_capture.py DIR SECONDS [ADDR:LEN ...]   DIR/000000.png ... + DIR/ram.jsonl (one line per frame:
                                           {"f": n, "ram": {"ADDR": "hex", ...}})
  frame_capture.py mp4 DIR OUT.mp4 [SCALE]      encodes DIR at 60 fps (H.264, nearest-neighbour SCALE, default 2)

As a module: rec = FrameRec(); rec.start(); rec.step() -> frame number; rec.shot(path);
rec.ranges([(addr, n), ...]); rec.read() -> [bytes, ...]; rec.poke(addr, bytes); rec.stop() (always: it removes the pause at each refresh).
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import json, os, subprocess, sys, urllib.parse, urllib.request

ROOT = _DEV_ROOT
PORT = int(os.environ.get('EMU_PORT', '38090'))
BASE = f'http://127.0.0.1:{PORT}'
LUA_FILE = os.path.join(ROOT, f'build/framerec-{PORT}.lua')

SETUP = """
FRAMEREC = FRAMEREC or {n = 0, on = false}
if not FRAMEREC.l then
  FRAMEREC.l = PCSX.Events.createEventListener('GPU::Vsync', function()
    if FRAMEREC.on then FRAMEREC.n = FRAMEREC.n + 1; PCSX.pauseEmulator() end
  end)
end
FRAMEREC.on = true
-- reads the RAM ranges set by FrameRec.ranges() as one hex string (far cheaper than the 2 MB dump)
FRAMEREC.rd = function()
  local m = PCSX.getMemPtr()
  local out = {}
  for _, r in ipairs(FRAMEREC.ranges or {}) do
    for i = r[1], r[1] + r[2] - 1 do out[#out + 1] = string.format('%02x', m[i]) end
  end
  return table.concat(out)
end
return FRAMEREC.n
"""


def api(path, data=None, timeout=30):
    return urllib.request.urlopen(urllib.request.Request(BASE + path, data=data), timeout=timeout).read()


def lua(code):
    if len(code) < 80:
        return api('/api/v1/lua/eval?code=' + urllib.parse.quote(code)).decode()
    open(LUA_FILE, 'w').write(code)
    return api('/api/v1/lua/eval?file=' + urllib.parse.quote(LUA_FILE)).decode()


class FrameRec:
    def start(self):
        self.n = int(lua(SETUP))
        return self.n

    def step(self):
        """Runs the emulator to the next refresh and returns its number (it stays paused there)."""
        lua('PCSX.resumeEmulator() return 1')
        while True:
            n = int(lua('return FRAMEREC.n'))
            if n != self.n:
                self.n = n
                return n

    def shot(self, path):
        open(path, 'wb').write(api('/api/v1/screen/still'))

    def ram(self):
        return api('/api/v1/cpu/ram/raw')

    def ranges(self, ranges):
        """Sets the (addr, len) ranges that read() returns, concatenated."""
        self.lens = [n for _, n in ranges]
        lua('FRAMEREC.ranges = {' + ','.join(f'{{{a & 0x1FFFFF},{n}}}' for a, n in ranges) + '} return 1')

    def read(self):
        h = bytes.fromhex(lua('return FRAMEREC.rd()'))
        out, o = [], 0
        for n in self.lens:
            out.append(h[o:o + n]); o += n
        return out

    def poke(self, addr, data):
        off = addr & 0x1FFFFF
        api(f'/api/v1/cpu/ram/raw?offset={off}&size={len(data)}', data=data)

    def stop(self):
        lua('FRAMEREC.on = false PCSX.resumeEmulator() return 1')


def mp4(src, out, scale=2):
    ffmpeg = os.path.expanduser('~/.local/bin/ffmpeg')
    cmd = [ffmpeg, '-y', '-loglevel', 'error', '-framerate', '60', '-i', os.path.join(src, '%06d.png'),
           '-vf', f'scale=iw*{scale}:ih*{scale}:flags=neighbor', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
           '-crf', '20', out]
    subprocess.run(cmd, check=True)


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == 'mp4':
        mp4(a[1], a[2], int(a[3]) if len(a) > 3 else 2)
        return
    out, secs = a[0], float(a[1])
    ranges = [(int(x.split(':')[0], 0), int(x.split(':')[1], 0)) for x in a[2:]]
    os.makedirs(out, exist_ok=True)
    rec = FrameRec()
    rec.start()
    rec.ranges(ranges)
    try:
        with open(os.path.join(out, 'ram.jsonl'), 'w') as log:
            for i in range(int(secs * 60)):
                f = rec.step()
                rec.shot(os.path.join(out, f'{i:06d}.png'))
                if ranges:
                    log.write(json.dumps({'f': f, 'ram': {hex(ad): b.hex()
                                                          for (ad, _), b in zip(ranges, rec.read())}}) + '\n')
    finally:
        rec.stop()
    print(f'{out}: {int(secs * 60)} frames')


if __name__ == '__main__':
    main()
