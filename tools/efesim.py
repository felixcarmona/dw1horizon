#!/usr/bin/env python3
"""A model of Digimon World's battle effect engine (src/btl/battle_effect.c) for checking effect chunks offline.

It runs a chunk's scripts as BTL_runEFEScript does (the opcodes, call/return with the saved context and
target index, spawnEFESubEffect's search for a free instance and context, the tick and render passes) and the
sub-opcodes the DW2 converter (tools/dw2efe.py) uses, against mocked fighters. It records what the chunk
draws (drawTMDYXZ: object, rotation, scale, position), the hits it deals and the sounds it plays, and can draw
those frames with the chunk's own TMD and TIM.

It also models the sub-opcodes the disc's own chunks use as templates for composed effects (tools/efecompose.py):
drawTMD, the projected sprites and quads (drawn with the chunk's TIM), the vector arithmetic, the bone and target
lookups (a fighter's bones are all at its mid height), the line, radius and box hit tests, and the random
numbers (a fixed generator, so two runs of one script draw alike). Effects the engine draws with its own
pictures (clouds, flashes, particles, lines) are recorded in `fx` but not drawn. Another sub-opcode stops the
run with an error.
"""
import math
import struct

from tools.efescript import HEADER, OPERATORS, COMPARISONS, SUB

BASE = 0x100000
WIDTH = {0x400: 4, 0x200: 2}


def _cdiv(a, b):
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


def _wrap(v, size):
    bits = 8 * size
    v &= (1 << bits) - 1
    return v - (1 << bits) if v >> (bits - 1) else v


class Fighter:
    """A mocked battle entity: position on the ground (y down), facing, size and health."""

    def __init__(self, type_, pos, yaw=0, radius=150, height=600, hp=100):
        self.type, self.pos, self.yaw = type_, list(pos), yaw
        self.radius, self.height, self.hp = radius, height, hp
        self.is_hit = 0
        self.hits = 0

    def bone(self, idx):
        """A stand-in for a bone's world position: on the body's axis at mid height."""
        return [self.pos[0], self.pos[1] - self.height // 2, self.pos[2]]


def ry(yaw):
    a = yaw * math.pi / 2048
    c, s = math.cos(a), math.sin(a)
    return [[c, 0, s], [0, 1, 0], [-s, 0, c]]


def rot_yxz(rx, ry_, rz):
    from tools.dw2efe import rot_yxz as r
    k = math.pi / 2048
    return r(rx * k, ry_ * k, rz * k)


def euler_y(x, z):
    return round(math.atan2(x, z) * 2048 / math.pi) & 0xfff


def rot_zyx(rx, ry_, rz):
    """libgte RotMatrixZYX (angles in 4096ths of a turn): Rz * Ry * Rx."""
    return _mul(_mul(_rz(rz), ry(ry_)), _rx(rx))


def rot_xyz(rx, ry_, rz):
    """libgte RotMatrix: Rx * Ry * Rz."""
    return _mul(_mul(_rx(rx), ry(ry_)), _rz(rz))


def _rx(a):
    a = a * math.pi / 2048
    c, s = math.cos(a), math.sin(a)
    return [[1, 0, 0], [0, c, -s], [0, s, c]]


def _rz(a):
    a = a * math.pi / 2048
    c, s = math.cos(a), math.sin(a)
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]


def _mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def euler_yxz(m):
    """Angles (4096ths) of a rotation matrix as RotMatrixYXZ takes them."""
    k = 2048 / math.pi
    ax = math.asin(max(-1.0, min(1.0, -m[1][2])))
    return (round(ax * k) & 0xfff, round(math.atan2(m[0][2], m[2][2]) * k) & 0xfff,
            round(math.atan2(m[1][0], m[1][1]) * k) & 0xfff)


def _lerp(a, b, t0, t1, t):
    """map.c lerp, which the effect scripts' interpolateVector calls."""
    if t1 == t0:
        return 0
    rng = b - a
    r = _cdiv(rng * (t - t0), t1 - t0)
    if rng >= 0:
        r = r - _cdiv(r, rng + 1) * (rng + 1)
        if r < 0:
            r += rng
    else:
        r = r - _cdiv(r, rng - 1) * (rng - 1)
        if r > 0:
            r += rng
    return r + a


def _segment_rect(rect, line):
    """map.c doSomethingWithSomePoints: -1 when the segment touches the rectangle (x0, z0, x1, z1)."""
    code = []
    for x, y in line:
        c = 5 if rect[2] < x else 3 if x < rect[0] else 4
        c += 3 if rect[3] < y else -3 if y < rect[1] else 0
        if c == 4:
            return -1
        code.append(c)
    if code[0] + code[1] == 8:
        return -1
    if code[0] // 3 == code[1] // 3 or code[0] % 3 == code[1] % 3:
        return 0
    (ax, ay), (bx, by) = line
    dx, dy = bx - ax, by - ay
    corners = [(rect[0], rect[1]), (rect[2], rect[1]), (rect[0], rect[3]), (rect[2], rect[3])]
    cross = [dx * (cy - ay) - dy * (cx - ax) for cx, cy in corners]
    return -1 if any(cross[0] * x < 0 for x in cross[1:]) else 0


class Context:
    def __init__(self):
        self.inst = None
        self.render = None
        self.instance = 0
        self.parent = 0
        self.source = None
        self.target = None
        self.bone_offset = None


class Sim:
    def __init__(self, chunk, fighters, caster, target, seed=1):
        """fighters: Fighter or None for each of the 10 entity slots; caster, target: their indices."""
        h = struct.unpack_from('<13i', chunk, 0)
        self.hdr = dict(zip(('start', 'init', 'uv', 'uv_end', 'subs', 'tmd', 'tmd_end', 'tim', 'tim_end', 'end',
                             'unk', 'n_sub', 'effect'), h))
        self.mem = bytearray(chunk[HEADER:])
        self.fighters = fighters
        self.caster, self.target = fighters[caster], fighters[target]
        self.contexts = [Context() for _ in range(self.hdr['n_sub'])]
        self.target_index = 1
        self.tick = 0
        self.draws, self.hits, self.sounds, self.log = [], [], [], []
        self.R = 0
        self.seed = seed
        self.sprites, self.quads, self.fx, self.tests = [], [], [], []
        self.colours = set()
        self.model_colours = {}                # chunk addresses read as colours (EfeColor, a sprite's VECTOR)
        self.uv = {}                        # TMD object: [keyframes, keyframe, uvFrame, du, dv]
        self.ctx = self.contexts[0]
        self.cur = 0
        self.prev = 0
        self.run(BASE + self.hdr['init'])
        self.ctx = self.contexts[0]
        self.cur = 0
        self.run(BASE + self.hdr['start'])

    # memory
    def rd(self, addr, size=4):
        o = addr - BASE
        if not 0 <= o <= len(self.mem) - size:
            raise RuntimeError(f'read outside the chunk at {o:#x}')
        return int.from_bytes(self.mem[o:o + size], 'little', signed=True)

    def wr(self, addr, v, size=4):
        o = addr - BASE
        if not 0 <= o <= len(self.mem) - size:
            raise RuntimeError(f'write outside the chunk at {o:#x}')
        self.mem[o:o + size] = _wrap(v, size).to_bytes(size, 'little', signed=True)

    def vec(self, addr):
        return [self.rd(addr + 4 * k) for k in range(3)]

    def setvec(self, addr, v):
        for k in range(3):
            self.wr(addr + 4 * k, int(v[k]))

    def var(self, off, where):
        return (self.cur if where == 0 else BASE) + off

    # the interpreter
    def run(self, pc):
        stack, calls = [], [0]
        self.pc = pc
        steps = 0
        while self.pc:
            steps += 1
            if steps > 200000:
                raise RuntimeError('script runs away')
            w = struct.unpack_from('<6h', self.mem + bytes(12), self.pc - BASE)
            word = w[0] & 0xFFFF
            op = word & 0xFF
            size = WIDTH.get(word & 0xF00, 1)
            if op == 0:
                self.R = w[1]; self.pc += 6
            elif op == 1:
                self.R = self.rd(self.var(w[1], w[2]), size); self.pc += 6
            elif op == 2:
                self.R = self.rand(); self.pc += 2
            elif op == 3:
                isz = WIDTH.get((word >> 4) & 0xF00, 1)
                idx = self.rd(self.var(w[3], w[4]), isz)
                self.R = self.rd(BASE + w[1] + idx * size, size); self.pc += 10
            elif op == 4:
                a = self.var(w[1], w[2]); x = self.rd(a, size); r = self.R
                name = OPERATORS[(word >> 12) & 7]
                x = {'set': lambda: r, 'add': lambda: x + r, 'sub': lambda: x - r, 'mul': lambda: x * r,
                     'div': lambda: _cdiv(x, r), 'mod': lambda: x - _cdiv(x, r) * r, 'shl': lambda: x << r,
                     'shr': lambda: x >> r}[name]()
                self.wr(a, x, size); self.pc += 6
            elif op == 7:
                x = self.rd(self.var(w[1], w[2]), size)
                c = COMPARISONS[(word >> 12) % 6]
                ok = {'==': x == self.R, '!=': x != self.R, '<': x < self.R, '<=': x <= self.R, '>': x > self.R,
                      '>=': x >= self.R}[c]
                self.pc = BASE + (w[3] & 0xFFFF) if ok else self.pc + 10
            elif op == 9:
                self.pc = BASE + (w[1] & 0xFFFF)
            elif op == 10:
                stack.append(w[1]); self.pc += 6
            elif op == 11:
                stack.append(self.rd(self.var(w[1], w[2]), size)); self.pc += 6
            elif op == 12:
                stack.append(self.var(w[1], w[2])); self.pc += 6
            elif op == 13:
                calls.append((self.target_index, self.ctx, self.pc + 6))
                self.pc = BASE + (w[1] & 0xFFFF)
            elif op == 14:
                self.pc += 2
                self.subop(word >> 8, stack)
            elif op == 15:
                self.ret(calls)
            elif op == 16:
                self.wr(self.var(w[1], w[2]), stack.pop()); self.pc += 6
            elif op == 17:
                self.spawn(w, calls)
            else:
                raise RuntimeError(f'opcode {op} not modelled')
        if self.cur and self.rd(self.cur) == -1:
            self.ctx.inst = None

    def ret(self, calls):
        top = calls.pop()
        if top == 0:
            self.pc = 0
            return
        self.target_index, self.ctx, self.pc = top
        self.cur, self.prev = self.ctx.instance, self.ctx.parent

    def spawn(self, w, calls):
        self.target_index = 1
        n, pool, stride = w[1], BASE + w[2], w[4]
        for i in range(n):
            if self.rd(pool + i * stride) == -1:
                inst = pool + i * stride
                break
        else:
            return self.ret(calls)
        src, tgt = self.ctx.source, self.ctx.target
        k = self.contexts.index(self.ctx)
        while self.contexts[k].inst is not None:
            k += 1
            if k >= len(self.contexts):
                return self.ret(calls)
        self.ctx = self.contexts[k]
        self.prev, self.cur = self.cur, inst
        self.ctx.instance, self.ctx.parent = inst, self.prev
        if self.prev == 0:
            self.ctx.source, self.ctx.target = self.caster, self.target
        else:
            self.ctx.source, self.ctx.target = src, tgt
        self.pc += 12

    # sub-opcodes
    def subop(self, code, st):
        name = SUB.get(code, code)
        c, cur = self.ctx, self.cur
        if name == 'checkTechCompatibility':
            t = st.pop()
            while True:
                ty = self.rd(t, 2)
                if ty == c.source.type:
                    break
                if ty < 0:
                    self.pc = 0
                    return
                t += 10
            c.bone_offset = [self.rd(t + 2 + 2 * k, 2) for k in range(4)]
        elif name == 'initializeSubEffectInstructions':
            a, b = st.pop(), st.pop()
            self.wr(cur, 0)
            c.inst, c.render = b, a
        elif name == 'initializeEFETransform':
            if self.prev == 0:
                self.bone_offset_transform()
            else:
                for k in range(6):
                    self.wr(cur + 4 + 4 * k, self.rd(self.prev + 4 + 4 * k))
        elif name == 'setTransformToBoneOffset':
            self.bone_offset_transform()
        elif name == 'setTransformToSourceBone':
            idx = st.pop()
            p = c.source.bone(idx)
            yaw = c.source.yaw
            p[0] += (round(math.sin(-(yaw >> 3) * math.pi / 256) * 4096) * 25) >> 12
            p[2] += (round(math.sin(-(((yaw >> 3) + 0x80) & 0x1ff) * math.pi / 256) * 4096) * 25) >> 12
            self.setvec(cur + 4, p)
            self.setvec(cur + 0x10, (0, yaw, 0))
        elif name == 'faceTargetEntity':
            if c.target is not None:
                s, t = c.source, c.target
                s.yaw = euler_y(s.pos[0] - t.pos[0], s.pos[2] - t.pos[2])
        elif name == 'initializeUVAnim':
            table, _val, idx = st.pop(), st.pop(), st.pop()
            if table == -1:                 # the disc's chunks: no keyframes of their own (the record stays idle)
                return
            n = self.rd(table)
            keys = [(self.rd(table + 4 + 4 * k, 2), self.rd(table + 6 + 4 * k, 1), self.rd(table + 7 + 4 * k, 1))
                    for k in range(n)]
            self.uv[idx] = [keys, 0, 0, 0, 0]
            self.wr(BASE + self.hdr['uv'] + 0x20 * idx + 0xc, n, 2)
        elif name == 'playSound':
            self.sounds.append((self.tick, st.pop()))
        elif name == 'copyTargetEntityPosition':
            self.setvec(st.pop(), c.target.pos)
        elif name in ('getTargetDigimonSize', 'getSourceDigimonSize'):
            f = c.target if name.startswith('getTarget') else c.source
            self.setvec(st.pop(), (f.radius, f.height, f.radius))
        elif name == 'subtractVectors':
            b, a = st.pop(), st.pop()
            self.setvec(a, [x - y for x, y in zip(self.vec(a), self.vec(b))])
        elif name == 'vectorLength':
            v, out = st.pop(), st.pop()
            self.wr(out, int(math.sqrt(sum(x * x for x in self.vec(v)))))
        elif name == 'vectorEulerAngles':
            v, out = st.pop(), st.pop()
            x, y, z = self.vec(v)
            self.setvec(out, (round(math.atan2(-y, math.hypot(x, z)) * 2048 / math.pi) & 0xfff, euler_y(x, z), 0))
        elif name == 'rotateVector':
            v, r = st.pop(), st.pop()
            m = rot_zyx(*[_wrap(x, 2) for x in self.vec(r)])
            x = [_wrap(t, 2) for t in self.vec(v)]
            self.setvec(v, [_wrap(round(sum(m[i][k] * x[k] for k in range(3))), 2) for i in range(3)])
        elif name in ('drawTMDYXZ', 'drawTMD'):
            sc, oid = st.pop(), st.pop()
            self.draws.append((self.tick, oid, tuple(self.vec(cur + 0x10)), tuple(self.vec(sc)),
                               tuple(self.vec(cur + 4)), tuple(self.uv[oid][3:]) if oid in self.uv else (0, 0),
                               'yxz' if name == 'drawTMDYXZ' else 'xyz', self.model_colours.get(oid)))
        elif name == 'selectNextTargetEntity':
            out = st.pop()
            while self.target_index < 10:
                f = self.fighters[self.target_index]
                if f is not None and f is not c.source and f.hp > 0:
                    break
                self.target_index += 1
            if self.target_index >= 10:
                self.wr(out, -1)
                return
            c.target = self.fighters[self.target_index]
            self.wr(out, self.target_index)
            self.target_index += 1
        elif name == 'addAttackObjectToTarget':
            t = c.target
            if t.is_hit:
                return
            t.is_hit = 1
            t.hits += 1
            self.hits.append((self.tick, self.fighters.index(t), tuple(self.vec(cur + 4))))
        elif not self.native(name, st):
            raise RuntimeError(f'sub-opcode {name} not modelled')

    # the disc's own chunks (templates of composed effects)
    def rand(self):
        """A fixed linear congruential generator in place of rand() and customRandom: same seed, same run."""
        self.seed = (self.seed * 1103515245 + 12345) & 0x7FFFFFFF
        return self.seed >> 16

    def colour(self, addr):
        self.colours.add(addr)
        return tuple(self.vec(addr))

    def hit(self, f, kind, pos):
        f.is_hit = 1
        f.hits += 1
        self.hits.append((self.tick, self.fighters.index(f), tuple(int(x) for x in pos)))
        self.tests.append((self.tick, kind, self.fighters.index(f)))

    def others(self):
        src = self.ctx.source
        return [(i, f) for i, f in enumerate(self.fighters) if f is not None and f is not src and i >= 1]

    def native(self, name, st):
        """The sub-opcodes of the disc's chunks; False when not modelled."""
        c, cur = self.ctx, self.cur
        pop = st.pop
        if name in ('addVectors', 'subtractVectors', 'multiplyVectors', 'divideVectors', 'maskVectors'):
            b, a = pop(), pop()
            x, y = self.vec(a), self.vec(b)
            f = {'addVectors': lambda p, q: p + q, 'subtractVectors': lambda p, q: p - q,
                 'multiplyVectors': lambda p, q: p * q, 'divideVectors': lambda p, q: _cdiv(p, q) if q else 0,
                 'maskVectors': lambda p, q: p & q}[name]
            self.setvec(a, [f(p, q) for p, q in zip(x, y)])
        elif name in ('multiplyVectorByScalar', 'divideVectorByScalar', 'maskVectorByScalar'):
            k, v = pop(), pop()
            f = {'multiplyVectorByScalar': lambda p: p * k, 'divideVectorByScalar': lambda p: _cdiv(p, k) if k else 0,
                 'maskVectorByScalar': lambda p: p & k}[name]
            self.setvec(v, [f(p) for p in self.vec(v)])
        elif name == 'copyVector':
            src, dst = pop(), pop()
            self.setvec(dst, self.vec(src))
        elif name == 'copyFromParentTransform':
            size, off, dst = pop(), pop(), pop()
            src = (self.prev or cur) + off
            n = {0xc: 12, 4: 4, 2: 2, 1: 1}.get(size, 0)
            if n == 12:
                self.setvec(dst, self.vec(src))
            elif n:
                self.wr(dst, self.rd(src, n), n)
        elif name in ('sine', 'cosine'):
            out, scale, ang = pop(), pop(), pop()
            f = math.sin if name == 'sine' else math.cos
            self.wr(out, (scale * round(f((ang & 0xfff) * math.pi / 2048) * 4096)) >> 12)
        elif name == 'randomInRange':
            a, b, out = pop(), pop(), pop()
            lo, hi = min(a, b), max(a, b)
            self.wr(out, lo + (self.rand() << 15 | self.rand()) % (hi - lo + 1))
        elif name == 'interpolateValue':
            end, start, t, hi, lo, out = pop(), pop(), pop(), pop(), pop(), pop()
            lo, hi = min(lo, hi), max(lo, hi)
            t = min(max(t, lo), hi)
            self.wr(out, start if lo == hi else start + _cdiv((t - lo) * (end - start), hi - lo))
        elif name == 'interpolateVector':
            out, t, t1, t0, b, a = pop(), pop(), pop(), pop(), pop(), pop()
            self.setvec(out, [_lerp(x, y, t0, t1, t) for x, y in zip(self.vec(a), self.vec(b))])
        elif name in ('discardOperand', 'discardOperandPair'):
            pop()
            if name == 'discardOperandPair':
                pop()
        elif name == 'rotateVectorByAngles':
            v, w = pop(), pop()
            m = rot_yxz(*[_wrap(x, 2) for x in self.vec(w)])
            x = self.vec(v)
            self.setvec(v, [round(sum(m[i][k] * x[k] for k in range(3))) for i in range(3)])
        elif name == 'normalizeRotationAngles2':
            v, out = pop(), pop()
            self.setvec(out, [x & 0xfff for x in self.vec(v)])
        elif name == 'combineRotations':
            b, a = pop(), pop()
            x, y = self.vec(a), self.vec(b)
            if any(y):
                m1, m2 = rot_yxz(*x), rot_yxz(*y)
                m = [[sum(m1[i][k] * m2[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
                self.setvec(a, euler_yxz(m))
        elif name in ('getSourceBoneTransform', 'getTargetBoneTransform'):
            rot, pos, idx = pop(), pop(), pop()
            f = c.source if name.startswith('getSource') else c.target
            self.setvec(pos, f.bone(idx))
            self.setvec(rot, (0, f.yaw, 0))
        elif name == 'setTransformToBoneMatrix':
            self.bone_offset_transform()
        elif name == 'setTransformToTargetBone':
            r, idx = pop(), pop()
            t = c.target
            p = t.bone(idx)
            yaw = t.yaw
            p[0] += (round(math.sin(-(yaw >> 3) * math.pi / 256) * 4096) * r) >> 12
            p[2] += (round(math.sin(-(((yaw >> 3) + 0x80) & 0x1ff) * math.pi / 256) * 4096) * r) >> 12
            self.setvec(cur + 4, p)
            self.setvec(cur + 0x10, (0, yaw, 0))
        elif name == 'getScatteredSpawnPosition':
            r, out = pop(), pop()
            p = c.source.bone(0) if self.prev == 0 else self.vec(self.prev + 4)
            if r > 0:
                p = [x + self.rand() % r - (r >> 1) for x in p]
            self.setvec(out, p)
        elif name == 'steerTransformTowardPoint':
            turn, speed, target = pop(), pop(), pop()
            pos, t = self.vec(cur + 4), self.vec(target)
            yaw = self.rd(cur + 0x14)
            want = euler_y(pos[0] - t[0], pos[2] - t[2])
            d = (want - yaw) & 0xfff
            d = d - 0x1000 if d > 0x800 else d
            d = max(-turn, min(turn, d))
            yaw += d
            self.wr(cur + 0x14, yaw)
            m = rot_zyx(self.rd(cur + 0x10), yaw, self.rd(cur + 0x18))
            v = [m[i][2] * -speed * 8 for i in range(3)]
            self.setvec(cur + 4, [p + int(x) // 8 for p, x in zip(pos, v)])
        elif name == 'setModelObjectColor':
            col, oid = pop(), pop()
            self.model_colours[oid] = self.colour(col)
        elif name in ('renderCenteredSprite', 'renderProjectedSprite'):
            if name == 'renderCenteredSprite':
                y, x = pop(), pop()
                for v in (x + 1, y + 1, x // 2, y // 2, 0, 5, 0):
                    st.append(v)
            row, attr, rot, my, mx, h, w, v, u, sy, sx, col, pos = [pop() for _ in range(13)]
            self.sprites.append((self.tick, tuple(self.vec(pos)), u, v, w, h, sx, sy, self.colour(col), row,
                                 rot, attr & 3 if attr & 4 else None))
        elif name == 'render3DTexturedQuad':
            semi, row, dv, du, v0, u0, col, p4, p3, p2, p1 = [pop() for _ in range(11)]
            self.quads.append((self.tick, [tuple(self.vec(p)) for p in (p1, p2, p3, p4)], u0, v0, du, dv,
                               self.colour(col), row, (semi >> 5) & 3 if semi else None))
        elif name == 'renderScreenSprite':
            for _ in range(13):
                pop()
            self.fx.append((self.tick, 'screen sprite', None, None))
        elif name == 'renderLine':
            flags, depth, col = pop(), pop(), pop()
            for _ in range(4):
                pop()
            self.fx.append((self.tick, 'line', None, self.colour(col)))
        elif name == 'projectPositionToScreen':
            depth, yo, xo, src = pop(), pop(), pop(), pop()
            p = self.vec(src)
            self.wr(xo, 160 + p[0] // 20), self.wr(yo, 120 + p[1] // 20), self.wr(depth, 300)
        elif name == 'addCloudEffect':
            self.fx.append((self.tick, 'cloud', tuple(self.vec(pop())), None))
        elif name == 'addParticleEmitter':
            frames, col, n, kind = pop(), pop(), pop(), pop()
            self.fx.append((self.tick, 'particles', tuple(self.vec(cur + 4)), self.colour(col)))
        elif name == 'createFlash':
            cmax, cmin, smax, smin, tmax, depth, pos, mode = [pop() for _ in range(8)]
            self.fx.append((self.tick, 'flash', tuple(self.vec(pos)), (self.colour(cmin), self.colour(cmax))))
        elif name == 'checkCollisionWithDefaultPower':
            st.append(-1)
            return self.native('applyBoxAttackHit', st)
        elif name in ('applyBoxAttackHit', 'findHitEntity'):
            if name == 'findHitEntity':
                ext, mode, out = pop(), pop(), pop()
            else:
                _r, out, ext = pop(), pop(), pop()
                mode = 0
            self.wr(out, 0)
            p, e = self.vec(cur + 4), self.vec(ext)
            for i, f in self.others():
                q = (f.pos[0], f.pos[1] - f.height // 2, f.pos[2])
                b = (f.radius // 2, f.height // 2, f.radius // 2)
                if all(abs(p[k] - q[k]) <= e[k] + b[k] for k in range(3)) and (mode == 1 or not f.is_hit):
                    self.hit_index = i
                    self.wr(out, 1)
                    if name == 'applyBoxAttackHit':
                        self.hit(f, 'box', p)
                    else:
                        self.tests.append((self.tick, 'find', i))
                    break
        elif name == 'setTargetToHitEntity':
            c.target = self.fighters[getattr(self, 'hit_index', self.fighters.index(c.target))]
        elif name == 'applyLineAttackHit':
            width, out, arg = pop(), pop(), pop()
            self.wr(out, 0)
            p, s = self.vec(cur + 4), c.source.pos
            line = ((p[0], p[2]), (s[0], s[2]))
            for _i, f in self.others():
                if f.is_hit:
                    continue
                r = f.radius
                rect = (f.pos[0] - r, f.pos[2] - r, f.pos[0] + r, f.pos[2] + r)
                if _segment_rect(rect, line) != -1 or p[1] < -f.height - self.rd(arg + 4):
                    continue
                self.hit(f, 'line', p)
                self.wr(out, 1)
                break
        elif name == 'applyRadiusAttackHit':
            out, r = pop(), pop()
            self.wr(out, 0)
            p = self.vec(cur + 4)
            for _i, f in self.others():
                if f.is_hit or f.radius ** 2 + r * r < (p[0] - f.pos[0]) ** 2 + (p[2] - f.pos[2]) ** 2:
                    continue
                self.hit(f, 'radius', p)
                self.wr(out, 1)
        elif name == 'checkTargetCollision':
            r, flag, out2, out = pop(), pop(), pop(), pop()
            p, t = self.vec(cur + 4), c.target.pos
            d0, d1 = p[0] - t[0], p[2] - t[2]
            if r * r < d0 * d0 + d1 * d1:
                self.wr(flag, 0)
            else:
                self.wr(flag, 1)
                ang = (-(round(math.atan2(d1, d0) * 2048 / math.pi) - 0x400)) & 0xfff
                self.wr(out2, ang + 0x800)
                a = (((ang + 0x800) >> 3) & 0x1ff)
                self.setvec(out, (round(r * math.cos((0x80 - a) * math.pi / 256)), self.rd(out + 4),
                                  round(r * math.sin((0x80 - a) * math.pi / 256))))
                self.tests.append((self.tick, 'target', self.fighters.index(c.target)))
        elif name == 'selectRandomTargetEntity':
            pop()
            live = [f for _i, f in self.others() if f.hp > 0]
            if live:
                c.target = live[self.rand() % len(live)]
        else:
            return False
        return True

    def bone_offset_transform(self):
        c = self.ctx
        s = c.source
        b = s.bone(c.bone_offset[0])
        m = ry(s.yaw)
        off = c.bone_offset[1:]
        p = [b[i] + round(sum(m[i][k] * off[k] for k in range(3))) for i in range(3)]
        self.setvec(self.cur + 4, p)
        self.setvec(self.cur + 0x10, (0, s.yaw, 0))

    def step(self, reset_hits=False):
        """One engine tick, then the render pass."""
        self.tick += 1
        if reset_hits:
            for f in self.fighters:
                if f is not None:
                    f.is_hit = 0
        for c in self.contexts:
            if c.inst is not None:
                self.ctx, self.cur, self.prev = c, c.instance, c.parent
                self.wr(self.cur, self.rd(self.cur) + 1)
                self.run(c.inst)
        for a in self.uv.values():          # BTL_tickEFEUVAnimation
            keys = a[0]
            a[2] += 1
            if a[2] >= keys[a[1]][0]:
                a[2] = 0
                a[1] = (a[1] + 1) % len(keys)
                a[3] += keys[a[1]][1]
                a[4] += keys[a[1]][2]
        for c in self.contexts:
            if c.inst is not None:
                self.ctx, self.cur, self.prev = c, c.instance, c.parent
                self.run(c.render)

    def live(self):
        return sum(c.inst is not None for c in self.contexts)


# ----------------------------------------------------------------- the chunk's own geometry and texture

def tmd_objects(chunk):
    """[(vertices, [(vertex indices, uvs, palette row, blend or None, colour or None)])] of the chunk's TMD: its
    textured polygons (the only kind effect chunks use), lit or not. colour: the prim's own (r, g, b), by which
    the texture is modulated (128 = as is); None for raw-texture prims (TGE) and lit ones (drawn as is)."""
    h = struct.unpack_from('<13i', chunk, 0)
    if h[5] == h[6]:
        return []
    base = HEADER + h[5]
    n = struct.unpack_from('<I', chunk, base + 8)[0]
    out = []
    for i in range(n):
        vt, nv, _nt, _n, pt, npr, _s = struct.unpack_from('<7I', chunk, base + 12 + 28 * i)
        verts = [struct.unpack_from('<3h', chunk, base + 12 + vt + 8 * k) for k in range(nv)]
        prims = []
        p = base + 12 + pt
        for _ in range(npr):
            olen, ilen, flag, mode = struct.unpack_from('<4B', chunk, p)
            size = 4 * (ilen + 1)
            if not mode & 4:                # untextured: not drawn (no effect chunk has one)
                p += size
                continue
            nvx = 4 if mode & 8 else 3
            uvw = struct.unpack_from(f'<{nvx * 2}H', chunk, p + 4)
            uvs = [(uvw[2 * k] & 0xFF, uvw[2 * k] >> 8) for k in range(nvx)]
            cba, tsb = uvw[1], uvw[3]
            q = p + 4 + 4 * nvx
            colour = None
            if flag & 1:                    # unlit: colours, then the vertex indices
                ncol = nvx if mode & 0x10 else 1
                cols = [struct.unpack_from('<3B', chunk, q + 4 * k) for k in range(ncol)]
                if not mode & 1:
                    colour = tuple(sum(c[k] for c in cols) // ncol for k in range(3))
                vi = struct.unpack_from(f'<{nvx}H', chunk, q + 4 * ncol)
            elif mode & 0x10:               # lit, smooth: (normal, vertex) pairs
                vi = struct.unpack_from(f'<{2 * nvx}H', chunk, q)[1::2]
            else:                           # lit, flat: one normal, then the vertices
                vi = struct.unpack_from(f'<{nvx + 1}H', chunk, q)[1:]
            prims.append((list(vi), uvs, (cba - 0x7a08) // 0x40, (tsb >> 5) & 3 if mode & 2 else None, colour))
            p += size
        out.append((verts, prims))
    return out


def strip_image(chunk):
    """The chunk's TIM as dw2effect images: texel rows, then the palettes at row 32 on (clut = (32 + row) << 6)."""
    h = struct.unpack_from('<13i', chunk, 0)
    t = HEADER + h[7]
    clen, _x, _y, cw, ch = struct.unpack_from('<I4H', chunk, t + 8)
    clut = [list(struct.unpack_from(f'<{cw}H', chunk, t + 20 + 2 * cw * r)) for r in range(ch)]
    p = t + 8 + clen
    _plen, _x, _y, pw, ph = struct.unpack_from('<I4H', chunk, p)
    rows = [list(struct.unpack_from(f'<{pw}H', chunk, p + 12 + 2 * pw * r)) for r in range(ph)]
    width = max(pw, 16)
    img = [r + [0] * (width - len(r)) for r in rows] + [[0] * width for _ in range(32 - ph)]
    img += [r + [0] * (width - len(r)) for r in clut]
    return img


class _Prim:
    def __init__(self, verts, uvs, clut, blend, colour=None):
        self.verts, self.uvs, self.clut, self.blend, self.colour = verts, uvs, clut, blend, colour


SPRITE_UNIT = 32        # a sprite w texels wide at scale s (4096 = 1) is w * s / SPRITE_UNIT units wide


def _raster(px, W, H, q, uv, prim, image):
    """dw2effect's rasteriser with the prim's colour modulating the texture (128 = as is)."""
    from tools import dw2effect as D
    if prim.colour is None or prim.colour == (128, 128, 128):
        return D._raster(px, W, H, q, uv, prim, image)
    k = [c / 128 for c in prim.colour]
    sub = [None] * (W * H)
    D._raster(sub, W, H, q, uv, _Prim(prim.verts, prim.uvs, prim.clut, None), image)
    for i, c in enumerate(sub):
        if c is None:
            continue
        c = tuple(min(255, int(x * f)) for x, f in zip(c, k))
        px[i] = D._blend(px[i], c, prim.blend) if prim.blend is not None else c


def render(chunk, sim, tick, cam, fighters=True, bg=(28, 30, 40)):
    """The chunk's draws of one tick (TMD objects, projected sprites and quads) through the dw2effect rasteriser
    (and the fighters as grey posts)."""
    objs = tmd_objects(chunk)
    image = strip_image(chunk)
    W, H = cam.w, cam.h
    px = [bg] * (W * H)
    if fighters:
        for f in sim.fighters:
            if f is None:
                continue
            for y in range(0, f.height, 12):
                p = cam.project((f.pos[0], f.pos[1] - y, f.pos[2]))
                if p and 0 <= int(p[0]) < W and 0 <= int(p[1]) < H:
                    px[int(p[1]) * W + int(p[0])] = (110, 110, 130)
    tris = []
    for t, oid, rot, sc, pos, (du, dv), *rest in sim.draws:
        if t != tick or oid >= len(objs):
            continue
        order = rest[0] if rest else 'yxz'
        over = rest[1] if len(rest) > 1 else None
        m = (rot_yxz if order == 'yxz' else rot_xyz)(*[_wrap(x, 2) for x in rot])
        s = [x / 4096 for x in sc]
        verts, prims = objs[oid]
        pts = []
        for v in verts:
            q = [pos[i] + sum(m[i][k] * s[k] * v[k] for k in range(3)) for i in range(3)]
            pts.append(cam.project(q))
        for vi, uvs, row, blend, colour in prims:
            uvs = [((u + du) & 0xff, (v + dv) & 0xff) for u, v in uvs]
            pr = _Prim(vi, uvs, (32 + row) << 6, blend, colour if colour is None or over is None else over)
            for tri in ([(0, 1, 2)] if len(vi) == 3 else [(0, 1, 2), (1, 3, 2)]):
                q = [pts[vi[i]] if vi[i] < len(pts) else None for i in tri]
                if None in q:
                    continue
                tris.append((sum(x[2] for x in q) / 3, q, [uvs[i] for i in tri], pr))
    for t, pos, u, v, w, h, sx, sy, col, row, _rot, blend in sim.sprites:
        c = cam.project(pos)
        if t != tick or c is None:
            continue
        hw, hh = w * sx / SPRITE_UNIT / 2 * cam.focal / c[2], h * sy / SPRITE_UNIT / 2 * cam.focal / c[2]
        corners = [(c[0] - hw, c[1] - hh, c[2]), (c[0] + hw, c[1] - hh, c[2]), (c[0] - hw, c[1] + hh, c[2]),
                   (c[0] + hw, c[1] + hh, c[2])]
        uvs = [(u, v), (u + w - 1, v), (u, v + h - 1), (u + w - 1, v + h - 1)]
        pr = _Prim([0, 1, 2, 3], uvs, (32 + row) << 6, blend, tuple(int(x) for x in col))
        for tri in ((0, 1, 2), (1, 3, 2)):
            tris.append((c[2], [corners[i] for i in tri], [uvs[i] for i in tri], pr))
    for t, pts, u, v, du, dv, col, row, blend in sim.quads:
        q = [cam.project(p) for p in pts]
        if t != tick or None in q:
            continue
        uvs = [(u, v), (u + du, v), (u, v + dv), (u + du, v + dv)]
        pr = _Prim([0, 1, 2, 3], uvs, (32 + row) << 6, blend, tuple(int(x) for x in col))
        for tri in ((0, 1, 2), (1, 3, 2)):
            tris.append((sum(q[i][2] for i in tri) / 3, [q[i] for i in tri], [uvs[i] for i in tri], pr))
    tris.sort(key=lambda x: -x[0])
    for _z, q, uv, pr in tris:
        _raster(px, W, H, q, uv, pr, image)
    return px
