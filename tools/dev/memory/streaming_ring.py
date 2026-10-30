#!/usr/bin/env python3
"""streaming_ring.py: check every READY ring slot against the TFS file."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import sys, struct, glob, re, os
import membudget as mb
em = mb.Emu(); r = em.ram(); s = em.syms
m = open(os.environ.get('MEMORY_MAP', _DEV_ROOT + '/build/full/exe/SLUS_010.32.elf.map')).read()
a = int(re.search(r'\.bss\.TFS_SLOTS\s*\n?\s*(0x[0-9a-f]+)', m).group(1), 16)
scr = mb.screen_id(mb.Ram(r, s)); name = mb.MAPS[scr]['file']
d = open(glob.glob(f'{_DEV_ROOT}/extracted/MAP/*/{name}.TFS')[0], 'rb').read()
n = struct.unpack_from('<I', d, 4)[0]
seq = struct.unpack_from('<35b', r, s['MOD_TFS_TILE_SEQ'] - 0x80000000)
for i in range(8):
    t, st, _, lu = struct.unpack_from('<bbhI', r, a - 0x80000000 + 8 * i)
    if st != 2: print(i, 'state', st); continue
    off = 8 + 512 * n + seq[t] * 0x4004 + 4
    base = 0x11000 + i * 0x4800 + (off & 0x7FF)
    ok = r[base:base + 0x4000] == d[off:off + 0x4000]
    print(f'slot {i} tile {t} seq {seq[t]} lastUse {lu} {"OK" if ok else "BAD"}')
