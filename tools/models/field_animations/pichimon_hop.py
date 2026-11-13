"""Pichimon's (species 471) field clips: a calm idle and three soft hops.

Pichimon keeps Koromon's seven-bone rig: 1 the body (scaled to squash and stretch, it holds the whole mesh), 2 the
body object, 3-4 and 5-6 the two feelers (a base and a tip each). The donor's walk lunges once every 18 ticks with a
40 % squash and a 59-unit leap, and the tired clip is the same lunge at the same speed. These clips are slower and
smaller:

  idle   96 ticks: two slow breaths (a few percent of squash), a slow look to one side and then the other, the feelers
         drifting loosely a little behind it, three blinks (about 1 s apart)
  walk   2 hops of 22 ticks (a left and a right one, 16 units a tick), 14 units high: a soft landing that squashes
         about 16 %, a slow rebound, a small crouch and a gentle stretch in the air; the feelers lag the body
  tired  2 hops of 30 ticks, 11 units a tick, 5 units high: a long low crouch, leaning forward, the feelers drooping
  run    3 hops of 16 ticks, 38 units a tick, 24 units high: long low bounds leaning forward, the feelers streaming back

The body lands and stays where it landed until it takes off (no slide while it is down); the root, which the game
follows, moves steadily. The body is lowered or raised after every pose so the lowest point of the mesh is exactly on
the floor on the ground and `lift` units above it in the air. Slots 2, 3 and 4 are replaced; slot 0 gets a clip of its
own when its program is shared with other poses. The mesh, the texture and the other slots do not change.

    python -m tools.models.field_animations.pichimon_hop SRC.MMD OUT.MMD
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

SPECIES = 471
DONOR = 2
NB = 7
BODY, EAR_L, TIP_L, EAR_R, TIP_R = 1, 3, 4, 5, 6
DEG = 4096 / 360
SLOTS = (0, 2, 3, 4)
EYES = {'open': (54, 32), 'half': (24, 0), 'lid': (44, 0), 'shut': (54, 0)}   # (source x in words, y) of the 10x32 eye rectangle at (2, 0)
MOUTHS = {'shut': (34, 32), 'open': (14, 32)}   # the 10x24 mouth rectangle at (0, 32)

# (tick in the hop, value); the body lands at tick 0 and leaves the ground at `contact`.
#   squash  1 = the deepest crouch, negative = stretched    pitch  degrees, positive leans forward
GAITS = {
    2: dict(name='walk', period=22, hops=2, contact=10, speed=16, height=14, base_pitch=2.5,
            squash={0: .45, 1: .8, 3: .55, 5: .2, 7: .3, 8: .7, 9: .35, 10: -.2, 11: -.4, 14: -.2, 18: -.3, 20: -.1},
            pitch={0: -2, 2: -3, 6: -1, 9: -3, 10: 0, 12: 4, 17: 2, 21: -1}, roll=2.2, yaw=3.5, ear=26,
            eyes=[(0, 'open')], mouth=[(0, 'shut'), (11, 'open'), (19, 'shut')], blinks=[(27, 4)],
            fin=dict(f0=-8, fa=42, fs=14, s0=0, sa=-24)),
    3: dict(name='tired', period=30, hops=2, contact=16, speed=11, height=5, base_pitch=7,
            squash={0: .55, 2: .9, 5: .6, 9: .45, 13: .8, 15: .85, 16: .3, 17: .05, 21: .15, 26: .25, 28: .4},
            pitch={0: 0, 3: -2, 8: 0, 13: -2, 16: 2, 20: 3, 26: 1, 29: 0}, roll=2.5, yaw=3, ear=-12,
            eyes=[(0, 'half')], mouth=[(0, 'shut'), (17, 'open'), (24, 'shut')], blinks=[(6, 4), (40, 4)],
            fin=dict(f0=-28, fa=16, fs=8, s0=8, sa=-8)),
    4: dict(name='run', period=16, hops=3, contact=6, speed=38, height=24, base_pitch=8,
            squash={0: .5, 1: .85, 3: .5, 4: .6, 5: .2, 6: -.2, 7: -.4, 10: -.25, 13: -.3, 15: -.05},
            pitch={0: -2, 2: -2, 5: -2, 6: 1, 8: 5, 12: 3, 15: 0}, roll=1.5, yaw=2, ear=36,
            eyes=[(0, 'open')], mouth=[(0, 'shut'), (7, 'open'), (13, 'shut')], blinks=[],
            fin=dict(f0=14, fa=26, fs=10, s0=-38, sa=-20)),
}
IDLE_TICKS = 96
IDLE_LOOK = [(0, 0), (16, 0), (26, 13), (44, 13), (54, 0), (64, 0), (74, -11), (90, -11), (96, 0)]


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


# ------------------------------------------------------------------ the little arms (the pectoral fins)
# The twelve fin quads (six a side, UVs in the fin paddle at texture x 176+, y 32-63) are authored inside the body
# object. They move to the objects of the two feeler-tip bones (2 and 4: a degenerate triangle each, bones 4 and 6),
# expressed in the tip bone's own rest frame (the body frame minus the two translations down the feeler chain), so the
# rest pose is vertex for vertex the same. Per frame the tip bone's translation and rotation are solved so that the fin
# turns about its own shoulder whatever the feeler is doing: L4 = inverse(L3) . F . T(O), F the fin's motion in the body
# frame. (The body bone's squash is above both chains and cancels out.)
FIN_SHOULDER = np.array([37., 30., 2.])          # the fin root of the authoring script (right-hand side, x > 0)
FIN_ROOT = np.array([-6., 26., 12.])             # the root edge direction, down and back
FIN_DIR0 = np.array([.5, .62, .58])
FIN_LEN = 34.
FIN_OBJECTS = {TIP_L: 2, TIP_R: 4}               # the object of each tip bone; x > 0 is the left feeler's side (bone 3)


def is_fin(prim):
    d = prim.decode()
    return bool(d['uv']) and all(u >= 176 and 32 <= v < 64 for u, v in d['uv'])


def move_fins(tmd):
    """Move the fin quads from object 0 to objects 2 (x > 0) and 4 (x < 0), in place; a model already done is left alone."""
    if len(tmd.objects[2].prims) > 1:
        return False
    old = [(list(tmd.obj_verts(i)), list(tmd.obj_norms(i)[:tmd.objects[i].nnorm])) for i in range(len(tmd.objects))]
    keep, fins = [], {2: [], 4: []}
    for prim in tmd.objects[0].prims:
        if not is_fin(prim):
            keep.append(prim)
            continue
        ids = prim.decode()['verts']
        xs = [old[0][0][i][0] for i in ids]
        assert all(x > 0 for x in xs) or all(x < 0 for x in xs)
        fins[2 if xs[0] > 0 else 4].append(prim)
    used = {i for pr in keep for i in pr.decode()['verts']}
    assert not any(i in used for pr in sum(fins.values(), []) for i in pr.decode()['verts']), 'a fin vertex is shared'
    assert len(fins[2]) == 6 and len(fins[4]) == 6
    pools = {}
    new_verts, new_norms, new_prims = [], [], []
    for oi in range(len(tmd.objects)):
        verts, norms = old[oi]
        if oi == 0:
            order = sorted({i for pr in keep for i in pr.decode()['verts']})
            assert len(order) == len(verts) - sum(len({i for pr in fins[k] for i in pr.decode()['verts']}) for k in fins), 'object 0 holds vertices that no primitive uses'
            remap = {o: n for n, o in enumerate(order)}
            pools[oi] = ([verts[i] for i in order], [norms[i] for i in order], [_remap(pr, remap) for pr in keep])
        elif oi in fins:
            order = sorted({i for pr in fins[oi] for i in pr.decode()['verts']})
            remap = {o: n for n, o in enumerate(order)}
            pools[oi] = ([old[0][0][i] for i in order], [old[0][1][i] for i in order], [_remap(pr, remap) for pr in fins[oi]])
        else:
            pools[oi] = (verts, norms, tmd.objects[oi].prims)
    # the fin vertices still hold the body-frame coordinates: the caller turns them into the tip frame
    start = 0
    out_v, out_n = [], []
    for oi, ob in enumerate(tmd.objects):
        v, n, prims = pools[oi][:3]
        ob.prims = list(prims)
        ob.vert_start = ob.norm_start = start
        ob.nvert = len(v)
        ob.nnorm = len(n)
        start += len(v)
        out_v += v
        out_n += n
    tmd.verts, tmd.norms = out_v, out_n
    return True


def _remap(prim, remap):
    d = prim.decode()
    assert d['norms'] == d['verts'], 'a fin primitive with its own normal indices'
    d['verts'] = [remap[i] for i in d['verts']]
    d['norms'] = [remap[i] for i in d['norms']] if d['norms'] else d['norms']
    return mmd.Prim.encode(d)


def fin_to_tip_frame(tmd, offsets):
    """Subtract each tip bone's rest offset from its fin vertices (body frame -> the tip bone's rest frame)."""
    for oi, off in offsets.items():
        ob = tmd.objects[oi]
        for k in range(ob.vert_start, ob.vert_start + ob.nvert):
            x, y, z, pad = tmd.verts[k]
            tmd.verts[k] = (x - off[0], y - off[1], z - off[2], pad)


def _rodrigues(axis, deg):
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    t = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * K @ K


def _fin_axes():
    w = FIN_ROOT / np.linalg.norm(FIN_ROOT)
    d = FIN_DIR0 - (FIN_DIR0 @ w) * w
    d /= np.linalg.norm(d)
    n = np.cross(d, w)
    if n[0] < 0:
        n = -n
    tip = d * FIN_LEN
    up = w if np.cross(w, tip)[1] < 0 else -w                  # the axis that lifts the tip (y is down)
    fwd = n if np.cross(n, tip)[2] < 0 else -n                 # the axis that swings the tip forward (z is back)
    return up, fwd


FIN_UP, FIN_FWD = _fin_axes()
MIRROR = np.diag([-1., 1., 1.])


def fin_motion(flap, sweep, side):
    """The fin's motion in the body frame (4x4): lifted `flap` degrees and swung forward `sweep` about its shoulder;
    side +1 the x > 0 fin, -1 its mirror image."""
    R = _rodrigues(FIN_FWD, sweep) @ _rodrigues(FIN_UP, flap)
    P = FIN_SHOULDER
    if side < 0:
        R, P = MIRROR @ R @ MIRROR, MIRROR @ P
    F = np.eye(4)
    F[:3, :3] = R
    F[:3, 3] = P - R @ P
    return F


def spring(drive, n, k=.22, zeta=.45, loops=5):
    """A damped spring following drive(t) (n ticks a loop, periodic): the steady-state loop, n + 1 values. The fin
    lags its target and overshoots it a little."""
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


# ------------------------------------------------------------------ the rig
class Rig:
    def __init__(self, model):
        self.model = model
        frames = _slot0(model)
        self.rest = [list(v) for v in frames[0]]
        self.rest[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
        self.skel = mmd.exe().skeleton[SPECIES]
        self.verts = {oi: [v[:3] for v in model.tmd.obj_verts(oi)] for oi, _ in self.skel if oi >= 0}
        self.offsets = {TIP_L: [self.rest[EAR_L][6 + i] + self.rest[TIP_L][6 + i] for i in range(3)],
                        TIP_R: [self.rest[EAR_R][6 + i] + self.rest[TIP_R][6 + i] for i in range(3)]}
        self._prev = {}
        self.floor = self._low(self.rest) + 1       # the rest mesh's lowest point as the studio measures it (rest pose, y down)

    def _low(self, pose):
        mats = mmd.bone_matrices(self.model, pose)
        low = -1e9
        for b, (oi, _) in enumerate(self.skel):
            if oi >= 0:
                M = mats[b]
                low = max(low, max(M[1][0] * x + M[1][1] * y + M[1][2] * z + M[1][3] for x, y, z in self.verts[oi]))
        return low

    def pose(self, squash=0., pitch=0., roll=0., yaw=0., lift=0., ear=(0., 0.), fin=(0., 0.), spread=0.):
        """ear: (left, right) bend of each feeler (degrees, positive swings forward); fin: (flap, sweep) of the little arms."""
        p = copy.deepcopy(self.rest)
        b = p[BODY]
        b[1] = round(4096 * (1 - .16 * squash))
        b[0] = b[2] = round(4096 * (1 + .08 * squash))
        b[3], b[4], b[5] = round(pitch * DEG), round(yaw * DEG), round(roll * DEG)
        for base, tip, k in ((EAR_L, TIP_L, 0), (EAR_R, TIP_R, 1)):
            p[base][3] += round(ear[k] * DEG)
            p[base][5] += round((spread if k == 0 else -spread) * DEG)
            self._place_fin(p, base, tip, 1 if k == 0 else -1, *fin)
        # the body hangs from its centre: put the lowest point of the mesh on the floor, then lift it
        p[BODY][7] = 0
        p[BODY][7] = math.floor(self.floor - lift - self._low(p))
        return p


    def _place_fin(self, p, base, tip, side, flap, sweep):
        """Solve the tip bone so the fin moves as fin_motion says, whatever the feeler above it does."""
        v = p[base]
        L3 = np.eye(4)
        L3[:3, :3] = np.array(mmd.rot_matrix(*v[3:6]))
        L3[:3, 3] = v[6:9]
        O = np.eye(4)
        O[:3, 3] = self.offsets[tip]
        M = np.linalg.inv(L3) @ fin_motion(flap, sweep, side) @ O
        prev = self._prev.get(tip)
        ang = mmd.matrix_euler(M[:3, :3].tolist(), prev)
        self._prev[tip] = ang
        p[tip][3:6] = [round(a) for a in ang]
        p[tip][6:9] = [round(x) for x in M[:3, 3]]


def _slot0(model):
    import animsheet
    return animsheet.slot_frames(model, NB, 0)[0]


# ------------------------------------------------------------------ events
def tex(frame_tick, kind, name):
    if kind == 'eye':
        src, size, dst = EYES[name], (10, 32), (2, 0)
    else:
        src, size, dst = MOUTHS[name], (10, 24), (0, 32)
    return (frame_tick, 'tex', dict(op='tex', frame=frame_tick + 1, src=src, size=size, dst=dst))


def blink(t, base, hold=2):
    """Eyelids coming down (a lid frame), shut for `hold` ticks, a lid frame again, then back to the base eye."""
    return [tex(t, 'eye', 'lid'), tex(t + 1, 'eye', 'shut'), tex(t + 1 + hold, 'eye', 'lid'),
            tex(t + 2 + hold, 'eye', base)]


# ------------------------------------------------------------------ the clips
def gait(rig, slot, sound):
    g = GAITS[slot]
    P, hops, c = g['period'], g['hops'], g['contact']
    n = P * hops
    squash, pitch = periodic(g['squash'], P), periodic(g['pitch'], P)
    hop = g['speed'] * P
    f = P - c

    def height(t):
        tau = t % P
        if tau <= c:
            return 0.
        s = (tau - c) / f
        return 4 * g['height'] * s * (1 - s)

    def body_z(t):
        k, tau = divmod(t, P)
        if tau <= c:
            return k * hop
        s = (tau - c) / f
        return k * hop + hop * (.1 * s + .9 * (3 * s * s - 2 * s ** 3))

    mean = sum(body_z(t) - g['speed'] * t for t in range(P)) / P
    vmax = max(1., 4 * g['height'] / f)
    fin = g['fin']
    flaps = spring(lambda x: fin['f0'] + fin['fa'] * height(x) / g['height'] + fin['fs'] * (squash(x % P) - .2), n)
    sweeps = spring(lambda x: fin['s0'] + fin['sa'] * (height(x) - height(x - 1)) / vmax, n, k=.3)
    frames = []
    for t in range(n + 1):
        tt = t % n
        tau = tt % P
        rise = lambda x: (height(x) - height(x - 1)) / vmax          # -1..1, up positive
        # the feelers lag the body: they follow the vertical speed a tick or two late and swing on a squash
        e1 = g['ear'] / 26 * (-14 * rise(tt - 2) + 9 * (squash(tau - 1) - .2)) + 5 * wave(hops * 2, n, tt, .15) * abs(g['ear']) / 26
        side = 1 if (tt // P) % 2 == 0 else -1
        roll = g['roll'] * side * math.sin(math.pi * min(1., tau / P)) * (1 if tau else 0)
        pose = rig.pose(squash=squash(tau), pitch=g['base_pitch'] + pitch(tau), lift=height(tt),
                        roll=roll, yaw=g['yaw'] * wave(hops / 2 if hops % 2 == 0 else hops, n, tt, .2),
                        ear=(e1, .9 * e1 + 2 * wave(hops * 2, n, tt, .6)),
                        fin=(flaps[t], sweeps[t]),
                        spread=3 * wave(hops, n, tt, .3))
        world = -body_z(t)
        root_line = -(.5 * (body_z(t) + mean) + .5 * g['speed'] * t)
        pose[0][8] = round(root_line)
        pose[BODY][8] = round(world - root_line)
        frames.append([[int(round(x)) for x in v] for v in pose])
    events = [(k * P, 'sound', dict(sound)) for k in range(hops)]
    for k in range(hops):
        events += [tex(k * P + t, 'eye', s) for t, s in g['eyes']]
        events += [tex(k * P + t, 'mouth', s) for t, s in g['mouth']]
    base = g['eyes'][0][1]
    for t, hold in g['blinks']:
        events += blink(t, base, hold)
    events.sort(key=lambda e: e[0])
    return frames, events


def idle(rig):
    n = IDLE_TICKS
    look = eased(IDLE_LOOK)
    frames = []
    for t in range(n + 1):
        tt = t % n
        breath = .5 - .5 * math.cos(2 * math.pi * 2 * tt / n)
        pose = rig.pose(squash=.28 * breath - .08, pitch=1.2 * wave(1, n, tt, .1) + 1, roll=1.2 * wave(1, n, tt, .6),
                        yaw=look(tt),
                        ear=(5 * wave(2, n, tt, .1) - 4 * (look(tt) / 13), 5 * wave(2, n, tt, .35) + 4 * (look(tt) / 13)),
                        fin=(8 * wave(2, n, tt, .05) + 10 * breath - 5, 8 * wave(2, n, tt, .3) + 3 * wave(3, n, tt, .6)),
                        spread=2 * wave(1, n, tt))
        frames.append([[int(round(x)) for x in v] for v in pose])
    events = [tex(0, 'eye', 'open'), tex(0, 'mouth', 'shut')] + blink(10, 'open', 4) + blink(42, 'open', 4) + blink(74, 'open', 4)
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
    rig = Rig(old)
    new = copy.deepcopy(old)
    if move_fins(new.tmd):
        fin_to_tip_frame(new.tmd, {FIN_OBJECTS[t]: o for t, o in rig.offsets.items()})
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
    actual = _parse(output)
    assert actual.tmd.build() == new.tmd.build()
    assert changed_programs(old, actual) == list(SLOTS), changed_programs(old, actual)
    return output, report


def build(data):
    output, report = author(data)
    return output, dict(species=SPECIES, clips=report, storage=motionstorage.require(output, NB))


def main():
    out, proof = build(Path(sys.argv[1]).read_bytes())
    Path(sys.argv[2]).write_bytes(out)
    print(proof)


if __name__ == '__main__':
    main()
