"""What an authored technique effect is built with: a script written against the battle's effect machine
(tools/efescript.py, src/btl/battle_effect.c) and a texture painted here, packed into one EFEDAT chunk.

A chunk made here holds nothing of the disc: its variables, its instance pools, its script, a one-row launch table
that tells the engine "whoever casts it, from its entity point" (type -2, BTL_checkTechCompatibility) and a 256x32
4-bit texture with up to four palettes. The effect finds its caster and its targets through the engine at run time.

The layout from the header's end ("base"): variables (VARS bytes), the launch table, the script, the pools, the
sub-effect table, the texture. Everything before the texture stays in the effect heap while the technique is
loaded, so pools are kept small: `kept` of build() is that size.
"""
import math
import struct

import numpy as np

from tools.efescript import Asm

CHUNK = 0x5000
HEADER = 0x34
VARS = 0x180            # bytes of base variables
LAUNCH = VARS           # the launch table: (-2, bone 0, 0, 0, 0), then the terminator
CODE = VARS + 12
I, B = 0, 1             # where a variable lives: the running instance, the chunk base
FRAME = (0, I)          # an instance's tick counter (-1: free)
POS = (4, I)            # its position (three int32)
ROT = (0x10, I)         # its rotation (three int32); free for an instance drawn as sprites
FREE = 0x1c             # the first free offset of an instance
CELLS = 8               # 32x32 texture cells
BLEND = {'half': 4, 'add': 5, 'sub': 6, 'soft': 7, None: 0}
QUAD = {'add': 0x20, 'sub': 0x40, 'soft': 0x60, None: 0}


def iv(off):
    """An instance variable at a byte offset (FREE and up)."""
    return (off, I)


def at(v, k):
    """Component k of a vector variable."""
    return (v[0] + 4 * k, v[1])


class Pool:
    def __init__(self, name, count, fields):
        self.name, self.count, self.stride = name, count, FREE + 4 * fields


class Fx:
    def __init__(self, delay=8, cast_sound=0, draw=False):
        """delay: the ticks of the cast animation before the effect starts; cast_sound: played at once (-1: none).
        The label `main` is called every tick from then on, NOW counting them from 0, until it jumps to `die`; with
        draw, the label `draw` is called every frame to paint."""
        self.a = Asm(CODE)
        self.nvars = 0
        self.pools = []
        self.tex = np.zeros((32, 32 * CELLS), dtype=np.uint8)
        self.palettes = []
        self.inits = []
        self._labels = 0
        # what every effect knows once it starts: the caster's and the target's feet, size (radius, height, radius)
        # and chest, and a scratch value and vector
        self.T, self.T2, self.T3 = self.var(), self.var(), self.var()
        self.TV, self.TV2 = self.vec(), self.vec()
        self.SRC, self.SSIZE, self.CHEST = self.vec(), self.vec(), self.vec()
        self.TGT, self.TSIZE, self.TCHEST = self.vec(), self.vec(), self.vec()
        self.NOW, self.SZ = self.var(), self.var()      # main's tick; the size of a particle of size None
        self.Q = [self.vec() for _ in range(4)]
        self.F1, self.F2 = self.var(), self.var()
        self.AT = self.vec()                # where the next particle() or travel() instance starts
        self.DEST = self.vec()              # where the next travel() instance goes
        self.root = self.pool('root', 1)
        a = self.a
        a.label('start')
        self.spawn(self.root)
        a.pusha(LAUNCH, B); a.sub('checkTechCompatibility')
        self.handlers('root_tick', 'draw' if draw else 'noop')
        if cast_sound >= 0:
            self.sound(cast_sound)
        a.ret()
        a.label('noop'); a.ret()
        a.label('die'); self.set(FRAME, -1); a.ret()
        a.label('root_tick'); a.ld(delay); a.br('<', *FRAME, 'noop'); a.br('>', *FRAME, 'root_run')
        a.sub('markFinished')
        a.pusha(*POS); a.push(0); a.sub('getScatteredSpawnPosition')
        self.vcopy(self.SRC, POS)
        a.pusha(*self.SSIZE); a.sub('getSourceDigimonSize')
        self.vcopy(self.CHEST, self.SRC)
        self.lin(self.T, at(self.SSIZE, 1), 6, 0, 10); self.sub_(at(self.CHEST, 1), self.T)
        self.aim()
        a.label('root_run'); self.lin(self.NOW, FRAME, 1, -delay); a.jmp('main')
        a.label('aim')                      # TGT, TSIZE and TCHEST of the current target
        a.pusha(*self.TGT); a.sub('copyTargetEntityPosition')
        a.pusha(*self.TSIZE); a.sub('getTargetDigimonSize')
        self.vcopy(self.TCHEST, self.TGT)
        self.lin(self.T, at(self.TSIZE, 1), 6, 0, 10); self.sub_(at(self.TCHEST, 1), self.T)
        a.ret()

    # ------------------------------------------------------------- declarations
    def var(self, n=1):
        off = self.nvars
        self.nvars += 4 * n
        if self.nvars > VARS:
            raise ValueError('authored effect: too many base variables')
        return (off, B)

    def vec(self):
        return self.var(3)

    def colour(self, r, g, b):
        """A base colour (a sprite's tint; 128 is the texture's own brightness), set by the init script."""
        v = self.vec()
        self.inits.append((v, (r, g, b)))
        return v

    def const(self, value):
        v = self.var()
        self.inits.append((v, (value,)))
        return v

    def pool(self, name, count, fields=0):
        p = Pool(name, count, fields)
        self.pools.append(p)
        return p

    def label(self, name=None):
        if name is None:
            self._labels += 1
            name = f'_l{self._labels}'
            return name
        self.a.label(name)
        return name

    # ------------------------------------------------------------- values
    def _push(self, x):
        if isinstance(x, tuple):
            self.a.pushv(*x)
        else:
            self.a.push(int(x))

    def _ld(self, x):
        if isinstance(x, tuple):
            self.a.ldv(*x)
        else:
            self.a.ld(int(x))

    def set(self, v, x):
        self._ld(x); self.a.op('set', *v)

    def add(self, v, x):
        self._ld(x); self.a.op('add', *v)

    def sub_(self, v, x):
        self._ld(x); self.a.op('sub', *v)

    def mul(self, v, x):
        self._ld(x); self.a.op('mul', *v)

    def div(self, v, x):
        self._ld(x); self.a.op('div', *v)

    def mod(self, v, x):
        self._ld(x); self.a.op('mod', *v)

    def lin(self, dst, src, mul=1, add=0, div=1):
        """dst = src * mul / div + add."""
        if dst != src:
            self.set(dst, src)
        if mul != 1:
            self.mul(dst, mul)
        if div != 1:
            self.div(dst, div)
        if add != 0:
            self.add(dst, add)

    def rnd(self, v, lo, hi):
        self.a.pusha(*v); self._push(lo); self._push(hi); self.a.sub('randomInRange')

    def sin(self, out, angle, amp):
        """out = amp * sin(angle); 4096 is a full turn."""
        self._push(angle); self._push(amp); self.a.pusha(*out); self.a.sub('sine')

    def cos(self, out, angle, amp):
        self._push(angle); self._push(amp); self.a.pusha(*out); self.a.sub('cosine')

    def circle(self, v, angle, radius, height=None):
        """v.x, v.z = a point of the circle of that radius around the origin (v.y untouched, or height)."""
        self.sin(at(v, 0), angle, radius)
        self.cos(at(v, 2), angle, radius)
        if height is not None:
            self.set(at(v, 1), height)

    # ------------------------------------------------------------- vectors
    def vset(self, v, x, y, z):
        for k, c in enumerate((x, y, z)):
            self.set(at(v, k), c)

    def vcopy(self, dst, src):
        self.a.pusha(*dst); self.a.pusha(*src); self.a.sub('copyVector')

    def vadd(self, dst, src):
        self.a.pusha(*dst); self.a.pusha(*src); self.a.sub('addVectors')

    def vsub(self, dst, src):
        self.a.pusha(*dst); self.a.pusha(*src); self.a.sub('subtractVectors')

    def vdiv(self, v, n):
        self.a.pusha(*v); self._push(n); self.a.sub('divideVectorByScalar')

    def vmul(self, v, n):
        self.a.pusha(*v); self._push(n); self.a.sub('multiplyVectorByScalar')

    def vlen(self, out, v):
        self.a.pusha(*out); self.a.pusha(*v); self.a.sub('vectorLength')

    def scatter(self, v, r):
        """v += a random offset of up to r/2 on each axis."""
        for k in range(3):
            self.rnd(self.T, -(r // 2), r // 2)
            self.add(at(v, k), self.T)

    def from_parent(self, dst, src_off, size=0xc):
        """Copy bytes of the spawning instance (its offset src_off) into dst."""
        self.a.pusha(*dst); self.a.push(src_off); self.a.push(size); self.a.sub('copyFromParentTransform')

    # ------------------------------------------------------------- flow
    def spawn(self, pool):
        self.a._ref('pool_' + pool.name, 2)
        self.a._w(17, pool.count, 0, -9555, pool.stride, 0)

    def handlers(self, tick, render='noop'):
        self.a.pusha_label(tick); self.a.pusha_label(render); self.a.sub('initializeSubEffectInstructions')

    def begin(self, name, pool, render='noop', inherit=True):
        """Open the spawn routine `name`: an instance of the pool with handlers name_tick and `render`. The code that
        follows sets the new instance up and ends with ret()."""
        self.a.label(name)
        self.spawn(pool)
        if inherit:
            self.a.sub('initializeEFETransform')
        self.handlers(name + '_tick', render)

    def br(self, v, cmp, x, label):
        """goto label if v <cmp> x."""
        self._ld(x); self.a.br(cmp, v[0], v[1], label)

    def life(self, ticks):
        """In a tick handler: the instance dies after that many ticks."""
        self.br(FRAME, '>', ticks, 'die')

    def call(self, label, times=1):
        for _ in range(times):
            self.a.call(label)

    def ret(self):
        self.a.ret()

    def jmp(self, label):
        self.a.jmp(label)

    def sound(self, n):
        self.a.push(n); self.a.sub('playSound')

    # ------------------------------------------------------------- ready-made instances
    def particle(self, name, count, life, cell, colour, size, grow=0, speed=0, lift=0, gravity=0, spread=0, clut=0,
                 blend='add', fade=False, spin=0, flat=None, sy=None, rot=0, drift=None):
        """Define the routine `name`: one sprite born at AT (scattered by spread), thrown at a random velocity of up
        to `speed` a tick on each axis plus `lift` upwards, pulled down by gravity, its size growing by `grow` a tick
        from `size` (a number or a (low, high) range), for `life` ticks. fade: its colour dims to black over its life
        (additive) instead of ending at once. spin: degrees a tick. sy: its height as a share of its width, in 1/16.
        flat: speed ranges per axis ((x), (y), (z)) instead of `speed`. size None: the value of SZ when it
        is born. rot: a fixed turn in degrees. drift: a base vector added to its velocity."""
        pool = self.pool(name, count, 8)
        vel, sz, col, ang = iv(FREE), iv(FREE + 12), iv(FREE + 16), iv(FREE + 28)
        skip = self.label()
        self.begin(name, pool, name + '_render', inherit=False)
        self.vcopy(POS, self.AT)
        if spread:
            self.scatter(POS, spread)
        for k in range(3):
            lo, hi = flat[k] if flat else (-speed, speed)
            if lo == hi:
                self.set(at(vel, k), lo)
            else:
                self.rnd(at(vel, k), lo, hi)
        if lift:
            self.sub_(at(vel, 1), lift)
        if drift:
            self.vadd(vel, drift)
        if size is None:
            self.set(sz, self.SZ)
        elif isinstance(size, tuple):
            self.rnd(sz, *size)
        else:
            self.set(sz, size)
        self.vset(col, *colour)
        if spin:
            self.rnd(ang, 0, 359)
        self.ret()
        self.a.label(name + '_tick')
        self.life(life)
        self.vadd(POS, vel)
        if gravity:
            self.add(at(vel, 1), gravity)
        if grow:
            self.add(sz, grow)
            self.br(sz, '>', 0, skip)
            self.set(sz, 1)
            self.a.label(skip)
        if fade:
            for k in range(3):
                self.lin(at(col, k), FRAME, -colour[k], colour[k], life + 1)
        if spin:
            self.add(ang, spin)
        self.ret()
        self.a.label(name + '_render')
        if sy is None:
            self.sprite(POS, col, sz, cell=cell, clut=clut, blend=blend, rot=ang if spin else rot)
        else:
            self.lin(self.T, sz, sy, 0, 16)
            self.sprite(POS, col, sz, self.T, cell=cell, clut=clut, blend=blend, rot=ang if spin else rot)
        self.ret()
        return pool

    def emit(self, name, where=None, times=1):
        """Throw `times` particles of that routine from a point (AT if none)."""
        if where is not None and where != self.AT:
            self.vcopy(self.AT, where)
        self.call(name, times)

    def travel(self, name, count, ticks, render, arrive, fields=0, every=None):
        """Define the routine `name`: an instance that flies from AT to DEST in `ticks` ticks, drawn by the label
        `render`, and calls the label `arrive` when it gets there (the instance stands at DEST then). every: a label
        called each tick of the flight. Its step is the instance vector at FREE; `fields` more follow it."""
        pool = self.pool(name, count, 3 + fields)
        step = iv(FREE)
        go = self.label()
        self.begin(name, pool, render, inherit=False)
        self.vcopy(POS, self.AT)
        self.vcopy(step, self.DEST)
        self.vsub(step, self.AT)
        self.vdiv(step, ticks)
        self.ret()
        self.a.label(name + '_tick')
        self.br(FRAME, '>=', ticks, go)
        self.vadd(POS, step)
        if every:
            self.a.call(every)
        self.ret()
        self.a.label(go)
        self.a.call(arrive)
        self.set(FRAME, -1)
        self.ret()
        return pool

    def when(self, tick, label):
        """In main: at that tick, call the label."""
        skip = self.label()
        self.br(self.NOW, '!=', tick, skip)
        self.a.call(label)
        self.a.label(skip)

    def end(self, tick):
        """In main: from that tick on the director is gone (the instances it left live on), and main returns."""
        self.br(self.NOW, '>=', tick, 'die')
        self.ret()

    def flat(self, centre, radius, colour, cell=0, angle=0, clut=0, blend='add'):
        """A texture cell laid flat on the ground plane around a point, turned by an angle (4096 a turn)."""
        r, t = self.F1, self.F2
        self.lin(r, radius, 181, 0, 128) if isinstance(radius, tuple) else self.set(r, radius * 181 // 128)
        for k in range(4):
            self.lin(t, angle, 1, 512 + 1024 * k) if isinstance(angle, tuple) else self.set(t, angle + 512 + 1024 * k)
            self.circle(self.Q[k], t, r, 0)
            self.vadd(self.Q[k], centre)
        self.quad(self.Q[0], self.Q[1], self.Q[3], self.Q[2], colour, cell, clut, blend)

    def pillar(self, base, width, height, colour, cell=0, clut=0, blend='add', rot=0):
        """A texture cell stood on a point, facing the camera: `width` wide, `height` tall."""
        self.vcopy(self.TV2, base)
        self.lin(self.T, height, 1, 0, 2)
        self.sub_(at(self.TV2, 1), self.T)
        self.sprite(self.TV2, colour, width, height, cell=cell, clut=clut, blend=blend, rot=rot)

    def after(self, ticks, label):
        """In a tick handler: at that tick, call the label."""
        skip = self.label()
        self.br(FRAME, '!=', ticks, skip)
        self.a.call(label)
        self.a.label(skip)

    def until(self, ticks, label):
        """In a tick handler: every tick before that one, call the label."""
        skip = self.label()
        self.br(FRAME, '>=', ticks, skip)
        self.a.call(label)
        self.a.label(skip)

    # ------------------------------------------------------------- hitting
    def aim(self):
        self.a.call('aim')

    def hit(self):
        """Hit the current target (once per cast: the engine ignores a target already hit)."""
        self.a.push(1); self.a.push(25); self.a.sub('setTransformToTargetBone'); self.a.sub('addAttackObjectToTarget')

    def hit_self(self):
        """A support technique: its target is the caster."""
        self.a.sub('addAttackObjectToTarget')

    def each_target(self, body):
        """Run body() once for every enemy not hit yet, each as the current target (TGT, TSIZE, TCHEST set); the
        instance ends where the last one stands."""
        loop, end = self.label(), self.label()
        self.a.label(loop)
        self.a.pusha(*self.T3); self.a.sub('selectNextTargetEntity')
        self.br(self.T3, '<', 0, end)
        self.a.pusha(*self.T3); self.a.sub('isTargetUnhit')
        self.br(self.T3, '==', 0, loop)
        self.aim()
        body()
        self.a.jmp(loop)
        self.a.label(end)

    # ------------------------------------------------------------- drawing
    def sprite(self, pos, colour, sx, sy=None, cell=0, clut=0, blend='add', rot=0, w=32, h=32):
        """A camera-facing sprite: texture cell `cell` (w x h texels from its corner), sx/sy its size."""
        a = self.a
        a.pusha(*pos); a.pusha(*colour); self._push(sx); self._push(sx if sy is None else sy)
        a.push(32 * cell); a.push(0); a.push(w); a.push(h); a.push(w // 2 - 1 + w % 2); a.push(h // 2 - 1 + h % 2)
        self._push(rot); a.push(BLEND[blend]); a.push(clut)
        a.sub('renderProjectedSprite')

    def quad(self, p1, p2, p3, p4, colour, cell=0, clut=0, blend='add', w=32, h=32, u=0):
        """A textured quad between four world points (p1 p2 the top edge, p3 p4 the bottom one)."""
        a = self.a
        for p in (p1, p2, p3, p4):
            a.pusha(*p)
        a.pusha(*colour); a.push(32 * cell + u); a.push(0); a.push(w - 1); a.push(h - 1); a.push(clut)
        a.push(QUAD[blend]); a.sub('render3DTexturedQuad')

    def overlay(self, colour, blend='sub', layer=10):
        """A colour over the whole screen."""
        self.a.push(layer); self.a.pusha(*colour); self.a.push(BLEND[blend]); self.a.sub('renderScreenOverlay')

    # ------------------------------------------------------------- texture
    def paint(self, cell, lum, cut=0.06, cells=1):
        """lum: a 32 x (32 * cells) array, 0..1; below cut is transparent, the rest the palette's 15 colours."""
        lum = np.asarray(lum, dtype=float)
        k = np.where(lum < cut, 0, 1 + np.minimum(14, ((lum - cut) / (1 - cut) * 15).astype(int)))
        self.tex[:, 32 * cell:32 * (cell + cells)] = k

    def palette(self, ramp):
        """A palette row: colours from dark to bright ('#rrggbb'), spread over the 15 opaque indices."""
        cols = [tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in ramp]
        row = [0]
        for k in range(15):
            x = k / 14 * (len(cols) - 1)
            i = min(int(x), len(cols) - 2)
            r, g, b = (round(p + (q - p) * (x - i)) for p, q in zip(cols[i], cols[i + 1]))
            row.append(max(1, (r >> 3) | (g >> 3) << 5 | (b >> 3) << 10) | 0x8000)
        self.palettes.append(row)
        return len(self.palettes) - 1

    def tim(self):
        rows = self.palettes or [[0] * 16]
        clut = b''.join(struct.pack('<16H', *r) for r in rows)
        pix = bytearray()
        for y in range(32):
            r = self.tex[y]
            pix += bytes(int(r[x]) | int(r[x + 1]) << 4 for x in range(0, 32 * CELLS, 2))
        return (struct.pack('<2I', 0x10, 8) + struct.pack('<I4H', 12 + len(clut), 128, 488, 16, len(rows)) + clut
                + struct.pack('<I4H', 12 + len(pix), 576, 256, 8 * CELLS, 32) + bytes(pix))

    # ------------------------------------------------------------- the chunk
    def build(self, effect_id):
        a = self.a
        a.label('init')
        for v, values in self.inits:
            for k, x in enumerate(values):
                self.set(at(v, k), x)
        a.ret()
        off = (a.here() + 3) & ~3
        for p in self.pools:
            a.labels['pool_' + p.name] = off
            off += p.count * p.stride
        code = a.bytes()
        body = bytearray(CODE)
        struct.pack_into('<6h', body, LAUNCH, -2, 0, 0, 0, 0, -1)
        body += code
        body += bytes(-len(body) % 4)
        for p in self.pools:
            assert len(body) == a.labels['pool_' + p.name]
            for _ in range(p.count):
                body += struct.pack('<i', -1) + bytes(p.stride - 4)
        nsub = sum(p.count for p in self.pools)
        subs = len(body)
        body += bytes(nsub * 28)
        kept = len(body)
        body += self.tim()
        end = len(body)
        hdr = struct.pack('<13i', a.labels['start'], a.labels['init'], subs, subs, subs, kept, kept, kept, end, end,
                          4, nsub, effect_id)
        chunk = hdr + bytes(body)
        if len(chunk) > CHUNK:
            raise ValueError(f'authored effect: {len(chunk)} bytes, a chunk holds {CHUNK}')
        return chunk + bytes(CHUNK - len(chunk)), kept


# ----------------------------------------------------------------- painting helpers
def grid(w=32, h=32):
    y, x = np.mgrid[0:h, 0:w]
    return x + 0.5, y + 0.5


def noise(w, h, scale, seed):
    r = np.random.default_rng(seed)
    gw, gh = max(2, w // scale), max(2, h // scale)
    g = r.random((gh, gw))
    ys, xs = np.arange(h) / h * gh, np.arange(w) / w * gw
    y0, x0 = np.floor(ys).astype(int), np.floor(xs).astype(int)
    fy, fx = (ys - y0)[:, None], (xs - x0)[None, :]
    fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
    p, q = g[y0 % gh][:, x0 % gw], g[y0 % gh][:, (x0 + 1) % gw]
    r_, s = g[(y0 + 1) % gh][:, x0 % gw], g[(y0 + 1) % gh][:, (x0 + 1) % gw]
    return p * (1 - fx) * (1 - fy) + q * fx * (1 - fy) + r_ * (1 - fx) * fy + s * fx * fy


def fbm(seed, w=32, h=32):
    return (noise(w, h, 8, seed) + 0.5 * noise(w, h, 4, seed + 1) + 0.25 * noise(w, h, 2, seed + 2)) / 1.75


def polar(cx=16.0, cy=16.0, w=32, h=32):
    x, y = grid(w, h)
    return np.hypot(x - cx, y - cy), np.arctan2(y - cy, x - cx)


def clip(v):
    return np.clip(v, 0, 1)


def glow(radius=14.0, power=1.6):
    r, _ = polar()
    return clip(1 - r / radius) ** power


def ring(radius=11.0, width=3.0):
    r, _ = polar()
    return clip(1 - np.abs(r - radius) / width)


def star(points=4, inner=2.5, outer=12.0, sharp=8, turn=0.0):
    r, ang = polar()
    edge = inner + outer * np.abs(np.cos((ang + turn) * points / 2)) ** sharp
    return clip(1 - r / edge) ** 0.6


def segment(x0, y0, x1, y1, width=2.0, w=32, h=32):
    """A soft line between two points."""
    x, y = grid(w, h)
    t = np.clip(((x - x0) * (x1 - x0) + (y - y0) * (y1 - y0)) / ((x1 - x0) ** 2 + (y1 - y0) ** 2), 0, 1)
    d = np.hypot(x - (x0 + t * (x1 - x0)), y - (y0 + t * (y1 - y0)))
    return clip(1 - d / width)


def crescent(radius=13.0, bite=10.0, shift=6.0, turn=0.0):
    """A crescent: a disc with an off-centre disc bitten out of it."""
    x, y = grid()
    cx, cy = 16 + shift * math.cos(turn), 16 + shift * math.sin(turn)
    body = clip((radius - np.hypot(x - 16, y - 16)) / 1.5)
    hole = clip((bite - np.hypot(x - cx, y - cy)) / 1.5)
    return clip(body - hole)
