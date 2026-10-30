#!/usr/bin/env python3
"""Porting 3D models from other PS1 games into Digimon World MMDs (library).

The front-ends (tools/dcb2mmd.py: Digimon Digital Card Battle; tools/dw3mmd.py:
Digimon World 2003) read their game's data into a `Model` (below) and this module
does the DW1 side, the same for every source:

- `build_tmd`: one TMD object per mesh bone (rigid pieces in the bone's local space),
  primitives ordered textured-first (updateTMDTextureData), UVs relative to the
  256×128 slot, CBA = palette row, TSB = 5 | blend mode.
- `build_tim`: the 0x4800-byte ALLTIM-style texture entry (4 bpp, 16 CLUT rows).
- `skeleton`: the DW1 skeleton [(objIndex, parentIndex)], bone 0 = the entity, model
  bone i = DW1 bone i + 1.
- `write_gltf` + `mmd.import_anims`: every animation goes through a glTF (nodes
  bone00.., rotation quaternions, times in seconds) and `import-anim`, which samples
  it at 20 ticks/s and converts the rotations to the engine's Rx·Ry·Rz Euler angles.
- `build_partner`: a full partner animation set from a spec: the everyday slots
  retargeted (tools/retarget.py) from a DW1 Digimon with a similar body, then slots
  taken from the source game's own animations (trimmed, retimed, root motion fixed).

Model (what a front-end fills):
  bones[i]   dict(parent=-1|j, offset=(x,y,z) joint in the parent's rest frame,
                  rest=quaternion xyzw (rest rotation, usually identity),
                  verts=[(x,y,z)], norms=[(x,y,z) 4096 = 1], prims=[Prim dicts])
             Prim dict: verts [3|4 indices, PS1 corner order], norms [..] or None (unlit),
                        uvs [(u, v)] relative to the slot or None, row (CLUT row),
                        semi (bool), abr (0..3 blend mode), color (r, g, b)
  idx        bytearray 256*128 palette indices; pals: [16 colours (15-bit)] × ≤ 16
  anims      {name: Anim(frames, fps, loop)}; frames[tick][i] = (quat xyzw, (tx, ty, tz), (sx, sy, sz))
             of model bone i (local TRS, translation = full joint position).
Standard library only (uses tools/mmd.py, tools/retarget.py).
"""
import base64
import json
import math
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mmd  # noqa: E402
import retarget  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLOT_MAX_BYTES, SLOT_CUT_TICKS = 20000, 120
PARTNER_MMD_MAX = 0x18800       # the converters aim at the original buffer; PARTNER_MMD_MAX=... for a bigger one (memmap.h)


def configure(env=None, partner_mmd_max=None):
    """The converters' partner model limit: PARTNER_MMD_MAX of the environment (default os.environ, as the command
    line; 0x18800, the original buffer, without it), or partner_mmd_max (a caller in the same process)."""
    global PARTNER_MMD_MAX
    e = os.environ if env is None else env
    PARTNER_MMD_MAX = partner_mmd_max if partner_mmd_max is not None else int(e.get('PARTNER_MMD_MAX') or '0x18800', 0)
    return PARTNER_MMD_MAX


configure()
MAX_VERTS_PER_OBJECT = 172      # the largest of the 178 originals (docs/mods/models.md § 6)


class Anim:
    def __init__(self, frames, fps=30.0, loop=False):
        # A source reader may defer conversion of an unused animation. Metadata
        # and frame values are unchanged; materialize once, on first use.
        self._frames, self.fps, self.loop = frames, fps, loop

    @property
    def frames(self):
        if callable(self._frames):
            self._frames = self._frames()
        return self._frames

    @frames.setter
    def frames(self, value):
        self._frames = value

    def map_frames(self, transform):
        """Apply an edit now to existing frames, or when deferred frames are read."""
        frames = self._frames
        self._frames = (lambda: transform(frames())) if callable(frames) else transform(frames)


class Model:
    def __init__(self, name, bones, idx, pals, anims):
        self.name, self.bones, self.idx, self.pals, self.anims = name, bones, idx, pals, anims


# ---------------------------------------------------------------- math
def quat_of_matrix(m):
    """xyzw quaternion of a 3×3 rotation matrix (rows)."""
    tr = m[0][0] + m[1][1] + m[2][2]
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        q = ((m[2][1] - m[1][2]) / s, (m[0][2] - m[2][0]) / s, (m[1][0] - m[0][1]) / s, 0.25 * s)
    elif m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1.0 + m[0][0] - m[1][1] - m[2][2]) * 2
        q = (0.25 * s, (m[0][1] + m[1][0]) / s, (m[0][2] + m[2][0]) / s, (m[2][1] - m[1][2]) / s)
    elif m[1][1] > m[2][2]:
        s = math.sqrt(1.0 + m[1][1] - m[0][0] - m[2][2]) * 2
        q = ((m[0][1] + m[1][0]) / s, 0.25 * s, (m[1][2] + m[2][1]) / s, (m[0][2] - m[2][0]) / s)
    else:
        s = math.sqrt(1.0 + m[2][2] - m[0][0] - m[1][1]) * 2
        q = ((m[0][2] + m[2][0]) / s, (m[1][2] + m[2][1]) / s, 0.25 * s, (m[1][0] - m[0][1]) / s)
    n = math.sqrt(sum(x * x for x in q)) or 1.0
    return tuple(x / n for x in q)


IDENTITY_Q = (0.0, 0.0, 0.0, 1.0)


# ---------------------------------------------------------------- skeleton, TMD, texture
def skeleton(model):
    """DW1 skeleton: bone 0 = the entity, model bone i -> DW1 bone i+1 with object i
    (a bone without geometry gets objIndex -1)."""
    out = [(-1, -1)]
    obj = 0
    objs = []
    for b in model.bones:
        if b['verts']:
            objs.append(obj); obj += 1
        else:
            objs.append(-1)
    for i, b in enumerate(model.bones):
        out.append((objs[i], b['parent'] + 1 if b['parent'] >= 0 else 0))
    return out


def build_tmd(model, log=print):
    t = mmd.TMD()
    stray = 0
    for i, b in enumerate(model.bones):
        if not b['verts']:
            continue
        if len(b['verts']) > MAX_VERTS_PER_OBJECT:
            log(f'  note: bone {i} has {len(b["verts"])} vertices (the originals go up to {MAX_VERTS_PER_OBJECT})')
        ob = mmd.TMDObject()
        # identical vertices / normals are stored once (indices are local to the object)
        vkey, nkey, vmap, nmap = {}, {}, [], []
        for v in b['verts']:
            k = tuple(int(round(x)) for x in v)
            vmap.append(vkey.setdefault(k, len(vkey)))
        for v in b['norms']:
            k = tuple(int(round(x)) for x in v)
            nmap.append(nkey.setdefault(k, len(nkey)))
        ob.vert_start, ob.nvert = len(t.verts), len(vkey)
        ob.norm_start, ob.nnorm = len(t.norms), len(nkey)
        t.verts += [k + (0,) for k in vkey]
        t.norms += [k + (0,) for k in nkey]
        prims = sorted(b['prims'], key=lambda p: p['uvs'] is None)   # textured first
        for p in prims:
            quad = len(p['verts']) == 4
            tex = p['uvs'] is not None
            lit = p['norms'] is not None
            mode = 0x20 | (8 if quad else 0) | (4 if tex else 0) | (2 if p.get('semi') else 0)
            d = dict(verts=[vmap[k] for k in p['verts']], uv=[], colors=[], norms=[])
            if lit:
                mode |= 0x10                            # Gouraud: a normal per corner
                d['norms'] = [nmap[k] for k in p['norms']]
                flag = 0
            else:
                mode |= 1 if tex else 0
                flag = 1
            if tex:
                # rule: a UV one texel past the slot's edge (a face that ends on the border: 128, 256) is clamped
                p['uvs'] = [(min(u, 255) if u <= 256 else u, min(v, 127) if v <= 128 else v) for u, v in p['uvs']]
                # rule: a face that samples well outside the slot (VenomMyotismon has one at V 160) reads VRAM
                # that is not the model's texture; clamp it into the slot (a handful of faces per model at most)
                if any(not (0 <= u <= 255 and 0 <= v <= 127) for u, v in p['uvs']):
                    stray += 1
                    if stray > 8:
                        raise SystemExit(f'bone {i}: more than 8 faces sample outside the 256×128 slot')
                    p['uvs'] = [(min(max(u, 0), 255), min(max(v, 0), 127)) for u, v in p['uvs']]
                d['uv'] = [(int(u), int(v)) for u, v in p['uvs']]
                d['cba'] = (488 + p['row']) << 6          # CLUT row 488 + row of the slot (an add: 488 has bit 3)
                d['tsb'] = 5 | ((p.get('abr', 0) & 3) << 5)
            if not lit or not tex:
                r, g, bb = p.get('color', (128, 128, 128))
                n = 1 if not (mode & 0x10) else (len(p['verts']) if not tex else 0)
                d['colors'] = [(r, g, bb, mode if k == 0 else 0) for k in range(n)]
            d['mode'], d['flag'] = mode, flag
            ob.prims.append(mmd.Prim.encode(d))
        t.objects.append(ob)
    return t


def build_tim(idx, pals):
    """ALLTIM-style entry (0x4800 bytes): ALLTIM entry 3 as the template (16 CLUT rows)."""
    tpl = mmd.alltim_entry(open(mmd.ALLTIM, 'rb').read(), 3)
    tim = mmd.Tim4(tpl)
    if len(pals) > tim.ch:
        raise SystemExit(f'{len(pals)} palettes: the slot has {tim.ch} CLUT rows')
    tim.pal = [list(p) + [0] * (16 - len(p)) for p in pals] + [[0] * 16] * (tim.ch - len(pals))
    tim.idx = bytearray(idx)
    assert len(tim.idx) == 256 * 128
    return tim.to_bytes()


def base_mmd(model, typ, log=print):
    """MMD with the model's TMD and no animations; registers the type's skeleton in mmd.exe()."""
    mmd.exe().add_type(typ, skeleton(model), model.name)
    m = mmd.MMD()
    m.tmd = build_tmd(model, log)
    m.anims = mmd.AnimSection()
    m.type, m.nbones = typ, len(model.bones) + 1
    return m


def rest_pose(model):
    """Engine pose (per DW1 bone: sx sy sz rx ry rz tx ty tz) of the rest pose."""
    out = [[4096, 4096, 4096, 0, 0, 0, 0, 0, 0]]
    prev = None
    for b in model.bones:
        e = [round(x) for x in mmd.matrix_euler(mmd.quat_matrix(b.get('rest', IDENTITY_Q)), prev)]
        out.append([4096, 4096, 4096] + e + [round(x) for x in b['offset']])
    return out


# ---------------------------------------------------------------- glTF
class _Buf:
    def __init__(self):
        self.data, self.views, self.accs = bytearray(), [], []

    def add(self, vals, typ):
        n = dict(SCALAR=1, VEC3=3, VEC4=4)[typ]
        flat = [x for v in vals for x in (v if n > 1 else [v])]
        off = len(self.data)
        self.data += struct.pack('<%df' % len(flat), *flat)
        self.views.append(dict(buffer=0, byteOffset=off, byteLength=4 * len(flat)))
        acc = dict(bufferView=len(self.views) - 1, componentType=5126, count=len(vals), type=typ)
        if typ == 'SCALAR':
            acc['min'], acc['max'] = [min(vals)], [max(vals)]
        self.accs.append(acc)
        return len(self.accs) - 1


def write_gltf(path, model, clips):
    """A glTF with the skeleton (bone00 = entity, bone01.. = model bones) and `clips`:
    {name: dict(frames=[tick][dw bone] (quat, t, s), fps, loop_sample)}; dw bone 0's
    translation is the root motion (the entity's displacement)."""
    nb = len(model.bones) + 1
    sk = skeleton(model)
    nodes = [dict(name='dw_root_flip', rotation=[1, 0, 0, 0], children=[1])]
    for b in range(nb):
        nd = dict(name=f'bone{b:02d}', extras=dict(dw_bone=b, dw_obj=sk[b][0], dw_parent=sk[b][1]))
        if b:
            mb = model.bones[b - 1]
            nd['translation'] = [float(x) for x in mb['offset']]
            nd['rotation'] = list(mb.get('rest', IDENTITY_Q))
        kids = [c + 1 for c in range(nb) if sk[c][1] == b and c != b]
        if kids:
            nd['children'] = kids
        nodes.append(nd)
    buf = _Buf()
    anims = []
    for name, c in clips.items():
        frames = c['frames']
        times = [i / c['fps'] for i in range(len(frames))]
        ti = buf.add(times, 'SCALAR')
        samplers, channels = [], []
        for b in range(nb):
            for k, (path_, typ) in enumerate((('rotation', 'VEC4'), ('translation', 'VEC3'), ('scale', 'VEC3'))):
                vals = [list(f[b][k]) for f in frames]
                if k == 0:          # keep consecutive quaternions in the same hemisphere
                    for i in range(1, len(vals)):
                        if sum(x * y for x, y in zip(vals[i], vals[i - 1])) < 0:
                            vals[i] = [-x for x in vals[i]]
                samplers.append(dict(input=ti, output=buf.add(vals, typ), interpolation='LINEAR'))
                channels.append(dict(sampler=len(samplers) - 1, target=dict(node=b + 1, path=path_)))
        an = dict(name=name, samplers=samplers, channels=channels)
        if c.get('loop_sample') is not None:
            an['extras'] = dict(loop_sample=c['loop_sample'])
        anims.append(an)
    g = dict(asset=dict(version='2.0', generator='tools/mmdport.py'), scene=0, scenes=[dict(nodes=[0])],
             nodes=nodes, animations=anims, accessors=buf.accs, bufferViews=buf.views,
             buffers=[dict(byteLength=len(buf.data),
                           uri='data:application/octet-stream;base64,' + base64.b64encode(bytes(buf.data)).decode())])
    if not anims:
        del g['animations']
    with open(path, 'w') as f:
        json.dump(g, f)
    return g


def clip(model, name, start=0, end=None, speed=1.0, hips='keep', hz=1.0, root_scale=1.0, loop=None,
         settle=0, rise=None):
    """A source animation as DW1 frames (dw bone 0 included), with:
    start/end: source ticks kept; speed: playback rate (the glTF times are divided by it);
    hips='keep': the model root's translation stays on its bone (pose only, the entity does
    not move); hips='entity': its horizontal motion (x, z, from the first kept tick) moves
    the entity instead (root motion: knockbacks, steps); hz scales the horizontal hips
    motion (from the first kept tick) that stays on the bone, which starts at its rest joint
    (0 = in place, lunges removed); root_scale scales the
    entity motion; settle: ticks appended that blend back to the first kept pose (so an
    in-place technique ends where it started); rise: the root never goes higher than this
    many source units above its rest joint (a card-game attack that flies off for its whole
    length would leave the camera's view)."""
    a = model.anims[name]
    fr = a.frames[start:end if end is not None else len(a.frames)]
    if not fr:
        raise SystemExit(f'{name}: empty range {start}..{end}')
    roots = [i for i, b in enumerate(model.bones) if b['parent'] < 0]
    r0 = {i: fr[0][i][1] for i in roots}
    out = []
    for f in fr:
        ent = [0.0, 0.0, 0.0]
        bones = []
        for i, (q, t, s) in enumerate(f):
            t = list(t)
            if i in roots:
                d = [t[k] - r0[i][k] for k in range(3)]
                rest = model.bones[i]['offset']        # horizontal motion is measured from the rest joint
                if hips == 'entity' and i == roots[0]:
                    ent = [d[0] * root_scale, 0.0, d[2] * root_scale]
                    t[0], t[2] = rest[0], rest[2]
                else:
                    t[0], t[2] = rest[0] + d[0] * hz, rest[2] + d[2] * hz
                if rise is not None and i == roots[0]:
                    t[1] = max(t[1], rest[1] - rise)         # y is down
            bones.append((tuple(q), tuple(t), tuple(s)))
        out.append([(IDENTITY_Q, tuple(ent), (1.0, 1.0, 1.0))] + bones)
    first, last = out[0], out[-1]
    for k in range(settle):
        u = (k + 1) / settle
        u = u * u * (3 - 2 * u)
        out.append([last[0]] + [(_nlerp(last[b][0], first[b][0], u),
                                 tuple(x + (y - x) * u for x, y in zip(last[b][1], first[b][1])),
                                 tuple(x + (y - x) * u for x, y in zip(last[b][2], first[b][2])))
                                for b in range(1, len(first))])
    fps = a.fps * speed
    if loop is None:
        loop = a.loop and start == 0 and end is None
    return dict(frames=out, fps=fps, loop_sample=0 if loop else None)


def _nlerp(a, b, u):
    if sum(x * y for x, y in zip(a, b)) < 0:
        b = [-x for x in b]
    q = [x + (y - x) * u for x, y in zip(a, b)]
    n = math.sqrt(sum(x * x for x in q)) or 1.0
    return tuple(x / n for x in q)


def import_clips(base, model, clips, maps, gltf_path, tol=1, log=print):
    """Writes the clips to a glTF and imports them into `base` (mmd.import_anims)."""
    write_gltf(gltf_path, model, clips)
    m, done = mmd.import_anims(base, gltf_path, maps, fps=20.0, tol=tol, only_mapped=True, log=log)
    return m, done


# ---------------------------------------------------------------- whole conversion
DEFAULT_SLOTS = {}          # front-ends fill: {source anim name: [slots]}


def convert(model, typ, out_mmd, out_tex, slots, gltf_path=None, tol=1, log=print):
    """Model -> MMD (TMD + the source animations in `slots` {anim name: [slot, ...]}) and
    the texture entry. Returns the MMD bytes."""
    base = base_mmd(model, typ, log)
    clips, maps = {}, {}
    for name, ss in slots.items():
        for s in ss:
            cname = f'{name}@{s:#04x}'
            clips[cname] = clip(model, name)
            maps[cname] = s
    gltf_path = gltf_path or os.path.splitext(out_mmd)[0] + '.gltf'
    m, done = import_clips(base, model, clips, maps, gltf_path, tol, log)
    data = m.build()
    open(out_mmd, 'wb').write(data)
    open(out_tex, 'wb').write(build_tim(model.idx, model.pals))
    for s, (name, n, ls, why, size) in sorted(done.items()):
        log(f'  slot {s:#04x} <- {name}: {n} ticks, {size} bytes' + (f', loops from {ls}' if ls is not None else ''))
    log(f'{out_mmd}: {len(data)} bytes; {out_tex}: texture entry')
    return data


class NativeModel:
    """The stand-in `build_partner` uses for a DW1 model that is already in the game: `bones` (one entry per
    DW1 bone below the entity) and `anims['idle']`, the model's own idle (slot 0) as per-bone local rotations,
    which the layer lays over the bones the donor map leaves out."""

    def __init__(self, base, nb):
        smp, lp, _ = retarget.play(base.anims.anims[base.anims.table[0]], nb, 0)
        frames = []
        for pose in smp:
            frames.append([(quat_of_matrix(retarget.rot_of(pose[b])), None, None) for b in range(1, nb)])
        self.bones = [None] * (nb - 1)
        self.anims = {'idle': Anim(frames, 20.0, True)}


# ---------------------------------------------------------------- partner
class Layer:
    """Motion of some bones taken from a looping source-game animation (its idle) and laid
    over the retargeted DW1 slots: a slot that loops plays a whole number of source cycles
    per loop (at least one, retimed to fit, so the loop stays seamless); a slot that does not
    loop plays the cycle at its own speed."""

    def __init__(self, model, anim, bones):
        a = model.anims[anim]
        self.frames, self.bones = a.frames, bones
        self.L = len(a.frames) - 1                       # the last frame closes the cycle
        self.Lt = self.L * 20.0 / a.fps                  # DW1 ticks per cycle

    def for_slot(self, n, loop):
        lay = Layer.__new__(Layer)
        lay.__dict__.update(self.__dict__)
        if loop is not None and n - 1 - loop > 0:
            P = n - 1 - loop
            c = max(1, round(P / self.Lt))
            lay.phase = lambda t: (max(0, t - loop) * c / P) if t >= loop else t / self.Lt
        else:
            lay.phase = lambda t: t / self.Lt
        lay.prev = {}
        lay.cache = {}
        return lay

    def quats(self, t):
        if t not in self.cache:
            x = (self.phase(t) % 1.0) * self.L
            i = int(x); u = x - i
            j = min(i + 1, self.L)
            self.cache[t] = {b: _nlerp(self.frames[i][b - 1][0], self.frames[j][b - 1][0], u) for b in self.bones}
        return self.cache[t]

    def matrices(self, t):
        return {b: mmd.quat_matrix(q) for b, q in self.quats(t).items()}

    def eulers(self, t):
        out = {}
        for b, q in self.quats(t).items():
            e = mmd.matrix_euler(mmd.quat_matrix(q), self.prev.get(b))
            self.prev[b] = e
            out[b] = [round(x) for x in e]
        return out


def _parse_map(spec):
    out = {}
    for t, s in spec.items():
        w = 1.0
        if isinstance(s, (list, tuple)) and len(s) == 2 and isinstance(s[1], float):
            s, w = s
        if isinstance(s, str) and ':' in s:
            a, b = s.split(':')
            s = (int(a), int(b))
        out[int(t)] = (s, w)
    return out


def num(x):
    return int(x, 0) if isinstance(x, str) else int(x)


def build_partner(model, spec, out_mmd, out_tex, workdir, log=print):
    """A partner MMD from a spec (dict, see content/models/dcb-import/*.json):
      type, source {type, mmd}, map {target bone: source bone | [source, weight] | "s1:s2"},
      hips [target bone, source bone, k], root_scale, ref_slot, tol,
      retarget: "all" | [slots] (source slots to retarget; the slot numbers stay),
      slot_from: {target slot: source slot} (retargeted into another slot number),
      skip: [slots] not to retarget, layer: {anim, bones} (bones the map leaves out take
      their motion from the source game's own looping animation, e.g. its idle, in every
      retargeted slot; "bones": "unmapped" = all of them), tail: {bones: [...], amp, period} (an idle sway layered
      on retargeted slots), clips {slot: {anim, start, end, speed, hips, hz, root_scale,
      loop, settle}} (source-game animations, replacing retargeted ones), tol_clips."""
    if spec.get('fit'):             # rule (tools/fitfix.py): animation keys within the tolerance, merged-away primitives, own size limit
        import fitfix
        return fitfix.build_partner_fit(model, spec, out_mmd, out_tex, workdir, log)
    typ = num(spec['type'])
    e = mmd.exe()
    native = spec.get('native')
    if native:
        # a DW1 model that is already in the game (a wild-enemy-only Digimon): its mesh and every animation
        # it has stay byte for byte; only the slots a partner needs and it lacks are retargeted from the donor.
        # `type` is the native type (its skeleton is in the executable); the layered idle is the model's own.
        base = mmd.MMD.load(os.path.join(ROOT, native), typ)
        nb = e.bone_count[typ]
        trest = retarget.rest_pose(base, nb, 0)
        model = NativeModel(base, nb)
    else:
        base = base_mmd(model, typ, log)
        nb = len(model.bones) + 1
        trest = rest_pose(model)
    src_t = num(spec['source']['type'])
    src = mmd.MMD.load(os.path.join(ROOT, spec['source']['mmd']), src_t)
    bone_map = _parse_map(spec['map'])
    hips = tuple(spec['hips']) if spec.get('hips') else None
    slots = spec.get('retarget', 'all')
    if slots == 'all':
        slots = [s for s, x in enumerate(src.anims.table) if x is not None]
    slots = [num(s) for s in slots if num(s) not in [num(k) for k in spec.get('skip', [])]]
    clips_spec = {num(k): v for k, v in spec.get('clips', {}).items()}
    tail = spec.get('tail')
    layer = None
    if spec.get('layer'):
        lb = spec['layer'].get('bones', 'unmapped')
        if lb == 'unmapped':
            lb = [b for b in range(1, len(model.bones) + 1) if b not in bone_map]
        layer = Layer(model, spec['layer']['anim'], [num(b) for b in lb])
        layer.slots = [num(x) for x in spec['layer']['slots']] if 'slots' in spec['layer'] else None
    done = {}
    cache = {}
    pairs = [(s, s) for s in slots] + [(num(t), num(f)) for t, f in spec.get('slot_from', {}).items()]
    for s, ss in pairs:
        if s in clips_spec:
            continue
        idx = src.anims.table[ss]
        if idx in cache:                       # the source shares this animation between slots
            base.anims.table += [None] * (s + 1 - len(base.anims.table))
            base.anims.table[s] = cache[idx]
            continue
        smp_src, src_loop, _ = retarget.play(src.anims.anims[idx], e.bone_count[src_t], ss)
        lay = layer.for_slot(len(smp_src), src_loop) if layer and (layer.slots is None or s in layer.slots) else None
        r = retarget.transfer(src, src_t, ss, typ, trest, bone_map, hips, spec.get('root_scale', 1.0),
                              num(spec.get('ref_slot', 0)), layered=lay.matrices if lay else None)
        smp = []
        for t in range(r['n']):
            pose = [list(v) for v in trest]
            for b, seq in r['rot'].items():
                pose[b][3:6] = [round(x) for x in seq[t]]
            if hips:
                hb = hips[0]
                pose[hb][6:9] = [round(trest[hb][6 + i] + r['hips'][t][i]) for i in range(3)]
            pose[0][3:6] = list(smp_src[t][0][3:6])          # the entity's facing (turns)
            kr = (spec.get('root_slots') or {}).get(f'{s:#04x}', 1.0)    # rule (list option "root_slots"): a walk whose ground travel is
            pose[0][6:9] = [round(x * kr) for x in r['root'][t]]       # scaled again, so short legs are not outrun by the body
            if lay:
                for b, e3 in lay.eulers(t).items():
                    pose[b][3:6] = e3
            if tail and (s in [num(x) for x in tail.get('slots', [])] or 'slots' not in tail):
                ph = 2 * math.pi * t / tail.get('period', 20)
                for k, b in enumerate(tail['bones']):
                    pose[b][4] += round(tail.get('amp', 40) * math.sin(ph - 0.8 * k))
            smp.append(pose)
        if spec.get('gait') and not native:           # rule (tools/rigfix.py gait_spec): legs the donor map leaves out walk by themselves
            import rigfix
            rigfix.gait(smp, spec['gait'], skeleton(model))
        lp = r['loop']
        if len(smp) > mmd.MAX_FRAME - 8:      # rule: a source slot longer than the frame field (Greymon's 0x1B, 4501
            log(f'  slot {s:#04x}: {len(smp)} ticks cut to {mmd.MAX_FRAME - 8} (frame field)')  # ticks) is cut
            smp = smp[:mmd.MAX_FRAME - 8]
            lp = lp if lp is not None and lp < len(smp) - 2 else None
        mmd.close_loop(smp, lp)
        ev = [(k, 'sound', dict(bank=c['bank'], note=c['note'])) for k, kind, c in r['events']
              if kind == 'sound' and k < len(smp)]
        anim = mmd.encode_anim(smp, nb, lp, ev, tol=spec.get('tol', 1))
        if len(anim.build()) > SLOT_MAX_BYTES and len(smp) > SLOT_CUT_TICKS:
            # rule: a retargeted slot over 20 KB (Greymon's 0x1B: a 20-tick stride repeated 225 times while the root
            # travels, 4087 ticks, 370 KB on a 30-bone body) is cut to its first 120 ticks (six strides)
            log(f'  slot {s:#04x}: {len(smp)} ticks are {len(anim.build())} bytes: cut to {SLOT_CUT_TICKS}')
            smp = smp[:SLOT_CUT_TICKS]
            lp = None
            mmd.close_loop(smp, lp)
            ev = [x for x in ev if x[0] < len(smp)]
            anim = mmd.encode_anim(smp, nb, lp, ev, tol=spec.get('tol', 1))
        base.anims.table += [None] * (s + 1 - len(base.anims.table))
        base.anims.table[s] = len(base.anims.anims)
        cache[idx] = len(base.anims.anims)
        base.anims.anims.append(anim)
        done[s] = (f'retarget {src_t}:{ss:#04x}', r['n'], len(anim.build()))
    for s, c in sorted((num(k), v) for k, v in spec.get('own', {}).items()):
        # native slots: {"slot": {"from": native slot, "stretch": factor}}; a slot of its own, slowed down (the tired walk)
        # or copied (the training run)
        fs = num(c['from'])
        a = base.anims.anims[base.anims.table[fs]]
        if c.get('stretch', 1.0) == 1.0:
            idx = base.anims.table[fs]
        else:
            smp, lp, evs = retarget.play(a, nb, fs)
            k = float(c['stretch'])
            n = len(smp) - 1
            m2 = round(n * k)
            out = []
            for t in range(m2 + 1):
                x = t / k
                i0 = min(int(x), n)
                i1 = min(i0 + 1, n)
                u = x - i0
                out.append([[round(p + (q - p) * u) for p, q in zip(va, vb)] for va, vb in zip(smp[i0], smp[i1])])
            lp2 = None if lp is None else round(lp * k)
            ev = []
            for kk, kind, ins in evs:
                if kind == 'sound':
                    ev.append((min(round(kk * k), m2 - 1), 'sound', dict(bank=ins['bank'], note=ins['note'])))
                elif kind == 'tex' and c.get('tex', True):
                    ev.append((min(round(kk * k), m2 - 1), 'tex', dict(src=tuple(ins['src']), size=tuple(ins['size']),
                                                                       dst=tuple(ins['dst']))))
            if lp2 is not None and lp2 >= len(out) - 1:
                lp2 = None
            mmd.close_loop(out, lp2)
            base.anims.anims.append(mmd.encode_anim(out, nb, lp2, ev, tol=spec.get('tol', 1)))
            idx = len(base.anims.anims) - 1
        base.anims.table += [None] * (s + 1 - len(base.anims.table))
        base.anims.table[s] = idx
        done[s] = (f'own {fs:#04x} x{c.get("stretch", 1.0)}', 0, 0)
    # source-game animations
    clips, maps = {}, {}
    for s, c in sorted(clips_spec.items()):
        kw = {k: c[k] for k in ('start', 'end', 'speed', 'hips', 'hz', 'root_scale', 'loop', 'settle', 'rise') if k in c}
        cname = f'{c["anim"]}@{s:#04x}'
        clips[cname] = clip(model, c['anim'], **kw)
        maps[cname] = s
        if 'sounds_from' in c:            # sounds of a source DW1 slot (bank 4 = this Digimon's voice)
            pass
    m = base
    if clips:
        m, d2 = import_clips(base, model, clips, maps, os.path.join(workdir, f'{typ}-clips.gltf'),
                             spec.get('tol_clips', spec.get('tol', 1)), log)
        for s, (name, n, ls, why, size) in d2.items():
            done[s] = (name, n, size)
    # sounds for the clip slots: copy the timing of the source slot they replace
    sfrom = {num(t): num(f) for t, f in spec.get('slot_from', {}).items()}
    for s, c in clips_spec.items():
        ss = sfrom.get(s, s)
        if c.get('sounds', True) and ss < len(src.anims.table) and src.anims.table[ss] is not None:
            ev = mmd.anim_events(src.anims.anims[src.anims.table[ss]], e.bone_count[src_t], ss, ['sound'])
            if ev:
                a = m.anims.anims[m.anims.table[s]]
                smp, ls, _ = retarget.play(a, nb, s)
                n = len(smp)
                m.anims.anims[m.anims.table[s]] = mmd.encode_anim(smp, nb, ls, [x for x in ev if x[0] < n],
                                                                    tol=0)
    # drop animations no slot uses
    used = sorted(set(x for x in m.anims.table if x is not None))
    remap = {o: k for k, o in enumerate(used)}
    m.anims.anims = [m.anims.anims[o] for o in used]
    m.anims.table = [remap[x] if x is not None else None for x in m.anims.table]
    data = m.build()
    for s in sorted(done):
        name, n, size = done[s]
        log(f'  slot {s:#04x} <- {name}: {n} ticks, {size} bytes')
    log(f'{out_mmd}: {len(data)} bytes (PARTNER_MODEL_BUFFER {PARTNER_MMD_MAX}: '
        f'{PARTNER_MMD_MAX - len(data)} bytes free)')
    if len(data) > PARTNER_MMD_MAX:
        raise SystemExit(f'{out_mmd}: {len(data)} bytes do not fit PARTNER_MODEL_BUFFER ({PARTNER_MMD_MAX})')
    open(out_mmd, 'wb').write(data)
    if not native:
        open(out_tex, 'wb').write(build_tim(model.idx, model.pals))
    return data

