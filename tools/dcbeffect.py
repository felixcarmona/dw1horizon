#!/usr/bin/env python3
"""Digimon Digital Card Battle technique effects: read, trace, render and hand them to the effect converter.

A Card Battle attack is a script (an "MSCD" record inside the attacking card's battle model, F.DRV) that
places and moves effect objects, plus a resource pack of its own (E.DRV/<attack id>.PAK: small 3D models,
their animations, sprite sheets as TIMs). The card's "extra" effect is a second script and pack, shared by
many cards, which plays on the defender. The formats are written down in docs/reference/dcb-effects.md.

This module:
- reads the packs (`read_pack`) and the scripts (`decode`);
- runs a script the way the battle's technique player does (`trace`): every effect object with its kind,
  its parameters and its motion over time;
- turns a traced script into a `tools.dw2effect.Effect` (`to_effect`), the in-memory form the Digimon World
  effect converter (`tools/dw2efe.py`) and the offline renderer already use: 3D models keep their meshes and
  textures, sprites become flat textured quads facing the battle camera.

Nothing from the disc is stored in the repository: everything is read from the player's own disc image.

Usage (from the repository root):
  python3 tools/dcbeffect.py --disc DCB.bin list WarGreymon         the card's attacks and their packs
  python3 tools/dcbeffect.py --disc DCB.bin script 1105               the decoded script
  python3 tools/dcbeffect.py --disc DCB.bin trace 1105                the effect objects over time
  python3 tools/dcbeffect.py --disc DCB.bin sheet 1105 --extra 435 --out sheet.png
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

from tools import dw2effect as D                                    # noqa: E402

TICK_HZ = 30                 # one technique-player step per frame (assumed 30 per second, like the models)
UNITS = 2.048                # Card Battle world units -> Digimon World 2 effect units (10240 / 5000 between rows)
SPRITE_UNIT = 16             # world units per sprite texel at scale 1.0 (calibrated by eye against the models)
NVARS = 460

# ---------------------------------------------------------------- disc

def drv(image, name):
    """{path inside the DRV: bytes} of one of the disc's DRV archives (F.DRV, E.DRV, ...)."""
    from tools.derive.importers.discs import Image, drv_files
    img = Image(image)
    try:
        files = img.index()
        if name not in files:
            raise SystemExit(f'{image}: no {name}')
        data = img.read(*files[name])
    finally:
        img.file.close()
    return dict(drv_files(data))


class Disc:
    """The Card Battle disc's battle models (F.DRV) and effect packs (E.DRV)."""

    def __init__(self, image=None, f=None, e=None):
        self.f = f if f is not None else {k.split('/')[-1]: v for k, v in drv(image, 'F.DRV').items()}
        self.e = e if e is not None else {k: v for k, v in drv(image, 'E.DRV').items()}
        self._scripts = None

    @classmethod
    def extracted(cls, games):
        """The disc as the build extracts it (`games`: source-games/dcb, with drv/F and drv/E)."""
        def folder(name):
            d = os.path.join(games, 'drv', name)
            if not os.path.isdir(d):
                raise FileNotFoundError(d)
            out = {}
            for n in sorted(os.listdir(d)):
                with open(os.path.join(d, n), 'rb') as fh:
                    out[n] = fh.read()
            return out
        return cls(f=folder('F'), e=folder('E'))

    def pack(self, pid):
        data = self.e.get(f'{pid}.PAK')
        return read_pack(data) if data and len(data) > 8 else Pack()

    def scripts(self):
        """{script id: MSCD bytes} from every battle model (the first copy of each id)."""
        if self._scripts is None:
            self._scripts = {}
            for name in sorted(self.f):
                for typ, rid, data in records(self.f[name]):
                    if typ == 2 and data[:4] == b'MSCD':
                        self._scripts.setdefault(rid, data)
        return self._scripts


# ---------------------------------------------------------------- packs

def records(d):
    """The (type, id, data) records of a battle model or effect pack."""
    if len(d) < 0x1c:
        return []
    rec = struct.unpack_from('<I', d, 4)[0] + 8
    out, p = [], rec
    while 0 < p and p + 8 <= len(d):
        typ, rid, size = struct.unpack_from('<hHI', d, p)
        if typ < 0 or p + 8 + size > len(d):
            break
        out.append((typ, rid, d[p + 8:p + 8 + size]))
        p += 8 + size
    return out


@dataclass
class Tim:
    """A 4bpp (or 8bpp) TIM: where it sits in VRAM, its palette rows and its image as rows of halfwords."""
    id: int
    bpp: int
    clut_xy: tuple
    clut: list               # rows of 16-bit colours
    xy: tuple
    words: list              # rows of halfwords


def parse_tim(d, tid=0):
    from tools.derive.importers.vendor.dcb.unpack import unpack
    if d[:4] != b'\x10\0\0\0':
        d = unpack(d)
    flags = struct.unpack_from('<I', d, 4)[0]
    q, clut_xy, clut = 8, (0, 0), []
    if flags & 8:
        size, x, y, w, h = struct.unpack_from('<I4H', d, q)
        clut_xy = (x, y)
        flat = struct.unpack_from(f'<{w * h}H', d, q + 12)
        clut = [list(flat[r * w:(r + 1) * w]) for r in range(h)]
        q += size
    size, x, y, w, h = struct.unpack_from('<I4H', d, q)
    flat = struct.unpack_from(f'<{w * h}H', d, q + 12)
    return Tim(tid, (4, 8, 16, 24)[flags & 3], clut_xy, clut, (x, y), [list(flat[r * w:(r + 1) * w]) for r in range(h)])


@dataclass
class Model:
    """An effect model: bones with their meshes (tools/derive/importers/vendor/dcb), its texture id."""
    id: int
    model: object
    texture: int
    anim: bytes = None


@dataclass
class Pack:
    id: int = 0
    models: dict = field(default_factory=dict)      # id -> Model
    tims: dict = field(default_factory=dict)        # id -> Tim
    sprites: dict = field(default_factory=dict)     # id -> raw sprite definition (record type 3)
    anims: dict = field(default_factory=dict)       # id -> raw animation (record type 1)


def _model(d, mid):
    from tools.derive.importers.vendor.dcb.model import parse_model
    m = parse_model(d, str(mid))
    stem = m.texture_name.split('.')[0]
    tex = int(stem.replace('_', '')) if stem.replace('_', '').isdigit() else -1
    return Model(mid, m, tex)


def read_pack(d):
    """An effect pack: a model file (its own model first) whose records add more models (type 0, the model file
    without its 8-byte header), animations (1), sprite definitions (3) and TIMs (5). Packs without a model of
    their own start straight with the record list."""
    from tools.derive.importers.vendor.dcb.model import unpacked_animation
    typ, pid = struct.unpack_from('<HH', d, 0)
    pack = Pack(pid)
    if typ == 0 and d[8:24].split(b'\0')[0].endswith(b'.tim'):
        pack.models[pid] = _model(d, pid)
        recs = records(d)
    else:
        recs = records(d)
    for t, rid, data in recs:
        if t == 0:
            hdr = struct.pack('<HHI', 0, rid, 0)
            try:
                body = hdr + data
                # the record list offset is relative to the model's own start
                body = body[:4] + struct.pack('<I', _records_at(body) - 8) + body[8:]
                pack.models[rid] = _model(body, rid)
            except (ValueError, struct.error, IndexError):
                pass
        elif t == 1:
            pack.anims[rid] = unpacked_animation(data)
        elif t == 3:
            pack.sprites[rid] = data
        elif t == 5:
            pack.tims[rid] = parse_tim(data, rid)
    for m in pack.models.values():
        m.anim = pack.anims.get(m.id)
    return pack


def _records_at(d):
    """Where a header-less model's record list starts: after its bones' meshes."""
    from tools.derive.importers.vendor.dcb.mesh import parse_object
    nb = struct.unpack_from('<I', d, 0x18)[0]
    p = 0x3c + 12 * nb
    for _ in range(nb):
        _mesh, p = parse_object(d, p)
    return p


# ---------------------------------------------------------------- scripts

OP_NAMES = {5: 'jmp', 6: 'blk', 7: 'set', 8: 'data', 9: 'skip'}
SET_OPS = ('=', '+=', '-=', '*=', '/=', '%=', 'rnd')
# op 9 skips the next instruction when the comparison holds (the interpreter, SLUS_013.28 0x80020f54)
CMP_OPS = ('==', '<=', '>=', '!=', '>', '<')


@dataclass
class Ins:
    at: int                  # byte offset in the script
    op: str                  # jmp blk set data skip cmdA..cmdE
    a: int = 0               # the variable, or the command number
    args: tuple = ()


def decode(r):
    """The instructions of an MSCD script: 'MSCD', u32 3, u32 size, u32 variable count, then 4-aligned
    instructions, each starting u16 op, u16 a."""
    out, p, n = [], 16, len(r)
    while p + 4 <= n:
        op, a = struct.unpack_from('<HH', r, p)
        if op == 5:
            out.append(Ins(p, 'jmp', 0, (struct.unpack_from('<I', r, p + 4)[0],)))      # to 16 + target
            q = p + 8
        elif op == 6:
            out.append(Ins(p, 'blk', a, (r[p + 4:p + 4 + a],)))
            q = p + 4 + a
        elif op in (7, 9):
            sub, mode, val = struct.unpack_from('<HHi', r, p + 4)
            out.append(Ins(p, 'set' if op == 7 else 'skip', a, (sub, bool(mode), val)))
            q = p + 12
        elif op == 8:
            ln = struct.unpack_from('<H', r, p + 4)[0]
            out.append(Ins(p, 'data', a, (r[p + 6:p + 6 + ln],)))
            q = p + 6 + ln
        elif 0xa <= op <= 0xe:
            k = op - 0xa
            args = []
            for i in range(k):
                isv, v = struct.unpack_from('<Hh', r, p + 4 + 4 * i)
                args.append(('var', v & 0xffff) if isv else v)
            out.append(Ins(p, 'cmd' + 'ABCDE'[k], a, tuple(args)))
            q = p + 4 + 4 * k
        else:
            raise ValueError(f'MSCD: unknown op {op} at {p:#x}')
        p = (q + 3) & ~3
    return out


def listing(r):
    lines = []
    for i in decode(r):
        if i.op in ('set', 'skip'):
            sub, isv, val = i.args
            opn = (SET_OPS if i.op == 'set' else CMP_OPS)[sub] if sub < 7 else str(sub)
            lines.append(f'{i.at:5d}  {i.op:4s} v{i.a} {opn} {"v%d" % val if isv else val}')
        elif i.op == 'jmp':
            lines.append(f'{i.at:5d}  jmp {i.args[0] + 16}')
        elif i.op.startswith('cmd'):
            a = ' '.join(f'v{x[1]}' if isinstance(x, tuple) else str(x) for x in i.args)
            lines.append(f'{i.at:5d}  {i.op} {i.a} {a}  {COMMANDS.get((i.op, i.a), "")}')
        else:
            lines.append(f'{i.at:5d}  {i.op} {i.a} ({len(i.args[0])} bytes)')
    return '\n'.join(lines)


COMMANDS = {
    ('cmdB', 0): 'show the attack-name banner (TIM id)',
    ('cmdB', 2): 'play an animation of the attacker',
    ('cmdB', 3): 'sound',
    ('cmdB', 6): 'apply the variables to object N again (new motion from now)',
    ('cmdB', 8): 'start object N',
    ('cmdB', 9): 'stop object N',
    ('cmdB', 10): 'wait N steps',
    ('cmdB', 15): 'load object N parameters into the variables',
    ('cmdB', 16): 'the script\'s own id',
    ('cmdC', 0): 'define object N of a kind from the variables',
    ('cmdC', 1): 'set the motion type of object N',
    ('cmdD', 0): 'load a sprite sheet (TIM and sprite definition) into VRAM',
}

# object parameters: variable numbers (the constructor copies them, SUGSEG 0x801e92b0)
V_START, V_END, V_SPEED, V_ACCEL = 407, 410, 413, 414
V_ROT, V_ROTV, V_ROTA = 415, 418, 421
V_SCALE, V_SCALE_END, V_SCALE_V = 424, 427, 430
V_RADIUS, V_DELAY, V_MOTION = 433, 434, 437
V_PHASE, V_AMP, V_FREQ = 438, 439, 440
V_ATTACH_BONE, V_MODEL, V_ATTACH_TO = 441, 442, 446
V_RGB, V_TP, V_SEMI, V_ABR = 41, 28, 29, 30
V_RECT, V_CLUT = 84, 88

# the motion type's update (the executable's table at 0x800108b0): S still, L straight line with
# acceleration, A line plus a vertical arc, W line plus a sideways wave, V line plus a vertical wave,
# T line plus an arc turned by the object's z angle, U line plus an accelerated turned arc,
# X and N not modelled (held still), H held
MOTION = 'SLAWVTNUXHHLLLAAAWWWVVVTTTUUULLLAAAWWWVVVTTTUUUSSSLAWVTUSLAWVTULAWVTUSLAWVTULAWVTUSLAWVTUXS'
# what a moving object does when it reaches its end point: for types 11-28, by (type - 11) % 3
ARRIVE = ('stop', 'snap', 'end')

MODEL_KINDS = {15}
FLIPBOOK_KIND = 16
SPRITE_KINDS = {1, 12, 13}
KIND_NAMES = {0: 'screen flash', 1: 'sprite', 3: 'camera', 10: 'sprite trail', 12: 'shaded sprite',
              13: 'sprite burst', 14: 'light', 15: 'model', 16: 'flipbook', 17: 'ribbon',
              19: 'afterimage', 21: 'afterimage'}


@dataclass
class Segment:
    t0: int                  # step the parameters took effect
    p: list                  # the variables at that moment


@dataclass
class Instance:
    slot: int
    kind: int
    segments: list
    start: int
    end: int = None          # step it was stopped (None: until the script ends)

    def params(self, t):
        seg = self.segments[0]
        for s in self.segments:
            if s.t0 <= t:
                seg = s
        return seg


@dataclass
class Trace:
    sid: int
    instances: list
    events: list             # (step, command, args)
    loads: list              # (resource id, x slot, y slot) sprite sheets loaded into VRAM
    length: int


def trace(script, sid=0, max_steps=1200, budget=20000):
    """Run a technique script: the objects it defines and starts, and when."""
    code = decode(script)
    at = {i.at: n for n, i in enumerate(code)}
    v = [0] * max(NVARS, struct.unpack_from('<I', script, 12)[0] + 1)
    defs, running, done, events, loads = {}, {}, [], [], []
    pc, step, skip, steps_budget = 0, 0, False, budget

    def val(x):
        return v[x[1]] if isinstance(x, tuple) else x

    def i16(x):
        return ((x + 0x8000) & 0xffff) - 0x8000

    while pc < len(code) and step < max_steps and steps_budget > 0:
        steps_budget -= 1
        ins = code[pc]
        pc += 1
        if skip:
            skip = False
            continue
        if ins.op == 'jmp':
            pc = at.get(ins.args[0] + 16, len(code))      # targets count from the code, after the header
        elif ins.op == 'set':
            sub, isv, x = ins.args
            x = v[x] if isv else x
            cur = v[ins.a]
            if sub == 0:
                cur = x
            elif sub == 1:
                cur += x
            elif sub == 2:
                cur -= x
            elif sub == 3:
                cur *= x
            elif sub == 4:
                cur = int(cur / x) if x else cur
            elif sub == 5:
                cur = int(math.fmod(cur, x)) if x else cur
            elif sub == 6:
                cur = (step * 1103515245 + 12345 + ins.at) % max(1, x)   # a fixed stand-in for rand() % x
            v[ins.a] = cur
        elif ins.op == 'skip':
            sub, isv, x = ins.args
            x = v[x] if isv else x
            a = v[ins.a]
            skip = (a == x, a <= x, a >= x, a != x, a > x, a < x)[sub] if sub < 6 else False
        elif ins.op == 'cmdB':
            n = val(ins.args[0]) if ins.args else 0
            if ins.a == 10:
                if v[0] == -1 and n > 0:
                    step += n
            elif ins.a == 8 and n in defs:
                kind, p = defs[n]
                if n in running:
                    running[n].end = step
                    done.append(running.pop(n))
                running[n] = Instance(n, kind, [Segment(step, p)], step)
            elif ins.a == 9 and n in running:
                running[n].end = step
                done.append(running.pop(n))
            elif ins.a == 15 and n in defs:
                p = defs[n][1]
                v[400:454] = p[400:454]
            elif ins.a == 6 and n in defs:
                p = list(v)
                defs[n] = (defs[n][0], p)
                if n in running:
                    running[n].segments.append(Segment(step, p))
            else:
                events.append((step, ins.a, tuple(val(x) for x in ins.args)))
        elif ins.op == 'cmdC':
            args = [val(x) for x in ins.args]
            if ins.a == 0 and len(args) >= 2:
                defs[args[0]] = (args[1], list(v))
            elif ins.a == 1 and len(args) >= 2 and args[0] in defs:
                defs[args[0]][1][V_MOTION] = args[1]
            elif ins.a == 2 and len(args) >= 2:
                v[1] = int(math.atan2(args[1], args[0]) * 2048 / math.pi) & 0xfff
            elif ins.a in (3, 4) and len(args) >= 2:
                f = math.sin if ins.a == 3 else math.cos
                v[1] = int(f(args[0] * math.pi / 2048) * 4096) * args[1] >> 12
        elif ins.op == 'cmdD':
            args = [val(x) for x in ins.args]
            if ins.a == 0 and args:
                loads.append(tuple(args + [0, 0])[:3])
        elif ins.op in ('cmdA', 'cmdE'):
            events.append((step, ins.op + str(ins.a), tuple(val(x) for x in ins.args)))
    for inst in running.values():
        inst.end = step
        done.append(inst)
    done.sort(key=lambda i: (i.start, i.slot))
    return Trace(sid, done, events, loads, step)


def _rsin(a):
    return math.sin(a * math.pi / 2048)


def motion_at(p, t):
    """(position, angles, scale, ended) of an object `t` steps after its parameters took effect (the
    executable's object update, 0x80030f90)."""
    start = [p[V_START + i] for i in range(3)]
    end = [p[V_END + i] for i in range(3)]
    speed, accel = p[V_SPEED], p[V_ACCEL]
    mtype = p[V_MOTION]
    cls = MOTION[mtype] if 0 <= mtype < len(MOTION) else 'S'
    vec = [e - s for e, s in zip(end, start)]
    dist = math.sqrt(sum(x * x for x in vec))
    unit = [x / dist for x in vec] if dist else [0, 0, 0]
    ended = False

    def along(tt):
        return speed * tt + accel * tt * tt

    tt = t
    if cls in 'LAWVTU' and dist:
        reach = dist - max(0, p[V_RADIUS])
        if along(t) >= reach and speed + 2 * accel * t > 0:
            # the first step that reaches the end point
            tt = next((k for k in range(t + 1) if along(k) >= reach), t)
            if 11 <= mtype <= 28:
                rule = ARRIVE[(mtype - 11) % 3]
                ended = rule == 'end'
                if rule == 'snap':
                    return end, _angles(p, tt), _scale(p, tt), ended
            else:
                tt = t
    if cls == 'S' or cls in 'NXH':
        pos = list(start)
    else:
        d = along(tt) if cls != 'U' else speed * tt
        pos = [s + d * u for s, u in zip(start, unit)]
        if cls == 'A':
            pos[1] += -speed * tt + speed * tt * tt / 224
        elif cls == 'W':
            pos[0] += _rsin((p[V_PHASE] + speed * tt) * p[V_FREQ]) * p[V_AMP] * 4
        elif cls == 'V':
            pos[1] += _rsin((p[V_PHASE] + speed * tt) * p[V_FREQ]) * p[V_AMP] * 4
        elif cls in 'TU':
            k = accel if cls == 'U' else speed
            h = -speed * tt + k * tt * tt / 224
            rz = p[V_ROT + 2]
            pos[0] -= h * _rsin(rz)
            pos[1] += h * math.cos(rz * math.pi / 2048)
    return pos, _angles(p, tt), _scale(p, t), ended


def _angles(p, t):
    return [p[V_ROT + i] + p[V_ROTV + i] * t + (p[V_ROTA + i] * t * t) / 64 for i in range(3)]


def _scale(p, t):
    out = []
    for i in range(3):
        s0, s1, ds = p[V_SCALE + i], p[V_SCALE_END + i], p[V_SCALE_V + i]
        s = s0 + ds * t
        if ds > 0 and s0 <= s1:
            s = min(s, s1)
        elif ds < 0 and s0 >= s1:
            s = max(s, s1)
        out.append(s / 4096)
    return out


def state(inst, step, by_slot=None):
    """(position, angles, scale) of an instance at a step, or None when it is not shown."""
    if step < inst.start or (inst.end is not None and step >= inst.end):
        return None
    seg = inst.params(step)
    p = seg.p
    t = step - seg.t0
    if seg is inst.segments[0]:
        t -= max(0, p[V_DELAY])
        if t < 0:
            return None
    pos, ang, sc, ended = motion_at(p, t)
    if ended:
        return None
    if p[V_ATTACH_BONE] >= 0 and p[V_ATTACH_TO] == -1 and by_slot:
        parent = by_slot.get(p[V_ATTACH_BONE])
        if parent is not None and parent is not inst:
            ps = state(parent, step)
            if ps is None:
                return None
            pos = [a + b for a, b in zip(pos, ps[0])]
    return pos, ang, sc


# ---------------------------------------------------------------- to an Effect

def _rot(ang):
    """Ry * Rx * Rz from 4096-per-turn angles (x, y, z)."""
    a, b, c = (x * math.pi / 2048 for x in ang)
    return D._mul(D._mul([[math.cos(b), 0, math.sin(b)], [0, 1, 0], [-math.sin(b), 0, math.cos(b)]],
                         [[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]]),
                  [[math.cos(c), -math.sin(c), 0], [math.sin(c), math.cos(c), 0], [0, 0, 1]])


class Atlas:
    """The effect's own texture: every model TIM and sprite rectangle it uses, stacked, with their palettes
    as extra rows (the layout tools/dw2effect.py reads: a prim's clut is row << 6 | x / 16)."""

    def __init__(self, shrink=1):
        self.shrink = shrink # every texture is drawn at 1/shrink of its size (to fit the chunk)
        self.blocks = []     # (rows of halfwords)
        self.pals = []       # 16-colour palettes
        self.where = {}
        self.y = 0

    def image(self, key, rows):
        if key not in self.where:
            self.where[key] = self.y
            rows = list(rows) + [[0] * len(rows[0])] * (-len(rows) % self.shrink) if rows else rows
            self.blocks.append(rows)
            self.y += len(rows)
        return self.where[key]

    def palette(self, colours):
        colours = tuple(colours[:16]) + (0,) * (16 - len(colours[:16]))
        if colours not in self.pals:
            self.pals.append(colours)
        return self.pals.index(colours)

    def tim(self):
        width = max([16] + [len(r[0]) for r in self.blocks if r])
        rows = [list(r) + [0] * (width - len(r)) for b in self.blocks for r in b]
        if self.shrink > 1:
            rows = [_shrink_row(r, self.shrink) for r in rows[::self.shrink]]
            width = max(16, len(rows[0]) if rows else 16)
            rows = [r + [0] * (width - len(r)) for r in rows]
        self.pal_row = len(rows)
        for p in self.pals:
            rows.append(list(p) + [0] * (width - 16))
        if not rows:
            rows = [[0] * width]
        flat = [x for r in rows for x in r]
        h = len(rows)
        return struct.pack('<II', 0x10, 0) + struct.pack('<I4H', 12 + 2 * len(flat), 0, 0, width, h) + \
            struct.pack(f'<{len(flat)}H', *flat)

    def clut(self, pal):
        return (self.pal_row_of(pal) << 6)

    def pal_row_of(self, pal):
        return sum(len(b) for b in self.blocks) // self.shrink + pal

    def uv(self, uvs):
        s = self.shrink
        return tuple((u // s, v // s) for u, v in uvs)


def _shrink_row(row, s):
    """Every s-th 4-bit texel of a row of halfwords, packed again."""
    tex = [(w >> (4 * k)) & 15 for w in row for k in range(4)][::s]
    tex += [0] * (-len(tex) % 4)
    return [tex[i] | tex[i + 1] << 4 | tex[i + 2] << 8 | tex[i + 3] << 12 for i in range(0, len(tex), 4)]


class Vram:
    """Halfword VRAM for the sprite sheets: the packs' TIMs where the script loads them."""

    def __init__(self):
        self.w = {}

    def put(self, tim, dx=0, dy=0):
        x, y = tim.xy
        for r, row in enumerate(tim.words):
            for c, hw in enumerate(row):
                self.w[(x + dx + c, y + dy + r)] = hw
        if tim.clut:
            cx, cy = tim.clut_xy
            for r, row in enumerate(tim.clut):
                for c, hw in enumerate(row):
                    self.w[(cx + c, cy + dy + r)] = hw

    def rect(self, x, y, w, h):
        return [[self.w.get((x + c, y + r), 0) for c in range(w)] for r in range(h)]


@dataclass
class Drawn:
    """Which instances an Effect drew, and how (for the fidelity notes)."""
    models: int = 0
    sprites: int = 0
    dropped: dict = field(default_factory=dict)      # kind name -> count
    notes: list = field(default_factory=list)


def _model_for(packs, mid):
    for pk in packs:
        if mid in pk.models:
            return pk.models[mid], pk
    return None, None


def _model_frames(m):
    """Per frame, per bone 4x4 world matrices of an effect model (its own animation looped, else rest)."""
    from tools.derive.importers.vendor.dcb import pose
    from tools.derive import dcbplayer
    nb = len(m.model.bones)
    frames = []
    if m.anim:
        try:
            fr, _ev, _loop = dcbplayer.play(m.anim, nb)
            for f in range(fr.shape[0]):
                frames.append([_plain(x) for x in pose.world_matrices(m.model, fr[f])])
        except Exception:                      # noqa: BLE001 - a broken clip: keep the rest pose
            frames = []
    if not frames:
        frames = [[_plain(x) for x in pose.world_matrices(m.model, None)]]
    return frames


def _plain(m4):
    return ([[float(m4[i, j]) for j in range(3)] for i in range(3)], [float(m4[i, 3]) for i in range(3)])


def to_effect(tr, packs, steps, origin=(0, 0, 0), turn=False, vram_tims=(), notes=None, max_flip=4, shrink=1,
              max_objects=None):
    """A dw2effect.Effect (in Digimon World 2 effect units, one frame per step) that draws the traced objects at
    the chosen steps. origin: subtracted from every position (the defender's place for a hit); turn: face the
    other way (a hit object faces the attacker)."""
    drawn = notes if notes is not None else Drawn()
    atlas = Atlas(shrink)
    vram = Vram()
    for t in vram_tims:
        vram.put(*t)
    bones, keys, per_bone_pose = [], [], []
    by_slot = {}
    for inst in tr.instances:
        by_slot.setdefault(inst.slot, inst)
    cache = {}
    for inst in thin(tr.instances, max_objects, drawn):
        p0 = inst.segments[0].p
        as_model = inst.kind in MODEL_KINDS or (inst.kind in SPRITE_KINDS and _model_for(packs, p0[V_MODEL])[0])
        glow = inst.kind in SPRITE_KINDS and p0[V_SEMI]
        if as_model:
            m, pk = _model_for(packs, p0[V_MODEL])
            if m is None:
                drawn.dropped[f'model {p0[V_MODEL]} missing'] = drawn.dropped.get(f'model {p0[V_MODEL]} missing', 0) + 1
                continue
            if m.id not in cache:
                cache[m.id] = _model_frames(m)
            mframes = cache[m.id]
            tim = next((p.tims[m.texture] for p in packs if m.texture in p.tims), None)
            first = len(bones)
            for b in m.model.bones:
                verts = [tuple(round(c * UNITS) for c in v) for v in b.mesh.vertices] if b.mesh else []
                prims = []
                for pr in (b.mesh.prims if b.mesh else []):
                    if not pr.uvs or tim is None:
                        continue
                    from tools.derive.importers.vendor.dcb.vram import page_origin
                    px, py, bpp = page_origin(pr.tpage)
                    if bpp != 4:
                        continue
                    y0 = atlas.image(('tim', tim.id), tim.words)
                    du = (px - tim.xy[0]) * 4
                    dv = py - tim.xy[1]
                    uvs = tuple((u + du, v + dv + y0) for u, v in pr.uvs)
                    crow = pr.clut[1] - tim.clut_xy[1]
                    cx = (pr.clut[0] - tim.clut_xy[0])
                    pal = tim.clut[crow][cx:cx + 16] if 0 <= crow < len(tim.clut) else [0] * 16
                    blend = ((pr.tpage >> 5) & 3) if pr.semi else (1 if glow else None)
                    prims.append((tuple(pr.verts), uvs, atlas.palette(pal), blend))
                bones.append(D.Bone(-1, verts, prims))
            per_bone_pose.append((inst, 'model', first, len(bones), mframes))
            drawn.models += 1
        elif inst.kind == FLIPBOOK_KIND or (inst.kind == 13 and p0[V_RECT + 2] <= 0 and
                                            any(p0[V_MODEL] in pk.tims for pk in packs)):
            sd = next((pk.sprites[p0[V_MODEL]] for pk in packs if p0[V_MODEL] in pk.sprites), None)
            stim = next((pk.tims[p0[V_MODEL]] for pk in packs if p0[V_MODEL] in pk.tims), None)
            if stim is None:
                drawn.dropped['flipbook without its sheet'] = drawn.dropped.get('flipbook without its sheet', 0) + 1
                continue
            if sd is not None:
                sheet = parse_sprite(sd)
            else:
                sheet = grid_sheet(stim)
                drawn.notes.append(f'object {inst.slot}: sheet {stim.id} has no frame list, read as 64x64 frames')
            use = sheet.frames
            if len(use) > max_flip:
                use = [use[round(i * len(use) / max_flip)] for i in range(max_flip)]
            pal = stim.clut[0][:16] if stim.clut else [0] * 16
            rgb = p0[V_RGB:V_RGB + 3]
            if any(rgb) and rgb != [128, 128, 128]:
                pal = tint(pal, rgb, True)
            first = len(bones)
            for fr in use:
                rows = [r[fr.u // 4:(fr.u + fr.w + 3) // 4] for r in stim.words[fr.v:fr.v + fr.h]]
                bones.append(_quad(atlas, ('flip', stim.id, fr.u, fr.v), rows, fr.w, fr.h, pal, p0[V_ABR] & 3))
            per_bone_pose.append((inst, 'flip', first, len(bones), (sheet, use)))
            drawn.sprites += 1
            if len(use) < len(sheet.frames):
                drawn.notes.append(f'object {inst.slot}: flipbook {len(sheet.frames)} frames kept as {len(use)}')
        elif inst.kind in SPRITE_KINDS:
            x, y, w, h = (p0[V_RECT + i] for i in range(4))
            cx, cy = p0[V_CLUT], p0[V_CLUT + 1]
            if w <= 0 or h <= 0 or w > 128 or h > 128:
                drawn.dropped['sprite without a frame'] = drawn.dropped.get('sprite without a frame', 0) + 1
                continue
            hw = (w + 3) // 4
            rows = vram.rect(x, y, hw, h)
            if not any(any(r) for r in rows):
                drawn.dropped['sprite with no loaded sheet'] = drawn.dropped.get('sprite with no loaded sheet', 0) + 1
                continue
            pal = vram.rect(cx, cy, 16, 1)[0] if (cx or cy) else _sheet_clut(vram_tims, x)
            rgb = p0[V_RGB:V_RGB + 3]
            if not any(rgb):
                drawn.dropped['sprite tinted black (unseen)'] = drawn.dropped.get('sprite tinted black (unseen)', 0) + 1
                continue
            semi = bool(p0[V_SEMI])
            pal = tint(pal, rgb, semi)
            first = len(bones)
            bones.append(_quad(atlas, ('rect', x, y, hw, h), rows, w, h, pal, (p0[V_ABR] & 3) if semi else None))
            per_bone_pose.append((inst, 'sprite', first, first + 1, None))
            drawn.sprites += 1
            if inst.kind == 13:
                drawn.notes.append(f'object {inst.slot}: a sprite burst drawn as one sprite')
        else:
            name = KIND_NAMES.get(inst.kind, f'kind {inst.kind}')
            drawn.dropped[name] = drawn.dropped.get(name, 0) + 1

    tim = atlas.tim()
    for b in bones:
        b.prims = [D.Prim(v, atlas.uv(u), atlas.pal_row_of(pal) << 6, bl) for v, u, pal, bl in b.prims]
    keys = [dict() for _ in bones]
    frames = []
    zero = ((0,) * 9, (0, 0, 0))
    for fi, step in enumerate(steps):
        row = [0] * len(bones)
        for inst, what, b0, b1, mframes in per_bone_pose:
            st = state(inst, step, by_slot)
            for b in range(b0, b1):
                if st is None:
                    keys[b][fi] = zero
                    continue
                pos, ang, sc = st
                pos = [(c - o) * UNITS for c, o in zip(pos, origin)]
                if what in ('sprite', 'flip'):
                    if what == 'flip':
                        sheet, use = mframes
                        k = _flip_frame(sheet, step - inst.start, len(use))
                        if b - b0 != k:
                            keys[b][fi] = zero
                            continue
                    r = D._mul(_rot((ang[2], 0, 0)), [[sc[0], 0, 0], [0, sc[0], 0], [0, 0, sc[0]]])
                    m, t = r, pos
                else:
                    sm = [[sc[0], 0, 0], [0, sc[1], 0], [0, 0, sc[2]]]
                    ro = D._mul(_rot(ang), sm)
                    age = step - inst.start
                    br, bt = mframes[age % len(mframes)][b - b0]
                    # the object's scale applied in the bone's own frame: the same when the bone does not turn,
                    # and never a shear (DW1 draws a rotation times a per-axis scale)
                    m = D._mul(D._mul(_rot(ang), br), sm)
                    t = [pos[i] + sum(ro[i][k] * bt[k] * UNITS for k in range(3)) for i in range(3)]
                m = unshear(m)
                if turn:
                    flip = [[-1, 0, 0], [0, 1, 0], [0, 0, -1]]
                    m = D._mul(flip, m)
                    t = [-t[0], t[1], -t[2]]
                mi = tuple(max(-32768, min(32767, round(x * 4096))) for rr in m for x in rr)
                if max(abs(x) for x in t) > FAR:
                    keys[b][fi] = zero
                    continue
                keys[b][fi] = (mi, tuple(round(x) for x in t))
            for b in range(b0, b1):
                row[b] = fi
        frames.append(row)
    for b in range(len(bones)):
        for fi in range(len(frames)):
            keys[b].setdefault(fi, zero)
    e = D.Effect(bones, tim, keys, frames)
    e._drawn = drawn
    return e


DRAWN_KINDS = MODEL_KINDS | {FLIPBOOK_KIND} | SPRITE_KINDS


def thin(instances, max_objects, drawn=None):
    """The instances to draw: all of them, or when more than max_objects are drawn, an evenly spread share of
    each group of alike objects (same kind and model), at least one per group. A swarm of sixty identical
    sparks keeps a few."""
    drawable = [i for i in instances if i.kind in DRAWN_KINDS]
    if not max_objects or len(drawable) <= max_objects:
        return instances
    groups = {}
    for i in drawable:
        groups.setdefault((i.kind, i.segments[0].p[V_MODEL]), []).append(i)
    quota = {k: max(1, len(g) * max_objects // len(drawable)) for k, g in groups.items()}
    keep = set()
    for k, g in groups.items():
        n = quota[k]
        keep.update(id(g[(j * len(g)) // n]) for j in range(n))
    if drawn is not None:
        drawn.notes.append(f'{len(drawable)} objects thinned to {len(keep)}')
    return [i for i in instances if i.kind not in DRAWN_KINDS or id(i) in keep]


MIN_SCALE = 0.06
FAR = 100000                # DW2 units: farther than this an object is off any battle screen (and past int16)


def unshear(m):
    """The nearest rotation times per-axis scale (DW1 draws only those): Gram-Schmidt on the columns."""
    cols = [[m[r][c] for r in range(3)] for c in range(3)]
    sc = [math.sqrt(sum(x * x for x in c)) for c in cols]
    if max(sc) < MIN_SCALE:
        return [[0.0] * 3 for _ in range(3)]            # too small to see: hidden
    if min(sc) < 1e-9:
        return m
    # an axis scaled almost to nothing loses its direction in 4.12 fixed point (and reads as a shear): keep it
    # at the smallest scale that still holds one
    sc = [max(x, MIN_SCALE) for x in sc]
    q = []
    for c, n in zip(cols, sc):
        v = [x / n for x in c]
        for u in q:
            d = sum(a * b for a, b in zip(v, u))
            v = [a - d * b for a, b in zip(v, u)]
        k = math.sqrt(sum(x * x for x in v))
        if k < 1e-6:
            return m
        q.append([x / k for x in v])
    return [[q[c][r] * sc[c] for c in range(3)] for r in range(3)]


def _quad(atlas, key, rows, w, h, pal, blend):
    """A flat textured quad facing the battle camera (the x axis), `w` x `h` texels at scale 1."""
    y0 = atlas.image(key, rows)
    hs, ws = h * SPRITE_UNIT * UNITS / 2, w * SPRITE_UNIT * UNITS / 2
    hs, ws = round(hs), round(ws)
    verts = [(0, -hs, -ws), (0, -hs, ws), (0, hs, -ws), (0, hs, ws)]
    uvs = ((0, y0), (w - 1, y0), (0, y0 + h - 1), (w - 1, y0 + h - 1))
    return D.Bone(-1, verts, [((0, 1, 2, 3), uvs, atlas.palette(pal), blend)])


@dataclass
class Frame:
    ticks: int
    u: int
    v: int
    w: int
    h: int


@dataclass
class Sheet:
    loop: bool
    clut_xy: tuple
    tex_xy: tuple
    frames: list


def parse_sprite(d):
    """A sprite definition (pack record type 3): char[16] TIM name, u32 1, u32 frame count, i16 loop (-1 loops),
    u16 0, u16 palette x, y, u16 sheet x, y, then per frame u32 steps, u8 u0, u1, v0, v1, u16 w, h, u16 1,
    u16 0x80, i16 0, i16 y offset."""
    n, loop = struct.unpack_from('<Ih', d, 20)
    cx, cy, tx, ty = struct.unpack_from('<4H', d, 28)
    frames = []
    for i in range(n):
        q = 36 + 20 * i
        if q + 12 > len(d):
            break
        dur, u0, _u1, v0, _v1, w, h = struct.unpack_from('<I4B2H', d, q)
        frames.append(Frame(max(1, dur), u0, v0, w, h))
    return Sheet(loop == -1, (cx, cy), (tx, ty), frames)


def grid_sheet(tim, cell=64, ticks=4):
    """A sheet without a frame list (its id names only a TIM): cells of 64 x 64 texels, row by row, 4 steps each
    (an estimate), or the whole TIM when it is not a grid of such cells."""
    w, h = len(tim.words[0]) * 4, len(tim.words)
    if w % cell or h % cell or w > 256:
        return Sheet(True, tim.clut_xy, tim.xy, [Frame(ticks, 0, 0, min(w, 128), min(h, 128))])
    return Sheet(True, tim.clut_xy, tim.xy,
                 [Frame(ticks, x, y, cell, cell) for y in range(0, h, cell) for x in range(0, w, cell)])


def _flip_frame(sheet, age, kept):
    total = sum(f.ticks for f in sheet.frames) or 1
    t = age % total if sheet.loop else min(age, total - 1)
    for i, f in enumerate(sheet.frames):
        if t < f.ticks:
            return min(kept - 1, i * kept // len(sheet.frames))
        t -= f.ticks
    return kept - 1


def _sheet_clut(vram_tims, x):
    """The palette of the sheet under VRAM column x (the scripts mostly leave the palette variables at 0)."""
    for t, dx, _dy in reversed(vram_tims):
        if t.clut and t.xy[0] + dx <= x < t.xy[0] + dx + len(t.words[0]):
            return t.clut[0][:16]
    for t, _dx, _dy in vram_tims:
        if t.clut:
            return t.clut[0][:16]
    return [0] * 16


def tint(pal, rgb, semi):
    """A palette as the GPU shows it under a sprite colour (128 = unchanged); semi: every visible colour blends."""
    out = []
    for c in pal:
        if c == 0:
            out.append(0)
            continue
        ch = [min(31, ((c >> (5 * i)) & 31) * rgb[i] // 128) for i in range(3)]
        v = ch[0] | ch[1] << 5 | ch[2] << 10 | (0x8000 if semi else c & 0x8000)
        out.append(v if v else 0x8000)
    return out


def sheet_tims(tr, packs):
    """Where a script's sprite sheets sit in VRAM: the effect area starts at x 320 and each TIM of the script's
    own pack takes the 64-halfword column of its name's last digit ("1105_3.tim" at x 512), which is where the
    scripts' sprite rectangles point; then the sheets the script loads itself (cmdD 0: TIM id, x in
    64-halfword columns, y in 256-line halves) on top."""
    out = []
    for t in packs[0].tims.values():
        if t.xy[0] == 320:
            out.append((t, 64 * (t.id % 10), 0))
    for lid, xs, ys in tr.loads:
        t = next((pk.tims[lid] for pk in packs if lid in pk.tims), None)
        if t is not None:
            out.append((t, xs * 64 - t.xy[0], ys * 256))
    return out


# ---------------------------------------------------------------- the CLI

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--disc', default=os.environ.get('DCB_IMAGE'), help='Digital Card Battle disc image')
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('script')
    s.add_argument('id', type=int)
    s = sub.add_parser('trace')
    s.add_argument('id', type=int)
    s = sub.add_parser('pack')
    s.add_argument('id', type=int)
    a = ap.parse_args(argv)
    if not a.disc:
        raise SystemExit('give the disc image with --disc or DCB_IMAGE')
    disc = Disc(a.disc)
    if a.cmd == 'script':
        print(listing(disc.scripts()[a.id]))
    elif a.cmd == 'trace':
        tr = trace(disc.scripts()[a.id], a.id)
        print(f'script {a.id}: {tr.length} steps, {len(tr.instances)} objects started, sheets {tr.loads}')
        for i in tr.instances:
            p = i.segments[0].p
            print(f'  step {i.start:4d}-{i.end:4d} object {i.slot:3d} {KIND_NAMES.get(i.kind, i.kind):16s} '
                  f'model {p[V_MODEL]} motion {p[V_MOTION]} start {p[V_START:V_START + 3]} '
                  f'end {p[V_END:V_END + 3]} segments {len(i.segments)}')
    elif a.cmd == 'pack':
        pk = disc.pack(a.id)
        print(f'pack {a.id}: models {sorted(pk.models)} tims {sorted(pk.tims)} sprites {sorted(pk.sprites)} '
              f'anims {sorted(pk.anims)}')


if __name__ == '__main__':
    main()
