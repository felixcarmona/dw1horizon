#!/usr/bin/env python3
"""Extracts the text of the scenario scripts (SCN/DG.SCN) of Digimon World (USA).

Usage:  tools/dws/testing/dialogue.py extracted/SCN/DG.SCN [ENTRY_N ...]

DG.SCN is an archive of 222 entries aligned to 0x800 (a table of u32 offsets
at the start). Entry 0 is a copy of MAPHEAD.SCN; entries 1..222 are the
scripts of each map. Each entry starts with a table of (u16 offset,
u16 id): see blocks(); each block mixes bytecode with full-width
Shift-JIS encoded text (0x8140 space, 0x8260.. letters),
which is converted to ASCII here. Bytes that are not text are shown as
{xx} so the control codes are not lost.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import struct, sys, unicodedata

APOS = {0x8175: "'", 0x8176: '"', 0x8142: '.'}   # the game uses 「 」 as ASCII quotes and 。 as a period

def decode_run(b):
    out = []; i = 0
    while i + 1 < len(b):
        code = (b[i] << 8) | b[i + 1]
        if code in APOS: out.append(APOS[code]); i += 2; continue
        if not (is_lead(b[i]) and 0x40 <= b[i + 1] <= 0xfc): break
        try:
            ch = b[i:i + 2].decode('shift_jis')
        except UnicodeDecodeError:
            break
        out.append(unicodedata.normalize('NFKC', ch)); i += 2
    return ''.join(out), i

def is_lead(x): return 0x81 <= x <= 0x84 or 0x88 <= x <= 0x9f

def extract(block):
    """Returns a string with readable text and {xx} for the rest."""
    out = []; i = 0; run = []
    while i < len(block):
        if is_lead(block[i]) and i + 1 < len(block) and 0x40 <= block[i + 1] <= 0xfc:
            s, used = decode_run(block[i:])
            if used >= 2:
                out.append(s); i += used; continue
        out.append('{%02x}' % block[i]); i += 1
    return ''.join(out)

def entries(d):
    offs = []; p = 0
    while True:
        o = struct.unpack_from('<I', d, p)[0]
        if o % 0x800 or o <= (offs[-1] if offs else 0) or o > len(d): break
        offs.append(o); p += 4
        if o == len(d): break          # sentinel: end of file, not an entry
    if offs and offs[-1] == len(d): offs.pop()
    return [(offs[i], (offs[i + 1] if i + 1 < len(offs) else len(d))) for i in range(len(offs))]

def blocks(e):
    """Section table: u16 (table size) and (u16 id, u16 offset) pairs up to id = 0xFFFF."""
    tab = []; p = 2
    while p + 4 <= len(e):
        idx, off = struct.unpack_from('<HH', e, p); p += 4
        if idx == 0xffff: break
        tab.append((off, idx))
    end = e.find(b'\xfe\x00\xff\x00', tab[-1][0] if tab else 0)   # real end; the rest of the sector is garbage
    tab.append(((end + 4) if end >= 0 else len(e), None))
    return [(tab[k][1], tab[k][0], tab[k + 1][0]) for k in range(len(tab) - 1)]

def main():
    d = open(sys.argv[1], 'rb').read()
    ents = entries(d)
    wanted = [int(x) for x in sys.argv[2:]] or range(len(ents))
    for n in wanted:
        a, b = ents[n]; e = d[a:b]
        print(f'=== entry {n} @ {a:#x} ({b - a} bytes)')
        for idx, s, t in blocks(e):
            txt = extract(e[s:t].rstrip(b'\0'))
            print(f'--- block id={idx} off={s:#x} len={t - s}')
            print(txt)

if __name__ == '__main__':
    main()
