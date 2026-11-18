"""Nyaromon's (species 476) field clips: a calm idle and three low, soft steps, with blinking eyes.

Nyaromon keeps Tokomon's eleven-bone rig, but its mesh is one rigid object on bone 2 (cat head, ears and tail; the
other bones only carry collapsed points). Tokomon's own clips hop high (a 130-unit jump, the soles 0 to 133 above the
floor) and slide 90 to 130 % of the body's travel. These are lower and slower, in the way a small cat waddles:

  idle   96 ticks: two slow breaths, a curious look to each side with a head tilt, a mew, three blinks (one a double)
  walk   2 steps of 16 ticks (20 units a tick), 5 high: a weight shift and a soft squash before each step, a roll
         and a twist of the head that alternate, a landing wobble, one blink
  tired  2 steps of 24 ticks (12 units a tick), 2.5 high: head low and forward, heavy lids, one slow blink
  run    3 steps of 14 ticks (37 units a tick), 9 high: a determined little trot, mouth open, one blink

The body lands and stays where it landed until it takes off (no slide while it is down); the root, which the game
follows, moves steadily. After every pose the body is lowered or raised so the lowest point of the mesh is exactly on the
floor on the ground and `lift` units above it in the air. The tail and the ears are part of the head mesh, so their
follow-through: the head's pitch lags the rise, and the tail and the ears are damped springs driven by the head's own accelerations
(a lagging wave along the two tail segments), with a bias for each clip (a gentle sway and a flick in the idle, a counter-sway
to the waddle, hanging low and slow when tired, streaming behind in the run).

The face page gets four eye frames next to the face (`paint_blinks`): a lid, a heavy lid, the closed eye, each a 40 x 28
texel window that overwrites the whole open eye, and a blink is a lid, a closed eye for two or three ticks, a lid, the
open eye. Mouth frames are windows of their own (the closed mouth, the half-open and the wide one), so a mouth change
never reopens a closed eye.

Slots 0, 2, 3 and 4 and their aliases 33, 35 and 36 (the same programs in the donor) are replaced. The mesh and the other
slots do not change.

    python -m tools.models.field_animations.nyaromon_calm SRC.MMD OUT.MMD [SRC.TIM OUT.TIM]
where SRC is the baby as built by `tools.models.babies` before this change.
"""
import copy
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import mmd  # noqa: E402
import motioncyclelayer  # noqa: E402
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402

SPECIES = 476
DONOR = 30
NB = 11
BODY = 2
DEG = 4096 / 360
SLOTS = (0, 2, 3, 4)
ALIASES = {33: 0, 35: 2, 36: 4}                  # slots that play the same program in the donor
TAIL_A, TAIL_B, EAR_R, EAR_L = 3, 4, 7, 8       # bones of the tail's base and tip segments and of the right and left ear
APPENDAGES = (TAIL_A, TAIL_B, EAR_R, EAR_L)
OBJ = {TAIL_A: 1, TAIL_B: 2, EAR_R: 5, EAR_L: 6}  # the object each of them carries
TAIL_UV = (76, 212, 100, 125)                    # texture window (u0, u1, v0, v1) of the tail strip, of the ears' two strips
EAR_UV = (120, 184, 50, 94)
RING_PIVOT_A, RING_JOINT = 96, 133               # u of the ring the tail's base turns about and of the joint between the segments

# ------------------------------------------------------------------ the face page
# Windows are (x in words of 4 texels, y in rows). The face block is 72 x 48 texels at (0, 0) (u = 0 is the centre line,
# the other half is mirrored); (0, 48) holds the plain face, the eye sits at texels 20-59 x 4-31, the mouth at 0-39 x 32-47.
EYE_SIZE, EYE_DST = (10, 28), (5, 4)
MOUTH_SIZE, MOUTH_DST = (10, 16), (0, 32)
EYES = {'open': (5, 52), 'lid': (46, 48), 'closed': (54, 48), 'heavy': (46, 76)}      # sources of the eye window
MOUTHS = {'shut': (0, 80), 'half': (18, 32), 'wide': (36, 32)}                          # sources of the mouth window
FACE = ((0, 48), (18, 48), (0, 0))                                                      # source, size, destination of the whole face
INK, BG = 1, 8                                                                          # palette entries of the face row


def paint_blinks(tim_bytes):
    """The same page with the lid, heavy-lid and closed-eye windows painted (from the plain face's own eye) at 184 / 216 x 48 / 76."""
    tim = mmd.Tim4(tim_bytes)
    w = tim.w
    x0, y0 = EYE_DST[0] * 4, EYE_DST[1] + 48
    eye = [[tim.idx[(y0 + r) * w + x0 + c] for c in range(40)] for r in range(28)]
    assert all(v == BG for v in eye[0]) and any(v != BG for row in eye for v in row)

    def lid(cut0, thick=2, slant=0.):
        """The open eye under a lid whose edge is an arch `cut0` rows down (lower at the corners), inked; `slant` rows lower at the outer corner, higher at the inner one (sleepy)."""
        out = [[BG] * 40 for _ in range(28)]
        for c in range(40):
            cut = cut0 + 3 * ((c - 19.5) / 19.5) ** 2 + slant * (c - 19.5) / 19.5
            for r in range(28):
                if eye[r][c] != BG and r >= cut:
                    out[r][c] = INK if r < cut + thick else eye[r][c]
        return out

    def closed():
        """The eye closed: an inked arc bulging down, thick in the middle, with the corners turned up."""
        out = [[BG] * 40 for _ in range(28)]
        for c in range(3, 37):
            u = (c - 19.5) / 17
            r = 12 + 5 * (1 - u * u)
            thick = 2.3 if abs(u) < .75 else 1.4
            for rr in range(28):
                if abs(rr + .5 - r) <= thick:
                    out[rr][c] = INK
        return out
    frames = {'lid': lid(12), 'closed': closed(), 'heavy': lid(17, 3, slant=3.5)}
    for name, rows in frames.items():
        sx, sy = EYES[name][0] * 4, EYES[name][1]
        for r in range(28):
            for c in range(40):
                tim.idx[(sy + r) * w + sx + c] = rows[r][c]
    return tim.to_bytes()


# ------------------------------------------------------------------ gaits
# (tick in the step, value); the body lands at tick 0 and leaves the ground at `contact`.
#   squash  1 = the deepest crouch, negative = stretched    pitch  degrees, positive leans forward
# `wiggle` is the roll rocking of the crouch before the step, `land` the damped wobble after landing, `air` the tilt in
# the air, `lag` the delayed lean of the back of the head (pitch against the rise).
GAITS = {
    2: dict(name='walk', period=16, hops=2, contact=8, speed=20, height=5, side_height=(1.0, .85), base_pitch=2,
            squash={0: .3, 1: .45, 3: .2, 5: .1, 7: .4, 8: .45, 9: -.05, 11: -.3, 13: -.2, 15: .1},
            pitch={0: -1, 2: -1.5, 5: -.5, 7: 1, 8: 1.5, 11: 2.5, 13: 1.5, 15: 0}, roll=4.5, yaw=3.5,
            wiggle=1.2, land=1.2, air=2.5, lag=2.5,
            eyes=[(0, 'open'), (20, 'lid'), (21, 'closed'), (24, 'lid'), (25, 'open')],
            mouth=[(0, 'shut')],
            tail=dict(sway=(8, 15), bob=(3, 6), curl=(2, 4), lag=(.05, .17), bias=(0, 0, 0, 0, 0, 0)), ears=2.5),
    3: dict(name='tired', period=24, hops=2, contact=13, speed=12, height=2.5, side_height=(1.0, .85), base_pitch=8,
            squash={0: .35, 2: .5, 6: .3, 10: .4, 14: .5, 15: .3, 17: -.05, 20: .1, 23: .3},
            pitch={0: 2, 4: 0, 9: 1, 14: 3, 17: 4, 21: 2, 23: 2}, roll=5, yaw=3,
            wiggle=0, land=1.5, air=1.5, lag=1.5,
            eyes=[(0, 'lid'), (12, 'heavy'), (16, 'closed'), (23, 'heavy'), (26, 'lid'), (38, 'heavy'), (41, 'closed'), (46, 'heavy'), (47, 'lid')],
            mouth=[(0, 'shut')],
            tail=dict(sway=(4, 8), bob=(2, 4), curl=(1.5, 3), lag=(.06, .2), bias=(0, 2, 12, 0, 3, 16)), ears=1.5),
    4: dict(name='run', period=14, hops=3, contact=5, speed=37, height=9, side_height=(1.0, .9), base_pitch=9,
            squash={0: .5, 1: .6, 3: .25, 4: .5, 5: .2, 6: -.3, 8: -.4, 11: -.2, 13: .1},
            pitch={0: -1, 3: -2, 5: -1, 6: 2, 8: 5, 11: 3, 13: 0}, roll=3, yaw=2.5,
            wiggle=.6, land=.8, air=2.5, lag=2.5,
            eyes=[(0, 'open'), (28, 'lid'), (29, 'closed'), (31, 'lid'), (32, 'open')],
            mouth=[(0, 'shut'), (6, 'half'), (12, 'shut'), (20, 'half'), (26, 'shut'), (34, 'half'), (40, 'shut')],
            tail=dict(sway=(7, 14), bob=(5, 10), curl=(2, 4), lag=(.07, .22), bias=(0, -8, -4, 0, -10, -6)), ears=4),
}
IDLE_TICKS = 96
IDLE_FLICKS = (22, 74)                           # ticks of the tail's flicks
IDLE_LOOK = [(0, 0), (4, 0), (26, 8), (42, 8), (60, 0), (62, 0), (78, -6), (82, -6), (96, 0)]
IDLE_TILT = [(0, 0), (22, 0), (32, 4), (42, 4), (52, 0), (68, 0), (76, -4), (86, -4), (96, 0)]   # a curious head tilt with each look
IDLE_EYES = [(0, 'open'), (14, 'lid'), (15, 'closed'), (18, 'lid'), (19, 'open'),                  # a single blink
             (44, 'lid'), (45, 'closed'), (47, 'lid'), (48, 'open'),                              # a double blink
             (55, 'lid'), (56, 'closed'), (58, 'lid'), (59, 'open'),
             (80, 'lid'), (81, 'closed'), (84, 'lid'), (85, 'open')]                              # a slow one
IDLE_MOUTH = [(0, 'shut'), (30, 'half'), (34, 'wide'), (38, 'half'), (41, 'shut')]                # a small mew while it looks


# ------------------------------------------------------------------ curves
def periodic(keys, period):
    """A smooth closed curve through (tick, value) keys (Catmull-Rom over the period)."""
    ks = sorted(keys.items())
    n = len(ks)

    def at(t):
        t %= period
        i = max(k for k in range(n) if ks[k][0] <= t) if t >= ks[0][0] else n - 1
        t0, p1 = ks[i]
        t1, p2 = ks[(i + 1) % n]
        p0, p3 = ks[(i - 1) % n][1], ks[(i + 2) % n][1]
        span = (t1 - t0) % period or period
        u = ((t - t0) % period) / span
        return .5 * (2 * p1 + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u
                     + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3)
    return at


def eased(keys):
    def at(t):
        for (t0, a), (t1, b) in zip(keys, keys[1:]):
            if t0 <= t <= t1:
                u = (t - t0) / (t1 - t0)
                return a + (b - a) * (1 - math.cos(math.pi * u)) / 2
        return keys[-1][1]
    return at


def wave(cycles, n, t, phase=0.):
    return math.sin(2 * math.pi * (cycles * t / n + phase))



# ------------------------------------------------------------------ the mesh
def _window(d, box):
    us, vs = [u for u, v in d['uv']], [v for u, v in d['uv']]
    return box[0] <= min(us) and max(us) <= box[1] and box[2] <= min(vs) and max(vs) <= box[3]


def split_mesh(model):
    """Move the tail and the ears out of object 0 into the objects of the appendage bones. Returns {bone: rest translation}.

    Vertices go bone-local (the joint's own coordinates), normals and UVs are copied untouched; the base segment also
    takes the first ring-row of the tip segment, so a bent joint shows no gap."""
    import numpy as np
    t = model.tmd
    head = t.objects[0]
    verts = [list(v) for v in t.obj_verts(0)]
    norms = [list(v) for v in t.obj_norms(0)[:head.nnorm]]
    prims = [p.decode() for p in head.prims]
    tail = [d for d in prims if _window(d, TAIL_UV)]
    ears = [d for d in prims if _window(d, EAR_UV) and d not in tail]
    rest = [d for d in prims if d not in tail and d not in ears]
    assert len(tail) == 120 and len(ears) == 32, (len(tail), len(ears))
    xyz = lambda ids: np.array([verts[i][:3] for i in ids], float)
    ring_ids = lambda u0: sorted({i for d in tail for i, (u, v) in zip(d['verts'], d['uv']) if abs(u - u0) <= 2})
    pivot_a = np.round(xyz(ring_ids(RING_PIVOT_A)).mean(0))
    joint = np.round(xyz(ring_ids(RING_JOINT)).mean(0))
    base = [d for d in tail if max(u for u, v in d['uv']) <= RING_JOINT + 12]  # the base also takes the first row of the tip
    tip = [d for d in tail if min(u for u, v in d['uv']) >= RING_JOINT - 2]
    assert base and tip and len(set(map(id, base)) | set(map(id, tip))) == len(tail)
    right = [d for d in ears if np.mean([verts[i][0] for i in d['verts']]) > 0]
    left = [d for d in ears if np.mean([verts[i][0] for i in d['verts']]) <= 0]
    assert len(right) == len(left) == 16
    ear_pivot = lambda group: (lambda x: np.round([x[:, 0].mean(), x[:, 1].max(), x[:, 2].mean()]))(
        xyz(sorted({i for d in group for i in d['verts']})))
    pieces = {OBJ[TAIL_A]: (base, pivot_a), OBJ[TAIL_B]: (tip, joint), OBJ[EAR_R]: (right, ear_pivot(right)),
              OBJ[EAR_L]: (left, ear_pivot(left))}

    def gather(group, pivot):
        vmap, nmap, nv, nn, out = {}, {}, [], [], []
        for d in group:
            d = dict(d)
            for key, src, dst, pool, shift in (('verts', verts, vmap, nv, pivot), ('norms', norms, nmap, nn, None)):
                new = []
                for i in d[key]:
                    if i not in dst:
                        dst[i] = len(pool)
                        pool.append([int(round(src[i][0] - shift[0])), int(round(src[i][1] - shift[1])),
                                     int(round(src[i][2] - shift[2])), src[i][3]] if shift is not None else list(src[i]))
                    new.append(dst[i])
                d[key] = new
            out.append(mmd.Prim.encode(d))
        return nv, nn, out
    pools = {0: gather(rest, np.zeros(3))}
    for oi, (group, pivot) in pieces.items():
        pools[oi] = gather(group, pivot)
    allv, alln = [], []
    for oi, ob in enumerate(t.objects):
        if oi in pools:
            nv, nn, ps = pools[oi]
            ob.prims = ps
        else:
            nv, nn = [list(v) for v in t.obj_verts(oi)], [list(v) for v in t.obj_norms(oi)[:ob.nnorm]]
        ob.vert_start, ob.nvert, ob.norm_start, ob.nnorm = len(allv), len(nv), len(alln), len(nn)
        allv += nv
        alln += nn
    t.verts = [tuple(v) for v in allv]
    t.norms = [tuple(v) for v in alln]
    pa, jt = [int(round(x)) for x in pivot_a], [int(round(x)) for x in joint]
    return {TAIL_A: pa, TAIL_B: [j - a for j, a in zip(jt, pa)],
            EAR_R: [int(round(x)) for x in pieces[OBJ[EAR_R]][1]], EAR_L: [int(round(x)) for x in pieces[OBJ[EAR_L]][1]]}


def rest_triangles(model, pose):
    """The set of distinct non-degenerate triangles (world corners, UVs, colours) of a model in a pose."""
    import animsheet
    out = set()
    for tri, uv, d in animsheet.world_tris(model, pose, mmd.exe().skeleton[SPECIES]):
        corners = tuple((round(x), round(y), round(z)) for x, y, z in tri)
        if len(set(corners)) == 3:
            out.add((tuple(sorted(zip(corners, tuple(uv or ())))), tuple(d['colors'][:1])))
    return out


def hold_appendages(model, rest_t):
    """Every other program keeps the four appendage bones at rest (Tokomon's own swing them wildly): their keys are dropped
    and their starting pose is the rest pose."""
    for anim in model.anims.anims:
        for b in APPENDAGES:
            anim.pose[b - 1] = ([4096, 4096, 4096] if anim.has_scale else []) + [0, 0, 0] + list(rest_t[b])
        for ins in anim.instrs:
            if ins['op'] == 'key':
                ins['bones'] = [e for e in ins['bones'] if e['bone'] not in APPENDAGES]

# ------------------------------------------------------------------ the rig
class Rig:
    def __init__(self, model, rest_t):
        self.model = model
        frames = _slot0(model)
        self.rest = [list(v) for v in frames[0]]
        self.rest[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
        for b in APPENDAGES:
            self.rest[b][3:6] = [0, 0, 0]
            self.rest[b][6:9] = rest_t[b]
        self.skel = mmd.exe().skeleton[SPECIES]
        self.verts = {oi: [v[:3] for v in model.tmd.obj_verts(oi)] for oi, _ in self.skel if oi >= 0}
        self.floor = self._low(self.rest)

    def _low(self, pose):
        mats = mmd.bone_matrices(self.model, pose)
        low = -1e9
        for b, (oi, _) in enumerate(self.skel):
            if oi >= 0:
                M = mats[b]
                low = max(low, max(M[1][0] * x + M[1][1] * y + M[1][2] * z + M[1][3] for x, y, z in self.verts[oi]))
        return low

    def pose(self, squash=0., pitch=0., roll=0., yaw=0., lift=0., tail=(), ears=()):
        """`tail`: (pitch, yaw, roll) of the base segment then of the tip segment, degrees; `ears`: the roll of each ear."""
        p = copy.deepcopy(self.rest)
        for i, b in enumerate((TAIL_A, TAIL_B)):
            if tail:
                p[b][3:6] = [round(x * DEG) for x in tail[3 * i:3 * i + 3]]
        for b, rz in zip((EAR_R, EAR_L), ears):
            p[b][5] = round(rz * DEG)
        b = p[BODY]
        b[1] = round(4096 * (1 - .14 * squash))
        b[0] = b[2] = round(4096 * (1 + .07 * squash))
        b[3], b[4], b[5] = round(pitch * DEG), round(yaw * DEG), round(roll * DEG)
        # the body hangs from its centre: put the lowest point of the mesh on the floor, then lift it
        p[BODY][7] = 0
        p[BODY][7] = math.floor(self.floor - lift - self._low(p))
        return p


def _slot0(model):
    import animsheet
    return animsheet.slot_frames(model, NB, 0)[0]


# ------------------------------------------------------------------ events
def eye(tick, name):
    return (tick, 'tex', dict(op='tex', frame=tick + 1, src=EYES[name], size=EYE_SIZE, dst=EYE_DST))


def mouth(tick, name):
    return (tick, 'tex', dict(op='tex', frame=tick + 1, src=MOUTHS[name], size=MOUTH_SIZE, dst=MOUTH_DST))


def face(tick):
    """The whole plain face: eyes open, mouth shut (the first event of every clip)."""
    src, size, dst = FACE
    return (tick, 'tex', dict(op='tex', frame=tick + 1, src=src, size=size, dst=dst))


# ------------------------------------------------------------------ the clips
def gait(rig, slot, sound):
    g = GAITS[slot]
    P, hops, c = g['period'], g['hops'], g['contact']
    n = P * hops
    squash, pitch = periodic(g['squash'], P), periodic(g['pitch'], P)
    hop = g['speed'] * P
    f = P - c

    def hscale(t):
        return g['side_height'][(t // P) % 2]

    def height(t):
        tau = t % P
        if tau <= c:
            return 0.
        s = (tau - c) / f
        return 4 * g['height'] * hscale(t) * s * (1 - s)

    def body_z(t):
        k, tau = divmod(t, P)
        if tau <= c:
            return k * hop
        s = (tau - c) / f
        return k * hop + hop * (.1 * s + .9 * (3 * s * s - 2 * s ** 3))

    mean = sum(body_z(t) - g['speed'] * t for t in range(P)) / P
    vmax = max(1., 4 * g['height'] / f)
    rise = lambda x: (height(x) - height(x - 1)) / vmax          # -1..1, up positive
    frames = []
    for t in range(n + 1):
        tt = t % n
        tau = tt % P
        side = 1 if (tt // P) % 2 == 0 else -1
        roll = g['roll'] * side * math.sin(math.pi * min(1., tau / P)) * (1 if tau else 0)
        if tau > c:                                   # a tilt in the air, against the way it leans on the ground
            roll += g['air'] * -side * math.sin(math.pi * (tau - c) / f)
        else:
            roll += g['land'] * side * math.exp(-tau / 3.) * math.sin(tau * 1.9)                    # the landing wobble
            if tau > c - 5:                                                                           # the weight shift before the step
                roll += g['wiggle'] * side * (tau - (c - 5)) / 5 * math.sin(2 * math.pi * (tau - (c - 5)) / 3.)
        lean = -g['lag'] * (rise(tt - 2) + .5 * rise(tt - 4))     # the back of the head lags: it leans back as the body rises
        yaw = g['yaw'] * wave(hops / 2 if hops % 2 == 0 else hops, n, tt, .2 + .06)               # the twist trails the roll
        pose = rig.pose(squash=squash(tau), pitch=g['base_pitch'] + pitch(tau) + lean, lift=height(tt),
                        roll=roll, yaw=yaw, tail=gait_tail(g, tt, n, rise), ears=gait_ears(g, rise, tt))
        world = -body_z(t)
        root_line = -(.5 * (body_z(t) + mean) + .5 * g['speed'] * t)
        pose[0][8] = round(root_line)
        pose[BODY][8] = round(world - root_line)
        frames.append([[int(round(x)) for x in v] for v in pose])
    events = [(k * P, 'sound', dict(sound)) for k in range(hops)]
    events += [face(0)]
    events += [eye(t, s) for t, s in g['eyes'] if t or s != 'open']
    events += [mouth(t, s) for t, s in g['mouth'] if t or s != 'shut']
    events.sort(key=lambda e: e[0])  # stable: the face first
    return frames, events


def gait_tail(g, tt, n, rise):
    """The tail of a gait: two segments, the tip a little behind the base. The sway is opposite to the waddle's roll, the
    pitch follows the body's rise with a delay (the tail streams behind it), a small roll rounds the tip's path into an oval."""
    c = n / (2. * g['period'])
    c = c if c == int(c) else n / g['period']
    sw, bob, curl, lag, bias = g['tail']['sway'], g['tail']['bob'], g['tail']['curl'], g['tail']['lag'], g['tail']['bias']
    out = []
    for i, (d1, d2) in enumerate(((3, 6), (6, 10))):
        out += [bias[3 * i] + bob[i] * rise(tt - d1) + (bob[i] * .5 * rise(tt - d2) if i else 0),
                bias[3 * i + 1] - sw[i] * wave(c, n, tt, lag[i]),
                bias[3 * i + 2] + curl[i] * wave(c, n, tt, lag[i] + .25)]
    return out


def gait_ears(g, rise, tt):
    r = g['ears'] * (rise(tt - 3) + .4 * rise(tt - 6))
    return [r, -r]


def pulse(t, centre, width):
    """A short bump, 0 outside `width` ticks around `centre`, 1 at the centre."""
    x = abs(t - centre) / width
    return 0. if x >= 1 else math.cos(math.pi / 2 * x) ** 2


def idle_tail(tt, n):
    """A slow sway (two a loop, the tip lagging), and now and then a flick of the tip with a damped overshoot."""
    flick = sum(pulse(tt, c, 16) * math.sin(2 * math.pi * (tt - c) / 13.) for c in IDLE_FLICKS)
    out = []
    for i, (lag, sw, bob) in enumerate(((.0, 6, 2), (.09, 11, 4))):
        out += [bob * wave(2, n, tt, lag + .3) + (4 * flick if i else 0),
                -sw * wave(2, n, tt, lag) + (-10 * flick if i else 0),
                2 * (i + 1) * wave(2, n, tt, lag + .25) + (8 * flick if i else 0)]
    return out


def idle_ears(tt, n):
    return [3.5 * pulse(tt, 52, 9) * math.sin(2 * math.pi * (tt - 52) / 6.), 3.5 * pulse(tt, 70, 9) * math.sin(2 * math.pi * (tt - 70) / 6.)]


def idle(rig):
    n = IDLE_TICKS
    look, tilt = eased(IDLE_LOOK), eased(IDLE_TILT)
    frames = []
    for t in range(n + 1):
        tt = t % n
        breath = .5 - .5 * math.cos(2 * math.pi * 2 * tt / n)
        squash = .22 * breath - .05
        nod = 1.5 * math.sin(math.pi * (tt - 24) / 20) ** 2 * wave(3, n, tt, .35) if 24 < tt < 44 else 0.   # a small nod while it mews
        pose = rig.pose(squash=squash, pitch=1.2 * wave(1, n, tt, .1) + 1 + nod,
                        roll=2.2 * wave(1, n, tt, .6) + tilt(tt), yaw=look(tt) + 3.5 * wave(2, n, tt, .3),
                        tail=idle_tail(tt, n), ears=idle_ears(tt, n))
        frames.append([[int(round(x)) for x in v] for v in pose])
    events = [face(0)] + [eye(t, s) for t, s in IDLE_EYES if t or s != 'open'] + [mouth(t, s) for t, s in IDLE_MOUTH if t or s != 'shut']
    events.sort(key=lambda e: e[0])  # stable: the face first
    return frames, events


# ------------------------------------------------------------------ build
def _parse(data):
    mmd.exe().skeleton[SPECIES] = mmd.exe().skeleton[DONOR]
    mmd.exe().bone_count[SPECIES] = NB
    model = mmd.MMD.parse(data, NB)
    model.type = SPECIES
    return model


def author(data):
    import animsheet
    old = _parse(data)
    new = copy.deepcopy(old)
    rest_t = split_mesh(new)
    hold_appendages(new, rest_t)
    rig = Rig(new, rest_t)
    assert rest_triangles(old, rig.rest) == rest_triangles(new, rig.rest), 'the split changed the look at rest'
    report = []
    for slot in SLOTS:
        if slot == 0:
            frames, events = idle(rig)
        else:
            _, _, src = animsheet.slot_frames(old, NB, slot)
            sound = next(dict(bank=e[2]['bank'], note=e[2]['note']) for e in src if e[1] == 'sound')
            frames, events = gait(rig, slot, sound)
        mmd.close_loop(frames, 0)
        anim = mmd.encode_anim(frames, NB, 0, events, tol={BODY: 0, None: 1})
        new.anims.table[slot] = len(new.anims.anims)
        new.anims.anims.append(anim)
        for alias, of in ALIASES.items():
            if of == slot:
                assert old.anims.table[alias] == old.anims.table[slot]
                new.anims.table[alias] = new.anims.table[slot]
        n = len(frames) - 1
        report.append(dict(slot=slot, ticks=n, root_per_tick=round((frames[0][0][8] - frames[-1][0][8]) / n, 2)))
    for anim in new.anims.anims:
        anim.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    output = new.build()
    actual = _parse(output)
    return output, report


def build(data):
    output, report = author(data)
    return output, dict(species=SPECIES, clips=report, storage=motionstorage.require(output, NB))


def main():
    out, proof = build(Path(sys.argv[1]).read_bytes())
    Path(sys.argv[2]).write_bytes(out)
    if len(sys.argv) == 5:
        Path(sys.argv[4]).write_bytes(paint_blinks(Path(sys.argv[3]).read_bytes()))
    print(proof)


if __name__ == '__main__':
    main()
