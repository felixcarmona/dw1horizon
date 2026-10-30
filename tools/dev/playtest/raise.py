#!/usr/bin/env python3
"""Marks Digimon types as raised in the running emulator (EMU_PORT), so the evolution chart shows them.

  EMU_PORT=38060 tools/dev/playtest/raise.py 51 210 259          originals: trigger 0x200 + type; the others: SPECIES_RAISED_BITS
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import os, subprocess, sys
ROOT = _DEV_ROOT
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from tools.dev import symbols as dwsyms
emu = lambda *a: subprocess.run([sys.executable, os.path.join(ROOT, 'tools/dev/emulator.py'), *a], capture_output=True, text=True).stdout
addr = dwsyms.table(os.environ.get('DW_BUILD', 'disc-full'))['SPECIES_RAISED_BITS']
raw = emu('peek', hex(addr), '128')
cur = bytearray(bytes.fromhex(''.join(l.split('  ', 1)[1].replace(' ', '') for l in raw.strip().split('\n')))[:128])
for a in sys.argv[1:]:
    t = int(a)
    if t < 180:
        subprocess.run([sys.executable, os.path.join(ROOT, 'tools/dev/game_state.py'), 'trigger', str(0x200 + t), '1'], capture_output=True)
    else:
        cur[t >> 3] |= 1 << (t & 7)
emu('poke', hex(addr), cur.hex())
