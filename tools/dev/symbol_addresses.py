#!/usr/bin/env python3
"""Looks up the address of a game symbol.

Usage:  symbol_addresses.py NAME [NAME ...] [--gcc]

Without --gcc it searches decomp/config/us/symbols.txt (addresses of the original
executable). With --gcc it searches the linker map of the GCC build
(decomp/build/us/psx/gcc/SLUS_010.32.elf.map), whose variables live at other
addresses: these are the ones to use for `emulator.py peek` on build/gcc.cue.
Accepts substrings (case-insensitive) and shows every match.
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import os, re, sys

ROOT = _DEV_ROOT
SYMS = os.path.join(ROOT, 'decomp/config/us/symbols.txt')
MAP = os.path.join(ROOT, 'decomp/build/us/psx/gcc/SLUS_010.32.elf.map')


def main():
    args = sys.argv[1:]; gcc = '--gcc' in args; names = [a for a in args if a != '--gcc']
    if not names: sys.exit(__doc__)
    found = {}
    if gcc:
        if not os.path.exists(MAP): sys.exit(f'missing {MAP}: tools/decomp-build.sh build')
        for line in open(MAP):
            m = re.match(r'\s+(0x[0-9a-f]+)\s+([A-Za-z_][A-Za-z0-9_]*)\s*$', line)
            if m: found[m.group(2)] = int(m.group(1), 16)
    else:
        for line in open(SYMS):
            m = re.match(r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(0x[0-9A-Fa-f]+);(.*)', line)
            if m: found[m.group(1)] = (int(m.group(2), 16), m.group(3).strip(' /'))
    for n in names:
        hits = [k for k in found if k == n] or [k for k in found if n.lower() in k.lower()]
        for k in sorted(hits)[:40]:
            v = found[k]; addr, note = (v, '') if isinstance(v, int) else v
            print(f'{k:40} {addr:#010x}  {note}')
        if not hits: print(f'{n}: not found')


if __name__ == '__main__':
    main()
