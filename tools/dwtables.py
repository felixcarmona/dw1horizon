#!/usr/bin/env python3
"""Dumps the data tables of SLUS_010.32 (Digimon World USA) to CSV: items, techniques, map names and files, file
names. The species (DIGIMON_DATA and the per-species tables) are JSON files: tools/species.py extract.

Usage:  dwtables.py extracted/SLUS_010.32 [OUTPUT_DIR]

Addresses are offsets inside the file; the RAM address (vram)
is  vram = offset - 0x800 + 0x80090800  (0x800-byte PS-X EXE header,
text loaded at 0x80090800). Field names follow the structs of the
jype0/dw_decomp decompilation (include/dw/params.h, item.h, map.h); see
the decompilation's headers.
"""
import csv, os, re, struct, sys

HDR = 0x800
TEXT_VRAM = 0x80090800
f2v = lambda o: o - HDR + TEXT_VRAM
v2f = lambda v: v - TEXT_VRAM + HDR

ITEM_TABLE = (0x969dc, 128, 0x20)      # ITEM_PARA, struct Item (decomp include/dw/item.h)
ITEM_DESC_PTRS = (0x979dc, 128)   # ITEM_DESC_PTR
TECH_NAME_PTRS = (0x96054, 121)
MAP_NAME_PTRS = 0x991bc                          # MAP_NAME_PTR: pointers to 28-byte strings
MAP_FILE_ANCHOR = b'MAYO05\0'                   # stride 16: name[10] + 6 bytes of attributes
FILE_TABLE = 0x8d490                             # 12-byte names

def cstr(b):
    return b.split(b'\0')[0].decode('ascii', 'replace')

def ptr_string(d, off):
    v = struct.unpack_from('<I', d, off)[0]
    o = v2f(v)
    return cstr(d[o:o + 64])

def scan_fixed(d, anchor, stride, ok):
    """Extends a table of fixed-size records backwards and forwards from anchor."""
    s = anchor
    while ok(d[s - stride:s]): s -= stride
    e = anchor
    while ok(d[e:e + stride]): e += stride
    return s, (e - s) // stride

def dump_items(d, out):
    base, n, st = ITEM_TABLE
    rows = []
    for i in range(n):
        r = d[base + i * st: base + (i + 1) * st]
        value, merit, sorting, color, droppable, unk = struct.unpack_from('<iHhBBH', r, 20)
        rows.append(dict(id=i, name=cstr(r[:20]), value=value, merit_value=merit, sorting_value=sorting,
                         item_color=color, droppable=droppable, unk=unk,
                         raw=r[20:].hex()))
    write(out, 'items.csv', rows)

def dump_techs(d, out):
    base, n = TECH_NAME_PTRS
    write(out, 'techs.csv', [dict(id=i, name=ptr_string(d, base + i * 4)) for i in range(n)])

def dump_maps(d, out):
    names = []; p = MAP_NAME_PTRS
    while True:
        v = struct.unpack_from('<I', d, p)[0]
        if not (TEXT_VRAM <= v < 0x80135000): break
        n = cstr(d[v2f(v):v2f(v) + 28])
        if not re.fullmatch(r"[ A-Za-z0-9.'\-!?]{1,24}", n): break
        names.append(n.strip()); p += 4
    ok2 = lambda r: len(r) == 16 and re.fullmatch(rb'[A-Z0-9_]{4,8}\0+', r[:10]) is not None
    s2, n2 = scan_fixed(d, d.find(MAP_FILE_ANCHOR), 16, ok2)
    files = []
    for i in range(n2):
        r = d[s2 + i * 16:s2 + (i + 1) * 16]
        n8, n4, flags, doors, toilet, loading = struct.unpack_from('<6b', r, 10)
        files.append(dict(id=i, file=cstr(r[:10]), num_8bpp=n8, num_4bpp=n4, flags=flags, doors_id=doors,
                          toilet_id=toilet, loading_name=loading,
                          map_name=names[loading] if 0 <= loading < len(names) else ''))
    write(out, 'map_names.csv', [dict(id=i, name=n) for i, n in enumerate(names)])
    write(out, 'map_files.csv', files)
    return MAP_NAME_PTRS, len(names), s2, n2

def dump_files(d, out):
    rows = []; o = FILE_TABLE; i = 0; table = 0
    while True:
        r = d[o:o + 12]
        if r == b'\0' * 4 + d[o + 4:o + 12] and re.fullmatch(rb'[A-Z0-9_]+\.[A-Z0-9]{2,3}\0*', d[o + 4:o + 16]):
            o += 4; table += 1; i = 0; continue   # separator between tables
        if not re.fullmatch(rb'[A-Z0-9_]+\.[A-Z0-9]{2,3}\0+', r):
            break
        rows.append(dict(table=table, index=i, offset=hex(o), name=cstr(r))); o += 12; i += 1
    write(out, 'file_names.csv', rows)
    return len(rows), table + 1

def write(out, name, rows):
    with open(os.path.join(out, name), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()),
                           lineterminator='\n' if name == 'items.csv' else '\r\n'); w.writeheader(); w.writerows(rows)
    print(f'{name:16} {len(rows):4} rows')

def main():
    exe = sys.argv[1]; out = sys.argv[2] if len(sys.argv) > 2 else 'docs/data'
    os.makedirs(out, exist_ok=True)
    d = open(exe, 'rb').read()
    dump_items(d, out); dump_techs(d, out)     # the species (DIGIMON_DATA ...): tools/species.py extract
    s, n, s2, n2 = dump_maps(d, out)
    print(f'map_names: {n} pointers at {s:#x} (vram {f2v(s):#x});  map_files @ {s2:#x} (vram {f2v(s2):#x}) x{n2}')
    nf, nt = dump_files(d, out); print(f'file_names: {nf} names in {nt} tables from {FILE_TABLE:#x} (vram {f2v(FILE_TABLE):#x})')

if __name__ == '__main__':
    main()
