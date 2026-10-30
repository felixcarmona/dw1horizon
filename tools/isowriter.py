#!/usr/bin/env python3
"""A PlayStation disc writer in plain Python (standard library only): the raw MODE2/2352 image (.bin + .cue) of a
disc layout, byte for byte what mkpsxiso makes of the same layout (docs/patcher.md "The disc writer").

Why: the end-user patcher (tools/patcher/dwpatch.py) lays the patched disc out on the player's machine, also in a
browser page, where mkpsxiso (a native program) cannot run.

The layout is mkpsxiso's XML (tools/disc-layout.xml, after build-disc.py's --add and --seek-order): file order,
dates, identifiers, file types (data; mixed = the STR movies, 2336-byte sectors with their subheaders) and the
license sectors. The files come from a map {disc path: source}; a source is bytes, a file name, or a Source object
(anything with .size, .read() and optionally .raw(k): the raw sector that holds sector k, to reuse its EDC/ECC).

mkpsxiso behaviour reproduced (read from its source, .tools/mkpsxiso/src/mkpsxiso: iso.cpp, cdwriter.cpp, main.cpp):
  - sectors 0-11: the license (12 x 2336 bytes from subheader on), Form 1 EDC/ECC computed; 12-15 blank Form 2
    (subheader 00 00 20 00); 16 the primary volume descriptor (submode 0x09), 17 the terminator (0x89); from 18
    the four path tables (L, L, M, M); the root directory at 18 + 4 x path table sectors;
  - the extents (directories, files, the dummy) in the XML's order, depth first (a directory's records, then its
    contents); the records inside a directory sorted by name (without ";1");
  - every extent's last sector has submode 0x89 (EOF | EOR | data), the others 0x08; the dummy's sectors 0;
  - Form 1 EDC/ECC with the address zeroed; Form 2 sectors (mixed files) with EDC 0 (the layout's xa_edc="false");
  - a directory record that would cross a sector boundary starts the next sector; CD-XA attributes after each.

  isowriter.py LAYOUT.xml DIR OUT.bin     the image of LAYOUT with its files from DIR (@DISC@ or the
                                          layout's source folder); OUT.cue next to it
"""
import hashlib
import operator
import os
import re
import struct
import sys
import xml.etree.ElementTree as ET

RAW = 2352
DATA = 2048
XA = 2336                                   # a mixed file's bytes per sector: subheader + 2324 + EDC (Form 2)
SYNC = b'\x00' + b'\xff' * 10 + b'\x00'
SUB_DATA, SUB_EOR, SUB_EOX = 0x08, 0x09, 0x89
PERM_DEFAULT, GMT_DEFAULT = 0x555, 36
DISC_TOKEN = '@DISC@'


# ---------------------------------------------------------------- EDC / ECC (CD-ROM Mode 2), fast in pure Python
_EDC8 = []
for _i in range(256):
    _e = _i
    for _k in range(8):
        _e = (_e >> 1) ^ (0xD8018001 if _e & 1 else 0)
    _EDC8.append(_e)
_EDC16 = []                                  # two bytes per step (the CRC is linear): 1028 steps for a Form 1 sector
for _v in range(65536):
    _s = _v
    _s = (_s >> 8) ^ _EDC8[_s & 0xFF]
    _s = (_s >> 8) ^ _EDC8[_s & 0xFF]
    _EDC16.append(_s)


def edc(data):
    """The EDC (CRC-32, polynomial 0xD8018001 reflected, init 0) of `data` (even length)."""
    e = 0; t = _EDC16
    for w in struct.unpack(f'<{len(data) // 2}H', data):
        e = (e >> 16) ^ t[(e ^ w) & 0xFFFF]
    return e


def _gf_mul(a, b):
    r = 0
    while b:
        if b & 1: r ^= a
        a = ((a << 1) ^ (0x11D if a & 0x80 else 0)) & 0xFF; b >>= 1
    return r


_INV3 = next(c for c in range(256) if _gf_mul(c, 3) == 1)   # ecc_b_lut: x -> x / (1 + alpha)


class _Swar:
    """GF(2^8) arithmetic on n bytes at once, packed in one Python integer (one column of the ECC per byte)."""
    def __init__(self, n):
        self.lo = int.from_bytes(b'\x7f' * n, 'little'); self.hi = int.from_bytes(b'\x80' * n, 'little')

    def mul2(self, v):
        return ((v & self.lo) << 1) ^ (((v & self.hi) >> 7) * 0x1D)

    def mulc(self, v, c):
        r = 0
        while c:
            if c & 1: r ^= v
            v = self.mul2(v); c >>= 1
        return r


_P = _Swar(86); _Q = _Swar(52)
_QIDX = []                                   # the Q code's diagonals: row m = byte (base_j + 88 m) mod 2236 of each column j
for _m in range(43):
    for _j in range(52):
        _QIDX.append(((_j >> 1) * 86 + (_j & 1) + 88 * _m) % 2236)
_QGET = operator.itemgetter(*_QIDX)


def _ecc_code(rows, w, sw):
    """One ECC code (P: 24 rows of 86 columns, Q: 43 rows of 52) of `rows` (bytes, row-major): 2 x width bytes."""
    a = b = 0; fb = int.from_bytes; mul2 = sw.mul2
    for o in range(0, len(rows), w):
        r = fb(rows[o:o + w], 'little'); a = mul2(a ^ r); b ^= r
    a = sw.mulc(mul2(a) ^ b, _INV3)
    return a.to_bytes(w, 'little') + (a ^ b).to_bytes(w, 'little')


def form1(lba, sub, data):
    """A raw Mode 2 Form 1 sector: sync, address, mode 2, the 8-byte subheader, 2048 bytes of data, EDC, ECC."""
    body = sub + data
    body += struct.pack('<I', edc(body))
    p = _ecc_code(b'\0\0\0\0' + body, 86, _P)
    q = _ecc_code(bytes(_QGET(b'\0\0\0\0' + body + p)), 52, _Q)
    return SYNC + msf(lba) + b'\x02' + body + p + q


def form2(lba, xa):
    """A raw Mode 2 Form 2 sector from 2336 bytes (subheader + 2324 data + EDC), the EDC zeroed (xa_edc false)."""
    return SYNC + msf(lba) + b'\x02' + xa[:2332] + b'\0\0\0\0'


def bcd(n):
    return (n // 10) << 4 | (n % 10)


def msf(lba):
    a = lba + 150
    return bytes((bcd(a // 4500), bcd(a // 75 % 60), bcd(a % 75)))


def blocks(size, unit=DATA):
    """GetSizeInSectors: an empty file still takes a sector."""
    return (size - 1) // unit + 1 if size else 1


# ---------------------------------------------------------------- sources
class Source:
    """A file of the disc: its size, its bytes (read once, when written) and, optionally, raw sectors of an image that
    already hold it (MOVE: their EDC/ECC are reused when the subheader and data match)."""
    def __init__(self, size, read, raw=None):
        self.size, self._read, self._raw = size, read, raw

    def read(self):
        return self._read()

    def raw(self, k):
        return self._raw(k) if self._raw else None


def as_source(x):
    if isinstance(x, Source): return x
    if isinstance(x, (bytes, bytearray, memoryview)):
        b = bytes(x); return Source(len(b), lambda: b)
    path = os.fspath(x)
    def read():
        with open(path, 'rb') as f: return f.read()
    return Source(os.path.getsize(path), read)


# ---------------------------------------------------------------- the layout
class Entry:
    def __init__(self, kind, name='', path='', date=None, xa=False, sectors=0, submode=0, attrs=None, parent=None):
        self.kind, self.name, self.path, self.date, self.xa = kind, name, path, date, xa
        self.sectors, self.submode, self.attrs, self.parent = sectors, submode, attrs or {}, parent
        self.children = []; self.lba = 0; self.size = 0

    @property
    def ident(self):                         # the name on the disc
        return self.name if self.kind == 'dir' else self.name + ';1'


class Layout:
    """mkpsxiso's XML: identifiers, license file, default attributes and the directory tree, in document order."""
    def __init__(self, xml_text):
        root = ET.fromstring(xml_text)
        track = root.find('track')
        if track is None or track.get('type') != 'data': raise ValueError('the layout has no data track')
        if root.findall('track')[1:]: raise ValueError('only one data track is supported')
        if track.get('xa_edc', 'true').lower() not in ('false', '0'):
            raise ValueError('xa_edc="true" is not supported (the layouts use false)')
        if track.get('cdvd_style', 'false').lower() not in ('false', '0'):
            raise ValueError('cdvd_style is not supported')
        ids = track.find('identifiers')
        self.ids = dict(ids.attrib) if ids is not None else {}
        lic = track.find('license')
        self.license = lic.get('file') if lic is not None else None
        da = track.find('default_attributes')
        self.defaults = self._attrs(da.attrib if da is not None else {}, None)
        tree = track.find('directory_tree')
        self.source = tree.get('source', '')
        self.root = Entry('dir', '', '', self.ids.get('creation_date'), attrs=self._attrs(tree.attrib, self.defaults))
        self.root.root = True
        self.entries = [self.root]                # mkpsxiso's EntryList: the extents' order
        self._walk(tree, self.root)

    @staticmethod
    def _attrs(a, base):
        out = dict(base) if base else dict(gmt=GMT_DEFAULT, xa_attrib=0xFF, perm=PERM_DEFAULT, gid=0, uid=0)
        for k, key in (('gmt_offs', 'gmt'), ('xa_attrib', 'xa_attrib'), ('xa_perm', 'perm'), ('xa_gid', 'gid'),
                       ('xa_uid', 'uid')):
            if k in a: out[key] = int(a[k])
        for k in ('hidden', 'offs', 'order'):
            if k in a and int(a[k]): raise ValueError(f'the attribute {k} is not supported')
        return out

    def _walk(self, node, parent):
        for e in node:
            if e.tag == 'file':
                if e.get('source'): raise ValueError('<file source=...> is not supported (files come by disc path)')
                t = (e.get('type') or 'data').lower()
                if t not in ('data', 'mixed', 'xa', 'str'): raise ValueError(f'file type {t} is not supported')
                name = e.get('name').upper()
                ent = Entry('file', name, parent.path + name, e.get('date'), xa=t != 'data',
                            attrs=self._attrs(e.attrib, self.defaults), parent=parent)
            elif e.tag == 'dir':
                name = e.get('name').upper()
                if any(c.kind == 'dir' and c.name == name for c in parent.children):
                    raise ValueError(f'directory {name} given twice')
                ent = Entry('dir', name, parent.path + name + '/', e.get('date'),
                            attrs=self._attrs(e.attrib, self.defaults), parent=parent)
            elif e.tag == 'dummy':
                if int(e.get('offs', 0)) or e.get('ecc_addr', 'false').lower() not in ('false', '0'):
                    raise ValueError('dummy offs/ecc_addr are not supported')
                ent = Entry('dummy', sectors=int(e.get('sectors')), submode=int(e.get('type', 0)), parent=parent)
            else:
                continue
            parent.children.append(ent); self.entries.append(ent)
            if ent.kind == 'dir': self._walk(e, ent)

    def files(self):
        """The disc paths of the files, in layout order."""
        return [e.path for e in self.entries if e.kind == 'file']


def _date(s, gmt, root=False):
    """ISO_DATESTAMP of a 'YYYYMMDDhhmmss[cc][+gmt]' string (ParseDateFromString)."""
    m = re.match(r'(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(?:\d{2}([+-]?\d+))?', s or '')
    if not m: raise ValueError(f'date {s!r}: the layout must give every date (mkpsxiso would use the file time)')
    y = int(m.group(1)); y = y - 1900 if y >= 1900 else 0
    if root: y %= 100
    g = int(m.group(7)) if m.group(7) is not None else gmt
    return bytes((y, int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5)), int(m.group(6)), g & 0xFF))


def _long_date(s):
    if not s or len(s) < 14 or not s[:14].isdigit(): return b'0' * 16 + b'\0'
    if s[14:16].isdigit(): return s[:16].encode() + bytes(((int(s[16:]) if s[16:] else GMT_DEFAULT) & 0xFF,))
    g = int(s[14:]) if s[14:15] in ('+', '-') else GMT_DEFAULT
    return s[:14].encode() + b'00' + bytes((g & 0xFF,))


def _pad(s, n):
    s = (s or '').upper().encode('latin-1')[:n]
    return s + b' ' * (n - len(s))


def _pair32(v):
    return struct.pack('<I', v) + struct.pack('>I', v)


def _pair16(v):
    return struct.pack('<H', v) + struct.pack('>H', v)


def _sorted(d):
    """The records of directory d in mkpsxiso's order: by name without ';1' (byte order)."""
    return sorted((c for c in d.children if c.kind != 'dummy'), key=lambda c: c.name.encode())


def _record_len(e):
    n = 33 + len(e.ident)
    return n + (n & 1) + 14


def _dir_len(d):
    n = 96                                   # '.' and '..' (34 + 14 each)
    for c in _sorted(d):
        k = _record_len(c)
        if (n & (DATA - 1)) + k > DATA: n = (n + DATA - 1) & ~(DATA - 1)
        n += k
    return n


def _path_table(lay):
    """[(name, parent index, entry)] breadth first, as mkpsxiso's GeneratePathTable."""
    out = [('', 1, lay.root)]; queue = [(lay.root, 1)]; idx = 2
    while queue:
        d, pi = queue.pop(0)
        for c in _sorted(d):
            if c.kind == 'dir':
                out.append((c.name, pi, c)); queue.append((c, idx)); idx += 1
    return out


def _path_table_len(lay):
    return sum(8 + (max(1, len(n)) + 1 & ~1) for n, _, _ in _path_table(lay))


# ---------------------------------------------------------------- planning (LBAs) and writing
class Plan:
    """The layout's LBAs for files of the given sizes: .lba {disc path: (lba, size on the disc)}, .total sectors."""
    def __init__(self, lay, sizes):
        self.lay = lay
        self.pt_len = _path_table_len(lay); self.pt_sec = blocks(self.pt_len)
        lba = 18 + 4 * self.pt_sec
        for e in lay.entries:
            if e.kind == 'dir':
                e.size = _dir_len(e); n = blocks(e.size)
            elif e.kind == 'file':
                if e.path not in sizes: raise KeyError(f'{e.path}: no source for this file of the layout')
                e.size = sizes[e.path]
                if e.xa and e.size % XA:
                    raise ValueError(f'{e.path}: a mixed file must be whole 2336-byte sectors ({e.size} bytes)')
                n = blocks(e.size, XA if e.xa else DATA)
            else:
                e.size = e.sectors * DATA; n = e.sectors
            e.lba = lba; e.nsec = n; lba += n
        self.total = lba
        # what the directory records say: a mixed file's size is its sectors x 2048
        self.lba = {e.path: (e.lba, DATA * e.nsec if e.xa else e.size) for e in lay.entries if e.kind == 'file'}


def plan(layout, sizes):
    lay = layout if isinstance(layout, Layout) else Layout(layout)
    return Plan(lay, sizes)


def _record(e, lba, length, date, ident, xa_attr, filenum, attrs):
    n = 33 + len(ident); pad = n & 1
    rec = bytearray(n + pad + 14)
    rec[0] = len(rec)
    rec[2:10] = _pair32(lba); rec[10:18] = _pair32(length); rec[18:25] = date
    rec[25] = 2 if e.kind == 'dir' else 0
    rec[28:32] = _pair16(1); rec[32] = len(ident); rec[33:33 + len(ident)] = ident
    x = n + pad
    rec[x:x + 2] = struct.pack('>H', attrs['gid']); rec[x + 2:x + 4] = struct.pack('>H', attrs['uid'])
    rec[x + 4:x + 6] = struct.pack('>H', xa_attr); rec[x + 6:x + 8] = b'XA'; rec[x + 8] = filenum
    return bytes(rec)


class _Extent:
    """mkpsxiso's M2F1 sector view for WriteMemory: records packed in sectors, the last one EOX, untouched sectors
    left as zeros."""
    def __init__(self, nsec):
        self.n = nsec; self.secs = [None] * nsec; self.cur = 0; self.off = 0; self.buf = bytearray(DATA); self.sub = None

    def space(self):
        return DATA - self.off

    def write(self, b, eox=True, sub=SUB_DATA):
        p = 0
        while p < len(b) and self.cur < self.n:
            if self.off == 0: self.sub = SUB_EOX if (self.cur == self.n - 1 and eox) else sub
            k = min(DATA - self.off, len(b) - p)
            self.buf[self.off:self.off + k] = b[p:p + k]; self.off += k; p += k
            if self.off >= DATA: self.next()

    def next(self):
        self.secs[self.cur] = (self.sub, bytes(self.buf)); self.buf = bytearray(DATA)
        self.off = 0; self.cur += 1

    def close(self):
        if self.off: self.next()
        return self.secs


def _xa_attr(e, filenum_byte):
    a = e.attrs['perm']
    if e.kind == 'dir': return a | 0x8800, 0
    if e.xa: return a | ((e.attrs['xa_attrib'] << 8) if e.attrs['xa_attrib'] != 0xFF else 0x3800), max(1, filenum_byte)
    return a | 0x800, 0


def _dir_sectors(d, lay, root_date, firsts):
    ext = _Extent(d.nsec)
    def one(e, ident):
        if e.kind == 'dir': length = DATA * e.nsec
        elif e.xa: length = DATA * e.nsec
        else: length = e.size
        date = root_date if e is lay.root else _date(e.date, e.attrs['gmt'])
        attr, fn = _xa_attr(e, firsts.get(e.path, 0))
        rec = _record(e, e.lba, length, date, ident, attr, fn, e.attrs)
        if ext.space() < len(rec): ext.next()
        ext.write(rec)
    one(d, b'\0')
    one(d.parent if d.parent else d, b'\1')
    for c in _sorted(d): one(c, c.ident.encode())
    return ext.close()


def _descriptor(lay, pl, root_date):
    ids = lay.ids
    d = bytearray(DATA)
    d[0] = 1; d[1:6] = b'CD001'; d[6] = 1
    d[8:40] = _pad(ids.get('system', 'PLAYSTATION'), 32); d[40:72] = _pad(ids.get('volume'), 32)
    d[80:88] = _pair32(pl.total)
    d[120:124] = _pair16(1); d[124:128] = _pair16(1); d[128:132] = _pair16(DATA)
    d[132:140] = _pair32(pl.pt_len)
    l1 = 18; l2 = l1 + pl.pt_sec; m1 = l2 + 1; m2 = m1 + pl.pt_sec      # mkpsxiso: M1 = L2 + 1 (one-sector tables here)
    d[140:144] = struct.pack('<I', l1); d[144:148] = struct.pack('<I', l2)
    d[148:152] = struct.pack('>I', m1); d[152:156] = struct.pack('>I', m2)
    r = bytearray(34); r[0] = 34; r[2:10] = _pair32(lay.root.lba); r[10:18] = _pair32(lay.root.nsec * DATA)
    r[18:25] = root_date; r[25] = 2; r[28:32] = _pair16(1); r[32] = 1
    d[156:190] = r
    d[190:318] = _pad(ids.get('volume_set'), 128); d[318:446] = _pad(ids.get('publisher'), 128)
    d[446:574] = _pad(ids.get('data_preparer'), 128); d[574:702] = _pad(ids.get('application', 'PLAYSTATION'), 128)
    d[702:739] = _pad(ids.get('copyright'), 37); d[739:776] = _pad(None, 37); d[776:813] = _pad(None, 37)
    d[813:830] = _long_date(ids.get('creation_date')); d[830:847] = _long_date(ids.get('modification_date'))
    d[847:864] = _long_date(None); d[864:881] = _long_date(None)
    d[881] = 1; d[883 + 141:883 + 149] = b'CD-XA001'
    t = bytearray(DATA); t[0] = 255; t[1:6] = b'CD001'; t[6] = 1
    return bytes(d), bytes(t)


def _path_tables(lay, pl):
    out = []
    for msb in (False, True):
        b = bytearray()
        for name, pi, e in _path_table(lay):
            n = max(1, len(name))
            b += bytes((n, 0)) + struct.pack('>IH' if msb else '<IH', e.lba, pi) + name.encode()
            b += b'\0' * ((n + 1 & ~1) - len(name))
        out.append(bytes(b) + b'\0' * (pl.pt_sec * DATA - len(b)))
    return out


def _subheader(m):
    return bytes((0, 0, m, 0)) * 2


def _file_sectors(e, src, lba):
    """The raw sectors of file e at lba (a generator)."""
    data = src.read()
    if len(data) != e.size: raise ValueError(f'{e.path}: the source gave {len(data)} bytes, {e.size} expected')
    n = e.nsec
    if e.xa:
        for k in range(n):
            xa = data[k * XA:(k + 1) * XA]; xa += b'\0' * (XA - len(xa))
            if xa[2] & 0x20:
                yield form2(lba + k, xa)
            else:
                yield _form1_reuse(src, k, lba + k, xa[0:8], xa[8:8 + DATA])
        return
    for k in range(n):
        chunk = data[k * DATA:(k + 1) * DATA]
        if len(chunk) < DATA: chunk += b'\0' * (DATA - len(chunk))
        yield _form1_reuse(src, k, lba + k, _subheader(SUB_EOX if k == n - 1 else SUB_DATA), chunk)


_BLANK = {}


def _form1_reuse(src, k, lba, sub, chunk):
    """Sector k of a file as Form 1 (8-byte subheader `sub`): the source's raw sector when it holds the same subheader
    and data (its EDC/ECC are then the ones computed here: a MOVE), else computed."""
    r = src.raw(k)
    if r is not None and r[16:24] == sub and r[24:24 + DATA] == chunk and r[15] == 2 and r[:12] == SYNC:
        return r[:12] + msf(lba) + r[15:]
    key = (bytes(sub), chunk[:1]) if chunk.count(chunk[:1]) == DATA else None     # blank sectors: computed once
    if key is not None and key in _BLANK:
        return _BLANK[key][:12] + msf(lba) + _BLANK[key][15:]
    s = form1(lba, sub, chunk)
    if key is not None: _BLANK[key] = s
    return s


def _license_sectors(lic):
    if lic is None:
        for k in range(16): yield form2(k, bytes((0, 0, 0x20, 0)) * 2 + bytes(XA - 8))
        return
    if len(lic) < 12 * XA: lic = lic + bytes(12 * XA - len(lic))
    for k in range(12):
        xa = lic[k * XA:(k + 1) * XA]
        yield form1(k, xa[:8], xa[8:8 + DATA])
    for k in range(12, 16):
        yield form2(k, bytes((0, 0, 0x20, 0)) * 2 + bytes(XA - 8))


class _Keep:
    """A caller's open file in a with statement (left open)."""
    def __init__(self, f): self.f = f
    def __enter__(self): return self.f
    def __exit__(self, *a): return False


def write(layout, files, out_bin, license=None, cue=True, progress=None):
    """Writes the image of `layout` (XML text or Layout) with `files` {disc path: bytes | file name | Source} to
    out_bin (+ .cue), a file name or an open binary file (a browser's stream: no .cue then). license: the 28 032 bytes
    of the license sectors (bytes or a file name; None = blank). Returns (Plan, SHA-1 of the image)."""
    lay = layout if isinstance(layout, Layout) else Layout(layout)
    srcs = {k: as_source(v) for k, v in files.items()}
    stray = sorted(set(srcs) - set(lay.files()))
    if stray: raise KeyError(f'{stray[0]}: not a file of the layout')
    pl = Plan(lay, {k: s.size for k, s in srcs.items()})
    if license is not None and not isinstance(license, (bytes, bytearray)):
        with open(license, 'rb') as f: license = f.read()
    firsts = {}
    for e in lay.entries:
        if e.kind == 'file' and e.xa:
            r = srcs[e.path].read(); firsts[e.path] = r[0] if r else 0
    root_date = _date(lay.root.date, lay.root.attrs['gmt'], root=True) if lay.root.date else None
    if root_date is None: raise ValueError('the layout has no creation_date (the root directory\'s date)')
    sha = hashlib.sha1(); lba = 0
    stream = hasattr(out_bin, 'write')
    tmp = None if stream else out_bin + '.part'
    with (_Keep(out_bin) if stream else open(tmp, 'wb')) as out:
        def put(s):
            nonlocal lba
            out.write(s); sha.update(s); lba += 1
            if progress and lba % 4096 == 0: progress(lba, pl.total)
        for s in _license_sectors(license): put(s)
        pvd, term = _descriptor(lay, pl, root_date)
        put(form1(16, _subheader(SUB_EOR), pvd)); put(form1(17, _subheader(SUB_EOX), term))
        for t in _path_tables(lay, pl)[:1] * 2 + _path_tables(lay, pl)[1:] * 2:
            for k in range(pl.pt_sec):
                put(form1(lba, _subheader(SUB_EOX if k == pl.pt_sec - 1 else SUB_DATA), t[k * DATA:(k + 1) * DATA]))
        for e in lay.entries:
            if e.lba != lba: raise AssertionError(f'{e.path or e.kind}: at {lba}, planned {e.lba}')
            if e.kind == 'dir':
                for sec in _dir_sectors(e, lay, root_date, firsts):
                    put(bytes(RAW) if sec is None else form1(lba, _subheader(sec[0]), sec[1]))
            elif e.kind == 'file':
                for s in _file_sectors(e, srcs[e.path], lba): put(s)
            else:
                for k in range(e.nsec):
                    if e.submode & 0x20: put(form2(lba, bytes((0, 0, e.submode, 0)) * 2 + bytes(XA - 8)))
                    else: put(_form1_reuse(Source(0, None), 0, lba, _subheader(e.submode), bytes(DATA)))
    if lba != pl.total: raise AssertionError(f'wrote {lba} sectors, planned {pl.total}')
    if stream: return pl, sha.hexdigest()
    os.replace(tmp, out_bin)
    if cue:
        with open(out_bin[:-4] + '.cue', 'w', newline='\n') as f:            # as mkpsxiso writes it
            f.write(f'FILE "{os.path.basename(out_bin)}" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n')
    return pl, sha.hexdigest()


# ---------------------------------------------------------------- Digimon World's own sector table
def filename_hash(name):
    """The engine's FNV-1a filename key (collisions are rejected at build time)."""
    value = 0x811C9DC5
    for byte in name.encode('ascii'):
        value = ((value ^ byte) * 0x01000193) & 0xFFFFFFFF
    return value


PACKED_TABLE_MARKER = b'DWFH\x02\0\0\0'


def file_size_code(size):
    """Lossless 21-bit size: literal below 1 MiB, otherwise 64-byte units."""
    if not 0 <= size < 1 << 26 or (size >= 1 << 20 and size % 64):
        raise ValueError(f'{size}: size cannot be represented in the packed file table')
    return size if size < 1 << 20 else 0x100000 | (size >> 6)


def file_table_entries(exe, t, base=0x80090000, names=None):
    """FILE_OFFSET_TABLE's entries in the executable image `exe` (table at file offset t): [(offset, sector, size, name)],
    through the NULL entry. Legacy layouts: {i32 sector, i32 size, char *name} (12 bytes, the original's) and, since patch
    0210, {i32 sector, i32 size, char name[12]} (20 bytes, no NUL at 12 letters).
    DWFH version 1 uses a marker then {i32 sector, i32 size, u32 FNV-1a key};
    Version 2 packs a 19-bit sector, lossless 21-bit size code and 24-bit key
    into eight bytes. names resolves keys against the planned disc."""
    packed = exe[t:t + 8] == PACKED_TABLE_MARKER
    if packed or tuple(struct.unpack_from('<III', exe, t)) == (0x48465744, 0x00010001, 0):
        keys = {}
        for name in names or ():
            key = filename_hash(name) & (0xFFFFFF if packed else 0xFFFFFFFF)
            if key in keys and keys[key] != name:
                raise ValueError(f'filename hash collision: {keys[key]} / {name}')
            keys[key] = name
        out = []
        stride = 8 if packed else 12
        at = t + stride
        while at + stride <= len(exe):
            if packed:
                word = int.from_bytes(exe[at:at + 8], 'little')
                sec, code, key = word & 0x7FFFF, (word >> 19) & 0x1FFFFF, word >> 40
                size = (code & 0xFFFFF) << 6 if code & 0x100000 else code
            else:
                sec, size, key = struct.unpack_from('<iiI', exe, at)
            if key == 0:
                return out
            out.append((at, sec, size, keys.get(key, f'@{key:08X}')))
            at += stride
        raise ValueError('unterminated hashed file table')
    ptr, = struct.unpack_from('<I', exe, t + 8)
    inline = not (0x80090000 <= ptr < 0x80200000)
    out = []
    while True:
        at = t + len(out) * (20 if inline else 12)
        sec, size = struct.unpack_from('<ii', exe, at)
        if inline:
            raw = bytes(exe[at + 8:at + 20]).split(b'\0')[0]
        else:
            ptr, = struct.unpack_from('<I', exe, at + 8)
            if not (0x80090000 <= ptr < 0x80200000): break
            raw = bytes(exe[ptr - base:exe.index(b'\0', ptr - base)])
        if not re.fullmatch(rb'[A-Z0-9_.]{1,16}', raw): break   # end of the table
        out.append((at, sec, size, raw.decode('ascii')))
        if inline and raw == b'NULL': break
    return out


def rewrite_file_table(exe, t, where):
    """Writes {name: (lba, size)} into the FILE_OFFSET_TABLE of `exe` (a bytearray; table at file offset t): the game
    reads its files by these sectors (the movies by name). Returns (entries, changed, names without a file, names)."""
    packed = exe[t:t + 8] == PACKED_TABLE_MARKER
    entries = file_table_entries(exe, t, names=where); changed = 0; missing = []
    for at, sec, size, name in entries:
        if name in where:
            lba, real = where[name]
            if (sec, size) != (lba, real): changed += 1
            if packed:
                if not 0 <= lba < 1 << 19:
                    raise ValueError(f'{name}: sector exceeds packed file table limits')
                # Preserve the three-byte filename key at the end of the row.
                exe[at:at + 5] = (lba | (file_size_code(real) << 19)).to_bytes(5, 'little')
            else:
                struct.pack_into('<ii', exe, at, lba, real)
        elif name != 'NULL':
            missing.append(name)
    return len(entries), changed, missing, {e[3] for e in entries}


# ---------------------------------------------------------------- reading an image back
class Image:
    """A raw MODE2/2352 image: its files {disc path: (lba, size on the disc, mixed)} from the ISO 9660 records."""
    def __init__(self, path):
        self.path = path; self.f = open(path, 'rb'); self.sectors = os.path.getsize(path) // RAW
        pvd = self.data(16)
        if pvd[1:6] != b'CD001': raise ValueError(f'{path}: no ISO 9660 volume descriptor')
        self.pvd = pvd; self.files = {}; self.dirs = {}; self.records = {}
        ext, ln = struct.unpack_from('<I', pvd, 158)[0], struct.unpack_from('<I', pvd, 166)[0]
        self._walk(ext, ln, '')

    def raw(self, lba, n=1):
        self.f.seek(lba * RAW); return self.f.read(RAW * n)

    def data(self, lba):
        return self.raw(lba)[24:24 + DATA]

    def _walk(self, ext, ln, pre):
        self.dirs[pre] = (ext, ln)
        for k in range(blocks(ln)):
            d = self.data(ext + k); p = 0
            while p < DATA and d[p]:
                rec = d[p:p + d[p]]; p += d[p]
                name = rec[33:33 + rec[32]]
                if name in (b'\0', b'\1'): continue
                e, n = struct.unpack_from('<I', rec, 2)[0], struct.unpack_from('<I', rec, 10)[0]
                full = pre + name.decode('ascii').split(';')[0]
                self.records[full] = rec
                if rec[25] & 2: self._walk(e, n, full + '/')
                else: self.files[full] = (e, n, self._xa(rec) & 0x3800 not in (0, 0x800))     # mixed: xa_attrib << 8

    @staticmethod
    def _xa(rec):
        x = 33 + rec[32]; x += x & 1
        return struct.unpack_from('>H', rec, x + 4)[0] if rec[x + 6:x + 8] == b'XA' else 0

    def read(self, path):
        """The bytes of a file: 2048 per sector, or for a mixed file 2336 (subheader + data + EDC) per sector."""
        lba, n, xa = self.files[path]
        if xa:
            k = n // DATA; raw = self.raw(lba, k)
            return b''.join(raw[i * RAW + 16:(i + 1) * RAW] for i in range(k))
        raw = self.raw(lba, blocks(n))
        return b''.join(raw[i * RAW + 24:i * RAW + 24 + DATA] for i in range(blocks(n)))[:n]

    def source(self, path, data=None):
        """A Source for the file at `path`, whose raw sectors are reused when they match (MOVE)."""
        lba, n, xa = self.files[path]
        size = (n // DATA) * XA if xa else n
        return Source(size, (lambda: data) if data is not None else (lambda: self.read(path)),
                      lambda k: self.raw(lba + k))

    def license(self):
        raw = self.raw(0, 12)
        return b''.join(raw[i * RAW + 16:(i + 1) * RAW] for i in range(12))


def _date_str(d):
    return f'{1900 + d[0]:04d}{d[1]:02d}{d[2]:02d}{d[3]:02d}{d[4]:02d}{d[5]:02d}', (d[6] - 256 if d[6] > 127 else d[6])


def layout_from_image(img):
    """The layout (mkpsxiso XML text, its tree under @DISC@) that gives back `img` (an Image) with the writer: the
    order of every extent, dates, identifiers, file types. Raises ValueError for what the writer cannot express."""
    pvd = img.pvd
    def s(a, b): return pvd[a:b].decode('latin-1').rstrip(' ')
    cd = pvd[813:830]
    ids = dict(system=s(8, 40), application=s(574, 702), volume=s(40, 72), volume_set=s(190, 318),
               publisher=s(318, 446), data_preparer=s(446, 574), copyright=s(702, 739),
               creation_date=cd[:16].decode() + f'{(cd[16] - 256 if cd[16] > 127 else cd[16]):+d}')
    if pvd[830:847] != b'0' * 16 + b'\0': raise ValueError('a modification date is not supported')
    # extents in LBA order: directories (their records) and files; children of a directory in their LBA order
    ext = [(lba, 'dir', p) for p, (lba, n) in img.dirs.items()] + [(v[0], 'file', p) for p, v in img.files.items()]
    ext.sort()
    xa_attrib = None; perms = set()
    for p, rec in img.records.items():
        x = Image._xa(rec); perms.add(x & 0x7FF)
        if p in img.files and img.files[p][2]: xa_attrib = (x >> 8) & 0xFF if xa_attrib is None else xa_attrib
    if len(perms) > 1: raise ValueError(f'records with different XA permissions: {perms}')
    perm = perms.pop() if perms else PERM_DEFAULT
    xa_attrib = 32 if xa_attrib is None else xa_attrib
    lines = ['<iso_project image_name="mkpsxiso.bin" cue_sheet="mkpsxiso.cue">',
             '    <track type="data" cdvd_style="false" xa_edc="false">',
             '        <identifiers ' + ' '.join(f'{k}="{v}"' for k, v in ids.items() if v) + '/>',
             f'        <license file="{DISC_TOKEN}/license_data.dat"/>',
             f'        <default_attributes gmt_offs="{GMT_DEFAULT}" xa_attrib="{xa_attrib}" xa_perm="{perm}" xa_gid="0" xa_uid="0"/>',
             f'        <directory_tree source="{DISC_TOKEN}">']
    open_dirs = ['']; ind = lambda: ' ' * (8 + 4 * len(open_dirs))
    end = None
    for lba, kind, p in ext:
        if p == '': end = lba + blocks(img.dirs[''][1]); continue
        if end is not None and lba != end: raise ValueError(f'{p}: a gap of {lba - end} sectors before it')
        parent = p.rsplit('/', 1)[0] + '/' if '/' in p else ''
        if kind == 'dir': parent = p[:-1].rsplit('/', 1)[0] + '/' if '/' in p[:-1] else ''
        while open_dirs[-1] != parent:
            open_dirs.pop(); lines.append(ind() + '</dir>')
        rec = img.records[p.rstrip('/')]
        date, gmt = _date_str(rec[18:25]); g = '' if gmt == GMT_DEFAULT else f' gmt_offs="{gmt}"'
        name = p.rstrip('/').split('/')[-1]
        if kind == 'dir':
            lines.append(ind() + f'<dir name="{name}" date="{date}"{g}>'); open_dirs.append(p)
            end = lba + blocks(img.dirs[p][1])
        else:
            l, n, xa = img.files[p]
            lines.append(ind() + f'<file name="{name}" type="{"mixed" if xa else "data"}" date="{date}"{g}/>')
            end = lba + blocks(n)
    while len(open_dirs) > 1:
        open_dirs.pop(); lines.append(ind() + '</dir>')
    if end < img.sectors: lines.append(ind() + f'<dummy sectors="{img.sectors - end}" type="0"/>')
    lines += ['        </directory_tree>', '    </track>', '</iso_project>', '']
    return '\n'.join(lines)


def files_from_image(img, lay):
    """{disc path: Source} of every file of `lay` in the image (raw sectors reused)."""
    return {p: img.source(p) for p in lay.files()}


def files_from_dir(lay, root):
    """{disc path: file name} of every file of the layout under root."""
    return {p: os.path.join(root, *p.split('/')) for p in lay.files()}


def main(argv):
    if len(argv) != 3:
        print(__doc__); return 2
    xml_path, root, out = argv
    text = open(xml_path).read()
    lay = Layout(text)
    src_dir = root
    lic = lay.license.replace(DISC_TOKEN, src_dir) if lay.license else None
    if lic and not os.path.isabs(lic) and DISC_TOKEN not in (lay.license or ''):
        lic = os.path.join(os.path.dirname(os.path.abspath(xml_path)), lay.license)
    pl, sha = write(lay, files_from_dir(lay, src_dir), out, license=lic)
    print(f'{out}: {pl.total} sectors, SHA-1 {sha}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
