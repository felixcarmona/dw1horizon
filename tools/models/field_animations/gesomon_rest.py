"""Gesomon's grounded idle (field slots 0, 1 and 18), its tired walk (slot 3) and the arms of its walk and run (2, 4).

The import played one 84-tick clip in the idle, the tired walk and two more slots: the whole squid hung 80 units
above the floor (its tentacle tips never came lower than 78 units) and its long arms swung up and down, so the lowest
point of the mesh moved between 9 and 89 units; the tired walk was the idle again. The walk and the run
(gesomon.py, kept as they are) stand on the floor. This module writes the other clips over that model:

- Idle (slots 0, 1, 18): the import's own clip, its mantle, head and tentacles as they were, lowered onto the floor.
  Per tick the pelvis is set so that the lowest tentacle tip is 1.5 units above the floor. The long arms are
  rewritten (Arm: a shoulder and two hinges, solved for the wrist and the lowest point of the claw; the claw's own
  pose is set so that its palm faces in and down and its fingers forward and down): they hang forward and out and
  sway a little behind the breathing. Same length.
- Walk and run (slots 2, 4): only the long arms change, to a loose counter-swing in step with the gait (the same
  arm solver, wider in the run), clear of the trunk and the floor, instead of the old frozen pose with a sine on it.
- Tired walk (slot 3): a 30-tick loop, one slow cycle. The mantle and head droop forward by 22 to 25
  degrees, the body sits low (pelvis 104 to 116 against the idle's 123 to 153) and lurches forward and settles back,
  and the squid hauls itself along on the floor: the eight small tentacles are planted for 45
  per cent of a cycle, staggered, while the root moves at a steady 11 units a tick, and each is dragged forward just
  above the floor (12 units) before it plants again. A planted tip does not move over the floor. The two long arms
  do not step: limp, they lie stretched out behind the body, forearm and claw within a few units of the floor and
  the palm on it, and are dragged along, swaying a little, one side half a cycle behind the other. Two footfall sounds per cycle, the walk's.

Offline authoring (the player's build replays the plain delta): `tools/models/edit.py get 240`, then
`python3 -m tools.models.field_animations.gesomon_rest --source build/imported-model-edit/edit/240-Gesomon.MMD
--out AFTER.MMD` and `tools/models/edit.py put 240 AFTER.MMD`. The source must be the importer's model.
"""
import copy
import math

import animsheet
import legik
import mmd
import motionstorage
import numeric as np
from tools.models.field_animations import gesomon
from tools.models.field_animations.war_greymon import align, set_rotation

SPECIES = 240
TENTACLES = tuple(range(11, 29))
ARMS = {'right': (3, 4, 5, 6), 'left': (7, 8, 9, 10)}
FLOOR = 1.5                # units the lowest tentacle tip keeps above the floor in the idle
TOLERANCE = 2              # fit error allowed when packing a clip, in the pose's own units
LOWER = 85                 # the import's own grounded copy of the idle (slot 33) sits this much lower


def smooth(values, radius):
    n = len(values)
    return [sum(values[(i+k) % n] for k in range(-radius, radius+1))/(2*radius+1) for i in range(n)]


def dilate(values, radius):
    n = len(values)
    return [max(values[(i+k) % n] for k in range(-radius, radius+1)) for i in range(n)]


class Body:
    def __init__(self, model, skeleton):
        self.model = model
        self.skeleton = skeleton
        self.verts = {b: np.array(model.tmd.obj_verts(obj))[:, :3]
                      for b, (obj, _) in enumerate(skeleton) if obj >= 0}

    def world(self, pose):
        p = copy.deepcopy(pose)
        p[0] = [4096]*3 + [0]*6
        return np.array(mmd.bone_matrices(self.model, p))

    def low(self, w, bones):
        """Height (up positive) of the lowest vertex of `bones`."""
        return -max(float((self.verts[b] @ w[b, :3, :3].T + w[b, :3, 3])[:, 1].max()) for b in bones if b in self.verts)

    def lowest_point(self, w, bones):
        best = None
        for b in bones:
            if b in self.verts:
                pts = self.verts[b] @ w[b, :3, :3].T + w[b, :3, 3]
                col = [float(x) for x in pts[:, 1]]
                i = max(range(len(col)), key=col.__getitem__)
                if best is None or col[i] > best[1]:
                    best = ([float(x) for x in pts[i]], col[i])
        return best[0]


def lift_arm(body, pose, chain, angle, history):
    """Turns the arm `chain` about its shoulder, about the horizontal axis that raises its lowest point, by `angle` degrees."""
    w = body.world(pose)
    shoulder = [float(x) for x in w[chain[0], :3, 3]]
    point = body.lowest_point(w, chain)
    lever = [a-b for a, b in zip(point, shoulder)]
    axis = [lever[1]*0 - lever[2]*-1, lever[2]*0 - lever[0]*0, lever[0]*-1 - lever[1]*0]   # lever x up, up = (0,-1,0)
    norm = math.sqrt(sum(x*x for x in axis))
    if norm < 1e-6:
        return
    ax = [x/norm for x in axis]
    t = angle*math.pi/180
    k = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
    rw = np.eye(3) + math.sin(t)*k + (1-math.cos(t))*(k @ k)
    parent = body.skeleton[chain[0]][1]
    r = w[parent, :3, :3].T @ (rw @ w[chain[0], :3, :3])
    set_rotation(pose, chain[0], r, history)


def clear_arms(body, frames, margin=1.5):
    need = {side: [0.]*len(frames) for side in ARMS}
    for side, chain in ARMS.items():
        for i, pose in enumerate(frames):
            hist = {chain[0]: [float(x) for x in pose[chain[0]][3:6]]}
            if body.low(body.world(pose), chain) >= margin:
                continue
            lo, hi = 0., 70.
            for _ in range(12):
                mid = (lo+hi)/2
                trial = copy.deepcopy(pose)
                lift_arm(body, trial, chain, mid, dict(hist))
                if body.low(body.world(trial), chain) >= margin:
                    hi = mid
                else:
                    lo = mid
            need[side][i] = hi
    for side, chain in ARMS.items():
        angles = smooth(dilate(need[side], 6), 6)
        for i, pose in enumerate(frames):
            if angles[i] > 0.01:
                lift_arm(body, pose, chain, angles[i], {chain[0]: [float(x) for x in pose[chain[0]][3:6]]})
    return need


def grounded_idle(body, frames):
    """The import's idle (frames: its loop, the last sample repeating the first) lowered onto the floor."""
    n = len(frames) - 1
    out = [copy.deepcopy(p) for p in frames[:n]]
    for p in out:
        p[1][7] += LOWER
    for radius in (3, 1):      # lower, then trim what the smoothing left: the lowest tentacle tip ends 1.5 units up
        drop = [body.low(body.world(p), TENTACLES) - FLOOR for p in out]
        for p, d in zip(out, smooth(drop, radius)):
            p[1][7] += round(d)
    out.append(copy.deepcopy(out[0]))
    return out


# ---- tired walk ----------------------------------------------------------------------------------------------
LOOP = 30                  # ticks: one slow cycle (two cycles do not fit the resident animation buffer)
CYCLE = 30
SPEED = 11                 # root units a tick
DUTY = .45
LIFT = 12                  # tentacle tips drag this low (units) while they are pulled forward
PELVIS = 112               # mean height of the pelvis (the walk's is 120, the idle's 138)
DROOP = 22                 # degrees the mantle and head tip forward
# (hip, knee, end) of the eight tentacles and of the two long arms (shoulder, the bar to the elbow, the claw)
LIMBS = [(c[0], c[1], c[-1]) for c in gesomon.CHAINS] + [(3, 5, 6), (7, 9, 10)]
ARM_LIMBS = (8, 9)


def limb_rest(body, rest):
    """Per limb: the straight rest pose's joints, the lengths of its two bars and the pointed end of its last bone."""
    rw = body.world(rest)
    out = []
    for hip, knee, end in LIMBS:
        pts = body.verts[end] @ rw[end, :3, :3].T + rw[end, :3, 3]
        if (hip, knee, end) in LIMBS[ARM_LIMBS[0]:]:
            direction = rw[end, :3, 3] - rw[knee, :3, 3]   # claws: the far end of the claw from its elbow
            origin = rw[knee, :3, 3]
            far = [float(np.linalg.norm(q - origin)) for q in pts]
        else:
            direction = rw[knee, :3, 3] - rw[hip, :3, 3]
            far = [float(x) for x in (pts @ direction)]
        i = max(range(len(far)), key=far.__getitem__)
        tip = pts[i]
        out.append((tip, float(np.linalg.norm(rw[knee, :3, 3]-rw[hip, :3, 3])), float(np.linalg.norm(tip-rw[knee, :3, 3]))))
    return rw, out


def plant(body, pose, rw, limb, tip_data, index, target_xz, lift, history, pole=None):
    """Puts the pointed end of one limb on the floor at `target_xz` (lift units above it): two bars, the elbow towards
    its rest side, the claw/tentacle's underside on the ground."""
    hip, knee, end = limb
    tip, length1, length2 = tip_data
    target = np.array([target_xz[0], -lift, target_xz[1]])
    hip_parent, knee_parent = body.skeleton[hip][1], body.skeleton[knee][1]
    error = 0
    for _ in range(8):
        w = body.world(pose)
        root = w[hip, :3, 3]
        pole_point = rw[knee, :3, 3] + np.array([20*(1 if index % 2 == 0 else -1), 0, 0]) if pole is None else root + np.array(pole)
        joint, endpoint = map(np.array, legik.solve(root.tolist(), target.tolist(), length1, length2, (pole_point-root).tolist()))
        rh = align(rw[knee, :3, 3]-rw[hip, :3, 3], joint-root) @ rw[hip, :3, :3]
        rk = align(tip-rw[knee, :3, 3], endpoint-joint) @ rw[knee, :3, :3]
        set_rotation(pose, hip, w[hip_parent, :3, :3].T @ rh, history)
        w = body.world(pose)
        set_rotation(pose, knee, w[knee_parent, :3, :3].T @ rk, history)
        w = body.world(pose)
        bottom = float((body.verts[end] @ w[end, :3, :3].T + w[end, :3, 3])[:, 1].max())
        error = bottom+lift
        chain = [b for b in range(hip, end+1) if body.skeleton[b][1] >= hip or b == hip]
        under = -1.5 - body.low(w, [b for b in chain if b in body.verts])
        target[1] -= error + max(0., under)
    return error


def bump(u, a, b):
    return math.sin(math.pi*(u-a)/(b-a))**2 if a <= u < b else 0.


def tired_frames(body, rest):
    rw, tip_data = limb_rest(body, rest)
    frames, plans, history = [], [], {}
    stride = SPEED*CYCLE*DUTY
    half = stride/2
    for t in range(LOOP):
        u = (t/CYCLE) % 1.
        pull = bump(u, 0., .5)
        slump = bump(u, .4, .9)
        p = copy.deepcopy(rest)
        p[0] = [4096]*3 + [0]*3 + [0, 0, -SPEED*t]
        p[1][7] = -round(PELVIS + 4*pull - 5*slump)
        p[1][8] = 22 - round(14*pull - 6*slump)
        p[1][3] = round((DROOP + 3*slump)*4096/360)
        row = []
        for index, (limb, data) in enumerate(zip(LIMBS, tip_data)):
            arm = index >= ARM_LIMBS[0]
            offset = (index % 2)*.5 + ((index//2)*.125 if not arm else .25)
            phase = (t/CYCLE + offset) % 1
            if arm:
                continue                   # the long arms are laid afterwards (rewrite_arms)
            if phase < DUTY:
                z, lift = -half + stride*phase/DUTY, 0.
            else:
                v = (phase-DUTY)/(1-DUTY)
                ease = v*v*(3-2*v)
                z, lift = half*(1-2*ease), LIFT*math.sin(math.pi*v)**2
            x, z0 = float(data[0][0]), float(data[0][2])
            if index >= 4:
                z0 -= 50              # the short front tentacles stay within reach of their roots
            err = plant(body, p, rw, limb, data, index, (x, z0+z), lift, history)
            row.append((limb[2], phase < DUTY, lift, err))
        frames.append(p)
        plans.append(row)
    frames.append(copy.deepcopy(frames[0]))
    frames[-1][0] = [4096]*3 + [0]*3 + [0, 0, -SPEED*LOOP]
    return frames, plans


def solve_linear(a, b):
    n = len(b)
    m = [list(row) + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[piv] = m[piv], m[c]
        if abs(m[c][c]) < 1e-12:
            m[c][c] = 1e-12
        for r in range(n):
            if r != c:
                f = m[r][c]/m[c][c]
                m[r] = [x - f*y for x, y in zip(m[r], m[c])]
    return [m[i][n]/m[i][i] for i in range(n)]


class Arm:
    """One long arm as the animators built it: a shoulder (bone 3 or 7) that turns about the vertical (ry) and
    swings in its plane (rz, rx kept at 0), and two hinges (the next two bones, rz only). The claw is set on its own:
    its fingers run along its local y and its palm faces local +z, and `frame` gives where they point in the world
    (the claw's pose is computed from the forearm's so that it does). Solved numerically for the wrist's place over
    the floor, the lowest point of the claw and, softly, the elbow."""

    def __init__(self, body, rest, side):
        self.body, self.bones = body, (3, 4, 5, 6) if side > 0 else (7, 8, 9, 10)
        self.prev = [0., 0., 0.]

    def apply(self, pose, u, frame):
        b3, b4, b5, b6 = self.bones
        pose[b3][3:6] = [0, round(u[0]), round(u[1])]
        pose[b4][3:6] = [0, 0, round(u[2])]
        pose[b5][3:6] = [0, 0, round(u[3])]
        f, n = frame
        w = self.body.world(pose)
        r5 = w[b5, :3, :3]
        cols = [[float(r5[i, j]) for i in range(3)] for j in range(3)]
        cols = [[x/math.sqrt(sum(y*y for y in c)) for x in c] for c in cols]
        r5 = [[cols[j][i] for j in range(3)] for i in range(3)]       # rotation part of bone 5, normalised
        x = [f[1]*n[2]-f[2]*n[1], f[2]*n[0]-f[0]*n[2], f[0]*n[1]-f[1]*n[0]]
        want = [[x[i], f[i], n[i]] for i in range(3)]                 # columns: local x, y, z in the world
        local = [[sum(r5[k][i]*want[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
        angles = mmd.matrix_euler(local, self.prev)
        self.prev = angles
        pose[b6][3:6] = [round(a) for a in angles]

    def measure(self, pose, u, frame):
        self.apply(pose, u, frame)
        w = self.body.world(pose)
        b3, b4, b5, b6 = self.bones
        return ([float(x) for x in w[b6, :3, 3]], [float(x) for x in w[b5, :3, 3]], self.body.low(w, [b6]),
                [self.body.low(w, [b]) for b in (b4, b5)])

    def solve(self, pose, goal, start, hold=None, iterations=40):
        """goal: dict with `x`, `z` (the wrist's place), `low` (height of the claw's lowest point), `frame` (finger and
        palm directions), `elbow` (x, height, z the elbow would like) with its `weights`, and `lie` (None, or the
        height the forearm's and the upper arm's lowest points are pulled to). Returns the angles and the residual."""
        u = [float(x) for x in start]
        frame = goal['frame']
        ew = goal.get('weights', (.5, .5, .5))
        lie = goal.get('lie')
        hold = goal.get('hold', .05) if hold is None else hold
        prev = list(self.prev)

        def residual(u):
            self.prev = list(prev)
            wrist, elbow, low, down = self.measure(pose, u, frame)
            r = [wrist[0]-goal['x'], wrist[2]-goal['z'], goal.get('low_weight', 1.)*(low-goal['low'])]
            r += [10*min(0., h-2.) for h in down]
            if lie is not None:
                r += [goal.get('upper_weight', goal.get('lie_weight', 2.))*(down[0]-lie), goal.get('lie_weight', 2.)*(down[1]-lie)]
            e = goal['elbow']
            r += [ew[0]*(elbow[0]-e[0]), ew[1]*(-elbow[1]-e[1]), ew[2]*(elbow[2]-e[2])]
            r += [hold*(u[i]-start[i]) for i in range(4)]
            return r
        for _ in range(iterations):
            r0 = residual(u)
            jac = []
            for i in range(4):
                v = list(u)
                v[i] += 6
                jac.append([(a-b)/6 for a, b in zip(residual(v), r0)])
            ata = [[sum(jac[i][k]*jac[j][k] for k in range(len(r0))) + (1e-3 if i == j else 0) for j in range(4)] for i in range(4)]
            atb = [-sum(jac[i][k]*r0[k] for k in range(len(r0))) for i in range(4)]
            step = solve_linear(ata, atb)
            big = max(abs(x) for x in step)
            if big > 120:
                step = [x*120/big for x in step]
            u = [a+b for a, b in zip(u, step)]
            if big < .4:
                break
        self.prev = list(prev)
        self.apply(pose, u, frame)
        return u, residual(u)[:3]


def unit(v):
    k = math.sqrt(sum(x*x for x in v))
    return [x/k for x in v]


def claw_frame(side, finger, palm):
    """Finger and palm directions in the world from their description for the right arm (x outwards, y down,
    forward is -z); the left arm mirrors x. The palm is made square to the fingers."""
    f = unit([side*finger[0], finger[1], finger[2]])
    n = [side*palm[0], palm[1], palm[2]]
    d = sum(a*b for a, b in zip(n, f))
    return f, unit([a-d*b for a, b in zip(n, f)])


def rewrite_arms(body, rest, frames, target, *, seam=True, starts=None):
    """Replaces the long arms of every tick (the closing copy of the first tick excepted when `seam`) by arms put at
    `target(tick, side)` (see Arm.solve), the rest of the pose staying as it is."""
    n = len(frames) - 1 if seam else len(frames)
    arms = {side: Arm(body, rest, side) for side in (1, -1)}
    last = {}
    for t in range(n):
        for side, arm in arms.items():
            goal = target(t, side)
            if side not in last:           # first tick: the best of a few starting poses
                best = None
                for ry in range(-2000, 2001, 500):
                    for rz in (-1000, 0, 1000):
                        for a4 in (-600, 0, 600):
                            trial = copy.deepcopy(frames[t])
                            arm.prev = [0., 0., 0.]
                            u, err = arm.solve(trial, goal, [ry, rz, a4, 0], hold=0., iterations=25)
                            cost = sum(e*e for e in err) + sum(v*v for v in [u[1]/200, u[2]/400, u[3]/400])
                            if best is None or cost < best[0]:
                                best = (cost, u, list(arm.prev))
                last[side] = best[1]
                arm.prev = best[2]
            last[side], _ = arm.solve(frames[t], goal, last[side])
    for sweep in range(2):                 # go round again from where the loop ended, so its end meets its start
        for t in range(n):
            for side, arm in arms.items():
                last[side], _ = arm.solve(frames[t], target(t, side), last[side])
    if seam:
        for b in range(3, 11):
            frames[n][b] = copy.deepcopy(frames[0][b])
    return frames


# hanging arms: the claw hangs in front, a little outside the shoulder, its fingers forward and down, the palm facing
# in and down; they swing against the steps and sway with the breathing
def arm_goal(side, x, z, low, finger, palm, elbow, weights=(.5, .5, .5), **more):
    return dict(x=side*x, z=z, low=low, frame=claw_frame(side, finger, palm),
                elbow=(side*elbow[0], elbow[1], elbow[2]), weights=weights, **more)


def idle_arms(t, side, n=83):
    ph = 2*math.pi*t/n + (0 if side > 0 else .7)
    s = math.sin(ph-1.3)
    return arm_goal(side, 185 + 6*math.sin(ph-.8), -40 + 14*s, 6 + 6*math.sin(ph-1.8), (.15, .55 - .06*s, -.8), (-.8, .5, .2),
                    (190, 120, 70))


def walk_arms(t, side, n=18):
    ph = 2*math.pi*t/n + (0 if side > 0 else math.pi)
    s = math.sin(ph+.6)
    return arm_goal(side, 185 + 8*math.sin(2*ph), -40 + 60*s, 28 + 22*math.sin(ph+.6+1.57), (.15, .55 - .3*s, -.8 + .2*s),
                    (-.8, .5, .2), (190, 120, 70), hold=.3)


def run_arms(t, side, n=18):
    ph = 2*math.pi*t/n + (0 if side > 0 else math.pi)
    s = math.sin(ph+.6)
    return arm_goal(side, 175 + 12*math.sin(2*ph), -40 + 100*s, 60 + 40*math.sin(ph+.6+1.57), (.15, .4 - .5*s, -.8 + .3*s),
                    (-.8, .5, .2), (180, 140, 60), hold=.3)


def tired_arms(t, side, n=LOOP):
    swing = 2*math.pi*(t/CYCLE + (0 if side > 0 else .5))
    return arm_goal(side, 170 + 8*math.sin(swing + 1.2), 400 + 18*math.sin(swing), -4., (.15, -.12, 1.), (0., 1., 0.),
                    (115, 4, 105), weights=(1., 1., 1.), lie=0., lie_weight=4., low_weight=1., hold=.4)


def put_clip(model, frames, slots, events=(), tol=TOLERANCE):
    frames = [[[int(round(x)) for x in v] for v in p] for p in frames]
    anim = mmd.encode_anim(frames, 29, loop_sample=0, events=list(events), tol=tol, repeats=False)
    model.anims.anims.append(anim)
    for slot in slots:
        model.anims.table[slot] = len(model.anims.anims) - 1


def drop_unused(model):
    """Removes the animations no slot plays any more and renumbers the table."""
    used = sorted({i for i in model.anims.table if i is not None})
    renumber = {old: new for new, old in enumerate(used)}
    model.anims.anims = [model.anims.anims[i] for i in used]
    model.anims.table = [None if i is None else renumber[i] for i in model.anims.table]


def build(data, skeleton):
    """data: the importer's model (gesomon.SOURCE) -> (the model with its walk, run, idle and tired walk, a report)."""
    walked, _ = gesomon.build(data, skeleton)
    mmd.exe().add_type(SPECIES, skeleton)
    model = mmd.MMD.parse(walked, 29)
    model.type = SPECIES
    body = Body(model, skeleton)
    idle_frames = animsheet.slot_frames(model, 29, 0)[0]
    shared = {s for s in range(len(model.anims.table)) if model.anims.table[s] == model.anims.table[0]}
    assert shared == {0, 1, 18}, shared
    idle = grounded_idle(body, idle_frames)
    rest = copy.deepcopy(idle_frames[40])
    rest[0] = [4096]*3 + [0]*6
    rest[1][6:9] = [0, -PELVIS, 22]
    rewrite_arms(body, rest, idle, idle_arms)
    walk, _, walk_events = animsheet.slot_frames(model, 29, 2)
    walk = rewrite_arms(body, rest, [copy.deepcopy(p) for p in walk], walk_arms)
    run, _, run_events = animsheet.slot_frames(model, 29, 4)
    run = rewrite_arms(body, rest, [copy.deepcopy(p) for p in run], run_arms)
    tired, plans = tired_frames(body, rest)
    tired = rewrite_arms(body, rest, tired, tired_arms)
    sounds = [(t, 'sound', dict(bank=1, note=17)) for t in range(0, LOOP, CYCLE//2)]
    put_clip(model, idle, (0, 1, 18))
    put_clip(model, walk, (2,), walk_events)
    put_clip(model, run, (4,), run_events)
    put_clip(model, tired, (3,), sounds)
    drop_unused(model)
    result = model.build()
    return result, dict(species=SPECIES, source_sha256=gesomon.SOURCE, changed_slots=[0, 1, 2, 3, 4, 18],
                        tired=dict(loop=LOOP, cycle=CYCLE, speed=SPEED, duty=DUTY, plan=plans),
                        storage=motionstorage.require(result, 29))


def main():
    import argparse
    import json
    from pathlib import Path
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', required=True, help="the importer's 240-Gesomon.MMD (edit.py get 240)")
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    rig = json.loads(Path('content/species/240-gesomon.json').read_text())['model']['skeleton']
    data, report = build(Path(args.source).read_bytes(), rig)
    Path(args.out).write_bytes(data)
    print(args.out, len(data), 'B', report['storage'])


if __name__ == '__main__':
    main()
