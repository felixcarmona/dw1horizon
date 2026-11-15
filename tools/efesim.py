#!/usr/bin/env python3
"""A model of Digimon World's battle effect engine (src/btl/battle_effect.c) for checking effect chunks offline.

It runs a chunk's scripts as BTL_runEFEScript does (the opcodes, call/return with the saved context and
target index, spawnEFESubEffect's search for a free instance and context, the tick and render passes) and the
sub-opcodes the DW2 converter (tools/dw2efe.py) uses, against mocked fighters. It records what the chunk
draws (drawTMDYXZ: object, rotation, scale, position), the hits it deals and the sounds it plays, and can draw
those frames with the chunk's own TMD and TIM.

Only what the converter's chunks need is modelled; another sub-opcode stops the run with an error.
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
    def __init__(self, chunk, fighters, caster, target):
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
            rx, ry_, rz = [_wrap(x, 2) for x in self.vec(r)]
            if rx or rz:
                raise RuntimeError('rotateVector with x or z angles is not modelled')
            m = ry(ry_)
            x = [_wrap(t, 2) for t in self.vec(v)]
            self.setvec(v, [_wrap(round(sum(m[i][k] * x[k] for k in range(3))), 2) for i in range(3)])
        elif name == 'drawTMDYXZ':
            sc, oid = st.pop(), st.pop()
            self.draws.append((self.tick, oid, tuple(self.vec(cur + 0x10)), tuple(self.vec(sc)),
                               tuple(self.vec(cur + 4)), tuple(self.uv[oid][3:]) if oid in self.uv else (0, 0)))
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
        else:
            raise RuntimeError(f'sub-opcode {name} not modelled')

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
    """[(vertices, [(vertex indices, uvs, palette row, blend or None)])] of the chunk's TMD."""
    h = struct.unpack_from('<13i', chunk, 0)
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
            quad = mode & 8
            nvx = 4 if quad else 3
            uvw = struct.unpack_from(f'<{nvx * 2}H', chunk, p + 4)
            uvs = [(uvw[2 * k] & 0xFF, uvw[2 * k] >> 8) for k in range(nvx)]
            cba, tsb = uvw[1], uvw[3]
            vi = struct.unpack_from(f'<{nvx}H', chunk, p + 4 + 4 * nvx + 4)
            prims.append((list(vi), uvs, (cba - 0x7a08) // 0x40, (tsb >> 5) & 3 if mode & 2 else None))
            p += 4 * (ilen + 1)
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
    def __init__(self, verts, uvs, clut, blend):
        self.verts, self.uvs, self.clut, self.blend = verts, uvs, clut, blend


def render(chunk, sim, tick, cam, fighters=True, bg=(28, 30, 40)):
    """The chunk's draws of one tick through the dw2effect rasteriser (and the fighters as grey posts)."""
    from tools import dw2effect as D
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
    for t, oid, rot, sc, pos, (du, dv) in sim.draws:
        if t != tick:
            continue
        m = rot_yxz(*[_wrap(x, 2) for x in rot])
        s = [x / 4096 for x in sc]
        verts, prims = objs[oid]
        pts = []
        for v in verts:
            q = [pos[i] + sum(m[i][k] * s[k] * v[k] for k in range(3)) for i in range(3)]
            pts.append(cam.project(q))
        for vi, uvs, row, blend in prims:
            uvs = [((u + du) & 0xff, (v + dv) & 0xff) for u, v in uvs]
            pr = _Prim(vi, uvs, (32 + row) << 6, blend)
            for tri in ([(0, 1, 2)] if len(vi) == 3 else [(0, 1, 2), (1, 3, 2)]):
                q = [pts[vi[i]] for i in tri]
                if None in q:
                    continue
                tris.append((sum(x[2] for x in q) / 3, q, [uvs[i] for i in tri], pr))
    tris.sort(key=lambda x: -x[0])
    for _z, q, uv, pr in tris:
        D._raster(px, W, H, q, uv, pr, image)
    return px
