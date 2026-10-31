#!/usr/bin/env python3
"""PS1 memory card images (.mcd, 128 KB) and Digimon World saves in them.

Usage:
  memory_card.py ls CARD                        files: name, blocks, size, first block
  memory_card.py get CARD NAME OUT              a file's bytes (its block chain)
  memory_card.py save CARD [NAME]               the Digimon World saves: both v1 copies (checksum,
                                        version word, partner, screens, items, bits) and,
                                        in a two-block (v2) or three-block (v3) file, both extensions
  memory_card.py patch CARD NAME OFFSET HEX     overwrite bytes of a file in place (tests: corrupt a
                                        copy, fake a newer version...)
  memory_card.py fill CARD N [-o OUT]           add N one-block dummy files (tests: a nearly full card)
  memory_card.py strip CARD NAME -o OUT         a copy holding only that save, with the game's own bytes of its header (the
                                        title and the icon: 0x04-0x43, 0x60-0x1FF) zeroed: a card fit to commit
                                        (tools/dev/saves/corpus/, docs/reference/save-format.md "Every release's save")
  --tags HEADER (any command)           the tag registry from that save_tags.h instead of the patch series

The save layout is docs/reference/ids.md "Save format v2": a 0x200 header, two 0xF00 v1
payloads (0x200, 0x1100) and, in a v2 file, two 0x1000 extensions (0x2000, 0x3000). The expanded-story engine
(docs/mods/story-state-engine.md) writes v3 files of three blocks: two 0x2000 extensions (0x2000, 0x4000) with the story
flags (triggers 800 and up) and variables; `save` prints the flags that are set and the variables that are not 0.
"""

from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))
import argparse, glob, os, re, struct, sys

BLOCK = 0x2000
FRAME = 0x80


class Card:
    def __init__(self, path):
        self.path = path
        with open(path, 'rb') as f:
            self.d = bytearray(f.read())
        assert len(self.d) == 0x20000 and self.d[:2] == b'MC', f'{path}: not a 128 KB memory card image'

    def entry(self, i):
        f = self.d[FRAME * i:FRAME * (i + 1)]
        state, size, nxt = struct.unpack_from('<IIH', f, 0)
        return state, size, nxt, f[10:31].split(b'\0')[0].decode('ascii', 'replace')

    def files(self):
        out = []
        for i in range(1, 16):
            state, size, nxt, name = self.entry(i)
            if state != 0x51: continue
            chain = [i]
            while nxt != 0xFFFF and len(chain) < 15:
                chain.append(nxt + 1); nxt = self.entry(nxt + 1)[2]
            out.append(dict(name=name, size=size, blocks=chain))
        return out

    def find(self, name):
        for f in self.files():
            if f['name'] == name: return f
        sys.exit(f'{self.path}: no file {name} (ls lists them)')

    def read(self, name):
        f = self.find(name)
        return bytes(b''.join(self.d[b * BLOCK:(b + 1) * BLOCK] for b in f['blocks']))[:f['size']]

    def write(self, name, offset, data):
        f = self.find(name)
        for i, byte in enumerate(data):
            o = offset + i
            b = f['blocks'][o // BLOCK]
            self.d[b * BLOCK + o % BLOCK] = byte
        open(self.path, 'wb').write(self.d)


    def strip(self, name):
        """Only file `name` stays (the other directory entries freed, their blocks zeroed); the save's header loses the
        game's own bytes (the title and the icon), which no checksum covers and no load reads."""
        keep = self.find(name)['blocks']
        for i in range(1, 16):
            if i in keep: continue
            f = bytearray(FRAME)
            struct.pack_into('<IIH', f, 0, 0xA0, 0, 0xFFFF)
            x = 0
            for b in f[:127]: x ^= b
            f[127] = x
            self.d[FRAME * i:FRAME * (i + 1)] = f
            self.d[i * BLOCK:(i + 1) * BLOCK] = bytes(BLOCK)
        h = keep[0] * BLOCK
        self.d[h + 0x04:h + 0x44] = bytes(0x40)
        self.d[h + 0x60:h + 0x200] = bytes(0x1A0)

    def add_dummy(self, name):
        for i in range(1, 16):
            if self.entry(i)[0] & 0xF0 == 0xA0:
                f = bytearray(FRAME)
                struct.pack_into('<IIH', f, 0, 0x51, BLOCK, 0xFFFF)
                f[10:10 + len(name)] = name.encode()
                x = 0
                for b in f[:127]: x ^= b
                f[127] = x
                self.d[FRAME * i:FRAME * (i + 1)] = f
                return i
        sys.exit('the card is full')


# the records of a v4/v5 extension (include/dw/save_tags.h, docs/reference/save-format.md): u16 tag, u16 length, data; tag 0 ends.
# The registry is the header as the tracked patch series leaves it (mods/patches/*.patch, every "-/+#define SAVE_TAG_" line in
# order), so it is the source's and not whatever build/decomp-* happens to hold; MCD_TAGS=HEADER (or `--tags HEADER`) reads a
# save_tags.h instead.
ROOT = _DEV_ROOT
TAGS = {1: 'screens', 2: 'inventory', 3: 'partnerType', 4: 'wregs', 5: 'registered', 6: 'poopMaps', 7: 'speciesRaised',
        8: 'speciesRecruited', 9: 'options', 10: 'vanillaSwap', 0x8001: 'storyFlags', 0x8002: 'storyVars'}
_DEFINE = re.compile(r'#define (SAVE_TAG_\w+)\s+(0x[0-9A-Fa-f]+)')


def _camel(n):
    w = n.lower().split('_')
    return w[0] + ''.join(x.title() for x in w[1:])


def _registry(defines):
    return {int(v, 0): _camel(k[len('SAVE_TAG_'):]) for k, v in defines.items() if k not in ('SAVE_TAG_END', 'SAVE_TAG_REQUIRED')}


def tags_from_header(path):
    """{tag: name} of a save_tags.h."""
    return _registry(dict(_DEFINE.findall(open(path).read())))


def tags_from_patches(root=ROOT):
    """{tag: name} of include/dw/save_tags.h after the patch series (mods/patches) in order."""
    d = {}
    for series in ('mods/patches',):
        for f in sorted(glob.glob(os.path.join(root, series, '*.patch'))):
            for line in open(f, errors='replace'):
                m = _DEFINE.match(line[1:]) if line[:1] in '+-' else None
                if not m: continue
                if line[0] == '-': d.pop(m.group(1), None)
                else: d[m.group(1)] = m.group(2)
    return _registry(d)


def load_tags(header=None):
    """Sets TAGS from `header` (a save_tags.h), $MCD_TAGS, or the patch series; returns it."""
    global TAGS
    header = header or os.environ.get('MCD_TAGS')
    t = tags_from_header(header) if header else tags_from_patches()
    if not t: raise ValueError('empty save tag registry')
    TAGS = t
    return TAGS


load_tags()


def parse_records(e):
    """[(tag, data)] of a tagged extension (None if it is not well formed)."""
    out, at = [], 12
    while at + 4 <= len(e) - 4:
        tag, n = struct.unpack_from('<HH', e, at)
        if tag == 0: return out if n == 0 else None
        if at + 4 + n > len(e) - 4 or any(t == tag for t, _ in out): return None
        out.append((tag, bytes(e[at + 4:at + 4 + n]))); at += 4 + n
    return None


def build_extension(head, records, size):
    """The bytes of a tagged extension: its 12-byte head, the records, the end record, zeros, the byte sum."""
    body = bytearray(head[:12]) + b''.join(struct.pack('<HH', t, len(d)) + d for t, d in records) + struct.pack('<HH', 0, 0)
    assert len(body) <= size - 4, 'the records do not fit the extension'
    body += bytes(size - 4 - len(body))
    return bytes(body) + struct.pack('<I', sum(body) & 0xFFFFFFFF)


def decode_records(recs):
    out = {}
    for tag, d in recs:
        name = TAGS.get(tag, f'unknown{tag:#06x}')
        if name in ('screens', 'inventory', 'registered', 'poopMaps'): out[name] = list(struct.unpack(f'<{len(d) // 2}h', d[:len(d) // 2 * 2]))
        elif name == 'wregs': out[name] = list(struct.unpack(f'<{len(d) // 2}H', d[:len(d) // 2 * 2]))
        elif name == 'partnerType': out[name] = struct.unpack('<i', d[:4])[0]
        elif name in ('speciesRaised', 'speciesRecruited', 'groundPickupBits'): out[name] = [i * 8 + b for i, x in enumerate(d) for b in range(8) if x >> b & 1]
        elif name == 'storyFlags': out['story_flags_set'] = [800 + i * 8 + b for i, x in enumerate(d) for b in range(8) if x >> b & 1]
        elif name == 'storyVars':
            vs = struct.unpack(f'<{len(d) // 4}i', d[:len(d) // 4 * 4]); out['story_vars'] = {i: v for i, v in enumerate(vs) if v}
        else: out[name] = d.hex()
    return out


def v1_checksum(p):
    return (sum(p[:0x4E4]) + sum(p[0x500:0xF00])) & 0xFFFFFFFF


def decode_save(data):
    out = {'bytes': len(data), 'blocks': data[3]}
    count = data[0x51] & 0x1F  # high bits: CHEATS, original enemy style, brief enemy bars
    if data[0x50] == ord('O') and 0 < count <= 12:
        options = data[0x54:0x54 + count]
        if count == 12:
            options += bytes([int(bool(data[0x51] & 0x80)),
                              int(bool(data[0x51] & 0x40)) | (int(bool(data[0x51] & 0x20)) << 1)])
        out['header_options'] = dict(number=struct.unpack_from('<H', data, 0x52)[0], bytes=options.hex())
    for k, base in enumerate((0x200, 0x1100)):
        p = data[base:base + 0xF00]
        stored = struct.unpack_from('<I', p, 0x4FC)[0]
        w = p[0x4E4:0x4E9]
        ver = w[4] if w[:4] == b'DW2\0' else 1
        calc = v1_checksum(p)
        c = dict(checksum_ok=stored == calc, refuses_original=stored == calc ^ 0xFFFFFFFF, checksum=stored, version=ver,
                 partnerType=struct.unpack_from('<i', p, 0x1B8)[0], money=struct.unpack_from('<i', p, 0x1B4)[0],
                 screen=p[0x49A], previousScreen=p[0x49B], items=list(p[0x40C:0x40C + 30]),
                 player=p[0x467:0x467 + 20].split(b'\0')[0].decode('ascii', 'replace'))
        out[f'copy{k}'] = c
    if len(data) >= 0x4000:
        # v2: two 0x1000 extensions (0x2000, 0x3000); v3 (expanded-story engine, three blocks): two 0x2000 ones (0x2000, 0x4000)
        size = 0x2000 if len(data) >= 0x6000 else 0x1000
        for k in range(2):
            e = data[0x2000 + k * size:0x2000 + (k + 1) * size]
            if e[:4] == b'DW4E':
                stored = struct.unpack_from('<I', e, size - 4)[0]; recs = parse_records(e)
                out[f'ext{k}'] = dict(magic='DW4E', version=struct.unpack_from('<H', e, 4)[0], size=struct.unpack_from('<H', e, 6)[0],
                                      checksum_ok=stored == sum(e[:size - 4]) & 0xFFFFFFFF,
                                      matches_v1=struct.unpack_from('<I', e, 8)[0] == out[f'copy{k}']['checksum'],
                                      records=None if recs is None else decode_records(recs))
                continue
            stored = struct.unpack_from('<i', e, size - 4)[0]
            mine = sum(e[:size - 4]) & 0xFFFFFFFF
            v1c = struct.unpack_from('<I', e, 8)[0]
            out[f'ext{k}'] = dict(
                magic=e[:4].decode('ascii', 'replace'), version=struct.unpack_from('<H', e, 4)[0],
                size=struct.unpack_from('<H', e, 6)[0],
                checksum_ok=(stored & 0xFFFFFFFF) == mine, matches_v1=v1c == out[f'copy{k}']['checksum'],
                screen=struct.unpack_from('<h', e, 12)[0], previousScreen=struct.unpack_from('<h', e, 14)[0],
                items=list(struct.unpack_from('<30h', e, 16)), partnerType=struct.unpack_from('<i', e, 76)[0],
                wregs=list(struct.unpack_from('<16H', e, 80)))
            if size == 0x2000:
                # the story state after the species bits (0x188 + 2 * 128 = 0x288): 2048 bytes of flags, 1024 i32 variables
                flags = e[0x288:0x288 + 2048]
                vs = struct.unpack_from('<1024i', e, 0x288 + 2048)
                out[f'ext{k}']['story_flags_set'] = [800 + i * 8 + b for i, x in enumerate(flags) for b in range(8) if x >> b & 1]
                out[f'ext{k}']['story_vars'] = {i: v for i, v in enumerate(vs) if v}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--tags', help='the tag registry from this save_tags.h (default: the patch series)')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('ls'); p.add_argument('card')
    p = sub.add_parser('get'); p.add_argument('card'); p.add_argument('name'); p.add_argument('out')
    p = sub.add_parser('save'); p.add_argument('card'); p.add_argument('name', nargs='?')
    p = sub.add_parser('tags'); p.add_argument('card'); p.add_argument('name')
    p = sub.add_parser('addtag'); p.add_argument('card'); p.add_argument('name'); p.add_argument('tag', type=lambda s: int(s, 0)); p.add_argument('hex')
    p = sub.add_parser('cuttag'); p.add_argument('card'); p.add_argument('name'); p.add_argument('tag', type=lambda s: int(s, 0)); p.add_argument('length', type=int)
    p = sub.add_parser('settag'); p.add_argument('card'); p.add_argument('name'); p.add_argument('tag', type=lambda s: int(s, 0)); p.add_argument('hex')
    p = sub.add_parser('deltag'); p.add_argument('card'); p.add_argument('name'); p.add_argument('tag', type=lambda s: int(s, 0))
    p = sub.add_parser('fill'); p.add_argument('card'); p.add_argument('n', type=int); p.add_argument('-o')
    p = sub.add_parser('strip'); p.add_argument('card'); p.add_argument('name'); p.add_argument('-o', required=True)
    p = sub.add_parser('patch'); p.add_argument('card'); p.add_argument('name')
    p.add_argument('offset', type=lambda s: int(s, 0)); p.add_argument('hex')
    a = ap.parse_args()
    if a.tags: load_tags(a.tags)
    c = Card(a.card)
    if a.cmd == 'ls':
        used = 0
        for f in c.files():
            used += len(f['blocks'])
            print(f'{f["name"]:21s} {len(f["blocks"])} block(s) {f["size"]:6d} bytes  blocks {f["blocks"]}')
        print(f'{used} of 15 blocks used')
    elif a.cmd == 'get':
        open(a.out, 'wb').write(c.read(a.name))
    elif a.cmd == 'save':
        names = [a.name] if a.name else [f['name'] for f in c.files() if 'DMR' in f['name'] or 'DMW' in f['name']]
        for n in names:
            print(n)
            for k, v in decode_save(c.read(n)).items():
                print(f'  {k}: {v}')
    elif a.cmd in ('tags', 'addtag', 'settag', 'cuttag', 'deltag'):
        data = c.read(a.name); size = 0x2000 if len(data) >= 0x6000 else 0x1000
        for k in range(2):
            e = data[0x2000 + k * size:0x2000 + (k + 1) * size]
            if e[:4] != b'DW4E': sys.exit(f'{a.name}: ext{k} is not a tagged (v4) extension')
            recs = parse_records(e)
            if a.cmd == 'tags': print(f'ext{k}:', [(f'{t:#06x}', TAGS.get(t, '?'), len(d)) for t, d in recs]); continue
            if a.cmd == 'addtag': recs = recs + [(a.tag, bytes.fromhex(a.hex))]       # tests: a tag no build knows
            elif a.cmd == 'settag': recs = [(t, bytes.fromhex(a.hex) if t == a.tag else d) for t, d in recs]   # tests: give a record content
            elif a.cmd == 'cuttag': recs = [(t, d[:a.length] if t == a.tag else d) for t, d in recs]   # tests: a shorter record
            else: recs = [(t, d) for t, d in recs if t != a.tag]
            c.write(a.name, 0x2000 + k * size, build_extension(e, recs, size))
        if a.cmd != 'tags': print(f'{a.card}: {a.name} {a.cmd} {a.tag:#06x}')
    elif a.cmd == 'fill':
        for k in range(a.n):
            c.add_dummy(f'BADUMMY-0000{k:02d}')
        open(a.o or a.card, 'wb').write(c.d)
        print(f'{a.o or a.card}: {sum(len(f["blocks"]) for f in c.files())} of 15 blocks used')
    elif a.cmd == 'strip':
        c.strip(a.name); open(a.o, 'wb').write(c.d)
        print(f'{a.o}: only {a.name}, its title and icon zeroed')
    elif a.cmd == 'patch':
        c.write(a.name, a.offset, bytes.fromhex(a.hex))
        print(f'{a.card}: {a.name} +{a.offset:#x} = {a.hex}')


if __name__ == '__main__':
    main()
