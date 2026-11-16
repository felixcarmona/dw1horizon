"""Synthetic CHD v5 fixtures only: no disc bytes or external tools required."""
import binascii
import lzma
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import zlib

from tools import isowriter as iso
from tools.patcher import discformats as d


def sector(number, mode=1):
    payload = bytes((i * 7 + number) % 256 for i in range(2048))
    if mode == 2:
        return iso.form1(number, b'\x01\0\x08\0' * 2, payload)
    body = iso.SYNC + iso.msf(number) + b'\x01' + payload
    body += struct.pack('<I', iso.edc(body)) + bytes(8)
    source = body[12:]
    p = iso._ecc_code(source, 86, iso._P)
    q = iso._ecc_code(bytes(iso._QGET(source + p)), 52, iso._Q)
    return body + p + q


def deflate(data):
    obj = zlib.compressobj(wbits=-15)
    return obj.compress(data) + obj.flush()


class Bits:
    def __init__(self):
        self.parts = []

    def put(self, value, n):
        self.parts.append(format(value, f'0{n}b') if n else '')

    def bytes(self):
        value = ''.join(self.parts)
        value += '0' * (-len(value) % 8)
        return int(value, 2).to_bytes(len(value) // 8, 'big')


def chd(tracks, codec=b'cdzl', compressed=True, references=True, rle=False,
        metadata=b'CHT2', stored_pregap=True, hunk_frames=4, self_codes=False, cycle=False):
    """Small v5 writer, with a full 4-bit Huffman alphabet for map symbols.

    Track tuples are (type, raw image, pregap). All bitmaps, CRCs and map entries
    are generated here; sectors come from the independent disc writer.
    """
    hunk = hunk_frames * 2448
    frames, texts = bytearray(), []
    for i, (kind, raw, pregap) in enumerate(tracks, 1):
        count = len(raw) // 2352
        pgtype = ('V' if stored_pregap else '') + kind
        text = f'TRACK:{i} TYPE:{kind} SUBTYPE:NONE FRAMES:{count}'
        if metadata == b'CHT2':
            text += f' PREGAP:{pregap} PGTYPE:{pgtype} PGSUB:NONE POSTGAP:0'
        texts.append(text.encode() + b'\0')
        for offset in range(0, len(raw), 2352):
            data = bytearray(raw[offset:offset+2352])
            if kind == 'AUDIO':
                data[::2], data[1::2] = data[1::2], data[::2]
            frames += data + bytes([i]) * 96
        frames += bytes(((-count) % 4) * 2448)
    logical = len(frames)
    frames += bytes(-len(frames) % hunk)
    chunks = [bytes(frames[i:i+hunk]) for i in range(0, len(frames), hunk)]
    blob = bytearray(124)
    if not compressed:
        map_at = len(blob)
        blob += bytes(len(chunks)*4)
        meta_at = len(blob)
    else:
        meta_at = len(blob)
    if metadata == b'CHCD':
        words = [len(tracks)]
        for kind, raw, _ in tracks:
            n = len(raw) // 2352
            words.extend([{'MODE1_RAW':1,'MODE2_RAW':6,'AUDIO':7}[kind],2,2352,0,n,(-n)%4])
        words.extend([0] * (1+99*6-len(words)))
        texts = [struct.pack('<'+'I'*len(words),*words)]
    for i, text in enumerate(texts):
        next_at = len(blob) + 16 + len(text) if i+1 < len(texts) else 0
        blob += metadata + len(text).to_bytes(4, 'big') + next_at.to_bytes(8, 'big') + text
    entries, payloads, seen = [], [], {}
    if not compressed:
        blob += bytes(-len(blob) % hunk)
    first = len(blob)
    for index, data in enumerate(chunks):
        if not compressed:
            struct.pack_into('>I', blob, map_at+index*4, len(blob)//hunk)
            blob += data
            continue
        if references and data in seen:
            entries.append((5, 0, index if cycle else seen[data], 0))
            continue
        seen[data] = index
        if codec in (b'cdzl', b'cdlz'):
            bitmap = bytearray((hunk_frames+7)//8)
            sectors, subcode = bytearray(), bytearray()
            for i in range(hunk_frames):
                s = bytearray(data[i*2448:i*2448+2352])
                source = bytes(4) + s[16:] if s[15] == 2 else bytes(s[12:])
                p = iso._ecc_code(source[:2064],86,iso._P)
                q = iso._ecc_code(bytes(iso._QGET(source[:2064]+p)),52,iso._Q)
                if s[:12] == iso.SYNC and s[2076:] == p+q:
                    bitmap[i//8] |= 1 << (i%8)
                    s[:12], s[2076:] = bytes(12), bytes(276)
                sectors += s
                subcode += data[i*2448+2352:(i+1)*2448]
            if codec == b'cdzl':
                packed = deflate(sectors)
            else:
                packed = lzma.compress(sectors, format=lzma.FORMAT_RAW, filters=[dict(
                    id=lzma.FILTER_LZMA1, dict_size=1<<26, lc=3, lp=0, pb=2)])
            payload = bitmap + len(packed).to_bytes(2 if hunk<65536 else 3, 'big') + packed + deflate(subcode)
        elif codec == b'zlib':
            payload = deflate(data)
        elif codec == b'lzma':
            payload = lzma.compress(data, format=lzma.FORMAT_RAW, filters=[dict(
                id=lzma.FILTER_LZMA1, dict_size=1<<26, lc=3, lp=0, pb=2)])
        else:
            payload = data
        kind = 4 if codec == b'none' else 0
        entries.append((kind, len(payload), len(blob), binascii.crc_hqx(data, 0xffff)))
        blob += payload
    if compressed:
        bits = Bits()
        # Code-length tree: all 16 symbols have length four, encoded with RLE.
        bits.put(1,4); bits.put(4,4); bits.put(13,4)
        kinds = []
        last_self = 0
        for kind, _, where, _ in entries:
            symbol = kind
            if kind == 5:
                if self_codes and where in (last_self, last_self+1):
                    symbol = 9 if where == last_self else 10
                last_self = where
            kinds.append(symbol)
        i = 0
        while i < len(kinds):
            bits.put(kinds[i], 4)
            j = i+1
            while j < len(kinds) and kinds[j] == kinds[i]:
                j += 1
            repeats = j-i-1
            if rle and 3 <= repeats <= 18:
                bits.put(7,4); bits.put(repeats-3,4)
            elif rle and 19 <= repeats <= 274:
                bits.put(8,4); bits.put((repeats-19)>>4,4); bits.put((repeats-19)&15,4)
            else:
                for _ in range(repeats):
                    bits.put(kinds[i],4)
            i = j
        lengthbits = max(e[1] for e in entries).bit_length()
        selfbits = max(1, len(chunks).bit_length())
        rawmap = bytearray()
        for symbol, (kind, length, offset, crc) in zip(kinds, entries):
            rawmap += bytes([kind]) + length.to_bytes(3,'big') + offset.to_bytes(6,'big') + crc.to_bytes(2,'big')
            if kind < 4:
                bits.put(length,lengthbits); bits.put(crc,16)
            elif kind == 4:
                bits.put(crc,16)
            elif symbol == 5:
                bits.put(offset,selfbits)
        encoded = bits.bytes()
        map_at = len(blob)
        blob += len(encoded).to_bytes(4,'big') + first.to_bytes(6,'big') + binascii.crc_hqx(rawmap,0xffff).to_bytes(2,'big')
        blob += bytes([lengthbits,selfbits,0,0]) + encoded
    blob[:16] = b'MComprHD' + struct.pack('>II',124,5)
    blob[16:32] = ((codec if codec != b'none' else b'zlib') + bytes(12)) if compressed else bytes(16)
    struct.pack_into('>QQQII',blob,32,logical,map_at,meta_at,hunk,2448)
    return blob


class CHDTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.src = Path(self.tmp.name)/'disc.chd'
        self.dst = Path(self.tmp.name)/'disc.bin'

    def roundtrip(self, tracks, **kw):
        self.src.write_bytes(chd(tracks, **kw))
        progress = []
        d.decode_chd(self.src,self.dst,progress.append)
        self.assertEqual(self.dst.read_bytes(), b''.join(t[1] for t in tracks))
        self.assertEqual(progress[-1],1)
        self.assertEqual(d.sniff(self.src),'chd')

    def test_codecs_and_maps(self):
        raw = b''.join(sector(i) for i in range(9))
        for codec in (b'cdzl',b'cdlz',b'zlib',b'lzma',b'none'):
            with self.subTest(codec=codec):
                self.roundtrip([('MODE1_RAW',raw,0)],codec=codec)
        self.roundtrip([('MODE1_RAW',raw,0)],compressed=False)
        self.roundtrip([('MODE1_RAW',raw,0)],metadata=b'CHCD')
        self.roundtrip([('MODE1_RAW',raw,0)],hunk_frames=32)

    def test_uncompressed_sparse_map(self):
        raw = bytes(2352*4)
        blob = chd([('MODE1_RAW',raw,0)],compressed=False)
        map_at = int.from_bytes(blob[40:48],'big')
        blob[map_at:map_at+4] = bytes(4)
        self.src.write_bytes(blob)
        d.decode_chd(self.src,self.dst)
        self.assertEqual(self.dst.read_bytes(),raw)

    def test_tracks_pregap_audio_and_padding(self):
        tracks = [('MODE1_RAW',b''.join(sector(i) for i in range(5)),0),
                  ('MODE2_RAW',b''.join(sector(i,2) for i in range(7)),2),
                  ('AUDIO',bytes(range(256))* (2352*3//256) + bytes(2352*3%256),1)]
        for stored in (True,False):
            self.roundtrip(tracks,stored_pregap=stored)
        self.roundtrip([(kind,raw,0) for kind,raw,_ in tracks],metadata=b'CHTR')

    def test_self_and_rle(self):
        raw = sector(0)*4
        for count in (8,28):
            for references in (True,False):
                self.roundtrip([('MODE1_RAW',raw*count,0)],references=references,rle=True)

    def test_self_shortcuts_and_cycle(self):
        first, second = sector(0)*4, sector(1)*4
        raw = first+second+first+first+second
        self.roundtrip([('MODE1_RAW',raw,0)],self_codes=True)
        self.src.write_bytes(chd([('MODE1_RAW',raw,0)],cycle=True))
        with self.assertRaisesRegex(d.FormatError,'cyclic self reference'):
            d.decode_chd(self.src,self.dst)
        self.assertFalse(self.dst.exists())

    def test_edc_and_ecc(self):
        for mode in (1,2):
            raw = sector(17,mode)
            cleared = bytearray(raw); cleared[2076:]=bytes(276)
            d._cd_ecc(cleared)
            self.assertEqual(cleared,raw)
        self.assertEqual(d._cd_edc(bytes(range(256))*8), iso.edc(bytes(range(256))*8))
        # Unflagged Form 2 / malformed sectors must keep even nonstandard EDC.
        raw = bytearray(sector(0,2)); raw[18] |= 0x20; raw[2076:]=bytes([71])*276
        self.roundtrip([('MODE2_RAW',bytes(raw),0)],codec=b'cdzl')

    def test_errors_and_cleanup(self):
        good = chd([('MODE1_RAW',sector(0)*4+sector(1)*4,0)])
        cases = [b'x', good[:-1]]
        bad=bytearray(good)
        map_at=int.from_bytes(bad[40:48],'big')
        bad[map_at+4:map_at+10]=b'\xff'*6
        cases.append(bad)
        for offset,value in ((0,b'notmagic'),(12,(4).to_bytes(4,'big')),(104,b'x'),(60,(512).to_bytes(4,'big'))):
            bad=bytearray(good); bad[offset:offset+len(value)]=value; cases.append(bad)
        bad=bytearray(good); bad[16:20]=b'cdfl'; cases.append(bad)
        bad=bytearray(good); bad[-1]^=128; cases.append(bad)
        for bad in cases:
            self.src.write_bytes(bad)
            with self.assertRaisesRegex(d.FormatError,'CHD not supported:'):
                d.decode_chd(self.src,self.dst)
            self.assertFalse(self.dst.exists())

    def test_cancel_and_cache(self):
        self.src.write_bytes(chd([('MODE1_RAW',sector(0)*32,0)]))
        stop=threading.Event()
        stop.set()
        with self.assertRaises(d.Cancelled):
            d.decode_chd(self.src,self.dst,cancel=stop)
        self.assertFalse(self.dst.exists())
        stop.clear()
        def tick(f):
            stop.set()
        with self.assertRaises(d.Cancelled):
            d.decode_chd(self.src,self.dst,tick,stop)
        self.assertFalse(self.dst.exists())
        cache=d.ConversionCache(); self.addCleanup(cache.close)
        with patch.object(d,'decode_chd',wraps=d.decode_chd) as decode:
            first=cache.convert(self.src)
            self.assertEqual(first,cache.convert(self.src)); self.assertEqual(decode.call_count,1)
            st=self.src.stat(); os.utime(self.src,ns=(st.st_atime_ns,st.st_mtime_ns+1))
            second=cache.convert(self.src)
            self.assertNotEqual(first,second); self.assertFalse(os.path.exists(first))
        cache.close(); self.assertFalse(os.path.exists(second))

    def test_cache_errors(self):
        self.src.write_bytes(chd([('MODE1_RAW',sector(0)*4,0)]))
        cache=d.ConversionCache(); self.addCleanup(cache.close)
        with patch.object(d.shutil,'disk_usage',return_value=type('Usage',(),{'free':0})()):
            with self.assertRaisesRegex(d.FormatError,'CHD space'):
                cache.convert(self.src)
        def change(_):
            st=self.src.stat()
            os.utime(self.src,ns=(st.st_atime_ns,st.st_mtime_ns+1))
        with self.assertRaisesRegex(d.FormatError,'CHD changed'):
            cache.convert(self.src,progress=change)
        self.assertFalse(cache.entries)
        self.assertEqual(list(Path(cache.folder).iterdir()),[])

    def test_desktop_and_cli(self):
        # Share the existing synthetic ISO fixture to exercise identification.
        from tools.test_desktop_patcher import image, desktop, dw
        raw=image('SLUS_013.28')
        self.src.write_bytes(chd([('MODE2_RAW',raw,0)],codec=b'zlib'))
        with patch.object(desktop,'cache_dir',return_value=self.tmp.name):
            result=desktop.identify(str(self.src))
        self.addCleanup(desktop.CONVERSIONS.close)
        self.assertEqual(result['path'],str(self.src))
        self.assertEqual(Path(dw.resolve_bin(str(self.src))).read_bytes(),raw)
        self.addCleanup(dw._CONVERSIONS.close)
        release = Path(self.tmp.name)/'release'
        release.mkdir()
        dw.copy_release_frontend(str(release))
        script = 'import dwpatch; print(dwpatch.boot_name(dwpatch.resolve_bin(' + repr(str(self.src)) + ')))'
        result = subprocess.run([sys.executable,'-c',script],cwd=release,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('SLUS_013.28',result.stdout)


if __name__ == '__main__':
    unittest.main()
