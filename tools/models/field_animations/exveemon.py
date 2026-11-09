"""ExVeemon's field clips with a calmer tail and legs that stay out of the body.

Offline authoring only: player builds replay the pinned plain delta. Run with --source (the reviewed field model,
content/models/authoring/native-polish/194.json's output) and --out, then store the result with
tools/models/edit.py put 194.

The clips themselves stay: the same timing, root travel, body and arm motion. What changes:

- The tail swung its tip about 200 units from side to side and 150 up and down in the idle, walk, condition walk
  and run. Each tail bone now turns only TAIL of the way from its mean turn in that clip, so the tail still sways
  and follows the steps, at about half the size.
- In the walk and condition walk the swinging ankle rose almost to the hip, the thigh flipped over in one tick (up to
  124 degrees) and the knee went up through the belly. In the walk, condition walk and run each leg is solved again
  onto its own ankle with the knee forward and out to its own side (KNEE), the ankle never folded closer to the hip
  than FOLD of the leg, and in the walks the ankle rises at most LIFT of the leg over where it stands. A lowered foot
  turns toward its standing turn by as much as its lift was taken away, so its claws stay out of the floor.
- The condition walk dragged its planted feet up to four and a half times the body's speed: each foot now moves
  PLANT of the way to staying on its footprint through the stance, the swing keeping its path.
- In the walks the body moves down (or, where a foot would touch the floor, up) to keep the lowest claw just over
  the floor at the ticks and the 60 fps thirds, eased over the ticks.

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
import legik  # noqa: E402
import mmd  # noqa: E402
import motionsecondary  # noqa: E402
import motionstorage  # noqa: E402
import retarget as R  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402
from motiontailspace import interpolate_pose  # noqa: E402

SOURCE = 'dcb6ccebfb46c1bd3c4d0dd1efc72470f4f5ef11cc0795d1fd1fcc377bfb6cc2'
SPECIES = 194
NB = 27
TAIL_BONES = (24, 25, 26)
TAIL = 0.35
LEGS = ((18, 19, 20), (21, 22, 23))   # thigh (at the hip), shin (at the knee), foot (at the ankle)
FEET = (20, 23)
TAIL_SLOTS = (0, 2, 3, 4)
LEG_SLOTS = (2, 3, 4)
FOLD = 0.4
KNEE = {18: [0.35, 0.4, -1], 21: [-0.35, 0.4, -1]}   # forward and out to the leg's own side
LIFT = {2: 0.45, 3: 0.3}   # of the leg, per slot: the condition walk shuffles
CLEAR = 0.5
EASE = 3
GROUNDED = (2, 3)
PLANTED = (3,)
STANCE = 0.35
PLANT = 0.6

def identity_root(pose):
    p = [list(b) for b in pose]
    p[0] = [4096] * 3 + [0] * 6
    return p


def calm_tail(frames):
    """Each tail bone turns TAIL of the way from its mean local turn in the clip."""
    out = [copy.deepcopy(p) for p in frames]
    for b in TAIL_BONES:
        qs = [mmd.quat(*p[b][3:6]) for p in frames]
        ref = qs[0]
        aligned = [q if sum(a * c for a, c in zip(q, ref)) >= 0 else [-v for v in q] for q in qs]
        mean = [sum(q[i] for q in aligned[:-1]) for i in range(4)]
        norm = math.sqrt(sum(v * v for v in mean))
        mean = [v / norm for v in mean]
        history = None
        for pose, q in zip(out, aligned):
            angles = mmd.matrix_euler(mmd.quat_matrix(mmd._slerp(mean, q, TAIL)), history)
            history = angles
            pose[b][3:6] = [round(v) for v in angles]
    return out


def lowest(model, skeleton, pose, bones):
    mats = mmd.bone_matrices(model, identity_root(pose))
    return max(sum(mats[b][1][j] * v[j] for j in range(3)) + mats[b][1][3]
               for b in bones for v in model.tmd.obj_verts(skeleton[b][0]))


def planted_ankles(model, skeleton, frames):
    """{(tick, foot): ankle z in the root's frame} that keeps each foot still on the ground through its stance (the
    ticks its ankle is within STANCE of its lowest); the swing keeps its path, eased from one correction to the next."""
    n = len(frames) - 1
    travel = frames[n][0][8] - frames[0][0][8]
    assert all(p[0][3:6] == frames[0][0][3:6] for p in frames)
    out = {}
    for foot in FEET:
        pos = [R.world_pos(skeleton, identity_root(p))[foot] for p in frames[:n]]
        ys = [v[1] for v in pos]
        world = [v[2] + frames[i][0][8] for i, v in enumerate(pos)]
        lo, hi = max(ys), min(ys)
        stance = [ys[i] > lo - STANCE * (lo - hi) for i in range(n)]
        start = next(i for i in range(n) if stance[i] and not stance[i - 1])
        runs, i = [], start
        while True:   # the stance runs around the loop, each [first, last] tick, unwrapped past start
            j = i
            while stance[(j + 1) % n] and j + 1 < start + n:
                j += 1
            runs.append((i, j))
            k = j + 1
            while k < start + n and not stance[k % n]:
                k += 1
            if k >= start + n:
                break
            i = k
        def z(t):
            return world[t % n] + travel * (t // n)
        prints = [z((a + b) // 2) for a, b in runs]
        for r, (a, b) in enumerate(runs):
            for t in range(a, b + 1):
                out[(t % n, foot)] = prints[r] + travel * -(t // n)
            # the swing keeps its own path, shifted by the stance corrections either side of it
            na = runs[(r + 1) % len(runs)][0] + (n if r + 1 == len(runs) else 0)
            after = prints[r] - z(b)
            before = prints[(r + 1) % len(runs)] + (travel if r + 1 == len(runs) else 0) - z(na)
            for t in range(b + 1, na):
                u = (t - b) / (na - b)
                u = u * u * (3 - 2 * u)
                out[(t % n, foot)] = z(t) + after + (before - after) * u + travel * -(t // n)
        for t in range(n):
            out[(t, foot)] -= frames[t][0][8]
        out[(n, foot)] = out[(0, foot)]
    return out


def resolve_legs(skeleton, frames, reference, lift, planted=None):
    """The legs solved again onto their own ankles, knees forward and out, never folded tighter than FOLD."""
    rp = R.world_pos(skeleton, identity_root(reference))
    rr = R.world_rots(skeleton, identity_root(reference))
    out, lowered = [], 0.
    history = {}
    heights = {foot: [R.world_pos(skeleton, identity_root(p))[foot][1] for p in frames] for foot in FEET}
    standing = {foot: max(h) for foot, h in heights.items()}
    # a lowered ankle turns its foot toward the foot's turn where it stands, as much as its lift was taken away
    flat = {foot: R.world_rots(skeleton, identity_root(frames[h.index(max(h))]))[foot] for foot, h in heights.items()}
    for tick, pose in enumerate(frames):
        new = copy.deepcopy(pose)
        base = identity_root(pose)
        pos, rots = R.world_pos(skeleton, base), R.world_rots(skeleton, base)
        for hip, knee, foot in LEGS:
            l1 = legik.norm(legik.sub(rp[knee], rp[hip]))
            l2 = legik.norm(legik.sub(rp[foot], rp[knee]))
            origin, target = pos[hip], list(pos[foot])
            if planted:
                target[2] += PLANT * (planted[(tick, foot)] - target[2])
            low = target[1]
            if lift:
                # the swinging ankle rises at most LIFT of the leg over the height it stands at
                low = max(low, standing[foot] - lift * (l1 + l2))
            fold = FOLD * (l1 + l2)
            horizontal = (target[0] - origin[0]) ** 2 + (target[2] - origin[2]) ** 2
            low = max(low, origin[1] + math.sqrt(max(0., fold ** 2 - horizontal)))
            lowered = max(lowered, low - target[1])
            target[1] = low
            kn, ac = legik.solve(origin, target, l1, l2, KNEE[hip])
            hr, kr = motionsecondary.native_plane_rotations(
                [rp[b] for b in (hip, knee, foot)], [origin, kn, ac], [rr[hip], rr[knee]])
            turn = rots[foot]
            if low > pos[foot][1]:
                u = min(1., (low - pos[foot][1]) / max(1., standing[foot] - pos[foot][1]))
                a, b = mmd.quat(*mmd.matrix_euler(turn)), mmd.quat(*mmd.matrix_euler(flat[foot]))
                turn = mmd.quat_matrix(mmd._slerp(a, b, u))
            for bone, world in ((hip, hr), (knee, kr), (foot, turn)):
                parent = R.world_rots(skeleton, identity_root(new))[skeleton[bone][1]]
                angles = mmd.matrix_euler(R.m3mul(R.m3t(parent), world), history.get(bone))
                history[bone] = angles
                new[bone][3:6] = [round(v) for v in angles]
        out.append(new)
    return out, lowered


def build(data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError('requires the reviewed ExVeemon field model')
    mmd.exe().add_type(SPECIES, skeleton)
    model = mmd.MMD.parse(data, NB)
    model.type = SPECIES
    reference = animsheet.slot_frames(model, NB, 2)[0][0]
    result = copy.deepcopy(model)
    checks, done = [], {}
    for slot in TAIL_SLOTS:
        index = model.anims.table[slot]
        if index in done:
            continue
        frames, loop, events = animsheet.slot_frames(model, NB, slot)
        mmd.close_loop(frames, loop)
        fixed = calm_tail(frames)
        lowered = lift = ground = 0.
        if slot in LEG_SLOTS:
            planted = planted_ankles(model, skeleton, fixed) if slot in PLANTED else None
            fixed, lowered = resolve_legs(skeleton, fixed, reference, LIFT.get(slot), planted)
            # the body sits on its feet: in the walks the reviewed clip hovered up to 22 units over the floor, and a
            # lowered ankle under a turned foot may dip; each tick the body moves to put the lowest claw CLEAR over the
            # floor there and at the 60 fps thirds around it, eased to at most EASE a tick (the run only rises)
            n = len(fixed) - 1
            gap = [-1e9] * n
            for i in range(n):
                for alpha in (0, 1365, 2730, 4096):
                    floor = lowest(model, skeleton, interpolate_pose(fixed[i], fixed[i + 1], alpha), FEET)
                    for k in (i, (i + 1) % n):
                        gap[k] = max(gap[k], floor)
            room = [-g - CLEAR if slot in GROUNDED else min(0., -g - CLEAR) for g in gap]
            shift = [min(room[j] + EASE * min((i - j) % n, (j - i) % n) for j in range(n)) for i in range(n)]
            shift.append(shift[0])
            for pose, down in zip(fixed, shift):
                pose[17][7] += down
            lift = -min(shift)
            lowered = max(lowered, 0.)
            ground = max(shift)
        fixed = [[[round(x) for x in bone] for bone in pose] for pose in fixed]
        mmd.close_loop(fixed, loop)
        sounds = [(t, k, c) for t, k, c in events if k == 'sound']
        # rewritten in place: every slot that shares the program (slot 33 plays the idle) keeps sharing it
        result.anims.anims[index] = mmd.encode_anim(fixed, NB, loop, sounds, tol=1, repeats=False)
        done[index] = slot
        checks.append(dict(slot=slot, ticks=len(frames) - 1, ankle_lowered=round(lowered, 1), body_lift=round(lift, 1),
                           body_lowered=round(ground, 1)))
    output = result.build()
    effective = mmd.MMD.parse(output, NB)
    effective.type = SPECIES
    assert effective.tmd.build() == model.tmd.build()
    changed = changed_programs(model, effective)
    assert set(changed) <= {s for s, i in enumerate(model.anims.table) if i in done}, changed
    return output, dict(source_sha256=SOURCE, output_sha256=hashlib.sha256(output).hexdigest(), changed_slots=changed,
                        checks=checks, storage=motionstorage.require(output, NB))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/194-exveemon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof, indent=2) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
