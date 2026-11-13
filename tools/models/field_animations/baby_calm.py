"""Calm field clips for the Koromon-rigged hand-made babies Motimon (474) and Bukamon (475).

Both keep Koromon's seven-bone rig: 1 the body (scaled to squash and stretch), 2 the body object, 3-4 and 5-6 two chains
that the donor uses as ears. Koromon's own clips lunge once every 18 ticks with a 40 % squash and a 59-unit leap, and its
tired clip is as fast as the walk. These clips are slower and much lower, and give each baby little arms that move and
eyes that blink:

  idle   128 ticks: two slow breaths, a slow look to each side, the arms drifting a little behind the breath,
         four blinks (one of them a double blink) at uneven intervals
  walk   2 hops of 22 ticks (a left and a right one, 16 units a tick), a few units high: a waddle (the body rocks from
         side to side), a soft landing, the arms swinging against each other and lagging the body
  tired  2 hops of 30 ticks, 11 units a tick, 2 units high: a long low crouch, leaning forward, the arms hanging, the lids
         half down, a slow heavy blink
  run    3 hops of 15 ticks, 37 units a tick, low and long, the arms streaming back

The body lands and stays where it landed until it takes off (no slide while it is down); the root, which the game
follows, moves steadily. After every pose the body is lowered or raised so the lowest point of the mesh is exactly on the
floor on the ground and `lift` units above it in the air. Slots 2, 3 and 4 are replaced; slot 0 gets a clip of its own
when its program is shared with other poses. The mesh and the other slots do not change, with two exceptions:

  Motimon: its two arm cones (66 primitives each, drawn into the body object) move to the two empty objects of the
    bones 4 and 6, their vertices expressed in that bone's rest frame so the rest pose is vertex for vertex the same.
    Each tick the bone is solved so the arm turns about its own shoulder whatever the (unused) ear chain above it does.
  Bukamon: the flippers already sit on the objects of bones 3 and 5, rooted at the shoulder: those bones turn.

The blink is a texture copy (tex events). The eye windows are the donor's 40x32 pixel eye frames at (2, 0); a lid
frame (half closed) comes before and after the closed frame. Motimon has no half-closed frame in its texture, so the
unused block at (44, 32) gets one (`paint_lid`): the open eye squashed to the lower half; its last four rows belong to
the arm patch, so the frame is copied in two rects (28 rows from the block, 4 rows of skin from the open eye).

    python -m tools.models.field_animations.baby_calm ID SRC.MMD SRC.TIM OUT.MMD OUT.TIM
where SRC is the baby as built by `tools.models.babies` before this change.
"""
import copy
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import mmd  # noqa: E402
import numpy as np  # noqa: E402
import motioncyclelayer  # noqa: E402
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402

DONOR = 2
NB = 7
BODY, EAR_L, TIP_L, EAR_R, TIP_R = 1, 3, 4, 5, 6
DEG = 4096 / 360
SLOTS = (0, 2, 3, 4)
MOUTH_RECT = ((10, 24), (0, 32))
EYE_DST = (2, 0)
MOUTHS = {'shut': (34, 32), 'open': (14, 32)}   # source x, y in words of the 10x24 mouth rectangle
IDLE_TICKS = 128
IDLE_LOOK = [(0, 0), (22, 0), (36, 12), (58, 12), (72, 0), (84, 0), (98, -10), (118, -10), (128, 0)]
IDLE_BREATHS = 2

# eye states: a list of rects (src x, src y in words / rows, w, h, dst x, dst y) copied in order
FULL = (10, 32)


def _eye(sx, sy):
    return [((sx, sy), FULL, EYE_DST)]


# (tick in the hop, value); the body lands at tick 0 and leaves the ground at `contact`.
#   squash  1 = the deepest crouch, negative = stretched    pitch  degrees, positive leans forward
# arm: f0 resting lift, fa lift in the air, fs lift on a squash, sw alternate swing, s0/sa sweep forward at rest / on the rise
GAITS = {
    2: dict(name='walk', period=22, hops=2, contact=11, speed=16, base_pitch=1.5, sq=.55,
            squash={0: .45, 1: .8, 3: .55, 5: .2, 7: .3, 8: .7, 9: .35, 10: -.2, 11: -.4, 14: -.2, 18: -.3, 20: -.1},
            pitch={0: -2, 2: -3, 6: -1, 9: -3, 10: 0, 12: 4, 17: 2, 21: -1}, mouth=[(0, 'shut'), (12, 'open'), (19, 'shut')],
            eyes='open'),
    3: dict(name='tired', period=30, hops=2, contact=17, speed=11, base_pitch=6, sq=.7,
            squash={0: .55, 2: .9, 5: .6, 9: .45, 13: .8, 15: .85, 16: .3, 17: .05, 21: .15, 26: .25, 28: .4},
            pitch={0: 0, 3: -2, 8: 0, 13: -2, 16: 2, 20: 3, 26: 1, 29: 0}, mouth=[(0, 'shut')], eyes='tired'),
    4: dict(name='run', period=15, hops=3, contact=6, speed=37, base_pitch=6, sq=.6,
            squash={0: .5, 1: .85, 3: .5, 4: .6, 5: .2, 6: -.2, 7: -.4, 9: -.25, 12: -.3, 14: -.05},
            pitch={0: -2, 2: -2, 5: -2, 6: 1, 8: 5, 12: 3, 14: 0}, mouth=[(0, 'shut'), (7, 'open'), (12, 'shut')],
            eyes='open'),
}

# per species: the tables above are shared, the numbers below are its own (Bukamon's join in its own commit)
CONFIGS = {
    474: dict(
        name='Motimon', arms='moved',
        height={2: 6, 3: 2.5, 4: 9}, roll={2: 4.5, 3: 3.5, 4: 2.5}, yaw={2: 3, 3: 2.5, 4: 2},
        # blink start ticks per clip, hold ticks (a double blink is two starts a few ticks apart)
        blinks={0: [(12, 3), (44, 3), (52, 2), (96, 3)], 2: [(31, 3)], 3: [(10, 6)], 4: [(23, 2)]},
        eye_states={'open': _eye(54, 32), 'shut': _eye(34, 0), 'tired': [((44, 32), (10, 28), EYE_DST), ((54, 32), (10, 4), (2, 28))],
                    'lid': [((44, 32), (10, 28), EYE_DST), ((54, 32), (10, 4), (2, 28))]},
        arm={2: dict(f0=-4, fa=10, fs=-9, sw=15, s0=2, sa=22),
             3: dict(f0=-22, fa=4, fs=-5, sw=5, s0=2, sa=8),
             4: dict(f0=-6, fa=14, fs=-8, sw=8, s0=-20, sa=14),
             0: dict(f0=0, fa=0, fs=-10, sw=10, s0=0, sa=0)},
        # the two arm cones: shoulder (body frame, y down, z back) and rest direction of each (x > 0 / x < 0)
        gain={0: (.46, .62), 2: (.48, .55), 3: (.66, .78), 4: (1.7, .55)},
        shoulder={1: (44., -11., -16.), -1: (-44., -11., -18.)},
        direction={1: (.93, .12, -.35), -1: (-.62, -.76, -.20)},
        # the arms the mesh was drawn with (one raised, one stretched out) are brought to hang relaxed at the sides:
        # the elevation of each arm's tip in degrees (negative = down) at rest in every clip
        hang={1: -38., -1: -46.},
    ),
}


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


def spring(drive, n, k=.22, zeta=.45, loops=5):
    """A damped spring following drive(t) (n ticks a loop, periodic): the steady-state loop, n + 1 values. The arm lags
    its target and overshoots it a little."""
    x = v = 0.
    w2, c = k, 2 * zeta * math.sqrt(k)
    out = []
    for i in range(loops * n + 1):
        t = i % n
        a = w2 * (drive(t) - x) - c * v
        v += a
        x += v
        if i >= (loops - 1) * n:
            out.append(x)
    return out


# ------------------------------------------------------------------ the texture
def paint_lid(tim):
    """Motimon: draw the half-closed eye into the unused block at (44, 32) (40x32 pixels): the open eye at (54, 32) squashed
    to half its height, its bottom on row 26, skin above; rows 28-31 are left alone (the arm patch samples them)."""
    w = tim.w
    idx = np.array(tim.idx, dtype=np.uint8).reshape(-1, w)
    eye = idx[32:64, 216:256]
    skin = int(eye[0, 0])
    out = np.full((32, 40), skin, dtype=np.uint8)
    rows = [r for r in range(32) if (eye[r] != skin).any()]
    top, bottom = rows[0], rows[-1]
    height = bottom - top + 1
    new_h = max(8, round(height * .5))
    for r in range(new_h):
        out[27 - new_h + 1 + r] = eye[top + min(height - 1, int(r * height / new_h))]
    # a darker lid line along the top of the squashed eye
    first = 27 - new_h + 1
    dark = int(eye[rows[len(rows) // 2]][np.argmax(eye[rows[len(rows) // 2]] != skin)])
    cols = np.nonzero(out[first] != skin)[0]
    out[first - 1, cols] = dark
    block = idx[32:64, 176:216]
    block[:28] = out[:28]
    tim.idx = idx.reshape(-1).copy() if not isinstance(tim.idx, np.ndarray) else idx.reshape(tim.idx.shape)
    return tim


# ------------------------------------------------------------------ the arms of Motimon
def _arm_axes(direction):
    d = np.asarray(direction, float)
    d /= np.linalg.norm(d)
    up = np.cross(d, (0., -1., 0.))             # a positive turn about it lifts the tip
    fwd = np.cross(d, (0., 0., -1.))            # ... swings the tip forward (z is back)
    return up / np.linalg.norm(up), fwd / np.linalg.norm(fwd)


def _rodrigues(axis, deg):
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    t = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * K @ K


def _motion(shoulder, up, fwd, flap, sweep):
    """The arm's motion in the body frame (4x4): lifted `flap` degrees and swung forward `sweep` about its shoulder."""
    R = _rodrigues(fwd, sweep) @ _rodrigues(up, flap)
    P = np.asarray(shoulder, float)
    F = np.eye(4)
    F[:3, :3] = R
    F[:3, 3] = P - R @ P
    return F


def is_arm(prim):
    d = prim.decode()
    return bool(d['uv']) and all(u >= 140 and 60 <= v <= 95 for u, v in d['uv'])


def _remap(prim, remap):
    d = prim.decode()
    assert d['norms'] == d['verts'], 'an arm primitive with its own normal indices'
    d['verts'] = [remap[i] for i in d['verts']]
    d['norms'] = [remap[i] for i in d['norms']] if d['norms'] else d['norms']
    return mmd.Prim.encode(d)


def move_arms(tmd, offsets):
    """Move the arm primitives from object 0 to objects 2 (x > 0) and 4 (x < 0), their vertices relative to the tip bone's
    rest origin (offsets: object -> rest origin in the body frame); in place; a model already done is left alone."""
    if len(tmd.objects[2].prims) > 1:
        return False
    old = [(list(tmd.obj_verts(i)), list(tmd.obj_norms(i)[:tmd.objects[i].nnorm])) for i in range(len(tmd.objects))]
    keep, arms = [], {2: [], 4: []}
    for prim in tmd.objects[0].prims:
        if not is_arm(prim):
            keep.append(prim)
            continue
        ids = prim.decode()['verts']
        xs = [old[0][0][i][0] for i in ids]
        assert all(x > 0 for x in xs) or all(x < 0 for x in xs)
        arms[2 if xs[0] > 0 else 4].append(prim)
    assert len(arms[2]) == len(arms[4]) == 66, (len(arms[2]), len(arms[4]))
    used = {i for pr in keep for i in pr.decode()['verts']}
    assert not any(i in used for pr in sum(arms.values(), []) for i in pr.decode()['verts']), 'an arm vertex is shared'
    pools = {}
    for oi in range(len(tmd.objects)):
        verts, norms = old[oi]
        if oi == 0:
            order = sorted(used)
            remap = {o: n for n, o in enumerate(order)}
            pools[oi] = ([verts[i] for i in order], [norms[i] for i in order], [_remap(pr, remap) for pr in keep])
        elif oi in arms:
            order = sorted({i for pr in arms[oi] for i in pr.decode()['verts']})
            remap = {o: n for n, o in enumerate(order)}
            off = offsets[oi]
            vs = [(old[0][0][i][0] - off[0], old[0][0][i][1] - off[1], old[0][0][i][2] - off[2]) + tuple(old[0][0][i][3:]) for i in order]
            pools[oi] = (vs, [old[0][1][i] for i in order], [_remap(pr, remap) for pr in arms[oi]])
        else:
            pools[oi] = (verts, norms, tmd.objects[oi].prims)
    start = 0
    out_v, out_n = [], []
    for oi, ob in enumerate(tmd.objects):
        v, n, prims = pools[oi]
        ob.prims = list(prims)
        ob.vert_start = ob.norm_start = start
        ob.nvert = len(v)
        ob.nnorm = len(n)
        start += len(v)
        out_v += v
        out_n += n
    tmd.verts, tmd.norms = out_v, out_n
    return True


# ------------------------------------------------------------------ the rig
class Rig:
    def __init__(self, species, model):
        self.species, self.cfg, self.model = species, CONFIGS[species], model
        frames = _slot0(model, species)
        self.rest = [list(v) for v in frames[0]]
        self.rest[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
        self.skel = mmd.exe().skeleton[species]
        self.verts = {oi: [v[:3] for v in model.tmd.obj_verts(oi)] for oi, _ in self.skel if oi >= 0}
        self.offsets = {TIP_L: [self.rest[EAR_L][6 + i] + self.rest[TIP_L][6 + i] for i in range(3)],
                        TIP_R: [self.rest[EAR_R][6 + i] + self.rest[TIP_R][6 + i] for i in range(3)]}
        self._prev = {}
        if self.cfg['arms'] == 'moved':
            self.shoulder = {EAR_L: self.cfg['shoulder'][1], EAR_R: self.cfg['shoulder'][-1]}
            self.axes = {EAR_L: _arm_axes(self.cfg['direction'][1]), EAR_R: _arm_axes(self.cfg['direction'][-1])}
            self.hang = {bone: self.cfg['hang'][side] - math.degrees(math.asin(-self.cfg['direction'][side][1] / np.linalg.norm(self.cfg['direction'][side])))
                         for bone, side in ((EAR_L, 1), (EAR_R, -1))}
        else:
            # a flipper's own direction: from its shoulder (the bone origin) to the far end of its vertices
            self.axes = {}
            for bone in (EAR_L, EAR_R):
                vs = np.array(self.verts[self.skel[bone][0]], float)
                far = vs[np.argsort(np.linalg.norm(vs, axis=1))[-max(3, len(vs) // 10):]].mean(0)
                self.axes[bone] = _arm_axes(far)
        self.floor = self._low(self.rest)

    def _low(self, pose):
        mats = mmd.bone_matrices(self.model, pose)
        low = -1e9
        for b, (oi, _) in enumerate(self.skel):
            if oi >= 0 and self.verts[oi]:
                M = mats[b]
                low = max(low, max(M[1][0] * x + M[1][1] * y + M[1][2] * z + M[1][3] for x, y, z in self.verts[oi]))
        return low

    def pose(self, squash=0., pitch=0., roll=0., yaw=0., lift=0., arms=((0., 0.), (0., 0.)), first=False):
        """arms: ((flap, sweep) of the x > 0 arm, (flap, sweep) of the x < 0 arm), degrees."""
        p = copy.deepcopy(self.rest)
        b = p[BODY]
        b[1] = round(4096 * (1 - .16 * squash))
        b[0] = b[2] = round(4096 * (1 + .08 * squash))
        b[3], b[4], b[5] = round(pitch * DEG), round(yaw * DEG), round(roll * DEG)
        for bone, tip, (flap, sweep) in ((EAR_L, TIP_L, arms[0]), (EAR_R, TIP_R, arms[1])):
            up, fwd = self.axes[bone]
            if self.cfg['arms'] == 'moved':
                self._place_arm(p, bone, tip, up, fwd, flap + self.hang[bone], sweep)
            else:
                R = _rodrigues(fwd, sweep) @ _rodrigues(up, flap)
                ang = mmd.matrix_euler(R.tolist(), self._prev.get(bone))
                self._prev[bone] = ang
                p[bone][3:6] = [round(a) for a in ang]
        # the body hangs from its centre: put the lowest point of the mesh on the floor, then lift it
        p[BODY][7] = 0
        # (the studio takes the floor from the first pose of the idle: that one is rounded to the lower whole unit and
        # every other pose to the higher one, so no pose of any clip is ever below it)
        p[BODY][7] = (math.ceil if first else math.floor)(self.floor - lift - self._low(p))
        return p

    def _place_arm(self, p, base, tip, up, fwd, flap, sweep):
        """Solve the tip bone so the arm moves as _motion says, whatever the bone above it does."""
        v = p[base]
        L3 = np.eye(4)
        L3[:3, :3] = np.array(mmd.rot_matrix(*v[3:6]))
        L3[:3, 3] = v[6:9]
        O = np.eye(4)
        O[:3, 3] = self.offsets[tip]
        M = np.linalg.inv(L3) @ _motion(self.shoulder[base], up, fwd, flap, sweep) @ O
        ang = mmd.matrix_euler(M[:3, :3].tolist(), self._prev.get(tip))
        self._prev[tip] = ang
        p[tip][3:6] = [round(a) for a in ang]
        p[tip][6:9] = [round(x) for x in M[:3, 3]]


def _slot0(model, species):
    import animsheet
    return animsheet.slot_frames(model, NB, 0)[0]


# ------------------------------------------------------------------ events
def eye_events(cfg, t, state):
    return [(t, 'tex', dict(op='tex', frame=t + 1, src=s, size=z, dst=d)) for s, z, d in cfg['eye_states'][state]]


def mouth_event(t, name):
    (w, h), dst = MOUTH_RECT
    return (t, 'tex', dict(op='tex', frame=t + 1, src=MOUTHS[name], size=(w, h), dst=dst))


def blink(cfg, t, base, hold):
    """Lid coming down (the half-closed frame), shut for `hold` ticks, the lid again, then the base eye."""
    return (eye_events(cfg, t, 'lid') + eye_events(cfg, t + 1, 'shut') + eye_events(cfg, t + 1 + hold, 'lid')
            + eye_events(cfg, t + 2 + hold, base))


# ------------------------------------------------------------------ the clips
def gait(rig, slot, sound):
    cfg, g = rig.cfg, GAITS[slot]
    P, hops, c = g['period'], g['hops'], g['contact']
    n = P * hops
    H, speed = cfg['height'][slot], g['speed']
    squash = periodic({k: v * g['sq'] for k, v in g['squash'].items()}, P)
    pitch = periodic(g['pitch'], P)
    hop = speed * P
    f = P - c
    arm = cfg['arm'][slot]
    cycles = hops / 2 if hops % 2 == 0 else hops

    def height(t):
        tau = t % P
        if tau <= c:
            return 0.
        s = (tau - c) / f
        return 4 * H * s * (1 - s)

    def body_z(t):
        k, tau = divmod(t, P)
        if tau <= c:
            return k * hop
        s = (tau - c) / f
        return k * hop + hop * (.1 * s + .9 * (3 * s * s - 2 * s ** 3))

    mean = sum(body_z(t) - speed * t for t in range(P)) / P
    vmax = max(1., 4 * H / f)

    def rise(x):
        return (height(x) - height(x - 1)) / vmax          # -1..1, up positive

    gain = cfg['gain'][slot]

    def flap_drive(i, sign):
        return lambda x: (arm['f0'] + gain[i] * (arm['fa'] * height(x) / H + arm['fs'] * (squash(x % P) - .2 * g['sq'])
                                                 + sign * arm['sw'] * wave(cycles, n, x, .1)))
    flaps = [spring(flap_drive(i, s), n) for i, s in enumerate((1, -1))]
    sweeps = [spring(lambda x, s=s, i=i: arm['s0'] + gain[i] * (arm['sa'] * rise(x) + s * .5 * arm['sw'] * wave(cycles, n, x, .35)), n, k=.3)
              for i, s in enumerate((1, -1))]
    frames = []
    for t in range(n + 1):
        tt = t % n
        tau = tt % P
        pose = rig.pose(squash=squash(tau), pitch=g['base_pitch'] + pitch(tau), lift=height(tt),
                        roll=cfg['roll'][slot] * wave(cycles, n, tt, 0), yaw=cfg['yaw'][slot] * wave(cycles, n, tt, .2),
                        arms=((flaps[0][t], sweeps[0][t]), (flaps[1][t], sweeps[1][t])))
        world = -body_z(t)
        root_line = -(.5 * (body_z(t) + mean) + .5 * speed * t)
        pose[0][8] = round(root_line)
        pose[BODY][8] = round(world - root_line)
        frames.append([[int(round(x)) for x in v] for v in pose])
    events = [(k * P, 'sound', dict(sound)) for k in range(hops)]
    events += eye_events(cfg, 0, g['eyes'])
    for k in range(hops):
        events += [mouth_event(k * P + t, s) for t, s in g['mouth']]
    for t, hold in cfg['blinks'][slot]:
        events += blink(cfg, t, g['eyes'], hold)
    events.sort(key=lambda e: e[0])
    return frames, events


def idle(rig):
    cfg = rig.cfg
    n = IDLE_TICKS
    look = eased(IDLE_LOOK)
    a = cfg['arm'][0]
    gain = cfg['gain'][0]
    flaps = [spring(lambda x, s=s, i=i: a['f0'] + gain[i] * (8 * wave(IDLE_BREATHS, n, x, .05 + (.5 if s < 0 else 0)) + a['sw'] * .5 * wave(1, n, x, .3 * s)
                    + a['fs'] * (.5 - .5 * math.cos(2 * math.pi * IDLE_BREATHS * x / n))), n, k=.12, zeta=.5) for i, s in enumerate((1, -1))]
    sweeps = [spring(lambda x, s=s, i=i: gain[i] * (6 * wave(IDLE_BREATHS, n, x, .3 + (.25 if s < 0 else 0)) + 3 * wave(3, n, x, .6)), n, k=.14, zeta=.5)
              for i, s in enumerate((1, -1))]
    frames = []
    for t in range(n + 1):
        tt = t % n
        breath = .5 - .5 * math.cos(2 * math.pi * IDLE_BREATHS * tt / n)
        pose = rig.pose(squash=.28 * breath - .08, pitch=1.2 * wave(1, n, tt, .1) + 1, roll=1.2 * wave(1, n, tt, .6),
                        yaw=look(tt), arms=((flaps[0][t], sweeps[0][t]), (flaps[1][t], sweeps[1][t])), first=tt == 0)
        frames.append([[int(round(x)) for x in v] for v in pose])
    events = eye_events(cfg, 0, 'open') + [mouth_event(0, 'shut')]
    for t, hold in cfg['blinks'][0]:
        events += blink(cfg, t, 'open', hold)
    events.sort(key=lambda e: e[0])
    return frames, events


# ------------------------------------------------------------------ build
def _parse(species, data):
    mmd.exe().skeleton[species] = mmd.exe().skeleton[DONOR]
    mmd.exe().bone_count[species] = NB
    model = mmd.MMD.parse(data, NB)
    model.type = species
    return model


def author(species, data, tim_bytes):
    import animsheet
    cfg = CONFIGS[species]
    old = _parse(species, data)
    rig = Rig(species, old)
    new = copy.deepcopy(old)
    tim = mmd.Tim4(tim_bytes)
    if cfg['arms'] == 'moved':
        if move_arms(new.tmd, {2: rig.offsets[TIP_L], 4: rig.offsets[TIP_R]}):
            tim = paint_lid(tim)
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
        index = old.anims.table[slot]
        if slot == 0 or sum(1 for i in old.anims.table if i == index) > 1:
            new.anims.table[slot] = len(new.anims.anims)
            new.anims.anims.append(anim)
        else:
            new.anims.anims[index] = anim
        n = len(frames) - 1
        report.append(dict(slot=slot, ticks=n, root_per_tick=round((frames[0][0][8] - frames[-1][0][8]) / n, 2)))
    for anim in new.anims.anims:
        anim.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    output = new.build()
    actual = _parse(species, output)
    assert actual.tmd.build() == new.tmd.build()
    assert changed_programs(old, actual) == list(SLOTS), changed_programs(old, actual)
    return output, tim.to_bytes(), report


def build(species, data, tim_bytes):
    output, tim, report = author(species, data, tim_bytes)
    return output, tim, dict(species=species, clips=report, storage=motionstorage.require(output, NB))


def main():
    species = int(sys.argv[1])
    out, tim, proof = build(species, Path(sys.argv[2]).read_bytes(), Path(sys.argv[3]).read_bytes())
    Path(sys.argv[4]).write_bytes(out)
    Path(sys.argv[5]).write_bytes(tim)
    print(proof)


if __name__ == '__main__':
    main()
