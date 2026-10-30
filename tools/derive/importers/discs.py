"""Read the source games' ISO path tables and DCB's DRV, without external extractors.

Supports raw 2352-byte and cooked 2048-byte source images. The existing release
file pins verify the files actually used, including the DCB archive.
"""
import hashlib
from pathlib import Path, PurePosixPath
import struct



class Image:
    def __init__(self, path):
        self.file = open(path, 'rb')
        for self.stride, self.offset in ((2352, 24), (2048, 0)):
            if self.data(16)[1:6] == b'CD001':
                break
        else:
            self.file.close()
            raise ValueError(f'{path}: no ISO 9660 primary volume descriptor')

    def data(self, sector):
        self.file.seek(sector * self.stride + self.offset)
        return self.file.read(2048)

    def read(self, sector, size):
        data = b''.join(self.data(sector + i) for i in range((size + 2047) // 2048))[:size]
        if len(data) != size:
            raise ValueError('source disc: truncated file')
        return data

    def index(self):
        pvd = self.data(16)
        length = struct.unpack_from('<I', pvd, 132)[0]
        start = struct.unpack_from('<I', pvd, 140)[0]
        table = self.read(start, length)
        dirs, pos = [], 0
        while pos < len(table):
            n = table[pos]
            if not n or pos + 8 + n > len(table):
                raise ValueError('source disc: invalid path table')
            sector, parent = struct.unpack_from('<IH', table, pos + 2)
            name = table[pos + 8:pos + 8 + n].decode('ascii')
            path = '' if name == '\0' else str(PurePosixPath(dirs[parent - 1][0]) / name)
            dirs.append((path, sector))
            pos += 8 + n + (n & 1)
        files = {}
        for folder, sector in dirs:
            size = struct.unpack_from('<I', self.data(sector), 10)[0]
            data, pos = self.read(sector, size), 0
            while pos < len(data):
                n = data[pos]
                if not n:
                    pos = (pos // 2048 + 1) * 2048
                    continue
                rec = data[pos:pos + n]
                pos += n
                if len(rec) < 34:
                    raise ValueError('source disc: invalid directory entry')
                name = rec[33:33 + rec[32]]
                if name in (b'\0', b'\1') or rec[25] & 2:
                    continue
                name = name.decode('ascii').split(';')[0]
                path = str(PurePosixPath(folder) / name)
                if '..' in PurePosixPath(path).parts or path.startswith('/'):
                    raise ValueError('source disc: unsafe path')
                files[path] = struct.unpack_from('<I', rec, 2)[0], struct.unpack_from('<I', rec, 10)[0]
        return files


RELEASES = {
    'dcb': {'SLUS_013.28': 'dcb', 'SLES_039.00': 'dcb-eu', 'SLPS_031.01': 'dcb-jp'},
    'dw2': {'SLUS_011.93': 'dw2', 'SLPS_028.44': 'dw2-jp'},
    'dw2003': {'SLES_039.36': 'dw2003', 'SLPS_034.46': 'dw3-jp'},
}


def drv_files(data, sector=0, folder='', seen=None):
    seen = set() if seen is None else seen
    if sector in seen:
        raise ValueError('DCB DRV: recursive directory')
    seen.add(sector)
    pos = sector * 2048
    while pos + 32 <= len(data):
        kind = data[pos]
        start, size = struct.unpack_from('<II', data, pos + 4)
        if kind == 0 and start == 0:
            return
        typ = data[pos + 1:pos + 4].decode('ascii').rstrip('\0 ')
        name = data[pos + 16:pos + 32].split(b'\0')[0].decode('cp932')
        if '/' in name or '\\' in name or name in ('.', '..'):
            raise ValueError('DCB DRV: unsafe path')
        if kind == 0x80:
            yield from drv_files(data, start, folder + name + '/', seen)
        elif kind == 1:
            if start * 2048 + size > len(data):
                raise ValueError('DCB DRV: truncated file')
            yield folder + name + '.' + typ, data[start * 2048:start * 2048 + size]
        else:
            raise ValueError('DCB DRV: invalid entry')
        pos += 32


def extract(game, path):
    """Yield (path under source-games/, bytes) for this player's source disc."""
    from tools import discs as catalog
    image = Image(path)
    try:
        files = image.index()
        def read(name):
            if name not in files:
                raise ValueError(f'{game}: missing disc file {name}')
            return image.read(*files[name])
        cnf = read('SYSTEM.CNF')
        boot = cnf.decode('latin-1').split('cdrom:')[1].lstrip('\\').split(';')[0].strip().upper()
        release = RELEASES.get(game, {}).get(boot)
        supported = {d['id'] for d in catalog.SOURCE_DISCS + catalog.SOURCE_VARIANTS
                     if d.get('supported', True)}
        if release not in supported:
            raise ValueError(f'{game}: unsupported source disc {boot}')
        pins = catalog.release_files()[release]
        yield f'{game}/disc/SYSTEM.CNF', cnf
        for name, sha in pins.items():
            data = read(name)
            if hashlib.sha1(data).hexdigest() != sha:
                raise ValueError(f'{game}: {name}: source disc checksum mismatch')
            if game == 'dcb' and name == 'F.DRV':
                for rel, data in drv_files(data):
                    if rel.endswith('.PAK') and rel.split('.')[0].isdigit():
                        yield f'dcb/drv/F/{rel}', data
            else:
                yield f'{game}/disc/{name}', data
    finally:
        image.file.close()


def extract_to(game, image, out):
    out = Path(out)
    count = 0
    for name, data in extract(game, image):
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        count += 1
    return count
