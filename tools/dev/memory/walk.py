#!/usr/bin/env python3
"""walk.py BUTTON:FRAMES ... : press each, then print streaming stats and window."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import sys, struct, time, subprocess
import membudget as mb; from tools.dev import emulator as emu
em = mb.Emu(); em.ram(); s = em.syms
names = 'opens pref hits waits miss syncV syncMax prefMax inval reopen err rows rowV'.split()
def show(tag):
    r = em.ram()
    st = ''
    if 'MOD_TFS_STATS' in s.t:
        v = struct.unpack_from('<13i', r, s['MOD_TFS_STATS'] - 0x80000000)
        st = ' '.join(f'{n}={x}' for n, x in zip(names, v) if n in ('pref','hits','waits','miss','syncMax','prefMax','inval','reopen'))
    md = s['MAP_TILE_DATA'] - 0x80000000
    cx, cy = struct.unpack_from('<hh', r, md + 0x1bb4)
    wx = r[s['MAP_TILE_X'] - 0x80000000]; wy = r[s['MAP_TILE_Y'] - 0x80000000]
    print(f'{tag:14} cam {cx:4},{cy:4} win {wx},{wy}  {st}', flush=True)
for spec in sys.argv[1:]:
    b, f = spec.split(':')
    for bb in b.split('+'): emu.api(f'/api/v1/lua/press?button={bb}')
    time.sleep(int(f) / 60)
    for bb in b.split('+'): emu.api(f'/api/v1/lua/release?button={bb}')
    time.sleep(0.3)
    show(spec)
