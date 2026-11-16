"""Disc container detection and single-disc, unencrypted PSP PBP extraction.

Matches web/js/pbp.js. Only the Python standard library is needed; no disc data
is retained after ConversionCache.close() (also registered for process exit).
"""
import atexit
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
            self.folder = tempfile.mkdtemp(prefix='pbp-', dir=parent)
        with open(path, 'rb') as f:
            _, total = _layout(f)
        need = max(CONVERSION_NEED, total)
        if shutil.disk_usage(self.folder).free < need:
            raise FormatError('PBP space')
        fd, dst = tempfile.mkstemp(suffix='.bin', dir=self.folder)
        os.close(fd)
        try:
            decode_pbp(path, dst, progress, cancel)
            after = os.stat(path)
            if (after.st_size, after.st_mtime_ns) != stamp:
                raise FormatError('PBP changed')
        except BaseException:
            try:
                os.unlink(dst)
            except FileNotFoundError:
                pass
            raise
        self.entries[path] = (stamp, dst)
        return dst
