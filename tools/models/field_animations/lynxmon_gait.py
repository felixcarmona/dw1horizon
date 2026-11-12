"""Lynxmon's field gaits (species 323): walk, tired walk and run with four legs that read as four legs.

Lynxmon is a flame-furred lynx. Its rig (24 bones, forward is -z): bone 1 is the chest (everything hangs from it), 2 the
neck with 3 the head and 4 the jaw, 5-8 the right foreleg and 9-12 the left one (shoulder, elbow, wrist, claws), 13 the
hips (a child of the chest at the same point) with the tail 14-15 and the hind legs 16-19 (right) and 20-23 (left).

The problem: when it moves, the legs and the other limbs are hard to tell apart; it reads as one uniform mass. The
texture paints the legs, the body and the tufts with the same flame pattern, so the picture offers no colour or shading
to tell a limb from the body; what is left to the clips is the silhouette and the gaps of open floor under the belly.
The imported walk, tired walk and run threw that away:

- the paws swing 146 to 263 units up, the belly's underside is 165 units over the floor: a swinging paw rose into the
  torso and vanished into the body's flames on most ticks;
- the feet came in towards the midline (the fore paws from x 209 at rest to 95 to 164, the hind paws from 140 to 74
  to 155), so the near and far legs and the fore and hind legs of one side stood on the same ground;
- the cycles were 16, 16 and 14 ticks, the soles slid (46 % of the body's travel at worst in the walk and tired walk,
  115 % in the run) and the tired walk and the run were faster than any native partner (23.6 and 69.4 units a tick).

Here `quadruped.py` plants each of the four paws (two-bone solves on the rig's own link lengths, in its own bend
planes) and the clips keep the four limbs apart in the picture: a lateral-sequence walk (hind, then the fore paw on the
same side, a quarter of a cycle later, then the other side), a low swing that stays under the belly, a stance about as
wide as the rest pose (the fore paws clear of the hind ones by their stagger along the body and the open floor under the belly, not by
spreading sideways),
and a rotary lope for the run with the hind pair and the fore pair split. The body is written by hand and keeps
moving against the legs: the chest rolls over the loaded side while the hips twist the other way, the shoulders ride
up over the planted fore paw, the neck and head follow late, the jaw works and the two-link tail trails the hips. The
walks are two different cycles long (the lift, the bob and the sway differ and ease into each other) and the neck, head,
jaw and tail follow through by a spring each. Nothing but the clips changes: the mesh is exact, and no species data.

Offline: `tools/models/edit.py get 323` on the commit before this change, then
`python3 -m tools.models.field_animations.lynxmon_gait --source THAT.MMD --out AFTER.MMD` and `edit.py put 323 AFTER.MMD`.
"""
import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import mmd  # noqa: E402
from tools.models.field_animations import quadruped  # noqa: E402
from tools.models.field_animations.quadruped import mul, rot, set_rot, smooth  # noqa: E402

SPECIES = 323
SOURCE = 'f3dd4bea5dda7c497cfcac090c407b0c77972082813273417e0ab371d02978bc'     # `edit.py get 323` before this change
TAU = 2 * math.pi
CHEST, NECK, HEAD, JAW, HIPS = 1, 2, 3, 4, 13
TAIL = (14, 15)
SHOULDERS = {'RF': 5, 'LF': 9}
TOE_OF = {'RF': 8, 'LF': 12, 'RH': 19, 'LH': 23}
LEGS = {'RF': (5, 6, 7, 1, True), 'LF': (9, 10, 11, -1, True), 'RH': (16, 17, 18, 1, False), 'LH': (20, 21, 22, -1, False)}


def harm(phase, *terms):
    """A sum of cosines: terms are (amplitude, rate, delay in cycles)."""
    return sum(a * math.cos(TAU * rate * (phase - delay)) for a, rate, delay in terms)


DEG = 4096 / 360


def turn(rig, pose, bone, degrees, hist, carry=None):
    """The bone's carriage (the angles in degrees of `carry`, else its rest rotation) turned by `degrees` (x pitch
    nose-down, y yaw, z roll)."""
    base = mmd.rot_matrix(*rig.rest[bone][3:6]) if carry is None else mmd.rot_matrix(*[a * DEG for a in carry])
    set_rot(pose, bone, mul(rot(degrees), base), hist)


def body(rig, cfg, phase, pose, hist):
    """Chest, hips, shoulders, neck, head, jaw and tail for a cycle phase (the legs are placed after it)."""
    rest, c = rig.rest, cfg
    rate = 1 if c['kind'] == 'gallop' else 2            # a bob comes once a cycle in a lope, twice in a walk
    bob = harm(phase, (c['bob'], rate, c['high']), (c['bob2'], 2 * rate, c['high'] + 0.03), (c['bob_side'], 1, c['high'] + 0.2))
    roll = harm(phase, (c['roll'], 1, c['roll_at']), (c['roll2'], 3, c['roll_at'] + 0.06))
    yaw = harm(phase, (c['yaw'], 1, c['yaw_at']), (c['yaw2'], 2, c['yaw_at'] + 0.1))
    pitch = c['tilt'] + harm(phase, (c['pitch'], rate, c['pitch_at']), (c['pitch1'], 1, c['pitch_at'] + 0.15))
    shift = harm(phase, (c['shift'], 1, c['roll_at'] + 0.02), (c['shift2'], 3, c['roll_at'] + 0.1))
    pose[CHEST][6] = rest[CHEST][6] + shift
    pose[CHEST][7] = rest[CHEST][7] - c['height'] - bob
    turn(rig, pose, CHEST, [pitch, yaw, roll], hist)
    # the hips twist and roll against the chest (the spine winds up), flexing against its pitch
    flex = -c['flex'] * harm(phase, (1, rate, c['pitch_at'] + c['flex_at']))
    turn(rig, pose, HIPS, [flex - 0.6 * (pitch - c['tilt']), -c['hips'] * yaw, -c['hips_roll'] * roll], hist)
    # the neck and the head follow the chest late and keep most of their gaze
    lag = c['head_lag']
    nod = harm(phase, (c['nod'], rate, c['pitch_at'] + lag), (c['nod1'], 1, lag + 0.3))
    steady = c['steady'] * (pitch - c['tilt'])
    look = c['look'](phase) if c.get('look') else 0.0
    turn(rig, pose, NECK, [0.5 * nod - 0.5 * steady + c['lower'](phase) * 0.5,
                           0.5 * harm(phase, (c['head_yaw'], 1, c['roll_at'] + lag + 0.5)) - 0.5 * c['against'] * yaw + 0.5 * look,
                           -0.4 * roll + harm(phase, (c['head_roll'], 1, c['roll_at'] + lag))], hist, c['carry'][NECK])
    turn(rig, pose, HEAD, [0.7 * nod - 0.5 * steady + c['lower'](phase) * 0.5,
                           0.5 * harm(phase, (c['head_yaw'], 1, c['roll_at'] + lag + 0.5)) - 0.5 * c['against'] * yaw + 0.5 * look,
                           -0.2 * roll + 0.6 * harm(phase, (c['head_roll'], 1, c['roll_at'] + lag + 0.1))], hist, c['carry'][HEAD])
    jaw = c['jaw'] * (0.5 + 0.5 * math.cos(TAU * rate * (phase - c['pitch_at'] - lag - 0.1))) + c['jaw_open'](phase)
    turn(rig, pose, JAW, [jaw, 0, 0], hist)
    # the tail hangs from the hips: each link a few ticks later than the one before
    for k, b in enumerate(TAIL):
        late = c['tail_lag'] * (k + 1)
        grow = 1.0 + 0.8 * k
        pitch_t = grow * harm(phase - late, (c['tail'], rate, c['pitch_at'] + 0.2), (c['tail1'], 1, 0.0))
        yaw_t = grow * harm(phase - late - 0.02, (c['tail_yaw'], 1, c['yaw_at'] + 0.5), (c['tail_yaw2'], 3, c['yaw_at'] + 0.55))
        turn(rig, pose, b, [pitch_t, yaw_t, 0], hist, c['carry'][b])


def look(u):
    """The head turns to one side, holds, comes back, then glances the other way a little."""
    def bump(c, w):
        d = (u - c + 0.5) % 1.0 - 0.5
        return math.cos(math.pi * d / w) ** 2 if abs(d) < w / 2 else 0.0
    return 14.0 * bump(0.3, 0.3) - 10.0 * bump(0.78, 0.3)


COMMON = dict(kind='walk', lower=lambda u: 0.0, jaw_open=lambda u: 0.0, look=None,
              slip=0.1, snap=False, jerk=0.3, arc=0.55, clear_ease=0.15, world_ease=0.2, fold_soft=10, heel=3, settle=0.0,
              reach={'front': 0, 'hind': 0}, track={'front': -24, 'hind': -10},
              peel={'front': 0, 'hind': -3}, curl={'front': 0, 'hind': 0}, lift={'front': 55, 'hind': 52},
              out={'front': 4, 'hind': 4}, wide={'front': 8, 'hind': 4},
              height=0, bob=7.0, bob2=1.5, bob_side=2.0, high=0.0,
              roll=7.0, roll2=1.5, roll_at=0.3, yaw=6.0, yaw2=1.2, yaw_at=0.0,
              tilt=0, pitch=3.0, pitch1=1.0, pitch_at=0.1, shift=14, shift2=2.0,
              flex=3.0, flex_at=0.0, hips=1.4, hips_roll=1.4,
              head_lag=0.1, nod=4.0, nod1=1.5, steady=0.4, head_yaw=8.0, against=0.5, head_roll=3.0,
              jaw=3, tail=6, tail1=3, tail_lag=0.07, tail_yaw=14, tail_yaw2=2)
# the imported clips' carriage of the neck, head and tail (the mean angles in degrees over each clip: pitch, yaw, roll): the
# field clips keep it and move around it
CARRY = {2: {NECK: (-8.2, -1.4, 1.1), HEAD: (3.7, 0, 0), 14: (15.7, 0, 0), 15: (-26.1, 13.7, -3.7)},
         3: {NECK: (36.0, 2.3, -4.6), HEAD: (8.5, 1.3, 0), 14: (-26.9, 3.3, 1.3), 15: (-27.1, 17.0, -3.3)},
         4: {NECK: (10.7, 0, 0), HEAD: (-13.4, 0, 0), 14: (22.7, 0, 0), 15: (-20.8, 18.8, -2.4)}}
WALK_TOUCH = {'LH': 0.0, 'LF': 0.25, 'RH': 0.5, 'RF': 0.75}
PROFILE = dict(
    species=SPECIES, name='Lynxmon', source=SOURCE,
    parents=[-1, 0, 1, 2, 3, 1, 5, 6, 7, 1, 9, 10, 11, 1, 13, 14, 13, 16, 17, 18, 13, 20, 21, 22],
    pelvis=CHEST, chest=CHEST, head=HEAD, tail=(), loose=(),
    legs=LEGS, pole_world=True, rest_plane=True, mirror_paws=True,
    pole={True: [0.64, -0.3, 0.70], False: [0.62, -0.75, 0.33]},
    paw_rest={'RF': [0, 0, 0], 'LF': [0, 0, 0], 'RH': [0, 0, 0], 'LH': [0, 0, 0]},     # filled from the rig below
    sole={True: [0, 0, 0], False: [0, 0, 0]},
    reach={'front': -86, 'hind': 0},       # the stance centre: the claws' place (shoulder / hip z + this)
    fold={True: 120, False: 110}, clear=2,
    speed_range={0: (0, 0), 2: (15, 31), 3: (10, 20), 4: (35, 52)},
    body=body, floor=3, stance_slip=0.35,
    gaits={},
)
PROFILE['gaits'] = {
    2: dict(COMMON, name='walk', ticks=18, speed=26, leg_reach={'LH': 25}, touchdown=WALK_TOUCH, carry=CARRY[2], steps=('LH', 'LF', 'RH', 'RF'),
            duty={'LH': 0.6, 'LF': 0.58, 'RH': 0.6, 'RF': 0.58}, leg_lift={'LH': 1.0, 'LF': 0.92, 'RH': 0.9, 'RF': 1.0}),
    3: dict(COMMON, name='tired walk', ticks=24, speed=15, leg_reach={'LH': 36}, touchdown={'LH': 0.0, 'LF': 0.27, 'RH': 0.5, 'RF': 0.77},
            carry=CARRY[3], steps=('LH', 'LF', 'RH', 'RF'), duty={'LH': 0.66, 'LF': 0.62, 'RH': 0.66, 'RF': 0.62},
            leg_lift={'LH': 1.0, 'LF': 0.9, 'RH': 0.85, 'RF': 1.0}, height=0, bob=5, bob2=1.0, roll=7, shift=16, pitch=2.5, nod=0.0, nod1=0.0, steady=0.8, head_roll=0.0,
            lift={'front': 30, 'hind': 28}, wide={'front': 10, 'hind': 0}, tail=3, tail1=2, tail_yaw=10, head_yaw=2),
    4: dict(COMMON, name='run', kind='gallop', ticks=16, speed=46, touchdown={'RH': 0.0, 'LH': 0.16, 'LF': 0.38, 'RF': 0.5},
            carry=CARRY[4], steps=('RH', 'LF'), duty={'RH': 0.26, 'LH': 0.26, 'LF': 0.24, 'RF': 0.24},
            leg_lift={'RH': 1.0, 'LH': 0.9, 'LF': 1.0, 'RF': 0.9}, lift={'front': 85, 'hind': 90}, out={'front': 8, 'hind': 8}, world_ease=0.85, wide={'front': 12, 'hind': 12},
            bob=22, bob2=3, bob_side=0, high=0.8, pitch=11, pitch1=0, pitch_at=0.4, flex=10, flex_at=0.1, roll=3, roll_at=0.4,
            yaw=3, yaw_at=0.2, shift=6, nod=6, nod1=0, steady=0.6, head_yaw=3, tail=10, tail1=4, tail_yaw=8, jaw=6),
}
# Every walking clip is two cycles long: the second one lifts, bobs and sways a little differently and the clip eases from the
# first into it and back, so no two steps are alike; then the neck, head, jaw and tail follow through by a loose spring each.
OTHER = {
    2: dict(scale=dict(bob=1.3, roll=1.2, pitch=1.25, shift=1.15, nod=1.3), leg_lift={'LH': 0.92, 'LF': 1.0, 'RH': 1.0, 'RF': 0.9}),
    3: dict(scale=dict(bob=1.4, roll=1.25, pitch=1.2, shift=1.15, nod=1.3), leg_lift={'LH': 0.9, 'LF': 1.0, 'RH': 1.0, 'RF': 0.88}),
    4: dict(scale=dict(bob=1.1, pitch=0.9, flex=1.1, nod=1.2), leg_lift={'RH': 0.92, 'LH': 1.0, 'LF': 0.92, 'RF': 1.0}),
}
FOLLOW = {NECK: (0.55, 0.5), HEAD: (0.5, 0.45), JAW: (0.45, 0.35), 14: (0.45, 0.4), 15: (0.38, 0.33)}   # rad per tick, damping


def spring(values, rate, damping):
    """A loose second-order follower of a cyclic sequence (run round three times so the loop settles)."""
    n = len(values)
    y, v = values[0], 0.0
    out = []
    for i in range(3 * n):
        v += rate * rate * (values[i % n] - y) - 2 * damping * rate * v
        y += v
        out.append(y)
    return out[-n:]


def blend(a, b, w):
    out = []
    for ba, bb in zip(a, b):
        row = list(ba)
        for i in range(3, 6):
            row[i] = ba[i] + ((bb[i] - ba[i] + 2048) % 4096 - 2048) * w
        for i in range(6, 9):
            row[i] = ba[i] + (bb[i] - ba[i]) * w
        out.append(row)
    return out


def compose(rig, cfg, frames_a):
    """Two cycles from cycle A (`frames_a`) and the cycle the gait's `other` settings give, eased into each other."""
    ticks, speed = cfg['ticks'], cfg['speed']
    frames_b, _ = quadruped.gait(rig, dict(cfg, **cfg['other']))
    out = []
    for i in range(2 * ticks):
        w = 0.5 - 0.5 * math.cos(math.pi * i / ticks)
        pose = blend(frames_a[i % ticks], frames_b[i % ticks], w)
        pose[0][8] = -round(speed * i)
        out.append(pose)
    for b, (rate, damping) in FOLLOW.items():
        for ch in (3, 4, 5):
            seq = [out[i][b][ch] for i in range(2 * ticks)]
            mixed = spring(seq, rate, damping)
            for i in range(2 * ticks):
                out[i][b][ch] = mixed[i]
    closing = [list(v) for v in out[0]]
    closing[0][8] = -round(speed * 2 * ticks)
    out.append(closing)
    return out


for slot, spec in OTHER.items():
    cfg = PROFILE['gaits'][slot]
    other = {k: v for k, v in spec.items() if k != 'scale'}
    other.update({k: cfg[k] * f for k, f in spec['scale'].items()})
    cfg.update(cycles=2, compose=compose, other=other)


def prepare(model, skeleton):
    """Fill what is read off the rig: each foot's toe direction and the pivot of the sole (the claw point)."""
    import animsheet
    pose = animsheet.slot_frames(model, len(skeleton), 0)[0][0]
    for name, toe in TOE_OF.items():
        PROFILE['paw_rest'][name] = list(pose[toe][6:9])
    PROFILE['sole'][True] = list(pose[TOE_OF['RF']][6:9])
    PROFILE['sole'][False] = list(pose[TOE_OF['RH']][6:9])


def build(data, skeleton):
    old = mmd.MMD.parse(data, len(skeleton))
    old.type = SPECIES
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = len(skeleton)
    prepare(old, skeleton)
    return quadruped.build(data, skeleton, PROFILE)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/323-lynxmon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof, indent=2, default=str) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
