#!/usr/bin/env python3
"""skip-intro-movie.py EXE MAP: turns startMovie's `jal MOV_playMovie` into a nop, in the file.

The GCC builds hung in the first STR movie under DuckStation until patch 0171 (docs/developing.md); tools/dev/duckstation.py
does this in RAM, this is the same patch in the executable, for a disc that plays on a device
(build-full.sh with NO_MOVIES=1). Every movie is skipped: the boot goes straight to the title."""
import re, struct, sys

exe, mapf = sys.argv[1:3]
syms = {}
for l in open(mapf):
    m = re.match(r'\s+(0x[0-9a-f]+)\s+(startMovie|MOV_playMovie)\s*$', l)
    if m: syms[m.group(2)] = int(m.group(1), 16)
d = bytearray(open(exe, 'rb').read())
load = struct.unpack_from('<I', d, 0x18)[0]
a = syms['startMovie']
jal = struct.pack('<I', 0x0C000000 | ((syms['MOV_playMovie'] >> 2) & 0x3FFFFFF))
o = 0x800 + a - load
k = d[o:o + 0x80].find(jal)
if k < 0 or k % 4: sys.exit('jal MOV_playMovie not found in startMovie')
d[o + k:o + k + 4] = bytes(4)
open(exe, 'wb').write(d)
print('movies skipped: nop at %#x' % (a + k))
