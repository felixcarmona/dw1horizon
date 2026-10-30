#!/usr/bin/env python3
"""What changed between two builds of the species data, byte by byte: the proof that a rename changes only names
(run after a rename or a species data change).

  species_bytes.py exe A/SLUS_010.32 B/SLUS_010.32 [--exe-dir build/decomp-int/build/us/psx/gcc]
      every differing byte of two executables: DIGIMON_DATA row and field, or "outside DIGIMON_DATA"
  species_bytes.py digi A/DIGI.DAT B/DIGI.DAT
      every DIGI.DAT record that differs: which fields (para fields by name); sector moves are listed apart

Two executables to compare are made from one linked build with `tools/balance.py build --exe-dir W -o OUT`, once
per content folder (SPECIES_CONTENT=...), so only the species files differ.
"""
import argparse, collections, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import balance as B
import species as SP

PARA_OFFSETS = []
_o = 0
for _n, _f in SP.PARA_FIELDS:
    import struct
    _s = struct.calcsize('<' + _f)
    PARA_OFFSETS.append((_o, _o + _s, _n)); _o += _s


def field_at(k):
    return next(n for a, b, n in PARA_OFFSETS if a <= k < b)


def cmd_exe(a):
    exe = B.Exe(a.exe_dir)
    _, off, size = exe.where('para')
    x = open(a.a, 'rb').read(); y = open(a.b, 'rb').read()
    if len(x) != len(y): sys.exit(f'the files have different sizes ({len(x)}, {len(y)})')
    rows = collections.defaultdict(set); outside = 0
    for i in range(len(x)):
        if x[i] != y[i]:
            if off <= i < off + size:
                t, k = divmod(i - off, 0x34)
                rows[t].add(field_at(k))
            else:
                outside += 1
    n = 0
    for t, fields in sorted(rows.items()):
        na = x[off + 0x34 * t:off + 0x34 * t + 20].split(b'\0')[0].decode()
        nb = y[off + 0x34 * t:off + 0x34 * t + 20].split(b'\0')[0].decode()
        cnt = sum(1 for i in range(0x34) if x[off + 0x34 * t + i] != y[off + 0x34 * t + i]); n += cnt
        print(f'DIGIMON_DATA[{t}]: {cnt} bytes, fields {", ".join(sorted(fields))}: "{na}" -> "{nb}"')
    print(f'{n} bytes differ in DIGIMON_DATA, {outside} outside it')
    sys.exit(0 if outside == 0 else 1)


def cmd_digi(a):
    _, c1, r1 = SP.read_archive(a.a); _, c2, r2 = SP.read_archive(a.b)
    moved = []
    for t in range(max(c1, c2)):
        x = r1[t] if t < c1 else {}; y = r2[t] if t < c2 else {}
        if x == y: continue
        keys = sorted(k for k in set(x) | set(y) if x.get(k) != y.get(k))
        if set(keys) <= {'modelSector', 'texSector', 'portrait'}:
            moved.append(t); continue
        para = sorted(k for k in (x.get('para') or {}) if (x.get('para') or {}).get(k) != (y.get('para') or {}).get(k))
        print(f'{t} "{(x.get("para") or {}).get("name", "")}" -> "{(y.get("para") or {}).get("name", "")}": '
              f'{", ".join(keys)}' + (f' (para: {", ".join(para)})' if para else ''))
    print(f'{len(moved)} records differ only in where their model, texture or icon sit (sectors)')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('exe'); p.add_argument('a'); p.add_argument('b')
    p.add_argument('--exe-dir', default=os.path.join(ROOT, 'build/decomp-int/build/us/psx/gcc')); p.set_defaults(f=cmd_exe)
    p = sub.add_parser('digi'); p.add_argument('a'); p.add_argument('b'); p.set_defaults(f=cmd_digi)
    a = ap.parse_args()
    a.f(a)


if __name__ == '__main__':
    main()
