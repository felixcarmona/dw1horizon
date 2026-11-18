"""Raidenmon's field gaits (species 336): walk, tired walk and run with the feet on the floor and a calmer body.

Raidenmon is a mechanical Kuwagamon-shaped import: body 1 (the torso carries the pelvis), left arm 2-3, tail 4-7, head 8,
medallions 9 and 23, right arm 10-14, right leg 15-18 (hip, knee, ankle, foot block) and left leg 19-22. The imported
clips rode the donor's rig: the legs hardly bent (the hips and knees turned a few degrees) and the whole foot block turned
up to 50 degrees about its own floor point, so the soles went up to 88 units under the floor in the walk, 82 in the
condition walk and 183 in the run, slid over the floor (105 % of the body's travel in the walk) and the trunk yawed and
rolled in sawtooth sweeps (the whole body turned 16 degrees in 10 ticks and snapped back) while the heavy arms and claws
whipped through 70 to 90 degrees every 21 ticks.

Here `quadruped.py` plants both feet (two-bone solve on the hip and knee, the foot block flat and still on the floor in
stance, heel strike and toe-off, a lifted swing), and the trunk, tail, head, arms and claws are the imported clip's own
channels, kept as the first harmonics of the donor's loop (a short Fourier series: the sawtooth edges and the tick-to-tick
noise go, the sway and swing that give the clip its character stay), their swing eased by a per-bone share and the
cycle slowed a little. The idle is the model's own; only its pelvis is raised on the ticks where it let the soles
sink a few units under the floor.

Offline: `tools/models/edit.py get 336` on the commit before this change, then
`python3 -m tools.models.field_animations.raidenmon_gait --source THAT.MMD --out AFTER.MMD` and `edit.py put 336 AFTER.MMD`.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet  # noqa: E402
import mmd  # noqa: E402
import motionstorage  # noqa: E402
from tools.models.field_animations import quadruped  # noqa: E402
from tools.models.field_animations.quadruped import mul, tr, rot, set_rot  # noqa: E402

SPECIES = 336
SOURCE = '0a3fb06f8b3ff035d18ff7b3eb5bd8879a63151a367c35092693eaa9bfcccd23'   # `edit.py get 336` before this change
TAU = 2 * math.pi
DEG = 4096 / 360
PELVIS = 1
LEGS = {'RH': (15, 16, 17, 1, False), 'LH': (19, 20, 21, -1, False)}
TOE_OF = {'RH': 18, 'LH': 22}
LEG_BONES = (15, 16, 17, 18, 19, 20, 21, 22)
TRUNK = tuple(b for b in range(1, 24) if b not in LEG_BONES)
DONOR = {}        # slot -> {(bone, channel): (mean, [(cos, sin) per harmonic])}


def series(frames, bone, k):
    """One angle channel of the donor's loop as degrees-free units (4096 a turn), unwrapped along the loop."""
    out, prev = [], None
    for f in frames:
        v = f[bone][k]
        if prev is not None:
            v = prev + ((v - prev + 2048) % 4096 - 2048)
        out.append(v)
        prev = v
    return out


def fourier(values, harmonics):
    n = len(values)
    mean = sum(values) / n
    terms = []
    for h in range(1, harmonics + 1):
        a = 2 / n * sum(v * math.cos(TAU * h * i / n) for i, v in enumerate(values))
        b = 2 / n * sum(v * math.sin(TAU * h * i / n) for i, v in enumerate(values))
        taper = 0.5 * (1 + math.cos(math.pi * h / (harmonics + 1)))     # the last harmonics count less: no ringing
        terms.append((a * taper, b * taper))
    return mean, terms


def donor_at(slot, bone, k, phase):
    mean, terms = DONOR[slot][bone, k]
    return mean + sum(a * math.cos(TAU * (h + 1) * phase) + b * math.sin(TAU * (h + 1) * phase) for h, (a, b) in enumerate(terms))


def body(rig, cfg, phase, pose, hist):
    """The donor's smoothed trunk, tail, head, arms and claws; the pelvis height is ours (the legs plant under it)."""
    rest = rig.rest
    slot, at = cfg['slot'], phase + cfg['shift']
    for b in TRUNK:
        for k in range(3, 6):
            mean, _ = DONOR[slot][b, k]
            share = cfg['swing'].get(b, cfg['share'])
            pose[b][k] = round(mean + share * (donor_at(slot, b, k, at) - mean))
    rate = cfg['bob_rate']
    pose[PELVIS][7] = rest[PELVIS][7] - cfg['height'] - cfg['bob'] * math.cos(TAU * rate * (phase - cfg['high']))
    for b, k, deg in cfg['rx']:
        pose[b][k] += round(deg * DEG)


ARMS = {'L': (2, (2, 3)), 'R': (10, (10, 11, 12, 13, 14))}     # shoulder, the bones that hang from it
MARGIN = 2


def arm_low(rig, pose, bones):
    """The lowest mesh point of an arm over the floor (y grows downwards: a positive value is under the floor)."""
    W = rig.world(pose)
    return max(rig.lowest(b, rig.R(W, b), [W[b][i][3] for i in range(3)]) for b in bones) + pose[0][7]


def keep_arms_up(rig, cfg, frames):
    """A swing that would drop a cannon or a claw under the floor lifts its shoulder (the pitch channel) just as far as it
    must, the lift eased along the loop so the arm never kicks."""
    ticks = len(frames) - 1
    for _, (shoulder, bones) in ARMS.items():
        need = []
        for pose in frames[:ticks]:
            lift, trial = 0, [list(b) for b in pose]
            if arm_low(rig, trial, bones) > -MARGIN:
                lo, hi = 0, 600
                for _ in range(14):
                    mid = (lo + hi) / 2
                    trial[shoulder][3] = pose[shoulder][3] - mid
                    lo, hi = (mid, hi) if arm_low(rig, trial, bones) > -MARGIN else (lo, mid)
                lift = hi
            need.append(lift)
        # ease the lift along the closed loop: widen it by two ticks, then two passes of a 1-2-1 average (radius two), which
        # never falls under the lift the arm needs at its own tick
        need = [max(need[(i + j) % ticks] for j in (-2, -1, 0, 1, 2)) for i in range(ticks)]
        for _ in range(2):
            need = [(need[i - 1] + 2 * need[i] + need[(i + 1) % ticks]) / 4 for i in range(ticks)]
        for pose, lift in zip(frames[:ticks], need):
            pose[shoulder][3] = round(pose[shoulder][3] - lift)
        for _ in range(20):       # settle: any tick still under the floor takes a little more
            worse = False
            for i, pose in enumerate(frames[:ticks]):
                over = arm_low(rig, pose, bones) + MARGIN
                if over > 0:
                    pose[shoulder][3] -= max(1, round(over * 1.2))
                    worse = True
            if not worse:
                break
    root = frames[ticks][0][8]
    frames[ticks] = [list(b) for b in frames[0]]
    frames[ticks][0][8] = root
    return frames


PROFILE = dict(
    species=SPECIES, name='Raidenmon', source=SOURCE,
    parents=[-1, 0, 1, 2, 1, 4, 5, 6, 1, 1, 1, 10, 11, 11, 11, 1, 15, 16, 17, 1, 19, 20, 21, 1],
    pelvis=PELVIS, chest=None, neck=None, head=8, tail=(), loose=(),
    legs=LEGS, toes={17: 18, 21: 22}, pole_world=True, rest_plane=True, pole={False: [0.0, 0.0, 1.0]},
    paw_rest={'RH': [0, 0, 0], 'LH': [0, 0, 0]},     # filled from the rig below
    sole={False: [0, 0, 0]},                            # filled from the rig below
    reach={'front': 0, 'hind': -85},      # the toe point stands ahead of the hip by the foot's length: the ankle sits under it
    fold={False: 100}, clear=2,
    speed_range={2: (15, 31), 3: (10, 20), 4: (35, 52)},
    body=body, floor=3, stance_slip=0.2,
    gaits={},
)
COMMON = dict(
    kind='walk', snap=False, arc=0.5, clear_ease=0.1, world_ease=True, fold_soft=10, slip=0.0, steps=('LH', 'RH'),
    reach={'front': 0, 'hind': 0}, lift={'front': 0, 'hind': 40}, curl={'front': 0, 'hind': 0}, peel={'front': 0, 'hind': 0},
    out={'front': 0, 'hind': 0}, wide={'front': 0, 'hind': 0}, track={'front': 0, 'hind': 0}, heel=0,
    harmonics=3, share=0.7, swing={}, shift=0.0, height=0, bob=3, bob_rate=2, high=0.1, rx=(), compose=keep_arms_up,
)
PROFILE['gaits'] = {
    2: dict(COMMON, slot=2, name='walk', ticks=24, speed=17,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.6, 'RH': 0.6}, lift={'front': 0, 'hind': 40}, shift=0.93),
    3: dict(COMMON, slot=3, name='tired walk', ticks=30, speed=11,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.66, 'RH': 0.66}, lift={'front': 0, 'hind': 28}, shift=0.93, share=0.6),
    4: dict(COMMON, slot=4, name='run', kind='trot', ticks=14, speed=40, world_ease=0.85, arc=1.0,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.38, 'RH': 0.38}, lift={'front': 0, 'hind': 70}, shift=0.93, share=0.35, rx=((2, 5, 10), (10, 5, -10))),
}


def prepare(model, skeleton):
    """Fill what is read off the rig: each foot block's toe point in the ankle's space (the sole's pivot)."""
    pose = animsheet.slot_frames(model, len(skeleton), 0)[0][0]
    for name, toe in TOE_OF.items():
        PROFILE['paw_rest'][name] = list(pose[toe][6:9])
    PROFILE['sole'][False] = list(pose[TOE_OF['RH']][6:9])


def lowest(rig, pose):
    W = rig.world(pose)
    return max(rig.lowest(b, rig.R(W, b), [W[b][i][3] for i in range(3)]) for b in rig.verts) + pose[0][7]


def raise_idle(data, skeleton):
    """The idle is the model's own, but its soles sank up to 5 units under the floor in the middle of the loop: the pelvis
    is raised by that much, eased along the loop (widened by two ticks, then smoothed), and nothing else changes."""
    n = len(skeleton)
    old = mmd.MMD.parse(data, n)
    old.type = SPECIES
    rig = quadruped.Rig(old, skeleton, PROFILE)
    frames, _, events = animsheet.slot_frames(old, n, 0)
    ticks = len(frames) - 1
    need = [max(0.0, lowest(rig, f) + MARGIN) for f in frames[:ticks]]
    need = [max(need[(i + j) % ticks] for j in (-3, -2, -1, 0, 1, 2, 3)) for i in range(ticks)]
    for _ in range(3):
        need = [(need[i - 1] + 2 * need[i] + need[(i + 1) % ticks]) / 4 for i in range(ticks)]
    out = []
    for f, up in zip(frames[:ticks], need):
        f = [list(b) for b in f]
        f[PELVIS][7] = round(f[PELVIS][7] - up)
        out.append(f)
    worst = max(lowest(rig, f) for f in out)
    out.append([list(b) for b in out[0]])
    index = old.anims.table[0]
    new = mmd.MMD.parse(data, n)
    new.type = SPECIES
    new.anims.anims[index] = mmd.encode_anim(out, n, loop_sample=0, events=events, tol=1)
    return new.build(), round(worst, 1)


def build(data, skeleton):
    old = mmd.MMD.parse(data, len(skeleton))
    old.type = SPECIES
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = len(skeleton)
    prepare(old, skeleton)
    n = len(skeleton)
    DONOR.clear()
    for slot, cfg in PROFILE['gaits'].items():
        frames = animsheet.slot_frames(old, n, slot)[0][:-1]
        DONOR[slot] = {(b, k): fourier(series(frames, b, k), cfg['harmonics']) for b in TRUNK for k in range(3, 6)}
    result, proof = quadruped.build(data, skeleton, PROFILE)
    result, proof['idle_lowest_point'] = raise_idle(result, skeleton)
    proof['storage'] = motionstorage.require(result, n)
    proof['output_sha256'] = hashlib.sha256(result).hexdigest()
    return result, proof


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    p.add_argument('--loose', action='store_true', help='diagnostic: no floor or slip bound')
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/336-raidenmon.json').read_text())['model']['skeleton']
    if a.loose:
        PROFILE.update(floor=999, stance_slip=9)
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof, indent=2, default=str) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        for c in proof['checks']:
            print(c['slot'], c['gait'], c['ticks'], 'speed', c['units_per_tick'], 'floor', c['lowest_point'], 'slip', c['stance_slip'], 'drop', c['body_drop'], 'short', c['unreached'])
        print('idle', proof['idle_lowest_point'], proof['storage']['resident_bytes'])


if __name__ == '__main__':
    main()
