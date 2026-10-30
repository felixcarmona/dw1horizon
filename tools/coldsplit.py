#!/usr/bin/env python3
"""Cold animations: the animations a partner plays rarely (eating, reactions, pooping...) leave the resident model and are read from
the disc when they start (src/main/anim.c, startAnimation: patch 0113). The model's file keeps its normal layout; this module cuts it in
two for DIGI.DAT:

  resident   the MMD without the cold animations; each of their slots in the animation table holds
             0x80000000 | (length in words << 16) | (offset in words of the animation in the cold part)
  cold       the cold animations one after the other, each starting on a word; read from the sector after the resident part

  coldsplit.py selftest [GLOB]     split every model of GLOB (default build/walkfix/*.MMD) and join it again: the same animations
  split(mmd_bytes, nbones, slots) -> (resident, cold)       join(resident, cold, nbones, table_length) -> the whole MMD again

An animation that a non-cold slot also uses stays resident (and so do its cold slots). The engine reads whole sectors, so the cold
buffer must hold the longest cold animation plus 2047 bytes (COLD_ANIM_BUFFER in include/dw/memmap.h).
"""
import glob, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mmd

COLD_SLOTS = (5, 7, 8, 9, 10, 11, 12, 13)           # the partner's reactions, eating and pooping; no other entity plays them
FLAG = 0x80000000


def cold_set(m, slots):
    """The slots that go cold: those of `slots` whose animation no other slot uses."""
    t = m.anims.table
    inc = {s for s in slots if s < len(t) and t[s] is not None}
    out = set()
    for s in inc:
        if all(o in inc for o, x in enumerate(t) if x == t[s]):
            out.add(s)
    return sorted(out)


def table_length(res):
    """Slots in the animation table of a resident part (the table ends where the first animation starts: its smallest offset)."""
    tab = struct.unpack_from('<I', res, 4)[0]
    low, k = len(res), 0
    while 4 * k < low:
        v = struct.unpack_from('<I', res, tab + 4 * k)[0]
        if v and not v & FLAG:
            low = min(low, v)
        k += 1
    return low // 4


def entries(res):
    tab = struct.unpack_from('<I', res, 4)[0]
    return {s: v for s in range(table_length(res)) for v in [struct.unpack_from('<I', res, tab + 4 * s)[0]] if v & FLAG}


def is_split(res):
    return bool(entries(res))


def cold_length(res):
    """Bytes of the cold part the entries of a resident part reach."""
    return max(((v & 0xFFFF) + (v >> 16 & 0x7FFF)) * 4 for v in entries(res).values())


def split(data, nb, slots=COLD_SLOTS, buffer_bytes=0x2000):
    m = mmd.MMD.parse(data, nb)
    cold = cold_set(m, slots)
    if not cold:
        return bytes(data), b''
    streams, entries = [], {}
    pos = 0
    by_idx = {}
    for s in cold:
        i = m.anims.table[s]
        if i not in by_idx:
            b = m.anims.anims[i].build()
            b += b'\0' * (-len(b) % 4)
            if buffer_bytes<=0 or buffer_bytes%2048:
                raise ValueError('cold animation buffer must contain whole sectors')
            if len(b)>buffer_bytes:
                raise ValueError(f'cold animation exceeds buffer: slot {s}, {len(b)} > {buffer_bytes}')
            # The engine reads complete sectors, including the bytes before
            # this stream. A fitting stream can overflow at an unaligned start.
            if (pos%2048+len(b)+2047)//2048*2048>buffer_bytes:
                padding=(-pos)%2048;streams.append(b'\0'*padding);pos+=padding
            by_idx[i] = (pos, len(b))
            streams.append(b); pos += len(b)
        o, n = by_idx[i]
        if o // 4 > 0xFFFF or n // 4 > 0x7FFF:
            raise ValueError(f'cold animation too big: offset {o}, length {n}')
        entries[s] = FLAG | (n // 4) << 16 | (o // 4)
    for s in cold:
        m.anims.table[s] = None
    used = sorted({x for x in m.anims.table if x is not None})
    remap = {o: k for k, o in enumerate(used)}
    m.anims.anims = [m.anims.anims[o] for o in used]
    m.anims.table = [remap[x] if x is not None else None for x in m.anims.table]
    res = bytearray(m.build())
    tab = struct.unpack_from('<I', res, 4)[0]
    for s, v in entries.items():
        struct.pack_into('<I', res, tab + 4 * s, v)
    return bytes(res), b''.join(streams)


def join(resident, cold, nb, ntab):
    """The whole MMD of a split one (to check it): the cold animations are appended to the resident part and the entries made plain."""
    res = bytearray(resident)
    tab = struct.unpack_from('<I', res, 4)[0]
    n = ntab
    fix = {}
    for s in range(n):
        v = struct.unpack_from('<I', res, tab + 4 * s)[0]
        if v & FLAG:
            fix[s] = v
    end = len(res) + (-len(res) % 4)
    res += b'\0' * (end - len(res))
    placed = {}
    for s, v in fix.items():
        o, ln = (v & 0xFFFF) * 4, (v >> 16 & 0x7FFF) * 4
        if (o, ln) not in placed:
            placed[(o, ln)] = len(res)
            res += cold[o:o + ln]
        struct.pack_into('<I', res, tab + 4 * s, placed[(o, ln)] - tab)
    return bytes(res)


def same_anim(a, b):
    """The same animation: frames, start pose and instructions (the word padding after its end does not count)."""
    return a.frame_count == b.frame_count and a.has_scale == b.has_scale and a.pose == b.pose and a.instrs == b.instrs


def selftest(pattern):
    import species
    e = mmd.exe(); ok = bad = 0; saved = []; worst = 0
    for f in sorted(glob.glob(pattern)):
        t = int(os.path.basename(f).split('-')[0]); nb = e.bone_count[t]
        data = open(f, 'rb').read()
        res, cold = split(data, nb)
        orig = mmd.MMD.parse(data, nb)
        back = mmd.MMD.parse(join(res, cold, nb, len(orig.anims.table)), nb)
        same = (table_length(res) == len(orig.anims.table) and (not cold or (is_split(res) and cold_length(res) == len(cold))) and len(back.anims.table) == len(orig.anims.table)
                and all((x is None) == (y is None) and (x is None or same_anim(back.anims.anims[x], orig.anims.anims[y]))
                        for x, y in zip(back.anims.table, orig.anims.table))
                and back.tmd.build() == orig.tmd.build() if hasattr(back.tmd, 'build') else True)
        if same:
            ok += 1; saved.append(len(cold)); worst = max(worst, len(res))
        else:
            bad += 1; print('DIFFERENT', f)
    print(f'{ok} models split and joined again identical, {bad} different; cold avg {sum(saved) / max(1, len(saved)) / 1024:.1f} KB; '
          f'largest resident part {worst} bytes')
    return bad == 0


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'selftest':
        sys.exit(0 if selftest(sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'build/walkfix/*.MMD')) else 1)
    print(__doc__)
