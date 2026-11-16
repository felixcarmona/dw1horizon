"""Disc container detection, PSP PBP and CHD v5 raw CD extraction.

The PBP path matches web/js/pbp.js. Only the Python standard library is needed; no disc data
is retained after ConversionCache.close() (also registered for process exit).
"""
import atexit
import binascii
import lzma
import os
import re
import shutil
import struct
import tempfile
import zlib

BLOCK = 16 * 2352
CONVERSION_NEED = 700 * 1024 ** 2
ARCHIVES = {'.zip', '.7z', '.rar', '.gz', '.xz', '.bz2', '.tar'}


class FormatError(ValueError):
    pass


class Cancelled(Exception):
    pass


def sniff(path):
    """Container name or None. Magic takes precedence over filename suffixes."""
    with open(path, 'rb') as f:
        head = f.read(4096)
    for magic, kind in ((b'\0PBP', 'pbp'), (b'MComprHD', 'chd'), (b'ECM\0', 'ecm'),
                        (b'PK\x03\x04', 'archive'), (b'7z\xbc\xaf\x27\x1c', 'archive'),
                        (b'Rar!', 'archive')):
        if head.startswith(magic):
            return kind
    if re.search(rb'^\s*FILE\s+(?:"|\S)', head.lstrip(b'\xef\xbb\xbf'), re.I | re.M):
        return 'cue'
    low = os.fsdecode(path).lower()
    ext = os.path.splitext(low)[1]
    if ext in ARCHIVES or re.search(r'\.(part\d+\.rar|\d{3}|z\d\d)$', low):
        return 'archive'
    return ext[1:] if ext in ('.cue', '.pbp', '.chd', '.ecm') else None


def _check(cancel):
    if cancel is not None and cancel.is_set():
        raise Cancelled()


def _read(f, at, n):
    f.seek(at)
    data = f.read(n)
    if len(data) != n:
        raise FormatError('PBP encrypted')
    return data


def _layout(f):
    head = _read(f, 0, 0x28)
    if head[:4] != b'\0PBP':
        raise FormatError('not PBP')
    psar = struct.unpack_from('<I', head, 0x24)[0]
    tag = _read(f, psar, 16)
    if tag.startswith(b'PSTITLEIMG'):
        raise FormatError('PBP multi-disc')
    if not tag.startswith(b'PSISOIMG0000'):
        raise FormatError('PBP encrypted')
    toc = _read(f, psar + 0x800, 0x400)
    sectors = 0
    for p in range(0, len(toc) - 9, 10):
        if toc[p + 2] == 0xa2:
            msf = toc[p + 7:p + 10]
            if any(x >> 4 > 9 or x & 15 > 9 for x in msf):
                raise FormatError('PBP encrypted')
            m, s, frame = [(x >> 4) * 10 + (x & 15) for x in msf]
            if s >= 60 or frame >= 75:
                raise FormatError('PBP encrypted')
            sectors = (m * 60 + s) * 75 + frame - 150
    if sectors <= 0:
        raise FormatError('PBP encrypted')
    return psar, sectors * 2352


def decode_pbp(src, dst, progress=None, cancel=None):
    """Write raw sectors to dst; progress(fraction), cancel threading.Event.

    Failed/cancelled extraction removes dst. Inflate output is bounded to one
    block so corrupt or encrypted input cannot allocate arbitrary amounts.
    """
    if os.path.realpath(src) == os.path.realpath(dst):
        raise ValueError('PBP input and output must differ')
    try:
        _check(cancel)
        with open(src, 'rb') as f:
            psar, total = _layout(f)
            blocks = -(-total // BLOCK)
            if 0x4000 + blocks * 32 > 0x100000:
                raise FormatError('PBP encrypted')
            index = _read(f, psar + 0x4000, blocks * 32)
            with open(dst, 'wb') as out:
                for i in range(blocks):
                    _check(cancel)
                    offset, length = struct.unpack_from('<IH', index, i * 32)
                    raw = _read(f, psar + 0x100000 + offset, length)
                    if length == BLOCK:
                        data = raw
                    else:
                        try:
                            dec = zlib.decompressobj(-15)
                            data = dec.decompress(raw, BLOCK + 1)
                            if not dec.eof or dec.unused_data or len(data) > BLOCK:
                                raise zlib.error('invalid block')
                        except zlib.error as e:
                            raise FormatError('PBP encrypted') from e
                    want = min(BLOCK, total - i * BLOCK)
                    if len(data) < want:
                        raise FormatError('PBP encrypted')
                    out.write(data[:want])
                    if progress and (i % 64 == 0 or i + 1 == blocks):
                        progress((i + 1) / blocks)
                _check(cancel)
    except BaseException:
        try:
            os.unlink(dst)
        except FileNotFoundError:
            pass
        raise


# CHD v5 follows MAME's chd.cpp/chdcodec.cpp and cdrom.cpp format.
# https://github.com/mamedev/mame/tree/master/src/lib/util
# Container checksums are CRC-16/CCITT, initial value 0xffff.
def _chd_error(reason):
    return FormatError('CHD not supported: ' + reason)


def _chd_read(f, at, size):
    if at < 0 or size < 0 or at + size > os.fstat(f.fileno()).st_size:
        raise _chd_error('truncated or invalid file')
    f.seek(at)
    data = f.read(size)
    if len(data) != size:
        raise _chd_error('truncated file')
    return data


class _Bits:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def read(self, n):
        if n < 0 or self.pos + n > len(self.data) * 8:
            raise _chd_error('truncated map')
        value = 0
        while n:
            byte, bit = divmod(self.pos, 8)
            take = min(n, 8 - bit)
            value = (value << take) | ((self.data[byte] >> (8 - bit - take)) & ((1 << take) - 1))
            self.pos += take
            n -= take
        return value


def _chd_tree(bits):
    lengths = []
    while len(lengths) < 16:
        n = bits.read(4)
        repeat = 1
        if n == 1:
            n = bits.read(4)
            if n != 1:
                repeat = bits.read(4) + 3
        if n > 8 or len(lengths) + repeat > 16:
            raise _chd_error('invalid Huffman tree')
        lengths.extend([n] * repeat)
    counts = [lengths.count(n) for n in range(9)]
    starts = [0] * 9
    start = 0
    for n in range(8, 0, -1):
        starts[n] = start
        total = start + counts[n]
        if n != 1 and total & 1:
            raise _chd_error('invalid Huffman tree')
        start = total >> 1
    tree = {}
    for symbol, n in enumerate(lengths):
        if n:
            if starts[n] >= 1 << n:
                raise _chd_error('invalid Huffman tree')
            tree[n, starts[n]] = symbol
            starts[n] += 1

    def decode():
        value = 0
        for n in range(1, 9):
            value = value * 2 + bits.read(1)
            if (n, value) in tree:
                return tree[n, value]
        raise _chd_error('invalid Huffman code')
    return decode


def _chd_map(f, at, count, hunk, compressed, cancel):
    if not compressed:
        raw = _chd_read(f, at, count * 4)
        return [(4, hunk, int.from_bytes(raw[i:i+4], 'big') * hunk, None)
                for i in range(0, len(raw), 4)]
    head = _chd_read(f, at, 16)
    size = int.from_bytes(head[:4], 'big')
    # The encoding needs at most a tree plus ~100 bits per hunk.
    if size > count * 16 + 256 or any(n > limit for n, limit in zip(head[12:15], (24, 32, 48))):
        raise _chd_error('invalid compressed map')
    bits = _Bits(_chd_read(f, at + 16, size))
    decode = _chd_tree(bits)
    types = []
    last = 0
    while len(types) < count:
        _check(cancel)
        kind = decode()
        repeat = 1
        if kind == 7:
            kind, repeat = last, 3 + decode()
        elif kind == 8:
            kind, repeat = last, 19 + (decode() << 4) + decode()
        else:
            last = kind
        if len(types) + repeat > count:
            raise _chd_error('map repeat exceeds hunk count')
        types.extend([kind] * repeat)
    offset = int.from_bytes(head[4:10], 'big')
    last_self = 0
    entries, raw = [], bytearray()
    for i, kind in enumerate(types):
        _check(cancel)
        length, crc, where = 0, 0, offset
        if kind < 4:
            length, crc = bits.read(head[12]), bits.read(16)
            if not 0 < length <= hunk:
                raise _chd_error('invalid compressed hunk length')
            offset += length
        elif kind == 4:
            length, crc = hunk, bits.read(16)
            offset += length
        elif kind == 5:
            last_self = where = bits.read(head[13])
        elif kind in (9, 10):
            last_self += kind == 10
            kind, where = 5, last_self
        elif kind in (6, 11, 12, 13):
            raise _chd_error('parent CHDs')
        else:
            raise _chd_error('invalid map compression type')
        if where >= 1 << 48:
            raise _chd_error('map offset overflow')
        if kind == 5 and where >= count:
            raise _chd_error('invalid self reference')
        entries.append((kind, length, where, crc))
        raw.extend(bytes([kind]) + length.to_bytes(3, 'big') + where.to_bytes(6, 'big') + crc.to_bytes(2, 'big'))
    if binascii.crc_hqx(raw, 0xffff) != int.from_bytes(head[10:12], 'big'):
        raise _chd_error('map CRC mismatch')
    return entries


def _chd_layout(f):
    head = _chd_read(f, 0, 16)
    if head[:8] != b'MComprHD':
        raise _chd_error('bad magic')
    if int.from_bytes(head[12:16], 'big') != 5:
        raise _chd_error('only CD-ROM v5 is supported')
    if int.from_bytes(head[8:12], 'big') != 124:
        raise _chd_error('invalid v5 header')
    head = _chd_read(f, 0, 124)
    codecs = [head[i:i+4] for i in range(16, 32, 4)]
    if codecs[0] == bytes(4) and any(c != bytes(4) for c in codecs):
        raise _chd_error('invalid codec list')
    logical, map_at, meta_at, hunk, unit = struct.unpack_from('>QQQII', head, 32)
    if any(head[104:124]):
        raise _chd_error('parent CHDs')
    if unit != 2448 or not hunk or hunk % 2448 or hunk > 16 * 1024 ** 2:
        raise _chd_error('requires CD-ROM frames of 2448 bytes')
    if not logical or logical % 2448 or logical > 1024 ** 3 or not map_at:
        raise _chd_error('invalid logical size or map')
    tracks, old, visited = [], None, set()
    while meta_at:
        if meta_at in visited or len(visited) >= 1024:
            raise _chd_error('invalid metadata chain')
        visited.add(meta_at)
        mh = _chd_read(f, meta_at, 16)
        length = int.from_bytes(mh[5:8], 'big')
        if length > 65536:
            raise _chd_error('oversized metadata')
        data = _chd_read(f, meta_at + 16, length)
        meta_at = int.from_bytes(mh[8:16], 'big')
        if mh[:4] in (b'CHGT', b'CHGD', b'CHTR', b'CHT2', b'CHCD', b'CHSE'):
            if mh[:4] == b'CHSE':
                if data.rstrip(b'\0') != b'SESSION:1':
                    raise _chd_error('multisession metadata')
                continue
            if mh[:4] in (b'CHGT', b'CHGD'):
                raise _chd_error('GD-ROM metadata')
            if mh[:4] == b'CHCD':
                old = data
                continue
            try:
                fields = dict(part.split(':', 1) for part in data.rstrip(b'\0').decode('ascii').split())
                number, frames = int(fields['TRACK']), int(fields['FRAMES'])
                kind = fields['TYPE']
                if number != len(tracks) + 1 or not 0 < frames or kind not in ('MODE1_RAW', 'MODE2_RAW', 'AUDIO'):
                    raise ValueError()
                if fields['SUBTYPE'] not in ('NONE', 'RW', 'RW_RAW'):
                    raise ValueError()
                if mh[:4] == b'CHT2':
                    pregap, postgap = int(fields['PREGAP']), int(fields['POSTGAP'])
                    pgtype = fields['PGTYPE']
                    if pregap < 0 or postgap < 0 or (pgtype.startswith('V') and
                            (pgtype[1:] != kind or pregap > frames)):
                        raise ValueError()
                    if fields['PGSUB'] not in ('NONE', 'RW', 'RW_RAW'):
                        raise ValueError()
                if int(fields.get('PAD', '0')):
                    raise ValueError()
            except (ValueError, KeyError, UnicodeError) as e:
                raise _chd_error('unsupported track or pregap layout') from e
            # FRAMES includes stored pregaps. Virtual PREGAP/POSTGAP belong only
            # in the cue; extractcd does not insert them into the binary image.
            tracks.append((kind, frames, (-frames) % 4))
    if not tracks and old is not None:
        if len(old) != (1 + 99 * 6) * 4:
            raise _chd_error('invalid CHCD metadata')
        endian = '<' if int.from_bytes(old[:4], 'little') <= 99 else '>'
        words = struct.unpack(endian + 'I' * (1 + 99 * 6), old)
        if not 1 <= words[0] <= 99:
            raise _chd_error('invalid CHCD track count')
        for i in range(words[0]):
            kind, sub, size, subsize, frames, extra = words[1+i*6:7+i*6]
            if kind not in (1, 6, 7) or size != 2352 or extra != (-frames) % 4 or not frames:
                raise _chd_error('unsupported CHCD track')
            tracks.append(({1: 'MODE1_RAW', 6: 'MODE2_RAW', 7: 'AUDIO'}[kind], frames, extra))
    if not tracks or len(tracks) > 99 or sum(n + pad for _, n, pad in tracks) * 2448 != logical:
        raise _chd_error('missing or inconsistent CD track metadata')
    return codecs, logical, map_at, hunk, tracks


# CD-ROM EDC is a reflected CRC with polynomial 0xd8018001, not zlib's CRC32.
def _edc_table():
    table = []
    for i in range(256):
        value = i
        for _ in range(8):
            value = (value >> 1) ^ (0xd8018001 if value & 1 else 0)
        table.append(value)
    return table


_EDC = _edc_table()


def _cd_edc(data):
    value = 0
    for byte in data:
        value = (value >> 8) ^ _EDC[(value ^ byte) & 255]
    return value


_ECC_F = [(i << 1) ^ (0x11d if i & 128 else 0) for i in range(256)]
_ECC_B = [0] * 256
for _i in range(256):
    _ECC_B[_i ^ _ECC_F[_i]] = _i


def _cd_ecc(sector):
    """Restore only P/Q parity, exactly as CHD does; retained EDC stays intact.

    Mode 2 address bytes are zero for parity, including any Form 2 sector that
    the encoder happened to flag. Unflagged sectors are never normalized.
    """
    source = bytearray(sector[12:])
    if sector[15] == 2:
        source[:4] = bytes(4)
    for major_count, minor_count, major_mult, minor_inc, dest in (
            (86, 24, 2, 86, 2076), (52, 43, 86, 88, 2248)):
        size = major_count * minor_count
        for major in range(major_count):
            index = (major >> 1) * major_mult + (major & 1)
            a = b = 0
            for _ in range(minor_count):
                value = source[index]
                index = (index + minor_inc) % size
                a = _ECC_F[a ^ value]
                b ^= value
            a = _ECC_B[_ECC_F[a] ^ b]
            sector[dest + major] = a
            sector[dest + major + major_count] = a ^ b
        source[2064:2236] = sector[2076:2248]


def _chd_dictionary(size):
    # LZMA SDK level 6, reduceSize=hunk size, then the encoded dictionary
    # property rounds up to 2*2**n or 3*2**n (minimum 4096).
    size = max(4096, min(size, 1 << 26))
    return next(v for n in range(11, 26) for v in (2 << n, 3 << n) if v >= size)


def _chd_inflate(data, size, codec):
    try:
        if codec == b'zlib':
            dec = zlib.decompressobj(-15)
            result = dec.decompress(data, size + 1)
            if not dec.eof or dec.unused_data:
                raise ValueError('invalid deflate stream')
        elif codec == b'lzma':
            dec = lzma.LZMADecompressor(lzma.FORMAT_RAW, filters=[dict(
                id=lzma.FILTER_LZMA1, dict_size=_chd_dictionary(size), lc=3, lp=0, pb=2)])
            # CHD's SDK stream omits the end marker; exact output size is known.
            result = dec.decompress(data, max_length=size)
            if dec.unused_data:
                raise ValueError('trailing LZMA data')
        else:
            raise _chd_error('codec ' + repr(codec))
        if len(result) != size:
            raise ValueError('invalid decoded length')
        return result
    except (zlib.error, lzma.LZMAError, ValueError) as e:
        if isinstance(e, FormatError):
            raise
        raise _chd_error('damaged compressed hunk') from e


def _chd_decompress(data, size, codec):
    if codec == b'cdfl':
        raise _chd_error('cdfl (FLAC) hunks require conversion with chdman extractcd')
    if codec not in (b'cdzl', b'cdlz'):
        return _chd_inflate(data, size, codec)
    frames = size // 2448
    bitmap, length_bytes = (frames + 7) // 8, 2 if size < 65536 else 3
    header = bitmap + length_bytes
    length = int.from_bytes(data[bitmap:header], 'big')
    if len(data) <= header + length or not length:
        raise _chd_error('invalid CD codec header')
    sectors = _chd_inflate(data[header:header+length], frames * 2352,
                           b'zlib' if codec == b'cdzl' else b'lzma')
    subcode = _chd_inflate(data[header+length:], frames * 96, b'zlib')
    result = bytearray()
    for i in range(frames):
        sector = bytearray(sectors[i*2352:(i+1)*2352])
        if data[i // 8] & (1 << (i % 8)):
            sector[:12] = b'\0' + b'\xff' * 10 + b'\0'
            _cd_ecc(sector)
        result.extend(sector)
        result.extend(subcode[i*96:(i+1)*96])
    return result


def decode_chd(src, dst, progress=None, cancel=None):
    """Extract v5 raw CD tracks to one BIN, dropping subcode and track padding.

    Audio samples are byte-swapped to CUE/BIN order. Unsupported variants fail
    explicitly, including FLAC when actually used (unused codec slots are OK).
    Memory is bounded to the map and a few hunks; self references are resolved
    iteratively, so cycles cannot recurse or retain a disc in memory.
    """
    if os.path.realpath(src) == os.path.realpath(dst):
        raise ValueError('CHD input and output must differ')
    try:
        _check(cancel)
        with open(src, 'rb') as f:
            codecs, logical, map_at, hunk, tracks = _chd_layout(f)
            count = (logical + hunk - 1) // hunk
            entries = _chd_map(f, map_at, count, hunk, any(c != bytes(4) for c in codecs), cancel)
            cached_index, cached_data = None, None

            def read_hunk(index):
                nonlocal cached_index, cached_data
                seen = set()
                while entries[index][0] == 5:
                    _check(cancel)
                    if index in seen:
                        raise _chd_error('cyclic self reference')
                    seen.add(index)
                    index = entries[index][2]
                if index == cached_index:
                    return cached_data
                kind, length, where, crc = entries[index]
                if crc is None and where == 0:
                    data = bytes(hunk)
                else:
                    data = _chd_read(f, where, length)
                    if kind < 4:
                        data = _chd_decompress(data, hunk, codecs[kind])
                if crc is not None and binascii.crc_hqx(data, 0xffff) != crc:
                    raise _chd_error('hunk CRC mismatch')
                cached_index, cached_data = index, data
                return data

            frame_at = done = 0
            total = sum(n for _, n, _ in tracks)
            with open(dst, 'wb') as out:
                for kind, frames, pad in tracks:
                    remaining = frames
                    while remaining:
                        _check(cancel)
                        index, offset = divmod(frame_at * 2448, hunk)
                        data = read_hunk(index)
                        take = min(remaining, (hunk - offset) // 2448)
                        raw = bytearray().join(data[p:p+2352] for p in range(offset, offset+take*2448, 2448))
                        if kind == 'AUDIO':
                            raw[::2], raw[1::2] = raw[1::2], raw[::2]
                        out.write(raw)
                        remaining -= take
                        frame_at += take
                        done += take
                        if progress and (index % 64 == 0 or done == total):
                            progress(done / total)
                    frame_at += pad
                _check(cancel)
    except BaseException:
        try:
            os.unlink(dst)
        except FileNotFoundError:
            pass
        raise


class ConversionCache:
    """Session-only conversions, reused while source size and mtime_ns match."""
    def __init__(self):
        self.entries = {}
        self.folder = None
        atexit.register(self.close)

    def close(self):
        if self.folder:
            shutil.rmtree(self.folder, ignore_errors=True)
        self.folder = None
        self.entries.clear()

    def discard(self, path):
        entry = self.entries.pop(os.path.abspath(path), None)
        if entry:
            try:
                os.unlink(entry[1])
            except FileNotFoundError:
                pass

    def convert(self, path, parent=None, progress=None, cancel=None):
        _check(cancel)
        path = os.path.abspath(path)
        st = os.stat(path)
        stamp = st.st_size, st.st_mtime_ns
        old = self.entries.get(path)
        if old and old[0] == stamp and os.path.isfile(old[1]):
            return old[1]
        self.discard(path)
        if self.folder is None:
            if parent:
                os.makedirs(parent, exist_ok=True)
            self.folder = tempfile.mkdtemp(prefix='disc-', dir=parent)
        kind = sniff(path)
        with open(path, 'rb') as f:
            if kind == 'chd':
                _, _, _, _, tracks = _chd_layout(f)
                total = sum(n for _, n, _ in tracks) * 2352
            else:
                _, total = _layout(f)
        label = 'CHD' if kind == 'chd' else 'PBP'
        need = max(CONVERSION_NEED, total)
        if shutil.disk_usage(self.folder).free < need:
            raise FormatError(label + ' space')
        fd, dst = tempfile.mkstemp(suffix='.bin', dir=self.folder)
        os.close(fd)
        try:
            decoder = decode_chd if kind == 'chd' else decode_pbp
            decoder(path, dst, progress, cancel)
            after = os.stat(path)
            if (after.st_size, after.st_mtime_ns) != stamp:
                raise FormatError(label + ' changed')
        except BaseException:
            try:
                os.unlink(dst)
            except FileNotFoundError:
                pass
            raise
        self.entries[path] = (stamp, dst)
        return dst
