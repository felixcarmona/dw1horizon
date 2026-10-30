#!/usr/bin/env python3
"""Reads, writes and converts Digimon World maps: `.MAP` (screen data)
and `.TFS` (prerendered background). Full specification: docs/mods/maps.md.

No dependencies (standard library only: PNG with zlib).

Usage (every edit command validates, prints the size against the original file and
explains what to do when the sector count changes; recipes: docs/mods/maps.md):
  dwmap.py describe NAME.MAP [--screen N] [--maphead F] [--tfs F] [--no-reverse]
                                                   everything in a map, readable, with world/tile/pixel
                                                   coordinates, MAP_ENTRIES row, MAPHEAD spawns, script sections
  dwmap.py coords NAME.MAP --world X Z | --tile TX TZ | --pixel U V | --screen-px SX SY [--live]
                                                   world <-> tile <-> background pixel <-> screen pixel
  dwmap.py edit IN.MAP OUT.MAP [ops…] [--maphead OUT.SCN] [--overlay OUT.png]
                                                   ops in order: --set-exit K X Z ROT MAP EXIT, --spawn K X Z [ROT],
                                                   --target K MAP EXIT, --clear-exit K, --paint TX0 TZ0 TX1 TZ1 V,
                                                   --paint-world X0 Z0 X1 Z1 V, --replace-value OLD NEW,
                                                   --camera EX EY EZ TX TY TZ, --projection F, --light I VX VY VZ R G B,
                                                   --regions A0..3 B0..3, --add-digimon TYPE X Z [LIKE],
                                                   --remove-digimon S, --move-digimon S X Z, --set-digimon S K=V…,
                                                   --path S STEP…, --instance I hide|show|X,Y, --sprite I K=V…, --tim K PNG
                                                   (V = free|wall|exit:K|toilet|step:N|press:N|number; `edit -h`)
  dwmap.py bg NAME.MAP NAME.TFS OUT.TFS [--paste PNG X Y] [--text X Y TEXT] [--fill X0 Y0 X1 Y1 RGB]
             [--fill-tiles TX0 TZ0 TX1 TZ1 RGB] [--scale N --color RGB --box RGB --at-world] [--overlay OUT.png]
                                                   background region edits keeping the palette
  dwmap.py overlay NAME.MAP OUT.png [--tfs F] [--clut 0|1|2] [--no-collision] [--no-grid]
                                                   see a (edited) map without the emulator; the grid labels the world
                                                   coordinates every 500 (what npc(..., at=(x, z)) is written in)
  dwmap.py tim-import NAME.MAP K sprite.png OUT.MAP  replace the pixels of sprite TIM K
  dwmap.py entry SLUS ID [FIELD=VALUE…] [-o OUT] [--map LINKER.map]
                                                   show/change a MAP_ENTRIES row (name n8 n4 flags sound daynight
                                                   digimon doors toilet label)
  dwmap.py doors SLUS [ENTRY] [--set K MODEL X Y Z ROT] [-o OUT]   DOOR_MAPDATA (24 × 6 doors)
  dwmap.py toilet SLUS [ENTRY] [--set X1 Z1 X2 Z2] [-o OUT]        TOILET_DATA (10 entries)
  dwmap.py info NAME.MAP                           short summary of the sections
  dwmap.py roundtrip [DIR]                         byte-exact parse→build of every .MAP/.TFS
                                                   (default extracted/MAP), .MAP→JSON→.MAP, background PNG
                                                   (indexed and RGB)→TFS, TIM PNG→TIM and collision PNG→.MAP
  dwmap.py dump NAME.MAP out.json                  the whole .MAP as JSON (TIMs in base64)
  dwmap.py build in.json out.MAP                   JSON → .MAP
  dwmap.py export NAME.MAP DIR                     background (day/evening/night), overlay with collision,
                                                   exits, Digimon and sprites, editable 100×100 collision,
                                                   sprite TIMs and JSON; looks for the .TFS next to it
  dwmap.py import-png NAME.MAP NAME.TFS background.png out.TFS [--new-palette]
                                                   PNG (indexed or RGB) → TFS, requantizing to the palette
  dwmap.py collision-import NAME.MAP collision.png out.MAP
                                                   edited grid (100×100 indexed PNG: index = value)
  dwmap.py set-tiles NAME.MAP out.MAP TX0 TZ0 TX1 TZ1 VALUE
                                                   fills a rectangle of tiles (inclusive) with VALUE
  dwmap.py map-entry NAME NUM8 NUM4 FLAGS DOORS TOILET LABEL
                                                   prints the 16 bytes of a MAP_ENTRIES row (hex)
  dwmap.py patch-exe SLUS_ORIG SLUS_NEW ID NAME NUM8 NUM4 FLAGS DOORS TOILET LABEL
                                                   copy of the original executable with row ID of
                                                   MAP_ENTRIES written (same size: no LBA moves)
  dwmap.py file-entry SLUS_ORIG SLUS_NEW NAME SECTOR SIZE
                                                   repoints the NAME entry of FILE_OFFSET_TABLE
                                                   (original executable) to another sector/size
  dwmap.py mmm OUT.DAT FILE...                     copy of MMM.DAT (27 MB of zeros at the end of the
                                                   disc) with the files inside, sector-aligned;
                                                   prints the absolute sector and size of each one
"""
import base64, glob, json, math, os, re, struct, sys, zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE_BASE = 0x80090000            # ram = file_offset + 0x80090000
MAP_ENTRIES_RAM = 0x801292D4     # MapEntry[255] ×16 (decomp/config/us/symbols.txt)
FILE_OFFSET_TABLE_RAM = 0x8011FE1C   # FileEntry[819] {i32 sector, i32 size, char *name}
MMM_SECTOR = 0x244BC             # LBA of MMM.DAT (last file on the disc, all zeros)

# ----------------------------------------------------------------------------- PNG

def png_write(path, w, h, rows, palette=None, mode='P'):
    """rows: list of bytes per row. mode 'P' (indexed, palette = [(r,g,b)]), 'RGB' or 'RGBA'."""
    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    ct = {'P': 3, 'RGB': 2, 'RGBA': 6}[mode]
    out = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, ct, 0, 0, 0))
    if mode == 'P':
        out += chunk(b'PLTE', b''.join(bytes(c[:3]) for c in palette))
    out += chunk(b'IDAT', zlib.compress(b''.join(b'\0' + bytes(r) for r in rows), 6)) + chunk(b'IEND', b'')
    open(path, 'wb').write(out)


def png_read(path, alpha=False):
    """Returns (w, h, mode, rows, palette): mode 'P' (rows of indices) or 'RGB' (RGB rows;
    grey and alpha are converted). With alpha=True an RGBA/grey-alpha PNG comes back as
    'RGBA' rows. Only 8 bits per channel and no interlacing."""
    d = open(path, 'rb').read()
    if d[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError(f'{path}: not a PNG')
    p, idat, pal = 8, b'', None
    while p < len(d):
        n, t = struct.unpack_from('>I4s', d, p); body = d[p + 8:p + 8 + n]; p += 12 + n
        if t == b'IHDR':
            w, h, bd, ct, _, _, il = struct.unpack('>IIBBBBB', body)
        elif t == b'PLTE':
            pal = [tuple(body[i:i + 3]) for i in range(0, len(body), 3)]
        elif t == b'IDAT':
            idat += body
    if bd != 8 or il:
        raise ValueError(f'{path}: only 8-bit non-interlaced PNG (bd={bd}, interlace={il})')
    bpp = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ct]
    raw = zlib.decompress(idat); stride = w * bpp; rows = []; prev = bytearray(stride); o = 0
    for _ in range(h):
        f = raw[o]; cur = bytearray(raw[o + 1:o + 1 + stride]); o += 1 + stride
        if f == 1:
            for i in range(bpp, stride): cur[i] = (cur[i] + cur[i - bpp]) & 255
        elif f == 2:
            for i in range(stride): cur[i] = (cur[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride): cur[i] = (cur[i] + ((cur[i - bpp] if i >= bpp else 0) + prev[i]) // 2) & 255
        elif f == 4:
            for i in range(stride):
                a = cur[i - bpp] if i >= bpp else 0; b = prev[i]; c = prev[i - bpp] if i >= bpp else 0
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                cur[i] = (cur[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(cur); prev = cur
    if ct == 3:
        return w, h, 'P', rows, pal
    if ct == 2:
        return w, h, 'RGB', rows, None
    if alpha and ct in (4, 6):
        if ct == 6: return w, h, 'RGBA', rows, None
        return w, h, 'RGBA', [bytearray(b for i in range(0, len(r), 2) for b in (r[i], r[i], r[i], r[i + 1])) for r in rows], None
    conv = []
    for r in rows:
        if ct == 0: conv.append(bytearray(b for v in r for b in (v, v, v)))
        elif ct == 4: conv.append(bytearray(b for i in range(0, len(r), 2) for b in (r[i], r[i], r[i])))
        else: conv.append(bytearray(b for i in range(0, len(r), 4) for b in r[i:i + 3]))
    return w, h, 'RGB', conv, None

# ----------------------------------------------------------------------------- PS1 colours

def bgr555_to_rgb(c):
    return ((c & 31) << 3 | (c & 31) >> 2, ((c >> 5) & 31) << 3 | ((c >> 5) & 31) >> 2,
            ((c >> 10) & 31) << 3 | ((c >> 10) & 31) >> 2)


def rgb_to_bgr555(r, g, b, stp=0):
    return (r >> 3) | (g >> 3) << 5 | (b >> 3) << 10 | stp << 15

# ----------------------------------------------------------------------------- TIM (map sprites)

class TIM:
    def __init__(self, data):
        self.raw = bytes(data)
        magic, self.flag = struct.unpack_from('<II', data)
        if magic != 0x10:
            raise ValueError('not a TIM')
        self.bpp = {0: 4, 1: 8, 2: 16, 3: 24}[self.flag & 3]
        p = 8; self.clut = None
        if self.flag & 8:
            n, cx, cy, cw, ch = struct.unpack_from('<I4H', data, p)
            self.clut = (cx, cy, cw, ch, list(struct.unpack_from(f'<{cw * ch}H', data, p + 12))); p += n
        n, self.x, self.y, self.w, self.h = struct.unpack_from('<I4H', data, p)
        self.pixels = data[p + 12:p + 12 + self.w * self.h * 2]
        self.size = p + n          # real size of the TIM (what follows up to the next section is padding)

    def to_png(self, path):
        if self.bpp not in (4, 8) or not self.clut:
            return False
        cx, cy, cw, ch, cl = self.clut
        width = self.w * (4 if self.bpp == 4 else 2); rows = []
        for y in range(self.h):
            line = self.pixels[y * self.w * 2:(y + 1) * self.w * 2]
            rows.append(bytes(v for b in line for v in (b & 15, b >> 4)) if self.bpp == 4 else line)
        pal = [bgr555_to_rgb(c) for c in cl[:cw]]          # first row of the CLUT
        pal += [(0, 0, 0)] * (256 - len(pal))
        png_write(path, width, self.h, rows, pal); return True

# ----------------------------------------------------------------------------- .MAP

SETUP_FIELDS = ['vpx', 'vpy', 'vpz', 'vrx', 'vry', 'vrz']
LIGHT_FIELDS = ['vx', 'vy', 'vz', 'r', 'g', 'b']
SPRITE_FIELDS = ['texX', 'texY', 'width', 'height', 'x', 'y', 'z', 'clut', 'transparency']
DIGI_FIELDS = ['type', 'followMode', 'posX', 'posY', 'posZ', 'rotX', 'rotY', 'rotZ', 'trackingRange',
               'unk2', 'scriptId', 'hp', 'mp', 'currentHP', 'currentMP', 'off', 'def', 'speed', 'brain',
               'bits', 'chargeMode', 'unk1', 'move0', 'move1', 'move2', 'move3',
               'prio0', 'prio1', 'prio2', 'prio3', 'fleeX', 'fleeY', 'fleeZ']


class MapFile:
    """A .MAP. The section order comes from the offset table at the start (loadMap, map.c:4147-4226):
    setup, 8 bpp TIM, 4 bpp TIM, sprites (only if there are TIMs), entities, collision."""

    def __init__(self, data):
        data = bytes(data)
        n = struct.unpack_from('<I', data)[0] // 4
        offs = list(struct.unpack_from(f'<{n}I', data))
        self.table_size = offs[0]
        bounds = offs + [len(data)]
        sec = [data[bounds[i]:bounds[i + 1]] for i in range(n)]
        self._parse_setup(sec[0])
        mid = sec[1:-2]
        self.tims = [bytes(s) for s in mid[:-1]] if mid else []      # raw bytes (padding included)
        self.has_sprites = bool(mid)
        if mid:
            self._parse_sprites(mid[-1])
        else:
            self.sprites, self.instances, self.sprites_tail = [], [], b''
        self._parse_entities(sec[-2])
        self.collision = bytearray(sec[-1][:10000])
        self.collision_tail = bytes(sec[-1][10000:])

    # -- setup: loadMapSetup (map.c:4270-4337)
    def _parse_setup(self, s):
        v = struct.unpack_from(f'<{len(s) // 4}i', s)
        self.camera = dict(zip(SETUP_FIELDS, v[0:6]))          # in the file: half the value (shifted <<1)
        self.lights = [dict(zip(LIGHT_FIELDS, v[6 + 6 * i:12 + 6 * i])) for i in range(3)]
        self.ambient = list(v[24:27])                          # read but ignored (GsSetAmbient is fixed)
        self.projection = v[27]                                # VIEWPORT_DISTANCE (GsSetProjection)
        self.regionA, self.regionB = list(v[28:32]), list(v[32:36])
        self.width, self.height = v[36], v[37]
        nt = self.width * self.height
        self.tiles = list(v[38:38 + nt])
        self.setup_tail = bytes(s[(38 + nt) * 4:])

    def _build_setup(self):
        c = self.camera
        v = [c[k] for k in SETUP_FIELDS]
        for l in self.lights: v += [l[k] for k in LIGHT_FIELDS]
        v += self.ambient + [self.projection] + self.regionA + self.regionB + [self.width, self.height] + self.tiles
        return struct.pack(f'<{len(v)}i', *v) + self.setup_tail

    # -- sprites: loadMapObjects (overworld.c:302-349)
    def _parse_sprites(self, s):
        p = 0; cnt = struct.unpack_from('<h', s)[0]; p = 2; self.sprites = []
        for _ in range(cnt):
            self.sprites.append(dict(zip(SPRITE_FIELDS, struct.unpack_from('<9h', s, p)))); p += 18
        cnt = struct.unpack_from('<h', s, p)[0]; p += 2; self.instances = []
        for _ in range(cnt):
            v = struct.unpack_from('<19h', s, p); p += 38
            self.instances.append({'frames': list(v[0:8]), 'times': list(v[8:16]), 'x': v[16], 'y': v[17],
                                   'flag': v[18]})
        self.sprites_tail = bytes(s[p:])

    def _build_sprites(self):
        out = struct.pack('<h', len(self.sprites))
        for o in self.sprites: out += struct.pack('<9h', *[o[k] for k in SPRITE_FIELDS])
        out += struct.pack('<h', len(self.instances))
        for i in self.instances: out += struct.pack('<19h', *(i['frames'] + i['times'] + [i['x'], i['y'], i['flag']]))
        return out + self.sprites_tail

    # -- entities: loadMapEntities (tamer.c:350-384) + loadMapDigimon (overworld.c:994-1054)
    def _parse_entities(self, s):
        w = struct.unpack_from('<60h', s)
        self.warps = [{'x': w[i], 'y': w[10 + i], 'z': w[20 + i], 'rotation': w[30 + i], 'targetMap': w[40 + i],
                       'targetExit': w[50 + i]} for i in range(10)]
        self.digimon_count = struct.unpack_from('<h', s, 120)[0]
        p = 122; self.digimon = []
        # The game only reads the list if MAP_ENTRIES.flags & 0x80; here it is read while it fits.
        try:
            for _ in range(self.digimon_count):
                v = struct.unpack_from('<33h', s, p); q = p + 66
                nw = struct.unpack_from('<h', s, q)[0]; q += 2
                ai = list(struct.unpack_from('<8h', s, q)); q += 16
                if not 0 <= nw <= 8: raise ValueError
                wp = [list(struct.unpack_from('<3h', s, q + 6 * j)) for j in range(nw)]; q += 6 * nw
                if q > len(s): raise ValueError
                d = dict(zip(DIGI_FIELDS, v)); d['aiSections'] = ai; d['waypoints'] = wp
                self.digimon.append(d); p = q
        except (ValueError, struct.error):
            self.digimon = []; p = 122
        self.entities_tail = bytes(s[p:])

    def _build_entities(self):
        w = self.warps
        out = struct.pack('<60h', *[x[k] for k in ('x', 'y', 'z', 'rotation', 'targetMap', 'targetExit') for x in w])
        out += struct.pack('<h', self.digimon_count)
        for d in self.digimon:
            out += struct.pack('<33h', *[d[k] for k in DIGI_FIELDS]) + struct.pack('<h', len(d['waypoints']))
            out += struct.pack('<8h', *d['aiSections'])
            for wp in d['waypoints']: out += struct.pack('<3h', *wp)
        return out + self.entities_tail

    def build(self):
        secs = [self._build_setup()] + list(self.tims)
        if self.has_sprites: secs.append(self._build_sprites())
        secs += [self._build_entities(), bytes(self.collision) + self.collision_tail]
        table = 4 * len(secs)
        out = bytearray(); offs = []; pos = table
        for s in secs: offs.append(pos); pos += len(s)
        out += struct.pack(f'<{len(secs)}I', *offs)
        for s in secs: out += s
        return bytes(out)

    # -- utilities
    def n_tiles(self):
        return sum(1 for t in self.tiles if t != -1)

    def to_json(self):
        d = {k: getattr(self, k) for k in ('camera', 'lights', 'ambient', 'projection', 'regionA', 'regionB',
                                           'width', 'height', 'tiles', 'sprites', 'instances', 'warps',
                                           'digimon_count', 'digimon')}
        d['has_sprites'] = self.has_sprites
        d['tims'] = [base64.b64encode(t).decode() for t in self.tims]
        for k in ('setup_tail', 'sprites_tail', 'entities_tail', 'collision_tail'):
            d[k] = getattr(self, k).hex()
        d['collision'] = [self.collision[r * 100:(r + 1) * 100].hex() for r in range(100)]
        return d

    @classmethod
    def from_json(cls, d):
        m = cls.__new__(cls)
        for k in ('camera', 'lights', 'ambient', 'projection', 'regionA', 'regionB', 'width', 'height', 'tiles',
                  'sprites', 'instances', 'warps', 'digimon_count', 'digimon', 'has_sprites'):
            setattr(m, k, d[k])
        m.tims = [base64.b64decode(t) for t in d['tims']]
        for k in ('setup_tail', 'sprites_tail', 'entities_tail', 'collision_tail'):
            setattr(m, k, bytes.fromhex(d[k]))
        m.collision = bytearray(bytes.fromhex(''.join(d['collision'])))
        return m

# ----------------------------------------------------------------------------- .TFS

class TfsFile:
    """Background: u16 width, u16 height (not read by the game), u32 CLUT count, CLUTs of 256×BGR555,
    and per tile a u32 (source VRAM position, not read either) + 128×128 pixels at 8 bpp.
    Read by setupMap (map.c:4352-4426). Uncompressed."""
    TILE = 128 * 128

    def __init__(self, data):
        data = bytes(data)
        self.hdr_w, self.hdr_h, n = struct.unpack_from('<HHI', data)
        self.cluts = [list(struct.unpack_from('<256H', data, 8 + 512 * i)) for i in range(n)]
        p = 8 + 512 * n; self.tiles = []
        while p + 4 + self.TILE <= len(data):
            self.tiles.append([bytes(data[p:p + 4]), bytearray(data[p + 4:p + 4 + self.TILE])]); p += 4 + self.TILE
        self.tail = bytes(data[p:])

    def build(self):
        out = bytearray(struct.pack('<HHI', self.hdr_w, self.hdr_h, len(self.cluts)))
        for c in self.cluts: out += struct.pack('<256H', *c)
        for pre, px in self.tiles: out += pre + px
        return bytes(out + self.tail)

    def layout(self, m=None):
        """List of (column, row) of each tile. With the .MAP this is exact (the −1 tiles are not in the TFS);
        without it the prefix of each tile (x/64, y/128) is used, which matches in every file."""
        if m is not None:
            pos = [(i % m.width, i // m.width) for i, t in enumerate(m.tiles) if t != -1]
            return pos, m.width, m.height
        pos = [(struct.unpack_from('<H', p)[0] // 64, struct.unpack_from('<H', p, 2)[0] // 128) for p, _ in self.tiles]
        return pos, max(c for c, _ in pos) + 1, max(r for _, r in pos) + 1

    def image_indices(self, m=None):
        pos, w, h = self.layout(m)
        W, H = w * 128, h * 128
        img = [bytearray(W) for _ in range(H)]
        for (c, r), (_, px) in zip(pos, self.tiles):
            for y in range(128):
                img[r * 128 + y][c * 128:(c + 1) * 128] = px[y * 128:(y + 1) * 128]
        return W, H, img

    def palette_rgb(self, i=0):
        return [bgr555_to_rgb(c) for c in self.cluts[i]]

# ----------------------------------------------------------------------------- camera

def camera_basis(m):
    """View matrix equivalent to GsSetRefView2 (rz = 0) with the .MAP values ×2.
    Camera axes: x right, y down, z forward (PS1 convention, Y pointing down)."""
    c = m.camera
    vp = [c['vpx'] * 2, c['vpy'] * 2, c['vpz'] * 2]; vr = [c['vrx'] * 2, c['vry'] * 2, c['vrz'] * 2]
    z = [vr[i] - vp[i] for i in range(3)]; n = math.sqrt(sum(a * a for a in z)); z = [a / n for a in z]
    up = (0.0, 1.0, 0.0)
    x = [up[1] * z[2] - up[2] * z[1], up[2] * z[0] - up[0] * z[2], up[0] * z[1] - up[1] * z[0]]
    n = math.sqrt(sum(a * a for a in x)); x = [a / n for a in x]
    y = [z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2], z[0] * x[1] - z[1] * x[0]]
    return vp, x, y, z


def project(m, basis, P):
    """World point → pixel of the full background (W×H). The look-at point falls at the centre of the
    background (setupMap: cameraX = W/2 − 160 with the player in the centre; initializeDrawingOffsets)."""
    vp, x, y, z = basis
    d = [P[i] - vp[i] for i in range(3)]
    cx = sum(d[i] * x[i] for i in range(3)); cy = sum(d[i] * y[i] for i in range(3)); cz = sum(d[i] * z[i] for i in range(3))
    if cz <= 1: return None
    return (m.width * 64 + m.projection * cx / cz, m.height * 64 + m.projection * cy / cz)

# ----------------------------------------------------------------------------- simple drawing (overlay)

TILE_COLORS = {}


def tile_color(v):
    if v == 0: return None
    if v & 0x80: return (255, 40, 40)                 # wall (bit 7: checkMapCollisionX/Z)
    if 110 <= v <= 119: return (40, 120, 255)         # exit v−110
    if v == 120: return (180, 90, 30)                 # toilet
    if 51 <= v <= 79: return (255, 220, 0)            # script on stepping
    if 80 <= v <= 109: return (0, 230, 120)           # script on pressing ✕
    return (255, 0, 255)                              # others (no known use)


def fill_poly(img, W, H, pts, col, alpha):
    ys = [p[1] for p in pts]; y0 = max(0, int(math.floor(min(ys)))); y1 = min(H - 1, int(math.ceil(max(ys))))
    n = len(pts)
    for yy in range(y0, y1 + 1):
        yc = yy + 0.5; xs = []
        for i in range(n):
            (ax, ay), (bx, by) = pts[i], pts[(i + 1) % n]
            if (ay <= yc < by) or (by <= yc < ay):
                xs.append(ax + (yc - ay) * (bx - ax) / (by - ay))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            xa = max(0, int(math.ceil(xs[k] - 0.5))); xb = min(W - 1, int(math.floor(xs[k + 1] - 0.5)))
            row = img[yy]
            for xx in range(xa, xb + 1):
                o = xx * 3
                for c in range(3): row[o + c] = int(row[o + c] * (1 - alpha) + col[c] * alpha)


def draw_box(img, W, H, x, y, r, col):
    for yy in range(int(y) - r, int(y) + r + 1):
        for xx in range(int(x) - r, int(x) + r + 1):
            if 0 <= xx < W and 0 <= yy < H:
                img[yy][xx * 3:xx * 3 + 3] = bytes(col)


# 5×7 font for labels and signs painted on backgrounds (lowercase is drawn as uppercase)
FONT = {}
for _ch, _g in {
    'A': '01110 10001 10001 11111 10001 10001 10001', 'B': '11110 10001 10001 11110 10001 10001 11110',
    'C': '01110 10001 10000 10000 10000 10001 01110', 'D': '11110 10001 10001 10001 10001 10001 11110',
    'E': '11111 10000 10000 11110 10000 10000 11111', 'F': '11111 10000 10000 11110 10000 10000 10000',
    'G': '01110 10001 10000 10111 10001 10001 01111', 'H': '10001 10001 10001 11111 10001 10001 10001',
    'I': '01110 00100 00100 00100 00100 00100 01110', 'J': '00111 00010 00010 00010 00010 10010 01100',
    'K': '10001 10010 10100 11000 10100 10010 10001', 'L': '10000 10000 10000 10000 10000 10000 11111',
    'M': '10001 11011 10101 10101 10001 10001 10001', 'N': '10001 10001 11001 10101 10011 10001 10001',
    'O': '01110 10001 10001 10001 10001 10001 01110', 'P': '11110 10001 10001 11110 10000 10000 10000',
    'Q': '01110 10001 10001 10001 10101 10010 01101', 'R': '11110 10001 10001 11110 10100 10010 10001',
    'S': '01111 10000 10000 01110 00001 00001 11110', 'T': '11111 00100 00100 00100 00100 00100 00100',
    'U': '10001 10001 10001 10001 10001 10001 01110', 'V': '10001 10001 10001 10001 10001 01010 00100',
    'W': '10001 10001 10001 10101 10101 10101 01010', 'X': '10001 10001 01010 00100 01010 10001 10001',
    'Y': '10001 10001 01010 00100 00100 00100 00100', 'Z': '11111 00001 00010 00100 01000 10000 11111',
    '0': '01110 10001 10011 10101 11001 10001 01110', '1': '00100 01100 00100 00100 00100 00100 01110',
    '2': '01110 10001 00001 00010 00100 01000 11111', '3': '11111 00010 00100 00010 00001 10001 01110',
    '4': '00010 00110 01010 10010 11111 00010 00010', '5': '11111 10000 11110 00001 00001 10001 01110',
    '6': '00110 01000 10000 11110 10001 10001 01110', '7': '11111 00001 00010 00100 01000 01000 01000',
    '8': '01110 10001 10001 01110 10001 10001 01110', '9': '01110 10001 10001 01111 00001 00010 01100',
    ' ': '00000 00000 00000 00000 00000 00000 00000', '.': '00000 00000 00000 00000 00000 01100 01100',
    ',': '00000 00000 00000 00000 01100 00100 01000', '!': '00100 00100 00100 00100 00100 00000 00100',
    '?': '01110 10001 00001 00010 00100 00000 00100', '-': '00000 00000 00000 11111 00000 00000 00000',
    ':': '00000 01100 01100 00000 01100 01100 00000', '>': '01000 00100 00010 00001 00010 00100 01000',
    '<': '00010 00100 01000 10000 01000 00100 00010', '/': '00001 00010 00010 00100 01000 01000 10000',
    "'": '00100 00100 01000 00000 00000 00000 00000', '#': '01010 01010 11111 01010 11111 01010 01010',
    '=': '00000 00000 11111 00000 11111 00000 00000', '+': '00000 00100 00100 11111 00100 00100 00000',
    '(': '00010 00100 01000 01000 01000 00100 00010', ')': '01000 00100 00010 00010 00010 00100 01000'}.items():
    FONT[_ch] = _g.replace(' ', '')


def text_size(s, scale=2):
    """Pixel size (w, h) of draw_text(s, scale)."""
    return max(0, len(s) * 6 * scale - scale), 7 * scale


def draw_text(img, W, H, x, y, s, col, scale=2):
    """Draws s on RGB rows (img[y] = bytearray of W*3) with the 5×7 font, glyph cell 6×7 × scale."""
    for ch in s.upper():
        g = FONT.get(ch, FONT['?'])
        for i, b in enumerate(g):
            if b == '1':
                for dy in range(scale):
                    yy = int(y) + (i // 5) * scale + dy
                    if not 0 <= yy < H: continue
                    for dx in range(scale):
                        xx = int(x) + (i % 5) * scale + dx
                        if 0 <= xx < W: img[yy][xx * 3:xx * 3 + 3] = bytes(col)
        x += 6 * scale


def collision_palette():
    pal = []
    for v in range(256):
        c = tile_color(v)
        pal.append((0, 0, 0) if c is None else c if not (v & 0x80) or v == 0x80 else (150, 20, 20))
    return pal

# ----------------------------------------------------------------------------- export / import

def find_tfs(map_path):
    p = map_path[:-4] + '.TFS'
    return p if os.path.exists(p) else None


def draw_line(img, W, H, a, b, col):
    n = int(max(abs(b[0] - a[0]), abs(b[1] - a[1]))) + 1
    for k in range(n + 1):
        x = int(a[0] + (b[0] - a[0]) * k / n); y = int(a[1] + (b[1] - a[1]) * k / n)
        if 0 <= x < W and 0 <= y < H: img[y][x * 3:x * 3 + 3] = bytes(col)


def walk_box(m):
    """The box of the screen's walkable tiles (no wall bit), in world units at the tile centres: (x0, x1, z0, z1), or None.
    Not every point of the box is walkable: the overlay shows which tiles are."""
    pts = [tile_to_world(i % 100, i // 100) for i, v in enumerate(m.collision) if not v & 0x80]
    if not pts: return None
    return min(x for x, _ in pts), max(x for x, _ in pts), min(z for _, z in pts), max(z for _, z in pts)


GRID = 500                  # the overlay's grid: a line every 500 world units, labelled (what at=(x, z) is written in)


def draw_grid(img, W, H, m, basis, step=GRID):
    """Lines x = k*step and z = k*step on the ground over the walkable box (one step of margin), each labelled with its value
    at one end: `X 500`, `Z -500`."""
    box = walk_box(m)
    if box is None: return
    x0, x1 = (box[0] // step - 1) * step, (box[1] // step + 2) * step
    z0, z1 = (box[2] // step - 1) * step, (box[3] // step + 2) * step
    col = (255, 255, 255)
    def line(a, b, label):
        pts = [project(m, basis, (a[0] + (b[0] - a[0]) * k / 40, 0, a[1] + (b[1] - a[1]) * k / 40)) for k in range(41)]
        for p, q in zip(pts, pts[1:]):
            if p and q: draw_line(img, W, H, p, q, col)
        end = next((p for p in pts if p and 0 <= p[0] < W - 40 and 8 <= p[1] < H - 8), None)
        if end:
            draw_text(img, W, H, end[0] + 3, end[1] + 3, label, (0, 0, 0), 1)          # (a shadow: readable on any background)
            draw_text(img, W, H, end[0] + 2, end[1] + 2, label, (255, 255, 0), 1)
    for x in range(x0, x1 + 1, step): line((x, z0), (x, z1), f'X {x}')
    for z in range(z0, z1 + 1, step): line((x0, z), (x1, z), f'Z {z}')


def render_overlay(m, t, clut=0, collision=True, grid=False):
    """Background (palette `clut`) + projected collision (red wall, blue exit, yellow script on
    stepping, green script with X, brown toilet) + spawn points `S<i>><map>.<exit>` (white),
    placed Digimon `D<slot>` with their path (orange) and sprite instances (cyan boxes; hidden
    ones dashed). Returns (W, H, RGB rows)."""
    W, H, idx = t.image_indices(m)
    pal = t.palette_rgb(min(clut, len(t.cluts) - 1))
    img = [bytearray(b for v in row for b in pal[v]) for row in idx]
    basis = camera_basis(m)
    if collision:
        for tz in range(100):
            for tx in range(100):
                col = tile_color(m.collision[tz * 100 + tx])
                if not col: continue
                x0, x1 = (tx - 50) * 100, (tx - 49) * 100; z0, z1 = (49 - tz) * 100, (50 - tz) * 100
                pts = [project(m, basis, (x, 0, z)) for x, z in ((x0, z0), (x1, z0), (x1, z1), (x0, z1))]
                if None in pts: continue
                fill_poly(img, W, H, pts, col, 0.45)
    if grid: draw_grid(img, W, H, m, basis)
    for inst_i, inst in enumerate(m.instances):
        fr = [f for f in inst['frames'] if f >= 0]
        if not fr or fr[0] >= len(m.sprites) or inst['flag'] & 0x80: continue
        sp = m.sprites[fr[0]]; x, y = inst['x'], inst['y']; hidden = inst['flag'] == 1 or all(f == -1 for f in inst['frames'])
        for xx in range(x, x + sp['width']):
            for yy in (y, y + sp['height'] - 1):
                if 0 <= xx < W and 0 <= yy < H and not (hidden and (xx // 4) % 2): img[yy][xx * 3:xx * 3 + 3] = b'\x00\xff\xff'
        for yy in range(y, y + sp['height']):
            for xx in (x, x + sp['width'] - 1):
                if 0 <= xx < W and 0 <= yy < H and not (hidden and (yy // 4) % 2): img[yy][xx * 3:xx * 3 + 3] = b'\x00\xff\xff'
        draw_text(img, W, H, x + 3, y + 3, f'I{inst_i}', (0, 255, 255), 1)
    for i, w in enumerate(m.warps):
        if not warp_used(w): continue
        p = project(m, basis, (w['x'], 0, w['z']))
        if p:
            # facing: heading 0 = +Z, 0x400 = +X
            a = w['rotation'] * 2 * math.pi / 4096
            q = project(m, basis, (w['x'] + 150 * math.sin(a), 0, w['z'] + 150 * math.cos(a)))
            if q: draw_line(img, W, H, p, q, (255, 255, 255))
            draw_box(img, W, H, p[0], p[1], 4, (255, 255, 255))
            lab = f'S{i}' + (f'>{w["targetMap"]}.{w["targetExit"]}' if w['targetMap'] >= 0 else '')
            draw_text(img, W, H, p[0] + 7, p[1] - 6, lab, (255, 255, 255))
    used = {}
    for i, d in enumerate(m.digimon):
        p = project(m, basis, (d['posX'], d['posY'], d['posZ']))
        prev = p
        for k, wp in enumerate(d['waypoints']):
            if k < 8 and d['aiSections'][k] in (1, 2):
                q = project(m, basis, (wp[0], wp[1], wp[2]))
                if q and prev: draw_line(img, W, H, prev, q, (255, 180, 60)); draw_box(img, W, H, q[0], q[1], 2, (255, 180, 60))
                prev = q or prev
        if p:
            k = (int(p[0]) // 8, int(p[1]) // 8); n = used.get(k, 0); used[k] = n + 1
            draw_box(img, W, H, p[0], p[1], 4, (255, 128, 0)); draw_text(img, W, H, p[0] + 7, p[1] - 6 + 16 * n, f'D{i}', (255, 128, 0))
    return W, H, img


def warp_used(w):
    return not (w['x'] == w['y'] == w['z'] == w['rotation'] == 0 and w['targetMap'] in (0, -1) and w['targetExit'] in (0, -1))


def export(map_path, outdir):
    os.makedirs(outdir, exist_ok=True)
    name = os.path.basename(map_path)[:-4]
    m = MapFile(open(map_path, 'rb').read())
    tp = find_tfs(map_path); t = TfsFile(open(tp, 'rb').read()) if tp else None
    files = []
    if t:
        W, H, idx = t.image_indices(m)
        for i, lab in enumerate(['day', 'evening', 'night', 'extra3', 'extra4'][:len(t.cluts)]):
            f = os.path.join(outdir, f'{name}-background-{lab}.png'); png_write(f, W, H, idx, t.palette_rgb(i)); files.append(f)
        W, H, img = render_overlay(m, t)
        f = os.path.join(outdir, f'{name}-overlay.png'); png_write(f, W, H, img, mode='RGB'); files.append(f)
    # editable collision (index = tile value; row = tz, column = tx) and ×4 view
    rows = [m.collision[r * 100:(r + 1) * 100] for r in range(100)]
    f = os.path.join(outdir, f'{name}-collision.png'); png_write(f, 100, 100, rows, collision_palette()); files.append(f)
    big = [bytes(v for v in r for _ in range(4)) for r in rows for _ in range(4)]
    f = os.path.join(outdir, f'{name}-collision-x4.png'); png_write(f, 400, 400, big, collision_palette()); files.append(f)
    for i, raw in enumerate(m.tims):
        tim = TIM(raw); f = os.path.join(outdir, f'{name}-tim{i}-{tim.bpp}bpp-vram{tim.x}x{tim.y}.png')
        if tim.to_png(f): files.append(f)
    d = m.to_json(); del d['tims']; d['collision_rows'] = d.pop('collision')
    f = os.path.join(outdir, f'{name}.json'); json.dump(d, open(f, 'w'), indent=1); files.append(f)
    return files


def median_cut(hist, n=256):
    """hist: {(r,g,b): count}. Returns n colours (list of (r,g,b))."""
    boxes = [list(hist.items())]
    while len(boxes) < n:
        best, bi, ch = -1, -1, 0
        for i, b in enumerate(boxes):
            if len(b) < 2: continue
            for c in range(3):
                vals = [k[c] for k, _ in b]; r = max(vals) - min(vals)
                if r > best: best, bi, ch = r, i, c
        if bi < 0: break
        b = sorted(boxes.pop(bi), key=lambda kv: kv[0][ch])
        tot = sum(v for _, v in b); acc = 0; cut = 1
        for j, (_, v) in enumerate(b):
            acc += v
            if acc >= tot / 2: cut = max(1, min(len(b) - 1, j + 1)); break
        boxes += [b[:cut], b[cut:]]
    out = []
    for b in boxes:
        tot = sum(v for _, v in b) or 1
        out.append(tuple(int(round(sum(k[c] * v for k, v in b) / tot)) for c in range(3)))
    return out + [(0, 0, 0)] * (n - len(out))


def import_png(map_path, tfs_path, png_path, out_path, new_palette=False):
    m = MapFile(open(map_path, 'rb').read()); t = TfsFile(open(tfs_path, 'rb').read())
    W, H, orig = t.image_indices(m)
    w, h, mode, rows, pal = png_read(png_path)
    if (w, h) != (W, H):
        raise SystemExit(f'the PNG is {w}×{h} and the background {W}×{H}')
    if new_palette:
        # new 256-colour palette for the day; evening and night are derived from the mean per-channel
        # ratio of the original CLUTs (or 1/0.7/0.7 and 0.5 like the updateTimeOfDay lights)
        if mode == 'P': rows = [bytearray(b for v in r for b in pal[v]) for r in rows]
        hist = {}
        for r in rows:
            for i in range(0, len(r), 3):
                k = (r[i] & 0xF8, r[i + 1] & 0xF8, r[i + 2] & 0xF8); hist[k] = hist.get(k, 0) + 1
        day = median_cut(hist, 255) ; day = [(0, 0, 0)] + day[:255]   # index 0 = reserved black
        ratios = []; ncl_orig = len(t.cluts)
        for k in (1, 2):
            if k < len(t.cluts):
                num = [0, 0, 0]; den = [0, 0, 0]
                for a, b in zip(t.palette_rgb(0), t.palette_rgb(k)):
                    for c in range(3): num[c] += b[c]; den[c] += a[c]
                ratios.append([num[c] / den[c] if den[c] else 1 for c in range(3)])
            else:
                ratios.append([1, .7, .7] if k == 1 else [.5, .5, .5])
        def enc(c, stp_black=True):
            v = rgb_to_bgr555(*c)
            return v if v else 0x8000 if stp_black else 0     # opaque black (0x0000 is transparent)
        t.cluts = [[enc(c) for c in day]] + [[enc(tuple(min(255, int(c[i] * r[i])) for i in range(3))) for c in day]
                                              for r in ratios]
        if ncl_orig == 1: t.cluts = t.cluts[:1]       # interiors (flags & 0x40): a single palette
        for c in t.cluts: c[0] = 0
        target = [bgr555_to_rgb(c) for c in t.cluts[0]]; mode = 'RGB'; pref = None
    else:
        target = t.palette_rgb(0); pref = orig
    cache = {}
    def nearest(r, g, b):
        k = (r, g, b)
        v = cache.get(k)
        if v is None:
            best = 1 << 30
            for i, (pr, pg, pb) in enumerate(target):
                dd = (pr - r) ** 2 * 3 + (pg - g) ** 2 * 4 + (pb - b) ** 2 * 2
                if dd < best: best, v = dd, i
            cache[k] = v
        return v
    out = []
    same_pal = mode == 'P' and pal is not None and [tuple(c) for c in pal[:256]] == [tuple(c) for c in target[:len(pal)]]
    for y in range(H):
        r = rows[y]
        if same_pal:
            out.append(bytearray(r)); continue
        if mode == 'P': r = bytearray(b for v in r for b in pal[v])
        line = bytearray(W)
        o = pref[y] if pref is not None else None
        for x in range(W):
            rgb = (r[3 * x], r[3 * x + 1], r[3 * x + 2])
            if o is not None and target[o[x]] == rgb:
                line[x] = o[x]                        # unchanged pixel: keep the original index
            else:
                line[x] = nearest(*rgb)
        out.append(line)
    pos, _, _ = t.layout(m)
    for (c, rr), tile in zip(pos, t.tiles):
        px = tile[1]
        for y in range(128):
            px[y * 128:(y + 1) * 128] = out[rr * 128 + y][c * 128:(c + 1) * 128]
    data = t.build(); open(out_path, 'wb').write(data)
    return data


def map_entry_bytes(name, n8, n4, flags, doors, toilet, label):
    nb = name.encode('ascii')
    if len(nb) > 9: raise SystemExit('name of 9 characters at most')
    return nb.ljust(10, b'\0') + struct.pack('<6B', n8 & 255, n4 & 255, flags & 255, doors & 255, toilet & 255, label & 255)

# ----------------------------------------------------------------------------- coordinates

def cdiv(a, b):
    """C integer division (truncates towards zero), as the game's `x / 100`."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def world_to_tile(x, z):
    """getModelTile / getTileTrigger (map_collision.c:32-54, 146-156), exactly: (tx, tz)."""
    tx = cdiv(int(x), 100) + 50; tz = 50 - cdiv(int(z), 100)
    if x < 0: tx -= 1
    if z > 0: tz -= 1
    return tx, tz


def tile_to_world(tx, tz):
    """Centre of a tile in world units (map.c:3767-3768)."""
    return (tx - 50) * 100 + 50, (50 - tz) * 100 - 50


def pixel_to_world(m, u, v, basis=None):
    """Background pixel → point on the ground (y = 0): the ray from the eye through the pixel."""
    vp, x, y, z = basis or camera_basis(m)
    dc = ((u - m.width * 64) / m.projection, (v - m.height * 64) / m.projection, 1.0)
    d = [x[i] * dc[0] + y[i] * dc[1] + z[i] * dc[2] for i in range(3)]
    if abs(d[1]) < 1e-9: return None
    t = -vp[1] / d[1]
    if t <= 0: return None
    return vp[0] + t * d[0], vp[2] + t * d[2]


def heading_name(r):
    """Heading 0-4095 (0 = +Z, 0x400 = +X, 0x800 = −Z, 0xC00 = −X) as text."""
    names = ['+Z', '+X+Z', '+X', '+X-Z', '-Z', '-X-Z', '-X', '-X+Z']
    return f'{r} ({names[round((r % 4096) / 512) % 8]})'


def parse_heading(s):
    s = s.strip().lower()
    named = {'+z': 0, 'z+': 0, '+x': 1024, 'x+': 1024, '-z': 2048, 'z-': 2048, '-x': 3072, 'x-': 3072}
    if s in named: return named[s]
    v = int(s, 0)
    if not 0 <= v < 4096: raise MapEditError(f'heading {v}: 0-4095 or z+ x+ z- x- (0 = +Z, 1024 = +X, 2048 = -Z, 3072 = -X)')
    return v

# ----------------------------------------------------------------------------- game tables (docs/data)

class MapEditError(Exception):
    pass


def _csv(name):
    import csv
    p = os.path.join(ROOT, 'docs/data', name)
    return list(csv.DictReader(open(p))) if os.path.exists(p) else []


_TABLES = {}


def tables():
    """map_files.csv (MAP_ENTRIES rows), map_names.csv (captions), the species of the disc (content/species)."""
    if not _TABLES:
        _TABLES['screens'] = {int(r['id']): r for r in _csv('map_files.csv')}
        _TABLES['names'] = {int(r['id']): r['name'] for r in _csv('map_names.csv')}
        import species
        _TABLES['digimon'] = {t: r for t, r in species.all_rows().items() if t < species.NUM_ORIGINAL}
    return _TABLES


def digimon_name(t):
    r = tables()['digimon'].get(t)
    return r['name'] if r else f'#{t}'


def digimon_type(s):
    """Digimon by id or name (the species of the disc, content/species), case-insensitive."""
    s = str(s).strip().strip('"')
    if re.fullmatch(r'-?\d+|0x[0-9a-fA-F]+', s): v = int(s, 0)
    else:
        by = {r['name'].lower(): i for i, r in tables()['digimon'].items()}
        if s.lower() not in by: raise MapEditError(f'no Digimon "{s}" (names in content/species)')
        v = by[s.lower()]
    if not 1 <= v < 180: raise MapEditError(f'Digimon type {v}: 1-179')
    return v


def screen_name(sid):
    r = tables()['screens'].get(sid)
    return f'{sid} {r["file"]} ({r["map_name"]})' if r else str(sid)


def screens_of_file(map_path):
    base = os.path.basename(map_path)[:-4].upper()
    return [i for i, r in tables()['screens'].items() if r['file'].upper() == base]


def original_file(map_path):
    """The file of the same name in extracted/MAP (what FILE_OFFSET_TABLE sizes refer to)."""
    base = os.path.basename(map_path)
    hits = glob.glob(os.path.join(ROOT, 'extracted/MAP/*', base))
    return hits[0] if hits else None


def size_report(path, data, orig=None):
    """Explains whether a rebuilt file still fits the original executable's FILE_OFFSET_TABLE.
    Returns True if it does."""
    orig = orig or original_file(path)
    if not orig: print(f'{path}: {len(data)} bytes (no original of that name in extracted/)'); return True
    o = os.path.getsize(orig); so, sn = -(-o // 2048), -(-len(data) // 2048)
    if sn <= so:
        print(f'{path}: {len(data)} bytes (original {o}), {sn} of {so} sectors: fits. With the original '
              f'executable build-disc.py keeps every LBA (it pads to the original size).')
        return True
    print(f'WARNING {path}: {len(data)} bytes needs {sn} sectors, the original {os.path.basename(orig)} has {so} '
          f'({o} bytes, {so * 2048 - o} bytes of slack). The original executable reads ⌈size/2048⌉ sectors from its '
          f'own FILE_OFFSET_TABLE, so this file would be cut and every later file on the disc would move. '
          f'Options: (a) the patched decompilation executable + `build-disc.py NAME --from DIR --relayout` (rewrites the table); '
          f'(b) original executable: put the file in MMM.DAT (`dwmap.py mmm`) and repoint its entry '
          f'(`dwmap.py file-entry`); (c) make it smaller (fewer waypoints/Digimon/sprites).', file=sys.stderr)
    return False

# ----------------------------------------------------------------------------- collision values

def parse_value(s):
    """Collision value: free | wall | exit:K | toilet | step:N (51-79) | press:N (80-109) | number."""
    s = str(s).strip().lower()
    m_ = re.fullmatch(r'(exit|step|press):?(\d+)', s)
    if s in ('free', 'floor', '0'): return 0
    if s in ('wall', 'block'): return 0x80
    if s == 'toilet': return 120
    if m_:
        k, n = m_.group(1), int(m_.group(2))
        if k == 'exit':
            if not 0 <= n <= 9: raise MapEditError('exit:K with K 0-9')
            return 110 + n
        lo, hi = (51, 79) if k == 'step' else (80, 109)
        if not lo <= n <= hi: raise MapEditError(f'{k}:N with N {lo}-{hi} (the tile value is the script section)')
        return n
    v = int(s, 0)
    if not 0 <= v <= 255: raise MapEditError(f'collision value {v}: 0-255')
    return v


def value_name(v):
    if v == 0: return 'free'
    if v & 0x80: return 'wall' if v == 0x80 else f'wall(0x{v:X})'
    if 110 <= v <= 119: return f'exit:{v - 110}'
    if v == 120: return 'toilet'
    if 51 <= v <= 79: return f'step:{v}'
    if 80 <= v <= 109: return f'press:{v}'
    return f'unused({v})'


def rects_of(grid, v):
    """Greedy decomposition of the tiles == v into inclusive rectangles (tx0, tz0, tx1, tz1)."""
    left = {(i % 100, i // 100) for i, b in enumerate(grid) if b == v}; out = []
    while left:
        tx, tz = min(left, key=lambda p: (p[1], p[0]))
        x1 = tx
        while (x1 + 1, tz) in left: x1 += 1
        z1 = tz
        while all((x, z1 + 1) in left for x in range(tx, x1 + 1)): z1 += 1
        for z in range(tz, z1 + 1):
            for x in range(tx, x1 + 1): left.discard((x, z))
        out.append((tx, tz, x1, z1))
    return out

# ----------------------------------------------------------------------------- scripts (read-only use of bytecode)

def _as_maphead(path, maphead, tmpdir):
    """tools/dws/bytecode/__main__.py treats a file as MAPHEAD when its name contains "maphead": copy it under that name if needed."""
    if not maphead or 'maphead' in os.path.basename(path).lower(): return path
    import shutil
    dst = os.path.join(tmpdir, 'MAPHEAD.SCN'); shutil.copyfile(path, dst); return dst


def scn_dis(path, maphead=False):
    """Disassembly of a .SCN with tools/dws/bytecode/__main__.py (its dis, in this process), cached in build/dwmap-scn/<name>-<mtime>-<size>/."""
    from dws import bytecode as bytecode
    st = os.stat(path)
    out = os.path.join(ROOT, 'build/dwmap-scn', f'{os.path.basename(path)}-{int(st.st_mtime)}-{st.st_size}')
    if not os.path.exists(os.path.join(out, '.done')):
        os.makedirs(out, exist_ok=True)
        r = bytecode.dis(_as_maphead(path, maphead, out), out)
        if r.returncode: raise MapEditError('bytecode dis: ' + (r.stderr or r.stdout))
        open(os.path.join(out, '.done'), 'w').close()
    return out


def section_body(text, sec):
    """(start, end, label) of section `sec` in a bytecode listing; the body runs to the next section label."""
    labels = dict((int(a), b) for a, b in re.findall(r'^\.section\s+(\d+)\s+(\w+)', text, re.M))
    if sec not in labels: return None
    lab = labels[sec]; seclabs = set(labels.values())
    m_ = re.search(rf'^{re.escape(lab)}:.*$', text, re.M)
    if not m_: return None
    end = len(text)
    for n in re.finditer(r'^(\w+):', text[m_.end():], re.M):
        if n.group(1) in seclabs: end = m_.end() + n.start(); break
    return m_.start(), end, lab


def maphead_info(screen, maphead=None):
    """What MAPHEAD section `screen` does: script id, LOAD/SET_DIGIMON lines (slot, type, autotalk, conditional?)."""
    d = scn_dis(maphead or os.path.join(ROOT, 'extracted/SCN/MAPHEAD.SCN'), maphead=True)
    text = open(os.path.join(d, 'maphead.scn.txt'), encoding='utf-8').read()
    b = section_body(text, screen)
    if not b: return None
    body = text[b[0]:b[1]]
    scr = re.search(r'SET_SCRIPT\s+(\d+),\s*(\d+)', body)
    sets = [(int(s), int(t), int(a)) for t, s, a in re.findall(r'^\s*SET_DIGIMON\s+(\d+),\s*(\d+),\s*(\d+)', body, re.M)]
    loads = [int(t) for t in re.findall(r'^\s*LOAD_DIGIMON\s+(\d+)', body, re.M)]
    cond = bool(re.search(r'^\s*(IF|JUMP_TO)\b', body, re.M))
    shared = [s for s, l in re.findall(r'^\.section\s+(\d+)\s+(\w+)', text, re.M) if l == b[2] and int(s) != screen]
    return {'script': int(scr.group(1)) if scr else None, 'sets': sets, 'loads': loads, 'conditional': cond,
            'body': body, 'label': b[2], 'shared_with': [int(s) for s in shared]}


def script_sections(script_id):
    """Section ids present in DG.SCN entry `script_id`."""
    d = scn_dis(os.path.join(ROOT, 'extracted/SCN/DG.SCN'))
    p = os.path.join(d, f'script_{script_id:03d}.scn.txt')
    if not os.path.exists(p): return None, ''
    text = open(p, encoding='utf-8').read()
    return sorted({int(a) for a in re.findall(r'^\.section\s+(\d+)', text, re.M)}), text


def model_size(dig):
    """Bytes malloc3 takes for a Digimon's model (whole sectors; model names at 0x80133B44, docs/mods/models.md)."""
    exe = open(os.path.join(ROOT, 'extracted/SLUS_010.32'), 'rb').read()
    o = 0x80133B44 - EXE_BASE + 8 * dig
    name = exe[o:o + 8].split(b'\0')[0].decode('ascii', 'replace')
    path = next(iter(glob.glob(os.path.join(ROOT, f'extracted/CHDAT/MMD*/{name}.MMD'))), None)
    return (os.path.getsize(path) + 0x7FF) & ~0x7FF if path else 0


def maphead_edit(src, dst, screen, ops):
    """Rewrites MAPHEAD section `screen` so the placed-Digimon slots appear (or not):
    ops = [('add', type, slot, autotalk), ('remove', slot), ('retype', slot, old, new)].
    'add' goes right after SET_SCRIPT (which has already run loadMap), so the slot appears
    unconditionally. Assembled with tools/dws/bytecode/__main__.py (its dis and asm, in this process; SCNASM_PACK_ASCII=1 packs the texts
    as the command line did); checked against the 25 000-byte buffer."""
    import tempfile, shutil
    from dws import bytecode as bytecode
    tmp = tempfile.mkdtemp(prefix='dwmap-mh-')
    try:
        r = bytecode.dis(_as_maphead(src, True, tmp), tmp)
        if r.returncode: raise MapEditError('bytecode dis: ' + (r.stderr or r.stdout))
        path = os.path.join(tmp, 'maphead.scn.txt'); text = open(path, encoding='utf-8').read()
        b = section_body(text, screen)
        if not b: raise MapEditError(f'MAPHEAD has no section {screen}')
        body = text[b[0]:b[1]]
        for op in ops:
            if op[0] == 'add':
                _, typ, slot, auto = op
                ins = f'    LOAD_DIGIMON {typ}\n    SET_DIGIMON {typ}, {slot}, {auto}\n'
                body, n = re.subn(r'(^\s*SET_SCRIPT\b.*\n)', lambda q: q.group(1) + ins, body, count=1, flags=re.M)
                if not n: raise MapEditError(f'MAPHEAD section {screen} has no SET_SCRIPT')
            elif op[0] == 'remove':
                slot = op[1]
                types = [int(t) for t in re.findall(rf'^\s*SET_DIGIMON\s+(\d+),\s*{slot},.*$', body, re.M)]
                body = re.sub(rf'^\s*SET_DIGIMON\s+\d+,\s*{slot},.*\n', '', body, flags=re.M)
                for t in set(types):
                    if not re.search(rf'^\s*SET_DIGIMON\s+{t},', body, re.M):
                        body = re.sub(rf'^\s*LOAD_DIGIMON\s+{t}\b.*\n', '', body, flags=re.M)
            elif op[0] == 'retype':
                _, slot, old, new = op
                body = re.sub(rf'^(\s*)SET_DIGIMON\s+{old}(,\s*{slot},.*)$',
                              lambda q: f'{q.group(1)}LOAD_DIGIMON {new}\n{q.group(1)}SET_DIGIMON {new}{q.group(2)}', body, flags=re.M)
                if not re.search(rf'^\s*SET_DIGIMON\s+{old},', body, re.M):
                    body = re.sub(rf'^\s*LOAD_DIGIMON\s+{old}\b.*\n', '', body, flags=re.M)
        text = text[:b[0]] + body + text[b[1]:]
        open(path, 'w', encoding='utf-8').write(text)
        r = bytecode.asm(path, dst, pack_ascii=os.environ.get('SCNASM_PACK_ASCII') == '1')
        if r.returncode: raise MapEditError('bytecode asm: ' + (r.stderr or r.stdout))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n = os.path.getsize(dst)
    if n > 25000: raise MapEditError(f'{dst}: {n} bytes; MAPHEAD_SCRIPT_BUFFER holds 25000 (0x61A8)')
    loads = re.findall(r'^\s*LOAD_DIGIMON\s+(\d+)', body, re.M)
    heap = sum(model_size(int(x)) for x in set(loads))
    if heap > 170 * 1024:
        print(f'WARNING: the models section {screen} can load add up to {heap // 1024} KB (all branches); about 170 KB fit '
              'in the NPC heap (docs/mods/models.md); if one branch really loads that much the screen hangs while loading',
              file=sys.stderr)
    print(f'{dst}: {n} bytes (buffer 25000); section {screen}: {len(loads)} LOAD_DIGIMON, '
          f'{len(set(loads))} distinct models')
    if len(set(loads)) > 5:
        print(f'WARNING: section {screen} loads {len(set(loads))} distinct models; NPC_MODELS has 5 slots (loadMMD)', file=sys.stderr)
    if len(loads) > 8:
        print(f'WARNING: {len(loads)} LOAD_DIGIMON in section {screen}; LOADED_DIGIMON_MODELS has 8 entries '
              '(only the ones on the branch actually taken count)', file=sys.stderr)
    size_report(dst, open(dst, 'rb').read(), os.path.join(ROOT, 'extracted/SCN/MAPHEAD.SCN'))

# ----------------------------------------------------------------------------- executable tables (original SLUS_010.32)

EXE_SYMBOLS = {'MAP_ENTRIES': 0x801292D4, 'DOOR_MAPDATA': 0x80122E60, 'TOILET_DATA': 0x80122E10,
               'FILE_OFFSET_TABLE': 0x8011FE1C, 'MAP_NAME_PTR': 0x801291BC}


def exe_offset(sym, linker_map=None):
    """File offset of a table in the executable: the original's address (symbols.txt) or, with the
    linker map of a GCC/mods build, the address there. file offset = RAM − 0x80090000."""
    if linker_map:
        for line in open(linker_map):
            m_ = re.match(r'\s+(0x[0-9a-f]+)\s+' + sym + r'\s*$', line)
            if m_: return int(m_.group(1), 16) - EXE_BASE
        raise MapEditError(f'{sym} is not in {linker_map}')
    return EXE_SYMBOLS[sym] - EXE_BASE


ENTRY_FIELDS = ['name', 'n8', 'n4', 'flags', 'doors', 'toilet', 'label']


def read_entry(exe, i, off):
    o = off + 16 * i; raw = exe[o:o + 16]
    name = raw[:10].split(b'\0')[0].decode('ascii', 'replace')
    n8, n4, fl, dr, to, lb = struct.unpack_from('<bbBbbB', raw, 10)
    return {'name': name, 'n8': n8, 'n4': n4, 'flags': fl, 'doors': dr, 'toilet': to, 'label': lb}


def entry_text(i, e):
    fl = e['flags']
    return (f'MAP_ENTRIES[{i}] "{e["name"]}": TIMs {e["n8"]}×8bpp + {e["n4"]}×4bpp, flags 0x{fl:02X} '
            f'(sound bank {fl & 0x1F}, day/night {"no (1 CLUT)" if fl & 0x40 else "yes (3 CLUTs)"}, '
            f'placed Digimon {"read" if fl & 0x80 else "NOT read"}), doors {e["doors"]}, toilet {e["toilet"]}, '
            f'caption {e["label"]} "{tables()["names"].get(e["label"], "?")}"')


def door_entries(exe, off):
    out = []
    for i in range(24):
        o = off + 54 * i
        mid = list(struct.unpack_from('<6b', exe, o)); v = struct.unpack_from('<24h', exe, o + 6)
        out.append([{'model': mid[k] & 255, 'x': v[k], 'y': v[6 + k], 'z': v[12 + k], 'rotation': v[18 + k]} for k in range(6)])
    return out


def toilet_entries(exe, off):
    return [list(struct.unpack_from('<4h', exe, off + 8 * i)) for i in range(10)]

# ----------------------------------------------------------------------------- background edits (TFS)

class Requant:
    """Nearest colour in a palette (day CLUT), with the same weights as import-png; index 0 is
    skipped when it is 0x0000 (transparent on the PS1)."""
    def __init__(self, pal, raw=None):
        self.pal = pal; self.cache = {}
        self.skip = {0} if raw is not None and raw[0] == 0 else set()

    def __call__(self, r, g, b):
        k = (r, g, b); v = self.cache.get(k)
        if v is None:
            best = 1 << 30
            for i, (pr, pg, pb) in enumerate(self.pal):
                if i in self.skip: continue
                dd = (pr - r) ** 2 * 3 + (pg - g) ** 2 * 4 + (pb - b) ** 2 * 2
                if dd < best: best, v = dd, i
            self.cache[k] = v
        return v


def tfs_put_pixels(m, t, pixels):
    """pixels: iterable of (x, y, index) in full-background coordinates → written into the TFS tiles."""
    pos, _, _ = t.layout(m); where = {p: k for k, p in enumerate(pos)}; n = 0
    for x, y, v in pixels:
        k = where.get((x // 128, y // 128))
        if k is None: continue
        t.tiles[k][1][(y % 128) * 128 + x % 128] = v; n += 1
    return n


def covering_instances(m, x0, y0, x1, y1):
    """Sprite instances whose first frame overlaps the background rectangle (they are drawn on top)."""
    out = []
    for i, inst in enumerate(m.instances):
        fr = [f for f in inst['frames'] if f >= 0]
        if not fr or fr[0] >= len(m.sprites) or inst['flag'] == 1 or inst['flag'] & 0x80: continue
        sp = m.sprites[fr[0]]
        if inst['x'] < x1 and x0 < inst['x'] + sp['width'] and inst['y'] < y1 and y0 < inst['y'] + sp['height']:
            out.append(i)
    return out


def bg_paste(m, t, png_path, X, Y):
    """Pastes a PNG (RGB, RGBA: alpha < 128 is skipped, or indexed with this palette) at background
    pixel (X, Y), requantized to the day palette (evening/night follow by index)."""
    w, h, mode, rows, pal = png_read(png_path, alpha=True)
    W, H = m.width * 128, m.height * 128
    rq = Requant(t.palette_rgb(0), t.cluts[0]); out = []
    same = mode == 'P' and pal and [tuple(c) for c in pal[:256]] == [tuple(c) for c in t.palette_rgb(0)[:len(pal)]]
    for yy in range(h):
        r = rows[yy]
        for xx in range(w):
            x, y = X + xx, Y + yy
            if not (0 <= x < W and 0 <= y < H): continue
            if mode == 'P':
                if same: out.append((x, y, r[xx])); continue
                c = pal[r[xx]]
            elif mode == 'RGBA':
                if r[4 * xx + 3] < 128: continue
                c = r[4 * xx:4 * xx + 3]
            else:
                c = r[3 * xx:3 * xx + 3]
            out.append((x, y, rq(*c)))
    return tfs_put_pixels(m, t, out), (X, Y, X + w, Y + h)


def bg_text(m, t, X, Y, text, scale, color, box=None, pad=None):
    """Writes text (5×7 font × scale) on the background at pixel (X, Y), optionally on a filled box."""
    tw, th = text_size(text, scale); pad = scale * 2 if pad is None else pad
    W, H = m.width * 128, m.height * 128
    rq = Requant(t.palette_rgb(0), t.cluts[0]); px = []
    if box is not None:
        bi = rq(*box)
        for y in range(Y - pad, Y + th + pad):
            for x in range(X - pad, X + tw + pad):
                if 0 <= x < W and 0 <= y < H: px.append((x, y, bi))
    img = [bytearray(tw * 3) for _ in range(th)]
    draw_text(img, tw, th, 0, 0, text, (1, 2, 3), scale)
    ci = rq(*color)
    for yy in range(th):
        for xx in range(tw):
            if img[yy][xx * 3:xx * 3 + 3] == b'\x01\x02\x03': px.append((X + xx, Y + yy, ci))
    return tfs_put_pixels(m, t, px), (X - pad, Y - pad, X + tw + pad, Y + th + pad)


def bg_fill(m, t, X0, Y0, X1, Y1, color):
    rq = Requant(t.palette_rgb(0), t.cluts[0]); v = rq(*color)
    return tfs_put_pixels(m, t, ((x, y, v) for y in range(Y0, Y1) for x in range(X0, X1))), (X0, Y0, X1, Y1)


def bg_fill_tiles(m, t, tx0, tz0, tx1, tz1, color):
    """Paints the projected ground quad of tiles tx0..tx1, tz0..tz1 (inclusive)."""
    W, H = m.width * 128, m.height * 128; basis = camera_basis(m)
    x0, x1 = (min(tx0, tx1) - 50) * 100, (max(tx0, tx1) - 49) * 100
    z0, z1 = (49 - max(tz0, tz1)) * 100, (50 - min(tz0, tz1)) * 100
    pts = [project(m, basis, (x, 0, z)) for x, z in ((x0, z0), (x1, z0), (x1, z1), (x0, z1))]
    if None in pts: raise MapEditError('those tiles are behind the camera')
    img = [bytearray(W * 3) for _ in range(H)]
    fill_poly(img, W, H, pts, (255, 255, 255), 1.0)
    rq = Requant(t.palette_rgb(0), t.cluts[0]); v = rq(*color)
    px = [(x, y, v) for y in range(H) for x in range(W) if img[y][3 * x]]
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return tfs_put_pixels(m, t, px), (int(min(xs)), int(min(ys)), int(max(xs)) + 1, int(max(ys)) + 1)


def parse_color(s):
    s = s.strip().lstrip('#')
    if ',' in s: return tuple(int(c) for c in s.split(','))
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))

# ----------------------------------------------------------------------------- sprite TIMs

def tim_import(m, k, png_path, tfs=None):
    """Replaces the pixels of TIM k (same size, same bpp) from a PNG: indexed with the TIM's palette
    copies indices; otherwise each pixel goes to the nearest colour of the CLUT the TIM is drawn with
    (its own CLUT, or the background day palette for CLUT row 480). Index 0 / colour 0x0000 is
    transparent: RGBA pixels with alpha < 128 are written as 0."""
    raw = bytearray(m.tims[k]); tim = TIM(bytes(raw))
    if tim.bpp not in (4, 8): raise MapEditError(f'TIM {k}: {tim.bpp} bpp is not supported')
    width = tim.w * (4 if tim.bpp == 4 else 2)
    w, h, mode, rows, pal = png_read(png_path, alpha=True)
    if (w, h) != (width, tim.h): raise MapEditError(f'TIM {k} is {width}×{tim.h} pixels, the PNG {w}×{h}')
    cx, cy, cw, ch, cl = tim.clut
    if cy == 480 and tfs is not None: cl_raw = tfs.cluts[0]
    else: cl_raw = cl[:cw]
    target = [bgr555_to_rgb(c) for c in cl_raw]; rq = Requant(target, cl_raw)
    own = [bgr555_to_rgb(c) for c in cl[:cw]]
    idx = []
    same = mode == 'P' and pal and [tuple(c) for c in pal[:len(own)]] == own[:len(pal)]
    for y in range(h):
        r = rows[y]
        if same: idx.append(list(r)); continue
        line = []
        for x in range(w):
            if mode == 'P':
                line.append(rq(*pal[r[x]]))
            elif mode == 'RGBA':
                line.append(0 if r[4 * x + 3] < 128 else rq(*r[4 * x:4 * x + 3]))
            else:
                line.append(rq(*r[3 * x:3 * x + 3]))
        idx.append(line)
    # pixel block: after the image block header (12 bytes) that follows the CLUT block
    p = 8 + (struct.unpack_from('<I', raw, 8)[0] if tim.flag & 8 else 0) + 12
    for y in range(h):
        if tim.bpp == 8: b = bytes(idx[y])
        else: b = bytes((idx[y][i] & 15) | (idx[y][i + 1] & 15) << 4 for i in range(0, w, 2))
        raw[p + y * len(b):p + (y + 1) * len(b)] = b
    m.tims[k] = bytes(raw)

# ----------------------------------------------------------------------------- describe

FOLLOW_MODES = {0: 'still', 1: 'path only', 2: 'turns to the player in range', 11: 'turns to the player in range',
                3: 'chases (square range)', 4: 'chases (square range)', 5: 'chases (square range)',
                12: 'chases (square range)', 13: 'chases (square range)', 14: 'chases (square range)',
                6: 'chases (radius)', 15: 'chases (radius)', 7: 'chases fast (radius)', 16: 'chases fast (radius)',
                8: 'chases (square, anim 2)', 9: 'chases (square, anim 2)', 17: 'chases (square, anim 2)',
                18: 'chases (square, anim 2)'}


def path_text(d):
    out = []
    for k, a in enumerate(d['aiSections']):
        if a == -1: out.append('loop'); break
        wp = d['waypoints'][k] if k < len(d['waypoints']) else None
        if a == 0: out.append(f'wait:{wp[0] if wp else "?"}')
        elif a in (1, 2): out.append(f'{"walk" if a == 1 else "run"}:{wp[0]},{wp[2]}' if wp else f'{a}:?')
        else: out.append(f'?{a}')
    return ' '.join(out)


def describe(path, tfs_path=None, maphead=None, screen=None, exe=None, reverse=True):
    m = MapFile(open(path, 'rb').read()); size = os.path.getsize(path)
    tp = tfs_path or find_tfs(path) or (original_file(path) or path)[:-4] + '.TFS'
    t = TfsFile(open(tp, 'rb').read()) if tp and os.path.exists(tp) else None
    orig = original_file(path); scr = screens_of_file(path)
    if screen is not None: scr = [screen]
    P = print
    P(f'== {path}: {size} bytes, {-(-size // 2048)} sectors' +
      (f' (original {os.path.getsize(orig)} bytes: {-(-os.path.getsize(orig) // 2048) * 2048 - size} bytes free in its sectors)' if orig else ''))
    P(f'   screens using this file: {", ".join(screen_name(s) for s in scr) or "none (no MAP_ENTRIES row)"}')
    exe_b = open(exe or os.path.join(ROOT, 'extracted/SLUS_010.32'), 'rb').read()
    for s in scr:
        P('   ' + entry_text(s, read_entry(exe_b, s, exe_offset('MAP_ENTRIES'))))
    basis = camera_basis(m); W, H = m.width * 128, m.height * 128
    c = m.camera
    E = (2 * c['vpx'], 2 * c['vpy'], 2 * c['vpz']); T = (2 * c['vrx'], 2 * c['vry'], 2 * c['vrz'])
    yaw = math.degrees(math.atan2(T[0] - E[0], T[2] - E[2]))
    pitch = math.degrees(math.atan2(-(T[1] - E[1]), math.hypot(T[0] - E[0], T[2] - E[2])))
    P(f'\n-- camera (world units = file ×2): eye {E} target {T}; looks {yaw:.0f}° from +Z towards +X, {pitch:.0f}° down; '
      f'projection {m.projection} (horizontal FOV {2 * math.degrees(math.atan(W / 2 / m.projection)):.1f}° over the background)')
    P('   lights (GsSetFlatLight; evening ×1/.7/.7, night ×.5): ' +
      '; '.join(f'{i}: dir ({l["vx"]},{l["vy"]},{l["vz"]}) rgb ({l["r"]},{l["g"]},{l["b"]})' for i, l in enumerate(m.lights)))
    P(f'   ambient {m.ambient} (ignored by the game); partner regions A {m.regionA} B {m.regionB}')
    P(f'-- background: {m.width}×{m.height} tiles = {W}×{H} px, {m.n_tiles()} tiles with image' +
      (f'; {tp}: {len(t.cluts)} CLUT(s), {len(t.tiles)} tiles' if t else '; no .TFS found'))
    for i, raw in enumerate(m.tims):
        tim = TIM(raw)
        P(f'   TIM {i}: {tim.bpp} bpp, VRAM ({tim.x},{tim.y}) {tim.w * (4 if tim.bpp == 4 else 2) if tim.bpp in (4, 8) else tim.w}×{tim.h} px, '
          f'CLUT {"background palette (row 480)" if tim.clut and tim.clut[1] == 480 else tim.clut[:2] if tim.clut else None}')
    if m.has_sprites:
        P(f'   sprites: {len(m.sprites)} definitions, {len(m.instances)} instances (pieces of the background drawn over characters)')
        for i, inst in enumerate(m.instances):
            fr = [f for f in inst['frames'] if f >= 0]
            sp = m.sprites[fr[0]] if fr and fr[0] < len(m.sprites) else None
            st = 'hidden (flag 1)' if inst['flag'] == 1 else 'snow' if inst['flag'] & 0x80 else 'shown'
            P(f'     I{i}: at px ({inst["x"]},{inst["y"]})' + (f' {sp["width"]}×{sp["height"]}' if sp else '') +
              f', {len(fr)} frame(s) {fr[:8]}, {st}' + (f', depth point ({sp["x"]},{sp["y"]},{sp["z"]})' if sp else ''))
    # exits
    P('\n-- exits (spawn point = where the player appears when ARRIVING through it; tiles exit:K send to the target)')
    for i, w in enumerate(m.warps):
        tiles = [j for j, v in enumerate(m.collision) if v == 110 + i]
        if not warp_used(w) and not tiles: continue
        tx, tz = world_to_tile(w['x'], w['z']); p = project(m, basis, (w['x'], 0, w['z']))
        tgt = f'{screen_name(w["targetMap"])} exit {w["targetExit"]}' if w['targetMap'] >= 0 else 'none (-1: script use)'
        rr = ' '.join(f'{a},{b}-{c2},{d2}' for a, b, c2, d2 in rects_of(m.collision, 110 + i)) or 'NONE'
        P(f'   exit {i}: spawn x={w["x"]} z={w["z"]} (tile {tx},{tz}, px {p[0]:.0f},{p[1]:.0f}) facing {heading_name(w["rotation"])}'
          f' -> {tgt}; trigger tiles ({len(tiles)}): {rr}' if p else f'   exit {i}: spawn {w} -> {tgt}')
        v = m.collision[tz * 100 + tx] if 0 <= tx < 100 and 0 <= tz < 100 else None
        if v is not None and (v & 0x80 or 110 <= v <= 119) and warp_used(w):
            P(f'     note: the spawn tile is {value_name(v)}')
    if reverse and scr:
        inc = []
        for p2 in sorted(glob.glob(os.path.join(ROOT, 'extracted/MAP/*/*.MAP'))):
            try: mm = MapFile(open(p2, 'rb').read())
            except Exception: continue
            for k, w in enumerate(mm.warps):
                if w['targetMap'] in scr and 0 <= w['targetExit'] <= 9: inc.append(f'{os.path.basename(p2)[:-4]} exit {k} -> exit {w["targetExit"]}')
        P('   arriving from: ' + ('; '.join(inc) if inc else 'no .MAP exit leads here (scripts only)'))
    # Digimon
    mh = maphead_info(scr[0], maphead) if scr else None
    reads = not scr or int(tables()['screens'][scr[0]]['flags']) & 0x80
    P(f'\n-- placed Digimon: {len(m.digimon)} (count field {m.digimon_count})' +
      ('' if reads else ' — MAP_ENTRIES flags lack 0x80: the game does NOT read this list'))
    for i, d in enumerate(m.digimon):
        tx, tz = world_to_tile(d['posX'], d['posZ']); p = project(m, basis, (d['posX'], d['posY'], d['posZ']))
        sets = [s for s in (mh['sets'] if mh else []) if s[0] == i]
        mv = [d[f'move{k}'] for k in range(4)]
        P(f'   D{i}: {digimon_name(d["type"])} (type {d["type"]}) at x={d["posX"]} z={d["posZ"]} (tile {tx},{tz}' +
          (f', px {p[0]:.0f},{p[1]:.0f}' if p else '') + f') facing {heading_name(d["rotY"])}; followMode {d["followMode"]} '
          f'{FOLLOW_MODES.get(d["followMode"], "?")}, range {d["trackingRange"]}')
        P(f'       script section {d["scriptId"]} on touch/talk; HP {d["hp"]} MP {d["mp"]} off {d["off"]} def {d["def"]} '
          f'speed {d["speed"]} brain {d["brain"]}, bits {d["bits"]}, moves {mv} prio {[d[f"prio{k}"] for k in range(4)]}, '
          f'flee ({d["fleeX"]},{d["fleeY"]},{d["fleeZ"]})')
        P(f'       path: {path_text(d)}; MAPHEAD: ' + ('unknown (no screen: pass --screen N)' if not mh else
          ', '.join(f'SET_DIGIMON {digimon_name(t2)} autotalk {a}' + ('' if t2 == d['type'] else ' (TYPE MISMATCH: fails)') for _, t2, a in sets)
           if sets else 'never spawned by MAPHEAD (a DG.SCN event may still spawn it)'))
    if mh:
        P(f'   MAPHEAD section {scr[0]} ({mh["label"]}): script {mh["script"]}, loads {[digimon_name(x) for x in mh["loads"]]}'
          f'{", with conditions (time/triggers)" if mh["conditional"] else ""}' +
          (f'; shared with screens {mh["shared_with"]}' if mh['shared_with'] else ''))
    # collision
    P('\n-- collision (100×100 tiles of 100 units; tile (tx,tz) centre = x (tx-50)*100+50, z (50-tz)*100-50)')
    vals = {}
    for v in m.collision: vals[v] = vals.get(v, 0) + 1
    secs, _ = script_sections(mh['script']) if mh and mh['script'] is not None else (None, '')
    for v, n in sorted(vals.items()):
        if v == 0 or v & 0x80:
            P(f'   {value_name(v)}: {n} tiles'); continue
        rr = rects_of(m.collision, v)
        note = ''
        if secs is not None and (51 <= v <= 109) and v not in secs: note = f'  (script {mh["script"]} has NO section {v})'
        if 110 <= v <= 119 and m.warps[v - 110]['targetMap'] < 0: note = '  (that exit has no target)'
        P(f'   {value_name(v)}: {n} tiles: ' + ' '.join(f'{a},{b}-{c2},{d2}' for a, b, c2, d2 in rr[:12]) +
          (' …' if len(rr) > 12 else '') + note)
    xs = [i % 100 for i, v in enumerate(m.collision) if not v & 0x80]
    zs = [i // 100 for i, v in enumerate(m.collision) if not v & 0x80]
    if xs:
        P(f'   walkable area spans tiles x {min(xs)}-{max(xs)}, z {min(zs)}-{max(zs)}')
    if mh and mh['script'] is not None and secs is not None:
        P(f'   screen script {mh["script"]} (DG.SCN) sections: {secs}')
    if m.entities_tail: P(f'   {len(m.entities_tail)} bytes after the entities (kept as they are)')


# ----------------------------------------------------------------------------- edit

def apply_ops(m, ops, ctx):
    """Applies the `edit` operations in order. ctx: {'screen', 'mh_ops', 'tfs', 'notes'}."""
    note = ctx['notes'].append
    def slot_ok(s):
        s = int(s)
        if not 0 <= s < len(m.digimon): raise MapEditError(f'no placed Digimon in slot {s} (slots 0-{len(m.digimon) - 1})')
        return s
    def exit_ok(k):
        k = int(k)
        if not 0 <= k <= 9: raise MapEditError(f'exit {k}: 0-9')
        return k
    def target_ok(mp, ex):
        mp, ex = int(mp), int(ex)
        if mp == -1: return -1, -1
        if not 0 <= mp <= 254 or not 0 <= ex <= 9: raise MapEditError(f'target {mp}.{ex}: screen 0-254 (or -1), exit 0-9')
        if mp not in tables()['screens']: note(f'target screen {mp} has no MAP_ENTRIES row today (new screen?)')
        return mp, ex
    for op, a in ops:
        if op == 'set_exit':
            k = exit_ok(a[0]); mp, ex = target_ok(a[4], a[5])
            m.warps[k].update(x=int(a[1]), y=0, z=int(a[2]), rotation=parse_heading(a[3]), targetMap=mp, targetExit=ex)
        elif op == 'spawn':
            k = exit_ok(a[0]); m.warps[k].update(x=int(a[1]), z=int(a[2]))
            if len(a) > 3: m.warps[k]['rotation'] = parse_heading(a[3])
        elif op == 'target':
            k = exit_ok(a[0]); mp, ex = target_ok(a[1], a[2]); m.warps[k].update(targetMap=mp, targetExit=ex)
        elif op == 'clear_exit':
            k = exit_ok(a[0]); m.warps[k].update(x=0, y=0, z=0, rotation=0, targetMap=-1, targetExit=-1)
            n = sum(1 for v in m.collision if v == 110 + k)
            if n: note(f'exit {k} cleared but {n} tiles still have exit:{k} (repaint them)')
        elif op in ('paint', 'paint_world'):
            if op == 'paint':
                x0, z0, x1, z1 = (int(v) for v in a[:4])
            else:
                (x0, z0), (x1, z1) = world_to_tile(int(a[0]), int(a[1])), world_to_tile(int(a[2]), int(a[3]))
            v = parse_value(a[4])
            for c in (x0, z0, x1, z1):
                if not 0 <= c <= 99: raise MapEditError(f'tile {c} outside 0-99')
            n = 0
            for tz in range(min(z0, z1), max(z0, z1) + 1):
                for tx in range(min(x0, x1), max(x0, x1) + 1): m.collision[tz * 100 + tx] = v; n += 1
            note(f'painted {n} tiles x {min(x0, x1)}-{max(x0, x1)} z {min(z0, z1)}-{max(z0, z1)} = {value_name(v)}')
        elif op == 'replace_value':
            old, new = parse_value(a[0]), parse_value(a[1]); n = 0
            for j, v in enumerate(m.collision):
                if v == old: m.collision[j] = new; n += 1
            note(f'{n} tiles {value_name(old)} -> {value_name(new)}')
        elif op == 'camera':
            e = [int(v) for v in a]
            if any(v % 2 for v in e): note('camera values are stored halved: odd values are rounded down to even')
            for k2, v in zip(SETUP_FIELDS, e): m.camera[k2] = v // 2
        elif op == 'projection':
            m.projection = int(a[0])
        elif op == 'light':
            i = int(a[0])
            if not 0 <= i <= 2: raise MapEditError('light 0-2')
            m.lights[i] = dict(zip(LIGHT_FIELDS, (int(v) for v in a[1:7])))
        elif op == 'regions':
            v = [int(x) for x in a]; m.regionA, m.regionB = v[:4], v[4:8]
        elif op == 'add_digimon':
            typ = digimon_type(a[0]); x, z = int(a[1]), int(a[2])
            if len(m.digimon) >= 8: raise MapEditError('already 8 placed Digimon (MAP_DIGIMON_TABLE[8])')
            like = int(a[3]) if len(a) > 3 else None
            if like is not None:
                d = json.loads(json.dumps(m.digimon[slot_ok(like)]))
            else:
                d = {k2: 0 for k2 in DIGI_FIELDS}
                d.update({'followMode': 12, 'trackingRange': 600, 'hp': 500, 'mp': 500, 'currentHP': 500, 'currentMP': 500,
                          'off': 100, 'def': 100, 'speed': 100, 'brain': 100, 'bits': 100,
                          'prio0': 1, 'prio1': 1, 'prio2': 1})
                d['aiSections'] = [0, -1, -1, -1, -1, -1, -1, -1]; d['waypoints'] = [[60, 0, 0]]
                d['scriptId'] = 5 + len(m.digimon)          # its entity id and talk section, as the game numbers them
            if like is None or d['type'] != typ:
                mvs = (tables()['digimon'].get(typ, {}).get('moves') or '').split()
                if not mvs: raise MapEditError(f'{digimon_name(typ)} has no techniques: it cannot fight')
                for k2 in range(4): d[f'move{k2}'] = 0x2E + k2 if k2 < min(3, len(mvs)) else 255
            old = (d['posX'], d['posZ']); d['type'] = typ; d['posX'], d['posY'], d['posZ'] = x, 0, z
            shift_path(d, x - old[0], z - old[1])
            m.digimon.append(d); m.digimon_count = len(m.digimon); slot = len(m.digimon) - 1
            ctx['mh_ops'].append(('add', typ, slot, 1)); ctx.setdefault('talk_sections', []).append((slot, d['scriptId']))
            note(f'added D{slot}: {digimon_name(typ)} at ({x},{z}), script section {d["scriptId"]}')
        elif op == 'remove_digimon':
            s = slot_ok(a[0]); ctx['mh_ops'].append(('remove', s))
            if s == len(m.digimon) - 1:
                m.digimon.pop(); m.digimon_count = len(m.digimon); note(f'removed D{s} from the .MAP and MAPHEAD')
            else:
                note(f'D{s} stays in the .MAP (later slots keep their numbers; scripts refer to them) and is no '
                     f'longer spawned by MAPHEAD')
        elif op == 'move_digimon':
            s = slot_ok(a[0]); d = m.digimon[s]; x, z = int(a[1]), int(a[2])
            shift_path(d, x - d['posX'], z - d['posZ']); d['posX'], d['posZ'] = x, z
        elif op == 'set_digimon':
            s = slot_ok(a[0]); d = m.digimon[s]
            for kv in a[1:]:
                k2, _, v = kv.partition('=')
                k2 = {'x': 'posX', 'y': 'posY', 'z': 'posZ', 'rotation': 'rotY', 'heading': 'rotY', 'script': 'scriptId',
                      'currenthp': 'currentHP', 'currentmp': 'currentMP', 'range': 'trackingRange', 'follow': 'followMode'}.get(k2.lower(), k2)
                if k2 == 'type':
                    new = digimon_type(v)
                    if new != d['type']: ctx['mh_ops'].append(('retype', s, d['type'], new))
                    d['type'] = new; continue
                if k2 not in DIGI_FIELDS: raise MapEditError(f'unknown Digimon field "{k2}" ({", ".join(DIGI_FIELDS)})')
                d[k2] = parse_heading(v) if k2 == 'rotY' else int(v, 0)
                if k2 in ('hp', 'mp'): d['current' + k2.upper()] = int(v, 0)
        elif op == 'path':
            s = slot_ok(a[0]); d = m.digimon[s]; ai, wps = [], []
            for st in a[1:]:
                kind, _, arg = st.partition(':')
                if kind == 'wait': ai.append(0); wps.append([int(arg), 0, 0])
                elif kind in ('walk', 'run'):
                    x, z = (int(v) for v in arg.split(',')); ai.append(1 if kind == 'walk' else 2); wps.append([x, 0, z])
                elif kind == 'loop': break
                else: raise MapEditError(f'path step "{st}": wait:FRAMES, walk:X,Z, run:X,Z, loop')
            if len(ai) > 7: raise MapEditError('a path has at most 7 steps (8 sections, the last one ends it)')
            d['aiSections'] = ai + [-1] * (8 - len(ai)); d['waypoints'] = wps
        elif op == 'instance':
            i = int(a[0])
            if not 0 <= i < len(m.instances): raise MapEditError(f'no sprite instance {i}')
            v = a[1].lower()
            if v == 'hide': m.instances[i]['flag'] = 1
            elif v == 'show': m.instances[i]['flag'] = 0
            else:
                x, y = (int(c) for c in v.split(',')); m.instances[i]['x'], m.instances[i]['y'] = x, y
        elif op == 'sprite':
            i = int(a[0])
            if not 0 <= i < len(m.sprites): raise MapEditError(f'no sprite definition {i}')
            for kv in a[1:]:
                k2, _, v = kv.partition('=')
                if k2 not in SPRITE_FIELDS: raise MapEditError(f'sprite field "{k2}" ({", ".join(SPRITE_FIELDS)})')
                m.sprites[i][k2] = int(v, 0)
        elif op == 'tim':
            tim_import(m, int(a[0]), a[1], ctx.get('tfs'))
        else:
            raise MapEditError(f'unknown operation {op}')


def shift_path(d, dx, dz):
    """Moves the walk/run waypoints with the Digimon (wait steps keep their frame count)."""
    for k, wp in enumerate(d['waypoints']):
        if k < 8 and d['aiSections'][k] in (1, 2): wp[0] += dx; wp[2] += dz


def validate(m, screen=None):
    """Problems that would make the edit misbehave in the game. Returns (errors, warnings)."""
    err, warn = [], []
    if len(m.digimon) > 8: err.append(f'{len(m.digimon)} placed Digimon (8 at most)')
    if m.digimon_count != len(m.digimon): err.append(f'digimon_count {m.digimon_count} != {len(m.digimon)} entries')
    for i, w in enumerate(m.warps):
        n = sum(1 for v in m.collision if v == 110 + i)
        if w['targetMap'] >= 0 and not n and warp_used(w):
            warn.append(f'exit {i} leads to {w["targetMap"]}.{w["targetExit"]} but no tile is exit:{i} (paint some)')
        if n and w['targetMap'] < 0: warn.append(f'{n} tiles are exit:{i} but exit {i} has no target')
        if warp_used(w):
            tx, tz = world_to_tile(w['x'], w['z'])
            if not (0 <= tx < 100 and 0 <= tz < 100): err.append(f'exit {i} spawn outside the grid'); continue
            v = m.collision[tz * 100 + tx]
            if v & 0x80: warn.append(f'exit {i} spawn ({w["x"]},{w["z"]}) is on a wall tile ({tx},{tz})')
            if 110 <= v <= 119: warn.append(f'exit {i} spawn ({w["x"]},{w["z"]}) is on exit tile {value_name(v)}: '
                                            'arriving there leaves again at once')
        if w['targetMap'] >= 0 and w['targetMap'] in tables()['screens']:
            f = tables()['screens'][w['targetMap']]['file']; tp = glob.glob(os.path.join(ROOT, f'extracted/MAP/*/{f}.MAP'))
            if tp:
                tw = MapFile(open(tp[0], 'rb').read()).warps[w['targetExit']]
                if not warp_used(tw): warn.append(f'exit {i}: target {w["targetMap"]}.{w["targetExit"]} has no spawn point '
                                                  f'there (the player would appear at 0,0 facing +Z)')
    for i, d in enumerate(m.digimon):
        if not 1 <= d['type'] < 180: err.append(f'D{i}: type {d["type"]}')
        tx, tz = world_to_tile(d['posX'], d['posZ'])
        if not (0 <= tx < 100 and 0 <= tz < 100): err.append(f'D{i} outside the grid')
        elif m.collision[tz * 100 + tx] & 0x80: warn.append(f'D{i} ({d["posX"]},{d["posZ"]}) stands on a wall tile ({tx},{tz})')
        if len(d['waypoints']) > 8: err.append(f'D{i}: {len(d["waypoints"])} waypoints (8 at most)')
    if screen is not None and screen in tables()['screens']:
        if m.digimon and not int(tables()['screens'][screen]['flags']) & 0x80:
            warn.append(f'MAP_ENTRIES[{screen}].flags lacks 0x80: the Digimon list is not read (dwmap.py entry … digimon=1)')
    return err, warn


class _Op(__import__('argparse').Action):
    def __call__(self, parser, ns, values, option_string=None):
        ns.ops.append((self.dest, values if isinstance(values, list) else [values]))


def edit_main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='dwmap.py edit', description='Edit a .MAP from the command line; operations '
                                 'run in the order given. Coordinates: world units (x, z), tiles (tx, tz) and '
                                 'background pixels; see `dwmap.py coords`.')
    ap.add_argument('src'); ap.add_argument('out')
    ap.set_defaults(ops=[])
    A = lambda *n, **k: ap.add_argument(*n, action=_Op, **k)
    A('--set-exit', nargs=6, metavar=('K', 'X', 'Z', 'ROT', 'MAP', 'EXIT'), help='exit K: spawn point, heading and target')
    A('--spawn', nargs='+', metavar='K X Z [ROT]', help='move the spawn point of exit K (ROT 0-4095 or z+ x+ z- x-)')
    A('--target', nargs=3, metavar=('K', 'MAP', 'EXIT'), help='where stepping on exit:K tiles leads (-1 -1: nowhere)')
    A('--clear-exit', nargs=1, metavar='K')
    A('--paint', nargs=5, metavar=('TX0', 'TZ0', 'TX1', 'TZ1', 'VALUE'),
      help='fill tiles (inclusive) with free|wall|exit:K|toilet|step:N|press:N|number')
    A('--paint-world', nargs=5, metavar=('X0', 'Z0', 'X1', 'Z1', 'VALUE'), help='same, corners in world units')
    A('--replace-value', nargs=2, metavar=('OLD', 'NEW'), help='every tile OLD becomes NEW')
    A('--camera', nargs=6, metavar=('EX', 'EY', 'EZ', 'TX', 'TY', 'TZ'), help='eye and look-at point in world units')
    A('--projection', nargs=1, metavar='F', help='focal length in pixels (GsSetProjection)')
    A('--light', nargs=7, metavar=('I', 'VX', 'VY', 'VZ', 'R', 'G', 'B'))
    A('--regions', nargs=8, metavar='R', help='partner area regions A0-3 B0-3')
    A('--add-digimon', nargs='+', metavar='TYPE X Z [LIKE_SLOT]',
      help='new placed Digimon (name or id) at x,z; LIKE_SLOT copies AI, path, stats and script section from that slot')
    A('--remove-digimon', nargs=1, metavar='SLOT')
    A('--move-digimon', nargs=3, metavar=('SLOT', 'X', 'Z'), help='its walk/run waypoints move with it')
    A('--set-digimon', nargs='+', metavar='SLOT KEY=VALUE', help='e.g. 2 hp=900 bits=500 type=Agumon script=7 rotation=+x')
    A('--path', nargs='+', metavar='SLOT STEP', help='steps wait:FRAMES walk:X,Z run:X,Z [loop]')
    A('--instance', nargs=2, metavar=('I', 'hide|show|X,Y'), help='sprite instance (foreground piece)')
    A('--sprite', nargs='+', metavar='I KEY=VALUE', help='sprite definition fields')
    A('--tim', nargs=2, metavar=('K', 'PNG'), help='replace the pixels of TIM K (same size)')
    ap.add_argument('--screen', type=int, help='screen id (default: the first MAP_ENTRIES row using this file)')
    ap.add_argument('--maphead', metavar='OUT.SCN', help='write MAPHEAD.SCN with the spawn lines for added/removed/retyped Digimon')
    ap.add_argument('--maphead-from', metavar='IN.SCN', default=os.path.join(ROOT, 'extracted/SCN/MAPHEAD.SCN'))
    ap.add_argument('--tfs', help='background for --overlay / TIM palette (default: next to SRC or in extracted/)')
    ap.add_argument('--overlay', metavar='OUT.png', help='render the result over the background')
    ap.add_argument('--force', action='store_true', help='write even with validation errors')
    a = ap.parse_args(argv)
    if not a.ops: ap.error('no operation given')
    m = MapFile(open(a.src, 'rb').read())
    scr = a.screen if a.screen is not None else (screens_of_file(a.src) or [None])[0]
    tp = a.tfs or find_tfs(a.src) or ((original_file(a.src) or a.src)[:-4] + '.TFS')
    t = TfsFile(open(tp, 'rb').read()) if os.path.exists(tp) else None
    ctx = {'screen': scr, 'mh_ops': [], 'notes': [], 'tfs': t}
    try:
        apply_ops(m, a.ops, ctx)
    except MapEditError as e:
        sys.exit(f'error: {e}')
    for n in ctx['notes']: print('note:', n)
    if ctx.get('talk_sections') and scr is not None:   # touching it runs that section; a missing one runs from NULL
        info = maphead_info(scr, a.maphead_from)
        secs = script_sections(info['script'])[0] if info and info['script'] is not None else None
        for slot, sec in ctx['talk_sections']:
            if secs is not None and sec not in secs:
                print(f'warning: D{slot} talks/fights through section {sec}, which script {info["script"]} does not have: '
                      f'add it (a DWS `place(..., slot: {slot})` writes a wild battle there, or `section {sec}:`) '
                      'or --set-digimon to an existing one', file=sys.stderr)
    err, warn = validate(m, scr)
    _, before = validate(MapFile(open(a.src, 'rb').read()), scr)
    old = [w for w in warn if w in before]; warn = [w for w in warn if w not in before]
    for w in warn: print('warning:', w, file=sys.stderr)
    if old: print(f'({len(old)} warning(s) already true of {os.path.basename(a.src)} not repeated; see `dwmap.py describe`)')
    for e in err: print('ERROR:', e, file=sys.stderr)
    if err and not a.force: sys.exit('not written (use --force to write anyway)')
    data = m.build()
    if MapFile(data).build() != data: sys.exit('internal error: the rebuilt .MAP does not parse back identically')
    open(a.out, 'wb').write(data); size_report(a.out, data, original_file(a.src))
    if ctx['mh_ops']:
        if not a.maphead:
            print(f'warning: placed Digimon were added/removed/retyped; MAPHEAD section {scr} decides which ones appear. '
                  f'Add --maphead OUT.SCN to rewrite it ({ctx["mh_ops"]})', file=sys.stderr)
        elif scr is None:
            sys.exit('--maphead needs --screen (this file has no MAP_ENTRIES row)')
        else:
            try:
                maphead_edit(a.maphead_from, a.maphead, scr, ctx['mh_ops'])
            except MapEditError as e:
                sys.exit(f'error: {e}')
    if a.overlay:
        if not t: sys.exit('no .TFS for the overlay (--tfs)')
        W, H, img = render_overlay(m, t); png_write(a.overlay, W, H, img, mode='RGB'); print(a.overlay)


def bg_main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='dwmap.py bg', description='Edit the background (.TFS) in place of a region, '
                                 'keeping the palette (evening/night follow by index). Coordinates: background pixels '
                                 '(see `dwmap.py coords`).')
    ap.add_argument('map'); ap.add_argument('tfs'); ap.add_argument('out')
    ap.set_defaults(ops=[])
    A = lambda *n, **k: ap.add_argument(*n, action=_Op, **k)
    A('--paste', nargs=3, metavar=('PNG', 'X', 'Y'), help='RGB/RGBA/indexed PNG at pixel X,Y (alpha < 128 skipped)')
    A('--text', nargs=3, metavar=('X', 'Y', 'TEXT'), help='write TEXT (5×7 font) with its top-left at X,Y')
    A('--fill', nargs=5, metavar=('X0', 'Y0', 'X1', 'Y1', 'COLOR'), help='filled rectangle (end exclusive)')
    A('--fill-tiles', nargs=5, metavar=('TX0', 'TZ0', 'TX1', 'TZ1', 'COLOR'),
      help='paint the ground under a rectangle of collision tiles (inclusive), projected through the camera')
    ap.add_argument('--scale', type=int, default=4); ap.add_argument('--color', default='255,255,255')
    ap.add_argument('--box', help='colour of a box behind --text (e.g. 40,30,20)')
    ap.add_argument('--at-world', action='store_true', help='X Y of --text/--paste are world x z (ground point → pixel; centred)')
    ap.add_argument('--overlay', metavar='OUT.png')
    a = ap.parse_args(argv)
    m = MapFile(open(a.map, 'rb').read()); t = TfsFile(open(a.tfs, 'rb').read())
    basis = camera_basis(m)
    for op, v in a.ops:
        if op == 'paste':
            X, Y = int(v[1]), int(v[2])
            if a.at_world:
                w, h, *_ = png_read(v[0]); p = project(m, basis, (X, 0, Y)); X, Y = int(p[0] - w / 2), int(p[1] - h / 2)
            n, box = bg_paste(m, t, v[0], X, Y)
        elif op == 'text':
            X, Y = int(v[0]), int(v[1])
            if a.at_world:
                tw, th = text_size(v[2], a.scale); p = project(m, basis, (X, 0, Y)); X, Y = int(p[0] - tw / 2), int(p[1] - th / 2)
            n, box = bg_text(m, t, X, Y, v[2], a.scale, parse_color(a.color), parse_color(a.box) if a.box else None)
        elif op == 'fill':
            n, box = bg_fill(m, t, *(int(c) for c in v[:4]), parse_color(v[4]))
        elif op == 'fill_tiles':
            n, box = bg_fill_tiles(m, t, *(int(c) for c in v[:4]), parse_color(v[4]))
        cov = covering_instances(m, *box)
        print(f'{op}: {n} pixels in {box[0]},{box[1]}-{box[2]},{box[3]}' +
              (f'; sprite instances {cov} are drawn over that area (hide them with edit --instance I hide)' if cov else ''))
    if not a.ops: ap.error('no operation given')
    data = t.build(); open(a.out, 'wb').write(data); size_report(a.out, data, (original_file(a.map) or a.map)[:-4] + '.TFS')
    if a.overlay:
        W, H, img = render_overlay(m, t, collision=False); png_write(a.overlay, W, H, img, mode='RGB'); print(a.overlay)


def coords_main(argv):
    import argparse, subprocess
    ap = argparse.ArgumentParser(prog='dwmap.py coords', description='Convert between world (x, z), tile (tx, tz), '
                                 'background pixel (u, v) and screen pixel for one map.')
    ap.add_argument('map')
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--world', nargs=2, type=int, metavar=('X', 'Z'))
    g.add_argument('--tile', nargs=2, type=int, metavar=('TX', 'TZ'))
    g.add_argument('--pixel', nargs=2, type=float, metavar=('U', 'V'), help='background pixel')
    g.add_argument('--screen-px', nargs=2, type=float, metavar=('SX', 'SY'), help='pixel of a 320×240 screenshot (needs --camera-xy or --live)')
    ap.add_argument('--camera-xy', nargs=2, type=int, metavar=('CX', 'CY'), help='MAP_TILE_DATA.cameraX/Y (background pixel at the top-left of the screen)')
    ap.add_argument('--live', action='store_true', help='read cameraX/Y from the running emulator (EMU_PORT)')
    a = ap.parse_args(argv)
    m = MapFile(open(a.map, 'rb').read()); basis = camera_basis(m)
    cam = a.camera_xy
    if a.live:
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools/dev/emulator.py'), 'peek', hex(0x8014F084 + 0x1BB4), '4'],
                           capture_output=True, text=True)
        hx = [w for w in r.stdout.split()[1:] if re.fullmatch(r'[0-9a-fA-F]{2}', w)]   # "ADDR  b0 b1 b2 b3" 
        if len(hx) >= 4:
            b = bytes(int(h, 16) for h in hx[:4]); cam = struct.unpack('<hh', b)
        else: sys.exit(f'emu.py peek: {r.stdout}{r.stderr}')
    if a.world: x, z = a.world
    elif a.tile: x, z = tile_to_world(*a.tile)
    else:
        u, v = a.pixel if a.pixel else (a.screen_px[0] + cam[0], a.screen_px[1] + cam[1]) if cam else sys.exit('--screen-px needs --camera-xy or --live')
        w = pixel_to_world(m, u, v, basis)
        if not w: sys.exit('that pixel does not look at the ground')
        x, z = round(w[0]), round(w[1])
    tx, tz = world_to_tile(x, z); p = project(m, basis, (x, 0, z))
    v = m.collision[tz * 100 + tx] if 0 <= tx < 100 and 0 <= tz < 100 else None
    print(f'world x={x} z={z}  tile tx={tx} tz={tz} ({value_name(v) if v is not None else "outside"}; centre '
          f'{tile_to_world(tx, tz)})  background px {p[0]:.0f},{p[1]:.0f}' if p else f'world {x},{z} tile {tx},{tz} (behind the camera)', end='')
    if cam and p: print(f'  screen px {p[0] - cam[0]:.0f},{p[1] - cam[1]:.0f} (camera {cam[0]},{cam[1]})')
    else: print()


def entry_main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='dwmap.py entry', description='Show or change a MAP_ENTRIES row of the executable. '
                                 'Fields: name n8 n4 flags sound daynight digimon doors toilet label.')
    ap.add_argument('exe'); ap.add_argument('id', type=int); ap.add_argument('set', nargs='*', metavar='FIELD=VALUE')
    ap.add_argument('-o', '--out', help='write the patched executable here (same size: no LBA moves)')
    ap.add_argument('--map', help='linker map of a GCC/mods executable (default: original addresses)')
    a = ap.parse_args(argv)
    exe = bytearray(open(a.exe, 'rb').read()); off = exe_offset('MAP_ENTRIES', a.map)
    if not 0 <= a.id < 255: sys.exit('id 0-254')
    e = read_entry(exe, a.id, off); print(entry_text(a.id, e))
    if not a.set: return
    for kv in a.set:
        k, _, v = kv.partition('=')
        if k == 'name':
            if not re.fullmatch(r'[A-Z0-9_]{1,9}', v): sys.exit('name: up to 9 of A-Z 0-9 _ (the file looked up is NAME.MAP/.TFS)')
            e['name'] = v
        elif k == 'sound': e['flags'] = (e['flags'] & ~0x1F) | (int(v, 0) & 0x1F)
        elif k == 'daynight': e['flags'] = (e['flags'] & ~0x40) | (0 if int(v) else 0x40)
        elif k == 'digimon': e['flags'] = (e['flags'] & ~0x80) | (0x80 if int(v) else 0)
        elif k in ('n8', 'n4', 'flags', 'doors', 'toilet', 'label'): e[k] = int(v, 0)
        else: sys.exit(f'unknown field {k}')
    if not 0 <= e['doors'] <= 24: sys.exit('doors 0-24 (DOOR_MAPDATA has 24 entries; 0 = none)')
    if not 0 <= e['toilet'] <= 10: sys.exit('toilet 0-10 (TOILET_DATA has 10 entries; 0 = none)')
    if not 0 <= e['label'] < 70: sys.exit('label 0-69 (MAP_NAME_PTR)')
    if e['flags'] & 0x40: print('note: daynight=0 needs a 1-CLUT .TFS, and 3 CLUTs otherwise')
    row = map_entry_bytes(e['name'], e['n8'], e['n4'], e['flags'], e['doors'], e['toilet'], e['label'])
    print('->  ' + entry_text(a.id, read_entry(row, 0, 0)))
    if not a.out: print(f'(not written: add -o OUT; RAM 0x{MAP_ENTRIES_RAM + 16 * a.id:08X} for emu.py poke: {row.hex()})'); return
    exe[off + 16 * a.id:off + 16 * a.id + 16] = row; open(a.out, 'wb').write(exe); print(a.out)


def doors_main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='dwmap.py doors', description='Show or change DOOR_MAPDATA (24 entries × 6 door '
                                 'models: model id (255 = none), x y z, rotation). A screen uses entry doors-1 '
                                 '(MAP_ENTRIES.doorsId). Opening/blocking doors is up to its script.')
    ap.add_argument('exe'); ap.add_argument('entry', type=int, nargs='?', help='1-24 (as in MAP_ENTRIES.doorsId)')
    ap.add_argument('--set', nargs=6, action='append', metavar=('K', 'MODEL', 'X', 'Y', 'Z', 'ROT'), default=[])
    ap.add_argument('-o', '--out'); ap.add_argument('--map')
    a = ap.parse_args(argv)
    exe = bytearray(open(a.exe, 'rb').read()); off = exe_offset('DOOR_MAPDATA', a.map); ents = door_entries(exe, off)
    users = {}
    for i, r in tables()['screens'].items():
        if int(r['doors_id']): users.setdefault(int(r['doors_id']), []).append(i)
    for i, e in enumerate(ents):
        if a.entry and i + 1 != a.entry: continue
        print(f'doors {i + 1} (screens {users.get(i + 1, [])}): ' +
              '; '.join(f'{k}: model {d["model"]} at ({d["x"]},{d["y"]},{d["z"]}) rot {d["rotation"]}' for k, d in enumerate(e) if d['model'] != 255))
    if a.set:
        if not a.entry: sys.exit('--set needs ENTRY')
        o = off + 54 * (a.entry - 1)
        for k, mid, x, y, z, r in a.set:
            k = int(k)
            if not 0 <= k < 6: sys.exit('door K 0-5')
            exe[o + k] = int(mid) & 255
            for j, v in enumerate((x, y, z, r)): struct.pack_into('<h', exe, o + 6 + 12 * j + 2 * k, int(v))
        if not a.out: sys.exit('add -o OUT to write')
        open(a.out, 'wb').write(exe); print(a.out)


def toilet_main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog='dwmap.py toilet', description='Show or change TOILET_DATA (10 entries: the two '
                                 'points x1 z1 x2 z2 the partner walks to). A screen uses entry toilet-1 '
                                 '(MAP_ENTRIES.toiletId) when the player stands on a `toilet` (120) tile.')
    ap.add_argument('exe'); ap.add_argument('entry', type=int, nargs='?')
    ap.add_argument('--set', nargs=4, type=int, metavar=('X1', 'Z1', 'X2', 'Z2'))
    ap.add_argument('-o', '--out'); ap.add_argument('--map')
    a = ap.parse_args(argv)
    exe = bytearray(open(a.exe, 'rb').read()); off = exe_offset('TOILET_DATA', a.map)
    users = {}
    for i, r in tables()['screens'].items():
        if int(r['toilet_id']): users.setdefault(int(r['toilet_id']), []).append(i)
    for i, e in enumerate(toilet_entries(exe, off)):
        if a.entry and i + 1 != a.entry: continue
        print(f'toilet {i + 1} (screens {users.get(i + 1, [])}): ({e[0]},{e[1]}) then ({e[2]},{e[3]})')
    if a.set:
        if not a.entry: sys.exit('--set needs ENTRY')
        struct.pack_into('<4h', exe, off + 8 * (a.entry - 1), *a.set)
        if not a.out: sys.exit('add -o OUT to write')
        open(a.out, 'wb').write(exe); print(a.out)

# ----------------------------------------------------------------------------- commands

def info(path):
    m = MapFile(open(path, 'rb').read())
    print(f'{path}: {os.path.getsize(path)} bytes, {len(m.tims)} TIM, sprites={m.has_sprites}')
    print(f'  camera (file values; the game multiplies them by 2): {m.camera}  projection {m.projection}')
    for i, l in enumerate(m.lights): print(f'  light {i}: {l}')
    print(f'  ambient {m.ambient}  regions A {m.regionA} B {m.regionB}')
    print(f'  background {m.width}×{m.height} tiles ({m.n_tiles()} with image): {m.tiles}')
    for i, raw in enumerate(m.tims):
        t = TIM(raw); print(f'  TIM {i}: {t.bpp} bpp in VRAM ({t.x},{t.y}) {t.w}×{t.h} words, CLUT {t.clut[:4] if t.clut else None}, {t.size}/{len(raw)} bytes')
    print(f'  sprites: {len(m.sprites)} definitions, {len(m.instances)} instances')
    for i, w in enumerate(m.warps):
        if any(w.values()): print(f'  exit {i}: {w}')
    print(f'  Digimon: count {m.digimon_count}, read {len(m.digimon)}')
    for i, d in enumerate(m.digimon):
        print(f"    {i}: type {d['type']} follow {d['followMode']} pos ({d['posX']},{d['posY']},{d['posZ']}) hp {d['hp']} bits {d['bits']} script {d['scriptId']} waypoints {len(d['waypoints'])}")
    vals = {}
    for v in m.collision: vals[v] = vals.get(v, 0) + 1
    print(f'  collision: {dict(sorted(vals.items()))}')
    if m.entities_tail: print(f'  remainder after entities: {len(m.entities_tail)} bytes')


def roundtrip(root):
    maps = sorted(glob.glob(os.path.join(root, '*', '*.MAP')))
    tfss = sorted(glob.glob(os.path.join(root, '*', '*.TFS')))
    bad = 0
    for p in maps:
        d = open(p, 'rb').read(); m = MapFile(d)
        if m.build() != d: bad += 1; print('MAP differs:', p)
        if MapFile.from_json(json.loads(json.dumps(m.to_json()))).build() != d: bad += 1; print('JSON differs:', p)
    for p in tfss:
        d = open(p, 'rb').read()
        if TfsFile(d).build() != d: bad += 1; print('TFS differs:', p)
    # PNG → TFS: exporting the background (indexed and, in one of every 10, RGB) and importing it must give the same TFS
    import tempfile
    tmp = tempfile.mkdtemp(); png = os.path.join(tmp, 'f.png'); out = os.path.join(tmp, 'f.TFS'); npng = ntim = 0
    for k, p in enumerate(maps):
        tp = p[:-4] + '.TFS'
        if not os.path.exists(tp): continue
        m = MapFile(open(p, 'rb').read()); t = TfsFile(open(tp, 'rb').read()); W, H, idx = t.image_indices(m)
        modes = ['P', 'RGB'] if k % 10 == 0 else ['P']
        for mode in modes:
            if mode == 'P': png_write(png, W, H, idx, t.palette_rgb(0))
            else:
                pal = t.palette_rgb(0); png_write(png, W, H, [bytes(b for v in r for b in pal[v]) for r in idx], mode='RGB')
            npng += 1
            if import_png(p, tp, png, out) != open(tp, 'rb').read(): bad += 1; print(f'PNG {mode} → TFS differs:', tp)
        # sprite TIMs: exported PNG → tim-import → same .MAP
        if m.tims:
            m2 = MapFile(open(p, 'rb').read())
            for i, raw in enumerate(m2.tims):
                if TIM(raw).to_png(png): tim_import(m2, i, png, t); ntim += 1
            if m2.build() != open(p, 'rb').read(): bad += 1; print('TIM PNG → MAP differs:', p)
        # collision: exported PNG → collision-import → same .MAP
        png_write(png, 100, 100, [m.collision[r * 100:(r + 1) * 100] for r in range(100)], collision_palette())
        _, _, _, rows, _ = png_read(png); m.collision = bytearray(b''.join(bytes(r) for r in rows))
        if m.build() != open(p, 'rb').read(): bad += 1; print('collision PNG differs:', p)
    for f in (png, out):
        if os.path.exists(f): os.remove(f)
    os.rmdir(tmp)
    print(f'{len(maps)} MAP and {len(tfss)} TFS (+ {npng} PNG→TFS, {ntim} TIM PNG→TIM and {len(maps)} collision PNG): '
          f'{"all identical" if not bad else f"{bad} failures"}')
    return bad


def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return
    cmd = a[0]
    if cmd == 'info':
        info(a[1])
    elif cmd == 'roundtrip':
        sys.exit(1 if roundtrip(a[1] if len(a) > 1 else os.path.join(ROOT, 'extracted/MAP')) else 0)
    elif cmd == 'dump':
        json.dump(MapFile(open(a[1], 'rb').read()).to_json(), open(a[2], 'w'), indent=1)
    elif cmd == 'build':
        open(a[2], 'wb').write(MapFile.from_json(json.load(open(a[1]))).build())
    elif cmd == 'export':
        for f in export(a[1], a[2]): print(f)
    elif cmd == 'import-png':
        data = import_png(a[1], a[2], a[3], a[4], '--new-palette' in a)
        print(f'{a[4]}: {len(data)} bytes ({"identical to the original" if data == open(a[2], "rb").read() else "changed"})')
    elif cmd == 'collision-import':
        m = MapFile(open(a[1], 'rb').read()); w, h, mode, rows, _ = png_read(a[2])
        if (w, h, mode) != (100, 100, 'P'): raise SystemExit('a 100×100 indexed PNG is required')
        m.collision = bytearray(b''.join(bytes(r) for r in rows)); open(a[3], 'wb').write(m.build())
    elif cmd == 'describe':
        import argparse
        ap = argparse.ArgumentParser(prog='dwmap.py describe')
        ap.add_argument('map'); ap.add_argument('--tfs'); ap.add_argument('--maphead'); ap.add_argument('--screen', type=int)
        ap.add_argument('--exe'); ap.add_argument('--no-reverse', action='store_true')
        o = ap.parse_args(a[1:])
        describe(o.map, o.tfs, o.maphead, o.screen, o.exe, not o.no_reverse)
    elif cmd == 'edit':
        edit_main(a[1:])
    elif cmd == 'bg':
        bg_main(a[1:])
    elif cmd == 'coords':
        coords_main(a[1:])
    elif cmd == 'overlay':
        import argparse
        ap = argparse.ArgumentParser(prog='dwmap.py overlay')
        ap.add_argument('map'); ap.add_argument('out'); ap.add_argument('--tfs')
        ap.add_argument('--clut', type=int, default=0, help='0 day, 1 evening, 2 night')
        ap.add_argument('--no-collision', action='store_true')
        ap.add_argument('--no-grid', action='store_true', help='leave out the grid of world coordinates (a line every 500, labelled)')
        o = ap.parse_args(a[1:])
        m = MapFile(open(o.map, 'rb').read())
        tp = o.tfs or find_tfs(o.map) or (original_file(o.map) or o.map)[:-4] + '.TFS'
        W, H, img = render_overlay(m, TfsFile(open(tp, 'rb').read()), o.clut, not o.no_collision, grid=not o.no_grid)
        png_write(o.out, W, H, img, mode='RGB'); print(o.out)
    elif cmd == 'entry':
        entry_main(a[1:])
    elif cmd == 'doors':
        doors_main(a[1:])
    elif cmd == 'toilet':
        toilet_main(a[1:])
    elif cmd == 'tim-import':
        m = MapFile(open(a[1], 'rb').read()); tp = find_tfs(a[1]) or (original_file(a[1]) or a[1])[:-4] + '.TFS'
        try:
            tim_import(m, int(a[2]), a[3], TfsFile(open(tp, 'rb').read()) if os.path.exists(tp) else None)
        except MapEditError as e:
            sys.exit(f'error: {e}')
        data = m.build(); open(a[4], 'wb').write(data); size_report(a[4], data, original_file(a[1]))
    elif cmd == 'set-tiles':
        m = MapFile(open(a[1], 'rb').read()); x0, z0, x1, z1, v = (int(x, 0) for x in a[3:8])
        for tz in range(min(z0, z1), max(z0, z1) + 1):
            for tx in range(min(x0, x1), max(x0, x1) + 1): m.collision[tz * 100 + tx] = v
        open(a[2], 'wb').write(m.build())
    elif cmd == 'map-entry':
        print(map_entry_bytes(a[1], *(int(x, 0) for x in a[2:8])).hex())
    elif cmd == 'patch-exe':
        exe = bytearray(open(a[1], 'rb').read()); i = int(a[3], 0)
        if not 0 <= i < 255: raise SystemExit('id 0-254')
        row = map_entry_bytes(a[4], *(int(x, 0) for x in a[5:11])); o = MAP_ENTRIES_RAM + 16 * i - EXE_BASE
        print(f'MAP_ENTRIES[{i}] in the file at 0x{o:X} (RAM 0x{MAP_ENTRIES_RAM + 16 * i:08X}): {exe[o:o + 16].hex()} → {row.hex()}')
        exe[o:o + 16] = row; open(a[2], 'wb').write(exe)
    elif cmd == 'file-entry':
        exe = bytearray(open(a[1], 'rb').read()); t = FILE_OFFSET_TABLE_RAM - EXE_BASE
        for i in range(819):
            sec, size, ptr = struct.unpack_from('<iiI', exe, t + 12 * i)
            nm = exe[ptr - EXE_BASE:exe.index(b'\0', ptr - EXE_BASE)].decode('ascii', 'replace') if ptr > EXE_BASE else ''
            if nm == a[3]:
                new = struct.pack('<ii', int(a[4], 0), int(a[5], 0))
                print(f'FILE_OFFSET_TABLE[{i}] "{nm}" in the file at 0x{t + 12 * i:X} (RAM 0x{FILE_OFFSET_TABLE_RAM + 12 * i:08X}): '
                      f'sector 0x{sec:X} size {size} → {new.hex()}')
                exe[t + 12 * i:t + 12 * i + 8] = new; open(a[2], 'wb').write(exe); break
        else:
            raise SystemExit(f'{a[3]} is not in the table')
    elif cmd == 'mmm':
        base = os.path.join(ROOT, 'extracted/MMM.DAT'); out = bytearray(open(base, 'rb').read()); off = 0
        for f in a[2:]:
            d = open(f, 'rb').read(); out[off:off + len(d)] = d
            print(f'{f}: sector 0x{MMM_SECTOR + off // 2048:X} ({MMM_SECTOR + off // 2048}), size {len(d)}')
            off += (len(d) + 2047) // 2048 * 2048
        if len(out) != os.path.getsize(base): raise SystemExit('does not fit in MMM.DAT')
        open(a[1], 'wb').write(out)
    else:
        print(__doc__); sys.exit(1)


if __name__ == '__main__':
    main()
