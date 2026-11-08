#!/usr/bin/env python3
"""Measure save storage with representative, explicitly constructed progress profiles.

Uses a real release card's records, upgraded to current widths. Profiles vary
history, recruits, daily pickups and script registers; they are capacity probes,
not claims to be independently played early/mid/late save files.
"""
import json
from pathlib import Path
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.dev import memory_card as mcd


def packbits(data):
    """Simple byte RLE: literal or repeated runs of up to 128 bytes."""
    out = bytearray(); at = 0
    while at < len(data):
        end = at + 1
        while end < min(at + 128, len(data)) and data[end] == data[at]:
            end += 1
        if end - at >= 3:
            out.extend((257 - (end - at), data[at])); at = end
        else:
            start = at; at = end
            while at < min(start + 128, len(data)):
                if at + 2 < len(data) and data[at] == data[at+1] == data[at+2]: break
                at += 1
            out.append(at - start - 1); out.extend(data[start:at])
    return bytes(out)


def profiles():
    f = mcd.Card(next((ROOT/'tools/dev/saves/corpus').glob('*.mcd'))).read('BASLUS-01032DMR0')
    base = dict(mcd.parse_records(f[0x2000:0x3000]))
    base[9] = base[9].ljust(14, b'\0'); base[10] = struct.pack('<hh', 470, 1)
    base[11] = b''; base[12] = bytes(128)
    for label, raised, recruits, pickups in [('early', 3, 2, 3), ('mid', 100, 50, 80), ('late', 300, 177, 300), ('full-chart', 478, 177, 1024)]:
        rs = base.copy()
        for tag, count in [(7, raised), (8, recruits), (12, pickups)]:
            b = bytearray(128)
            for i in range(count): b[i//8] |= 1 << (i%8)
            rs[tag] = bytes(b)
        rs[4] = struct.pack('<16H', *[i * (raised//3) for i in range(16)])
        raw = b''.join(struct.pack('<HH', t, len(v)) + v for t, v in sorted(rs.items())) + bytes(4)
        yield label, raw


def main():
    rows = []
    for k,v in profiles():
        head=struct.pack('<4sHHi',b'DW4E',4,4096,123456)
        legacy=head+v+bytes(4096-16-len(v))
        legacy+=struct.pack('<I',sum(legacy))
        rows.append(dict(profile=k,records_raw=len(v),framed_raw=len(v)+16,
                         packbits=len(packbits(v)),zlib=len(zlib.compress(v,9)),
                         legacy_allocated=len(legacy),legacy_packbits=len(packbits(legacy)),
                         legacy_zlib=len(zlib.compress(legacy,9))))
    print(json.dumps(dict(block=8192, header=512, payload_each=3840,
        contiguous_tail_free=0, original_defined_fields=5546, original_explicit_unused=2646,
        original_registration_padding_each=1280, registration_padding_each=1120,
        other_unused_payload_bytes=29, raw_max=850, margin=270,
        profiles=rows), indent=2))


if __name__ == '__main__': main()
