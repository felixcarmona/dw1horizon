"""GranKuwagamon's field gaits written from the claws up, and a calmer idle.

Offline authoring is not needed: the build makes the clips from the pinned reviewed model (`SOURCE`).

GranKuwagamon (210) is a low, beetle-bodied beast: four two-bone legs (a hip plate carrying a rigid link and the whole
claw foot), two free upper arms with their claws, mandibles, and four wing blades on the back. The imported walk and
run kept the native hunch with the wings thrashing through 50 degrees, the arms and mandibles swinging with them,
and the feet down for only a quarter (fore) or half (hind) of the stride, so the whole animal read as a tangle of
limbs moving without sense. These clips are written so that every part has one job:

- Walk (slot 2): a lateral sequence (left hind, left fore, right hind, right fore, a quarter cycle apart), each foot
  on the floor for 64 % of the cycle, 16 ticks at 15 units per tick. Condition walk (slot 3): the same sequence
  lower and slower, 20 ticks at 10 units. Run (slot 4): a trot (diagonal pairs together, 42 % stance) with the body
  pitched forward, 10 ticks at 36 units.
- A stance foot stands on its rolling sole (heel to toe, solved against the real mesh) and stays put in the world
  while the body passes; the pelvis height is the one value all four standing feet agree on, smoothed around the
  cycle. A swinging foot is lifted and swung wide of the body (a rigid link can only hold a foot up by reaching out).
- The body pitches, rolls and sways a little with the footfalls, the head steadies against it, the upper arms swing
  as pendulums a quarter cycle behind the chest, the mandibles hold their opening and the wings only twitch.
- The idle keeps its sequence and its floor clearance, but the arms, mandibles and wings move about half as far from
  the clip's first pose as they did.

Every other program and the mesh stay exact. The build refuses another source.
"""
import copy
import hashlib
import math
import numeric as np
import mmd
import animsheet
import motionsecondary
import motioncyclelayer
import motionstorage
from tools.models.field_animations.articulation import replace_channels
from tools.models.field_animations import quadruped as Q
from motiondiscidentity import changed_programs
from tools.models.field_animations.war_greymon import rotation, set_rotation, align
SOURCE = '7aff3957ff3d24b65db422b36b8dd8394155722a8256cf7f6b3f97ac990dfc66'

def _pack(model):
    for animation in model.anims.anims:
        animation.tail = b''
    model.anims.anims, model.anims.table = motioncyclelayer.share_identical_streams(model.anims.anims, model.anims.table)
    return model.build()

def _parse(data, sk):
    mmd.exe().skeleton[210] = sk
    mmd.exe().bone_count[210] = len(sk)
    model = mmd.MMD.parse(data, len(sk))
    model.type = 210
    return model



# ------------------------------------------------------------------ the field gaits
# The rig: 1 pelvis, 2 chest, 3 head, 5 and 6 the mandibles, 11-14 the two upper arms with their claws, 15-18 the
# wings, and four two-bone legs. A leg is a hip plate (7 and 9 on the chest, 19 and 21 on the pelvis) whose rigid link
# carries the foot bone (8, 10, 20, 22) with the whole claw foot as its mesh. The hip plate aims the link; the foot
# pitches about the lateral axis (heel to toe) on a rolling sole, so a stance leg stays planted while the body passes.
LEGS = (('RF', 7, 8, True), ('LF', 9, 10, True), ('RH', 19, 20, False), ('LH', 21, 22, False))
ANGLES = [-40 + 0.5 * i for i in range(161)]     # the foot's pitch, degrees
LIMIT = {True: (-30.0, 22.0), False: (-30.0, 30.0)}
SPEED_RANGE = {2: (15, 31), 3: (10, 20), 4: (35, 52)}

GAITS = {
    2: dict(name='walk', ticks=16, speed=15, duty=0.64, lift=dict(F=26, H=22), wide=dict(F=14, H=10),
            td=dict(LH=0.0, LF=0.25, RH=0.5, RF=0.75), steps=('LH', 'RH'),
            pref=dict(F=(-14, 8), H=(-16, 14)), shift=dict(F=-6, H=-4),
            drop=8, bob=3, pitch=1.8, roll=1.6, yaw=2.0, head=0.5, nod=3.0, arm=6.0, wing=3.5, jaw=3.0, lean=0),
    3: dict(name='condition walk', ticks=20, speed=10, duty=0.7, lift=dict(F=20, H=18), wide=dict(F=10, H=8),
            td=dict(LH=0.0, LF=0.25, RH=0.5, RF=0.75), steps=('LH', 'RH'),
            pref=dict(F=(-12, 6), H=(-14, 12)), shift=dict(F=-6, H=-4),
            drop=22, bob=2, pitch=1.4, roll=1.4, yaw=1.5, head=0.4, nod=3.5, arm=4.0, wing=2.5, jaw=2.5, lean=3),
    4: dict(name='run', window=30, ticks=10, speed=36, duty=0.42, lift=dict(F=34, H=30), wide=dict(F=16, H=12),
            td=dict(LF=0.0, RH=0.0, RF=0.5, LH=0.5), steps=('LF', 'RF'),
            pref=dict(F=(-16, 14), H=(-18, 20)), shift=dict(F=-6, H=-4),
            drop=14, bob=7, pitch=2.4, roll=1.8, yaw=2.2, head=0.6, nod=3.5, arm=9.0, wing=5.0, jaw=3.5, lean=8),
}


def _wave(phase, delay=0.0, rate=1):
    return math.cos(2 * math.pi * rate * (phase - delay))


class _Gait:
    """One field clip: the stance solved for the common body height, the swings between the stances."""

    def __init__(self, model, sk, rest, cfg):
        self.m, self.sk, self.cfg = model, sk, cfg
        self.base = [list(map(float, b)) for b in rest]
        self.ticks = cfg['ticks']
        self.speed = cfg['speed']
        self.verts, self.flat = {}, {}
        fr = animsheet.slot_frames(model, 23, 0)[0][0]
        native = [list(b) for b in fr]
        native[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
        W = mmd.bone_matrices(model, native)
        self.hip = {n: h for n, h, f, fr_ in LEGS}
        self.table, self.length, self.rest_k = {}, {}, {}
        for name, hip, foot, front in LEGS:
            self.verts[name] = [list(v[:3]) for v in model.tmd.obj_verts(sk[foot][0])]
            self.flat[name] = [r[:3] for r in W[foot][:3]]
            self.table[name] = [motionsecondary.rolling_foot(self.verts[name], self.flat[name], a) for a in ANGLES]
            self.length[name] = Q.norm(native[foot][6:9])
            self.rest_k[name] = [W[foot][i][3] for i in range(3)]

    # -- the body pose at a tick, legs at rest, root identity
    def body(self, phase, hist):
        cfg, p = self.cfg, [list(b) for b in self.base]
        p[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
        pitch = cfg['pitch'] * _wave(phase, 0.15, 2)
        roll = cfg['roll'] * math.sin(2 * math.pi * (phase - 0.05))
        yaw = cfg['yaw'] * math.sin(2 * math.pi * (phase - 0.3))
        lean = cfg['lean']
        rest = self.base
        Q.set_rot(p, 1, Q.mul(mmd.rot_matrix(*rest[1][3:6]), Q.rot([pitch + lean * 0.4, 0.5 * yaw, roll])), hist)
        Q.set_rot(p, 2, Q.mul(mmd.rot_matrix(*rest[2][3:6]), Q.rot([-pitch * 0.6 + lean * 0.4, -yaw, -roll * 0.6])), hist)
        nod = cfg['nod'] * _wave(phase, 0.1, 2)
        Q.set_rot(p, 3, Q.mul(mmd.rot_matrix(*rest[3][3:6]),
                              Q.rot([-cfg['head'] * (pitch * 0.4 + lean * 0.8) + nod * 0.5, 0.8 * yaw, 0])), hist)
        for b in (5, 6):    # the mandibles open and close a little with the head's nod
            Q.set_rot(p, b, Q.mul(mmd.rot_matrix(*rest[b][3:6]), Q.rot([cfg['jaw'] * _wave(phase, 0.2, 2), 0, 0])), hist)
        for b, sign in ((11, -1), (13, 1)):    # the upper arms swing a little behind the chest, as a pendulum
            swing = cfg['arm'] * _wave(phase, 0.25 + (0.5 if b == 13 else 0), 1)
            Q.set_rot(p, b, Q.mul(mmd.rot_matrix(*rest[b][3:6]), Q.rot([swing, 0, 0])), hist)
        for b, sign in ((15, -1), (16, 1), (17, -1), (18, 1)):   # the wings only twitch, late
            lag = 0.3 if b < 17 else 0.4
            Q.set_rot(p, b, Q.mul(mmd.rot_matrix(*rest[b][3:6]), Q.rot([0, 0, sign * cfg['wing'] * _wave(phase, lag, 1)])), hist)
        return p

    def feasible(self, name, front, K, W0, b0):
        """Body heights (pelvis y) for which the foot, pitched anywhere in its range, can stand at origin plan K."""
        hip = self.hip[name]
        Hx, Hy, Hz = [W0[hip][i][3] for i in range(3)]
        L = self.length[name]
        out = []
        for i, a in enumerate(ANGLES):
            r, dz, sole = self.table[name][i]
            dxz2 = (K[0] - Hx) ** 2 + (K[2] + dz - Hz) ** 2
            if dxz2 >= L * L:
                out.append(None)
                continue
            out.append(b0 + (-sole - math.sqrt(L * L - dxz2)) - Hy)
        return out

    def run(self):
        cfg, ticks, speed = self.cfg, self.ticks, self.speed
        bodies = [self.body(t / ticks, {}) for t in range(ticks)]
        W0 = [mmd.bone_matrices(self.m, p) for p in bodies]
        b0 = [p[1][7] for p in bodies]
        # stance plans (root frame): the foot origin's z travels back at the speed while the leg stands
        stance = {}
        for name, hip, foot, front in LEGS:
            key = 'F' if front else 'H'
            sx = cfg['duty'] * ticks * speed
            for t in range(ticks):
                u = (t / ticks - cfg['td'][name]) % 1.0
                if u < cfg['duty']:
                    q = u / cfg['duty']
                    rest = self.rest_k[name]
                    K = [rest[0], 0.0, rest[2] + cfg['shift'][key] + sx * (q - 0.5)]
                    stance[(name, t)] = (q, K)
        lo_hi = []
        for t in range(ticks):
            lo, hi = -1e9, 1e9
            for name, hip, foot, front in LEGS:
                if (name, t) not in stance:
                    continue
                q, K = stance[(name, t)]
                pref = self.pref(name, front, q)
                vals = self.feasible(name, front, K, W0[t], b0[t])
                ok = [v for a, v in zip(ANGLES, vals) if v is not None and abs(a - pref) <= self.cfg.get('window', 20) and LIMIT[front][0] <= a <= LIMIT[front][1]]
                if not ok:
                    raise ValueError(('stance unreachable', cfg['name'], t, name, round(K[2]), round(q, 2)))
                lo, hi = max(lo, min(ok)), min(hi, max(ok))
            lo_hi.append((lo, hi))
        for t, (lo, hi) in enumerate(lo_hi):
            if lo > hi + 0.01:
                raise ValueError(('no common body height', cfg['name'], t, round(lo, 1), round(hi, 1)))
        wanted = []
        for t in range(ticks):
            ph = t / ticks
            bob = cfg['bob'] * _wave(ph, cfg.get('high', 0.12), 2)
            wanted.append(self.base[1][7] + cfg['drop'] * 0 - bob)
        vals = [min(max(w, lo), hi) for w, (lo, hi) in zip(wanted, lo_hi)]
        for _ in range(200):
            for t in range(ticks):
                lo, hi = lo_hi[t]
                d = (17 * (vals[t - 1] + vals[(t + 1) % ticks]) - 4 * (vals[t - 2] + vals[(t + 2) % ticks]) + 0.05 * wanted[t]) / 26.05
                vals[t] = min(max(d, lo), hi) if hi > lo else (lo + hi) / 2
        self.height = vals
        self.lo_hi = lo_hi
        self.W0, self.bodies, self.b0 = W0, bodies, b0
        return vals

    def pref(self, name, front, q):
        a, b = self.cfg['pref']['F' if front else 'H']
        return a + (b - a) * q


    def roll(self, name, angle):
        """The rolling sole at any angle: (world rotation, z shift, height of the origin over the floor)."""
        return motionsecondary.rolling_foot(self.verts[name], self.flat[name], angle)

    def solve_stance(self, name, front, K, t, q, previous=None):
        """The pitch at which the foot stands on its plan at the chosen body height: nearest the preferred roll."""
        hip = self.hip[name]
        Hx, Hy, Hz = [self.W0[t][hip][i][3] for i in range(3)]
        Hy += self.height[t] - self.b0[t]
        L = self.length[name]
        pref = self.pref(name, front, q)
        g = []
        for i, a in enumerate(ANGLES):
            r, dz, sole = self.table[name][i]
            g.append((K[0] - Hx) ** 2 + (K[2] + dz - Hz) ** 2 + (-sole - Hy) ** 2 - L * L)
        roots = []
        for i in range(len(ANGLES) - 1):
            if LIMIT[front][0] <= ANGLES[i] <= LIMIT[front][1] and g[i] * g[i + 1] <= 0 and g[i] != g[i + 1]:
                roots.append(ANGLES[i] + 0.5 * g[i] / (g[i] - g[i + 1]))
        if not roots:
            roots = [min(ANGLES, key=lambda a: abs(g[ANGLES.index(a)]))]
        a = min(roots, key=lambda x: abs(x - (pref if previous is None else previous)))
        r, dz, sole = self.roll(name, a)
        return a, [K[0], -sole, K[2] + dz], r

    def frames(self):
        cfg, ticks, speed = self.cfg, self.ticks, self.speed
        self.run()
        stance, solved = {}, {}
        for name, hip, foot, front in LEGS:
            previous = None
            order = sorted(range(ticks), key=lambda t: (t / ticks - cfg['td'][name]) % 1.0)
            for t in order:
                u = (t / ticks - cfg['td'][name]) % 1.0
                if u < cfg['duty']:
                    q = u / cfg['duty']
                    rest = self.rest_k[name]
                    key = 'F' if front else 'H'
                    sx = cfg['duty'] * ticks * speed
                    K = [rest[0], 0.0, rest[2] + cfg['shift'][key] + sx * (q - 0.5)]
                    a, pos, r = self.solve_stance(name, front, K, t, q, previous)
                    previous = a
                    solved[(name, t)] = (a, pos, r)
        # swings between the stances, in the world: z_world = z_local - speed * t
        for name, hip, foot, front in LEGS:
            key = 'F' if front else 'H'
            standing = [t for t in range(ticks) if (name, t) in solved]
            for t in range(ticks):
                if (name, t) in solved:
                    continue
                a = max(k for k in range(t - ticks, t) if (k % ticks) in standing)
                b = min(k for k in range(t + 1, t + 1 + ticks) if (k % ticks) in standing)
                A, B = solved[(name, a % ticks)], solved[(name, b % ticks)]
                s = (t - a) / (b - a)
                za = A[1][2] - speed * a
                zb = B[1][2] - speed * b
                k = Q.minimum_jerk(s)
                z = (za + (zb - za) * k) + speed * t
                theta = A[0] + (B[0] - A[0]) * (0.5 - 0.5 * math.cos(math.pi * s))
                side = 1 if name[0] == 'R' else -1
                x = A[1][0] + side * cfg['wide'][key] * math.sin(math.pi * s)
                r, dz, sole = self.roll(name, theta)
                lift = cfg['lift'][key] * math.sin(math.pi * min(1.0, s ** 0.85)) ** 1.0
                Hh = [self.W0[t][hip][i][3] for i in range(3)]
                Hh[1] += self.height[t] - self.b0[t]
                Ly = -sole - lift
                vy = min(Ly - Hh[1], L_ := self.length[name] - 1)
                need = math.sqrt(max(0.0, L_ * L_ - vy * vy))
                dz = z - Hh[2]
                if abs(dz) < need and abs(x - Hh[0]) < math.sqrt(need * need - dz * dz):
                    x = Hh[0] + side * math.sqrt(need * need - dz * dz)    # wide enough for the foot to be held up
                solved[(name, t)] = (theta, [x, Hh[1] + vy, z], r, 'swing')
        poses = []
        hist = {}
        info = dict(reach=0.0)
        for t in range(ticks):
            p = self.body(t / ticks, hist)
            p[1][7] = round(self.height[t])
            W = mmd.bone_matrices(self.m, p)
            for name, hip, foot, front in LEGS:
                a, K, r = solved[(name, t)][:3]
                H = [W[hip][i][3] for i in range(3)]
                Rh0 = [x[:3] for x in W[hip][:3]]
                o = Q.sub([W[foot][i][3] for i in range(3)], H)
                L = self.length[name]
                d = Q.sub(K, H)
                if abs(Q.norm(d) - L) > info['reach']:
                    info['reach'] = abs(Q.norm(d) - L)
                d = Q.scale(Q.unit(d), L)
                Rh = Q.mul(Q.turn_to(o, d), Rh0)
                parent = [x[:3] for x in W[self.sk[hip][1]][:3]]
                Q.set_rot(p, hip, Q.mul(Q.tr(parent), Rh), hist)
                Q.set_rot(p, foot, Q.mul(Q.tr(Rh), r), hist)
            p[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, -round(speed * t)]
            poses.append(p)
        self.solved, self.info = solved, info
        return poses


def _played(animation, ticks, slot):
    player = mmd.AnimPlayer(animation, 23, slot)
    played = []
    for _ in range(ticks * 9 + 1):
        assert player.tick()
        pose = [list(v) for v in player.pose]
        pose[0][6:9] = list(player.root)
        played.append(pose)
    return played, player.events


def _locomotion(old, sk, rest):
    """Slots 2, 3 and 4 written from the paws up; every other program stays as it is."""
    new = copy.deepcopy(old)
    reports, changed = [], set()
    for slot, cfg in sorted(GAITS.items()):
        gait = _Gait(old, sk, rest, cfg)
        poses = gait.frames()
        ticks = cfg['ticks']
        source_events = animsheet.slot_frames(old, 23, slot)[2]
        sound = next((dict(e) for _, kind, e in source_events if kind == 'sound'), dict(op='sound', bank=1, note=13))
        events = [(t, kind, e) for t, kind, e in source_events if kind == 'tex' and t == 0]
        for name in cfg['steps']:
            tick = round(cfg['td'][name] * ticks) % ticks
            events.append((tick, 'sound', dict(sound, frame=tick + 1)))
        events.sort(key=lambda e: e[0])
        frames = [[[round(x) for x in bone] for bone in pose] for pose in poses]
        closing = [list(b) for b in frames[0]]
        closing[0][8] = -round(cfg['speed'] * ticks)
        frames.append(closing)
        frames = motionsecondary.cyclic_euler_branches(frames, [b for b in range(1, 23) if b not in (0,)])
        animation = mmd.encode_anim(frames, 23, loop_sample=0, events=events, tol=1)
        index = old.anims.table[slot]
        new.anims.anims[index] = animation
        changed |= {s for s, i in enumerate(old.anims.table) if i == index}
        played, _ = _played(animation, ticks, slot)
        for tick in range(ticks, ticks * 9 + 1, ticks):
            assert all(abs(a - b) <= 2 for bone, other in zip(played[0][1:], played[tick][1:]) for a, b in zip(bone, other)), (slot, 'loop drift')
        speed = abs(played[ticks][0][8] - played[0][0][8]) / ticks
        low, high = SPEED_RANGE[slot]
        assert low <= speed <= high and abs(speed - cfg['speed']) <= 0.5, (slot, speed)
        reports.append(dict(slot=slot, gait=cfg['name'], ticks=ticks, units_per_tick=round(speed, 2),
                            body_height_range=[round(min(gait.height), 1), round(max(gait.height), 1)],
                            max_swing_reach_gap=round(gait.info['reach'], 1),
                            stream_bytes=len(animation.build())))
    return new, reports, sorted(changed)


def _verify(original, actual, sk, changed):
    assert changed_programs(original, actual) == changed
    assert original.tmd.build() == actual.tmd.build()


def build(data, sk):
    if hashlib.sha256(data).hexdigest() != SOURCE or len(sk) != 23:
        raise ValueError('GranKuwagamon recipe requires the pinned reviewed source')
    original = _parse(data, sk)
    resting, idle_checks = _idle(_parse(_pack(original), sk), sk)
    resting = _calm(_parse(_pack(resting), sk), sk)
    rest = animsheet.slot_frames(resting, 23, 0)[0][0]
    moving, moving_checks, changed = _locomotion(resting, sk, rest)
    result = _pack(moving)
    actual = _parse(result, sk)
    _verify(original, actual, sk, sorted({0, *changed}))
    storage = motionstorage.audit(result, 23)
    assert storage['fits'], storage
    return result, dict(species=210, source_sha256=SOURCE,
                        output_sha256=hashlib.sha256(result).hexdigest(),
                        changed_slots=sorted({0, *changed}), storage=storage,
                        idle_checks=idle_checks, moving_checks=moving_checks)


def _axis_angle(m):
    c = max(-1.0, min(1.0, (m[0][0] + m[1][1] + m[2][2] - 1) / 2))
    angle = math.acos(c)
    if angle < 1e-6:
        return [1.0, 0.0, 0.0], 0.0
    k = 1 / (2 * math.sin(angle))
    return Q.unit([(m[2][1] - m[1][2]) * k, (m[0][2] - m[2][0]) * k, (m[1][0] - m[0][1]) * k]), angle


CALM = {5: 0.6, 6: 0.6, 11: 0.5, 12: 0.5, 13: 0.5, 14: 0.5, 15: 0.45, 16: 0.45, 17: 0.45, 18: 0.45}


def _calm(model, sk):
    """The idle's arms, mandibles and wings keep their sequence but move about half as far from where the clip starts."""
    n = 23
    new = copy.deepcopy(model)
    frames, loop, events = animsheet.slot_frames(model, n, 0)
    poses = [[list(b) for b in f] for f in frames]
    hist = {}
    deviation = 0.0
    for pose in poses:
        for b, k in CALM.items():
            r0 = mmd.rot_matrix(*frames[0][b][3:6])
            rt = mmd.rot_matrix(*pose[b][3:6])
            axis, angle = _axis_angle(Q.mul(Q.tr(r0), rt))
            Q.set_rot(pose, b, Q.mul(r0, Q.spin(axis, angle * k)), hist)
    poses[-1][1:] = copy.deepcopy(poses[0][1:])
    poses = motionsecondary.cyclic_euler_branches(poses, sorted(CALM))
    channels = {(b, c) for b in CALM for c in (3, 4, 5)}
    new.anims.anims.append(replace_channels(model.anims.anims[model.anims.table[0]], poses, loop, n, channels))
    new.anims.table[0] = len(new.anims.anims) - 1
    return new


def _idle(old, sk):
    n = len(sk)
    new = copy.deepcopy(old)
    fs, loop, events = animsheet.slot_frames(old, n, 0)
    poses = []
    history = {}
    feet = [8, 10, 20, 22]
    verts = {b: np.array(old.tmd.obj_verts(obj))[:, :3] for b, (obj, _) in enumerate(sk) if obj >= 0}
    lifts = []
    handfold = []
    for i, original in enumerate(fs):
        f = copy.deepcopy(original)
        f[0] = [4096] * 3 + [0] * 6
        w = np.array(mmd.bone_matrices(old, f))
        floor = max((float((verts[b] @ w[b, :3, :3].T + w[b, :3, 3])[:, 1].max()) for b in feet))
        lift = math.ceil(max(0, floor + 2))
        f[1][7] -= lift
        lifts.append(lift)
        for jaw in [5, 6]:
            w = np.array(mmd.bone_matrices(old, f))
            set_rotation(f, jaw, w[3, :3, :3].T @ rotation([-8, 0, 0]) @ w[jaw, :3, :3], history)
        for hand, sign in [(12, -1), (14, 1)]:
            w = np.array(mmd.bone_matrices(old, f))
            base = rotation([0, sign * 12, sign * 6]) @ w[hand, :3, :3]
            h = w[hand, :3, 3]
            extra = 0
            for extra in np.arange(0, 25.01, 0.25):
                target = rotation([0, 0, sign * float(extra)]) @ base
                ground = float((verts[hand] @ target.T + h)[:, 1].max())
                if ground <= -6:
                    break
            assert ground <= -6, (i, hand, ground)
            set_rotation(f, hand, w[sk[hand][1], :3, :3].T @ target, history)
            handfold.append(float(extra))
        f[0] = copy.deepcopy(original[0])
        poses.append(f)
    poses[-1][1:] = copy.deepcopy(poses[0][1:])
    poses = motionsecondary.cyclic_euler_branches(poses, [5, 6, 12, 14])
    channels = {(1, 7)} | {(b, c) for b in [5, 6, 12, 14] for c in [3, 4, 5]}
    new.anims.anims.append(replace_channels(old.anims.anims[old.anims.table[0]], poses, loop, n, channels))
    new.anims.table[0] = len(new.anims.anims) - 1
    return (new, dict(body_lift_range=[min(lifts), max(lifts)], max_extra_pincer_roll=max(handfold)))


