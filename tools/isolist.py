#!/usr/bin/env python3
"""Lists the files of a PS1 image (.bin, MODE2/2352 sectors) with their LBA,
size and sector type, reading the ISO 9660 directly.

Usage:  isolist.py "Digimon World (USA).bin" [output.csv]
"""
import csv, struct, sys

RAW = 2352

class Img:
    def __init__(self, path):
        self.f = open(path, 'rb')
    def raw(self, lba):
        self.f.seek(lba * RAW); return self.f.read(RAW)
    def data(self, lba):
        return self.raw(lba)[24:24 + 2048]
    def submode(self, lba):
        return self.raw(lba)[18]

def walk(img, lba, size, path, out):
    nsec = (size + 2047) // 2048
    for i in range(nsec):
        sec = img.data(lba + i); p = 0
        while p < 2048:
            ln = sec[p]
            if ln == 0: break
            rec = sec[p:p + ln]; p += ln
            extent, = struct.unpack_from('<I', rec, 2); dlen, = struct.unpack_from('<I', rec, 10)
            flags = rec[25]; nlen = rec[32]; name = rec[33:33 + nlen]
            if name in (b'\0', b'\1'): continue
            name = name.decode('ascii').split(';')[0]
            su = rec[33 + nlen + (1 - nlen % 2):]
            xa = struct.unpack_from('>H', su, 4)[0] if len(su) >= 14 and su[6:8] == b'XA' else None
            full = f'{path}/{name}'
            if flags & 2:
                walk(img, extent, dlen, full, out)
            else:
                sm = img.submode(extent)
                kind = 'form2/STR-XA' if sm & 0x20 else 'form1/data'
                out.append(dict(path=full, lba=extent, size=dlen, sectors=(dlen + 2047) // 2048,
                                kind=kind, xa_attr=f'{xa:#06x}' if xa is not None else ''))

def main():
    img = Img(sys.argv[1]); pvd = img.data(16)
    assert pvd[1:6] == b'CD001'
    root = pvd[156:190]; extent, = struct.unpack_from('<I', root, 2); dlen, = struct.unpack_from('<I', root, 10)
    out = []; walk(img, extent, dlen, '', out)
    out.sort(key=lambda r: r['lba'])
    if len(sys.argv) > 2:
        with open(sys.argv[2], 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    total = struct.unpack_from('<I', pvd, 80)[0]
    print(f'{len(out)} files; volume {total} sectors; last file ends at LBA {max(r["lba"] + r["sectors"] for r in out)}')
    gaps = [(a['lba'] + a['sectors'], b['lba']) for a, b in zip(out, out[1:]) if b['lba'] > a['lba'] + a['sectors']]
    print('gaps between files:', gaps[:10])
    for r in out[:5] + out[-3:]: print(f'  {r["lba"]:7} {r["size"]:9} {r["kind"]:13} {r["path"]}')

if __name__ == '__main__':
    main()
