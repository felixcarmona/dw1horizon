"""Creepymon's field idle, walk, tired walk and run (species 312), authored on its own 20-bone rig with planted feet.

Offline only (player builds replay the pinned delta and the overlay): the overlay `creepymon-chibi` builds the chibi
proportions and the celebrations as before (`celebrations.build`) and then writes the field slots again with this module.

What was wrong. The imported clips of a robed demon on short chibi legs slid the soles over the floor (stance slip 96 % mean and
156 % worst in the walk, 104 % in the tired walk, 75 % in the run), the run went 56 units a tick (native runs are 35 to 52), the
arms flung out forward to the horizontal, and the long robe, the wings and the head all rode the body as one rigid block.

What it is now. The legs are solved by position (hip, knee, ankle: `legik`) onto footprints, as for Magnamon and SlashAngemon: each
foot is planted at the ground's speed (no slip), swings on an arc that leaves and meets the floor at the ground's speed, and
the body sinks where the legs reach furthest (the short legs bend, hidden under the robe) and rises over the planted foot. The
run has a short flight between the steps (the body hops, the boots tuck). The robe (the pelvis bone) lags the hips and flares
back with speed, the chest turns against the hips on a slow curve, the head stays level and follows a little late, the arms hang
and swing as loose pendulums (the elbow after the shoulder, the hand after the elbow), the wings breathe and trail the chest a few
ticks late (swept back in the run). Each clip is a whole number of ticks, its root travels the same distance every tick, and the
last pose equals the first.
"""
import argparse
import copy
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet  # noqa: E402
import legik  # noqa: E402
import mmd  # noqa: E402
import motioncyclelayer  # noqa: E402
import motionstorage  # noqa: E402
import retarget as R  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402
from tools.models.field_animations.upright_gait import (  # noqa: E402
    apply, leg, lift_off_floor, mul, neutral_worlds, positions, rx, ry, rz, smooth, to_pose, wave)

SPECIES, NB = 312, 20
BODY, PELVIS, HEAD = 1, 13, 7
ARMS = {1: (2, 3, 4, 5), -1: (8, 9, 10, 11)}          # shoulder, upper arm, forearm, hand (right is +x)
WINGS = {1: 6, -1: 12}
# thigh, shin, foot (the boot), side
LEGS = [(14, 15, 16, 1), (17, 18, 19, -1)]
FLOOR = (16, 19)
CLIP_OF_SLOT = {0: 'idle', 2: 'walk', 3: 'tired', 4: 'run'}
TWINS = {2: (35,), 4: (36,)}
SLOTS = (0, 2, 3, 4, 35, 36)
KNEE_BEND = 20
DEBUG = False
NOTE = 21

BASE = dict(ticks=20, travel=300, duty=0.55, front=0.46, lift=24, heel=0, strike=0, peel=0.55, drift=0.9, peak=0.6,
            unroll=0.45, hop=0, beats=2,
            sway=4.0, yaw=6.0, roll=2.5, rock=1.5, crouch=3, min_bend=22, stance_bend=26, knee_out=0.10,
            # the upper body
            counter=1.3, chest_roll=2.0, lean=1.0, rise=1.5, chest_pitch=0.8,
            head_follow=0.7, head_lag=0.16, head_tilt=2.0, head_up=1.5, head_nod=1.5, head_down=0,
            arm=9.0, arm_lag=0.12, arm_out=2.0, elbow=7.0, elbow_lag=0.10, wrist=5.0, wrist_lag=0.10, arm_fwd=0.0,
            wing_flap=2.5, wing_lag=0.12, wing_back=0.0, wing_pitch=1.5,
            robe_back=0.0, robe_lag=0.10, robe_pitch=2.5, robe_roll=1.5,
            breath=0.0, glance=0.0, shift=0.0)

CLIPS = {
    'idle': dict(BASE, ticks=72, travel=0, duty=1.0, front=0, lift=0, heel=0, strike=0, beats=3, sway=2.5, yaw=2.0, roll=1.0,
                 rock=0.5, crouch=4, counter=0.8, chest_roll=0.8, lean=0.5, rise=1.2, chest_pitch=0.9, head_follow=1.0,
                 head_tilt=1.5, head_up=0.5, head_nod=1.2, arm=2.0, arm_lag=0.08, arm_out=1.0, elbow=2.5, wrist=3.0,
                 wing_flap=2.0, wing_back=0.0, wing_pitch=1.8, robe_pitch=1.0, robe_roll=0.8, breath=1.0, glance=9.0,
                 shift=3.0),
    'walk': dict(BASE, ticks=20, travel=320, duty=0.55, lift=26, sway=4.0, yaw=6.0, roll=2.5, rock=2.0, crouch=2,
                 counter=1.4, lean=1.5, rise=1.5, arm=12.0, elbow=9.0, wrist=6.0, wing_flap=3.0, wing_back=2.0,
                 robe_back=3.0, robe_pitch=3.0),
    'tired': dict(BASE, ticks=24, travel=288, duty=0.625, lift=14, heel=0, strike=0, sway=5.0, yaw=4.0, roll=3.0, rock=1.0,
                  crouch=7, counter=1.0, chest_roll=2.5, lean=9.0, rise=1.0, head_follow=0.5, head_up=-9.0, head_nod=1.5,
                  head_tilt=3.0, arm=6.0, arm_lag=0.14, elbow=4.0, wrist=3.0, arm_out=-1.0, arm_fwd=3.0,
                  wing_flap=1.6, wing_back=-3.0, wing_pitch=1.5, robe_back=1.5, robe_pitch=1.5, knee_out=0.12),
    'run': dict(BASE, ticks=14, travel=532, duty=0.3571, front=0.46, lift=40, heel=0, strike=0, hop=14, sway=3.0, yaw=8.0,
                roll=2.5, rock=2.5, crouch=2, counter=1.5, chest_roll=2.0, lean=11.0, rise=2.0, arm=19.0, arm_lag=0.08,
                elbow=14.0, elbow_lag=0.08, wrist=6.0, arm_fwd=14.0, wing_flap=2.5, wing_back=16.0, wing_lag=0.08,
                robe_back=13.0, robe_pitch=3.5, head_up=4.0, head_nod=2.0, head_follow=0.5, peak=0.5, drift=0.3),
}


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
    # the swing is a quintic in the world's frame (the foot leaves and meets the floor at rest), plus the ground's own
    # travel back through the body's frame, so a planted foot stays planted to the last tick and starts gently
    ground = g['travel'] * (1 - duty)
    start, end = stride - front, -front - ground
    z = start + (end - start) * u ** 3 * (10 - 15 * u + 6 * u * u) + ground * u
    lift = g['lift'] * math.sin(math.pi * u) ** g['peak']
    pitch = toe_off * (1 - smooth(u / g['unroll']))
    pitch -= g['strike'] * smooth((u - 0.6) / 0.4)
    return z, lift, pitch, None


def flight(g, t):
    """The body's hop at cycle phase t: a half sine over each stretch where neither foot is on the floor."""
    d = g['duty']
    if g['hop'] <= 0 or d >= 0.5:
        return 0.
    t %= 0.5
    if t < d:
        return 0.
    return g['hop'] * math.sin(math.pi * (t - d) / (0.5 - d))


def _identity_root(pose):
    p = [list(b) for b in pose]
    p[0] = [4096] * 3 + [0] * 6
    return p


def build_frames(model, skeleton, g):
    rig = skeleton
    reference = animsheet.slot_frames(model, NB, 0)[0][0]
    offsets = {b: list(reference[b][6:9]) for b in range(1, NB)}
    neutral = neutral_worlds(rig, reference)
    carrier = list(reference[BODY][6:9])
    npos = positions(rig, offsets, neutral, BODY, carrier)
    rest = dict(neutral)
    w = mmd.bone_matrices(model, _identity_root(reference))
    contacts, floor = {}, 0.
    for thigh, shin, foot, side in LEGS:
        verts = [[sum(w[foot][i][j] * v[j] for j in range(3)) + w[foot][i][3] for i in range(3)]
                 for v in model.tmd.obj_verts(rig[foot][0])]
        floor = max(floor, max(v[1] for v in verts))
        sole = [v for v in verts if v[1] > max(v[1] for v in verts) - 8]
        heel = max(sole, key=lambda v: v[2])
        tip = min(sole, key=lambda v: v[2])
        contacts[foot] = [heel[i] - npos[foot][i] for i in range(3)], [tip[i] - npos[foot][i] for i in range(3)]
    stand = carrier[1] - floor
    n = g['ticks']
    pelvis_kids = children(rig, PELVIS)
    torso_kids = [b for b in children(rig, BODY) if b != PELVIS and b not in pelvis_kids and b != HEAD]
    lens = {s: (legik.norm(offsets[shin]), legik.norm(offsets[foot])) for _, shin, foot, s in LEGS}
    sink = [0.] * n
    toe_off = {foot: g['heel'] for _, _, foot, _ in LEGS}
    longest = {s: math.sqrt(a * a + b * b + 2 * a * b * math.cos(math.radians(g['min_bend']))) for s, (a, b) in lens.items()}
    planted = {s: math.sqrt(a * a + b * b + 2 * a * b * math.cos(math.radians(g['stance_bend']))) for s, (a, b) in lens.items()}
    K = g['beats']
    for _ in range(3):
        need = [0.] * n
        latest = dict(toe_off)
        history, frames, reach = {}, [], 0.
        for tick in range(n + 1):
            t = (tick % n) / n
            step = (K * t) % 1.
            hop = flight(g, t)
            yaw = g['yaw'] * sided(t, 0.02, 0.2, 0.1)
            late = g['yaw'] * sided(t, 0.14, 0.2, 0.1)
            rock = g['rock'] * wave((2 * t) % 1., 0.12, 0.3)
            roll = -g['roll'] * sided(t, 0.3, 0.35, 0.2)
            sway = g['sway'] * sided(t, 0.28, 0.2) + g['shift'] * math.sin(2 * math.pi * t)
            breath = g['breath'] * wave(step, 0.0, 0.2)
            worlds = dict(rest)
            # the robe: the pelvis bone carries the whole skirt; it lags the hips' turn and trails back with speed
            robe_lag = g['robe_lag']
            robe_yaw = g['yaw'] * sided(t - robe_lag, 0.02, 0.2, 0.1)
            robe = mul(ry(robe_yaw), rz(roll - g['robe_roll'] * sided(t - robe_lag, 0.4, 0.3)),
                       rx(rock - g['robe_back'] + g['robe_pitch'] * wave(step, 0.3 + robe_lag, 0.2)), rest[PELVIS])
            worlds[PELVIS] = robe
            hips = mul(ry(yaw), rz(roll), rx(rock))
            # the chest turns against the hips on a slow S-curve, rolls the other way and lifts a little with each push-off
            chest_yaw = -g['counter'] * late
            chest = mul(ry(chest_yaw), rz(-g['chest_roll'] * roll / max(g['roll'], 1e-9)),
                        rx(g['lean'] - g['rise'] * wave(step, 0.2, 0.2) + g['chest_pitch'] * breath))
            worlds[BODY] = mul(chest, rest[BODY])
            # the head stays level and follows the chest's turn a few ticks late, tilts and nods softly
            follow = -g['counter'] * g['yaw'] * sided(t - g['head_lag'], 0.14, 0.2, 0.1)
            glance = g['glance'] * (math.sin(2 * math.pi * t) * math.sin(2 * math.pi * t) * math.sin(4 * math.pi * t))
            head = mul(ry(g['head_follow'] * follow + glance),
                       rz(g['head_tilt'] * sided(t, 0.4, 0.2)),
                       rx(-g['head_up'] + g['head_down'] + g['head_nod'] * wave(step, 0.35, 0.3)))
            worlds[HEAD] = mul(head, rest[HEAD])
            # arms: loose pendulums, the elbow after the shoulder and the hand after the elbow, a different phase on each side
            for side, chain in ARMS.items():
                half = 0. if side > 0 else 0.5
                shoulder = mul(chest, rz(-side * (g['arm_out'] + 0.5 * wave(step, 0.1, 0.2))))
                worlds[chain[0]] = mul(shoulder, rest[chain[0]])
                swing = g['arm'] * wave(t, g['arm_lag'] + half, 0.2, 0.1) - g['arm_fwd']
                upper = mul(rx(swing), shoulder)
                worlds[chain[1]] = mul(upper, rest[chain[1]])
                fore = mul(rx(-g['elbow'] * 0.5 * (1 + wave(t, g['arm_lag'] + g['elbow_lag'] + half + 0.1, 0.2, 0.1))), upper)
                worlds[chain[2]] = mul(fore, rest[chain[2]])
                hand = mul(rx(g['wrist'] * wave(t, g['arm_lag'] + g['elbow_lag'] + g['wrist_lag'] + half, 0.2)),
                           rz(side * 0.6 * g['wrist'] * wave(t, g['arm_lag'] + g['elbow_lag'] + 0.25 + half, 0.2)), fore)
                worlds[chain[3]] = mul(hand, rest[chain[3]])
            # wings: a soft lift on each push-off, each a little later than the chest; swept back with speed
            for side, bone in WINGS.items():
                lag = g['wing_lag']
                lift = g['wing_flap'] * wave(step, 0.2 + lag, 0.2)
                wing = mul(rz(-side * (lift - 0.6 * g['wing_back'])), rx(-g['wing_back'] + g['wing_pitch'] * wave(step, 0.3 + lag, 0.2)), chest)
                worlds[bone] = mul(wing, rest[bone])
            body = [carrier[0] + sway, stand + g['crouch'] + sink[tick % n] - hop, carrier[2]]
            # the legs hang from the pelvis bone, which carries the hips' turn (not the robe's lag)
            worlds[PELVIS] = mul(hips, rest[PELVIS])
            pos = positions(rig, offsets, worlds, BODY, body)
            for thigh, shin, foot, side in LEGS:
                z, lift, pitch, stance = foot_track(g, t if side > 0 else t + 0.5, toe_off[foot])
                lift += hop if stance is None else 0.
                ankle = [npos[foot][0], npos[foot][1] - (carrier[1] - stand) - lift, npos[foot][2] + z]
                hip = pos[thigh]
                l1, l2 = lens[side]
                heel, tip = contacts[foot]

                def place(p):
                    pivot = tip if p > 0 else heel
                    turned = apply(rx(p), pivot)
                    return [ankle[i] + pivot[i] - turned[i] for i in range(3)]
                target = place(pitch)
                if stance is not None or lift < 3.:     # a foot in the air may trail at the full stretch of the leg; one on the floor must reach
                    reach = max(reach, legik.norm(legik.sub(target, hip)) / (l1 + l2))
                    across = (target[0] - hip[0]) ** 2 + (target[2] - hip[2]) ** 2
                    depth = math.sqrt(max(0., planted[side] ** 2 - across))
                    need[tick % n] = max(need[tick % n], target[1] - hip[1] - depth + sink[tick % n])
                if DEBUG and foot == 16:
                    print('T', tick, round(z, 1), round(lift, 1), [round(v) for v in target], [round(v) for v in hip], stance, round(sink[tick % n], 1), round(reach, 3))
                knee0 = npos[shin]
                bent = rx(KNEE_BEND)
                ankle0 = [knee0[i] + apply(bent, [npos[foot][j] - knee0[j] for j in range(3)])[i] for i in range(3)]
                pole = apply(ry(0.5 * yaw), [g['knee_out'] * side, 0, -1])
                worlds[thigh], worlds[shin] = leg(hip, target, l1, l2, pole, [npos[thigh], knee0, ankle0],
                                                  [rest[thigh], mul(bent, rest[shin])])
                worlds[foot] = mul(rx(pitch), rest[foot])
            worlds[PELVIS] = robe
            frames.append(to_pose(rig, reference, worlds, BODY, body, g['travel'] * tick / n, history))
        toe_off = latest
        wide = [max(need[(i + k) % n] for k in range(-2, 3)) for i in range(n)]
        sink = [sum(wt * wide[(i + k) % n] for k, wt in zip(range(-2, 3), (1, 4, 6, 4, 1))) / 16 for i in range(n)]
    assert reach < 1.0, reach
    return frames, reach


def finish(frames, n, g):
    """The loop's last pose is its first, the root at the whole stride."""
    out = [[list(b) for b in p] for p in frames]
    out[-1] = [list(b) for b in out[0]]
    out[-1][0] = list(frames[-1][0])
    return out


def clip(model, skeleton, name):
    g = CLIPS[name]
    frames, reach = build_frames(model, skeleton, g)
    frames = finish(frames, g['ticks'], g)
    frames, lift = lift_off_floor(model, skeleton, frames, FLOOR, BODY)
    n = g['ticks']
    events = []
    if g['travel']:
        events = [(t, 'sound', {'op': 'sound', 'frame': t + 1, 'bank': 1, 'note': NOTE}) for t in (0, n // 2)]
    return frames, events, reach, lift


def author(data, skeleton):
    model = mmd.MMD.parse(data, NB)
    model.type = SPECIES
    result = copy.deepcopy(model)
    streams, notes = {}, {}
    for slot, name in CLIP_OF_SLOT.items():
        frames, events, reach, lift = clip(model, skeleton, name)
        streams[slot] = len(result.anims.anims)
        result.anims.anims.append(mmd.encode_anim(frames, NB, 0, events, tol=1, repeats=False))
        notes[name] = dict(ticks=len(frames) - 1, reach=round(reach, 3), maximum_body_lift=round(lift, 1))
    for slot, twins in TWINS.items():
        for twin in twins:
            result.anims.table[twin] = streams[slot]
    for slot in CLIP_OF_SLOT:
        result.anims.table[slot] = streams[slot]
    for anim in result.anims.anims:
        anim.tail = getattr(anim, 'tail', b'')
    used = sorted({i for i in result.anims.table if i is not None})
    renumber = {i: k for k, i in enumerate(used)}
    result.anims.anims = [result.anims.anims[i] for i in used]
    result.anims.table = [None if i is None else renumber[i] for i in result.anims.table]
    result.anims.anims, result.anims.table = motioncyclelayer.share_identical_streams(result.anims.anims, result.anims.table)
    out = result.build()
    effective = mmd.MMD.parse(out, NB)
    effective.type = SPECIES
    assert effective.tmd.build() == model.tmd.build()
    return out, notes, changed_programs(model, effective)


def build(data, skeleton):
    """The celebrations' model (chibi proportions kept) with the four field clips written again -> (bytes, proof)."""
    from tools.models.field_animations import celebrations
    base, proof = celebrations.build(data, skeleton)
    exe = mmd.exe()
    kept = exe.skeleton[SPECIES], exe.bone_count[SPECIES]
    try:
        exe.skeleton[SPECIES] = skeleton
        exe.bone_count[SPECIES] = len(skeleton)
        out, notes, changed = author(base, skeleton)
    finally:
        exe.skeleton[SPECIES], exe.bone_count[SPECIES] = kept
    storage = motionstorage.require(out, NB)
    proof = dict(proof, preceding_recipe=dict(recipe='celebrations', output_sha256=proof['output_sha256']),
                 output_sha256=hashlib.sha256(out).hexdigest(), gait=notes, changed_slots=changed, storage=storage,
                 resident_bytes=[storage['resident_bytes'], storage['resident_limit']])
    proof['bytes'] = [proof['bytes'][0], len(out)]
    return out, proof


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads(next((ROOT / 'content/species').glob('312-*.json')).read_text())['model']['skeleton']
    out, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(out)
    text = json.dumps({k: proof[k] for k in ('gait', 'changed_slots', 'storage', 'bytes')}, indent=2, default=str) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
