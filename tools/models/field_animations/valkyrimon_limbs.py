"""Valkyrimon's field clips (idle, walk, condition walk, run: slots 0, 2, 3, 4) with their limbs kept out of the body.

Offline only (player builds replay the pinned delta): `tools/models/edit.py get 255` on the commit before this change,
then `python3 -m tools.models.field_animations.valkyrimon_limbs --source THAT.MMD --out AFTER.MMD --report R.json` and
`edit.py put 255 AFTER.MMD`.

What was wrong. The clips are native Angemon's walk, condition walk and run solved onto this rig (and its own idle).
Timing, root travel, footsteps and the character of the movement are right and are kept as they are; but in the walk and
the run the right arm swings through the chest (up to 117 vertices of the arm inside the torso), the legs cut into each
other a little in the walk, the run, the condition walk and in the second half of the idle (2 to 13 vertices).

What this does. Every clip is decoded, and only where a test finds a limb vertex inside the closed mesh of another part is a
small extra rotation put on the limb's root bone (the elbow opened outward so the hand clears the chest, both hips spread apart),
in its parent's frame, the smallest that clears with a margin. The corrections are spread over neighbouring ticks (a
smooth bump, never a step) and checked again on the whole pose. Everything else, the other bones, the root travel, the sound
events, the number of ticks and the loop, is the original value.
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
import animstudio  # noqa: E402
import mmd  # noqa: E402
import motionsecondary  # noqa: E402
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402

R = motionsecondary.R
SPECIES, NB = 255, 30
SLOTS = (0, 2, 3, 4)
# The calmer carriage of each clip (see `relax`); the idle is not touched.
CARRIAGE = {
    0: dict(bob=1, lift=1, elbow=(-40, 1.0), arm=1.0, delay=0, life=True),
    2: dict(bob=.55, lift=.65, elbow=(-40, .5), arm=1.25, delay=1.5, widen=9, cape=0.0),
    3: dict(bob=.8, lift=.8, elbow=(-40, 1.0), arm=1.0, delay=0, widen=5, cape=0.0),
    4: dict(bob=.7, lift=.75, elbow=(-40, .5), arm=.85, delay=1.0, widen=9, cape=0.0),
}
SOURCE = '2206ecd01480cecd0a918a69cf51fcc7988af2acd42ffe3ae79dabff0d22904d'   # edit.py get 255 before this change
TOLERANCE = 0                                       # the original keys are kept: unchanged ticks stay exact
MARGIN = 2.5                                        # degrees past the first clear angle
R_LEG, L_LEG = (18, 19, 20), (21, 22, 23)
ARMS = ((5, (5, 6, 7, 8)), (9, (9, 10, 11, 12)))
DIRS = ([1, .3, .2], [0, 1, .1], [.1, .2, 1], [-.7, .2, .5], [.3, -1, .2])


def inside(points, tris, direction):
    """Points inside the closed mesh `tris` (n, 3, 3) by one ray's parity (Moeller-Trumbore)."""
    a0, a1, a2 = tris[:, 0], tris[:, 1], tris[:, 2]
    e1, e2 = a1 - a0, a2 - a0
    d = np.array(direction, float)
    h = np.cross(d, e2)
    det = (e1 * h).sum(1)
    ok = np.abs(det) > 1e-9
    det = np.where(ok, det, 1)
    s = points[:, None, :] - a0[None]
    u = (s * h[None]).sum(2) / det[None]
    q = np.cross(s, e1[None])
    v = (q * d).sum(2) / det[None]
    t = (e2[None] * q).sum(2) / det[None]
    hit = ok[None] & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-6)
    return hit.sum(1) % 2 == 1


class Body:
    """Counts the vertices of a limb that lie inside another part, in a pose (majority of five ray parities)."""

    def __init__(self, model, sk):
        self.model = model
        self.mesh = animstudio.FastMesh(type('M', (), dict(m=model, skel=sk))())

    def world(self, pose):
        p = copy.deepcopy(pose)
        p[0] = [4096] * 3 + [0] * 6
        mats = mmd.bone_matrices(self.model, p)
        return mats, self.mesh.world(mats).astype(float)

    @staticmethod
    def count(mesh, mats, world, a_bones, b_bones, socket=None):
        tri = world[mesh.tri[np.isin(mesh.bone, a_bones)]]
        points = np.vstack([tri.reshape(-1, 3), tri.mean(1)])
        if socket is not None:             # the shoulder joint itself is built inside the torso
            joint = np.array(mats[socket], float)[:3, 3]
            points = points[np.linalg.norm(points - joint, axis=1) > 30]
        tris = world[mesh.tri[np.isin(mesh.bone, b_bones)]]
        votes = sum(inside(points, tris, d).astype(int) for d in DIRS)
        return int((votes >= 3).sum())

    def report(self, pose, only=None):
        mesh = self.mesh
        mats, world = self.world(pose)
        c = lambda a, b, s=None: self.count(mesh, mats, world, a, b, s)
        out = {}
        want = lambda k: only is None or k in only
        if want('legs'):
            out['legs'] = c(R_LEG[1:], L_LEG) + c(L_LEG[1:], R_LEG)
        if want('pelvis'):
            out['pelvis'] = c(R_LEG + L_LEG, (1,))
        for name, (shoulder, arm) in zip('RL', ARMS):
            if want('arm' + name):
                out['arm' + name] = c(arm[1:], (1, 2), shoulder) + c(arm[1:], R_LEG + L_LEG) + c(arm[1:], (10, 11, 12) if name == 'R' else (6, 7, 8))
        return out


def spin(pose, bone, degrees):
    """A turn about the z axis (front to back) of the bone's parent frame, put in front of its own rotation."""
    local = R.rot_of(pose[bone])
    new = R.m3mul(R.from_axis_angle([0, 0, 1], math.radians(degrees)), local)
    pose[bone][3:6] = [round(v) for v in mmd.matrix_euler(new, pose[bone][3:6])]


def apply(frames, plan):
    """The frames with each `bone: [(degrees, sign) per tick]` turn of the plan put on."""
    out = copy.deepcopy(frames)
    for bone, angles in plan.items():
        for tick, a in enumerate(angles):
            if abs(a) > 1e-9:
                spin(out[tick], bone, a)
    return out


def smooth_bump(need, margin, reach=2):
    """Periodic envelope of the needed angles: the largest need within two ticks, blurred, plus a margin where used."""
    n = len(need)
    sign = 1 if max(need) >= -min(need) else -1
    mag = [max(0.0, sign * v) for v in need]
    dil = [max(mag[(i + k) % n] for k in range(-reach, reach + 1)) for i in range(n)]
    ker = (1, 2, 3, 2, 1) if reach == 2 else (1, 2, 1)
    blur = [sum(w * dil[(i + k - reach) % n] for k, w in enumerate(ker)) / sum(ker) for i in range(n)]
    return [sign * (max(b, d * .9) + margin * min(1, max(b, d) / 3)) for b, d in zip(blur, dil)]


def limb_stage(body, frames, modes, key, notes, margin=MARGIN, reach=2):
    """One stage. `modes` is a list of {bone: factor} ways to clear a tick; the way that needs the smallest turn (degrees,
    about z, times each factor) is used there, in the same direction through the whole clip."""
    base = [body.report(f, (key,)) for f in frames]
    if not any(r[key] for r in base):
        return frames
    sign = None
    bones = sorted({b for m in modes for b in m})
    need = {b: [0.0] * len(frames) for b in bones}
    for i, f in enumerate(frames):
        if not base[i][key]:
            continue
        found = None
        for k in range(1, 61):
            for s in ((sign,) if sign else (1, -1)):
                for mi, mode in enumerate(modes):
                    g = copy.deepcopy(f)
                    for bone, factor in mode.items():
                        spin(g, bone, s * factor * k)
                    if body.report(g, (key,))[key] == 0:
                        found = (s, k, mode)
                        break
                if found:
                    break
            if found:
                break
        if not found:
            raise LookupError((key, i))
        sign = sign or found[0]
        for bone, factor in found[2].items():
            need[bone][i] = sign * factor * found[1]
    bump = {b: smooth_bump(need[b], margin, reach) if any(need[b]) else [0.0] * len(frames) for b in bones}
    for _ in range(40):                    # a tick the smoothing left inside the body grows until it is clear
        out = copy.deepcopy(frames)
        for bone, angles in bump.items():
            for i, a in enumerate(angles):
                if a:
                    spin(out[i], bone, a)
        bad = [i for i, f in enumerate(out) if body.report(f, (key,))[key]]
        if not bad:
            break
        for i in bad:
            for bone in bones:
                if bump[bone][i]:
                    bump[bone][i] += sign * 1.5 * (1 if bump[bone][i] * sign > 0 else 0)
    else:
        raise AssertionError(('did not clear', key, bad))
    notes[key] = dict(need={b: need[b] for b in bones}, degrees={b: [round(v, 1) for v in bump[b]] for b in bones})
    return out


def fix_slot(body, frames, notes):
    out = frames
    for name, elbow in zip('RL', (6, 10)):
        out = limb_stage(body, out, [{elbow: 1}], 'arm' + name, notes)
    # the legs: the hips spread (the left one turns the other way). The thigh tops overlap by construction, not counted.
    out = limb_stage(body, out, [{18: .5, 21: -.5}], 'legs', notes, margin=1.0, reach=1)
    return out


def _unit(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def twist_of(zero_dir, swing_before, world):
    """The turn about the bone's own axis a world rotation holds beyond the swing that points the bone where it points."""
    m = R.m3mul(R.m3t(swing_before), world)
    axis, angle = R.axis_angle(m)
    z = _unit(zero_dir)
    return angle if sum(axis[i] * z[i] for i in range(3)) >= 0 else -angle


def solve_leg(ref, bones, hip_at, goal, was):
    """World rotations of the thigh and the shin for a foot at `goal`, the knee bending toward the side it did, and the
    turn of each about its own axis kept. `was`: the original world positions (hip, knee, ankle) and rotations (thigh, shin)."""
    hip, knee, ankle = bones
    (hip0, knee0, ankle0), (thigh0, shin0) = was
    a = math.dist(ref[knee], ref[hip])
    b = math.dist(ref[ankle], ref[knee])
    delta = [goal[i] - hip_at[i] for i in range(3)]
    dist = min(math.sqrt(sum(v * v for v in delta)), a + b - .5)
    direction = _unit(delta)
    pole = [knee0[i] - hip0[i] for i in range(3)]
    dot = sum(pole[i] * direction[i] for i in range(3))
    pole = _unit([pole[i] - direction[i] * dot for i in range(3)])
    along = (a * a - b * b + dist * dist) / (2 * dist)
    height = math.sqrt(max(0.0, a * a - along * along))
    joint = [hip_at[i] + direction[i] * along + pole[i] * height for i in range(3)]
    goal = [hip_at[i] + direction[i] * dist for i in range(3)]
    zero_hip = [ref[knee][i] - ref[hip][i] for i in range(3)]
    zero_knee = [ref[ankle][i] - ref[knee][i] for i in range(3)]
    tw_hip = twist_of(zero_hip, R.swing(zero_hip, [knee0[i] - hip0[i] for i in range(3)]), thigh0)
    tw_knee = twist_of(zero_knee, R.swing(zero_knee, [ankle0[i] - knee0[i] for i in range(3)]), shin0)
    turn = lambda d, ang: R.from_axis_angle(_unit(d), ang)
    r_hip = R.m3mul(R.swing(zero_hip, [joint[i] - hip_at[i] for i in range(3)]), turn(zero_hip, tw_hip))
    r_knee = R.m3mul(R.swing(zero_knee, [goal[i] - joint[i] for i in range(3)]), turn(zero_knee, tw_knee))
    return r_hip, r_knee


def put(pose, bone, rotation):
    pose[bone][3:6] = [round(v) for v in mmd.matrix_euler(rotation, pose[bone][3:6])]


def hold_cape(frames, share):
    """The two cloth pieces that hang from the left thigh (bones 24 and 25) are rigid in the walk and the run, so they
    swing with the whole leg, up to twice the size of the cloth away from the chest, and leave the body whenever that
    leg strides. The thigh's turn reaches them at only `share` of its size: both their hanging point and their own
    turn (the pose and offset they have at the hip stay as they were)."""
    for f in frames:
        r_hip = R.rot_of(f[21])
        axis, angle = R.axis_angle(r_hip)
        softer = R.from_axis_angle(axis, angle * share)
        offset = f[24][6:9]
        carried = [sum(softer[i][j] * offset[j] for j in range(3)) for i in range(3)]
        f[24][6:9] = [round(sum(r_hip[j][i] * carried[j] for j in range(3))) for i in range(3)]
        put(f, 24, R.m3mul(R.m3mul(R.m3t(softer), r_hip), R.rot_of(f[24])))


def breathe(frames, deg):
    """The idle's life, in whole cycles of its 126 ticks (so the loop closes): two breaths (chest and shoulders lift, the
    wings and cloth trail them a little later), one slow look to either side with a nod, a sway of the arms against
    the weight shift. It is added to what the clip already does, so the held stretch is no longer a still picture."""
    n = len(frames)
    for t, f in enumerate(frames):
        ph = 2 * math.pi * t / n
        add = lambda bone, ch, amount: f[bone].__setitem__(ch, f[bone][ch] + amount * deg)
        b = math.sin(2 * ph)
        add(2, 3, 2.6 * b)
        add(2, 5, 1.8 * math.sin(ph + 1.0))
        add(3, 3, -1.2 * b)
        add(5, 5, -2.2 * b)
        add(9, 5, 2.2 * b)
        add(5, 3, 3.0 * math.sin(ph - .8))
        add(9, 3, -3.0 * math.sin(ph - .8))
        add(6, 3, 3.5 * math.sin(2 * ph - .5))
        add(10, 3, 3.5 * math.sin(2 * ph + .8))
        add(4, 4, 6.0 * math.sin(ph))
        add(4, 3, 2.0 * math.sin(2 * ph + 1.0))
        for bone, lag, amount in ((13, 1.0, 3.0), (15, 1.0, 3.0), (14, 1.6, 4.0), (16, 1.6, 4.0), (28, 1.2, 2.5), (24, 1.4, 3.0), (25, 2.0, 3.5)):
            add(bone, 3, amount * math.sin(2 * ph - lag))


def relax(model, sk, frames, spec):
    """The same clip with a calmer carriage, at the same timing: a smaller bob of the pelvis, the swinging foot lifted
    less (both legs solved again onto the same feet, which keep their ground contact and their turn), the forearms
    opened, the shoulders' swing wider and later than the legs'. `spec`: bob, lift (factors), elbow (centre degrees,
    factor), arm (factor of the shoulders' fore-aft swing), delay (ticks the arms trail the stride)."""
    n = len(frames)
    out = copy.deepcopy(frames)
    flat = []
    for f in frames:
        q = copy.deepcopy(f)
        q[0] = [4096] * 3 + [0] * 6
        flat.append(q)
    base = copy.deepcopy(flat[0])
    for b in range(1, NB):
        base[b][3:6] = [0, 0, 0]
    ref = R.world_pos(sk, base)
    rots = [R.world_rots(sk, q) for q in flat]
    pos = [R.world_pos(sk, q) for q in flat]
    ys = [f[1][7] for f in frames]
    mean = sum(ys) / n
    sway = [0.0] * n                      # the pelvis' sideways shift (the idle's weight shift)
    for t, f in enumerate(out):
        f[1][7] = round(mean + spec['bob'] * (ys[t] - mean))
    if spec.get('life'):
        for t, f in enumerate(out):
            ph = 2 * math.pi * t / n
            f[1][7] += round(-1.6 * math.sin(2 * ph))              # the body rises a little on each breath
            sway[t] = 5.0 * math.sin(ph + .4)
            f[1][6] += round(sway[t])
    # how far each sole's lowest point is above the ground, per tick (the sole rolls: the ankle's own height is not it)
    low = {}
    for ankle in (20, 23):
        verts = [v[:3] for v in model.tmd.obj_verts(sk[ankle][0])]
        row = []
        for q in flat:
            m = mmd.bone_matrices(model, q)[ankle]
            row.append(max(sum(m[1][i] * v[i] for i in range(3)) + m[1][3] for v in verts))
        low[ankle] = [max(row) - r for r in row]
    for t in range(n):
        dy = out[t][1][7] - frames[t][1][7]
        dx = out[t][1][6] - frames[t][1][6]
        rp = rots[t][1]
        for bones in ((18, 19, 20), (21, 22, 23)):
            hip, knee, ankle = bones
            hip_at = [pos[t][hip][0] + dx, pos[t][hip][1] + dy, pos[t][hip][2]]
            goal = list(pos[t][ankle])
            goal[1] += (1 - spec['lift']) * low[ankle][t]
            goal[0] += (1 if pos[t][ankle][0] > pos[t][1][0] else -1) * spec.get('widen', 0)   # feet further apart
            r_hip, r_knee = solve_leg(ref, bones, hip_at, goal, ((pos[t][hip], pos[t][knee], pos[t][ankle]), (rots[t][hip], rots[t][knee])))
            put(out[t], hip, R.m3mul(R.m3t(rp), r_hip))
            put(out[t], knee, R.m3mul(R.m3t(r_hip), r_knee))
            put(out[t], ankle, R.m3mul(R.m3t(r_knee), rots[t][ankle]))
    # arms
    deg = 4096 / 360
    centre, k = spec['elbow']
    for bone in (5, 6, 7, 9, 10, 11):
        for ch in (3, 4, 5):
            series = [f[bone][ch] for f in out]
            lag = spec['delay']
            lo = math.floor(lag)
            new = []
            for t in range(n):
                x0 = series[(t - lo) % n]
                x1 = series[(t - lo - 1) % n]
                new.append(x0 + (x1 - x0) * (lag - lo))
            for t in range(n):
                out[t][bone][ch] = new[t]
    for shoulder in (5, 9):
        mid = sum(f[shoulder][3] for f in out) / n
        for f in out:
            f[shoulder][3] = mid + spec['arm'] * (f[shoulder][3] - mid)
    for elbow in (6, 10):
        for f in out:
            x = f[elbow][3] / deg
            x -= 360 * math.floor(x / 360 + 1)            # into -360..0: a bent elbow
            f[elbow][3] = (centre + k * (x - centre)) * deg
    if spec.get('life'):
        breathe(out, deg)
    for f in out:
        for bone in range(1, NB):
            f[bone][3:6] = [round(v) for v in f[bone][3:6]]
    return out


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


def build(data, sk):
    if hashlib.sha256(data).hexdigest() != SOURCE or len(sk) != NB:
        raise ValueError('Valkyrimon limbs require the 30-bone import as `edit.py get 255` gave it before this change')
    model = _parse(data, sk)
    body = Body(model, sk)
    result = copy.deepcopy(model)
    checks = []
    for slot in SLOTS:
        frames, loop, events = original(model, slot)
        notes = {}
        if slot in CARRIAGE:
            frames = relax(model, sk, frames, CARRIAGE[slot])
        fixed = fix_slot(body, frames, notes)
        if CARRIAGE.get(slot, {}).get('cape') is not None:
            hold_cape(fixed, CARRIAGE[slot]['cape'])
        program = mmd.encode_anim(fixed, NB, loop, events, tol=TOLERANCE, repeats=False)
        index = model.anims.table[slot]
        if slot == 0:                      # its program is shared with slot 33: only the field idle changes
            index = len(result.anims.anims)
            result.anims.anims.append(program)
            result.anims.table[slot] = index
        else:
            assert sum(1 for v in model.anims.table if v == index) == 1
            result.anims.anims[index] = program
        checks.append(dict(slot=slot, ticks=len(frames), stages=notes))
    for animation in result.anims.anims:
        animation.tail = b''
    output = result.build()
    effective = _parse(output, sk)
    assert effective.tmd.build() == model.tmd.build()
    changed = changed_programs(model, effective)
    return output, dict(species=SPECIES, source_sha256=SOURCE, output_sha256=hashlib.sha256(output).hexdigest(),
                        changed_slots=changed, checks=checks, storage=motionstorage.require(output, NB))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    sk = json.loads((ROOT / 'content/species/255-valkyrimon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), sk)
    a.out.write_bytes(data)
    if a.report:
        a.report.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({k: proof[k] for k in ('changed_slots',)}), proof['storage']['resident_bytes'], len(data))
    for c in proof['checks']:
        print(c['slot'], {k: {b: max(map(abs, a)) for b, a in v['degrees'].items()} for k, v in c['stages'].items()})


if __name__ == '__main__':
    main()
