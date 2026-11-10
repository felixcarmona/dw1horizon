"""Digmon's run, made from its own walk (a quicker cycle, longer strides, a lean, a flight in every step), and its
claws and drills kept out of the floor.

Offline authoring only: player builds replay the pinned plain delta. Run with --source (the reviewed field model)
and --out, then store the result with tools/models/edit.py put 193.

The reviewed run was the walk's 20-tick cycle with each pose pushed a little further and twice the travel, so on
screen it read as the walk played fast. The run now takes the walk's own poses (the hop-step, the swinging drills and
claws: Digmon's character) and:

- plays the cycle in TICKS ticks instead of 20, at the same field speed as before (the root travels SPEED a tick),
  so each stride is 1.4 times the walk's;
- swings the thighs STRIDE times as far from their mean pitch;
- leans the upper body LEAN forward, the drills and head with it;
- sets the body's height so a foot is on the floor while it pushes and both feet are off it around each of the
  walk's two hops: the lowest claw rises on a smooth arc to FLIGHT over the floor there and sits CLEAR over it
  otherwise.

In the walk, condition walk and run the clip's long toe claws pointed down through the floor (up to 77 units) in
almost every tick, and the right arm's drill dug into it as the arm swung. The walks keep their timing and motion;
in all three the ankles and toes turn toward their standing turn as far as keeps the claws over the floor (eased
over the ticks, the body rising only where that is not enough), and an arm swings up at the shoulder just enough to
keep its drill ARM_CLEAR over the floor. Every check is made at the ticks and at the 60 fps thirds between them.

The mesh and every other program stay exact.
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
import retarget as R  # noqa: E402
import mmd  # noqa: E402
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402
from motiontailspace import interpolate_pose  # noqa: E402

SOURCE = 'c8d721fd0030ee49c74c03776b86b09ab41dfc28aa36cd09dfa0ac33e502187c'
SPECIES = 193
NB = 26
WALK, RUN = 2, 4
BODY, CHEST = 1, 10
HIPS = (2, 6)
FEET = (4, 5, 8, 9)
LEGS = ((4, 5), (8, 9))  # ankle, toe
SLOTS = (2, 3, 4)
STEPS = 20
ARMS = ((14, 15, 16), (17, 18, 19))   # shoulder, forearm, drill
ARM_CLEAR = 4
ARM_STEP = 20           # shoulder pitch tried, 1/4096 turn (negative raises the arm)
ARM_EASE = 60           # how fast the raise comes and goes, a tick
TICKS = 14
SPEED = 37.6
STRIDE = 1.2
LEAN = 180              # pitch of the chest (1/4096 turn): forward
FLIGHT = 18
CLEAR = 0.5
HOPS = (0.3, 0.8)       # the walk's two hops (its ticks 6 and 16 of 20), as a part of the cycle
WINDOW = 0.13           # half the airborne part of each step, as a part of the cycle


def identity_root(pose):
    p = [list(b) for b in pose]
    p[0] = [4096] * 3 + [0] * 6
    return p


def lowest(model, skeleton, pose, bones=FEET):
    mats = mmd.bone_matrices(model, identity_root(pose))
    return max(sum(mats[b][1][j] * v[j] for j in range(3)) + mats[b][1][3]
               for b in bones for v in model.tmd.obj_verts(skeleton[b][0]))


def _blend(flat, own, u):
    return mmd.quat_matrix(mmd._slerp(mmd.quat(*mmd.matrix_euler(flat)), mmd.quat(*mmd.matrix_euler(own)), u))


def _turn_leg(skeleton, pose, leg, flat, own, u, history):
    for b in leg:
        parent = R.world_rots(skeleton, pose)[skeleton[b][1]]
        angles = mmd.matrix_euler(R.m3mul(R.m3t(parent), _blend(flat[b], own[b], u)), history.get(b))
        history[b] = angles
        pose[b][3:6] = [round(v) for v in angles]


def flat_feet(model, skeleton, frames, flat):
    """The ankle and toe of each foot turned from the clip's turn toward the standing turn, only as far as keeps the
    claws over the floor at the tick (0 = standing, 1 = the clip's own), eased over the neighbouring ticks."""
    n = len(frames) - 1
    owns = [R.world_rots(skeleton, identity_root(p)) for p in frames]
    keep = {}
    for leg in LEGS:
        amounts = []
        for pose, own in zip(frames[:n], owns):
            best = 0.
            for step in range(STEPS, -1, -1):
                trial = identity_root(pose)
                _turn_leg(skeleton, trial, leg, flat, own, step / STEPS, {})
                if lowest(model, skeleton, trial, leg) <= -CLEAR:
                    best = step / STEPS
                    break
            amounts.append(best)
        eased = [min(amounts[(i - 1) % n], amounts[i], amounts[(i + 1) % n]) for i in range(n)]
        eased = [min(amounts[i], (eased[(i - 1) % n] + 2 * eased[i] + eased[(i + 1) % n]) / 4) for i in range(n)]
        keep[leg] = eased + eased[:1]
    out = []
    for i, (pose, own) in enumerate(zip(frames, owns)):
        new = copy.deepcopy(pose)
        history = {}
        for leg in LEGS:
            _turn_leg(skeleton, new, leg, flat, own, keep[leg][i], history)
        out.append(new)
    return out, keep


def ground(model, skeleton, frames, target):
    """Moves the body so the lowest claw is target(tick) over the floor, then raises it where a 60 fps third between
    two ticks would still touch the floor. target None: the body only rises, by what a dipping claw needs, eased."""
    n = len(frames) - 1
    gap = [lowest(model, skeleton, p) for p in frames[:n]]
    if target:
        shift = [-target(t) - gap[t] for t in range(n)]
    else:
        need = [min(0., -CLEAR - g) for g in gap]
        shift = [min(need[j] + 2 * min((i - j) % n, (j - i) % n) for j in range(n)) for i in range(n)]
    for _ in range(6):
        moved = [copy.deepcopy(p) for p in frames[:n]]
        for p, d in zip(moved, shift):
            p[BODY][7] += d
        moved.append(moved[0])
        deeper = False
        for t in range(n):
            for alpha in (1365, 2730):
                between = interpolate_pose([[round(x) for x in b] for b in moved[t]],
                                           [[round(x) for x in b] for b in moved[t + 1]], alpha)
                dip = lowest(model, skeleton, between) + CLEAR
                if dip > 0.25:
                    shift[t] -= dip
                    shift[(t + 1) % n] -= dip
                    deeper = True
        if not deeper:
            break
    shift.append(shift[0])
    out = [copy.deepcopy(p) for p in frames]
    for p, d in zip(out, shift):
        p[BODY][7] += d
    return out, shift


def height(phase):
    """How far the lowest claw is over the floor at this part of the cycle."""
    up = 0.
    for hop in HOPS:
        d = abs((phase - hop + 0.5) % 1 - 0.5)
        if d < WINDOW:
            up = max(up, FLIGHT * math.cos(math.pi / 2 * d / WINDOW) ** 2)
    return up + CLEAR


def raise_arms(model, skeleton, frames):
    """Each arm swung up at the shoulder just as far as keeps its drill ARM_CLEAR over the floor at the ticks and the
    60 fps thirds, the raise eased in and out over the neighbouring ticks."""
    n = len(frames) - 1
    raised = {arm: [0.] * n for arm in ARMS}

    def apply(poses):
        out = [copy.deepcopy(p) for p in poses]
        for arm, amount in raised.items():
            for i, p in enumerate(out):
                p[arm[0]][3] -= amount[i % n]
        return out
    for _ in range(40):
        moved = apply(frames)
        deeper = False
        for arm, amount in raised.items():
            for t in range(n):
                for alpha in (0, 1365, 2730):
                    between = interpolate_pose([[round(x) for x in b] for b in moved[t]],
                                               [[round(x) for x in b] for b in moved[t + 1]], alpha)
                    if lowest(model, skeleton, between, arm) > -ARM_CLEAR:
                        for k in (t, (t + 1) % n) if alpha else (t,):
                            amount[k] += ARM_STEP
                        deeper = True
                        break
            eased = [max(amount[j] - ARM_EASE * min((i - j) % n, (j - i) % n) for j in range(n)) for i in range(n)]
            amount[:] = eased
        if not deeper:
            break
    return apply(frames), {arm[0]: round(max(a)) for arm, a in raised.items()}


def run_cycle(walk):
    n = len(walk) - 1
    travel = abs(walk[n][0][8] - walk[0][0][8])
    out = []
    for t in range(TICKS + 1):
        u = t * n / TICKS
        i = min(int(u), n - 1)
        pose = interpolate_pose(walk[i], walk[i + 1], round((u - i) * 4096))
        pose = [list(map(float, b)) for b in pose]
        pose[0][8] = pose[0][8] * (SPEED * TICKS) / travel
        out.append(pose)
    for hip in HIPS:
        mean = sum(p[hip][3] for p in out[:TICKS]) / TICKS
        for p in out:
            p[hip][3] = mean + STRIDE * (p[hip][3] - mean)
    for p in out:
        p[CHEST][3] += LEAN
    return out


def build(data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError('requires the reviewed Digmon field model')
    mmd.exe().add_type(SPECIES, skeleton)
    model = mmd.MMD.parse(data, NB)
    model.type = SPECIES
    rest = animsheet.slot_frames(model, NB, 0)[0][0]
    flat = {b: r for b, r in enumerate(R.world_rots(skeleton, identity_root(rest)))}
    walk, walk_loop, _ = animsheet.slot_frames(model, NB, WALK)
    assert walk_loop == 0
    mmd.close_loop(walk, walk_loop)
    result = copy.deepcopy(model)
    checks = []
    for slot in SLOTS:
        frames, loop, events = animsheet.slot_frames(model, NB, slot)
        mmd.close_loop(frames, loop)
        before = [round(lowest(model, skeleton, p)) for p in frames[:-1]]
        if slot == RUN:
            frames = run_cycle(walk)
            # the two footfall sounds keep their place in the step
            events = [(round(t * TICKS / (len(walk) - 1)) % TICKS, k, c) for t, k, c in events]
        frames, keep = flat_feet(model, skeleton, frames, flat)
        n = len(frames) - 1
        frames, shift = ground(model, skeleton, frames, (lambda t: height(t / n)) if slot == RUN else None)
        frames, arms = raise_arms(model, skeleton, frames)
        frames = [[[round(x) for x in bone] for bone in pose] for pose in frames]
        mmd.close_loop(frames, loop)
        sounds = [(t, k, c) for t, k, c in events if k == 'sound']
        # a program of its own: any other slot that shared the reviewed one keeps it
        result.anims.anims.append(mmd.encode_anim(frames, NB, loop, sounds, tol=1, repeats=False))
        result.anims.table[slot] = len(result.anims.anims) - 1
        checks.append(dict(slot=slot, ticks=n, travel=frames[n][0][8] - frames[0][0][8],
                           lowest_claw_before=before, lowest_claw=[round(lowest(model, skeleton, p)) for p in frames[:n]],
                           clip_foot_turn_kept=[round(min(k), 2) for k in keep.values()],
                           body_shift=[round(min(shift), 1), round(max(shift), 1)], shoulder_raise=arms))
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
    skeleton = json.loads((ROOT / 'content/species/193-digmon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof, indent=2) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
