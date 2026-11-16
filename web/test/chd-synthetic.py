"""Generate a large synthetic benchmark CHD in bounded memory, without self references.

Run from the repo root: python3 web/test/chd-synthetic.py build/chd/synthetic.chd cdlz 320
Uses the desktop tests' independent sector encoder and CHD codec writer.
"""
import binascii
import hashlib
from pathlib import Path
import struct
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.test_chd import Bits, chd, sector
from tools.patcher import discformats as d

path, codec, mib = sys.argv[1], sys.argv[2].encode(), int(sys.argv[3])
raw = b''.join(sector(i, 2) for i in range(32))
sample = chd([('MODE2_RAW', raw, 0)], codec=codec, hunk_frames=32)
with tempfile.TemporaryFile() as f:
    f.write(sample)
    f.flush()
    codecs, logical, map_at, hunk, tracks = d._chd_layout(f)
    kind, length, offset, crc = d._chd_map(f, map_at, 1, hunk, True, None)[0]
    payload = sample[offset:offset+length]
assert kind == 0
count = -(-(mib * 1048576) // len(raw))
text = f'TRACK:1 TYPE:MODE2_RAW SUBTYPE:NONE FRAMES:{count*32} PREGAP:0 PGTYPE:MODE2_RAW PGSUB:NONE POSTGAP:0\0'.encode()
meta = b'CHT2' + len(text).to_bytes(4, 'big') + bytes(8) + text
first = 124 + len(meta)
bits, rawmap = Bits(), bytearray()
bits.put(1, 4); bits.put(4, 4); bits.put(13, 4)
for i in range(count):
    bits.put(0, 4)
for i in range(count):
    bits.put(length, length.bit_length()); bits.put(crc, 16)
    rawmap += bytes([0]) + length.to_bytes(3, 'big') + (first+i*length).to_bytes(6, 'big') + crc.to_bytes(2, 'big')
encoded = bits.bytes()
maphead = len(encoded).to_bytes(4, 'big') + first.to_bytes(6, 'big') + binascii.crc_hqx(rawmap, 65535).to_bytes(2, 'big') + bytes([length.bit_length(), 0, 0, 0])
head = bytearray(124)
head[:16] = b'MComprHD' + struct.pack('>II', 124, 5)
head[16:20] = codec
struct.pack_into('>QQQII', head, 32, count*hunk, first+count*length, 124, hunk, 2448)
hash_ = hashlib.sha1()
with open(path, 'wb') as out:
    out.write(head); out.write(meta)
    for i in range(count):
        out.write(payload); hash_.update(raw)
    out.write(maphead); out.write(encoded)
print(f'{count*len(raw)} bytes; expected SHA-1 {hash_.hexdigest()}')
