"""Shared helpers for the partner models of this folder (WaruMonzaemon, Myotismon,
ShogunGekomon): retargeting another Digimon's slots onto a model, layering extra motion
on a pose in model axes, and assembling the animation table within the partner buffer.

Conventions (docs/mods/models.md § 2.2): Y points down, the Digimon faces -Z, angles are
1/4096 of a turn and a bone's local matrix is Rx·Ry·Rz. A pose is a list of nb entries
[sx sy sz rx ry rz tx ty tz]; entry 0 holds the accumulated root motion in tx..tz.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import mmd  # noqa: E402
import retarget  # noqa: E402

PARTNER_MODEL_BUFFER = 0x18800
UNITS = 4096 / 360.0
IDENT = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]


def load(rel):
    return mmd.MMD.load(os.path.join(ROOT, rel))


def nbones(t):
    return mmd.exe().bone_count[t]


def play(m, slot, max_ticks=6000):
    """Per-tick poses of a slot of m (root motion accumulated in entry 0), loop sample, events
    as (sample, kind, dict)."""
    nb = nbones(m.type)
    smp, loop, ev = retarget.play(m.anims.anims[m.anims.table[slot]], nb, slot, max_ticks)
    events = []
    for k, kind, c in ev:
        if kind == 'sound':
            events.append((k, 'sound', dict(bank=c['bank'], note=c['note'])))
        elif kind == 'tex':
            events.append((k, 'tex', dict(src=c['src'], size=c['size'], dst=c['dst'])))
    return smp, loop, events


def rest(m, slot=0, tick=0):
    """Pose at a tick of a slot (bone 0 cleared): the rest a retarget starts from."""
    if tick == 0:
        return retarget.rest_pose(m, nbones(m.type), slot)
    smp, _, _ = play(m, slot, max_ticks=tick + 1)
    pose = [list(v) for v in smp[tick]]
    pose[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
    return pose


# ---------------------------------------------------------------- model-axis layering
def mdeg(rx, ry, rz):
    return mmd.rot_matrix(rx * UNITS, ry * UNITS, rz * UNITS)


def world_rots(t, pose):
    return retarget.world_rots(mmd.exe().skeleton[t], pose)


def layer(t, pose, rot=None, off=None, prev=None):
    """Adds motion to an engine pose. rot: {bone: (rx, ry, rz) degrees} applied about the
    bone's joint in MODEL axes (as the parent is oriented in `pose`): +rx tips the top of
    an upright piece forward (-Z), +rz tips it towards -X... (Rx·Ry·Rz of the model frame).
    off: {bone: (dx, dy, dz)} moves the joint in model axes. prev: the previous tick's
    output (keeps the Euler solution continuous). Returns a new pose."""
    skel = mmd.exe().skeleton[t]
    out = [list(v) for v in pose]
    if not rot and not off:
        return out
    W = world_rots(t, pose)
    for b in range(1, len(pose)):
        par = skel[b][1]
        Wp = W[par] if par >= 0 else IDENT
        if rot and b in rot and any(rot[b]):
            D = mdeg(*rot[b])
            L = retarget.rot_of(pose[b])
            M = retarget.m3mul(retarget.m3mul(retarget.m3t(Wp), retarget.m3mul(D, Wp)), L)
            ref = prev[b][3:6] if prev else pose[b][3:6]
            out[b][3:6] = [round(x) for x in mmd.matrix_euler(M, ref)]
        if off and b in off and any(off[b]):
            d = off[b]
            loc = [sum(Wp[j][i] * d[j] for j in range(3)) for i in range(3)]   # Wp^T · d
            out[b][6:9] = [round(out[b][6 + i] + loc[i]) for i in range(3)]
    return out


def lerp_pose(a, b, u):
    return [[x + (y - x) * u for x, y in zip(va, vb)] for va, vb in zip(a, b)]


# ---------------------------------------------------------------- retargeting
def retarget_samples(src, slot, tgt_type, tgt_rest, bone_map, hips=None, root_scale=1.0, ref_slot=0,
                     layered=None):
    """tools/retarget.transfer, turned into full target poses (unmapped bones at tgt_rest)."""
    r = retarget.transfer(src, src.type, slot, tgt_type, tgt_rest, bone_map, hips, root_scale, ref_slot,
                          layered)
    smp = []
    for t in range(r['n']):
        pose = [list(v) for v in tgt_rest]
        for b, seq in r['rot'].items():
            pose[b][3:6] = [round(x) for x in seq[t]]
        if hips:
            hb = hips[0]
            pose[hb][6:9] = [round(tgt_rest[hb][6 + i] + r['hips'][t][i]) for i in range(3)]
        pose[0][6:9] = [round(x) for x in r['root'][t]]
        smp.append(pose)
    events = []
    for k, kind, c in r['events']:
        if kind == 'sound':
            events.append((k, 'sound', dict(bank=c['bank'], note=c['note'])))
        elif kind == 'tex':
            events.append((k, 'tex', dict(src=c['src'], size=c['size'], dst=c['dst'])))
    return smp, r['loop'], events


def map_events(events, sound=None, tex=None):
    """sound(bank, note) -> (bank, note) or None; tex(event dict) -> list of dicts (or [])."""
    out = []
    for k, kind, c in events:
        if kind == 'sound':
            s = sound(c['bank'], c['note']) if sound else (c['bank'], c['note'])
            if s:
                out.append((k, 'sound', dict(bank=s[0], note=s[1])))
        elif kind == 'tex':
            if tex:
                out += [(k, 'tex', d) for d in tex(c)]
            else:
                out.append((k, kind, c))
    return out


def keyed(smp, step, loop=None):
    """Keeps every `step`-th sample (and the first, last and loop start) and interpolates the
    rest linearly: fewer keyframes for slow motion. Root motion (entry 0) is kept per tick."""
    if step <= 1 or len(smp) < 3:
        return smp
    n = len(smp)
    ks = sorted(set([0, n - 1] + ([loop] if loop is not None else []) + list(range(0, n, step))))
    out = []
    for t in range(n):
        if t in ks:
            out.append([list(v) for v in smp[t]])
            continue
        a = max(k for k in ks if k < t)
        b = min(k for k in ks if k > t)
        u = (t - a) / (b - a)
        p = [[round(x + (y - x) * u) for x, y in zip(va, vb)] for va, vb in zip(smp[a], smp[b])]
        p[0] = list(smp[t][0])
        out.append(p)
    return out


def encode(smp, nb, loop, events, tol=1, step=1):
    smp = keyed(smp, step, loop)
    mmd.close_loop(smp, loop)
    return mmd.encode_anim(smp, nb, loop, events, tol=tol)


# ---------------------------------------------------------------- assembling the file
class Builder:
    """Animation table of a partner model: original animations kept as they are (exact),
    new ones encoded; identical animations shared."""

    def __init__(self, base, size=0x40):
        self.base = base
        self.sec = mmd.AnimSection()
        self.sec.table = [None] * size
        self.keys = {}

    def put(self, slot, anim):
        key = anim.build()
        if key not in self.keys:
            self.keys[key] = len(self.sec.anims)
            self.sec.anims.append(anim)
        while len(self.sec.table) <= slot:
            self.sec.table.append(None)
        self.sec.table[slot] = self.keys[key]

    def keep(self, *slots, tol=None):
        """The base model's own animations; with tol, replayed and re-encoded (smaller,
        within tol units of the original at every tick)."""
        for s in slots:
            a = self.base.anims.anims[self.base.anims.table[s]]
            if tol is not None:
                smp, loop, ev = play(self.base, s)
                b = encode(smp, nbones(self.base.type), loop, ev, tol=tol)
                if len(b.build()) < len(a.build()):
                    a = b
            self.put(s, a)

    def alias(self, slot, other):
        self.sec.table[slot] = self.sec.table[other]

    def missing(self, required):
        return [hex(s) for s in required if s >= len(self.sec.table) or self.sec.table[s] is None]

    def build(self, tmd, out_path, pad=False, label=''):
        # trim the table after the last used slot
        last = max(i for i, x in enumerate(self.sec.table) if x is not None)
        self.sec.table = self.sec.table[:last + 1]
        out = mmd.MMD()
        out.tmd, out.anims = tmd, self.sec
        data = out.build()
        size = len(data)
        if os.environ.get('SIZES'):
            for slot, i in enumerate(self.sec.table):
                if i is not None:
                    print(f'  slot {slot:#04x} anim {i:2d} {len(self.sec.anims[i].build())}')
        if size > PARTNER_MODEL_BUFFER and os.environ.get('NO_SIZE_CHECK'):
            print('too big:', size)
            open(out_path, 'wb').write(data)
            return size
        assert size <= PARTNER_MODEL_BUFFER, f'{size} bytes > PARTNER_MODEL_BUFFER ({PARTNER_MODEL_BUFFER})'
        if pad:
            data += bytes(PARTNER_MODEL_BUFFER - size)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        open(out_path, 'wb').write(data)
        used = sum(x is not None for x in self.sec.table)
        print(f'{out_path}: {label}{len(self.sec.anims)} animations in {used} slots, {size} bytes '
              f'(PARTNER_MODEL_BUFFER {PARTNER_MODEL_BUFFER}, {PARTNER_MODEL_BUFFER - size} free)'
              f'{" padded" if pad else ""}')
        return size


# every slot the 64 partner models have (the union; see content/models/cherrymon/clips.py)
PARTNER_SLOTS = ([0, 1, 2, 3, 4, 5] + list(range(7, 0x14)) + list(range(0x15, 0x1A)) + [0x1B] +
                 list(range(0x21, 0x26)) + list(range(0x28, 0x2D)))


def scale_samples(smp, k):
    """Multiplies every translation (bone offsets and root motion) by k."""
    return [[v[:6] + [round(x * k) for x in v[6:9]] for v in s] for s in smp]


def scale_mesh(m, k):
    for i, (x, y, z, p) in enumerate(m.tmd.verts):
        m.tmd.verts[i] = (round(x * k), round(y * k), round(z * k), p)


def args():
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    return (a[0] if a else None), ('--pad' in sys.argv)


def deg(v):
    return v * 360.0 / 4096


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def smooth(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def bump(x):
    return math.sin(math.pi * clamp(x))


def wave(t, period, phase=0.0):
    return math.sin(2 * math.pi * (t / period + phase))


def resample(smp, speed):
    """A looping cycle played at `speed` times its rate (0.75: slower): linear in every
    channel, root motion included, so feet and ground speed stay matched. The first and
    last samples are kept (the last equals the loop start's pose)."""
    n = len(smp) - 1
    m = max(2, round(n / speed))
    out = []
    for i in range(m + 1):
        x = i * n / m
        a = min(int(x), n - 1)
        u = x - a
        out.append([[round(p + (q - p) * u) for p, q in zip(va, vb)] for va, vb in zip(smp[a], smp[a + 1])])
    return out


def layered_cycle(t, smp, rot=None, off=None):
    """layer() over every sample of a cycle; rot/off are functions of the sample index."""
    out, prev = [], None
    for i, pose in enumerate(smp):
        p = layer(t, pose, rot(i) if rot else None, off(i) if off else None, prev)
        p[0] = list(pose[0])
        out.append(p)
        prev = p
    return out
