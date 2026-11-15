#!/usr/bin/env python3
"""Digimon World 2 technique effects: decode, inspect and render them offline.

A DW2 technique (skill) shows up to six effect objects: three at the caster when it
casts, three at each target when it is hit. Each effect object is a pair of disc
files: an `M` file, a small model in the same format as a Digimon's model, and an `A`
file, an animation bank with one 60-frame clip for it. The format is written down in
docs/reference/dw2-effects.md.

Everything is read from the player's own Digimon World 2 (USA) disc image, through
the boot executable's file table, so file ids from the skill table can be used
directly. Nothing from the disc is stored in the repository.

Usage (from the repository root):
  python3 tools/dw2effect.py --disc DW2.bin skill "Hyper Heat"       the skill record and its effect files
  python3 tools/dw2effect.py --disc DW2.bin digimon Cyclonemon       a Digimon's signature skill and launch points
  python3 tools/dw2effect.py --disc DW2.bin info 933 895             one effect object (model file, anim file)
  python3 tools/dw2effect.py --disc DW2.bin render "Hyper Heat" --caster Cyclonemon --out sheet.png
The disc can also be given with the DW2_IMAGE environment variable.
"""
import argparse
import math
import os
import struct
import sys
from dataclasses import dataclass, field

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

EXE = 'SLUS_011.93'          # Digimon World 2 (USA)
FILE_COUNT = 0xE5B           # entries of the executable's file table
FILE_LBA = 0x33F94           # i32 start sector of each file id
FILE_SECTORS = 0x37900       # u16 sector count of each file id
SKILL_FILE = 0x25B           # skill table (stride 0x44)
BASE_FILE = 0xC6C            # Digimon base data (stride 0x12): learned skill
DATA_FILES = (0xCB9, 0xCBA, 0xCBB)   # Digimon data (stride 0x28)

CAST_TICKS = 0x78            # a cast effect object lives 120 ticks (60 Hz): its 60 frames
HIT_TICKS = 0x3C             # a hit effect object lives 60 ticks: the first 30 frames
CAST_WAIT = 0x96             # the battle script waits 150 ticks after the cast before cutting to the target
HOME_DISTANCE = 0x2800       # distance between the two rows of fighters
CAST_ANIM_BANK = 'FGH'       # the caster's clip: Skill cast field 0, 1, 2 = animation file F, G, H
BLEND_MODES = {0: '50% back + 50% effect', 1: 'back + effect (additive)', 2: 'back - effect', 3: 'back + 25% effect'}
TARGETS = {5: 'one enemy', 6: 'all enemies', 8: 'one enemy (random)', 9: 'anyone (random)', 2: 'one ally', 0: 'self'}


# ----------------------------------------------------------------- disc access

class Disc:
    """The DW2 disc image, files by the executable's file id."""

    def __init__(self, path):
        from tools.derive.importers.discs import Image
        self.image = Image(path)
        self.files = self.image.index()
        if EXE not in self.files:
            raise SystemExit(f'{path}: not Digimon World 2 (USA) ({EXE} missing)')
        exe = self.image.read(*self.files[EXE])
        self.lba = struct.unpack_from(f'<{FILE_COUNT}i', exe, FILE_LBA)
        self.sectors = struct.unpack_from(f'<{FILE_COUNT}H', exe, FILE_SECTORS)
        self.by_lba = {sector: (name, size) for name, (sector, size) in self.files.items()}
        self._cache = {}

    def name(self, fid):
        hit = self.by_lba.get(self.lba[fid])
        return hit[0] if hit else None

    def file(self, fid):
        if fid not in self._cache:
            hit = self.by_lba.get(self.lba[fid])
            size = hit[1] if hit else self.sectors[fid] * 2048
            self._cache[fid] = self.image.read(self.lba[fid], size)
        return self._cache[fid]

    def entry(self, fid, index):
        """Cd_GetFileEntry(fid << 16 | index): the file's offset table points into it."""
        data = self.file(fid)
        return data, struct.unpack_from('<I', data, 4 * index)[0]


def text(data, off):
    """DW2 text: 0x0A.. upper case, 0x24.. lower case, 0..9 digits, 0xFD space, 0x49 hyphen, 0xFF end."""
    out = []
    while off < len(data) and data[off] != 0xFF:
        b = data[off]
        off += 1
        if 0x24 <= b < 0x24 + 26:
            out.append(chr(b - 0x24 + 97))
        elif 0x0A <= b < 0x0A + 26:
            out.append(chr(b - 0x0A + 65))
        elif b < 10:
            out.append(str(b))
        elif b == 0xFD:
            out.append(' ')
        elif b == 0x49:
            out.append('-')
        else:
            out.append(f'<{b:02x}>')
    return ''.join(out)


# ----------------------------------------------------------------- tables

@dataclass
class Skill:
    id: int
    name: str
    mp: int
    power: int
    kind: int            # 3 = support
    target: int
    cast: int            # 0..2: the caster plays animation file F, G or H
    xa: tuple            # (XA file id, channel): the voice line said with the skill
    banner: int          # partsEntry: the skill-name banner parts (file << 16 | entry)
    cast_fx: list        # 3 x (model file id, anim file id), 0 = none
    hit_fx: list


def parse_skills(data):
    """The skill table (file 0x25B): records of 0x44 bytes from the offset in its first word, ended by id 0."""
    out = {}
    o = struct.unpack_from('<I', data, 0)[0]
    while o + 0x44 <= len(data):
        w0 = struct.unpack_from('<I', data, o)[0]
        sid = w0 & 0xFFFF
        if sid == 0:
            break
        mp, xch, xf, power = struct.unpack_from('<BBhh', data, o + 4)
        banner = struct.unpack_from('<i', data, o + 12)[0]
        name_off = struct.unpack_from('<I', data, o + 0x24)[0]
        fx = struct.unpack_from('<12h', data, o + 0x2C)        # fxFiles[4][3]: cast models, cast anims, hit models, hit anims
        out[sid] = Skill(sid, text(data, name_off), mp, power, (w0 >> 18) & 3, (w0 >> 20) & 0xF, (w0 >> 16) & 3,
                         (xf, xch), banner, list(zip(fx[0:3], fx[3:6])), list(zip(fx[6:9], fx[9:12])))
        o += 0x44
    return out


@dataclass
class Digimon:
    id: int
    name: str
    model: int
    anims: list          # 11 animation file ids, A..K
    head: int            # field_1E: cast/hit slot 0 sits at y = -0x280 - head
    hit_y: int           # hit slot 1 sits this high
    cast_rows: list      # per cast kind: (x, y, z) offset of cast slot 1 (the launch point)
    learned: int = 0


def parse_digimon(data):
    """A Digimon data file (0xCB9, 0xCBA, 0xCBB): entry 0 the records (0x28 bytes), entry 1 the launch-point rows."""
    out = {}
    o, rows = struct.unpack_from('<2I', data, 0)
    while o + 0x28 <= len(data):
        name_off, packed = struct.unpack_from('<Ii', data, o)
        did = (packed >> 1) & 0x7FFF
        if did == 0:
            break
        model = struct.unpack_from('<h', data, o + 6)[0]
        anims = list(struct.unpack_from('<11h', data, o + 8))
        head, hit_y, r0, r1, r2 = struct.unpack_from('<5h', data, o + 0x1E)
        cast = [struct.unpack_from('<3h', data, rows + 6 * r) for r in (r0, r1, r2)]
        out[did] = Digimon(did, text(data, name_off), model, anims, head, hit_y, cast)
        o += 0x28
    return out


def parse_learned(data):
    """Base data (file 0xC6C): records of 0x12 bytes {s16 id, u8 learned skill, ...}, ended by id 0."""
    out, o = {}, 0
    while o + 0x12 <= len(data):
        did, skill = struct.unpack_from('<hB', data, o)
        if did == 0:
            break
        out[did] = skill
        o += 0x12
    return out


class Tables:
    def __init__(self, disc):
        self.disc = disc
        self.skills = parse_skills(disc.file(SKILL_FILE))
        self.digimon = {}
        for fid in DATA_FILES:
            self.digimon.update(parse_digimon(disc.file(fid)))
        for did, skill in parse_learned(disc.file(BASE_FILE)).items():
            if did in self.digimon:
                self.digimon[did].learned = skill

    def skill(self, key):
        if str(key).isdigit():
            return self.skills[int(key)]
        hits = [s for s in self.skills.values() if s.name.lower() == str(key).lower()]
        if not hits:
            raise SystemExit(f'no skill named {key!r}')
        return hits[0]

    def digi(self, key):
        if str(key).isdigit():
            return self.digimon[int(key)]
        hits = [d for d in self.digimon.values() if d.name.lower() == str(key).lower()]
        if not hits:
            raise SystemExit(f'no Digimon named {key!r}')
        return hits[0]


# ----------------------------------------------------------------- effect objects

@dataclass
class Prim:
    verts: tuple
    uvs: tuple
    clut: int            # row << 6 | x / 16, inside the model's own texture
    blend: int           # semi-transparency mode (0..3), None = opaque


@dataclass
class Bone:
    parent: int
    vertices: list
    prims: list


@dataclass
class TexMove:
    """A texture-animation part: a rectangle copied inside the texture each tick (x and w in halfwords)."""
    dst: tuple
    size: tuple
    frames: list         # source (x, y) of each frame
    ticks: int           # ticks per frame
    period: int = 0      # timed parts: ticks of the whole cycle


@dataclass
class Effect:
    bones: list
    tim: bytes
    keys: list           # per bone: {key index: (m[9], t[3])} raw int16 (4096 = 1.0), the keys the clip uses
    frames: list         # [[key index per bone]] (one frame per two ticks)
    tex_moves: list = field(default_factory=list)
    model_size: int = 0
    anim_size: int = 0


def _list(d, off):
    n = struct.unpack_from('<h', d, off)[0]
    v = struct.unpack_from(f'<{3 * n}h', d, off + 6)
    return [v[i:i + 3] for i in range(0, 3 * n, 3)]


def _prims(d, off):
    prims = []
    for sec in range(4):                  # semi quads, opaque quads, semi triangles, opaque triangles
        n = struct.unpack_from('<i', d, off)[0]
        off += 4
        k = 4 if sec < 2 else 3
        size = 0x14 if k == 4 else 0x10
        for i in range(n):
            r = d[off + i * size:off + (i + 1) * size]
            clut, tpage = struct.unpack_from('<2H', r, 4 * k)
            uv = tuple((r[2 * k + 2 * j], r[2 * k + 2 * j + 1]) for j in range(k))
            prims.append(Prim(tuple(r[:k]), uv, clut, (tpage >> 5) & 3 if sec % 2 == 0 else None))
        off += n * size
    return prims


def tex_moves(d, count):
    """The texture-animation parts after the bone tables (DW2 Gfx_AnimateModelTex): two blink slots (unused by
    effects), then up to eight 3-frame cycles (8 ticks a frame), then after a 0xFE byte up to ten timed flipbooks
    {dstX, dstY, w, h, 4 unused, period, timer, (u, v, -, -) * 8}: frame = timer / 2, timer counts ticks modulo period."""
    off = 12 + 16 * count
    first = min(struct.unpack_from(f'<{4 * count}i', d, 12)[i] for i in range(0, count * 3))
    out = []
    for i in range(10):
        e = d[off + 10 * i:off + 10 * i + 10]
        if off + 10 * i + 10 > first:
            return out
        if i < 2:
            continue
        if e[0] == 0xFF:
            return out
        if e[0] == 0xFE:
            q = off + 10 * i + 1
            for _ in range(10):
                if q >= first or d[q] == 0xFF:
                    break
                dx, dy, w, h = d[q:q + 4]
                period = d[q + 8]
                uv = d[q + 10:q + 42]
                n = (period + 1) // 2
                out.append(TexMove((dx, dy), (w, h), [(uv[4 * f], uv[4 * f + 1]) for f in range(min(n, 8))], 2, period))
                q += 0x2A
            return out
        out.append(TexMove((e[0], e[1]), (e[2], e[3]), [(e[4], e[5]), (e[6], e[7]), (e[8], e[9])], 8))
    return out


def parse_effect(model, anim):
    """An effect object from its M (model) and A (animation bank) files."""
    toff, _rel, count = struct.unpack_from('<3I', model, 0)
    t = struct.unpack_from(f'<{count * 4}i', model, 12)
    verts, _norms, polys, depth = (t[i * count:(i + 1) * count] for i in range(4))
    bones, stack = [], []
    for j in range(count):
        del stack[depth[j]:]
        if len(stack) != depth[j]:
            raise ValueError(f'bone {j}: depth jumps')
        bones.append(Bone(stack[-1] if stack else -1, _list(model, verts[j]), _prims(model, polys[j])))
        stack.append(j)
    tables = struct.unpack_from(f'<{count}I', anim, 4)
    first = struct.unpack_from('<I', anim, 4 + 4 * count)[0]
    frames, pos = [], first
    while pos + count < len(anim):
        frames.append(list(anim[pos:pos + count]))
        pos += count
        if anim[pos] in (0xFF, 0xFE):
            break
    used = [sorted({f[b] for f in frames}) for b in range(count)]
    # a bone's keys are read from the start of its table with no bound (tables can overlap), so read the used ones
    keys = [{i: (struct.unpack_from('<9h', anim, start + 0x18 * i), struct.unpack_from('<3h', anim, start + 0x18 * i + 18))
             for i in used[b]} for b, start in enumerate(tables)]
    return Effect(bones, model[toff:], keys, frames, tex_moves(model, count), len(model), len(anim))


def load_effect(disc, model_fid, anim_fid):
    return parse_effect(disc.file(model_fid), disc.file(anim_fid))


def bone_matrix(effect, frame, b):
    """The bone's local transform at a clip frame as (3x3 float rows, translation)."""
    m, t = effect.keys[b][effect.frames[frame][b]]
    return [[m[3 * r + c] / 4096 for c in range(3)] for r in range(3)], list(t)


def world(effect, frame):
    out = []
    for b, bone in enumerate(effect.bones):
        r, t = bone_matrix(effect, frame, b)
        if bone.parent >= 0:
            pr, pt = out[bone.parent]
            r, t = _mul(pr, r), [pt[i] + sum(pr[i][k] * t[k] for k in range(3)) for i in range(3)]
        out.append((r, t))
    return out


def _mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def scale_of(r):
    return max(math.sqrt(sum(r[i][j] ** 2 for i in range(3))) for j in range(3))


def summary(effect):
    """What the object holds and does: sizes, blend modes, texture area, visible frames, travel."""
    prims = [p for b in effect.bones for p in b.prims]
    uvs = [uv for p in prims for uv in p.uvs]
    visible, reach = [], []
    for f in range(len(effect.frames)):
        W = world(effect, f)
        pts = [[t[i] + sum(r[i][k] * v[k] for k in range(3)) for i in range(3)]
               for (r, t), bone in zip(W, effect.bones) if scale_of(r) > 0.01 for v in bone.vertices]
        visible.append(len(pts) > 0)
        reach.append(min((p[2] for p in pts), default=0))
    tim_w, tim_h = tim_size(effect.tim)
    return dict(bones=len(effect.bones), prims=len(prims), triangles=sum(len(p.verts) - 2 for p in prims),
                vertices=sum(len(b.vertices) for b in effect.bones),
                blend=sorted({BLEND_MODES[p.blend] if p.blend is not None else 'opaque' for p in prims}),
                palettes=len({p.clut for p in prims}), texture=f'{tim_w}x{tim_h} 4bpp',
                uv_box=(min(u for u, _ in uvs), min(v for _, v in uvs), max(u for u, _ in uvs), max(v for _, v in uvs)) if uvs else None,
                frames=len(effect.frames), keys=sum(len(k) for k in effect.keys),
                visible_frames=(visible.index(True), len(visible) - 1 - visible[::-1].index(True)) if any(visible) else None,
                forward_reach=-min(reach), tex_moves=len(effect.tex_moves),
                model_bytes=effect.model_size, anim_bytes=effect.anim_size)


def shear(r):
    """How far a bone matrix is from (rotation x per-axis scale), the only form Digimon World's drawTMD
    effect op can draw: the largest off-diagonal cosine between its non-zero columns."""
    cols = [[r[i][j] for i in range(3)] for j in range(3)]
    norms = [math.sqrt(sum(x * x for x in c)) for c in cols]
    live = [(c, n) for c, n in zip(cols, norms) if n > 1e-3]
    worst = 0.0
    for i in range(len(live)):
        for j in range(i + 1, len(live)):
            (a, na), (b, nb) = live[i], live[j]
            worst = max(worst, abs(sum(x * y for x, y in zip(a, b))) / (na * nb))
    return worst


def mirrored(r):
    """True when the live columns turn the wrong way (a negative scale), which the effect op cannot draw.
    A flattened axis (zero column) is completed with the cross product of the other two."""
    cols = [[r[i][j] for i in range(3)] for j in range(3)]
    norms = [math.sqrt(sum(x * x for x in c)) for c in cols]
    if sum(n > 1e-3 for n in norms) < 2:
        return False
    unit = [[x / n for x in c] if n > 1e-3 else None for c, n in zip(cols, norms)]
    for k in range(3):
        if unit[k] is None:
            a, b = unit[(k + 1) % 3], unit[(k + 2) % 3]
            unit[k] = [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]
    a, b, c = unit
    return a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0]) < 0


def uv_blocks(effect):
    """The texture rectangles (u0, v0, u1, v1 inclusive) a converter must copy: the prims' UV boxes merged where
    they overlap, plus every texture-animation frame (a flipbook becomes UV switching, so its frames must be
    resident)."""
    rects = []
    for b in effect.bones:
        for p in b.prims:
            us, vs = [u for u, _ in p.uvs], [v for _, v in p.uvs]
            rects.append([min(us), min(vs), max(us), max(vs)])
    for m in effect.tex_moves:
        w, h = m.size[0] * 4, m.size[1]
        rects += [[x * 4, y, x * 4 + w - 1, y + h - 1] for x, y in m.frames]
    merged = True
    while merged:
        merged = False
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                a, b = rects[i], rects[j]
                if a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]:
                    rects[i] = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]
                    del rects[j]
                    merged = True
                    break
            if merged:
                break
    return sorted(tuple(r) for r in rects)


def shelf_pack(sizes, width=256, height=32):
    """Place (w, h) blocks in a width x height strip, tallest first, each at the lowest spot of the skyline it
    fits. A list of (x, y), or None if they do not fit."""
    sky = [0] * width
    places = {}
    for i in sorted(range(len(sizes)), key=lambda i: (-sizes[i][1], -sizes[i][0])):
        w, h = sizes[i]
        best = min(((max(sky[x:x + w]), x) for x in range(width - w + 1)), default=None)
        if best is None or best[0] + h > height:
            return None
        y, x = best
        sky[x:x + w] = [y + h] * w
        places[i] = (x, y)
    return [places[i] for i in range(len(sizes))]


def texels(effect):
    """The texture area the prims really sample, in texels: the union of their UV boxes."""
    used = set()
    for b in effect.bones:
        for p in b.prims:
            us, vs = [u for u, _ in p.uvs], [v for _, v in p.uvs]
            used.update((u, v) for u in range(min(us), max(us) + 1) for v in range(min(vs), max(vs) + 1))
    return len(used)


EFE_CHUNK = 0x5000                # one Digimon World effect chunk
EFE_SLOT_TEXELS = 256 * 32        # its texture slot in VRAM (4bpp)
EFE_PALETTES = 6                  # its palette rows


def efe_budget(effects):
    """Will these effect objects fit one Digimon World effect chunk? Estimates of what a converter would write:
    a TMD object per drawn bone, one pose record (euler, scale, position: 18 bytes) per distinct pose and a byte
    per bone and frame to pick it."""
    drawn = poses = verts = quads = frames = 0
    worst = 0.0
    flips = 0
    for e in effects:
        seen = set()
        for f in range(len(e.frames)):
            for b, (r, t) in enumerate(world(e, f)):
                if not e.bones[b].prims or scale_of(r) < 0.01:
                    continue
                worst = max(worst, shear(r))
                flips += mirrored(r)
                seen.add((b, tuple(round(x * 4096) for row in r for x in row), tuple(round(x) for x in t)))
        poses += len(seen)
        bones = [b for b in e.bones if b.prims]
        drawn += len(bones)
        verts += sum(len(b.vertices) for b in bones)
        quads += sum(len(b.prims) for b in bones)
        frames += len(e.frames) * len(bones)
    tmd = 12 + 28 * drawn + 16 * verts + 40 * quads
    # plus a 32-byte UV-animation record per TMD object, scripts, variables and the sub-effect table
    resident = tmd + 18 * poses + frames + 32 * drawn + 0x600
    tex = sum(texels(e) for e in effects)
    pals = len({(id(e), p.clut) for e in effects for b in e.bones for p in b.prims})
    chunk = resident + 32 + EFE_SLOT_TEXELS // 2 + 32 * pals     # plus the TIM: header, 4bpp image, palettes
    blocks = [r for e in effects for r in uv_blocks(e)]
    sizes = [(r[2] - r[0] + 1, r[3] - r[1] + 1) for r in blocks]
    packed = shelf_pack(sizes)
    return dict(objects=drawn, poses=poses, worst_shear=round(worst, 4), mirrored_poses=flips, tmd_bytes=tmd,
                resident_bytes=resident, chunk_bytes=chunk, texels=tex, palettes=pals,
                tex_moves=sum(len(e.tex_moves) for e in effects), texture_blocks=sizes,
                fits=dict(chunk=chunk <= EFE_CHUNK, texture=packed is not None, palettes=pals <= EFE_PALETTES,
                          pose=worst < 0.01 and flips == 0))


# ----------------------------------------------------------------- texture

def tim_size(tim):
    flags = struct.unpack_from('<I', tim, 4)[0]
    p = 8 + (struct.unpack_from('<I', tim, 8)[0] if flags & 8 else 0)
    _size, _x, _y, w, h = struct.unpack_from('<I4H', tim, p)
    return w * 4, h


def tim_halfwords(tim):
    """The 4bpp image as rows of halfwords (the palettes live inside it: row << 6 | x / 16)."""
    flags = struct.unpack_from('<I', tim, 4)[0]
    p = 8 + (struct.unpack_from('<I', tim, 8)[0] if flags & 8 else 0)
    _size, _x, _y, w, h = struct.unpack_from('<I4H', tim, p)
    flat = struct.unpack_from(f'<{w * h}H', tim, p + 12)
    return [list(flat[r * w:(r + 1) * w]) for r in range(h)]


def animate_texture(image, moves, tick):
    """The image after this tick's texture-animation copies."""
    out = [row[:] for row in image]
    for m in moves:
        if m.period:
            f = ((tick % m.period) >> 1) % len(m.frames)
        else:
            f = (tick % 24) // 8
        sx, sy = m.frames[f]
        w, h = m.size
        block = [image[sy + y][sx:sx + w] for y in range(h) if sy + y < len(image)]
        for y, row in enumerate(block):
            if m.dst[1] + y < len(out):
                out[m.dst[1] + y][m.dst[0]:m.dst[0] + len(row)] = row
    return out


def texel(image, clut, u, v):
    """The 15-bit colour of texel (u, v) with the prim's palette."""
    row = image[v % len(image)]
    idx = (row[(u >> 2) % len(row)] >> (4 * (u & 3))) & 0xF
    pal = image[(clut >> 6) % len(image)]
    return pal[((clut & 0x3F) * 16 + idx) % len(pal)]


# ----------------------------------------------------------------- render

@dataclass
class Placed:
    """An effect object put in the battle: where (caster space, -z = toward the target) and how it is turned."""
    effect: Effect
    origin: tuple
    turn: bool          # True: faces back toward the caster (hit objects at the target)
    start: int          # first tick (60 Hz) of its life
    ticks: int          # how long it lives


def stage_objects(tables, skill, caster, target=None):
    """The skill's effect objects placed as DW2's fighter places them (Stg30_SpawnSkillCastFx / HitFx)."""
    disc = tables.disc
    out = []
    target = target or caster
    row = caster.cast_rows[skill.cast]
    for i, (m, a) in enumerate(skill.cast_fx):
        if m:
            origin = [(0, -0x280 - caster.head, 0), (row[0], -row[1], -(0x100 + row[2])), (0, 0, 0)][i]
            out.append(Placed(load_effect(disc, m, a), origin, False, 0, CAST_TICKS))
    for i, (m, a) in enumerate(skill.hit_fx):
        if m:
            origin = [(0, -0x280 - target.head, 0), (0, -target.hit_y, 0), (0, 0, 0)][i]
            origin = (-origin[0], origin[1], -HOME_DISTANCE - origin[2])
            out.append(Placed(load_effect(disc, m, a), origin, True, CAST_WAIT, HIT_TICKS))
    return out


class Camera:
    """A fixed pinhole camera: from the side of the line between the two fighters, a little above."""

    def __init__(self, width, height, eye=(14000, -4200, -5120), look=(0, -1400, -5120), fov=0.95):
        self.w, self.h = width, height
        self.eye = eye
        f = [look[i] - eye[i] for i in range(3)]
        n = math.sqrt(sum(x * x for x in f))
        self.f = [x / n for x in f]
        up = (0, -1, 0)
        r = [self.f[1] * up[2] - self.f[2] * up[1], self.f[2] * up[0] - self.f[0] * up[2], self.f[0] * up[1] - self.f[1] * up[0]]
        n = math.sqrt(sum(x * x for x in r))
        self.r = [x / n for x in r]
        self.u = [self.r[1] * self.f[2] - self.r[2] * self.f[1], self.r[2] * self.f[0] - self.r[0] * self.f[2],
                  self.r[0] * self.f[1] - self.r[1] * self.f[0]]
        self.focal = width / 2 / math.tan(fov / 2)

    def project(self, p):
        d = [p[i] - self.eye[i] for i in range(3)]
        z = sum(d[i] * self.f[i] for i in range(3))
        if z < 10:
            return None
        x = sum(d[i] * self.r[i] for i in range(3))
        y = sum(d[i] * self.u[i] for i in range(3))
        return (self.w / 2 + self.focal * x / z, self.h / 2 - self.focal * y / z, z)


def _blend(dst, src, mode):
    if mode == 0:
        return tuple((a + b) // 2 for a, b in zip(dst, src))
    if mode == 1:
        return tuple(min(255, a + b) for a, b in zip(dst, src))
    if mode == 2:
        return tuple(max(0, a - b) for a, b in zip(dst, src))
    return tuple(min(255, a + b // 4) for a, b in zip(dst, src))


def _rgb(c):
    return ((c & 0x1F) * 255 // 31, ((c >> 5) & 0x1F) * 255 // 31, ((c >> 10) & 0x1F) * 255 // 31)


def render_tick(objects, tick, cam, bg=(28, 30, 40), markers=True):
    """One 60 Hz tick of the skill: every live object's triangles, painter-sorted like an ordering table, with
    the PlayStation's semi-transparency (only texels with the STP bit blend; colour 0 is transparent)."""
    W, H = cam.w, cam.h
    px = [bg] * (W * H)
    if markers:                      # the ground line and the two fighters' home points
        for z in range(-HOME_DISTANCE - 1500, 1501, 40):
            p = cam.project((0, 0, z))
            if p and 0 <= int(p[0]) < W and 0 <= int(p[1]) < H:
                px[int(p[1]) * W + int(p[0])] = (70, 74, 90)
        for z in (0, -HOME_DISTANCE):
            for y in range(0, -1800, -30):
                p = cam.project((0, y, z))
                if p and 0 <= int(p[0]) < W and 0 <= int(p[1]) < H:
                    px[int(p[1]) * W + int(p[0])] = (110, 110, 130)
    tris = []
    for ob in objects:
        age = tick - ob.start
        if age < 0 or age >= ob.ticks:
            continue
        e = ob.effect
        frame = min(age // 2, len(e.frames) - 1)
        image = animate_texture(e._image, e.tex_moves, age) if e.tex_moves else e._image
        for (r, t), bone in zip(world(e, frame), e.bones):
            if scale_of(r) < 1e-3 or not bone.vertices:
                continue
            pts = []
            for v in bone.vertices:
                p = [t[i] + sum(r[i][k] * v[k] for k in range(3)) for i in range(3)]
                if ob.turn:
                    p = [-p[0], p[1], -p[2]]
                pts.append(cam.project([p[i] + ob.origin[i] for i in range(3)]))
            for prim in bone.prims:
                for tri in ([(0, 1, 2)] if len(prim.verts) == 3 else [(0, 1, 2), (1, 3, 2)]):
                    q = [pts[prim.verts[i]] if prim.verts[i] < len(pts) else None for i in tri]
                    if None in q:
                        continue
                    tris.append((sum(x[2] for x in q) / 3, q, [prim.uvs[i] for i in tri], prim, image))
    tris.sort(key=lambda x: -x[0])
    for _z, q, uv, prim, image in tris:
        _raster(px, W, H, q, uv, prim, image)
    return px


def _raster(px, W, H, q, uv, prim, image):
    (x0, y0, _), (x1, y1, _), (x2, y2, _) = q
    area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
    if abs(area) < 1e-6:
        return
    lo_x, hi_x = max(int(min(x0, x1, x2)), 0), min(int(max(x0, x1, x2)) + 1, W)
    lo_y, hi_y = max(int(min(y0, y1, y2)), 0), min(int(max(y0, y1, y2)) + 1, H)
    for y in range(lo_y, hi_y):
        cy = y + 0.5
        for x in range(lo_x, hi_x):
            cx = x + 0.5
            w0 = ((x1 - cx) * (y2 - cy) - (x2 - cx) * (y1 - cy)) / area
            w1 = ((x2 - cx) * (y0 - cy) - (x0 - cx) * (y2 - cy)) / area
            w2 = 1 - w0 - w1
            if w0 < 0 or w1 < 0 or w2 < 0:
                continue
            u = int(w0 * uv[0][0] + w1 * uv[1][0] + w2 * uv[2][0])
            v = int(w0 * uv[0][1] + w1 * uv[1][1] + w2 * uv[2][1])
            c = texel(image, prim.clut, u, v)
            if c == 0:
                continue
            i = y * W + x
            if prim.blend is not None and c & 0x8000:
                px[i] = _blend(px[i], _rgb(c), prim.blend)
            else:
                px[i] = _rgb(c)


def prepare(objects):
    for ob in objects:
        if not hasattr(ob.effect, '_image'):
            ob.effect._image = tim_halfwords(ob.effect.tim)
    return objects


def contact_sheet(objects, ticks, width=320, height=180, cols=6):
    """The chosen ticks side by side, as an RGB image."""
    from tools import image as img
    cam = Camera(width, height)
    rows = (len(ticks) + cols - 1) // cols
    sheet = img.new('RGB', (cols * width, rows * height), (0, 0, 0))
    for n, tick in enumerate(ticks):
        px = render_tick(objects, tick, cam)
        tile = img.frombytes('RGB', (width, height), bytes(c for p in px for c in p))
        sheet.paste(tile, ((n % cols) * width, (n // cols) * height))
    return sheet


# ----------------------------------------------------------------- CLI

def _disc(a):
    path = a.disc or os.environ.get('DW2_IMAGE')
    if not path:
        raise SystemExit('give the Digimon World 2 (USA) disc image with --disc or DW2_IMAGE')
    return Disc(path)


def describe_skill(tables, s):
    disc = tables.disc
    users = [d.name for d in tables.digimon.values() if d.learned == s.id]
    lines = [f'skill {s.id} {s.name}: power {s.power}, MP {s.mp}, target {TARGETS.get(s.target, s.target)}, '
             f'caster clip {CAST_ANIM_BANK[s.cast]}0, voice XA file {s.xa[0]} channel {s.xa[1]}, learned by {", ".join(users) or "-"}']
    for stage, fx in (('cast', s.cast_fx), ('hit', s.hit_fx)):
        for slot, (m, a) in enumerate(fx):
            if m:
                lines.append(f'  {stage} slot {slot}: model {m} {disc.name(m)}  anim {a} {disc.name(a)}')
    return '\n'.join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--disc')
    sub = p.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('skill')
    s.add_argument('key')
    s = sub.add_parser('digimon')
    s.add_argument('key')
    s = sub.add_parser('info')
    s.add_argument('model', type=int)
    s.add_argument('anim', type=int)
    s = sub.add_parser('budget', help="will the skill's effect objects fit one Digimon World effect chunk")
    s.add_argument('skill')
    s = sub.add_parser('render')
    s.add_argument('skill')
    s.add_argument('--caster', required=True)
    s.add_argument('--target')
    s.add_argument('--out', required=True)
    s.add_argument('--step', type=int, default=12, help='ticks between images (default 12)')
    a = p.parse_args(argv)
    disc = _disc(a)
    if a.cmd == 'info':
        for k, v in summary(load_effect(disc, a.model, a.anim)).items():
            print(f'{k}: {v}')
        return
    tables = Tables(disc)
    if a.cmd == 'skill':
        print(describe_skill(tables, tables.skill(a.key)))
    elif a.cmd == 'budget':
        skill = tables.skill(a.skill)
        effects = [load_effect(disc, m, an) for m, an in skill.cast_fx + skill.hit_fx if m]
        for k, v in efe_budget(effects).items():
            print(f'{k}: {v}')
    elif a.cmd == 'digimon':
        d = tables.digi(a.key)
        print(f'{d.id} {d.name}: model {disc.name(d.model)}, head {d.head}, hit point y {d.hit_y}, launch points {d.cast_rows}')
        if d.learned:
            print(describe_skill(tables, tables.skills[d.learned]))
    elif a.cmd == 'render':
        skill = tables.skill(a.skill)
        objects = prepare(stage_objects(tables, skill, tables.digi(a.caster), tables.digi(a.target) if a.target else None))
        end = max(o.start + o.ticks for o in objects)
        ticks = list(range(0, end, a.step))
        contact_sheet(objects, ticks).save(a.out)
        print(f'{a.out}: {len(ticks)} images, ticks 0..{ticks[-1]} every {a.step} (cast at 0, hit at {CAST_WAIT})')


if __name__ == '__main__':
    main()
