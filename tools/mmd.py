#!/usr/bin/env python3
"""Digimon World (USA) MMD: reading, byte-exact writing, glTF and textures.

An .MMD (CHDAT/MMD0..5/*.MMD) is  u32 off_tmd (=8), u32 off_anim, a Psy-Q TMD
(one object per rigid piece) and the animation section interpreted by
decomp/src/main/anim.c. The skeleton is NOT in the file: it is the
DIGIMON_SKELETONS table of the executable (decomp/src/main/model.c:2305) and the
bone count is DIGIMON_DATA[type].boneCount. The texture is entry `type` of
CHDAT/ALLTIM.TIM (0x4800 bytes per Digimon). Full format: docs/mods/models.md.

Uses only the standard library (own PNG code with zlib).

Usage:
  mmd.py info MMD                          summary (objects, primitives, animations)
  mmd.py roundtrip [MMD ...]               byte-exact parse→write (all 178 by default) and
                                           normalization test (decodes/re-encodes everything)
  mmd.py gltf MMD OUT.gltf [--no-anim]     exports mesh + skeleton + animations + PNG
  mmd.py import-gltf BASE.MMD IN.gltf OUT.MMD
                                           rebuilds the TMD from a glTF (same skeleton) and
                                           keeps the animations of BASE
  mmd.py import-anim BASE.MMD IN.gltf OUT.MMD [--map GLTF_ANIM_NAME=SLOT ...] [--fps 20] [--tol 1]
                   [--loop NAME[=SECONDS]] [--no-loop NAME] [--keep-sounds] [--keep-tex] [--gltf-events]
                                           encodes glTF animations (same skeleton: nodes bone00..)
                                           as MMD keyframes into slots of BASE (replacing or adding);
                                           without --map, animNN names / extras.dw_slot pick the slot
  mmd.py anim-roundtrip [MMD ...]          export glTF → import-anim (exact) → compares the pose
                                           of every bone on every tick of every slot (all 178)
  mmd.py transplant MESH.MMD ANIM.MMD OUT.MMD
                                           TMD of MESH + animations of ANIM (same skeleton)
  mmd.py transform MMD OUT.MMD [--scale S] [--bone-scale BONE=S ...]
                                           scales the mesh (vertices) as a whole or per bone
  mmd.py tex-export TYPE OUT.png [--alltim F] [--mmd F]
  mmd.py tex-import TYPE IN.png OUT_ALLTIM [--alltim F] [--mmd F]
                                           replaces pixels and CLUT of entry TYPE
  mmd.py recolor TYPE OUT_ALLTIM [--alltim F] [--hue DEGREES] [--swap rgb→bgr...]
  mmd.py preview MMD OUT.png [--anim SLOT --tick N --yaw 0 90 180]
                                           software render (check without emulator or Blender)
  mmd.py copy-tex ORIG DEST OUT_ALLTIM [--alltim F]
                                           copies ALLTIM entry ORIG over DEST

TYPE is the Digimon index (0 = tamer, 3 = Agumon, 0x11 = Gabumon...), the one used by
DIGIMON_DATA and by the executable's name table.
"""
import argparse, glob, json, math, os, struct, sys, zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTRACTED = os.path.join(ROOT, 'extracted')
ALLTIM = os.path.join(EXTRACTED, 'CHDAT', 'ALLTIM.TIM')

# ---------------------------------------------------------------- executable
ALLTIM_STRIDE = 0x4800           # 9 sectors per entry (model.c:3285, readFileSectors(type*9, 9))


class Exe:
    """Executable tables a model needs: name, bones, skeleton. The disc's 180 types come from the committed tables
    (tools/species.py originals(): content/tables/disc-species.json, skeletons.json), not from the disc's executable
    (rule: a European disc has another one): names (the model file names, AGUM, GABU...), para (DigimonPara, 0x34
    bytes), bone_count, skeleton [(objIndex, parentIndex)...] and skel_ptr, the name of the DIGIMON_SKELETONS array
    (SKELETON_AGUMON...): types with the same skel_ptr share one skeleton array, as the pointers of the executable did."""

    def __init__(self, include_imports=True):
        import species
        O = species.originals()
        self.names, self.bone_count, self.skel_ptr, self.skeleton, self.para = [], [], [], [], []
        for t in range(species.NUM_ORIGINAL):
            r = O.rec[t]
            self.names.append(r['modelName'])
            self.para.append(species.pack(species.PARA_FIELDS, r['para']))
            self.bone_count.append(r['para']['boneCount'])
            self.skel_ptr.append(O.skeleton_name[t])
            self.skeleton.append([tuple(b) for b in r['bones']])
        if include_imports:
            self._add_new_species()

    def _add_new_species(self):
        """Species 180.. of content/species/*.json (tools/species.py): name, bone count and
        skeleton, so preview/animsheet/retarget/import-anim work with `--type 182`."""
        try:
            import species
            new = species.imports()
            for t in sorted(new):
                if t < len(self.names):
                    break
                while len(self.names) < t:           # rule: a gap in the ids (301 is left to an experiment) is an undefined type
                    self.names.append(''); self.para.append(b'\0' * 0x34); self.bone_count.append(0)
                    self.skel_ptr.append(None); self.skeleton.append([])
                r = species.species_record(new[t])
                self.names.append('')
                self.para.append(species.pack(species.PARA_FIELDS, dict(r['para'], padding=0)))
                self.bone_count.append(len(r['bones']))
                self.skel_ptr.append(None)
                self.skeleton.append([tuple(b) for b in r['bones']])
        except (ImportError, SystemExit, KeyError, OSError):
            pass

    def add_type(self, t, bones, name=''):
        """Registers (or replaces) a type that is not in the executable: its skeleton
        [(objIndex, parentIndex)...] (tools/dcb2mmd.py, before its species JSON exists)."""
        while len(self.names) <= t:
            self.names.append(''); self.para.append(b'\0' * 0x34); self.bone_count.append(0)
            self.skel_ptr.append(None); self.skeleton.append([])
        self.bone_count[t] = len(bones)
        self.skeleton[t] = [tuple(b) for b in bones]
        p = bytearray(self.para[t]); p[:20] = name.encode()[:19].ljust(20, b'\0')
        struct.pack_into('<i', p, 20, len(bones)); self.para[t] = bytes(p)

    def type_of(self, path):
        base = os.path.splitext(os.path.basename(path))[0].upper()
        if base in self.names:
            return self.names.index(base)
        raise SystemExit(f'{path}: the name {base} is not in the executable\'s Digimon table; use --type')

    def name(self, t):
        return self.para[t][:20].split(b'\0')[0].decode('ascii', 'replace')


_EXE = None


def exe():
    global _EXE
    if _EXE is None:
        _EXE = Exe()
    return _EXE


# ---------------------------------------------------------------- TMD
# mode (byte 3 of the primitive header): bit0 TGE (no brightness), bit1 ABE (semi-transparent),
# bit2 TME (texture), bit3 quad, bit4 IIP (Gouraud), bits 5-7 code (1 = polygon).
# flag (byte 2): bit0 LGT (unlit), bit1 FCE (double-sided), bit2 GRD (gradient).
OLEN = {0x24: 7, 0x25: 7, 0x26: 7, 0x27: 7, 0x2C: 9, 0x2D: 9, 0x2E: 9, 0x2F: 9,
        0x34: 9, 0x35: 9, 0x36: 9, 0x37: 9, 0x3C: 12, 0x3D: 12, 0x3E: 12, 0x3F: 12,
        0x20: 4, 0x28: 5, 0x30: 6, 0x38: 8, 0x21: 4, 0x29: 5, 0x31: 6, 0x39: 8}


def prim_shape(mode, flag):
    """How many UVs, colors and normals a polygon primitive carries (Psy-Q TMD)."""
    tex, quad, gour = bool(mode & 4), bool(mode & 8), bool(mode & 16)
    light = not (flag & 1)
    nv = 4 if quad else 3
    nuv = nv if tex else 0
    if light:
        ncol = 0 if tex else (nv if (flag & 4) else 1)
        nnorm = nv if gour else 1
    else:
        ncol = nv if (gour or flag & 4) else 1
        nnorm = 0
    return nv, nuv, ncol, nnorm


class Prim:
    """Polygon primitive. Stored raw (exact round trip) and decoded into fields."""
    __slots__ = ('raw',)

    def __init__(self, raw):
        self.raw = bytes(raw)

    @property
    def olen(self): return self.raw[0]
    @property
    def ilen(self): return self.raw[1]
    @property
    def flag(self): return self.raw[2]
    @property
    def mode(self): return self.raw[3]

    def decode(self):
        mode, flag = self.mode, self.flag
        if mode >> 5 != 1:
            raise ValueError(f'non-polygon primitive: mode {mode:#x}')
        nv, nuv, ncol, nnorm = prim_shape(mode, flag)
        w = struct.unpack_from('<%dI' % self.ilen, self.raw, 4)
        k = 0
        out = dict(mode=mode, flag=flag, olen=self.olen, uv=[], cba=None, tsb=None, uvpad=[], colors=[],
                   norms=[], verts=[], pad=[])
        for i in range(nuv):
            x = w[k]; k += 1
            out['uv'].append((x & 0xFF, (x >> 8) & 0xFF))
            hi = x >> 16
            if i == 0: out['cba'] = hi
            elif i == 1: out['tsb'] = hi
            else: out['uvpad'].append(hi)
        for i in range(ncol):
            x = w[k]; k += 1
            out['colors'].append((x & 0xFF, (x >> 8) & 0xFF, (x >> 16) & 0xFF, x >> 24))
        hw = []
        for x in w[k:]:
            hw += [x & 0xFFFF, x >> 16]
        j = 0
        if nnorm == nv:              # Gouraud: (n_i, v_i)
            for i in range(nv):
                out['norms'].append(hw[j]); out['verts'].append(hw[j + 1]); j += 2
        elif nnorm == 1:             # flat: n0 v0 v1 v2 [v3]
            out['norms'].append(hw[0]); j = 1
            for i in range(nv):
                out['verts'].append(hw[j]); j += 1
        else:                        # unlit: v0 v1 v2 [v3]
            for i in range(nv):
                out['verts'].append(hw[j]); j += 1
        out['pad'] = hw[j:]
        return out

    @staticmethod
    def encode(p):
        mode, flag = p['mode'], p['flag']
        nv, nuv, ncol, nnorm = prim_shape(mode, flag)
        w = []
        uvpad = list(p.get('uvpad') or [])
        for i in range(nuv):
            u, v = p['uv'][i]
            hi = p['cba'] if i == 0 else p['tsb'] if i == 1 else (uvpad[i - 2] if i - 2 < len(uvpad) else 0)
            w.append((u & 0xFF) | (v & 0xFF) << 8 | (hi & 0xFFFF) << 16)
        for i in range(ncol):
            r, g, b, c = p['colors'][i]
            w.append(r | g << 8 | b << 16 | c << 24)
        hw = []
        if nnorm == nv:
            for i in range(nv):
                hw += [p['norms'][i], p['verts'][i]]
        elif nnorm == 1:
            hw = [p['norms'][0]] + list(p['verts'][:nv])
        else:
            hw = list(p['verts'][:nv])
        pad = list(p.get('pad') or [])
        if len(hw) % 2:
            hw.append(pad[0] if pad else 0)
        for i in range(0, len(hw), 2):
            w.append(hw[i] | hw[i + 1] << 16)
        olen = p.get('olen') or OLEN.get(mode, 0)
        return Prim(struct.pack('<BBBB', olen, len(w), flag, mode) + struct.pack('<%dI' % len(w), *w))


class TMDObject:
    def __init__(self):
        self.prims = []        # [Prim]
        self.vert_start = 0    # index into the vertex pool
        self.nvert = 0
        self.norm_start = 0
        self.nnorm = 0
        self.scale = 0


class TMD:
    """TMD as the MMDs write it: header, object table, all primitives (in object order),
    all vertices, all normals. Vertices and normals are kept as global pools with
    (start, count) per object: TANE.MMD overlaps normals."""

    def __init__(self):
        self.id, self.flags = 0x41, 0
        self.objects = []
        self.verts = []        # (x, y, z, pad) int16
        self.norms = []        # (x, y, z, pad) int16, 4.12

    @classmethod
    def parse(cls, d, base):
        t = cls()
        t.id, t.flags, nobj = struct.unpack_from('<III', d, base)
        if t.id != 0x41:
            raise ValueError('not a TMD')
        o0 = base + 12
        raw = [struct.unpack_from('<IIIIIIi', d, o0 + 28 * i) for i in range(nobj)]
        vmin = min((r[0] for r in raw if r[1]), default=0)
        nmin = min((r[2] for r in raw if r[3]), default=min((r[2] for r in raw), default=0))   # no normals at all (flat model): an empty block where the objects point
        vmax = max((r[0] + 8 * r[1] for r in raw), default=0)
        nmax = max((r[2] + 8 * r[3] for r in raw), default=0)
        t.verts = [struct.unpack_from('<4h', d, o0 + o) for o in range(vmin, vmax, 8)]
        t.norms = [struct.unpack_from('<4h', d, o0 + o) for o in range(nmin, nmax, 8)]
        t._layout = (vmin, nmin)
        for (vt, nv, nt, nn, pt, np_, sc) in raw:
            ob = TMDObject()
            assert (vt - vmin) % 8 == 0 and (nt - nmin) % 8 == 0
            ob.vert_start, ob.nvert = (vt - vmin) // 8, nv
            ob.norm_start, ob.nnorm = (nt - nmin) // 8, nn
            ob.scale = sc
            p = o0 + pt
            for _ in range(np_):
                ln = 4 + d[p + 1] * 4
                ob.prims.append(Prim(d[p:p + ln]))
                p += ln
            t.objects.append(ob)
        return t

    def obj_verts(self, i):
        o = self.objects[i]; return self.verts[o.vert_start:o.vert_start + o.nvert]

    def obj_norms(self, i):
        # the GTE reads normal_top + 8·index without checking n_normal: TANE.MMD (objects 0 and 1)
        # uses indices beyond its count and reads the normals of the next object
        o = self.objects[i]; return self.norms[o.norm_start:]

    def build(self):
        n = len(self.objects)
        head = 28 * n
        prim_off, pos = [], head
        body = bytearray()
        for ob in self.objects:
            prim_off.append(pos)
            for p in ob.prims:
                body += p.raw
            pos = head + len(body)
        vbase = pos
        for v in self.verts:
            body += struct.pack('<4h', *v)
        nbase = head + len(body)
        for v in self.norms:
            body += struct.pack('<4h', *v)
        tab = bytearray()
        for i, ob in enumerate(self.objects):
            tab += struct.pack('<IIIIIIi', vbase + 8 * ob.vert_start, ob.nvert, nbase + 8 * ob.norm_start,
                               ob.nnorm, prim_off[i], len(ob.prims), ob.scale)
        return struct.pack('<III', self.id, self.flags, n) + bytes(tab) + bytes(body)


# ---------------------------------------------------------------- animations
CHANNELS = ['sx', 'sy', 'sz', 'rx', 'ry', 'rz', 'tx', 'ty', 'tz']   # bit 14 → sx ... bit 6 → tz (anim.c:381-389)


class Anim:
    """One animation: frameCount (bit 15 = the initial pose includes scale), initial pose of
    bones 1..n-1 and instruction list (anim.c:201-357)."""

    def __init__(self):
        self.frame_count = 0
        self.has_scale = False
        self.pose = []          # per bone 1..n-1: [sx,sy,sz,]rx,ry,rz,tx,ty,tz
        self.instrs = []        # dicts
        self.tail = b''         # bytes after the terminator up to the next animation

    @classmethod
    def parse(cls, d, start, end, nbones):
        a = cls()
        w0 = struct.unpack_from('<H', d, start)[0]
        a.frame_count, a.has_scale = w0 & 0x7FFF, bool(w0 & 0x8000)
        per = 9 if a.has_scale else 6
        p = start + 2
        for _ in range(nbones - 1):
            a.pose.append(list(struct.unpack_from('<%dh' % per, d, p))); p += 2 * per
        H = lambda q: struct.unpack_from('<H', d, q)[0]
        h = lambda q: struct.unpack_from('<h', d, q)[0]
        while p + 2 <= end:
            w = H(p)
            op = w >> 12
            if w == 0:                       # frame 0 is never reached: end of the animation
                a.instrs.append(dict(op='end')); p += 2
                break
            if op == 0:
                ins = dict(op='key', frame=w & 0xFFF, bones=[]); p += 2
                while p + 2 <= end and H(p) & 0x8000:
                    b = H(p); div = h(p + 2); p += 4
                    vals = {}
                    for i, ch in enumerate(CHANNELS):
                        if b & (0x4000 >> i):
                            vals[ch] = h(p); p += 2
                    ins['bones'].append(dict(bone=b & 0x3F, div=div, vals=vals))
            elif op == 1:
                ins = dict(op='loop_start', count=w & 0xFF, raw=w); p += 2
            elif op == 2:
                ins = dict(op='loop_end', frame=w & 0xFFF, jump=H(p + 2)); p += 4
            elif op == 3:
                a1, a2, a3 = H(p + 2), H(p + 4), H(p + 6)
                ins = dict(op='tex', frame=w & 0xFFF, src=(a1 >> 8, a1 & 0xFF), size=(a2 >> 8, a2 & 0xFF),
                           dst=(a3 >> 8, a3 & 0xFF)); p += 8
            elif op == 4:
                a1 = H(p + 2)
                ins = dict(op='sound', frame=w & 0xFFF, bank=a1 >> 8, note=a1 & 0xFF); p += 4
            else:
                raise ValueError(f'unknown animation opcode {w:#06x} at {p:#x}')
            a.instrs.append(ins)
        a.tail = bytes(d[p:end])
        return a

    def build(self):
        out = bytearray(struct.pack('<H', self.frame_count | (0x8000 if self.has_scale else 0)))
        for v in self.pose:
            out += struct.pack('<%dh' % len(v), *v)
        for ins in self.instrs:
            op = ins['op']
            if op == 'end':
                out += b'\0\0'
            elif op == 'key':
                out += struct.pack('<H', ins['frame'])
                for b in ins['bones']:
                    m = 0
                    for i, ch in enumerate(CHANNELS):
                        if ch in b['vals']:
                            m |= 0x4000 >> i
                    out += struct.pack('<Hh', 0x8000 | m | b['bone'], b['div'])
                    for ch in CHANNELS:
                        if ch in b['vals']:
                            out += struct.pack('<h', b['vals'][ch])
            elif op == 'loop_start':
                out += struct.pack('<H', ins.get('raw', 0x1000 | ins['count']))
            elif op == 'loop_end':
                out += struct.pack('<HH', 0x2000 | ins['frame'], ins['jump'])
            elif op == 'tex':
                (sx, sy), (w, hh), (dx, dy) = ins['src'], ins['size'], ins['dst']
                out += struct.pack('<4H', 0x3000 | ins['frame'], sx << 8 | sy, w << 8 | hh, dx << 8 | dy)
            elif op == 'sound':
                out += struct.pack('<HH', 0x4000 | ins['frame'], ins['bank'] << 8 | ins['note'])
        return bytes(out) + self.tail


class AnimSection:
    """Table of u32 (offsets relative to the table itself, 0 = absent) + animations.
    The table size is not stored: it is min(non-zero offsets)/4."""

    def __init__(self):
        self.table = []        # per slot: index into self.anims or None
        self.anims = []        # in order of appearance in the file
        self.raw = b''         # whole section (for MMDs with unknown bone count)

    @classmethod
    def parse(cls, d, start, end, nbones):
        s = cls()
        s.raw = bytes(d[start:end])
        # table size = smallest non-zero offset
        offs, i = [], 0
        while True:
            o = struct.unpack_from('<I', d, start + 4 * i)[0]
            offs.append(o)
            i += 1
            nz = [x for x in offs if x]
            if nz and 4 * i >= min(nz):
                break
        n = min(x for x in offs if x) // 4
        offs = offs[:n]
        uniq = sorted(set(x for x in offs if x))
        bounds = uniq + [end - start]
        idx = {}
        for k, o in enumerate(uniq):
            idx[o] = k
            if nbones is not None:
                s.anims.append(Anim.parse(d, start + o, start + bounds[k + 1], nbones))
        s.table = [idx[o] if o else None for o in offs]
        s.offsets = uniq
        return s

    def build(self):
        head = 4 * len(self.table)
        body, offs = bytearray(), []
        for a in self.anims:
            offs.append(head + len(body))
            body += a.build()                 # unaligned: the original sometimes pads with 0xCDCD (.tail)
        tab = b''.join(struct.pack('<I', offs[k] if k is not None else 0) for k in self.table)
        return tab + bytes(body)


class MMD:
    def __init__(self):
        self.tmd = None
        self.anims = None
        self.type = None
        self.nbones = None

    @classmethod
    def parse(cls, data, nbones=None):
        m = cls()
        off_tmd, off_anim = struct.unpack_from('<II', data, 0)
        if off_tmd != 8:
            raise ValueError('off_tmd != 8')
        m.tmd = TMD.parse(data, off_tmd)
        m.anims = AnimSection.parse(data, off_anim, len(data), nbones)
        m.nbones = nbones
        return m

    @classmethod
    def load(cls, path, typ=None):
        e = exe()
        t = e.type_of(path) if typ is None else typ
        m = cls.parse(open(path, 'rb').read(), e.bone_count[t])
        m.type = t
        return m

    def build(self):
        tmd = self.tmd.build()
        an = self.anims.build()
        return struct.pack('<II', 8, 8 + len(tmd)) + tmd + an


# ---------------------------------------------------------------- animation simulation
def rot_matrix(rx, ry, rz):
    """libgte RotMatrix: M = Rx·Ry·Rz, angles in 1/4096 of a turn."""
    k = 2 * math.pi / 4096
    cx, sx, cy, sy, cz, sz = math.cos(rx * k), math.sin(rx * k), math.cos(ry * k), math.sin(ry * k), math.cos(rz * k), math.sin(rz * k)
    return [[cy * cz, -cy * sz, sy],
            [sx * sy * cz + cx * sz, -sx * sy * sz + cx * cz, -sx * cy],
            [-cx * sy * cz + sx * sz, cx * sy * sz + sx * cz, cx * cy]]


def quat(rx, ry, rz):
    """Quaternion (x,y,z,w) of Rx·Ry·Rz."""
    k = math.pi / 4096
    c1, s1, c2, s2, c3, s3 = math.cos(rx * k), math.sin(rx * k), math.cos(ry * k), math.sin(ry * k), math.cos(rz * k), math.sin(rz * k)
    return (s1 * c2 * c3 + c1 * s2 * s3, c1 * s2 * c3 - s1 * c2 * s3, c1 * c2 * s3 + s1 * s2 * c3, c1 * c2 * c3 - s1 * s2 * s3)


def s16(v):
    return ((v + 0x8000) & 0xFFFF) - 0x8000


def rot_scale_matrix(v):
    """posMatrix of a bone (calculatePosMatrix): RotMatrix · ScaleMatrix, scale in 4.12."""
    R = rot_matrix(*v[3:6])
    return [[R[i][j] * v[j] / 4096 for j in range(3)] for i in range(3)]


class AnimPlayer:
    """tickAnimation (anim.c:276-357) tick by tick, integer-exact: momentum with its
    remainder counters (animReadMomentumInstruction/animApplyMomentum), rotations stored
    as int16 (SVECTOR), the `instruction & 0x1000` pre-check, loops with a u8 counter.

    After each tick: `pose[b]` = 9 values (sx sy sz rx ry rz tx ty tz) of every bone; for
    bone 0 tx..tz stay 0 and the root motion of the tick (the momentum of bone 0's
    translation, in its own frame, applyRootMomentum) is in `base`; `root` accumulates it in
    the parent frame like the game (R·S of bone 0 applied, as floats). `events` holds
    (sample, kind, data) with sample = tick − 1 (the pose index the tick produces)."""

    def __init__(self, anim, nbones, slot=None):
        self.anim, self.nb, self.slot = anim, nbones, slot
        self.pose = [[4096, 4096, 4096, 0, 0, 0, 0, 0, 0] for _ in range(nbones)]
        for b in range(1, nbones):
            v = anim.pose[b - 1]
            self.pose[b] = list(v) if anim.has_scale else [4096, 4096, 4096] + list(v)
        self.mom = [[[0, 0, 0, 0, 0] for _ in range(9)] for _ in range(nbones)]   # delta sub reload counter sign
        self.ip, self.frame, self.loop_end_frame, self.loop_count, self.loop_start = 0, 1, 1, 0, 0
        self.running, self.ticks = True, 0
        self.base, self.root = [0, 0, 0], [0.0, 0.0, 0.0]
        self.events = []
        self.frames = []                 # frame counter of each tick (before the increment)
        self.loop_start_tick = None
        self.jumps = []                  # (tick, target frame, infinite)

    def _cur(self):
        ins = self.anim.instrs
        return ins[self.ip] if self.ip < len(ins) else dict(op='end')

    def _word(self):
        c = self._cur()
        op = c['op']
        if op == 'loop_start':
            return c.get('raw', 0x1000 | c['count'])
        if op == 'end':
            return 0
        return dict(key=0, loop_end=0x2000, tex=0x3000, sound=0x4000)[op] | c['frame']

    def tick(self, stop_at_infinite_loop=False):
        if not self.running:
            return False
        self.ticks += 1
        sample = self.ticks - 1
        P, M = self.pose, self.mom
        for b in range(self.nb):                                    # tickMomentum
            for j in range(9):
                m = M[b][j]
                if m[0] == 0 and m[1] == 0:
                    continue
                if b == 0 and j >= 6:
                    break
                v = P[b][j] + m[0]
                if m[1]:
                    m[3] -= m[1]
                    if m[3] <= 0:
                        m[3] += m[2]
                        v += m[4]
                P[b][j] = s16(v) if 3 <= j < 6 else v
        base = []                                                   # applyRootMomentum
        for i in range(3):
            m = M[0][6 + i]
            if i == 0 and self.slot in (0x23, 0x24):
                base.append(0)
                continue
            v = m[0]
            if m[1]:
                m[3] -= m[1]
                if m[3] <= 0:
                    m[3] += m[2]
                    v += m[4]
            base.append(v)
        self.base = base
        if any(base):
            R = rot_scale_matrix(P[0])
            for i in range(3):
                self.root[i] += sum(R[i][k] * base[k] for k in range(3))
        self.frames.append(self.frame)
        w = self._word()
        if w & 0x1000:                   # literal pre-check: also true for a pending texture instruction
            c = self._cur()
            if c['op'] == 'tex':
                self.events.append((sample, 'tex_quirk', c))
            self.loop_count = w & 0xFF
            self.ip += 1
            self.loop_start = self.ip
            self.loop_end_frame = self._word() & 0xFFF
            self.loop_start_tick = self.ticks
        guard = 0
        while self.frame == self.loop_end_frame:
            guard += 1
            if guard > 100000:
                raise RuntimeError('animation stuck in a zero-length loop')
            c = self._cur()
            op = c['op']
            if op == 'key':
                for bb in c['bones']:
                    div = bb['div']
                    for i, ch in enumerate(CHANNELS):
                        if ch in bb['vals']:
                            val = bb['vals'][ch]
                            q = int(val / div)           # C division and remainder (toward 0)
                            r = val - q * div
                            m = M[bb['bone']][i]
                            m[0], m[1] = q, abs(r)
                            if r:
                                m[4] = 1 if r > 0 else -1
                                m[2] = m[3] = div
                self.ip += 1
            elif op == 'loop_start':
                self.loop_count = c['count']
                self.ip += 1
                self.loop_start = self.ip
                self.loop_start_tick = self.ticks
            elif op == 'loop_end':
                if self.loop_count != 0xFF:
                    self.loop_count = (self.loop_count - 1) & 0xFF
                if self.loop_count == 0:
                    self.ip += 1
                else:
                    infinite = self.loop_count == 0xFF
                    self.jumps.append((self.ticks, c['jump'], infinite))
                    if infinite and stop_at_infinite_loop:
                        self.running = False
                        return True
                    self.frame = c['jump']
                    self.ip = self.loop_start
            elif op == 'tex':
                self.events.append((sample, 'tex', c))
                self.ip += 1
            elif op == 'sound':
                self.events.append((sample, 'sound', c))
                self.ip += 1
            else:
                break
            self.loop_end_frame = self._word() & 0xFFF
        if self.frame == self.anim.frame_count:
            self.running = False
        else:
            self.frame = s16(self.frame + 1)
        return True

    def loop_sample(self):
        """For an animation that reached an infinite loop: the sample the loop body starts
        from. The jump at tick N sets the frame to J and re-runs the instructions of frame J,
        so tick N+k repeats the motion of tick T_J+k, where T_J is the tick that ran frame J
        after the loop start (checked on all 1242 infinite loops of the 178 MMDs)."""
        inf = [j for j in self.jumps if j[2]]
        if not inf:
            return None
        tick, target, _ = inf[0]
        start = self.loop_start_tick or 1
        for t in range(start, tick + 1):
            if self.frames[t - 1] == target:
                return t - 1
        return None


def simulate(anim, nbones, max_ticks=6000, slot=None):
    """Plays the animation like anim.c. Returns (poses, info): poses[k][b] = 9 values after
    tick k+1 (k = sample, 20 per second); bone 0 carries the accumulated root motion (floats).
    Infinite loops are played once: info['loop'] = (jump frame, loop end frame) and
    info['loop_sample'] = sample whose motion follows the last one."""
    p = AnimPlayer(anim, nbones, slot)
    out = []
    while len(out) < max_ticks and p.tick(stop_at_infinite_loop=True):
        snap = [list(v) for v in p.pose]
        snap[0][6:9] = list(p.root)
        out.append(snap)
    info = dict(loop=None, loop_sample=None)
    inf = [j for j in p.jumps if j[2]]
    if inf:
        info['loop'] = (inf[0][1], p.frames[inf[0][0] - 1])
        info['loop_sample'] = p.loop_sample()
    info['sounds'] = [(k, c['bank'], c['note']) for k, kind, c in p.events if kind == 'sound']
    info['texs'] = [(k, c) for k, kind, c in p.events if kind == 'tex']
    info['tex_quirk'] = any(kind == 'tex_quirk' for _, kind, _ in p.events)
    return out, info


# ---------------------------------------------------------------- minimal PNG
def png_write(path, w, h, rgba):
    raw = b''.join(b'\0' + bytes(rgba[y * w * 4:(y + 1) * w * 4]) for y in range(h))
    chunk = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xFFFFFFFF)
    open(path, 'wb').write(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
                           + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def png_read(path):
    d = open(path, 'rb').read()
    assert d[:8] == b'\x89PNG\r\n\x1a\n', 'not a PNG'
    p, idat, plte, trns = 8, b'', None, None
    while p < len(d):
        n, t = struct.unpack_from('>I4s', d, p)
        c = d[p + 8:p + 8 + n]
        if t == b'IHDR':
            w, h, bd, ct, _, _, il = struct.unpack('>IIBBBBB', c)
        elif t == b'PLTE': plte = c
        elif t == b'tRNS': trns = c
        elif t == b'IDAT': idat += c
        p += 12 + n
    if bd != 8 or il:
        raise SystemExit('PNG: only 8 bits per channel and no interlacing')
    ch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ct]
    raw = zlib.decompress(idat)
    stride = w * ch
    out, prev, q = bytearray(), bytearray(stride), 0
    for y in range(h):
        f = raw[q]; line = bytearray(raw[q + 1:q + 1 + stride]); q += 1 + stride
        for i in range(stride):
            a = line[i - ch] if i >= ch else 0
            b = prev[i]
            c2 = prev[i - ch] if i >= ch else 0
            if f == 1: line[i] = (line[i] + a) & 255
            elif f == 2: line[i] = (line[i] + b) & 255
            elif f == 3: line[i] = (line[i] + (a + b) // 2) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c2), abs(a - c2), abs(a + b - 2 * c2)
                pr = a if pa <= pb and pa <= pc else b if pb <= pc else c2
                line[i] = (line[i] + pr) & 255
        out += line; prev = line
    rgba = bytearray()
    for i in range(w * h):
        px = out[i * ch:(i + 1) * ch]
        if ct == 6: rgba += px
        elif ct == 2: rgba += px + b'\xff'
        elif ct == 0: rgba += bytes([px[0]] * 3) + b'\xff'
        elif ct == 4: rgba += bytes([px[0]] * 3) + px[1:2]
        else:
            k = px[0]
            rgba += plte[3 * k:3 * k + 3] + bytes([trns[k] if trns and k < len(trns) else 255])
    return w, h, rgba


# ---------------------------------------------------------------- ALLTIM / texture
class Tim4:
    """ALLTIM.TIM entry: 4 bpp TIM with a 16×N CLUT (N = 1..16 palettes) and a 64×128-word
    image = 256×128 pixels. The VRAM position in the file is ignored (model.c:3543-3564)."""

    def __init__(self, blob):
        self.blob = bytearray(blob)
        magic, flag = struct.unpack_from('<II', blob, 0)
        assert magic == 0x10 and flag == 8, 'ALLTIM: expected a 4 bpp TIM with CLUT'
        self.clen, self.cx, self.cy, self.cw, self.ch = struct.unpack_from('<IHHHH', blob, 8)
        self.pal = [list(struct.unpack_from('<16H', blob, 20 + 32 * r)) for r in range(self.ch)]
        po = 8 + self.clen
        self.plen, self.px, self.py, self.pw, self.ph = struct.unpack_from('<IHHHH', blob, po)
        self.w, self.h = self.pw * 4, self.ph
        pix = blob[po + 12:po + 12 + self.pw * 2 * self.ph]
        self.idx = bytearray(self.w * self.h)
        for i, b in enumerate(pix):
            self.idx[2 * i] = b & 15
            self.idx[2 * i + 1] = b >> 4

    def to_bytes(self):
        b = self.blob
        for r in range(self.ch):
            struct.pack_into('<16H', b, 20 + 32 * r, *self.pal[r])
        po = 8 + self.clen + 12
        for i in range(len(self.idx) // 2):
            b[po + i] = self.idx[2 * i] | self.idx[2 * i + 1] << 4
        return bytes(b)


def c15_to_rgba(c):
    r, g, b = (c & 31) << 3, (c >> 5 & 31) << 3, (c >> 10 & 31) << 3
    r, g, b = r | r >> 5, g | g >> 5, b | b >> 5
    return (r, g, b, 0 if c == 0 else 255)


def rgba_to_c15(r, g, b, a=255):
    if a < 128:
        return 0
    c = (r >> 3) | (g >> 3) << 5 | (b >> 3) << 10
    return c or 0x8000              # opaque black = 0x8000 (0x0000 is transparent)


def alltim_entry(data, t):
    return data[t * ALLTIM_STRIDE:(t + 1) * ALLTIM_STRIDE]


def palette_map(m, tim):
    """Which CLUT row each texture pixel uses: the UV triangles of each textured primitive are
    rasterized with its row (CBA − 0x7A00) >> 6; uncovered pixels take the most frequent row
    of their 8×8 block, and texture animations (op 0x3000) copy the map from the destination
    to their source (eyelids, mouths)."""
    W, H = tim.w, tim.h
    pm = [-1] * (W * H)

    def tri(a, b, c, row):
        xs, ys = [a[0], b[0], c[0]], [a[1], b[1], c[1]]
        for y in range(max(0, min(ys)), min(H - 1, max(ys)) + 1):
            for x in range(max(0, min(xs)), min(W - 1, max(xs)) + 1):
                def e(p, q):
                    return (q[0] - p[0]) * (y + .5 - p[1]) - (q[1] - p[1]) * (x + .5 - p[0])
                e1, e2, e3 = e(a, b), e(b, c), e(c, a)
                if (e1 >= -1 and e2 >= -1 and e3 >= -1) or (e1 <= 1 and e2 <= 1 and e3 <= 1):
                    pm[y * W + x] = row
    for ob in m.tmd.objects:
        for p in ob.prims:
            if not p.mode & 4:
                continue
            d = p.decode()
            row = ((d['cba'] >> 6) - 488) if d['cba'] >> 6 >= 488 else 0
            uv = d['uv']
            tri(uv[0], uv[1], uv[2], row)
            if len(uv) == 4:
                tri(uv[1], uv[2], uv[3], row)
    for a in (m.anims.anims if m.anims else []):
        for ins in a.instrs:
            if ins['op'] == 'tex':
                (sx, sy), (w, h), (dx, dy) = ins['src'], ins['size'], ins['dst']
                for y in range(h):
                    for x in range(w * 4):
                        s = (sy + y) * W + sx * 4 + x
                        dd = (dy + y) * W + dx * 4 + x
                        if 0 <= s < W * H and 0 <= dd < W * H and pm[s] < 0:
                            pm[s] = pm[dd]
    out = list(pm)
    for by in range(0, H, 8):
        for bx in range(0, W, 8):
            cnt = {}
            for y in range(by, by + 8):
                for x in range(bx, bx + 8):
                    r = pm[y * W + x]
                    if r >= 0: cnt[r] = cnt.get(r, 0) + 1
            best = max(cnt, key=cnt.get) if cnt else 0
            for y in range(by, by + 8):
                for x in range(bx, bx + 8):
                    if out[y * W + x] < 0: out[y * W + x] = best
    return [min(r, tim.ch - 1) for r in out]


def texture_rgba(m, tim):
    pm = palette_map(m, tim)
    rgba = bytearray()
    for i, k in enumerate(tim.idx):
        rgba += bytes(c15_to_rgba(tim.pal[pm[i]][k]))
    return rgba


def quantize(colors, n):
    """Simple median cut: list of (r,g,b) → at most n colors."""
    boxes = [list(colors)]
    while len(boxes) < n:
        boxes.sort(key=lambda b: -len(b))
        b = boxes[0]
        if len(b) < 2: break
        rng = [max(c[i] for c in b) - min(c[i] for c in b) for i in range(3)]
        ax = rng.index(max(rng))
        if rng[ax] == 0: break
        b.sort(key=lambda c: c[ax])
        boxes = boxes[1:] + [b[:len(b) // 2], b[len(b) // 2:]]
    return [tuple(sum(c[i] for c in b) // len(b) for i in range(3)) for b in boxes if b]


def tex_import(m, tim, w, h, rgba):
    if (w, h) != (tim.w, tim.h):
        raise SystemExit(f'the PNG must be {tim.w}×{tim.h}')
    pm = palette_map(m, tim)
    for row in range(tim.ch):
        px = [i for i in range(w * h) if pm[i] == row]
        if not px:
            continue
        opaque = [tuple(rgba[4 * i:4 * i + 3]) for i in px if rgba[4 * i + 3] >= 128]
        trans = any(rgba[4 * i + 3] < 128 for i in px)
        uniq = sorted(set((r >> 3 << 3, g >> 3 << 3, b >> 3 << 3) for r, g, b in opaque))
        slots = 15 if trans else 16
        pal = uniq if len(uniq) <= slots else quantize([(r >> 3 << 3, g >> 3 << 3, b >> 3 << 3) for r, g, b in opaque], slots)
        newpal = ([0] if trans else []) + [((r >> 3) | (g >> 3) << 5 | (b >> 3) << 10) or 0x8000 for r, g, b in pal]
        newpal += [0] * (16 - len(newpal))
        tim.pal[row] = newpal
        cols = [c15_to_rgba(c) for c in newpal]
        start = 1 if trans else 0
        cache = {}
        for i in px:
            r, g, b, a = rgba[4 * i:4 * i + 4]
            if a < 128:
                tim.idx[i] = 0; continue
            key = (r, g, b)
            if key not in cache:
                cache[key] = min(range(start, start + len(pal)),
                                 key=lambda k: (cols[k][0] - r) ** 2 + (cols[k][1] - g) ** 2 + (cols[k][2] - b) ** 2)
            tim.idx[i] = cache[key]


def hue_shift(c, deg):
    if c == 0:
        return 0
    import colorsys
    stp = c & 0x8000
    r, g, b = (c & 31) / 31, (c >> 5 & 31) / 31, (c >> 10 & 31) / 31
    hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
    r, g, b = colorsys.hls_to_rgb((hh + deg / 360) % 1, ll, ss)
    n = round(r * 31) | round(g * 31) << 5 | round(b * 31) << 10
    return (n | stp) or 0x8000


# ---------------------------------------------------------------- glTF
def matname(d):
    """Material per (mode without the quad bit, flag, CLUT row, TSB bits): the name is the
    specification import-gltf uses (also editable by hand in Blender)."""
    mode = d['mode'] & ~8
    s = f"dw_m{mode:02x}_f{d['flag']}"
    if d['mode'] & 4:
        s += f"_p{(d['cba'] >> 6) - 488:02d}_t{d['tsb']:02x}"
    return s


def parse_matname(n):
    if not n or not n.startswith('dw_'):
        raise SystemExit(f'material {n!r}: the name must be dw_m<mode>_f<flag>[_p<row>_t<TSB>] (copy it from an export)')
    n = n.split('.')[0]                   # Blender appends .001, .002... to duplicates
    parts = dict((p[0], p[1:]) for p in n.split('_')[1:])
    out = dict(mode=int(parts['m'], 16), flag=int(parts['f']))
    if 'p' in parts:
        out['row'] = int(parts['p']); out['tsb'] = int(parts['t'], 16)
    return out


def export_gltf(m, out_path, with_anims=True, tim=None):
    e = exe()
    t = m.type
    skel = e.skeleton[t]
    nb = e.bone_count[t]
    base = os.path.splitext(out_path)[0]
    tw, th = (tim.w, tim.h) if tim is not None else (256, 128)   # UVs are normalized by the image size (6 textures are not 256x128)
    binbuf = bytearray()
    accessors, views, meshes, nodes, materials, mat_idx = [], [], [], [], [], {}

    def add(data, fmt, count, typ, ctype, minmax=None, target=None):
        while len(binbuf) % 4: binbuf.append(0)
        off = len(binbuf)
        binbuf.extend(data)
        v = dict(buffer=0, byteOffset=off, byteLength=len(data))
        if target: v['target'] = target
        views.append(v)
        a = dict(bufferView=len(views) - 1, componentType=ctype, count=count, type=typ)
        if minmax: a['min'], a['max'] = minmax
        accessors.append(a)
        return len(accessors) - 1

    def material(name, d):
        if name in mat_idx:
            return mat_idx[name]
        mt = dict(name=name, pbrMetallicRoughness=dict(baseColorFactor=[1, 1, 1, 1], metallicFactor=0, roughnessFactor=1),
                  doubleSided=bool(d['flag'] & 2))
        if d['mode'] & 4:
            mt['pbrMetallicRoughness']['baseColorTexture'] = dict(index=0)
            mt['alphaMode'] = 'BLEND' if d['mode'] & 2 else 'MASK'
            if not d['mode'] & 2: mt['alphaCutoff'] = 0.5
        if d['flag'] & 1:
            mt['extensions'] = {'KHR_materials_unlit': {}}
        mt['extras'] = dict(dw_mode=d['mode'], dw_flag=d['flag'], dw_cba=d['cba'], dw_tsb=d['tsb'])
        materials.append(mt)
        mat_idx[name] = len(materials) - 1
        return mat_idx[name]

    def build_mesh(oi):
        verts, norms = m.tmd.obj_verts(oi), m.tmd.obj_norms(oi)
        groups = {}
        for pi, p in enumerate(m.tmd.objects[oi].prims):
            d = p.decode()
            d['_index'] = pi
            groups.setdefault(matname(d), (d, []))[1].append(d)
        prims = []
        for name, (d0, lst) in groups.items():
            pos, nrm, uv, col, dv, dn, idx, key = [], [], [], [], [], [], [], {}
            for d in lst:
                nv = len(d['verts'])
                corners = []
                for c in range(nv):
                    vi = d['verts'][c]
                    ni = d['norms'][c] if len(d['norms']) == nv else (d['norms'][0] if d['norms'] else -1)
                    u = d['uv'][c] if d['uv'] else (0, 0)
                    co = d['colors'][c] if len(d['colors']) == nv else (d['colors'][0] if d['colors'] else (255, 255, 255, 0))
                    k = (vi, ni, u, co[:3])
                    if k not in key:
                        key[k] = len(pos)
                        pos.append(verts[vi][:3])
                        n = norms[ni][:3] if ni >= 0 else (0, -4096, 0)
                        nrm.append(tuple(x / 4096 for x in n))
                        uv.append((u[0] / tw, u[1] / th))
                        col.append(co[:3])
                        dv.append(vi); dn.append(max(ni, 0))
                    corners.append(key[k])
                # same convention as DW1ModelConverter: (2,1,0) and (1,2,3)
                idx += [corners[2], corners[1], corners[0]]
                if nv == 4:
                    idx += [corners[1], corners[2], corners[3]]
            n = len(pos)
            attrs = {}
            mn = [min(p[i] for p in pos) for i in range(3)]; mx = [max(p[i] for p in pos) for i in range(3)]
            attrs['POSITION'] = add(struct.pack('<%df' % (3 * n), *[c for p in pos for c in p]), None, n, 'VEC3', 5126, (mn, mx), 34962)
            if not d0['flag'] & 1:
                attrs['NORMAL'] = add(struct.pack('<%df' % (3 * n), *[c for p in nrm for c in p]), None, n, 'VEC3', 5126, None, 34962)
            if d0['mode'] & 4:
                attrs['TEXCOORD_0'] = add(struct.pack('<%df' % (2 * n), *[c for p in uv for c in p]), None, n, 'VEC2', 5126, None, 34962)
            if d0['colors']:
                cb = bytearray()
                for c in col: cb += bytes(c) + b'\0'
                a = add(bytes(cb), None, n, 'VEC3', 5121, None, 34962)
                accessors[a]['normalized'] = True
                views[accessors[a]['bufferView']]['byteStride'] = 4
                attrs['COLOR_0'] = a
            # original TMD indices (custom attributes; Blender drops them)
            # (float: vertex attributes must be 4-byte aligned)
            attrs['_DW_VERT'] = add(struct.pack('<%df' % n, *dv), None, n, 'SCALAR', 5126, None, 34962)
            attrs['_DW_NORM'] = add(struct.pack('<%df' % n, *dn), None, n, 'SCALAR', 5126, None, 34962)
            ia = add(struct.pack('<%dH' % len(idx), *idx), None, len(idx), 'SCALAR', 5123, None, 34963)
            # original index of each primitive and whether it was a quad: import-gltf restores order and quads
            prims.append(dict(attributes=attrs, indices=ia, material=material(name, d0), mode=4,
                              extras=dict(dw_prims=[d['_index'] for d in lst],
                                          dw_quads=[len(d['verts']) == 4 for d in lst])))
        # vertices/normals no primitive uses (HYOG, JIJI, HAGU): for an exact round trip
        ob = m.tmd.objects[oi]
        uv_ = set(); un_ = set()
        for p in ob.prims:
            d = p.decode(); uv_ |= set(d['verts']); un_ |= set(d['norms'])
        ex = dict(dw_nvert=ob.nvert, dw_nnorm=ob.nnorm,
                  dw_unused_verts={i: m.tmd.verts[ob.vert_start + i] for i in range(ob.nvert) if i not in uv_},
                  dw_unused_norms={i: m.tmd.norms[ob.norm_start + i] for i in range(ob.nnorm) if i not in un_})
        meshes.append(dict(name=f'obj{oi:02d}', primitives=prims, extras=ex))
        return len(meshes) - 1

    a0 = m.anims.anims[m.anims.table[0]]
    nodes.append(dict(name='dw_root_flip', rotation=[1, 0, 0, 0], children=[1],
                      extras=dict(note='PS1 is Y-down: 180° turn around X for glTF viewers')))
    for b in range(nb):
        obj, par = skel[b]
        nd = dict(name=f'bone{b:02d}', extras=dict(dw_bone=b, dw_obj=obj, dw_parent=par))
        if b > 0:
            v = a0.pose[b - 1]
            if a0.has_scale:
                nd['scale'] = [x / 4096 for x in v[:3]]; v = v[3:]
            nd['rotation'] = list(quat(*v[:3]))
            nd['translation'] = [float(x) for x in v[3:6]]
        if obj >= 0:
            nd['mesh'] = build_mesh(obj)
        nodes.append(nd)
    for b in range(nb):
        par = skel[b][1]
        if par >= 0:
            nodes[1 + par].setdefault('children', []).append(1 + b)
    roots = [1 + b for b in range(nb) if skel[b][1] < 0]
    nodes[0]['children'] = roots

    animations = []
    if with_anims:
        for slot, ai in enumerate(m.anims.table):
            if ai is None:
                continue
            an = m.anims.anims[ai]
            frames, info = simulate(an, nb)
            times = [k / 20 for k in range(len(frames))]
            tacc = add(struct.pack('<%df' % len(times), *times), None, len(times), 'SCALAR', 5126, ([times[0]], [times[-1]]))
            samplers, channels = [], []
            for b in range(nb):
                tr = [frames[k][b][6:9] for k in range(len(frames))]
                rot = [quat(*frames[k][b][3:6]) for k in range(len(frames))]
                sc = [[x / 4096 for x in frames[k][b][0:3]] for k in range(len(frames))]
                for path, data, typ, w in (('translation', tr, 'VEC3', 3), ('rotation', rot, 'VEC4', 4), ('scale', sc, 'VEC3', 3)):
                    # a missing channel means the node's rest value (the pose of slot 0)
                    if path == 'scale' and all(s == nodes[1 + b].get('scale', [1, 1, 1]) for s in data):
                        continue
                    flat = [float(c) for v in data for c in v]
                    acc = add(struct.pack('<%df' % len(flat), *flat), None, len(data), typ, 5126)
                    samplers.append(dict(input=tacc, output=acc, interpolation='LINEAR'))
                    channels.append(dict(sampler=len(samplers) - 1, target=dict(node=1 + b, path=path)))
            ex = dict(dw_slot=slot, frame_count=an.frame_count)
            if info.get('loop'):
                ex['loop_jump_frame'], ex['loop_end_frame'] = info['loop']
                # after the last sample the motion continues as from this sample on (import-anim)
                ex['loop_sample'] = info['loop_sample']
            if info['sounds']: ex['sounds'] = [dict(tick=k, bank=b, note=n) for k, b, n in info['sounds']]
            if info['texs']: ex['texture_moves'] = [dict(tick=k, src=c['src'], size=c['size'], dst=c['dst']) for k, c in info['texs']]
            animations.append(dict(name=f'anim{slot:02d}', samplers=samplers, channels=channels, extras=ex))

    g = dict(asset=dict(version='2.0', generator='digimonworld tools/mmd.py'),
             scene=0, scenes=[dict(nodes=[0])], nodes=nodes, meshes=meshes, materials=materials,
             accessors=accessors, bufferViews=views,
             buffers=[dict(uri=os.path.basename(base) + '.bin', byteLength=len(binbuf))],
             extras=dict(dw_type=t, dw_name=e.names[t], dw_bones=nb, dw_nobj=len(m.tmd.objects), dw_tex=[tw, th]))
    if animations:
        g['animations'] = animations
    if any(mt['extensions'] for mt in materials if 'extensions' in mt):
        g['extensionsUsed'] = ['KHR_materials_unlit']
    if tim is not None:
        png = base + '.png'
        png_write(png, tim.w, tim.h, texture_rgba(m, tim))
        g['images'] = [dict(uri=os.path.basename(png))]
        g['samplers'] = [dict(magFilter=9728, minFilter=9728, wrapS=33071, wrapT=33071)]
        g['textures'] = [dict(source=0, sampler=0)]
    else:
        for mt in materials:
            mt['pbrMetallicRoughness'].pop('baseColorTexture', None)
    while len(binbuf) % 4: binbuf.append(0)
    g['buffers'][0]['byteLength'] = len(binbuf)
    open(base + '.bin', 'wb').write(binbuf)
    json.dump(g, open(out_path, 'w'), indent=1)
    return g


def gltf_load(path):
    g = json.load(open(path))
    bufs = []
    for b in g['buffers']:
        uri = b['uri']
        if uri.startswith('data:'):
            import base64
            bufs.append(base64.b64decode(uri.split(',', 1)[1]))
        else:
            bufs.append(open(os.path.join(os.path.dirname(path), uri), 'rb').read())

    def read(ai):
        a = g['accessors'][ai]
        v = g['bufferViews'][a['bufferView']]
        buf = bufs[v['buffer']]
        ncomp = dict(SCALAR=1, VEC2=2, VEC3=3, VEC4=4, MAT4=16)[a['type']]
        fmt = {5126: 'f', 5123: 'H', 5125: 'I', 5121: 'B', 5120: 'b', 5122: 'h'}[a['componentType']]
        sz = struct.calcsize(fmt)
        stride = v.get('byteStride') or sz * ncomp
        off = v.get('byteOffset', 0) + a.get('byteOffset', 0)
        out = []
        for i in range(a['count']):
            vals = struct.unpack_from('<%d%s' % (ncomp, fmt), buf, off + i * stride)
            if a.get('normalized') and fmt == 'B':
                vals = tuple(x / 255 for x in vals)
            out.append(vals if ncomp > 1 else vals[0])
        return out
    return g, read


def _gltf_tex_size(g, path):
    """Image size the UVs of a glTF are normalized by: extras.dw_tex of our export, else the
    header of the PNG next to it (Blender drops the extras), else 256x128."""
    ex = (g.get('extras') or {}).get('dw_tex')
    if ex:
        return tuple(ex)
    try:
        uri = g['images'][0]['uri']
        if uri.startswith('data:'):
            import base64
            hdr = base64.b64decode(uri.split(',', 1)[1])[:24]
        else:
            hdr = open(os.path.join(os.path.dirname(path), uri), 'rb').read(24)
        return struct.unpack_from('>II', hdr, 16)
    except (KeyError, IndexError, OSError, struct.error, ValueError):
        return 256, 128


def import_gltf(base, path):
    """Rebuilds the TMD of `base` from a glTF with one node per bone (bone00..), a rigid mesh in
    the bone's local space and dw_m.._f.._p.._t.. materials. Keeps the animation section of
    `base`. If the _DW_VERT/_DW_NORM attributes are present (our own export with unchanged
    topology) the original TMD indices are kept."""
    e = exe()
    t = base.type
    skel = e.skeleton[t]
    g, read = gltf_load(path)
    tw, th = _gltf_tex_size(g, path)
    bone_node = {}
    for i, nd in enumerate(g['nodes']):
        ex = nd.get('extras') or {}
        if 'dw_bone' in ex:
            bone_node[ex['dw_bone']] = nd
        elif nd.get('name', '').startswith('bone') and nd['name'][4:].isdigit():
            bone_node.setdefault(int(nd['name'][4:]), nd)
    nobj = max(o for o, _ in skel) + 1
    if nobj != len(base.tmd.objects):
        print(f'warning: the skeleton needs {nobj} objects and BASE has {len(base.tmd.objects)}')
    tmd = TMD()
    for oi in range(nobj):
        bones = [b for b, (o, _) in enumerate(skel) if o == oi]
        nd = bone_node.get(bones[0]) if bones else None
        ob = TMDObject()
        ob.vert_start, ob.norm_start = len(tmd.verts), len(tmd.norms)
        vlist, nlist, vkey, nkey = [], [], {}, {}
        tex_prims, col_prims = [], []
        if nd is not None and 'mesh' in nd:
            for pr in g['meshes'][nd['mesh']]['primitives']:
                at = pr['attributes']
                if 'material' not in pr:
                    raise SystemExit(f'mesh of bone {bones[0]}: primitive without a dw_... material')
                mat = g['materials'][pr['material']]
                spec = parse_matname(mat['name'])
                pos = read(at['POSITION'])
                nrm = read(at['NORMAL']) if 'NORMAL' in at else None
                uvs = read(at['TEXCOORD_0']) if 'TEXCOORD_0' in at else None
                col = read(at['COLOR_0']) if 'COLOR_0' in at else None
                dvi = [int(x) for x in read(at['_DW_VERT'])] if '_DW_VERT' in at else None
                dni = [int(x) for x in read(at['_DW_NORM'])] if '_DW_NORM' in at else None
                idx = read(pr['indices']) if 'indices' in pr else list(range(len(pos)))
                q = lambda v: tuple(max(-32768, min(32767, round(c))) for c in v)

                def vref(i):
                    v = q(pos[i])
                    if dvi is not None:
                        k = ('i', dvi[i])
                    else:
                        k = v
                    if k not in vkey:
                        vkey[k] = len(vlist); vlist.append(v + (0,))
                    else:
                        vlist[vkey[k]] = v + (0,)
                    return vkey[k]

                def nref(i):
                    n = nrm[i] if nrm else (0, -1, 0)
                    v = tuple(max(-32768, min(32767, round(c * 4096))) for c in n)
                    k = ('i', dni[i]) if dni is not None else v
                    if k not in nkey:
                        nkey[k] = len(nlist); nlist.append(v + (0,))
                    return nkey[k]

                tris = [idx[k:k + 3] for k in range(0, len(idx), 3)]
                ex = pr.get('extras') or {}
                hint_q, hint_i = ex.get('dw_quads'), ex.get('dw_prims')
                if hint_q is not None and sum(2 if q else 1 for q in hint_q) != len(tris):
                    hint_q = hint_i = None          # topology changed: pair by guesswork
                k = 0
                n_out = 0
                while k < len(tris):
                    a = tris[k]
                    quad = None
                    if hint_q is not None:
                        if hint_q[n_out]:
                            b2 = tris[k + 1]
                            quad = [a[2], a[1], a[0], b2[2]]
                    elif k + 1 < len(tris):
                        b2 = tris[k + 1]
                        # (c2,c1,c0) + (c1,c2,c3) → quad c0..c3
                        if b2[0] == a[1] and b2[1] == a[0]:
                            quad = [a[2], a[1], a[0], b2[2]]
                    corners = quad or [a[2], a[1], a[0]]
                    k += 2 if quad else 1
                    mode = spec['mode'] | (8 if quad else 0)
                    flag = spec['flag']
                    nv, nuv, ncol, nnorm = prim_shape(mode, flag)
                    d = dict(mode=mode, flag=flag, uv=[], colors=[], norms=[], verts=[], cba=None, tsb=None)
                    d['verts'] = [vref(c) for c in corners]
                    if nnorm == nv:
                        d['norms'] = [nref(c) for c in corners]
                    elif nnorm == 1:
                        d['norms'] = [nref(corners[0])]
                    if nuv:
                        d['uv'] = [(max(0, min(tw - 1, round(uvs[c][0] * tw))), max(0, min(th - 1, round(uvs[c][1] * th)))) for c in corners]
                        d['cba'] = (488 + spec['row']) << 6
                        d['tsb'] = spec['tsb']
                    if ncol:
                        cc = [tuple(round(x * 255) for x in col[c][:3]) if col else (128, 128, 128) for c in corners]
                        code = mode if not mode & 4 else 0
                        d['colors'] = [c + (code,) for c in cc[:ncol]]
                    order = hint_i[n_out] if hint_i is not None else 1 << 30
                    n_out += 1
                    (tex_prims if mode & 4 else col_prims).append((order, len(tex_prims) + len(col_prims), Prim.encode(d)))
        # textured ones first: updateTMDTextureData stops at the first untextured one (graphics.c:177-180)
        ob.prims = [p for _, _, p in sorted(tex_prims)] + [p for _, _, p in sorted(col_prims)]
        # with the original indices (_DW_VERT/_DW_NORM) the pool is rebuilt exactly as it was,
        # filling the unused ones from the mesh extras (unchanged export → same TMD)
        mex = (g['meshes'][nd['mesh']].get('extras') or {}) if nd is not None and 'mesh' in nd else {}

        def rebuild(key, lst, count, unused):
            if not key or not all(isinstance(k, tuple) and len(k) == 2 and k[0] == 'i' for k in key):
                return lst, None
            n = max([count or 0] + [k[1] + 1 for k in key])
            full = [None] * n
            for k, pos in key.items():
                full[k[1]] = lst[pos]
            for i in range(n):
                if full[i] is None:
                    full[i] = tuple(unused.get(str(i), unused.get(i, (0, 0, 0, 0))))
            return full, {pos: k[1] for k, pos in key.items()}
        vlist, vmap = rebuild(vkey, vlist, mex.get('dw_nvert'), mex.get('dw_unused_verts', {}))
        nlist, nmap = rebuild(nkey, nlist, mex.get('dw_nnorm'), mex.get('dw_unused_norms', {}))
        if vmap or nmap:
            ob.prims = [_remap(p, vmap, nmap) for p in ob.prims]
        ob.nvert, ob.nnorm = len(vlist), len(nlist)
        tmd.verts += vlist
        tmd.norms += nlist
        tmd.objects.append(ob)
    out = MMD()
    out.tmd, out.anims, out.type, out.nbones = tmd, base.anims, t, base.nbones
    return out


def _remap(p, vmap, nmap):
    d = p.decode()
    if vmap: d['verts'] = [vmap[v] for v in d['verts']]
    if nmap: d['norms'] = [nmap[v] for v in d['norms']]
    return Prim.encode(d)


# ---------------------------------------------------------------- animation import (glTF → MMD)
UNITS_PER_RAD = 4096 / (2 * math.pi)
MAX_FRAME = 0xFFF                    # instruction frame field: 12 bits


def quat_matrix(q):
    """3×3 matrix of a glTF quaternion (x, y, z, w)."""
    x, y, z, w = q
    n = math.sqrt(x * x + y * y + z * z + w * w) or 1.0
    x, y, z, w = x / n, y / n, z / n, w / n
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]


def matrix_euler(M, prev=None, rx_hint=None):
    """Angles (rx, ry, rz) in 1/4096 turn with M = Rx·Ry·Rz (libgte RotMatrix), as floats.
    Of the two equivalent solutions, (rx, ry, rz) and (rx+2048, 2048−ry, rz+2048), each
    shifted by whole turns, the one closest to `prev` is returned (a spin keeps adding up
    instead of jumping back; a quaternion only knows the angle modulo one turn). In gimbal
    lock (|ry| = 1024) only rx ± rz is defined: rx is `rx_hint` or the one of `prev`."""
    sy = max(-1.0, min(1.0, M[0][2]))
    cy = math.hypot(M[0][0], M[0][1])
    ry = math.atan2(sy, cy)
    if cy > 1e-6:
        rx = math.atan2(-M[1][2], M[2][2])
    elif rx_hint is not None:
        rx = rx_hint / UNITS_PER_RAD
    else:
        rx = prev[0] / UNITS_PER_RAD if prev is not None else 0.0
    cx, sx = math.cos(rx), math.sin(rx)
    rz = math.atan2(cx * M[1][0] + sx * M[2][0], cx * M[1][1] + sx * M[2][1])   # row 1 of Rxᵀ·M = (sz, cz, 0)
    c1 = (rx * UNITS_PER_RAD, ry * UNITS_PER_RAD, rz * UNITS_PER_RAD)
    if prev is None:
        return [(v + 2048) % 4096 - 2048 for v in c1]
    best, cost = None, None
    for c in (c1, (c1[0] + 2048, 2048 - c1[1], c1[2] + 2048)):
        u = [v + 4096 * round((p - v) / 4096) for v, p in zip(c, prev)]
        k = sum(abs(a - b) for a, b in zip(u, prev))
        if best is None or k < cost - 1e-9:
            best, cost = u, k
    return best


def _slerp(a, b, u):
    d = sum(x * y for x, y in zip(a, b))
    if d < 0:
        b, d = [-x for x in b], -d
    if d > 0.9995:
        r = [x + (y - x) * u for x, y in zip(a, b)]
    else:
        th = math.acos(d)
        s = math.sin(th)
        wa, wb = math.sin((1 - u) * th) / s, math.sin(u * th) / s
        r = [wa * x + wb * y for x, y in zip(a, b)]
    n = math.sqrt(sum(x * x for x in r)) or 1.0
    return [x / n for x in r]


class GltfTrack:
    """One glTF animation sampler (LINEAR, STEP or CUBICSPLINE) evaluated at any time."""

    def __init__(self, read, sampler, path):
        self.t = [float(x) for x in read(sampler['input'])]
        out = [list(v) if isinstance(v, (tuple, list)) else [v] for v in read(sampler['output'])]
        self.interp = sampler.get('interpolation', 'LINEAR')
        self.rot = path == 'rotation'
        if self.interp == 'CUBICSPLINE':
            self.a, self.v, self.b = out[0::3], out[1::3], out[2::3]
        else:
            self.v = out

    def end(self):
        return self.t[-1] if self.t else 0.0

    def at(self, t):
        T, V = self.t, self.v
        if not T:
            return None
        if t <= T[0] + 1e-6:
            return list(V[0])
        if t >= T[-1] - 1e-6:
            return list(V[-1])
        import bisect
        i = bisect.bisect_right(T, t) - 1
        if abs(t - T[i]) < 1e-6:
            return list(V[i])
        if abs(T[i + 1] - t) < 1e-6:
            return list(V[i + 1])
        dt = T[i + 1] - T[i]
        u = (t - T[i]) / dt
        if self.interp == 'STEP':
            return list(V[i])
        if self.interp == 'CUBICSPLINE':
            u2, u3 = u * u, u * u * u
            r = [(2 * u3 - 3 * u2 + 1) * p0 + (u3 - 2 * u2 + u) * dt * m0 + (-2 * u3 + 3 * u2) * p1 + (u3 - u2) * dt * m1
                 for p0, m0, p1, m1 in zip(V[i], self.b[i], V[i + 1], self.a[i + 1])]
            if self.rot:
                n = math.sqrt(sum(x * x for x in r)) or 1.0
                r = [x / n for x in r]
            return r
        if self.rot:
            return _slerp(V[i], V[i + 1], u)
        return [x + (y - x) * u for x, y in zip(V[i], V[i + 1])]


def gltf_bone_nodes(g, nb):
    """glTF node index of each bone (extras.dw_bone, or the name boneNN)."""
    out = {}
    for i, nd in enumerate(g['nodes']):
        ex = nd.get('extras') or {}
        if 'dw_bone' in ex:
            out[ex['dw_bone']] = i
        elif nd.get('name', '').startswith('bone') and nd['name'][4:].split('.')[0].isdigit():
            out.setdefault(int(nd['name'][4:].split('.')[0]), i)
    missing = [b for b in range(nb) if b not in out]
    if missing:
        raise SystemExit(f'the glTF has no node for bones {missing} (bone00..bone{nb - 1:02d}, as the export names them)')
    return out


def gltf_anim_samples(g, read, an, nb, fps=20.0):
    """Samples a glTF animation once per game tick (glTF time t → tick t·fps) and converts
    it to the engine's integers: per sample and bone [sx sy sz rx ry rz tx ty tz] (scale in
    4.12, angles in 1/4096 turn, unwrapped per bone so spins accumulate). For bone 0 tx..tz
    is the root motion accumulated in its own frame (what the momentum of bone 0 moves:
    the translation of node bone00 differentiated and brought back through its R·S)."""
    bnode = gltf_bone_nodes(g, nb)
    node_bone = {n: b for b, n in bnode.items()}
    tracks = {}
    for ch in an['channels']:
        tgt = ch.get('target', {})
        if tgt.get('node') in node_bone and tgt.get('path') in ('translation', 'rotation', 'scale'):
            tracks[(node_bone[tgt['node']], tgt['path'])] = GltfTrack(read, an['samplers'][ch['sampler']], tgt['path'])
    if not tracks:
        raise SystemExit(f'animation {an.get("name")!r} moves none of the bone nodes')
    dur = max(tr.end() for tr in tracks.values())
    n = int(round(dur * fps)) + 1
    rest = {}
    for b in range(nb):
        nd = g['nodes'][bnode[b]]
        rest[b] = dict(translation=nd.get('translation', [0, 0, 0]), rotation=nd.get('rotation', [0, 0, 0, 1]),
                       scale=nd.get('scale', [1, 1, 1]))
    samples = [[None] * nb for _ in range(n)]
    for b in range(nb):
        get = lambda path, t: (tracks[(b, path)].at(t) if (b, path) in tracks else list(rest[b][path]))
        mats = [quat_matrix(get('rotation', i / fps)) for i in range(n)]
        eul, prev_e = [], None
        for M in mats:
            prev_e = matrix_euler(M, prev_e)
            eul.append(prev_e)
        # gimbal lock: rx halfway between the neighbouring ticks (exact for linear motion)
        for i in range(1, n - 1):
            if math.hypot(mats[i][0][0], mats[i][0][1]) <= 1e-6 and math.hypot(mats[i + 1][0][0], mats[i + 1][0][1]) > 1e-6:
                eul[i] = matrix_euler(mats[i], eul[i - 1], (eul[i - 1][0] + eul[i + 1][0]) / 2)
                eul[i + 1] = matrix_euler(mats[i + 1], eul[i])
        prev_t = None
        root = [0, 0, 0]
        for i in range(n):
            t = i / fps
            sc = [round(x * 4096) for x in get('scale', t)]
            er = [round(x) for x in eul[i]]
            tr = get('translation', t)
            if b == 0:
                if prev_t is not None:
                    d = [tr[k] - prev_t[k] for k in range(3)]
                    R = rot_matrix(*er)
                    loc = [sum(R[k][j] * d[k] for k in range(3)) for j in range(3)]   # Rᵀ·d
                    for j in range(3):
                        root[j] += round(loc[j] * 4096 / sc[j]) if sc[j] else 0
                prev_t = tr
                tv = list(root)
            else:
                tv = [round(x) for x in tr]
            samples[i][b] = sc + er + tv
    return samples


def close_loop(samples, loop_sample):
    """An infinite loop repeats the Euler *deltas* of its body after the last sample, so the
    last pose must be written in the same Euler solution as the loop start, not the one
    closest to the previous tick (a loop that snaps back to its start pose in one tick, or a
    full spin, would otherwise continue in the other solution and drift on the second pass).
    When the last pose equals the loop start pose (modulo whole turns and the equivalent
    solution), it is rewritten as the loop start one, each angle shifted by whole turns
    towards the previous tick."""
    n = len(samples) - 1
    if loop_sample is None or n < 1:
        return
    for b in range(len(samples[0])):
        a, z, prev = samples[loop_sample][b][3:6], samples[n][b][3:6], samples[n - 1][b][3:6]
        if a == z or _rot_err(a, z) != 0:
            continue
        samples[n][b][3:6] = [x + 4096 * round((p - x) / 4096) for x, p in zip(a, prev)]


def fit_segments(Vs, forced=(), tol=0):
    """Splits channels (Vs[c][i] = value of channel c at sample i) into linear segments the
    engine can play, with common boundaries: a keyframe (val, div) adds trunc(k·val/div)
    after k ticks (animReadMomentumInstruction + animApplyMomentum, a Bresenham whose counter
    starts at div). Greedy: each segment is extended as far as every intermediate sample of
    every channel stays within `tol` of what the engine will produce (tol = 0 → exact);
    segment ends land exactly on the samples. `forced` = samples where a segment must break
    (loop start). Returns [(start_sample, div, [val per channel])]."""
    n = len(Vs[0]) - 1
    knots = []
    forced = sorted(set(f for f in forced if 0 < f < n))
    a = 0
    while a < n:
        lim = min([n, a + 0x7FFF] + [f for f in forced if f > a])
        lo, hi = [-1e18] * len(Vs), [1e18] * len(Vs)
        cands = []
        for b in range(a + 1, lim + 1):
            k = b - a
            ok, stop = True, False
            for c, V in enumerate(Vs):
                d = V[b] - V[a]
                if abs(d) > 0x7FFF:
                    stop = True
                    break
                if not lo[c] - 1e-9 <= d / k <= hi[c] + 1e-9:
                    ok = False
                lo[c] = max(lo[c], (d - tol - 1) / k)      # necessary: |V − k·slope| < tol + 1
                hi[c] = min(hi[c], (d + tol + 1) / k)
                if lo[c] > hi[c] + 1e-9:
                    stop = True
            if ok and not (stop and any(abs(V[b] - V[a]) > 0x7FFF for V in Vs)):
                cands.append(b)
            if stop:
                break
        best = a + 1
        for b in reversed(cands):
            D = b - a
            good = True
            for V in Vs:
                d = V[b] - V[a]
                sg, ad = (1 if d >= 0 else -1), abs(d)
                if not all(abs(V[a + k] - V[a] - sg * (k * ad // D)) <= tol for k in range(1, D)):
                    good = False
                    break
            if good:
                best = b
                break
        knots.append((a, best - a, [V[best] - V[a] for V in Vs]))
        a = best
    return knots


def _bone_keys(chans, Vs, forced, tol):
    """Keyframe blocks of one bone: [(sample, div, {channel: val})]. Two encodings are tried,
    one segmentation per channel (fewest values) and one shared by all channels of the bone
    (fewest blocks: one per bone and keyframe, as the original files do); the smaller wins."""
    def emit(per):          # per: [(channel, knots)] → blocks, dropping keys that change nothing
        blocks = {}
        for c, knots in per:
            speed = {}
            for s, div, vals in knots:
                for cc, val in zip(c, vals):
                    q, r = int(val / div), val - int(val / div) * div
                    st = (q, 0) if r == 0 else (val, div)
                    if st == speed.get(cc, (0, 0)) and r == 0 and s not in forced:
                        continue            # same whole speed already running (a loop jump needs it)
                    speed[cc] = st
                    blocks.setdefault((s, div), {})[cc] = val
        return blocks
    sep = emit([((c,), fit_segments([V], forced, tol)) for c, V in zip(chans, Vs)]) if len(chans) > 1 else None
    joint = emit([(tuple(chans), fit_segments(Vs, forced, tol))])
    cost = lambda bl: sum(2 + len(v) for v in bl.values())
    return joint if sep is None or cost(joint) <= cost(sep) else sep


def find_repeats(samples, events=(), before=None, max_period=512, max_loops=4):
    """Finite loops hidden in a sampled animation: runs where the per-tick motion (every
    channel of every bone) and the sounds/texture moves repeat with period p, R ≥ 2 times.
    Returns [(s, p, R)]: the body is samples s+1..s+p, repeated up to sample s+R·p. Loops do
    not touch each other and end before `before` (the infinite loop's start): the engine has
    a single loop register and a loop start must be pending at the start of a tick."""
    n = len(samples) - 1
    ids, D = {}, [None]
    for i in range(1, n + 1):
        k = tuple(x - y for b0, b1 in zip(samples[i], samples[i - 1]) for x, y in zip(b0, b1))
        D.append(ids.setdefault(k, len(ids)))
    evs = {}
    for s, kind, c in events:
        evs.setdefault(s, []).append((kind, repr(sorted(c.items()))))
    E = [tuple(sorted(evs.get(i, []))) for i in range(n + 1)]
    # Intern motion/event pairs once; map compares integer IDs in C.
    from operator import eq
    pairs = {}
    timeline = [pairs.setdefault((d, e), len(pairs)) for d, e in zip(D[1:], E[:-1])]
    runs = []
    for p in range(1, min(max_period, n // 2) + 1):
        spans, start = [], None
        for i, same in enumerate(map(eq, timeline, timeline[p:])):
            if same:
                if start is None:
                    start = i
            elif start is not None:
                spans.append((start, i))
                start = None
        if start is not None:
            spans.append((start, n - p))
        runs.extend((p, a, b - a) for a, b in spans if b - a >= p)
    end = n if before is None else before - 1
    loops = []
    while len(loops) < max_loops:
        best = None
        for p, s0, length in runs:
            R = min(length // p + 1, 254)
            while R >= 2:
                e0 = s0 + R * p
                clash = e0 > end or any(not (s0 > s1 + r1 * p1 or s1 > e0) for s1, p1, r1 in loops)
                if not clash:
                    break
                R -= 1
            if R >= 2 and (best is None or (R - 1) * p > (best[2] - 1) * best[1]):
                best = (s0, p, R)
        if best is None or (best[2] - 1) * best[1] < 2:
            break
        loops.append(best)
    return sorted(loops)


def _compress(samples, events, loop_sample, loops):
    """Removes repetitions 2..R of each finite loop: returns the samples, events and infinite
    loop start in the shortened timeline, and the loops as (s, p, R) in it."""
    n = len(samples) - 1
    drop, after = set(), {}
    for s, p, R in loops:
        drop.update(range(s + p + 1, s + R * p + 1))
        after[s + R * p] = (s, p, R)
    idx, out, off, new = {}, [], None, []
    shift = [[0] * 9 for _ in samples[0]]
    for i in range(n + 1):
        if i in drop:
            if i in after:
                s, p, R = after[i]
                for b in range(len(shift)):
                    for j in range(9):
                        shift[b][j] += samples[i][b][j] - samples[s + p][b][j]
            continue
        idx[i] = len(out)
        out.append([[samples[i][b][j] - shift[b][j] for j in range(9)] for b in range(len(shift))])
    # events of samples s+p .. s+(R-1)·p are replays of those of sample s (the jump re-runs
    # frame s+1); those of sample s+R·p run on the last pass, after the loop end
    replay = set()
    for s, p, R in loops:
        replay.update(range(s + p, s + R * p))
    ev = []
    for s0, kind, c in events:
        if s0 in after:
            ev.append((idx[after[s0][0]] + after[s0][1], kind + '_after', c))
        elif s0 not in drop and s0 not in replay:
            ev.append((idx[s0], kind, c))
    loops2 = [(idx[s], p, R) for s, p, R in loops]
    return out, ev, (idx[loop_sample] if loop_sample is not None else None), loops2


def encode_anim(samples, nb, loop_sample=None, events=(), tol=0, repeats=True):
    """Builds an Anim from per-tick samples (gltf_anim_samples). Sample i is the pose after
    tick i+1; a keyframe at frame f sets the speed for the motion into sample f, so the
    segment that starts at sample a goes in frame a+1. With `loop_sample` = s the animation
    loops forever: loop start before frame s+1, a full keyframe there (every channel that
    moves, so the jump resets all speeds) and loop end at frame N = last sample + 1 jumping
    to s+1. `events`: (sample, 'sound'|'tex', instruction dict). With `repeats`, motion that
    repeats itself is also tried as finite loops (find_repeats) and the smaller result wins."""
    best = _encode(samples, nb, loop_sample, list(events), tol, [])
    if repeats:
        loops = find_repeats(samples, events, loop_sample)
        if loops:
            smp, ev, ls, lp = _compress(samples, events, loop_sample, loops)
            alt = _encode(smp, nb, ls, ev, tol, lp)
            if best is None or len(alt.build()) < len(best.build()):
                best = alt
    if best is None:
        raise ValueError(f'{len(samples)} ticks: the frame field allows {MAX_FRAME} (and no repetition was found to loop)')
    return best


def _encode(samples, nb, loop_sample, events, tol, loops):
    n = len(samples) - 1
    N = n + 1
    if N > MAX_FRAME:
        return None
    loop = loop_sample is not None
    if loop and not 0 <= loop_sample < n:
        raise ValueError(f'loop start sample {loop_sample} outside 0..{n - 1}')
    a = Anim()
    a.frame_count = N
    a.has_scale = any(samples[0][b][0:3] != [4096, 4096, 4096] for b in range(1, nb))
    for b in range(1, nb):
        v = samples[0][b] if a.has_scale else samples[0][b][3:]
        for x in v:
            if not -0x8000 <= x <= 0x7FFF:
                raise ValueError(f'initial pose of bone {b} out of int16: {samples[0][b]}')
        a.pose.append(list(v))
    keys = {}                                            # frame → [(bone, channel, val, div)]
    forced = set([loop_sample] if loop else [])
    for s, p, R in loops:
        forced |= {s, s + p}
    for b in range(nb):
        chans, Vs = [], []
        for j in range(9):
            V = [samples[i][b][j] for i in range(n + 1)]
            if any(x != V[0] for x in V):
                chans.append(j)
                Vs.append(V)
        if not chans:
            continue
        for (s, div), vals in _bone_keys(chans, Vs, forced, tol).items():
            for j, val in vals.items():
                keys.setdefault(s + 1, []).append((b, j, val, div))
    ev = {}
    for s, kind, c in events:
        if 0 <= s <= n:
            ev.setdefault(s + 1, []).append((kind, c))
    starts = {s + 1: R for s, p, R in loops}
    ends = {s + p + 1: s + 1 for s, p, R in loops}
    if loop:
        starts[loop_sample + 1] = 0xFF
    instrs = []

    def event(kind, c, f):
        if kind.startswith('tex'):
            instrs.append(dict(op='tex', frame=f, src=tuple(c['src']), size=tuple(c['size']), dst=tuple(c['dst'])))
        else:
            instrs.append(dict(op='sound', frame=f, bank=c['bank'], note=c['note']))

    for f in range(1, N + 1):
        evs = sorted(ev.get(f, []), key=lambda x: not x[0].startswith('tex'))
        if f in ends:
            # finite loop end first: on the last pass the keys and events of this frame (the
            # ones after the loop) run
            instrs.append(dict(op='loop_end', frame=f, jump=ends[f]))
        if f in starts:
            instrs.append(dict(op='loop_start', count=starts[f], raw=0x1000 | starts[f]))
        kl = keys.get(f, [])
        if kl or evs or f in starts or f in ends or f == 1:
            # a keyframe always goes first: a pending texture instruction would be taken as a
            # loop start by tickAnimation's `instruction & 0x1000` pre-check. Frame 1 always
            # has one: startAnimation sets loopEndFrame = 1, so the first instruction runs on
            # tick 1 whatever its frame
            groups = {}
            for b, j, val, div in kl:
                groups.setdefault((b, div), {})[CHANNELS[j]] = val
            instrs.append(dict(op='key', frame=f, bones=[dict(bone=b, div=d, vals=groups[(b, d)]) for b, d in sorted(groups)]))
        for kind, c in evs:
            event(kind, c, f)
        if loop and f == N:
            instrs.append(dict(op='loop_end', frame=N, jump=loop_sample + 1))
    instrs.append(dict(op='end'))
    a.instrs = instrs
    return a


def anim_events(an, nb, slot, kinds):
    """Sound / texture instructions of an existing animation as (sample, kind, dict)."""
    _, info = simulate(an, nb, slot=slot)
    out = []
    if 'sound' in kinds:
        out += [(k, 'sound', dict(bank=b, note=nt)) for k, b, nt in info['sounds']]
    if 'tex' in kinds:
        out += [(k, 'tex', dict(src=c['src'], size=c['size'], dst=c['dst'])) for k, c in info['texs']]
    return out


def anim_loops(an, nb):
    """Sample where an existing animation's infinite loop restarts, or None."""
    return simulate(an, nb)[1]['loop_sample']


def gltf_anim_slot(an, maps):
    name = an.get('name', '')
    if name in maps:
        return maps[name]
    ex = an.get('extras') or {}
    if 'dw_slot' in ex:
        return int(ex['dw_slot'])
    if name.startswith('anim') and name[4:].split('.')[0].isdigit():
        return int(name[4:].split('.')[0])
    return None


def import_anims(base, path, maps=None, fps=20.0, tol=1, loops=None, keep=(), gltf_events=False, only_mapped=False,
                 log=print):
    """Replaces/adds animation slots of `base` with the animations of a glTF that has the
    same skeleton (bone00.. nodes). maps: {glTF animation name: slot}; loops: {name: seconds
    or None (no loop)}; keep: 'sound'/'tex' from the replaced slot of BASE; gltf_events: take
    sounds and texture moves from the animation extras (our own export)."""
    maps, loops = dict(maps or {}), dict(loops or {})
    e = exe()
    nb = e.bone_count[base.type]
    g, read = gltf_load(path)
    sec = AnimSection()
    sec.table, sec.anims = list(base.anims.table), list(base.anims.anims)
    done = {}
    built = {}
    for an in g.get('animations', []):
        name = an.get('name', '')
        if only_mapped and name not in maps:
            continue
        slot = gltf_anim_slot(an, maps)
        if slot is None:
            log(f'  {name!r}: no slot (use --map {name}=SLOT), skipped')
            continue
        if not 0 <= slot < 256:
            raise SystemExit(f'{name}: slot {slot} out of range (animId is a u8)')
        samples = gltf_anim_samples(g, read, an, nb, fps)
        ex = an.get('extras') or {}
        old = base.anims.table[slot] if slot < len(base.anims.table) else None
        old_an = base.anims.anims[old] if old is not None else None
        if name in loops:
            ls = None if loops[name] is None else int(round(loops[name] * fps))
            why = 'option'
        elif ex.get('loop_sample') is not None:
            ls, why = int(ex['loop_sample']), 'glTF extras'
        elif ex.get('loop_jump_frame') is not None:
            ls, why = int(ex['loop_jump_frame']) - 1, 'glTF extras'
        elif name.lower().endswith(('_loop', '-loop', '.loop')):
            ls, why = 0, 'name'
        elif old_an is not None and anim_loops(old_an, nb) is not None:
            ls, why = 0, f'slot {slot:#x} of BASE loops'
        else:
            ls, why = None, ''
        if ls is not None and ls >= len(samples) - 1:
            raise SystemExit(f'{name}: loop start {ls} is not before the last tick {len(samples) - 1}')
        close_loop(samples, ls)
        events = []
        if gltf_events:
            events += [(s['tick'], 'sound', dict(bank=s['bank'], note=s['note'])) for s in ex.get('sounds', [])]
            events += [(s['tick'], 'tex', dict(src=tuple(s['src']), size=tuple(s['size']), dst=tuple(s['dst'])))
                       for s in ex.get('texture_moves', [])]
        if keep and old_an is not None:
            events += anim_events(old_an, nb, slot, keep)
        lost = [x for x in events if x[0] >= len(samples)]
        if lost:
            log(f'  {name}: {len(lost)} sound/texture instructions fall after the end and are dropped')
        anim = encode_anim(samples, nb, ls, events, tol)
        blob = anim.build()
        if blob in built:
            idx = built[blob]
        else:
            idx = len(sec.anims)
            sec.anims.append(anim)
            built[blob] = idx
        while len(sec.table) <= slot:
            sec.table.append(None)
        sec.table[slot] = idx
        done[slot] = (name, len(samples), ls, why, len(blob))
    # drop animations no slot points to any more
    used = sorted(set(i for i in sec.table if i is not None))
    remap = {o: k for k, o in enumerate(used)}
    sec.anims = [sec.anims[o] for o in used]
    sec.table = [remap[i] if i is not None else None for i in sec.table]
    out = MMD()
    out.tmd, out.anims, out.type, out.nbones = base.tmd, sec, base.type, base.nbones
    return out, done


def _rot_err(a, b):
    """Rotation difference in 1/4096 turn, modulo whole turns and the equivalent Euler
    solution; exact integer comparison first, the angle between both matrices otherwise."""
    d = max(abs((x - y + 2048) % 4096 - 2048) for x, y in zip(a, b))
    if d == 0:
        return 0
    alt = (b[0] + 2048, 2048 - b[1], b[2] + 2048)
    d = min(d, max(abs((x - y + 2048) % 4096 - 2048) for x, y in zip(a, alt)))
    if d == 0:
        return 0
    A, B = rot_matrix(*a), rot_matrix(*b)
    tr = sum(A[k][i] * B[k][i] for i in range(3) for k in range(3))
    ang = math.acos(max(-1.0, min(1.0, (tr - 1) / 2))) * UNITS_PER_RAD
    return min(d, round(ang, 2))


def compare_anims(orig, new, nb, slot, max_ticks=6000):
    """Plays both animations tick by tick (an infinite loop three times) and returns the
    largest differences: rotation (1/4096 turn), translation, scale (1/4096), root motion
    per tick, plus whether they stop on the same tick and play the same sounds/texture moves."""
    p, q = AnimPlayer(orig, nb, slot), AnimPlayer(new, nb, slot)
    err = dict(rot=0, pos=0, scale=0, root=0, ticks=0, stop=True, events=True)
    while err['ticks'] < max_ticks:
        r1, r2 = p.tick(), q.tick()
        if r1 != r2:
            err['stop'] = False
            break
        if not r1 or sum(1 for j in p.jumps if j[2]) >= 3:
            break
        err['ticks'] += 1
        for b in range(nb):
            u, v = p.pose[b], q.pose[b]
            err['rot'] = max(err['rot'], _rot_err(u[3:6], v[3:6]))
            err['scale'] = max(err['scale'], max(abs(x - y) for x, y in zip(u[0:3], v[0:3])))
            if b:
                err['pos'] = max(err['pos'], max(abs(x - y) for x, y in zip(u[6:9], v[6:9])))
        err['root'] = max(err['root'], max(abs(x - y) for x, y in zip(p.base, q.base)))
    def events(pl):
        return sorted((k, kind, tuple(sorted((x, tuple(y) if isinstance(y, (list, tuple)) else y)
                                             for x, y in c.items() if x != 'frame')))
                      for k, kind, c in pl.events if k < err['ticks'])
    e1, e2 = events(p), events(q)
    err['events'] = e1 == e2
    return err


# ---------------------------------------------------------------- preview
def mat_mul(a, b):
    # Keep sum's rounding and product order, without a generator per cell.
    return [[sum((r[0] * b[0][j], r[1] * b[1][j], r[2] * b[2][j], r[3] * b[3][j]))
             for j in range(4)] for r in a]


def bone_matrices(m, pose):
    """World matrix of each bone (chained GsCOORDINATE2: local = T·R·S)."""
    e = exe()
    skel = e.skeleton[m.type]
    out = [None] * len(skel)

    def get(b):
        if out[b] is None:
            v = pose[b]
            R = rot_matrix(*v[3:6])
            L = [[R[i][j] * v[j] / 4096 for j in range(3)] + [v[6 + i]] for i in range(3)] + [[0, 0, 0, 1]]
            par = skel[b][1]
            out[b] = mat_mul(get(par), L) if par >= 0 else L
        return out[b]
    for b in range(len(skel)):
        get(b)
    return out


def render(m, tim, pose, size=256, yaw=0.0, cull=False):
    """Software rasterizer (z-buffer, texture with its per-face CLUT, simple flat lighting).
    cull: drop back faces like the GsTMDfast routines do (single-sided unless flag bit 1)."""
    e = exe()
    skel = e.skeleton[m.type]
    mats = bone_matrices(m, pose)
    cy, sy = math.cos(yaw), math.sin(yaw)
    tris = []
    for b, (oi, _) in enumerate(skel):
        if oi < 0: continue
        M = mats[b]
        vs = m.tmd.obj_verts(oi)
        wv = []
        for x, y, z, _ in vs:
            X = M[0][0] * x + M[0][1] * y + M[0][2] * z + M[0][3]
            Y = M[1][0] * x + M[1][1] * y + M[1][2] * z + M[1][3]
            Z = M[2][0] * x + M[2][1] * y + M[2][2] * z + M[2][3]
            wv.append((cy * X + sy * Z, Y, -sy * X + cy * Z))
        for p in m.tmd.objects[oi].prims:
            d = p.decode()
            ids = d['verts']
            corners = [(0, 1, 2)] + ([(1, 3, 2)] if len(ids) == 4 else [])
            for c in corners:
                tris.append(([wv[ids[k]] for k in c], [d['uv'][k] for k in c] if d['uv'] else None, d))
    allp = [v for t in tris for v in t[0]]
    if not allp:
        raise SystemExit('empty model')
    mnx, mxx = min(v[0] for v in allp), max(v[0] for v in allp)
    mny, mxy = min(v[1] for v in allp), max(v[1] for v in allp)
    sc = (size - 16) / max(mxx - mnx, mxy - mny, 1)
    ox, oy = size / 2 - (mnx + mxx) / 2 * sc, size / 2 - (mny + mxy) / 2 * sc
    zb = [1e30] * (size * size)
    img = bytearray([40, 44, 52, 255] * (size * size))
    for pts, uv, d in tris:
        P = [(v[0] * sc + ox, v[1] * sc + oy, v[2]) for v in pts]
        ux, uy, uz = (pts[1][i] - pts[0][i] for i in range(3))
        vx, vy, vz = (pts[2][i] - pts[0][i] for i in range(3))
        nz = ux * vy - uy * vx
        nl = math.sqrt((uy * vz - uz * vy) ** 2 + (uz * vx - ux * vz) ** 2 + nz ** 2) or 1
        shade = 0.55 + 0.45 * abs(nz / nl)
        x0, x1 = max(0, int(min(p[0] for p in P))), min(size - 1, int(max(p[0] for p in P)) + 1)
        y0, y1 = max(0, int(min(p[1] for p in P))), min(size - 1, int(max(p[1] for p in P)) + 1)
        area = (P[1][0] - P[0][0]) * (P[2][1] - P[0][1]) - (P[1][1] - P[0][1]) * (P[2][0] - P[0][0])
        if abs(area) < 1e-9: continue
        if cull and area < 0 and not d['flag'] & 2: continue
        row = ((d['cba'] >> 6) - 488) if d['cba'] else 0
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                px, py = x + .5, y + .5
                w0 = ((P[1][0] - px) * (P[2][1] - py) - (P[1][1] - py) * (P[2][0] - px)) / area
                w1 = ((P[2][0] - px) * (P[0][1] - py) - (P[2][1] - py) * (P[0][0] - px)) / area
                w2 = 1 - w0 - w1
                if w0 < 0 or w1 < 0 or w2 < 0: continue
                z = w0 * P[0][2] + w1 * P[1][2] + w2 * P[2][2]
                i = y * size + x
                if z >= zb[i]: continue
                if uv and tim is not None:
                    u = int(w0 * uv[0][0] + w1 * uv[1][0] + w2 * uv[2][0])
                    v = int(w0 * uv[0][1] + w1 * uv[1][1] + w2 * uv[2][1])
                    u, v = max(0, min(tim.w - 1, u)), max(0, min(tim.h - 1, v))
                    c = tim.pal[min(row, tim.ch - 1)][tim.idx[v * tim.w + u]]
                    if c == 0: continue
                    r, g, b, _ = c15_to_rgba(c)
                elif d['colors']:
                    r, g, b = d['colors'][0][:3]
                else:
                    r, g, b = 200, 200, 200
                zb[i] = z
                img[4 * i:4 * i + 4] = bytes((int(r * shade), int(g * shade), int(b * shade), 255))
    return img


# ---------------------------------------------------------------- commands
def all_mmds():
    return sorted(glob.glob(os.path.join(EXTRACTED, 'CHDAT', 'MMD*', '*.MMD')))


def cmd_info(a):
    m = MMD.load(a.mmd, a.type)
    e = exe()
    t = m.type
    print(f'{a.mmd}: type {t} ({e.name(t)}), {e.bone_count[t]} bones, skeleton {e.skel_ptr[t]}, '
          f'{len(m.tmd.objects)} TMD objects, {len(m.tmd.verts)} vertices, {len(m.tmd.norms)} normals')
    from collections import Counter
    c = Counter(p.mode for o in m.tmd.objects for p in o.prims)
    print('  primitives per mode:', ', '.join(f'{k:#04x}×{v}' for k, v in sorted(c.items())))
    print('  skeleton (bone: object, parent):', ' '.join(f'{b}:{o},{p}' for b, (o, p) in enumerate(e.skeleton[t])))
    n = sum(1 for x in m.anims.table if x is not None)
    print(f'  animations: table of {len(m.anims.table)} slots, {n} used, {len(m.anims.anims)} distinct')
    for s, ai in enumerate(m.anims.table):
        if ai is None: continue
        an = m.anims.anims[ai]
        ops = Counter(i['op'] for i in an.instrs)
        print(f'    slot {s:#04x}: {an.frame_count:4d} frames{" +scale" if an.has_scale else ""}, '
              + ', '.join(f'{k}×{v}' for k, v in ops.items()) + (f', tail {len(an.tail)} B' if an.tail else ''))


def cmd_roundtrip(a):
    files = a.mmd or all_mmds()
    e = exe()
    ok = norm_ok = 0
    bad = []
    from collections import Counter
    stats = Counter()
    for f in files:
        d = open(f, 'rb').read()
        m = MMD.load(f)
        if m.build() == d:
            ok += 1
        else:
            bad.append(f)
        # normalization: decode and re-encode every primitive and every animation
        for ob in m.tmd.objects:
            ob.prims = [Prim.encode(p.decode()) for p in ob.prims]
        if m.build() == d:
            norm_ok += 1
        else:
            bad.append(f + ' (normalized)')
        for an in m.anims.anims:
            stats['tail_bytes'] += len(an.tail)
            stats['tail_nonzero'] += any(an.tail)
            stats['scale'] += an.has_scale
            for i in an.instrs:
                stats[i['op']] += 1
        a0 = m.anims.anims[m.anims.table[0]]
        stats['anim0_scale'] += a0.has_scale
    print(f'raw round trip: {ok}/{len(files)} identical; normalized: {norm_ok}/{len(files)}')
    print('instructions:', dict(stats))
    for b in bad: print('  DIFFERS', b)
    return 0 if not bad else 1


def load_tim(alltim, t):
    return Tim4(alltim_entry(open(alltim, 'rb').read(), t))


def mmd_for_type(t, given=None):
    if given:
        return MMD.load(given, t)
    name = exe().names[t]
    for f in all_mmds():
        if os.path.splitext(os.path.basename(f))[0] == name:
            return MMD.load(f, t)
    raise SystemExit(f'no MMD for type {t}')


def cmd_gltf(a):
    m = MMD.load(a.mmd, a.type)
    tim = None if a.no_tex else load_tim(a.alltim, a.tex_type if a.tex_type is not None else m.type)
    g = export_gltf(m, a.out, not a.no_anim, tim)
    print(f'{a.out}: {len(g["nodes"]) - 1} bones, {len(g["meshes"])} meshes, {len(g.get("animations", []))} animations')


def cmd_import(a):
    base = MMD.load(a.base, a.type)
    m = import_gltf(base, a.gltf)
    data = m.build()
    open(a.out, 'wb').write(data)
    orig = os.path.getsize(a.base)
    print(f'{a.out}: {len(data)} bytes (original {orig}, {"identical" if data == open(a.base, "rb").read() else "different"})')
    check_size(a.base, len(data))


def cmd_import_anim(a):
    base = MMD.load(a.base, a.type)
    maps = {}
    for spec in a.map:
        name, _, slot = spec.rpartition('=')
        if not name:
            raise SystemExit(f'--map {spec}: expected GLTF_ANIM_NAME=SLOT')
        maps[name] = int(slot, 0)
    loops = {}
    for spec in a.loop:
        name, _, t = spec.partition('=')
        loops[name] = float(t) if t else 0.0
    for name in a.no_loop:
        loops[name] = None
    keep = [k for k, on in (('sound', a.keep_sounds), ('tex', a.keep_tex)) if on]
    m, done = import_anims(base, a.gltf, maps, a.fps, a.tol, loops, keep, a.gltf_events, only_mapped=bool(maps))
    if not done:
        raise SystemExit('no animation imported (name them animNN or use --map NAME=SLOT)')
    for slot, (name, n, ls, why, size) in sorted(done.items()):
        lp = f', loops from tick {ls} ({why})' if ls is not None else ''
        print(f'  slot {slot:#04x} ← {name!r}: {n} ticks, {size} bytes{lp}')
    data = m.build()
    open(a.out, 'wb').write(data)
    print(f'{a.out}: {len(data)} bytes (original {os.path.getsize(a.base)})')
    check_size(a.base, len(data))


def anim_roundtrip_one(f):
    """export → glTF → import-anim (exact) → compare every slot tick by tick."""
    import tempfile
    m = MMD.load(f)
    nb = exe().bone_count[m.type]
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        gp = os.path.join(tmp, 'x.gltf')
        export_gltf(m, gp, True, None)
        try:
            new, _ = import_anims(m, gp, tol=0, gltf_events=True, log=lambda *x: None)
        except (SystemExit, ValueError) as ex:
            new, err_all = None, str(ex)
    size = len(new.build()) if new else None
    for slot, ai in enumerate(m.anims.table):
        if ai is None:
            continue
        if new is None:
            rows.append((slot, dict(fail=err_all)))
            continue
        rows.append((slot, compare_anims(m.anims.anims[ai], new.anims.anims[new.anims.table[slot]], nb, slot)))
    return f, os.path.getsize(f), size, rows


def cmd_anim_roundtrip(a):
    files = a.mmd or all_mmds()
    if a.jobs > 1 and len(files) > 1:
        import multiprocessing
        with multiprocessing.Pool(a.jobs) as pool:
            results = pool.map(anim_roundtrip_one, files)
    else:
        results = [anim_roundtrip_one(f) for f in files]
    tot = dict(rot=0, pos=0, scale=0, root=0)
    nslots = exact = 0
    bad = []
    for f, osz, nsz, rows in results:
        name = os.path.basename(f)
        worst = dict(rot=0, pos=0, scale=0, root=0)
        for slot, r in rows:
            nslots += 1
            if 'fail' in r:
                bad.append(f'{name} slot {slot:#x}: {r["fail"]}')
                continue
            for k in worst:
                worst[k] = max(worst[k], r[k])
                tot[k] = max(tot[k], r[k])
            if not r['stop'] or not r['events']:
                bad.append(f'{name} slot {slot:#x}: ' + ('stops on a different tick ' if not r['stop'] else '')
                           + ('different sounds/texture moves' if not r['events'] else ''))
            elif all(r[k] == 0 for k in worst):
                exact += 1
            elif max(r[k] for k in worst) > a.max_err:
                bad.append(f'{name} slot {slot:#x}: error ' + ', '.join(f'{k} {r[k]}' for k in worst if r[k]))
        if a.verbose or len(files) == 1:
            sz = f'{nsz} bytes (original {osz}{", exceeds its sectors" if nsz and nsz > (osz + 0x7FF) & ~0x7FF else ""})' if nsz else 'failed'
            print(f'{name}: {len(rows)} slots, max error ' + ', '.join(f'{k} {v}' for k, v in worst.items()) + f'; {sz}')
    grown = [(os.path.basename(f), nsz - osz) for f, osz, nsz, _ in results if nsz and nsz > (osz + 0x7FF) & ~0x7FF]
    print(f'animation round trip (export glTF → import-anim → tickAnimation per tick): {len(results)} MMDs, '
          f'{nslots} slots, {exact} exact; max error ' + ', '.join(f'{k} {v}' for k, v in tot.items()))
    print(f'  re-encoded files that outgrow their sectors: {len(grown)}' + (f' {grown[:8]}' if grown else ''))
    for b in bad:
        print('  DIFFERS', b)
    return 0 if not bad else 1


def check_size(orig_path, n):
    orig = os.path.getsize(orig_path)
    sect = (orig + 0x7FF) & ~0x7FF
    if n > sect:
        print(f'  WARNING! {n} > {sect} (sectors of the original): files on the disc must be moved and '
              f'FILE_OFFSET_TABLE redone (decomp/src/main/file_table_us.c)')
    elif n > orig:
        print(f'  fits in the sectors of the original ({sect}) but exceeds the table size ({orig})')
    pmax = int(os.environ.get('PARTNER_MMD_MAX', '0x18800'), 0)
    if n > pmax:
        print(f'  WARNING! does not fit in PARTNER_MODEL_BUFFER (0x{pmax:X}; PARTNER_MMD_MAX=... for another)')


def cmd_transplant(a):
    e = exe()
    mesh = MMD.load(a.mesh)
    anim = MMD.load(a.anim)
    if e.skel_ptr[mesh.type] != e.skel_ptr[anim.type]:
        sm, sa = e.skeleton[mesh.type], e.skeleton[anim.type]
        if len(sm) != len(sa) or [o for o, _ in sm] != [o for o, _ in sa]:
            raise SystemExit(f'different skeletons ({e.names[mesh.type]} {len(sm)} bones, {e.names[anim.type]} {len(sa)}): '
                             'transplanting only works with the same DIGIMON_SKELETONS')
        print('warning: skeletons with the same object assignment but a different tree')
    out = MMD()
    out.tmd, out.anims = mesh.tmd, anim.anims
    data = out.build()
    open(a.out, 'wb').write(data)
    print(f'{a.out}: mesh of {e.names[mesh.type]} + animations of {e.names[anim.type]}, {len(data)} bytes '
          f'(original {os.path.getsize(a.anim)})')
    check_size(a.anim, len(data))


def cmd_transform(a):
    m = MMD.load(a.mmd, a.type)
    e = exe()
    per_obj = {}
    for spec in a.bone_scale:
        b, s = spec.split('=')
        o = e.skeleton[m.type][int(b, 0)][0]
        if o < 0: raise SystemExit(f'bone {b} has no mesh')
        per_obj[o] = float(s)
    for oi, ob in enumerate(m.tmd.objects):
        s = per_obj.get(oi, 1.0) * a.scale
        if s == 1.0: continue
        for i in range(ob.vert_start, ob.vert_start + ob.nvert):
            x, y, z, p = m.tmd.verts[i]
            m.tmd.verts[i] = tuple(max(-32768, min(32767, round(c * s))) for c in (x, y, z)) + (p,)
    data = m.build()
    open(a.out, 'wb').write(data)
    print(f'{a.out}: {len(data)} bytes')


def cmd_tex_export(a):
    tim = load_tim(a.alltim, a.type)
    m = mmd_for_type(a.type, a.mmd)
    png_write(a.out, tim.w, tim.h, texture_rgba(m, tim))
    print(f'{a.out}: {tim.w}×{tim.h}, {tim.ch} 16-color palettes')


def write_alltim_entry(a, t, tim):
    data = bytearray(open(a.alltim, 'rb').read())
    data[t * ALLTIM_STRIDE:t * ALLTIM_STRIDE + len(tim.blob)] = tim.to_bytes()
    open(a.out, 'wb').write(data)


def cmd_tex_import(a):
    tim = load_tim(a.alltim, a.type)
    m = mmd_for_type(a.type, a.mmd)
    w, h, rgba = png_read(a.png)
    tex_import(m, tim, w, h, rgba)
    write_alltim_entry(a, a.type, tim)
    print(f'{a.out}: entry {a.type} replaced')


def cmd_recolor(a):
    tim = load_tim(a.alltim, a.type)
    for r in range(tim.ch):
        pal = tim.pal[r]
        if a.hue:
            pal = [hue_shift(c, a.hue) for c in pal]
        if a.swap:
            src = 'rgb'
            def sw(c):
                if c == 0: return 0
                ch = dict(r=c & 31, g=c >> 5 & 31, b=c >> 10 & 31)
                n = ch[a.swap[0]] | ch[a.swap[1]] << 5 | ch[a.swap[2]] << 10
                return (n | (c & 0x8000)) or 0x8000
            pal = [sw(c) for c in pal]
        tim.pal[r] = pal
    write_alltim_entry(a, a.type, tim)
    print(f'{a.out}: entry {a.type} recolored ({tim.ch} palettes)')


def cmd_copy_tex(a):
    data = bytearray(open(a.alltim, 'rb').read())
    data[a.dest * ALLTIM_STRIDE:(a.dest + 1) * ALLTIM_STRIDE] = data[a.orig * ALLTIM_STRIDE:(a.orig + 1) * ALLTIM_STRIDE]
    open(a.out, 'wb').write(data)
    print(f'{a.out}: entry {a.orig} copied over {a.dest}')


def cmd_preview(a):
    m = MMD.load(a.mmd, a.type)
    tim = load_tim(a.alltim, a.tex_type if a.tex_type is not None else m.type)
    nb = exe().bone_count[m.type]
    frames, _ = simulate(m.anims.anims[m.anims.table[a.anim]], nb)
    pose = frames[min(a.tick, len(frames) - 1)]
    pose[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
    imgs = [render(m, tim, pose, a.size, math.radians(y), cull=True) for y in a.yaw]
    W = a.size * len(imgs)
    out = bytearray()
    for y in range(a.size):
        for im in imgs:
            out += im[4 * y * a.size:4 * (y + 1) * a.size]
    png_write(a.out, W, a.size, out)
    print(f'{a.out}: animation {a.anim:#x}, tick {a.tick}, views {a.yaw}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    num = lambda s: int(s, 0)
    p = sub.add_parser('info'); p.add_argument('mmd'); p.add_argument('--type', type=num); p.set_defaults(f=cmd_info)
    p = sub.add_parser('roundtrip'); p.add_argument('mmd', nargs='*'); p.set_defaults(f=cmd_roundtrip)
    p = sub.add_parser('gltf'); p.add_argument('mmd'); p.add_argument('out'); p.add_argument('--type', type=num)
    p.add_argument('--no-anim', action='store_true'); p.add_argument('--no-tex', action='store_true')
    p.add_argument('--alltim', default=ALLTIM); p.add_argument('--tex-type', type=num); p.set_defaults(f=cmd_gltf)
    p = sub.add_parser('import-gltf'); p.add_argument('base'); p.add_argument('gltf'); p.add_argument('out')
    p.add_argument('--type', type=num); p.set_defaults(f=cmd_import)
    p = sub.add_parser('import-anim'); p.add_argument('base'); p.add_argument('gltf'); p.add_argument('out')
    p.add_argument('--type', type=num)
    p.add_argument('--map', action='append', default=[], metavar='NAME=SLOT',
                   help='glTF animation NAME goes to SLOT (repeatable); without --map: animNN names / extras.dw_slot')
    p.add_argument('--fps', type=float, default=20.0, help='game ticks per second of glTF time (20 = real time)')
    p.add_argument('--tol', type=int, default=1, help='allowed error per channel between keyframes, in engine units (0 = exact)')
    p.add_argument('--loop', action='append', default=[], metavar='NAME[=SECONDS]', help='loop forever, restarting at SECONDS')
    p.add_argument('--no-loop', action='append', default=[], metavar='NAME', help='play once and stop')
    p.add_argument('--keep-sounds', action='store_true', help="keep the sound instructions of the replaced slot")
    p.add_argument('--keep-tex', action='store_true', help="keep the texture moves (blinks) of the replaced slot")
    p.add_argument('--gltf-events', action='store_true', help='take sounds/texture moves from the animation extras')
    p.set_defaults(f=cmd_import_anim)
    p = sub.add_parser('anim-roundtrip'); p.add_argument('mmd', nargs='*'); p.add_argument('-v', '--verbose', action='store_true')
    p.add_argument('--jobs', type=int, default=os.cpu_count() or 1); p.add_argument('--max-err', type=float, default=1)
    p.set_defaults(f=cmd_anim_roundtrip)
    p = sub.add_parser('transplant'); p.add_argument('mesh'); p.add_argument('anim'); p.add_argument('out'); p.set_defaults(f=cmd_transplant)
    p = sub.add_parser('transform'); p.add_argument('mmd'); p.add_argument('out'); p.add_argument('--type', type=num)
    p.add_argument('--scale', type=float, default=1.0); p.add_argument('--bone-scale', action='append', default=[])
    p.set_defaults(f=cmd_transform)
    p = sub.add_parser('tex-export'); p.add_argument('type', type=num); p.add_argument('out')
    p.add_argument('--alltim', default=ALLTIM); p.add_argument('--mmd'); p.set_defaults(f=cmd_tex_export)
    p = sub.add_parser('tex-import'); p.add_argument('type', type=num); p.add_argument('png'); p.add_argument('out')
    p.add_argument('--alltim', default=ALLTIM); p.add_argument('--mmd'); p.set_defaults(f=cmd_tex_import)
    p = sub.add_parser('recolor'); p.add_argument('type', type=num); p.add_argument('out')
    p.add_argument('--alltim', default=ALLTIM); p.add_argument('--hue', type=float, default=0)
    p.add_argument('--swap', help='e.g. bgr: the red channel becomes the old blue one...'); p.set_defaults(f=cmd_recolor)
    p = sub.add_parser('preview'); p.add_argument('mmd'); p.add_argument('out'); p.add_argument('--type', type=num)
    p.add_argument('--alltim', default=ALLTIM); p.add_argument('--tex-type', type=num)
    p.add_argument('--anim', type=num, default=0); p.add_argument('--tick', type=int, default=0)
    p.add_argument('--size', type=int, default=200); p.add_argument('--yaw', type=float, nargs='+', default=[0, 90, 180])
    p.set_defaults(f=cmd_preview)
    p = sub.add_parser('copy-tex'); p.add_argument('orig', type=num); p.add_argument('dest', type=num); p.add_argument('out')
    p.add_argument('--alltim', default=ALLTIM); p.set_defaults(f=cmd_copy_tex)
    a = ap.parse_args()
    sys.exit(a.f(a) or 0)


if __name__ == '__main__':
    main()
