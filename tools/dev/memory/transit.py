#!/usr/bin/env python3
"""transit.py SCREEN[:EXIT] ...: warp chain, Vcount from the warp poke to control (tamer state 0)."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import sys, struct, time
import membudget as mb
em = mb.Emu(); em.ram(); s = em.syms
def u32(r, a): return struct.unpack_from('<I', r, a - 0x80000000)[0]
def stats(r):
    if 'MOD_TFS_STATS' not in s.t: return ''
    v = struct.unpack_from('<13i', r, s['MOD_TFS_STATS'] - 0x80000000)
    names = 'opens pref hits waits miss syncV syncMax prefMax inval reopen err rows rowV'.split()
    return ' '.join(f'{n}={x}' for n, x in zip(names, v))
for spec in sys.argv[1:]:
    scr, _, ex = spec.partition(':'); scr = int(scr); ex = int(ex or 0)
    time.sleep(2.5)
    r = em.ram(); v0 = u32(r, s['Vcount'])
    em.poke(s['TAMER_SUB_STATE'], b'\0')
    em.poke(s['TARGET_MAP'], struct.pack('<h', scr) if mb.dwsyms.wide_ids(em.build) else bytes([scr]))
    em.poke(s['CURRENT_EXIT'], bytes([ex]))
    em.poke(s['TAMER_STATE'], b'\5\0')
    seen5 = False; t0 = time.time()
    while time.time() - t0 < 40:
        r = em.ram(); ts = r[s['TAMER_STATE'] - 0x80000000]
        if ts == 5: seen5 = True
        if seen5 and ts == 0 and mb.screen_id(mb.Ram(r, s)) == scr: break
        time.sleep(0.03)
    v1 = u32(r, s['Vcount'])
    print(f'{scr:3}:{ex} {v1 - v0:5} vsyncs  {stats(r)}', flush=True)
