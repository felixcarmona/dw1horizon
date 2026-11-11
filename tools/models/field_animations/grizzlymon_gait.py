"""Grizzlymon's field clips (species 296): a bear's idle, lumbering walk, dragging tired walk and loping run.

The rig (20 bones, forward is -z): bone 1 is the chest (everything hangs from it), 2 the head with 3 the jaw, 4 / 8 the
shoulder pads (right x>0, left x<0) carrying the forelegs 5-7 / 9-11 (an upper arm, a short forearm and the big clawed
gauntlet that stands on the floor), 12 the hips with the hind legs 13-15 / 17-19 (a long thigh down to the hock, the
shin, a flat plantigrade foot) and 16 the tail stub.

The imported walk, tired walk and run came from a biped and played on this four-footed body: the soles slid by 40-65 %
of the body's travel, the run was a 65-tick loop, and the body rode over the paws like a block while only the legs worked
(a machine walking under a statue). Here `quadruped.py` plants every paw (the soles are the targets, two-bone solves
reach them), the legs step in a lateral sequence (hind, then the fore paw on the same side) and `body` below moves what
is above them like a bear's weight: the chest sways and rolls over the loaded side while the hips roll the other way, the
shoulder blade rises over the planted fore paw, the head hangs low and follows the shoulder late, the tail trails. The
run is a rotary lope (the hind pair thrusts, a flight phase, the fore paws reach and land one after the other) with a
flexing spine. The idle is a slow breath, a weight shift and a head that looks about over planted paws.

Offline: `tools/models/edit.py get 296` on the commit before this change, then
`python3 -m tools.models.field_animations.grizzlymon_gait --source THAT.MMD --out AFTER.MMD` and `edit.py put 296 AFTER.MMD`.
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

TAU = 2 * math.pi
SPECIES = 296
SOURCE = '12607d3bc0410bf6383d28aca68f42b20df64205b31ab084d17b754e20d3106b'     # `edit.py get 296` before this change
CHEST, HEAD, JAW, HIPS, TAIL = 1, 2, 3, 12, 16
PADS = {'RF': 4, 'LF': 8}


def harm(phase, *terms):
    """A sum of cosines: terms are (amplitude, rate, delay in cycles)."""
    return sum(a * math.cos(TAU * rate * (phase - delay)) for a, rate, delay in terms)


def bump(u, centre, width):
    """A smooth periodic pulse (0..1) centred on `centre`, `width` cycles wide."""
    d = (u - centre + 0.5) % 1.0 - 0.5
    return math.cos(math.pi * d / width) ** 2 if abs(d) < width / 2 else 0.0


def breath(u):
    """One breath 0..1: a quicker inhale, a short hold, a slower exhale, a short rest."""
    u %= 1.0
    if u < 0.34:
        return smooth(u / 0.34)
    if u < 0.42:
        return 1.0
    return 1.0 - smooth((u - 0.42) / 0.5) if u < 0.92 else 0.0


def turn(rig, pose, bone, degrees, hist):
    """The bone's rest rotation turned by `degrees` (x pitch nose-down, y yaw to the left, z roll to the right)."""
    set_rot(pose, bone, mul(rot(degrees), mmd.rot_matrix(*rig.rest[bone][3:6])), hist)


def body(rig, cfg, phase, pose, hist):
    """Chest, hips, shoulder pads, head, jaw and tail for a cycle phase (the legs are placed after it)."""
    rest, c = rig.rest, cfg
    gallop = c['kind'] == 'gallop'
    rate = 1 if gallop or c['kind'] == 'idle' else 2        # the bounce comes once a cycle in a lope, twice in a walk
    bob = harm(phase, (c['bob'], rate, c['high']), (c['bob2'], 2 * rate, c['high'] + 0.03), (c['bob_side'], 1, c['high'] + 0.2))
    roll = harm(phase, (c['roll'], 1, c['roll_at']), (c['roll2'], 3, c['roll_at'] + 0.06))
    yaw = harm(phase, (c['yaw'], 1, c['yaw_at']), (c['yaw2'], 2, c['yaw_at'] + 0.1))
    pitch = c['tilt'] + harm(phase, (c['pitch'], rate, c['pitch_at']), (c['pitch1'], 1, c['pitch_at'] + 0.15))
    shift = harm(phase, (c['shift'], 1, c['roll_at'] + 0.02), (c['shift2'], 3, c['roll_at'] + 0.1))
    br = 0.0
    if c.get('breath'):
        B = c['breath']
        br = breath(phase * B['rate'] + B['at']) - 0.5
        pitch -= B['chest'] * br
    pitch -= c['swell'](phase)
    pose[CHEST][6] = rest[CHEST][6] + shift
    # a fore paw landing drops the whole front a little and the body shudders for a moment (heavy strikes)
    slam = 0.0
    for name in ('LF', 'RF'):
        slam += bump(phase, c['touchdown'][name] + c['impact_at'], c['impact_width'])
    pose[CHEST][7] = rest[CHEST][7] - c['height'] - bob + c['impact'] * slam
    turn(rig, pose, CHEST, [pitch, yaw, roll], hist)
    # the hips roll and turn against the chest (the spine twists), flex against its pitch
    hip_pitch = -c['flex'] * harm(phase, (1, rate, c['pitch_at'] + c['flex_at']))
    turn(rig, pose, HIPS, [hip_pitch - 0.6 * (pitch - c['tilt']), -c['hips'] * yaw, -c['hips_roll'] * roll], hist)
    # the shoulder blade rises over a planted fore paw (the hump) and the pad turns a little with the leg's swing
    for name, bone in PADS.items():
        stance, s = quadruped.leg_phase(cfg, name, phase)
        up = math.sin(math.pi * s) if stance else 0.0
        pose[bone][7] = rest[bone][7] - c['hump'] * up - c['pads'] * br
    # the head hangs low and follows the shoulders late
    lag = c['head_lag']
    hp = c['head_tilt'] + harm(phase, (c['nod'], rate, c['pitch_at'] + lag), (c['nod1'], 1, lag + 0.3)) \
        - c['steady'] * (pitch - c['tilt'])
    hy = harm(phase, (c['head_yaw'], 1, c['roll_at'] + lag + 0.5), (c['head_yaw2'], 2, c['yaw_at'] + lag)) - c['against'] * yaw
    hr = harm(phase, (c['head_roll'], 1, c['roll_at'] + lag)) - 0.4 * roll
    if c.get('look'):
        hy += c['look'](phase)
    hp += c['lower'](phase)
    if c.get('breath'):
        hp -= c['breath']['head'] * (breath(phase * c['breath']['rate'] + c['breath']['at'] - 0.07) - 0.5)
    hp += c.get('sniff', lambda u: 0.0)(phase)
    turn(rig, pose, HEAD, [hp, hy, hr], hist)
    # the head is pushed out ahead of the shoulders and lunges a little with each fore step
    pose[HEAD][8] = rest[HEAD][8] - c['thrust'] - harm(phase, (c['lunge'], rate, c['pitch_at'] + lag))
    pose[HEAD][7] = rest[HEAD][7] + c['head_drop']
    jaw = c['jaw'] * (0.5 + 0.5 * math.cos(TAU * rate * (phase - c['pitch_at'] - lag - 0.1))) + c.get('jaw_open', lambda u: 0.0)(phase)
    turn(rig, pose, JAW, [jaw, 0, 0], hist)
    turn(rig, pose, TAIL, [harm(phase, (c['tail'], rate, c['pitch_at'] + 0.2)) + c['tail_up'],
                           harm(phase, (c['tail_yaw'], 1, c['roll_at'] + 0.3)), 0], hist)


def look(u):
    """The head turns to one side, holds, comes back, then glances the other way a little."""
    return 22.0 * bump(u, 0.26, 0.3) - 18.0 * bump(u, 0.74, 0.3)


def lower(u):
    """The head sinks slowly over the loop as if sizing something up, and comes back up before the end."""
    return 9.0 * math.sin(math.pi * u) ** 2


def growl(u):
    """Two slow pulses of the jaw (the mouth opens a little)."""
    return 12.0 * bump(u, 0.52, 0.16) + 9.0 * bump(u, 0.80, 0.12)


def swell(u):
    """The chest swells with each growl."""
    return 2.5 * bump(u, 0.50, 0.2) + 2.0 * bump(u, 0.79, 0.16)


def sniff(u):
    """Two short bursts of quick small nose pitch."""
    return 3.0 * bump(u, 0.60, 0.1) * math.cos(TAU * 6 * u) + 2.0 * bump(u, 0.84, 0.08) * math.cos(TAU * 5 * u + 1.0)


COMMON = dict(kind='walk', swell=lambda u: 0.0, lower=lambda u: 0.0, pads=0.0, impact=0.0, impact_at=0.02, impact_width=0.25, thrust=0.0, lunge=0.0, head_drop=0.0,
               slip=0.0, snap=False, jerk=0.3, arc=1.0, clear_ease=0.4, fold_soft=10,
              reach={'front': 90, 'hind': 0}, track={'front': 0, 'hind': 0},
              peel={'front': 10, 'hind': 10}, curl={'front': 8, 'hind': 6}, lift={'front': 26, 'hind': 28},
              out={'front': 4, 'hind': 4}, wide={'front': 6, 'hind': 6}, heel=3, settle=0.0,
              height=0, bob=2.0, bob2=0.2, bob_side=0.4, high=0.0,
              roll=4.0, roll2=0.5, roll_at=0.3, yaw=2.5, yaw2=0.4, yaw_at=0.0,
              tilt=0, pitch=1.4, pitch1=0.5, pitch_at=0.1, shift=14, shift2=2.0,
              flex=1.2, flex_at=0.0, hips=0.8, hips_roll=1.0, hump=7,
              head_tilt=8, head_lag=0.1, nod=2.0, nod1=0.8, steady=0.4, head_yaw=4.0, head_yaw2=1.5, against=0.5, head_roll=1.5,
              jaw=2, tail=3, tail_up=0, tail_yaw=4)
TOUCHDOWN = {'LH': 0.0, 'LF': 0.25, 'RH': 0.5, 'RF': 0.75}
PROFILE = dict(
    species=SPECIES, name='Grizzlymon', source=SOURCE,
    parents=[-1, 0, 1, 2, 1, 4, 5, 6, 1, 8, 9, 10, 1, 12, 13, 14, 12, 12, 17, 18],
    pelvis=CHEST, chest=CHEST, head=HEAD, tail=(), loose=(),
    legs={'RF': (5, 6, 7, 1, True), 'LF': (9, 10, 11, -1, True), 'RH': (13, 14, 15, 1, False), 'LH': (17, 18, 19, -1, False)},
    paw_rest={'RF': [0, 1, 0], 'LF': [0, 1, 0], 'RH': [0, 0, -1], 'LH': [0, 0, -1]},
    flat_shin={False: 0.95}, pole_world=True, pole={True: [0, 0.3, 1], False: [0, 0, 1]},
    sole={True: [0.0, 71.4, 64.8], False: [0.0, 25.1, -83.7]},
    reach={'front': -123, 'hind': -11},
    fold={True: 97, False: 130}, clear=2,
    body=body, floor=3, stance_slip=0.35,
    gaits={
        0: dict(COMMON, kind='idle', name='idle', ticks=96, speed=0, touchdown={'LH': 0.0, 'LF': 0.55, 'RH': 0.0, 'RF': 0.0}, duty={'LH': 1.0, 'LF': 0.8, 'RH': 1.0, 'RF': 1.0},
                steps=(), lift={'front': 28, 'hind': 0}, peel={'front': 0, 'hind': 0}, bob=0.0, bob2=0.0, bob_side=0.0, roll=1.2, roll2=0.0, roll_at=0.15, yaw=1.0, yaw2=0.0,
                tilt=0, pitch=0.0, pitch1=0.0, shift=5.0, shift2=0.0, flex=0.0, hips=0.5, hips_roll=0.8, hump=0, head_tilt=18, nod=0.0, nod1=1.0, thrust=10, head_drop=8, lower=lower, swell=swell, pads=2.5, jaw_open=growl,
                steady=0.0, head_yaw=2.0, head_yaw2=0.0, head_roll=1.0, jaw=0.0, tail=1.0, tail_yaw=3.0, look=look, sniff=sniff,
                breath=dict(rate=2, at=0.0, chest=3.4, head=3.5)),
        2: dict(COMMON, name='walk', ticks=24, speed=15, slip=0.1, touchdown=TOUCHDOWN, reach={'front': 100, 'hind': 16},
                head_tilt=22, thrust=18, lunge=8, head_drop=14, head_yaw=12, roll=4.5, yaw=3, shift=15, hump=8, impact=10, jaw=5,
                lift={'front': 30, 'hind': 28}, curl={'front': 6, 'hind': 6}, peel={'front': 6, 'hind': 10},
                duty={'LH': 0.48, 'RH': 0.48, 'LF': 0.42, 'RF': 0.42}, steps=('LH', 'LF', 'RH', 'RF')),
        3: dict(COMMON, name='tired walk', ticks=28, speed=11, slip=0.1, touchdown={'LH': 0.0, 'LF': 0.27, 'RH': 0.5, 'RF': 0.77},
                reach={'front': 100, 'hind': 10}, duty={'LH': 0.52, 'RH': 0.52, 'LF': 0.44, 'RF': 0.44}, steps=('LH', 'LF', 'RH', 'RF'),
                lift={'front': 14, 'hind': 14}, peel={'front': 4, 'hind': 4}, curl={'front': 3, 'hind': 3}, height=10, bob=1.5,
                roll=6.0, shift=14, yaw=3.0, head_tilt=24, nod=1.5, head_yaw=9.0, hump=5, tail_up=-10,
                thrust=14, lunge=6, head_drop=10, impact=8, jaw=5),
        4: dict(COMMON, kind='gallop', name='run', ticks=15, speed=38, slip=0.1,
                touchdown={'RH': 0.0, 'LH': 0.07, 'LF': 0.36, 'RF': 0.46},
                reach={'front': 100, 'hind': 10}, duty={'RH': 0.24, 'LH': 0.24, 'LF': 0.22, 'RF': 0.22}, steps=('RH', 'LF'),
                lift={'front': 50, 'hind': 40}, peel={'front': 14, 'hind': 14}, curl={'front': 10, 'hind': 10}, out={'front': 8, 'hind': 8},
                height=8, tilt=2, bob=13, bob2=0.2, bob_side=0.0, high=0.8, pitch=5, pitch1=0.0, pitch_at=0.4, flex=6, flex_at=0.1,
                roll=4, roll_at=0.4, yaw=3, yaw_at=0.2, shift=6, head_tilt=20, nod=3, nod1=0, steady=0.6, head_yaw=3, hump=9, tail_up=8, jaw=8,
                thrust=16, lunge=8, head_drop=9, impact=6, impact_width=0.3),
    },
)


def build(data, skeleton):
    return quadruped.build(data, skeleton, PROFILE)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/296-grizzlymon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof, indent=2) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
