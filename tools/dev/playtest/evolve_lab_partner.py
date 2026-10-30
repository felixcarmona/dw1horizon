#!/usr/bin/env python3
"""Evolves the partner into a species of DIGI.DAT through the lab menu (the pause screen's SELECT), driving the
running emulator (EMU_PORT). The game must be in the world with control. Prints nothing when it worked.

  EMU_PORT=38060 tools/dev/playtest/evolve_lab_partner.py 326 [DIGI.DAT]      (WarGrowlmon; default build/portraits/DIGI.DAT)
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import os, subprocess, sys, time
ROOT = _DEV_ROOT
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import species

t = int(sys.argv[1])
dat = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'build/portraits/DIGI.DAT')
d, _, _ = species.read_archive(dat)
partners, _, _ = species.read_index(d)
FIXED = 11                                  # MOD_LAB_EVO_FIXED in mod_lab.c
choice = FIXED + partners.index(t)
emu = lambda *a: subprocess.run([sys.executable, os.path.join(ROOT, 'tools/dev/emulator.py'), *a], capture_output=True, text=True).stdout
def key(b, f=6, w=1.5):
    emu('press', b, str(f)); emu('wait', str(w))
key('START', 8, 2)
key('SELECT', 8, 2)
for _ in range(3): key('DOWN', 6, 1)          # the evolve entry, MOD_LAB_OPT_EVOLVE = 3 (since patch 0080)
emu('poke', 'MOD_LAB_EVO_CHOICE', choice.to_bytes(4, 'little').hex())
key('RIGHT', 6, 1); key('LEFT', 6, 1)        # redraw the entry
emu('poke', 'MOD_LAB_EVO_CHOICE', choice.to_bytes(4, 'little').hex())
key('CROSS', 8, 2)
key('TRIANGLE', 8, 3)
key('START', 10, 3)
