"""ExTyrannomon's arms in the walk, tired walk and run (species 266, slots 2, 3 and 4).

Offline only (player builds replay the pinned delta): `tools/models/edit.py get 266` on the commit before this change,
then `python3 -m tools.models.field_animations.extyrannomon_arms --source THAT.MMD --out AFTER.MMD --report R.json` and
`edit.py put 266 AFTER.MMD`.

What was wrong. The rig has nine bones and every limb is one rigid piece hung on the body bone (1): the head and back
(1), the belly plate (2), the left and right leg (3, 4), the tail (5), a small horn (6) and the left and right arm
(7, 8: shoulder disc, cannon and claws in one piece). The arms barely moved: the walk swung them 4 degrees, the tired
walk held them still, and the run pumped them with a straight-line ramp.

What this does. Only the two arm bones' rotation is rewritten, tick by tick, in the body's frame. Each arm is driven by
the leg on its own side (the arm goes forward as that foot goes back), and the arm is a heavy spring that follows the
drive: it arrives a tick or two late, overshoots a little and settles, which stands in for the elbow and the forearm that
the one-piece arm does not have. A second, quarter-cycle-late term sweeps the claws in and out so the claw tip travels
an oval instead of a line, a small twist about the arm's length rolls the shoulder disc, and every foot landing (the
clip's own step sounds) knocks both arms down and lets them rebound. Nothing else is touched: the other bones, the
root, the sound and texture events, the number of ticks and the loop are the original values. The cycle of a clip is
its length minus the closing sample, and the drive is read off the legs of the same clip, so the arms close the loop.
Slot 36 shares the run's program and changes with it.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet  # noqa: E402
import animstudio  # noqa: E402
import mmd  # noqa: E402
import numpy as np  # noqa: E402
import motionstorage  # noqa: E402
import retarget as R  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402
from tools.models.field_animations.valkyrimon_limbs import DIRS, inside  # noqa: E402

SPECIES, NB = 266, 9
SLOTS = (0, 2, 3, 4)
SOURCE = '4ac9d27b348f7f097433405ff2bb7e9f9f283e25c0570d2971089384d73dfd46'   # edit.py get 266 before this change
ARMS = {7: dict(leg=3, side=-1), 8: dict(leg=4, side=1)}       # left (x < 0) and right arm, the leg on the same side
DEG = 4096 / 360
# Per clip, in degrees (ticks for the spring): `swing` raises the claws as the same-side foot goes back, `sweep` moves
# them outward, `twist` rolls the arm about its length, `lift` is a constant raise of the whole arm over the clip's own
# hang, `period` the spring's own period (ticks), `damp` its damping ratio, `smooth` the blur of the leg drive (ticks),
# `bump` the knock of a foot landing and `sound` the ticks of the landings are read from the clip's step sounds.
PLAN = {
    2: dict(swing=21, swing2=4, sweep=9, twist=7, lift=14, period=7.5, damp=.45, smooth=2.0, bump=4, sway=4),
    3: dict(swing=11, swing2=2, sweep=9, twist=8, lift=10, period=12, damp=.28, smooth=3.0, bump=3, sway=5),
    4: dict(swing=36, swing2=6, sweep=11, twist=9, lift=22, period=5.5, damp=.4, smooth=1.3, bump=6, sway=5),
}


def rot(axis, degrees):
    return R.from_axis_angle(axis, math.radians(degrees))


def pitch(frame, leg):
    """Where the leg's foot is fore and aft: the angle of its down direction in the side view (degrees, backward +)."""
    r = R.rot_of(frame[leg])
    return math.degrees(math.atan2(r[2][1], r[1][1]))


def blur(values, sigma):
    """Circular gaussian blur of a periodic series."""
    n = len(values)
    reach = max(1, int(math.ceil(3 * sigma)))
    weights = [math.exp(-.5 * (k / sigma) ** 2) for k in range(-reach, reach + 1)]
    total = sum(weights)
    return [sum(w * values[(i + k - reach) % n] for k, w in enumerate(weights)) / total for i in range(n)]


def spring(target, period, damp, kicks, cycles=60):
    """The periodic response of a damped spring (period `period` ticks, damping ratio `damp`) to `target`, with a velocity
    kick at the ticks of `kicks` ({tick: size}); the steady state after many cycles, so the loop closes."""
    n = len(target)
    w = 2 * math.pi / period
    x, v = target[0], 0.0
    out = [0.0] * n
    for cycle in range(cycles):
        for t in range(n):
            v += kicks.get(t, 0.0)
            a = w * w * (target[t] - x) - 2 * damp * w * v
            v += a
            x += v
            out[t] = x
    return out


def drive_of(frames, leg, n, spec):
    """The same-side leg's fore-aft swing, centred, scaled to -1..1 and blurred: one value per tick of the cycle."""
    p = [pitch(frames[t], leg) for t in range(n)]
    mid = (max(p) + min(p)) / 2
    half = (max(p) - min(p)) / 2
    return blur([(v - mid) / half for v in p], spec['smooth'])


def landings(events, n):
    return sorted({k % n for k, kind, _ in events if kind == 'sound'})


def arm_angles(frames, events, n, spec, arm):
    """Per tick: (swing, sweep, twist) in degrees of one arm, to be put on its hang."""
    info = ARMS[arm]
    d = drive_of(frames, info['leg'], n, spec)
    # the clip's leg cycle: the first tick the drive comes back to its start, within the cycle
    cyc = cycle_length(frames, info['leg'], n)
    quarter = cyc / 4
    late = lambda series, shift: [series[int(math.floor(t - shift)) % n] * (1 - (shift % 1)) +
                                  series[int(math.floor(t - shift) + 1) % n] * (shift % 1) for t in range(n)]
    sw = [spec['swing'] * v + spec['swing2'] * (2 * v * v - 1) for v in d]       # a flattened second harmonic: no pure sine
    sweep = [info['side'] * spec['sweep'] * v for v in late(d, quarter)]
    twist = [info['side'] * spec['twist'] * v for v in late(d, -quarter / 2)]
    kicks = {t: -spec['bump'] * 2 * math.pi / spec['period'] * .35 for t in landings(events, n)}
    s = spring(sw, spec['period'], spec['damp'], kicks)
    w = spring(sweep, spec['period'] * 1.3, spec['damp'] + .1, {t: info['side'] * spec['sway'] * .1 for t in landings(events, n)})
    tw = spring(twist, spec['period'] * 1.6, spec['damp'] + .15, {})
    return s, w, tw


def cycle_length(frames, leg, n):
    """Ticks of one stride of the leg (the walk holds three in its 60)."""
    p = [round(pitch(frames[t], leg)) for t in range(n)]
    for c in range(2, n):
        if n % c == 0 and all(abs(p[t] - p[(t + c) % n]) <= 1 for t in range(n)):
            return c
    return n


GROUPS = {'back': (1,), 'belly': (2,), 'tail': (5,), 'horn': (6,), 'legs': (3, 4)}
SHOULDER = 30                              # vertices this close to the shoulder joint are built into the body


class Collider:
    """Counts the vertices of an arm that lie inside another part (the closed mesh, majority of five ray parities)."""

    def __init__(self, model, sk):
        self.model = model
        self.mesh = animstudio.FastMesh(type('M', (), dict(m=model, skel=sk))())

    def scene(self, pose, arm):
        """What an arm can hit in this pose: the world triangles of the other parts, fixed while the arm turns."""
        p = copy.deepcopy(pose)
        p[0] = [4096] * 3 + [0] * 6
        world = self.mesh.world(mmd.bone_matrices(self.model, p)).astype(float)
        other = 15 - arm                                       # 7 <-> 8
        groups = dict(GROUPS, arm=(other,))
        return {k: world[self.mesh.tri[np.isin(self.mesh.bone, v)]] for k, v in groups.items()}

    def counts(self, pose, arm, scene):
        p = copy.deepcopy(pose)
        p[0] = [4096] * 3 + [0] * 6
        mats = mmd.bone_matrices(self.model, p)
        a_, k_ = next((a, k) for b, a, k in self.mesh.slices if b == arm)
        m_ = np.array(mats[arm], float)
        world = np.zeros((len(self.mesh.V), 3))
        world[a_:a_ + k_] = self.mesh.V[a_:a_ + k_].astype(float) @ m_[:3, :3].T + m_[:3, 3]
        tri = world[self.mesh.tri[self.mesh.bone == arm]]
        points = np.vstack([tri.reshape(-1, 3), tri.mean(1)])
        points = points[np.linalg.norm(points - np.array(mats[arm], float)[:3, 3], axis=1) > SHOULDER]
        out = {}
        for k, tris in scene.items():
            lo, hi = tris.reshape(-1, 3).min(0), tris.reshape(-1, 3).max(0)
            near = points[((points >= lo) & (points <= hi)).all(1)]        # only these can be inside the closed mesh
            out[k] = int((sum(inside(near, tris, d).astype(int) for d in DIRS) >= 3).sum()) if len(near) else 0
        return out


def arm_pose(pose, arm, hang, angles, sign):
    """`pose` with the arm bone turned by `angles` = (swing, sweep, twist, extra yaw, extra lift) degrees on its hang."""
    s, w, tw, dy, dp = angles
    lifted = rot([1, 0, 0], sign * (s + dp))
    m = R.m3mul(rot([0, 1, 0], w + dy), R.m3mul(rot([0, 0, 1], tw), R.m3mul(lifted, hang)))
    out = copy.deepcopy(pose)
    out[arm][3:6] = [round(v) for v in mmd.matrix_euler(m, pose[arm][3:6])]
    return out


REACH = 40                                 # the largest extra turn tried, degrees, in steps of STEP
STEP = 3
MARGIN = 3.0                               # kept from the edge of the clear range


def smooth_within(low, high, start):
    """The smoothest periodic series between `low` and `high` (per tick) that stays near `start`: blur, then clamp, repeated."""
    n = len(start)
    x = list(start)
    ker = (1, 2, 3, 4, 3, 2, 1)
    for _ in range(14):
        x = [sum(w * x[(i + k - 3) % n] for k, w in enumerate(ker)) / sum(ker) for i in range(n)]
        x = [min(max(v, lo), hi) for v, lo, hi in zip(x, low, high)]
    return x


def correct(clear, n, required=True, sign_choices=(1, -1)):
    """An extra turn per tick (degrees) so that `clear(t, turn)` holds on every tick: the smallest, in one direction through
    the whole clip, smooth, and inside the range that is clear on each tick (a bound on the far side too)."""
    if all(clear(t, 0.0) for t in range(n)):
        return [0.0] * n
    best = None
    for sign in sign_choices:
        failing = [t for t in range(n) if not clear(t, 0.0)]
        near = set(range(n))
        low, high, start, ok = [0.0] * n, [float(REACH)] * n, [0.0] * n, True
        for t in range(n):
            if t not in near:
                continue
            run = [v for v in range(0, REACH + 1, STEP) if clear(t, sign * v)]
            if not run:
                ok = False
                break
            first = run[0]
            if first == 0:                 # clear as it is: the range is the run from 0
                last = 0
                while last + STEP in run:
                    last += STEP
                high[t] = max(0.0, last - MARGIN)
            else:                          # the first clear value, and the run that follows it
                last = first
                while last + STEP in run:
                    last += STEP
                low[t] = min(first + MARGIN, (first + last) / 2)
                high[t] = max(last - MARGIN, low[t])
                start[t] = low[t]
        if not ok:
            continue
        x = smooth_within(low, high, start)
        score = max(abs(v) for v in x)
        if best is None or score < best[0]:
            best = (score, [sign * v for v in x])
    if best is None and not required:
        return [0.0] * n
    if best is None:
        raise ValueError('an arm cannot be cleared within the reviewed range')
    return best[1]


def apply(model, sk, frames, events, n, spec, sign, hangs, allowed):
    """The frames with both arms re-posed on their `hangs` (pose entries), `sign` the turn about x that lifts the claws;
    where an arm would sink into the body or a leg deeper than `allowed` (vertices per part), an extra outward turn and
    then an extra upward turn (the smallest ones, in one direction through the clip, smooth) are put on."""
    out = copy.deepcopy(frames)
    collider = Collider(model, sk)
    notes = {}
    for arm in ARMS:
        hang = R.rot_of(hangs[arm])
        s, w, tw = arm_angles(frames, events, n, spec, arm)
        base = [(s[t] + spec['lift'], w[t], tw[t]) for t in range(n)]
        scenes = [collider.scene(out[t], arm) for t in range(n)]
        extra = {'yaw': [0.0] * n, 'lift': [0.0] * n}

        def fits(t, yaw, lift):
            c = collider.counts(arm_pose(out[t], arm, hang, base[t] + (yaw, lift), sign), arm, scenes[t])
            return all(c[k] <= allowed[k] for k in c)

        extra['yaw'] = correct(lambda t, v: fits(t, v, 0.0), n, required=False)   # outward if that is enough
        extra['lift'] = correct(lambda t, v: fits(t, extra['yaw'][t], v), n)   # the upward turn is found with the outward one on
        notes[arm] = {k: (round(min(v), 1), round(max(v), 1)) for k, v in extra.items()}
        for t in range(n):
            out[t] = arm_pose(out[t], arm, hang, base[t] + (extra['yaw'][t], extra['lift'][t]), sign)
    for a in ARMS:
        out[n][a][3:6] = out[0][a][3:6]
    return out, notes


def _parse(data, sk):
    mmd.exe().skeleton[SPECIES] = sk
    mmd.exe().bone_count[SPECIES] = len(sk)
    model = mmd.MMD.parse(data, len(sk))
    model.type = SPECIES
    return model


def original(model, slot):
    """The clip as stored: whole-number poses per tick, loop start and events."""
    frames, loop, events = animsheet.slot_frames(model, NB, slot)
    frames = [[[int(round(v)) for v in bone] for bone in pose] for pose in frames]
    return frames, loop, [(k, kind, c) for k, kind, c in events]


def lift_sign(model):
    """+1 when a turn about x by a positive angle lifts the claws of the idle arm (it moves the tip up the screen)."""
    import numpy as np
    sk = mmd.exe().skeleton[SPECIES]
    verts = np.array(model.tmd.obj_verts(sk[7][0]))[:, :3].astype(float)
    tip = verts[verts[:, 2].argmin()]
    up = np.array(R.m3mul(rot([1, 0, 0], 10), [[1, 0, 0], [0, 1, 0], [0, 0, 1]])) @ tip
    return 1 if up[1] < tip[1] else -1


HANG = {2: 'idle', 3: 'own', 4: 'idle'}


def baseline(model, sk, slot):
    """The most vertices of an arm inside each other part in the clip as it is stored."""
    collider = Collider(model, sk)
    worst = {k: 0 for k in (*GROUPS, 'arm')}
    for pose in original(model, slot)[0]:
        for arm in ARMS:
            for k, v in collider.counts(pose, arm, collider.scene(pose, arm)).items():
                worst[k] = max(worst[k], v)
    return worst


def new_frames(model, sk, slot, plan=None):
    frames, loop, events = original(model, slot)
    n = len(frames) - 1
    spec = (plan or PLAN)[slot]
    idle = original(model, 0)[0][0]
    hangs = {a: (idle[a] if HANG[slot] == 'idle' else frames[0][a]) for a in ARMS}
    out, notes = apply(model, sk, frames, events, n, spec, lift_sign(model), hangs, baseline(model, sk, slot))
    return out, loop, events, notes


def build(data, sk, plan=None):
    if hashlib.sha256(data).hexdigest() != SOURCE or len(sk) != NB:
        raise ValueError('ExTyrannomon arms require the nine-bone import as `edit.py get 266` gave it before this change')
    model = _parse(data, sk)
    result = copy.deepcopy(model)
    checks = []
    for slot in (2, 3, 4):
        frames, loop, events, notes = new_frames(model, sk, slot, plan)
        program = mmd.encode_anim(frames, NB, loop, events, tol=0, repeats=False)
        index = model.anims.table[slot]
        assert sum(1 for v in model.anims.table if v == index) == (2 if slot == 4 else 1)
        result.anims.anims[index] = program
        checks.append(dict(slot=slot, ticks=len(frames), corrections=notes))
    for animation in result.anims.anims:
        animation.tail = b''
    output = result.build()
    effective = _parse(output, sk)
    assert effective.tmd.build() == model.tmd.build()
    return output, dict(species=SPECIES, source_sha256=SOURCE, output_sha256=hashlib.sha256(output).hexdigest(),
                        changed_slots=changed_programs(model, effective), checks=checks, storage=motionstorage.require(output, NB))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    sk = json.loads((ROOT / 'content/species/266-extyrannomon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), sk)
    a.out.write_bytes(data)
    if a.report:
        a.report.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps(proof['changed_slots']), proof['storage']['resident_bytes'], len(data))


if __name__ == '__main__':
    main()
