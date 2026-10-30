#!/usr/bin/env python3
"""npc_models.py: every NPC model in RAM: kept slots byte-identical to the file, dropped slots -> 1-frame stub."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import sys, struct, os
import membudget as mb, npcanims
em = mb.Emu(); r = em.ram(); s = em.syms
ks, _, _ = npcanims.audit(npcanims.os.path.join(npcanims.ROOT, 'extracted/SCN/DG.SCN'), npcanims.os.path.join(npcanims.ROOT, 'extracted/SCN/MAPHEAD.SCN'))
keep = {t: sum(1 << b for b in v) for t, v in ks.items()}
R = lambda a, n: r[a - 0x80000000:a - 0x80000000 + n]
npc = s['NPC_MODELS']
for i in range(5):
    m = npc + i * mb.MC
    use, mmd = struct.unpack('<I', R(m, 4))[0], struct.unpack('<I', R(m + 12, 4))[0]
    if not use or not mmd: continue
    t = struct.unpack('<h', R(m + 0x18, 2))[0]
    p, name = mb.model_file(t); d = open(p, 'rb').read()
    ta, offs, size = npcanims.mmd_slots(d)
    tab = mmd + struct.unpack('<I', R(mmd + 4, 4))[0]
    bad = []; stubs = 0
    keptoffs = {o for k, o in enumerate(offs) if o and keep[t] >> k & 1}
    for k, o in enumerate(offs):
        no = struct.unpack('<I', R(tab + 4 * k, 4))[0]
        if not o:
            if no: bad.append((k, 'was 0'))
            continue
        if o in keptoffs:
            ln = size[o]
            if R(tab + no, ln) != d[ta + o:ta + o + ln]: bad.append((k, 'data'))
        else:
            fc = struct.unpack('<H', R(tab + no, 2))[0] & 0x7FFF
            if fc != 1: bad.append((k, 'stub fc', fc))
            stubs += 1
    hdr = struct.unpack('<II', R(mmd - 8, 8))
    print(f'slot {i} {mb.digi_name(t):14} {name} file {len(d)} block {hdr[1] * 8} stubs {stubs} {"OK" if not bad else bad}')
st = struct.unpack('<3i', R(s['MOD_NPC_TRIM_STATS'], 12))
print('trim stats models/bytes/last', st)
