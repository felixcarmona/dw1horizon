#!/usr/bin/env python3
"""power_cut_model.py standard|expanded-story OLD.mcd NEW.mcd [--order copy|file]: for EVERY 128-byte frame N of the save's write, the card a
write stopped after N frames leaves (OLD's blocks, NEW's directory, the first N frames of the write order from NEW), and
which copy a model of the loader (pickSaveCopy, isSaveCopyValid, isExtensionValid of patch 0096 / expanded-story loader) takes:
old, new or none. --order file models the 0093 two-part write ([0,0x2000) then the extensions) with the 0093 loader."""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import struct, sys
NAME = 'BASLUS-01032DMR0'; FRAME = 0x80; BLOCK = 0x2000
mode, oldp, newp = sys.argv[1:4]; order = sys.argv[sys.argv.index('--order') + 1] if '--order' in sys.argv else 'copy'

def chain(raw):
    for i in range(1, 16):
        st, size, nxt = struct.unpack_from('<IIH', raw, FRAME * i)
        if st == 0x51 and raw[FRAME * i + 10:FRAME * i + 10 + len(NAME)].decode('ascii', 'replace') == NAME:
            c = [i]
            while nxt != 0xFFFF: c.append(nxt + 1); nxt = struct.unpack_from('<IIH', raw, FRAME * (nxt + 1))[2]
            return c, size
    return None, 0

def fileof(raw):
    c, size = chain(raw)
    return b''.join(raw[b * BLOCK:(b + 1) * BLOCK] for b in c)[:size], size

def payload(f, c): return f[0x200 + c * 0xF00:0x200 + (c + 1) * 0xF00]
def v1sum(p): return sum(p[:0x4E1]) + sum(p[0x500:])          # createSavegameChecksum skips 0x4E1-0x4FF
def s32(x): return struct.unpack('<i', struct.pack('<I', x & 0xFFFFFFFF))[0]
def version(p): return p[0x4E8] if p[0x4E4:0x4E8] == b'DW2\0' else 1

def ext_ok(f, size, c, nbytes):
    p = payload(f, c)
    if nbytes < 0x4000: return False
    if mode == 'expanded-story': nbytes = 0x6000 if version(p) >= 3 else 0x4000     # the legacy copy's layout
    E = (nbytes - 0x2000) // 2; lv = 3 if nbytes >= 0x6000 else 2
    e = f[0x2000 + c * E:0x2000 + (c + 1) * E]
    if len(e) < E: return False
    mag, ver, sz, v1c = struct.unpack_from('<4sHHi', e, 0)
    return mag == b'DW2E' and ver == lv and sz == E and struct.unpack_from('<i', e, E - 4)[0] == s32(sum(e[:E - 4])) \
        and v1c == struct.unpack_from('<i', p, 0x4FC)[0]

def copy_valid(f, size, c, nbytes):
    p = payload(f, c); ck = struct.unpack_from('<i', p, 0x4FC)[0]; s = v1sum(p)
    return ck == s or (ck == s32(~s) and version(p) >= 2 and ext_ok(f, size, c, nbytes))

def pick(f, size):
    nbytes = 0x6000 if (mode == 'expanded-story' and size >= 0x6000) else 0x4000 if size >= 0x4000 else 0x2000
    if order == 'file':                                # 0093: copy 0 valid, else copy 1
        for c in (0, 1):
            if copy_valid(f, size, c, nbytes): return c
        return None
    for i in range(4):
        c = i & 1
        if copy_valid(f, size, c, nbytes) and (i >= 2 or ext_ok(f, size, c, nbytes)): return c
    return None

old = bytearray(open(oldp, 'rb').read()); new = bytearray(open(newp, 'rb').read())
nchain, nsize = chain(new); E = (nsize - 0x2000) // 2
parts = [(0, 0x2000)] if E == 0 else [(0, 0x2000), (0x2000, 2 * E)] if order == 'file' else \
        [(0x1100, 0xF00), (0x2000 + E, E), (0, 0x1100), (0x2000, E)]
frames = [o for ofs, n in parts for o in range(ofs, ofs + n, FRAME)]
oldf, _ = fileof(old); newf, _ = fileof(new)
res = []
for N in range(len(frames) + 1):
    raw = bytearray(old); raw[0:BLOCK] = new[0:BLOCK]       # the directory after the delete/create
    for o in frames[:N]:
        b = nchain[o // BLOCK] * BLOCK + o % BLOCK; raw[b:b + FRAME] = new[b:b + FRAME]
    f, size = fileof(raw); c = pick(f, size)
    p = None if c is None else payload(f, c)
    res.append('none' if c is None else 'new' if p == payload(newf, 0) else 'old' if p in (payload(oldf, 0), payload(oldf, 1)) else 'other')
runs = []; i = 0
while i < len(res):
    j = i
    while j < len(res) and res[j] == res[i]: j += 1
    runs.append(f'{res[i]} {i}-{j - 1}'); i = j
print(f'{mode} {order}-order, {len(frames)} frames: ' + ', '.join(runs) + ('  ** SLOT LOST **' if 'none' in res or 'other' in res else ''))
