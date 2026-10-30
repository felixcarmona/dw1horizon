#!/usr/bin/env python3
"""Opens the VS mode ("BATTLE MODE" of the title menu) on fake registered Digimon, without memory cards.

Boots DISC.cue (interpreter + debugger), waits for the title menu, writes the registered-Digimon buffer of both
players (types given below) and sets TARGET_MENU to the state that starts VS (0x38); then presses X through the
mode and map screens and takes screenshots into OUTDIR (vs-N.png).

  EMU_PORT=38068 tools/dev/playtest/versus_mode.py build/portraits.cue OUTDIR [first-player species] [-- second-player species]
  default first player: 3 183 210 250 100 115 8 45   second player: 17 184 230 5 90 252 66 40
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import os, subprocess, sys, time, struct
ROOT = _DEV_ROOT
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from tools.dev import symbols as dwsyms
from tools.image import Image

disc, out = sys.argv[1], sys.argv[2]
rest = sys.argv[3:]
p1 = [3, 183, 210, 250, 100, 115, 8, 45]
p2 = [17, 184, 230, 5, 90, 252, 66, 40]
if rest:
    k = rest.index('--') if '--' in rest else len(rest)
    p1 = [int(x) for x in rest[:k]] or p1
    p2 = [int(x) for x in rest[k + 1:]] or p2
os.makedirs(out, exist_ok=True)
emu = lambda *a: subprocess.run([sys.executable, os.path.join(ROOT, 'tools/dev/emulator.py'), *a], capture_output=True, text=True, cwd=ROOT).stdout
env = dict(os.environ, EMU_ARGS='-interpreter -debugger')
subprocess.run([sys.executable, 'tools/dev/emulator.py', 'stop'], capture_output=True, cwd=ROOT)
time.sleep(2)
subprocess.run(['cp', 'build/states/file-city.mcd', 'build/vstest-card.mcd'], cwd=ROOT)
print(subprocess.run([sys.executable, 'tools/dev/emulator.py', 'start', disc, '--card', 'build/vstest-card.mcd'], capture_output=True, text=True, cwd=ROOT, env=env).stdout.strip())

def shot(path):
    emu('shot', path)
    try:
        return Image.open(path).convert('RGB')
    except Exception:
        return None
t0 = time.time()
while time.time() - t0 < 300:
    time.sleep(4)
    im = shot(os.path.join(out, 'title.png'))
    if im is None:
        continue
    w, h = im.size
    yel = sum(1 for x in range(w * 55 // 100, w * 95 // 100) for y in range(h * 90 // 100, h * 98 // 100)
              if im.getpixel((x, y))[0] > 200 and im.getpixel((x, y))[1] > 170 and im.getpixel((x, y))[2] < 90)
    white = sum(1 for x in range(70, 250) for y in range(48, 108) if min(im.getpixel((x, y))) > 200)
    if yel > 40 and white > 150:
        break
    emu('press', 'START', '20')
else:
    sys.exit('the title menu never showed')

t = dwsyms.table(os.environ.get('DW_BUILD', 'disc-full'))
ptr = struct.unpack('<I', bytes.fromhex(emu('peek', hex(t['VS__REGISTERED_DIGIMON_BUFFER']), '4').split('\n')[0].split('  ', 1)[1].replace(' ', '')))[0]
print('buffer at', hex(ptr))
def entry(ty, n):
    e = bytearray(64)
    struct.pack_into('<7h', e, 0, 500 + n * 10, 300, 200 + n, 150, 120, 100, 50)
    e[28] = ty
    return bytes(e)
buf = b''.join(entry(ty, i) for i, ty in enumerate(p1)) + bytes(64 * (40 - len(p1)))
buf += b''.join(entry(ty, i) for i, ty in enumerate(p2)) + bytes(64 * (40 - len(p2)))
emu('poke', hex(ptr), buf.hex())
emu('poke', 'TARGET_MENU', (0x38).to_bytes(4, 'little').hex())
time.sleep(6)
for i in range(1, 9):
    emu('press', 'CROSS', '8')
    time.sleep(5)
    shot(os.path.join(out, f'vs-{i}.png'))
print('screens in', out)
