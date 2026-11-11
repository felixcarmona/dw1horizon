"""Shadramon's calm idle (field slot 0) and the looser upper body of its walk and run (slots 2 and 4).

The reviewed gait (shadramon.py: claw strides solved onto the floor, speeds 16 and 38 units a tick) stays: this module is
written over the model that gait produced, and every foot keeps the world position and orientation it had on every tick.
What changes:

- Idle (slot 0 only; slot 33, the battle idle, shares the old clip and keeps it): the import's clip hopped. The
  pelvis went from 123 to 297 units over the floor between ticks 24 and 37 (the head top 371 to 542) and rode a
  58-unit breathing bob besides. The new clip has the same length (72 ticks) (seamless): both claws stay planted on the floor for
  the whole loop, the pelvis breathes (+-2 units), shifts its weight from one foot to the other and turns a little, the
  chest and the head follow it a beat later, the arms hang and sway out of step with each other, the four wing lobes
  flutter at their own phases.
- Walk and run (2, 4): legs and feet are re-solved to the same ankle positions and foot orientations, so the stride,
  the speeds and the planting are those of shadramon.py. The pelvis now sways over the stance foot, drops on the
  swinging side and turns against the shoulders; the spine and head answer through a spring (they trail the hips and
  overshoot a little); the arms swing with a different amplitude each, a second harmonic and their elbows a beat behind;
  each wing lobe flaps with its own amplitude, phase and a second harmonic. No sinusoid repeats with equal amplitudes
  on both sides.

The tired walk (3) is not touched. Offline: `tools/models/edit.py get 250` on the commit before this change, then
`python3 -m tools.models.field_animations.shadramon_loose --source THAT.MMD --out AFTER.MMD` and `edit.py put 250 AFTER.MMD`.
"""
import cmath
import copy
import hashlib
import math

import animsheet
import mmd
import motionstorage
import numeric as np
from tools.models.field_animations.channels import coalesce, replace_channels
from tools.models.field_animations.war_greymon import align, rotation, set_rotation

SPECIES = 250
SOURCE = '7c07a92fdc3c0d342f35e7d68e881518535f4762fd59ad1c51524c10897ebf8f'   # edit.py get 250 before this change
PARENTS = [-1, 0, 1, 2, 2, 4, 2, 6, 1, 8, 9, 1, 11, 12, 2, 2, 2, 2]
IDLE = 72
PI = math.pi
FLOOR = 1.5               # idle claws rest this high over the floor (the walk's stance keeps 4)
LEGS = ((8, 9, 10, -1), (11, 12, 13, 1))
LEG_CHANNELS = {(b, c) for b in range(8, 14) for c in (3, 4, 5)}
UPPER = {(b, c) for b in (1, 2, 3, 4, 5, 6, 7, 14, 15, 16, 17) for c in (3, 4, 5)}
# per wing lobe: (bone, side, yaw amplitude, phase lag, pitch amplitude); the rear lobes are the big ones
LOBES = ((14, -1, 8.4, 0.0, 1.5), (16, 1, 7.2, .21, 1.2), (15, -1, 12.6, .62, 3.0), (17, 1, 10.4, .93, 2.4))
PROFILE = {
    2: dict(sway=4.2, roll=2.3, yaw=3.2, bob=2.6, arm=(19.2, 16.2), elbow=5.5, wing=1.0, head=1.0, lean=4),
    4: dict(sway=5.0, roll=2.8, yaw=4.5, bob=3.4, arm=(28.5, 24.0), elbow=8.0, wing=1.15, head=1.25, lean=13),
}


def wave(t, period, terms, fn=None, zeta=.5):
    """Sum of amp*sin(k*theta + phase). With `fn` the terms pass a spring of natural frequency fn (cycles a loop):
    the response trails and overshoots near fn, as a limb hung on the body does."""
    theta = 2*PI*t/period
    total = 0.
    for k, amp, phase in terms:
        z = amp*cmath.exp(1j*(k*theta + phase))
        if fn:
            r = k/fn
            z /= (1 - r*r + 2j*zeta*r)
        total += z.imag
    return total


class Body:
    def __init__(self, model, skeleton):
        self.model = model
        self.skeleton = skeleton
        self.verts = {b: np.array(model.tmd.obj_verts(o))[:, :3] for b, (o, _) in enumerate(skeleton) if o >= 0}

    def world(self, pose):
        p = copy.deepcopy(pose)
        p[0] = [4096]*3 + [0]*6
        return np.array(mmd.bone_matrices(self.model, p))

    def lowest(self, pose, bones=None):
        """Height over the floor (up positive) of the lowest vertex."""
        w = self.world(pose)
        return -max(float((self.verts[b] @ w[b, :3, :3].T + w[b, :3, 3])[:, 1].max())
                    for b in self.verts if bones is None or b in bones)


def solve_leg(body, rw, f, leg, goal, foot_rotation):
    """Hip and knee rotations putting the ankle on `goal` (original link lengths, the walk's knee pole)."""
    hip, knee, foot, sign = leg
    h = body.world(f)[hip, :3, 3]
    la = np.linalg.norm(f[knee][6:9])
    lb = np.linalg.norm(f[foot][6:9])
    delta = np.array(goal, float) - h
    dist = np.linalg.norm(delta)
    assert abs(la - lb) < dist < la + lb - .1, ('reach', hip, dist, la + lb)
    direct = delta/dist
    pole = np.array([sign*.35, 0, -1.])
    pp = pole - direct*(pole @ direct)
    pp /= np.linalg.norm(pp)
    along = (la*la - lb*lb + dist*dist)/(2*dist)
    joint = h + direct*along + pp*math.sqrt(max(0, la*la - along*along))
    rh = align(rw[hip, :3, :3] @ np.array(f[knee][6:9]), joint - h) @ rw[hip, :3, :3]
    rk = align(rw[knee, :3, :3] @ np.array(f[foot][6:9]), np.array(goal, float) - joint) @ rw[knee, :3, :3]
    return rh, rk, np.array(foot_rotation)


def set_legs(body, rw, f, goals, hist):
    """goals: {foot bone: (ankle world position, foot world rotation)}; the pose f already has its pelvis."""
    solved = {leg: solve_leg(body, rw, f, leg, *goals[leg[2]]) for leg in LEGS}
    for leg in LEGS:
        hip, knee, foot, _ = leg
        rh, rk, rf = solved[leg]
        set_rotation(f, hip, body.world(f)[1, :3, :3].T @ rh, hist)
        set_rotation(f, knee, body.world(f)[hip, :3, :3].T @ rk, hist)
        set_rotation(f, foot, body.world(f)[knee, :3, :3].T @ rf, hist)


def pelvis_pose(f, x, y, z, yaw, roll, hist):
    f[1][6:9] = [round(x), round(y), round(z)]
    set_rotation(f, 1, rotation([0, yaw, roll]), hist)


def torso(body, f, spine_world, head_world, hist):
    set_rotation(f, 2, body.world(f)[1, :3, :3].T @ spine_world, hist)
    set_rotation(f, 3, body.world(f)[2, :3, :3].T @ head_world, hist)


def arms(f, ref, swing, lift, elbow, twist, hist):
    """swing, lift, elbow, twist: {side: degrees}; the shoulders' carried-out anchors stay as stored."""
    for shoulder, elbow_bone, side in ((4, 5, -1), (6, 7, 1)):
        set_rotation(f, shoulder, rotation([swing[side], twist[side], -side*lift[side]]) @ np.array(mmd.rot_matrix(*ref[shoulder][3:6])), hist)
        set_rotation(f, elbow_bone, rotation([elbow[side], 0, 0]) @ np.array(mmd.rot_matrix(*ref[elbow_bone][3:6])), hist)


def wings(f, ref, t, period, scale, hist, harmonic=.24):
    for bone, side, amp, lag, pitch in LOBES:
        yaw = wave(t, period, [(1, amp*scale, -lag), (2, amp*scale*harmonic, .8 - lag)])
        nod = wave(t, period, [(1, pitch*scale, -lag - .9)])
        set_rotation(f, bone, rotation([nod, side*yaw, 0]) @ np.array(mmd.rot_matrix(*ref[bone][3:6])), hist)


def frames_of(model, slot):
    return animsheet.slot_frames(model, 18, slot)[0]


def author_idle(body, rw, idle0, walk):
    """72 ticks (73 samples, as the import had), both claws on the floor on every one."""
    n = IDLE
    base = copy.deepcopy(walk[0])       # the walk's carried-out shoulders and anchors
    ref = copy.deepcopy(idle0)
    ref[1][3:6] = [0, 0, 0]
    w0 = body.world(idle0)
    spine_ref, head_ref = w0[2, :3, :3], w0[3, :3, :3]
    # the standing claws: the walk's mid-stance ankle of each foot, lowered to FLOOR units over the floor
    goals = {}
    for foot, tick in ((10, 4), (13, 4 + 8)):
        w = body.world(walk[tick])
        position = w[foot, :3, 3].copy()
        rotation_world = w[foot, :3, :3].copy()
        position[0] = math.copysign(65, position[0])
        goals[foot] = (position, rotation_world)
    probe = copy.deepcopy(base)
    pelvis_pose(probe, 0, -150, 0, 0, 0, {})
    set_legs(body, rw, probe, goals, {})
    drop = FLOOR - body.lowest(probe, range(8, 14))
    for foot in goals:
        goals[foot][0][1] -= drop
    frames = []
    hist = {}
    fhist = {}
    for t in range(n):
        f = copy.deepcopy(base)
        f[0] = copy.deepcopy(idle0[0])

        def b(*terms, **kw):
            return wave(t, n, list(terms), **kw)
        breath = b((1, 1, 0), (2, .22, .9), (3, .06, 2.1))
        shift = b((1, 1, .5), (2, .28, 2.0))
        pelvis_pose(f, 3.4*shift + .6*b((3, 1, .4)), -150 + 2.2*breath, 1.2*b((2, 1, 1.3)),
                    1.1*b((1, 1, 1.9)), 1.3*b((1, 1, 2.2), (2, .3, .2)), hist)
        spine = rotation([2.4 + 1.5*b((1, 1, -.35), (2, .2, .4)), 2.4*b((1, 1, 1.2), (2, .35, 1.9), fn=1.8, zeta=.6),
                          1.0*b((1, 1, -.2))]) @ spine_ref
        head = rotation([2.4*b((1, 1, .5), (3, .35, 2.2), fn=2.4, zeta=.4) - .8*breath,
                         7.5*b((1, 1, 2.0), (2, .4, .3), fn=2.2, zeta=.45),
                         1.6*b((1, 1, .9), (2, .5, 2.4), fn=2.2, zeta=.45)]) @ head_ref
        torso(body, f, spine, head, hist)
        arms(f, ref,
             {-1: 2.8*b((1, 1, .4), (2, .3, 1.1), fn=2.0, zeta=.5), 1: 2.2*b((1, 1, 2.0), (2, .35, .2), fn=2.0, zeta=.5)},
             {-1: 10 + 1.4*b((1, 1, 1.4)), 1: 10 + 1.0*b((1, 1, 3.0))},
             {-1: -5 - 2.4*b((1, 1, -.2), fn=1.8, zeta=.5), 1: -5 - 2.0*b((1, 1, 1.4), fn=1.8, zeta=.5)},
             {-1: 1.5*b((1, 1, .2)), 1: 1.2*b((1, 1, 1.8))}, hist)
        wings(f, ref, t, n, .55, hist, harmonic=.35)
        set_legs(body, rw, f, goals, fhist)
        frames.append(f)
    frames.append(copy.deepcopy(frames[0]))
    return frames


def loosen(body, model, rw, idle0, slot):
    """New pelvis, torso, head, arms and wings for a walk or run, the legs solved to the ankles it had."""
    p = PROFILE[slot]
    cur = frames_of(model, slot)
    n = len(cur) - 1
    ref = copy.deepcopy(idle0)
    ref[1][3:6] = [0, 0, 0]
    spine_ref = body.world(idle0)[2, :3, :3]
    out, ankles = [], []
    hist, fhist = {}, {}
    for t, source in enumerate(cur):
        f = copy.deepcopy(source)
        ws = body.world(source)
        goals = {foot: (ws[foot, :3, 3].copy(), ws[foot, :3, :3].copy()) for foot in (10, 13)}
        head_cur = ws[3, :3, :3].copy()

        def b(*terms, **kw):
            return wave(t, n, list(terms), **kw)
        pelvis_pose(f, -p['sway']*b((1, 1, .3), (2, .18, 1.4)), -150 + p['bob']*b((2, 1, PI/2 + .25), (1, .3, 1.1)),
                    1.6*b((2, 1, .9)), p['yaw']*b((1, 1, PI + .1), (2, .22, .6)), p['roll']*b((1, 1, .3), (2, .25, 1.0)), hist)
        spine = rotation([p['lean'] + 1.5*b((2, 1, .6), (1, .35, 2.0), fn=3, zeta=.5),
                          4.4*b((1, 1, 0), (2, .2, 1.1), fn=3, zeta=.55),
                          1.5*b((1, 1, PI/2), (2, .6, 2.1), fn=3, zeta=.5)]) @ spine_ref
        head = rotation([p['head']*2.4*b((2, 1, -.9), (1, .35, 1.2), fn=2.6, zeta=.4),
                         p['head']*3.0*b((1, 1, -.8), (2, .3, .5), fn=2.6, zeta=.4),
                         p['head']*1.6*b((1, 1, .6), (2, .5, 2.0), fn=2.6, zeta=.4)]) @ head_cur
        torso(body, f, spine, head, hist)
        left, right = p['arm']
        arms(f, ref,
             {-1: left*b((1, 1, 0), (2, .16, -.7), fn=3.2, zeta=.55), 1: right*b((1, 1, PI), (2, .2, .5), fn=3.2, zeta=.55)},
             {-1: 10 + 2.2*b((1, 1, .9)), 1: 10 + 1.6*b((1, 1, PI + 1.6))},
             {-1: -4 - p['elbow']*(.5 + .5*b((1, 1, -.45 - PI/2), fn=3.6, zeta=.5)),
              1: -4 - p['elbow']*1.1*(.5 + .5*b((1, 1, PI/2 - .5), fn=3.6, zeta=.5))},
             {-1: 2.0*b((1, 1, .3)), 1: 1.7*b((1, 1, 2.3))}, hist)
        wings(f, ref, t, n, p['wing'], hist)
        set_legs(body, rw, f, goals, fhist)
        out.append(f)
        ankles.append({foot: goals[foot][1] for foot in goals})
    out[-1][1:] = copy.deepcopy(out[0][1:])
    return out, ankles


def pack_gait(body, model, slot, frames, ankles):
    old = model.anims.anims[model.anims.table[slot]]
    animation = replace_channels(old, frames, 0, 18, UPPER | LEG_CHANNELS, tolerance=1)
    animation = replace_channels(animation, frames, 0, 18, {(1, c) for c in (6, 7, 8)}, tolerance=0)
    temporary = copy.deepcopy(model)
    temporary.anims.table[slot] = len(temporary.anims.anims)
    temporary.anims.anims.append(animation)
    decoded = animsheet.slot_frames(temporary, 18, slot)[0]
    fhist = {}
    for tick, f in enumerate(decoded):      # the feet follow the decoded knees, not the solved ones
        for knee, foot in ((9, 10), (12, 13)):
            set_rotation(f, foot, body.world(f)[knee, :3, :3].T @ ankles[tick][foot], fhist)
    decoded[-1][1:] = copy.deepcopy(decoded[0][1:])
    animation = replace_channels(animation, decoded, 0, 18, {(b, c) for b in (10, 13) for c in (3, 4, 5)}, tolerance=0)
    animation, _ = coalesce(animation)
    return animation


def build(data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE or [b[1] for b in skeleton] != PARENTS:
        raise ValueError("Shadramon's loose clips are written over the model with the reviewed claw strides")
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = len(skeleton)
    model = mmd.MMD.parse(data, 18)
    model.type = SPECIES
    body = Body(model, skeleton)
    idle0 = frames_of(model, 0)[0]
    walk = frames_of(model, 2)
    ref = copy.deepcopy(idle0)
    ref[1][3:6] = [0, 0, 0]
    rw = body.world(ref)
    gaits = {}
    for slot in (2, 4):
        frames, ankles = loosen(body, model, rw, idle0, slot)
        gaits[slot] = pack_gait(body, model, slot, frames, ankles)
    idle = [[[int(round(x)) for x in v] for v in p] for p in author_idle(body, rw, idle0, walk)]
    for slot, animation in gaits.items():
        model.anims.table[slot] = len(model.anims.anims)
        model.anims.anims.append(animation)
    model.anims.anims.append(mmd.encode_anim(idle, 18, loop_sample=0, events=[], tol=1, repeats=False))
    model.anims.table[0] = len(model.anims.anims) - 1
    used = sorted({i for i in model.anims.table if i is not None})      # drop what no slot plays any more
    renumber = {old: new for new, old in enumerate(used)}
    model.anims.anims = [model.anims.anims[i] for i in used]
    model.anims.table = [None if i is None else renumber[i] for i in model.anims.table]
    result = model.build()
    return result, dict(species=SPECIES, source_sha256=SOURCE, changed_slots=[0, 2, 4], storage=motionstorage.require(result, 18))


def main():
    import argparse
    import json
    from pathlib import Path
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    rig = json.loads(Path('content/species/250-shadramon.json').read_text())['model']['skeleton']
    data, report = build(Path(args.source).read_bytes(), rig)
    Path(args.out).write_bytes(data)
    print(args.out, len(data), 'B', report['storage'])


if __name__ == '__main__':
    main()
