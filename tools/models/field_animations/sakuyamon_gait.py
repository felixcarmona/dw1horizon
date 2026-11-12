"""Sakuyamon's legs in the walk, tired walk and run (species 316, slots 2, 3 and 4), put back on two lanes.

Offline only (player builds replay the pinned delta): `tools/models/edit.py get 316` on the commit before this change,
then `python3 -m tools.models.field_animations.sakuyamon_gait --source THAT.MMD --out AFTER.MMD` and `edit.py put 316 AFTER.MMD`.

What looked wrong ("it walks as if desperate to pee, thighs together"). The import maps Angemon's gait onto the 27-bone rig, and
Angemon's legs are far apart (its hips and feet sit 130-160 units apart) while Sakuyamon's hips are 33 apart with 50-unit thigh
volumes. In the walk the mapped legs closed on each other: the knees came in to 41 (52 at rest, 32 in the run), the ankles
crossed the body's midline in their lane (the feet's meshes overlapped sideways by up to 20 units and the toes by 33, against a
clear +14 and +48 at rest), the shins ground into each other (as many as 46 vertices inside the other leg) and each foot turned
in about 40 degrees from the idle's toe-out of 31 (to about -10).

The legs are now solved again by position. Every tick keeps the ankle's height and fore-aft position (so the stride, the lift, the
timing, the stance slip and the root speed are the import's) and takes its lateral place on a lane: one fixed distance either side
of the walk's own centre line. The knee points forward and a little outwards, and the foot is turned back to a relaxed toe-out
(the import's own foot motion on top, a quarter of it). Pelvis, arms, staff, head and every other channel, and the idle and the
other programs, are the import's byte for byte.
"""
import argparse
import copy
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet  # noqa: E402
import legik  # noqa: E402
import mmd  # noqa: E402
import motionsecondary  # noqa: E402
import motionstorage  # noqa: E402
import retarget as R  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402
from tools.models.field_animations.articulation import replace_channels  # noqa: E402
from tools.models.field_animations.war_greymon import set_rotation  # noqa: E402

SPECIES, NB = 316, 27
SOURCE = 'edacbd328e73eb021fc2107bf46343c5a8e777c9f4daf5353aec08d8b2d1d518'     # `edit.py get 316` before this change
SLOTS = (2, 3, 4)
PELVIS = 2
# thigh, shin, ankle, toe, side's sign in x (right +)
LEGS = [(3, 4, 5, 6, 1), (7, 8, 9, 10, -1)]
CHANNELS = {(b, c) for leg in LEGS for b in leg[:3] for c in (3, 4, 5)} | {(1, 7)}

G = {
    2: dict(lane=42., toe_out=16., keep=0.25, knee_out=0.30, reach=0.985, slope=1.5),
    3: dict(lane=42., toe_out=16., keep=0.25, knee_out=0.30, reach=0.985, slope=1.5),
    4: dict(lane=44., toe_out=14., keep=0.25, knee_out=0.30, reach=0.985, slope=1.5),
}


def parse(data):
    m = mmd.MMD.parse(data, NB)
    m.type = SPECIES
    return m


def _root0(pose):
    p = copy.deepcopy(pose)
    p[0] = [4096] * 3 + [0] * 6
    return p


def worlds(model, pose):
    return np.array(mmd.bone_matrices(model, _root0(pose)))


def lateral_yaw(rot):
    """Where the foot's own sideways axis points on the ground plane (degrees); the toe-out is this less the idle's, with the
    sign of the side. Immune to the foot's pitch (the heel kick and the toe-off), unlike the toe's own direction."""
    a = rot[:, 0]
    return math.degrees(math.atan2(a[2], a[0]))


def about_y(deg):
    return np.array(R.from_axis_angle([0, 1, 0], math.radians(deg)))


def build_slot(model, frames, g, idle):
    n = len(frames)
    skeleton = mmd.exe().skeleton[SPECIES]
    offs = {b: np.array(frames[0][b][6:9], float) for b in range(1, NB)}
    lens = {leg[0]: (np.linalg.norm(offs[leg[1]]), np.linalg.norm(offs[leg[2]])) for leg in LEGS}
    ref = [worlds(model, f) for f in frames]
    # the leg's twist is the idle's (its bend plane is steady; the import's own is not, where the leg is nearly straight)
    rest = worlds(model, animsheet.slot_frames(model, NB, 0)[0][0])
    centre = np.mean([(w[5, 0, 3] + w[9, 0, 3]) / 2 for w in ref[:-1]])
    yaw0 = {leg[0]: [lateral_yaw(w[leg[2], :3, :3]) for w in ref] for leg in LEGS}
    out = []
    history = {}
    worst = 0.
    targets = []
    for w0 in ref:
        row = {}
        for hip, knee, foot, toe, side in LEGS:
            ankle0 = w0[foot, :3, 3]
            row[hip] = np.array([centre + side * g['lane'], ankle0[1], ankle0[2]])
        targets.append(row)
    # the legs are nearly straight when planted: a lane further out needs the body a little lower there (never the foot higher or
    # the lane narrower). The crouch per tick is the least that lets both legs reach, as a tent over the ticks (a 1.5 unit slope).
    need = [0.] * (n - 1)
    for t in range(n - 1):
        for hip, knee, foot, toe, side in LEGS:
            h = ref[t][hip, :3, 3]
            la, lb = lens[hip]
            tg = targets[t][hip]
            lim = g['reach'] * (la + lb)
            dx, dz, dy = tg[0] - h[0], tg[2] - h[2], tg[1] - h[1]
            if math.sqrt(dx * dx + dz * dz + dy * dy) > lim:
                need[t] = max(need[t], dy - math.sqrt(max(0., lim * lim - dx * dx - dz * dz)))
    m = n - 1
    crouch = [max(0., max(need[j] - g['slope'] * min((i - j) % m, (j - i) % m) for j in range(m))) for i in range(m)] + [0.]
    crouch[-1] = crouch[0]
    for t, source in enumerate(frames):
        p = copy.deepcopy(source)
        p[1][7] = round(p[1][7] + crouch[t])
        w0 = worlds(model, p)
        for hip, knee, foot, toe, side in LEGS:
            h = w0[hip, :3, 3]
            la, lb = lens[hip]
            target = targets[t][hip]
            line = target - h
            line /= np.linalg.norm(line)
            # the knee forward and a little outwards, with the pelvis (the import's own knee direction wanders where the leg is straight)
            pole = w0[PELVIS, :3, :3] @ np.array([side * g['knee_out'], 0., -1.])
            knee_pos, got = legik.solve(h.tolist(), target.tolist(), la, lb, pole.tolist())
            upper, lower = motionsecondary.native_plane_rotations(
                [rest[b, :3, 3].tolist() for b in (hip, knee, foot)], [h.tolist(), knee_pos, got],
                [rest[hip, :3, :3].tolist(), rest[knee, :3, :3].tolist()])
            set_rotation(p, hip, w0[PELVIS, :3, :3].T @ np.array(upper), history)
            w = worlds(model, p)
            set_rotation(p, knee, w[hip, :3, :3].T @ np.array(lower), history)
            w = worlds(model, p)
            # the foot: its sideways yaw back to a toe-out, the pitch and roll as the import has them
            yaw_now = yaw0[hip][t]
            keep = g['keep'] * (yaw_now - np.mean(yaw0[hip][:-1]))      # the import's own swing of the foot, a quarter of it
            want = side * g['toe_out'] + keep
            r_foot = about_y(idle['turn'] * (want - yaw_now)) @ ref[t][foot, :3, :3]
            set_rotation(p, foot, w[knee, :3, :3].T @ r_foot, history)
            w = worlds(model, p)
            worst = max(worst, float(np.linalg.norm(w[foot, :3, 3] - target)))
        out.append(p)
    return out, worst, max(crouch)


def idle_foot(model):
    """The idle's foot: its sideways axis' yaw per side and its toe-out (degrees, the toe's direction from the ankle; the sideways
    yaw is the toe-out times the side's sign), and `turn`, the sign with which a turn about the vertical moves that yaw."""
    w = worlds(model, animsheet.slot_frames(model, NB, 0)[0][0])
    info = dict(yaw={}, toe_out=None)
    for hip, knee, foot, toe, side in LEGS:
        info['yaw'][side] = lateral_yaw(w[foot, :3, :3])
        outward = side_toe_out(w[toe, :3, 3] - w[foot, :3, 3], side)
        assert abs(info['yaw'][side] - side * outward) < 2, (side, info['yaw'][side], outward)
        info['toe_out'] = outward if info['toe_out'] is None else (info['toe_out'] + outward) / 2
    info['turn'] = 1 if lateral_yaw(about_y(10.) @ w[5, :3, :3]) > lateral_yaw(w[5, :3, :3]) else -1
    return info


def side_toe_out(d, side):
    return side * math.degrees(math.atan2(d[0], -d[2]))


def build(data, g=G):
    model = parse(data)
    assert hashlib.sha256(data).hexdigest() == SOURCE
    old_slots = {s: model.anims.table[s] for s in SLOTS}
    assert len(set(old_slots.values())) == 3
    for s in SLOTS:
        assert [i for i, v in enumerate(model.anims.table) if v == old_slots[s]] == [s]
    idle = idle_foot(model)
    result = copy.deepcopy(model)
    worst = {}
    for s in SLOTS:
        frames, loop, events = animsheet.slot_frames(model, NB, s)
        assert loop == 0
        frames = [[list(b) for b in f] for f in frames]
        new, err, crouch = build_slot(model, frames, g[s], idle)
        new[-1][1:] = copy.deepcopy(new[0][1:])
        for f_new, f_old in zip(new, frames):                  # only the legs' rotations move
            for b in range(NB):
                for c in range(9):
                    if (b, c) not in CHANNELS and b != 0:
                        assert f_new[b][c] == f_old[b][c], (s, b, c)
        original = model.anims.anims[old_slots[s]]
        result.anims.anims[old_slots[s]] = replace_channels(original, new, loop, NB, CHANNELS)
        worst[s] = dict(solve_error=round(err, 3), crouch=round(crouch, 1))
    out = result.build()
    effective = parse_effective(out)
    assert effective.tmd.build() == model.tmd.build()
    assert changed_programs(model, effective) == list(SLOTS)
    storage = motionstorage.audit(out, NB)
    assert storage['fits'], storage
    return out, dict(output_sha256=hashlib.sha256(out).hexdigest(), slots=worst, storage=storage)


def parse_effective(data):
    m = mmd.MMD.parse(data, NB)
    m.type = SPECIES
    return m


# ---- measurements (used by the tests and while tuning)

LEG_R, LEG_L = (3, 4, 5, 6), (7, 8, 9, 10)


def lane_gaps(model, slot):
    """Per tick, how far apart the two legs' meshes are sideways (right's lowest x less left's highest x) for the thigh, shin,
    foot and toe parts, the knee and ankle bones' lateral distance, and the leg-on-leg penetration count."""
    from tools.models.field_animations import okuwamon_limbs as ok
    body = ok.Body(model, mmd.exe().skeleton[SPECIES])
    rows = []
    for f in animsheet.slot_frames(model, NB, slot)[0]:
        mats, world = body.world(f)
        row = {}
        for name, a, b in (('thigh', 3, 7), ('shin', 4, 8), ('foot', 5, 9), ('toe', 6, 10)):
            row[name] = float(body.points(world, [a])[:, 0].min() - body.points(world, [b])[:, 0].max())
        w = np.array(mats)
        row['knee'] = float(w[4, 0, 3] - w[8, 0, 3])
        row['ankle'] = float(w[5, 0, 3] - w[9, 0, 3])
        row['pen'] = body.count(mats, world, list(LEG_R), list(LEG_L)) + body.count(mats, world, list(LEG_L), list(LEG_R))
        rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    data, report = build(a.source.read_bytes())
    a.out.write_bytes(data)
    print(json.dumps(report, indent=1))


if __name__ == '__main__':
    main()
