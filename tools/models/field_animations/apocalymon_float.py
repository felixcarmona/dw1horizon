"""Apocalymon's field idle, walk, tired walk and run: a floating mass that hovers, glides, sags and surges (species 400).

The import's four clips were one 105-tick performance (the tentacles and the cape waving) with only the root faster, so the
walk, the tired walk and the run were the idle drifting over the ground. Offline only (player builds replay the pinned
delta): `tools/models/edit.py get 400` on the commit before this change, then
`python3 -m tools.models.field_animations.apocalymon_float --source THAT.MMD --out AFTER.MMD` and `edit.py put 400 AFTER.MMD`.

The rig has no legs. Bone 1 is the dodecahedron body (and the root of everything else) with bone 30, the golden drill
under it, hung at the same pivot; bones 2, 3 and 4-5 are the neck, the humanoid torso and its hat; bones 6-8 and 9-11 are
the two small arms; bones 12-14 are the cape, a three-link chain trailing behind (+z); bones 15-17, 18-20, 21-23, 24-26 and
27-29 are five tentacle chains of two links and a spiked ball. The tentacle balls are the lowest points. The model's own
tick-0 lowest point is the floor these clips keep to: the body hovers above it, never through it.

Every clip is written as a whole loop of body terms (height, place along the ground, the body's turn), and then every
loose piece follows the body through damped springs driven by the body's velocity (the tentacles and the cape trail it,
the arms and the torso lag it, the drill hangs back). A chain bends joint by joint towards the direction the air pushes it
(opposite to the body's velocity, plus a droop), each link a little later and further than the one before, so the follow-
through arrives late and the chains move like ropes and not like one rigid fan:

- Idle (120 ticks): a slow hover. The body rises and falls twice with a small drift and a slow turn; the torso breathes, the
  head looks about, the tentacles drift on springs of different periods, the cape stirs, the arms float.
- Walk (60 ticks, 21 units a tick): a hovering glide. Two soft surges per loop (the body leans forward and gains a little
  on the root, then falls back), a rocking from side to side, the tentacles and the cape trailing behind.
- Tired walk (84 ticks, 13 units a tick): low and heavy. The mass sags to the floor, its tentacle balls dragging, the torso
  and head hang forward, the tentacles droop, slow wide rocking, long springs.
- Run (40 ticks, 44 units a tick): a fast push. The body pitches forward and surges in a bound twice a loop, the
  tentacles stream back, the cape lifts and whips, the arms trail.

Every clip repeats exactly (the last sample is the first with the root travelled), the root moves the same distance every
tick, and slots 1, 18 and 33, which share the idle's program, follow it.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet  # noqa: E402
import mmd  # noqa: E402
import motionstorage  # noqa: E402
import retarget as rt  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402
from tools.models.field_animations.celebrations import set_world, turn  # noqa: E402
from tools.models.field_animations.syakomon_hop import harmonics, spring  # noqa: E402

SPECIES, NB = 400, 31
SOURCE = '91f9848cd31f8c5865b620ce4feb95ce31c09585cb41195d70b876519af2758b'   # edit.py get 400 before this change
SLOTS = (0, 2, 3, 4)
SHARED_WITH_IDLE = (1, 18, 33)
CLIP_OF_SLOT = {0: 'idle', 2: 'walk', 3: 'tired', 4: 'run'}

# chains: (bones from the base to the tip) and the share of the bend each joint takes
TENTACLES = ((15, 16, 17), (18, 19, 20), (21, 22, 23), (24, 25, 26), (27, 28, 29))
CAPE = (12, 13, 14)
ARM_L, ARM_R = (6, 7, 8), (9, 10, 11)
JOINT = (.5, .9, .85)            # share of the bend a joint takes, base to tip

# n ticks; v: root units a tick; for the body: up/ahead/side/pitch/yaw/roll amplitudes and the cycles in the loop (rhythm);
# wind: (trail gain, vertical gain, lateral gain) of the limbs; droop: constant pull down; lift: pull up with speed.
CLIPS = {
    'idle': dict(n=120, v=0., hover=6., bob=5., bob_cycles=2, ahead=0., side=6., pitch=1.6, yaw=4., roll=2.2,
                 trail=0., vert=1.0, lat=1.0, droop=.3, lift=0., wobble=1.5, torso=2.6, spring=(20., 24., 28.)),
    'walk': dict(n=60, v=21., hover=8., bob=7., bob_cycles=2, ahead=16., side=7., pitch=6., yaw=4.5, roll=4.,
                 trail=1.7, vert=1.0, lat=1.0, droop=.12, lift=.4, wobble=1.0, torso=1.8, spring=(12., 15., 18.)),
    'tired': dict(n=84, v=13., hover=0., bob=3., bob_cycles=2, ahead=5., side=8., pitch=10., yaw=3., roll=4.5,
                  trail=.9, vert=.8, lat=1.0, droop=1.4, lift=0., wobble=.5, torso=1.8, spring=(20., 25., 30.)),
    'run': dict(n=40, v=44., hover=10., bob=11., bob_cycles=2, ahead=24., side=6., pitch=15., yaw=3.5, roll=5.,
                trail=2.4, vert=1.0, lat=1.0, droop=0., lift=1.2, wobble=.7, torso=1.3, spring=(8., 10., 12.)),
}
TOL = {None: 6, **{b: (18 if b >= 15 else 90) for b in range(2, 30) if b not in (3, 4)}}
SUB = 8
V_REF = 40.        # a body speed (units a tick) that bends a chain by one unit of wind
GAIN_TENT, GAIN_CAPE, GAIN_ARM = .36, .4, .3   # radians of bend per unit of wind and joint share
V_VERT = 8.0       # and the vertical / sideways speed that does


def unit(v):
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-9 else v


def axis_angle(axis, angle):
    a = unit(axis)
    c, s = math.cos(angle), math.sin(angle)
    x, y, z = a
    C = 1 - c
    return [[c + x * x * C, x * y * C - z * s, x * z * C + y * s],
            [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
            [z * x * C - y * s, z * y * C + x * s, c + z * z * C]]


class Rig:
    def __init__(self, model, skeleton, base):
        self.model, self.sk, self.base = model, skeleton, base
        self.objs = {b: np.array(model.tmd.obj_verts(skeleton[b][0]))[:, :3].astype(float)
                     for b in range(1, len(skeleton)) if skeleton[b][0] is not None and skeleton[b][0] >= 0}

    def mats(self, pose):
        return mmd.bone_matrices(self.model, pose)

    def lowest(self, pose):
        """Largest y (the lowest point; y is down) of the posed mesh, without the root's own height."""
        m = self.mats(pose)
        top = -1e9
        for b, v in self.objs.items():
            M = np.array(m[b])
            top = max(top, float((v @ M[:3, :3].T + M[:3, 3])[:, 1].max()))
        return top

    def bend(self, pose, chain, winds, gain):
        """Bend each joint of the chain towards `wind` (a vector, world), sweeping the whole chain round joint by joint."""
        for k, b in enumerate(chain):
            m = self.mats(pose)
            nxt = chain[k + 1] if k + 1 < len(chain) else None
            a = np.array([m[b][i][3] for i in range(3)])
            if nxt is not None:
                d = np.array([m[nxt][i][3] for i in range(3)]) - a
            else:
                prev = chain[k - 1]
                d = a - np.array([m[prev][i][3] for i in range(3)])
            u = unit(d)
            wind = winds[k]
            perp = wind - float(wind @ u) * u
            if k == 0:
                # the first link leaves the body: never bend it back into the body's surface
                out = a - np.array([m[1][i][3] for i in range(3)])
                out = unit(out)
                perp = perp - min(0., float(perp @ out)) * out
            mag = float(np.linalg.norm(perp))
            if mag < 1e-6:
                continue
            angle = min(1.5, gain * JOINT[k] * mag)
            wr, _ = rt.world_transform(self.sk, pose)
            R = rt.m3mul(axis_angle(np.cross(u, perp), angle), wr[b])
            set_world(pose, self.sk, b, rotation=R)


def raise_envelope(need, radius, sigma):
    """A smooth (circular) curve at or above `need`: its running maximum over +-radius ticks, blurred over about the same
    reach, so the body rises ahead of the tentacle that would touch the floor and settles after it."""
    n = len(need)
    top = np.array([max(need[(i + j) % n] for j in range(-radius, radius + 1)) for i in range(n)])
    ker = np.exp(-(np.arange(-radius, radius + 1) / sigma) ** 2 / 2)
    ker /= ker.sum()
    return np.array([sum(ker[j + radius] * top[(i + j) % n] for j in range(-radius, radius + 1)) for i in range(n)])


def follow(drive, period, zeta=.4):
    """Damped spring following a (n, 3) periodic drive."""
    return np.stack([spring(drive[:, i], period, zeta) for i in range(3)], 1)


def series(name):
    c = CLIPS[name]
    n, v = c['n'], c['v']
    t = np.arange(n, dtype=float)
    ph = 2 * math.pi * t / n
    bc = c['bob_cycles']
    pb = bc * ph
    # height: the hover plus a bob of two soft cycles with a harmonic, not a sine
    up = c['hover'] + c['bob'] * (np.sin(pb) + .28 * np.sin(2 * pb + 1.1)) / 1.2
    ahead = c['ahead'] * (np.sin(pb - .9) + .3 * np.sin(2 * pb + .4)) / 1.2          # surges: gains on the root, falls back
    ahead -= ahead.mean()
    side = c['side'] * (np.sin(ph + .4) + .3 * np.sin(2 * ph + 1.6)) / 1.2
    pitch = c['pitch'] * (1 + .35 * np.sin(pb - .5 + .5))                              # leaning forward, more on the push
    pitch += .5 * c['pitch'] * .0
    roll = c['roll'] * (np.sin(ph + 1.9) + .3 * np.sin(2 * ph + .3)) / 1.2
    yaw = c['yaw'] * (np.sin(ph + .7) + .25 * np.sin(3 * ph + 2.2)) / 1.2
    if name == 'idle':
        pitch = 1.0 + c['pitch'] * (np.sin(pb + .8) + .3 * np.sin(1 * ph + .3))
    return dict(n=n, t=t, up=up, ahead=ahead, side=side, pitch=pitch, roll=roll, yaw=yaw)


def velocity(s, c):
    """Body velocity per tick in the model's world (x right, y down, z back): the root's travel and the body's own."""
    n = s['n']
    cyc = lambda a: (np.roll(a, -1) - np.roll(a, 1)) / 2.0 if False else (np.roll(a, -1) - np.roll(a, 1)) / 2.0
    vx = cyc(s['side'])
    vy = -cyc(s['up'])
    vz = -(c['v'] + cyc(s['ahead']))
    return np.stack([vx, vy, vz], 1)


def wind_of(V, c, periods, lag):
    """The wind the limbs lean into: against the body's velocity (steady trail, bob lag) plus droop, and a little
    wobble. Per-axis normalised, then lagged through springs."""
    n = len(V)
    t = np.arange(n, dtype=float)
    drive = np.stack([-V[:, 0] / V_VERT * c['lat'],
                      -V[:, 1] / V_VERT * c['vert'] + c['droop'] - c['lift'] * np.abs(V[:, 2]) / V_REF,
                      -V[:, 2] / V_REF * c['trail']], 1)
    wob = c['wobble']
    k = 2 * math.pi * t / n
    c1, c2 = c.get('cyc', (2, 3))
    drive[:, 0] += wob * (np.sin(c1 * k + lag) + .15 * np.sin(c2 * k + 2 * lag))
    drive[:, 1] += wob * .8 * (np.sin(c1 * k + 1.0 + lag) + .15 * np.sin(c2 * k + 3 * lag))
    drive[:, 2] += wob * .9 * np.sin(c1 * k + 2.0 + lag)
    return follow(drive, periods)


DRILL = 1.         # how much the drill lags the body's turn
MARGIN = 4.
KEEP = 2              # channels (of rx, ry, rz) a limb bone keeps moving: every channel costs resident bytes


def channel_mask(rig, poses):
    """The Euler channels each limb bone moves in (the KEEP most-moving ones; the others stay at rest)."""
    mask = {}
    for b in range(1, len(rig.sk)):
        if b in (1, 30):
            continue
        rest = np.array(rig.base[b][3:6], float)
        spread = np.ptp(np.array([p[b][3:6] for p in poses], float) - rest, 0)
        mask[b] = sorted(int(c) for c in np.argsort(-spread)[:KEEP])
    return mask


def apply_mask(rig, poses, mask):
    for p in poses:
        for b, chans in mask.items():
            p[b][3:6] = [round(p[b][3 + c]) if c in chans else rig.base[b][3 + c] for c in range(3)]


def build_frames(rig, name):
    c = CLIPS[name]
    s = series(name)
    n = s['n']
    V = velocity(s, c)
    p1, p2, p3 = c['spring']
    def wave(cc, per, lag, step=.9, joints=3):
        """One wind per joint of a chain, each a little later in phase than the joint before: a travelling wave."""
        return [wind_of(V, cc, per * (1 + .08 * j), lag + step * j) for j in range(joints)]
    cyc = ((1, 2),) * 5
    tent = [wave(dict(c, cyc=cyc[k]), (p1, p2, p3)[k % 3] * (1 + .05 * k), .7 * k, step=.6) for k in range(5)]
    cape = wave(dict(c, droop=c['droop'] * .6, lift=c['lift'] * 2.2, wobble=c['wobble'] * 1.5, cyc=(1, 2)), p2, 4.0, step=.8)
    arm = wave(dict(c, wobble=c['wobble'] * 1.3, cyc=(1, 2)), p1, 2.5, step=.6)
    arm_r = wave(dict(c, wobble=c['wobble'] * 1.3, cyc=(1, 2)), p1 * 1.3, 5.1, step=.6)
    t = np.arange(n, dtype=float)
    k = 2 * math.pi * t / n
    ts = c['torso']
    bc = c['bob_cycles']
    # the torso looms: a slow lean in and out, against the body's turn; the head lags it and looks about; the hat sways late
    chest = np.stack([spring(-.8 * s['pitch'] * ts + 3.0 * ts * np.sin(bc * k + .6) + 6.0 * ts * np.sin(k + 4.0), 9., .4),
                      spring(-1.4 * s['yaw'] + 5.0 * ts * np.sin(k + 2.2), 11., .45),
                      spring(-.9 * s['roll'] + 3.0 * ts * np.sin(2 * k + 1.4) + 3.0 * ts * np.sin(k), 10., .45)], 1)
    head = np.stack([spring(-.6 * s['pitch'] + 6.0 * ts * np.sin(bc * k + 1.4) + (14. if name == 'tired' else 0.), 8., .35),
                     spring(14. * ts * (np.sin(k + .3) + .4 * np.sin(3 * k + 1.0)), 10., .4),
                     spring(-1.2 * s['roll'] + 5. * ts * np.sin(2 * k + .9), 9., .4)], 1)
    hat = np.stack([spring(-.5 * head[:, 0] + 6. * np.sin(bc * k + 2.6), 6., .3),
                    spring(-.4 * head[:, 1], 7., .3),
                    spring(8. * np.sin(2 * k + 3.0) + 3 * np.sin(k), 7., .3)], 1)
    drill = np.stack([spring(-.9 * s['pitch'] + 5. * np.sin(bc * k + 2.4), 12., .3),
                      spring(-1.2 * s['yaw'] + 8. * np.sin(k + 1.0), 13., .3),
                      spring(-1.0 * s['roll'] + 5. * np.sin(2 * k + 2.0), 11., .3)], 1)

    def make(i, lift):
        pose = copy.deepcopy(rig.base)
        pose[0] = [4096] * 3 + [0] * 6
        pose[1][6] += s['side'][i]
        pose[1][7] += -s['up'][i] - lift
        pose[1][8] += -s['ahead'][i]
        turn(pose, 1, [s['pitch'][i], s['yaw'][i], s['roll'][i]])
        turn(pose, 30, list(drill[i]))
        turn(pose, 3, list(chest[i]))
        turn(pose, 4, list(head[i]))
        turn(pose, 5, list(hat[i]))
        for j, ch in enumerate(TENTACLES):
            rig.bend(pose, ch, [w[i] for w in tent[j]], GAIN_TENT)
        rig.bend(pose, CAPE, [w[i] for w in cape], GAIN_CAPE)
        rig.bend(pose, ARM_L, [w[i] for w in arm], GAIN_ARM)
        rig.bend(pose, ARM_R, [w[i] for w in arm_r], GAIN_ARM)
        return pose

    poses = [make(i, 0.) for i in range(n)]
    apply_mask(rig, poses, channel_mask(rig, poses))
    # never through the floor: where a drooping tentacle's ball would dip below the tick-0 floor, the body is raised
    # (a rigid shift, so every pose keeps its shape), the raise eased over a few ticks
    need = np.array([max(0., rig.lowest(p) - rig.floor + MARGIN) for p in poses])
    lift = raise_envelope(need, 12, 4.5)
    for p, up in zip(poses, lift):
        p[1][7] -= up
    return poses, s, c


def decoded_deficit(result, anim, rig, n):
    """Per tick of the decoded clip: how far its lowest point is below the floor (less the margin kept), eased."""
    probe = copy.deepcopy(result)
    probe.anims.anims.append(anim)
    probe.anims.table[2] = len(probe.anims.anims) - 1
    frames = animsheet.slot_frames(probe, NB, 2)[0]
    need = np.array([max(0., rig.lowest(frames[i]) - rig.floor + MARGIN - 2.) for i in range(n)])
    return raise_envelope(need, 5, 2.0)


def author(data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError("Apocalymon's floating clips are written over the reviewed import")
    mmd.exe().add_type(SPECIES, skeleton)
    old = mmd.MMD.parse(data, NB)
    old.type = SPECIES
    base = [[round(x) for x in v] for v in animsheet.slot_frames(old, NB, 0)[0][0]]
    rig = Rig(old, skeleton, base)
    rig.floor = rig.lowest(base)
    result = copy.deepcopy(old)
    streams, ticks = {}, {}
    for slot in SLOTS:
        name = CLIP_OF_SLOT[slot]
        frames_, loop, _ = animsheet.slot_frames(old, NB, slot)
        assert loop == 0, (slot, loop)
        poses, s, c = build_frames(rig, name)
        speed = c['v']
        n = len(poses)
        out = []
        for i, p in enumerate(poses):
            q = [[round(x) for x in b] for b in p]
            q[0] = [4096] * 3 + [0, 0, 0, 0, 0, -round(speed * i)]
            out.append(q)
        out.append(copy.deepcopy(out[0]))
        out[-1][0] = [4096] * 3 + [0, 0, 0, 0, 0, -round(speed * n)]
        mmd.close_loop(out, 0)
        anim = mmd.encode_anim(out, NB, 0, [], tol=TOL, repeats=False)
        for _ in range(4):
            # the key fit moves the tentacle tips by a few units: lift the body where the decoded clip dips below the floor
            deficit = decoded_deficit(result, anim, rig, n)
            if deficit.max() <= 0:
                break
            for i in range(n):
                out[i][1][7] -= int(math.ceil(deficit[i]))
            out[n][1][7] = out[0][1][7]
            anim = mmd.encode_anim(out, NB, 0, [], tol=TOL, repeats=False)
        streams[slot] = len(result.anims.anims)
        result.anims.anims.append(anim)
        ticks[slot] = n
    for slot in SHARED_WITH_IDLE:
        result.anims.table[slot] = streams[0]
    for slot in SLOTS:
        result.anims.table[slot] = streams[slot]
    for anim in result.anims.anims:
        anim.tail = b''
    used = sorted({i for i in result.anims.table if i is not None})
    renumber = {i: k for k, i in enumerate(used)}
    result.anims.anims = [result.anims.anims[i] for i in used]
    result.anims.table = [None if i is None else renumber[i] for i in result.anims.table]
    output = result.build()
    effective = mmd.MMD.parse(output, NB)
    effective.type = SPECIES
    assert effective.tmd.build() == old.tmd.build()
    changed = changed_programs(old, effective)
    assert set(changed) == set(SLOTS) | set(SHARED_WITH_IDLE), changed
    return output, dict(ticks=ticks, storage=motionstorage.audit(output, NB), species=SPECIES, source_sha256=SOURCE,
                        changed_slots=changed)


def build(data, skeleton):
    output, report = author(data, skeleton)
    return output, dict(report, output_sha256=hashlib.sha256(output).hexdigest())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    skeleton = [tuple(b) for b in json.loads((ROOT / 'content/species/400-apocalymon.json').read_text())['model']['skeleton']]
    data, report = build(args.source.read_bytes(), skeleton)
    args.out.write_bytes(data)
    print(args.out, len(data), 'B', json.dumps(report, default=str))


if __name__ == '__main__':
    main()
