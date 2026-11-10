"""Zudomon's upper body on the beat of its legs, so the heavy walrus walks and runs as one animal.

Offline authoring only: player builds replay the pinned plain delta. Run with --source (the reviewed field model)
and --out, then store the result with tools/models/edit.py put 219.

The reviewed walk, condition walk and run took their legs from a gait solver (a step every 15, 22.5 and 12 ticks)
but left the upper body playing the idle's slow 96-tick performance, squeezed to the clip's length: the hammer arm
swung 79 degrees once per loop, the head lifted and thrashed once per loop, the chest rocked once per loop, none of
it tied to the feet. The legs and the upper body were on different beats (one upper beat per 4 steps in the walk,
per 8 in the run) and in no fixed phase, so the halves read as two animals.

The three clips keep their legs, root travel, loop length and footstep sounds. Their chest, neck, head, arms,
hammer and tail are replaced by the idle's mean carry pose plus a small movement locked to the step phase (theta,
0 when the right foot is furthest forward, so every beat divides the loop evenly and the loop is seamless):

- pelvis yaws with the leading hip and rolls a little with the weight over the planted foot; the hips turn the
  opposite way so the feet stay where the leg solver put them (the pelvis, chest and head counter-rotate);
- the chest turns the other way, later, and leans over the planted foot; the neck and head counter it, later
  still, and nod once a step;
- the free right arm swings against its own leg; the hammer arm swings against the left leg with a third of the
  reach, and the hammer lags it (a pendulum, later than the hands) so the weight arrives after the hand;
- the tail sways against the hips with a growing delay along its length.
The run adds a forward lean, the condition walk droops the head and shrinks the movement.
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
import numeric as np  # noqa: E402
import animsheet  # noqa: E402
import mmd  # noqa: E402
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402
from tools.models.field_animations.articulation import replace_channels  # noqa: E402
from tools.models.field_animations.war_greymon import rotation, set_rotation  # noqa: E402

SOURCE = '03d44b9f766ce43662aca754997dc955346d035a7d044753bba19c93e2397a7a'
SPECIES = 219
NB = 22
TOL = 7
SLOTS = (2, 3, 4)
PELVIS, CHEST, NECK, HEAD, JAW = 11, 1, 2, 3, 4
R_ARM, L_ARM = (5, 6, 7), (8, 9, 10)
TAIL = (12, 13, 14)
HIPS = (15, 18)
HAMMER, HAMMER_CLEAR = 10, -8
RIGHT_FOOT, PELVIS_Z = 17, 11
UPPER = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 14)
CHANNELS = {(b, c) for b in UPPER + (PELVIS,) + HIPS for c in (3, 4, 5)}
# beats of the right foot per loop: the walk and condition walk 4 steps, the run 8
BEATS = {2: 4, 3: 4, 4: 8}
# degrees: pelvis yaw, pelvis roll, chest counter-yaw, chest roll, free arm, hammer arm, forward lean, head droop
PARAM = {
    2: dict(yaw=4.0, roll=1.6, chest_yaw=7.0, chest_roll=2.6, arm=15.0, heavy=6.0, lean=0.0, droop=0.0, bob=1.4, fine=1.0, tip=1.0),
    3: dict(yaw=2.4, roll=1.0, chest_yaw=4.0, chest_roll=1.8, arm=8.0, heavy=3.5, lean=5.0, droop=9.0, bob=1.0, fine=1.0, tip=1.0),
    4: dict(yaw=5.5, roll=2.0, chest_yaw=9.0, chest_roll=2.6, arm=24.0, heavy=9.0, lean=8.0, droop=0.0, bob=2.2, fine=0.0, tip=0.0),
}


def _world(model, pose):
    p = copy.deepcopy(pose)
    p[0] = [4096] * 3 + [0] * 6
    return np.array(mmd.bone_matrices(model, p))


def _phase(model, frames, beats):
    """Phase of the right foot's fore-aft swing: theta = 0 when it is furthest forward (towards -z)."""
    n = len(frames) - 1
    lead = []
    for f in frames[:n]:
        w = _world(model, f)
        lead.append(-(w[RIGHT_FOOT, 2, 3] - w[PELVIS_Z, 2, 3]))
    lead = np.array(lead)
    t = 2 * math.pi * beats * np.arange(n) / n
    a, b = np.linalg.lstsq(np.column_stack([np.cos(t), np.sin(t)]), lead - lead.mean(), rcond=None)[0]
    return math.atan2(b, a)


def _idle_mean(model):
    fs, _, _ = animsheet.slot_frames(model, NB, 0)
    n = len(fs) - 1
    arr = np.array(fs[:n], float)
    return {b: [float(arr[:, b, c].mean()) for c in (3, 4, 5)] for b in UPPER}


def _author(model, sk, slot, base, lift=0.0):
    frames, loop, events = animsheet.slot_frames(model, NB, slot)
    assert loop == 0
    n = len(frames) - 1
    K = BEATS[slot]
    q = PARAM[slot]
    phi = _phase(model, frames, K)
    out = []
    for t, src in enumerate(frames):
        # the loop's last frame repeats the first so the clip closes exactly
        tt = t % n
        th = 2 * math.pi * K * tt / n - phi
        c = lambda lag=0.0, k=1: math.cos(k * (th - lag))
        s = lambda lag=0.0, k=1: math.sin(k * (th - lag))
        p = copy.deepcopy(src)
        hist = {}
        # pelvis: yaw with the leading hip, roll with the weight; hips turn back so the feet stay put
        wp = _world(model, p)
        old = wp[PELVIS, :3, :3]
        d = rotation([0, q['yaw'] * c(), -q['roll'] * s()])
        set_rotation(p, PELVIS, d @ np.array(mmd.rot_matrix(*p[PELVIS][3:6])), hist)
        new = d @ old
        for hip in HIPS:
            hw = old @ np.array(mmd.rot_matrix(*src[hip][3:6]))
            set_rotation(p, hip, new.T @ hw, hist)
        # upper body: the idle's carry pose, then the step-locked movement in each parent's frame
        def put(b, dx=0.0, dy=0.0, dz=0.0):
            base_r = np.array(mmd.rot_matrix(*base[b]))
            set_rotation(p, b, rotation([dx, dy, dz]) @ base_r, hist)
        put(CHEST, dx=q['lean'] + q['bob'] * c(0.6, 2), dy=-q['chest_yaw'] * c(0.25), dz=q['chest_roll'] * s(0.3))
        put(NECK, dx=-0.5 * q['lean'] + 0.5 * q['droop'] + 0.6 * q['fine'] * q['bob'] * c(1.0, 2), dy=0.55 * q['chest_yaw'] * c(0.5), dz=-0.5 * q['chest_roll'] * s(0.5))
        put(HEAD, dx=-0.5 * q['lean'] + 0.5 * q['droop'] - 0.5 * q['fine'] * q['bob'] * c(1.4, 2), dy=0.45 * q['chest_yaw'] * c(0.7), dz=-0.4 * q['chest_roll'] * s(0.7))
        put(JAW)
        a, h = q['arm'], q['heavy']
        put(R_ARM[0], dx=a * c(0.2))
        put(R_ARM[1], dx=0.35 * a * c(0.9) - 0.15 * a)
        put(R_ARM[2], dx=0.2 * a * c(1.4))
        put(L_ARM[0], dx=-h * c(0.35), dz=lift)
        put(L_ARM[1], dx=-0.5 * h * c(0.9), dz=0.5 * lift)
        put(L_ARM[2], dx=-0.9 * h * c(1.6))
        put(TAIL[0], dy=-0.6 * q['yaw'] * c(0.4), dx=0.5 * q['fine'] * q['bob'] * c(0.8, 2))
        put(TAIL[1], dy=-0.9 * q['yaw'] * c(0.9), dx=0.6 * q['fine'] * q['bob'] * c(1.2, 2))
        put(TAIL[2], dy=-1.3 * q['tip'] * q['yaw'] * c(1.4), dx=0.8 * q['fine'] * q['bob'] * c(1.6, 2))
        out.append(p)
    # integer channels: the last frame closes onto the first
    out[-1][1:] = copy.deepcopy(out[0][1:])
    out[-1][0] = copy.deepcopy(frames[-1][0])
    out = [[[round(x) for x in bone] for bone in pose] for pose in out]
    return out, events, loop, dict(slot=slot, ticks=n, beats=K, phase_deg=round(math.degrees(phi), 1), hammer_lift_deg=lift)


def _hammer_low(model, sk, frames):
    """Lowest point of the hammer (y down, the floor is 0) over the clip, at the ticks."""
    verts = np.array(model.tmd.obj_verts(sk[HAMMER][0]))[:, :3]
    low = -1e9
    for f in frames[:-1]:
        w = _world(model, f)
        low = max(low, float((verts @ w[HAMMER, :3, :3].T + w[HAMMER, :3, 3])[:, 1].max()))
    return low


def _author_clear(model, sk, slot, base):
    """The hammer arm's carry, lifted by the least angle that keeps the hammer head off the floor all clip."""
    for lift in range(0, 41, 2):
        result = _author(model, sk, slot, base, lift)
        low = _hammer_low(model, sk, result[0])
        if low <= HAMMER_CLEAR:
            return result[:3] + (dict(result[3], hammer_lowest=round(low, 1)),)
    raise ValueError('the hammer cannot be kept off the floor')


def build(data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError('requires the reviewed Zudomon field model')
    mmd.exe().add_type(SPECIES, skeleton)
    model = mmd.MMD.parse(data, NB)
    model.type = SPECIES
    base = _idle_mean(model)
    result = copy.deepcopy(model)
    checks = []
    for slot in SLOTS:
        frames, events, loop, info = _author_clear(model, skeleton, slot, base)
        # the slot's own program is replaced in place, so the resident animation buffer stays within its budget
        index = model.anims.table[slot]
        assert sum(1 for v in model.anims.table if v == index) == 1
        result.anims.anims[index] = replace_channels(model.anims.anims[index], frames, loop, NB, CHANNELS, tolerance=TOL)
        checks.append(info)
    output = result.build()
    effective = mmd.MMD.parse(output, NB)
    effective.type = SPECIES
    assert effective.tmd.build() == model.tmd.build()
    changed = changed_programs(model, effective)
    assert set(changed) <= set(SLOTS), changed
    return output, dict(source_sha256=SOURCE, output_sha256=hashlib.sha256(output).hexdigest(), changed_slots=changed,
                        checks=checks, storage=motionstorage.require(output, NB))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/219-zudomon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof, indent=2) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
