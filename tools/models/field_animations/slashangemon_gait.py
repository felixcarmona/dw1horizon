"""SlashAngemon's field walk (species 300, slot 2), authored on its own 31-bone rig with planted feet.

Offline only (player builds replay the pinned delta): `tools/models/edit.py get 300` on the commit before this change,
then `python3 -m tools.models.field_animations.slashangemon_gait --source THAT.MMD --out AFTER.MMD` and
`edit.py put 300 AFTER.MMD`.

What was strange. The imported walk kept each foot planted for about 11 ticks of 16, but at the step before every
touchdown the planted knee folded to 93 degrees while the other foot lifted (the thigh went from -69 to -104 degrees and back
in two ticks, the foot jumped 22 units), the swinging foot flew forward at up to 4 times the ground speed and stopped dead
on landing, and the chest yawed a held +-20 degrees that flipped in three ticks, twice the tired walk's and the
run's, with the pelvis and the head turning against it, so the whole fan of wings swivelled in a snap.

What the walk is now. The legs are solved by position (hip, knee and ankle: `legik`) onto footprints, as for Magnamon:
each foot is planted at the ground's speed (the foot's track in the body's frame runs back at the root speed), swings
on an arc that leaves and meets the floor at the ground's speed (no skid, no stamp), lands heel first, rolls flat and
peels off the toe with the toe bone flat on the floor. The body sinks where the legs reach furthest (both feet down)
and rises over the planted foot (an inverted pendulum), the pelvis turns and rolls a little with the stride, the chest
counters it later and more slowly (a smooth, warped wave, never a hold and a flip), the head keeps looking ahead.
Arms, wings and skirt ride on the torso as in the run and the tired walk; they only lag it a little. Idle (slots 0 and
33), tired walk and run are the import's, byte for byte.
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
import motionstorage  # noqa: E402
import retarget as R  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402
from tools.models.field_animations.upright_gait import (  # noqa: E402
    apply, leg, lift_off_floor, mul, neutral_worlds, positions, rx, ry, rz, smooth, to_pose, wave)

SPECIES, NB = 300, 31
SOURCE = '1f76f61fcb691d22244c5d6ce7c7c8a22f85523a308ff0aa8e862a4cea366f3c'     # `edit.py get 300` before this change
SLOT = 2
BODY, PELVIS, HEAD = 1, 19, 18
# thigh, shin, ankle (the foot's big block), toe, side's sign in x
LEGS = [(20, 21, 22, 23, 1), (27, 28, 29, 30, -1)]
SKIRT = (24, 25, 26)
FLOOR = (22, 23, 29, 30)
REACH = 0.975
KNEE_BEND = 20          # a reference bend for the knee's plane

G = dict(ticks=16, travel=322, duty=0.60, front=0.46, lift=30, heel=8, strike=8, peel=0.55, drift=0.9, peak=0.7,
         unroll=0.45, sway=4.0, yaw=6.0, roll=3.0, rock=2.0, crouch=6, min_bend=22, stance_bend=28, knee_out=0.12,
         # the upper body: the chest turns against the hips (counter times the hips' yaw), rolls and lifts with each step
         counter=1.5, arm_unturn=1.0, chest_roll=3.0, lean=0.5, rise=2.5,
         head_follow=0.5, head_lag=0.19, head_tilt=2.5, head_up=1.5, head_nod=1.5,
         arm=7.0, arm_out=-2.0, shoulder_roll=1.5, arm_lag=0.10, blade=5.0, blade_lag=0.09, open=3.0,
         wing_lift=2.0, wing_lag=0.02, wing_pitch=0.4,
         skirt=-8.0, skirt_back=0.0, skirt_lag=0.08, skirt_roll=0.0)


def sided(t, *shape):
    """The second half cycle is the first mirrored, so both steps match."""
    return 0.5 * (wave(t, *shape) - wave(t + 0.5, *shape))


def children(skeleton, root):
    out, stack = [], [root]
    while stack:
        b = stack.pop()
        for c in range(len(skeleton)):
            if skeleton[c][1] == b:
                out.append(c)
                stack.append(c)
    return sorted(out)


def parse(data, skeleton):
    m = mmd.MMD.parse(data, NB)
    m.type = SPECIES
    return m


def foot_track(g, phase, toe_off):
    """Per cycle phase (the foot lands at 0): the ankle's forward offset in the body frame (forward is -z) for a flat
    foot, its lift, its pitch (positive heel up) and, in the stance, the share of the stance gone (None in the air)."""
    duty = g['duty']
    stride = g['travel'] * duty
    front = stride * g['front']
    t = phase % 1.
    if t < duty:
        s = t / duty
        pitch = g['heel'] * smooth((s - g['peel']) / (1 - g['peel'])) - g['strike'] * (1 - smooth(s / 0.2))
        return -front + stride * s, 0., pitch, s
    u = (t - duty) / (1 - duty)
    duration, start, end = 1 - duty, stride - front, -front
    speed = g['travel'] * duration * g['drift']
    z = (2 * u**3 - 3 * u**2 + 1) * start + (u**3 - 2 * u**2 + u) * speed + (3 * u**2 - 2 * u**3) * end \
        + (u**3 - u**2) * speed
    lift = g['lift'] * math.sin(math.pi * min(1., u ** g['peak']))
    pitch = toe_off * (1 - smooth(u / g['unroll']))
    pitch -= g['strike'] * smooth((u - 0.6) / 0.4)
    return z, lift, pitch, None


def build_frames(model, skeleton, g=G):
    rig = skeleton
    reference = animsheet.slot_frames(model, NB, 0)[0][0]
    offsets = {b: list(reference[b][6:9]) for b in range(1, NB)}
    neutral = neutral_worlds(rig, reference)
    carrier = list(reference[BODY][6:9])
    npos = positions(rig, offsets, neutral, BODY, carrier)
    rest = dict(neutral)
    w = mmd.bone_matrices(model, _identity_root(reference))
    contacts, floor = {}, 0.
    for thigh, shin, foot, toe, side in LEGS:
        verts = []
        for b in (foot, toe):
            verts += [[sum(w[b][i][j] * v[j] for j in range(3)) + w[b][i][3] for i in range(3)]
                      for v in model.tmd.obj_verts(rig[b][0])]
        floor = max(floor, max(v[1] for v in verts))
        sole = [v for v in verts if v[1] > max(v[1] for v in verts) - 8]
        heel = max(sole, key=lambda v: v[2])
        contacts[foot] = [heel[i] - npos[foot][i] for i in range(3)], [npos[toe][i] - npos[foot][i] for i in range(3)]
    stand = carrier[1] - floor
    n = g['ticks']
    torso_kids = [b for b in children(rig, BODY) if b != PELVIS and b not in children(rig, PELVIS)]
    head_kids = children(rig, HEAD) + [HEAD]
    skirt_kids = list(SKIRT)
    lens = {s: (legik.norm(offsets[shin]), legik.norm(offsets[foot])) for _, shin, foot, _, s in LEGS}
    sink = [0.] * n
    toe_off = {foot: g['heel'] for _, _, foot, _, _ in LEGS}
    longest = {s: math.sqrt(a * a + b * b + 2 * a * b * math.cos(math.radians(g['min_bend']))) for s, (a, b) in lens.items()}
    planted = {s: math.sqrt(a * a + b * b + 2 * a * b * math.cos(math.radians(g['stance_bend']))) for s, (a, b) in lens.items()}
    for _ in range(3):
        need = [0.] * n
        latest = dict(toe_off)
        history, frames, reach = {}, [], 0.
        for tick in range(n + 1):
            t = (tick % n) / n
            yaw = g['yaw'] * sided(t, 0.02, 0.2, 0.1)
            late = g['yaw'] * sided(t, 0.14, 0.2, 0.1)
            rock = g['rock'] * wave((2 * t) % 1., 0.12, 0.3)
            roll = -g['roll'] * sided(t, 0.3, 0.35, 0.2)
            sway = g['sway'] * sided(t, 0.28, 0.2)
            worlds = dict(rest)
            worlds[PELVIS] = mul(ry(yaw), rz(roll), rx(rock), rest[PELVIS])
            step = (2 * t) % 1.
            # the chest turns against the hips on a slow S-curve, rolls the other way and lifts a little with each push-off
            chest_yaw = -g['counter'] * late
            chest = mul(ry(chest_yaw), rz(-g['chest_roll'] * roll / max(g['roll'], 1e-9)),
                        rx(g['lean'] - g['rise'] * wave(step, 0.2, 0.2) + 0.6 * wave(t, 0.4, 0.4)))
            for b in torso_kids:
                worlds[b] = mul(chest, rest[b])
            # the head stays level and follows the chest's turn a few ticks late, tilts and nods softly
            follow = -g['counter'] * g['yaw'] * sided(t - g['head_lag'], 0.14, 0.2, 0.1)
            head = mul(ry(g['head_follow'] * follow), rz(g['head_tilt'] * sided(t, 0.4, 0.2)),
                       rx(-g['head_up'] + g['head_nod'] * wave(step, 0.35, 0.3)))
            for b in head_kids:
                worlds[b] = mul(head, rest[b])
            # arms: relaxed pendulums, a different phase on each side, the shoulder rolling a little, the blade arm lagging
            # more and its hand opening outwards at the end of each swing
            for chain, half, side in (((2, 3, 4), 0., 1), ((5, 6, 7), 0.5, -1)):
                shoulder = mul(ry(-g['arm_unturn'] * chest_yaw), chest, rz(-side * (g['arm_out'] + g['shoulder_roll'] * wave(step, 0.1, 0.2))))
                worlds[chain[0]] = mul(shoulder, rest[chain[0]])
                upper = mul(rx(g['arm'] * wave(t, g['arm_lag'] + half, 0.2, 0.1)), shoulder)
                worlds[chain[1]] = mul(upper, rest[chain[1]])
                hand = mul(rx(g['blade'] * wave(t, g['arm_lag'] + g['blade_lag'] + half, 0.2, 0.1)),
                           rz(side * g['open'] * wave(t, g['arm_lag'] + g['blade_lag'] + 0.25 + half, 0.2)), upper)
                worlds[chain[2]] = mul(hand, rest[chain[2]])
            # wings breathe: a soft lift on each push-off, a soft fold on each landing, each feather section a little later
            for chain, side in (((13, 14, 15, 16, 17), 1), ((8, 9, 10, 11, 12), -1)):
                d = chest
                for k, b in enumerate(chain):
                    lift = g['wing_lift'] * wave(step, 0.2 + g['wing_lag'] * k, 0.2)
                    d = mul(rz(-side * lift), rx(g['wing_pitch'] * wave(step, 0.3 + g['wing_lag'] * k, 0.2)), d)
                    worlds[b] = mul(d, rest[b])
            # the skirt trails the hips and drapes: each piece a little later than the one above
            base = mul(worlds[PELVIS], R.m3t(rest[PELVIS]))
            worlds[24] = mul(rx(g['skirt_back'] * wave(step, 0.3 + g['skirt_lag'], 0.2)), base, rest[24])
            front = mul(rx(g['skirt'] * wave(step, 0.3 + g['skirt_lag'], 0.2)),
                        rz(g['skirt_roll'] * sided(t, 0.45 + g['skirt_lag'], 0.2)), base)
            worlds[25] = mul(front, rest[25])
            front = mul(rx(g['skirt'] * wave(step, 0.3 + 2 * g['skirt_lag'], 0.2)), front)
            worlds[26] = mul(front, rest[26])
            body = [carrier[0] + sway, stand + g['crouch'] + sink[tick % n], carrier[2]]
            pos = positions(rig, offsets, worlds, BODY, body)
            for thigh, shin, foot, toe, side in LEGS:
                z, lift, pitch, stance = foot_track(g, t if side > 0 else t + 0.5, toe_off[foot])
                ankle = [npos[foot][0], npos[foot][1] - (carrier[1] - stand) - lift, npos[foot][2] + z]
                hip = pos[thigh]
                l1, l2 = lens[side]
                heel, tip = contacts[foot]

                def place(p):
                    pivot = tip if p > 0 else heel
                    turned = apply(rx(p), pivot)
                    return [ankle[i] + pivot[i] - turned[i] for i in range(3)]
                target = place(pitch)
                if (stance is None or stance > 0.3) and legik.norm(legik.sub(target, hip)) > planted[side]:
                    low, high = pitch, 60.
                    for _ in range(24):
                        mid = (low + high) / 2
                        low, high = (mid, high) if legik.norm(legik.sub(place(mid), hip)) > planted[side] else (low, mid)
                    pitch = high
                    target = place(pitch)
                    if stance is not None:
                        latest[foot] = pitch
                reach = max(reach, legik.norm(legik.sub(target, hip)) / (l1 + l2))
                across = (target[0] - hip[0]) ** 2 + (target[2] - hip[2]) ** 2
                depth = math.sqrt(max(0., longest[side] ** 2 - across))
                need[tick % n] = max(need[tick % n], target[1] - hip[1] - depth + sink[tick % n])
                knee0 = npos[shin]
                bent = rx(KNEE_BEND)
                ankle0 = [knee0[i] + apply(bent, [npos[foot][j] - knee0[j] for j in range(3)])[i] for i in range(3)]
                pole = apply(ry(0.5 * yaw), [g['knee_out'] * side, 0, -1])
                worlds[thigh], worlds[shin] = leg(hip, target, l1, l2, pole, [npos[thigh], knee0, ankle0],
                                                  [rest[thigh], mul(bent, rest[shin])])
                worlds[foot] = mul(rx(pitch), rest[foot])
                # the toe bone stays flat while the heel peels, and turns up with the foot before the landing
                worlds[toe] = mul(rx(min(pitch, 0.)), rest[toe])
            frames.append(to_pose(rig, reference, worlds, BODY, body, g['travel'] * tick / n, history))
        toe_off = latest
        wide = [max(need[(i + k) % n] for k in range(-2, 3)) for i in range(n)]
        sink = [sum(wt * wide[(i + k) % n] for k, wt in zip(range(-2, 3), (1, 4, 6, 4, 1))) / 16 for i in range(n)]
    assert reach < 1.0, reach
    return frames, reach


def _identity_root(pose):
    p = [list(b) for b in pose]
    p[0] = [4096] * 3 + [0] * 6
    return p


def build(data, skeleton, g=G):
    model = parse(data, skeleton)
    frames, reach = build_frames(model, skeleton, g)
    frames, lift = lift_off_floor(model, skeleton, frames, FLOOR, BODY)
    n = g['ticks']
    old = animsheet.slot_frames(model, NB, SLOT)
    sounds = [(t, 'sound', {'op': 'sound', 'frame': t + 1, 'bank': 1, 'note': 16}) for t in (0, n // 2)]
    result = copy.deepcopy(model)
    index = model.anims.table[SLOT]
    assert [s for s, i in enumerate(model.anims.table) if i == index] == [SLOT]
    result.anims.anims[index] = mmd.encode_anim(frames, NB, 0, sounds, tol=1, repeats=False)
    out = result.build()
    effective = mmd.MMD.parse(out, NB)
    effective.type = SPECIES
    assert effective.tmd.build() == model.tmd.build()
    changed = changed_programs(model, effective)
    assert changed == [SLOT], changed
    return out, dict(output_sha256=hashlib.sha256(out).hexdigest(), reach=round(reach, 3), maximum_body_lift=round(lift, 1),
                     changed_slots=changed, storage=motionstorage.require(out, NB))


# ---- measurements (used by the tests and while tuning)

def measure(model, skeleton, slot):
    """Ticks, root speed, per foot part (ankle block 22 / 29, toe 23 / 30) the stance slip of its sole vertex at rest (percent of the
    root speed over the ticks it is within 4 units of the floor), the floor penetration of the feet and the body bob."""
    from tools.models.field_animations import okuwamon_limbs as ok
    body = ok.Body(model, skeleton)
    frames = animsheet.slot_frames(model, NB, slot)[0]
    n = len(frames)
    speed = abs(frames[-1][0][8] - frames[0][0][8]) / max(1, n - 1)
    out = dict(ticks=n, speed=speed, feet={}, foot_floor=0.0)
    worlds = []
    for f in frames:
        mats, world = body.world(f)
        worlds.append((mats, world, f[0][8]))
    rest_world = body.world(animsheet.slot_frames(model, NB, 0)[0][0])[1]
    for bone in (22, 23, 29, 30):
        i = int(body.points(rest_world, [bone])[:, 1].argmax())          # the vertex that is the sole at rest
        low = []
        for mats, world, root in worlds:
            pts = body.points(world, [bone])
            low.append((pts[i, 1], pts[i, 2] + root))
        stance = [t for t in range(n - 1) if low[t][0] > -4 and low[t + 1][0] > -4]
        sl = [abs(low[t + 1][1] - low[t][1]) / speed * 100 for t in stance] if speed else []
        out['feet'][bone] = dict(stance=len(stance), slip_sole=(sum(sl) / len(sl) if sl else 0, max(sl, default=0)))
        out['foot_floor'] = max(out['foot_floor'], max(l[0] for l in low))
    ys = [np.array(mats[BODY])[1, 3] for mats, _, _ in worlds]
    out['bob'] = max(ys) - min(ys)
    return out


GROUPS = {'armL': (5, 6, 7), 'armR': (2, 3, 4), 'legL': (27, 28, 29, 30), 'legR': (20, 21, 22, 23),
          'wingL': tuple(range(8, 13)), 'wingR': tuple(range(13, 18)), 'skirt': SKIRT}
BODY_PARTS = (1, 18, 19)


def upper_motion(model, skeleton, slot):
    """What the upper body does over the loop, in the body frame: per group the peak-to-peak travel of its centroid (x, y, z), the
    chest turn (the line through the two wings' centroids, degrees), the hips' turn (the skirt's back to front line), how the two correlate (negative is against) and the
    roughest tick (largest second difference over the group's peak-to-peak: a steady curve is small, a flutter near 1)."""
    from tools.models.field_animations import okuwamon_limbs as ok
    body = ok.Body(model, skeleton)
    frames = animsheet.slot_frames(model, NB, slot)[0][:-1]
    cent = {k: [] for k in ('head', 'armL', 'armR', 'wingL', 'wingR', 'skirtB', 'skirtF')}
    chains = dict(head=(HEAD,), armL=GROUPS['armL'], armR=GROUPS['armR'], wingL=GROUPS['wingL'], wingR=GROUPS['wingR'],
                  skirtB=(24,), skirtF=(25, 26))
    for f in frames:
        world = body.world(f)[1]
        for k, chain in chains.items():
            cent[k].append(body.points(world, list(chain)).mean(axis=0))
    cent = {k: np.array(v) for k, v in cent.items()}
    out = dict(travel={}, rough={})
    for k in ('head', 'armL', 'armR', 'wingL', 'wingR'):
        c = cent[k]
        span = c.max(axis=0) - c.min(axis=0)
        out['travel'][k] = [float(v) for v in span]
        second = np.abs(np.roll(c, -1, axis=0) - 2 * c + np.roll(c, 1, axis=0)).max(axis=0)
        out['rough'][k] = float((second / np.maximum(span, 1e-6)).max())

    def turn(a, b):
        d = a - b
        ang = np.degrees(np.arctan2(d[:, 2], d[:, 0]))
        return (ang - ang[0] + 180) % 360 - 180
    chest, hips = turn(cent['wingL'], cent['wingR']), turn(cent['skirtB'], cent['skirtF'])
    out['chest_turn'] = float(chest.max() - chest.min())
    out['hip_turn'] = float(hips.max() - hips.min())
    out['against'] = float(np.corrcoef(chest, hips)[0, 1])      # negative: the chest turns against the hips
    return out


def penetration(model, skeleton, pose, body=None):
    """Vertices of each limb group inside the parts it must not cut (point in mesh): the torso, head and pelvis and the other groups."""
    from tools.models.field_animations import okuwamon_limbs as ok
    body = body or ok.Body(model, skeleton)
    mats, world = body.world(pose)
    out = {}
    for key, chain in GROUPS.items():
        others = tuple(b for k, c in GROUPS.items() if k != key and not (k.startswith('wing') and key.startswith('wing')) for b in c)
        out[key] = body.count(mats, world, chain, BODY_PARTS + others)
    return out


def penetration_report(model, skeleton, slot):
    from tools.models.field_animations import okuwamon_limbs as ok
    body = ok.Body(model, skeleton)
    frames = animsheet.slot_frames(model, NB, slot)[0]
    worst, total = {}, 0
    for f in frames[:-1]:
        for k, v in penetration(model, skeleton, f, body).items():
            worst[k] = max(worst.get(k, 0), v)
            total += v
    return worst, total


def jumps(model, skeleton, slot):
    """Largest tick-to-tick mean vertex displacement (root motion removed) over the median, around the loop."""
    from tools.models.field_animations import okuwamon_limbs as ok
    body = ok.Body(model, skeleton)
    frames = animsheet.slot_frames(model, NB, slot)[0]
    worlds = [body.world(f)[1] for f in frames[:-1]]
    d = [float(np.linalg.norm(worlds[(i + 1) % len(worlds)] - worlds[i], axis=1).mean()) for i in range(len(worlds))]
    med = float(np.median(d))
    return max(d) / med if med else 0.0, med


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    data = a.source.read_bytes()
    assert hashlib.sha256(data).hexdigest() == SOURCE, 'the source is not the import before this change'
    skeleton = json.loads(next((ROOT / 'content/species').glob('300-*.json')).read_text())['model']['skeleton']
    out, proof = build(data, skeleton)
    a.out.write_bytes(out)
    text = json.dumps(proof, indent=2, default=str) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
