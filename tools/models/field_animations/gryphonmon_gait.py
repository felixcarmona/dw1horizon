"""Gryphonmon's field clips (species 293): a calm breathing idle, a lion's walk, a heavy tired walk and a bounding run.

Gryphonmon is a winged lion with an eagle's head: a pelvis (bone 1) carrying the hind legs (19-21 right, 22-24 left: hip,
hock, flat paw) and a four-bone tail whose last bone is the snake head (2-5), a chest (6) carrying the forelegs (9-11 and
12-14), the neck and mane (7), the head (8) and two wings (15-16 right, 17-18 left: an inner arm and an outer fan). The
imported walk dragged the paws (slip 44-53 % of the body's travel in stance, 73 % in the tired walk), the legs hardly
moved under a body that flapped its wings while walking, and the idle repeated the walk's pose.

Here the legs come from `quadruped.py` (four planted paws, a lateral-sequence walk, a rotary gallop) and the rest of the
animal is written around them:

- Walk (slot 2, 24 ticks at 16 units per tick): left hind, left fore, right hind, right fore a quarter cycle apart, 62 %
  stance, each paw flat and still while the body passes over it. The body bobs and rolls with the steps, the head
  steadies against it and follows late, the tail swings with a delay along its four bones, and the wings beat once a
  stride: a quick downstroke and a slower upstroke of the whole wing about its hinge, the fan trailing the arm.
- Tired walk (slot 3, 28 ticks at 11): lower and slower, 70 % stance, the head hanging, the tail trailing low and the
  wings beating low and slowly.
- Run (slot 4, 16 ticks at 38): a gallop (hind pair, then the fore pair) with a gathered flight, the spine flexing, the
  wings beating wide once a bound, the tail streaming.
- Idle (slot 0, 96 ticks): all four paws planted, two slow breaths, a weight shift, a look about, a wing ruffle and
  two blinks, the tail swaying with a lag.

    python -m tools.models.field_animations.gryphonmon_gait --source SRC.MMD --out OUT.MMD
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
import mmd  # noqa: E402
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402
from tools.models.field_animations import quadruped  # noqa: E402

SPECIES = 293
SOURCE = '3a5ffd5e8fa213f759112da5040264e5c039ab0c05e3d9a8f6cda142ecbf89b6'    # `edit.py get 293` before this change
DEG = quadruped.DEG
TAU = 2 * math.pi
IDLE_TICKS = 96
PELVIS, CHEST, NECK, HEAD = 1, 6, 7, 8
WINGS = {15: 1, 16: 1, 17: -1, 18: -1}       # inner arm and outer fan of each wing; +1 right (x > 0), -1 left
BLINK = ((0, 45), (1, 57), (3, 45), (4, 48))   # the source's eye frames: (tick offset, source x), then open again


def wave(phase, delay=0.0, rate=1):
    return math.cos(TAU * rate * (phase - delay))


def bump(phase, centre, width):
    """A smooth periodic pulse (0..1) centred on `centre`, `width` cycles wide."""
    d = (phase - centre + 0.5) % 1.0 - 0.5
    return math.cos(math.pi * d / width) ** 2 if abs(d) < width / 2 else 0.0


def extra(rig, cfg, phase, pose):
    """Wings, the weight shift and the head's look, which the quadruped module has no row for. Wing angles are added to the
    rest pose: z swings a wing down (right +, left -), x tilts its sheet, y sweeps it."""
    rest = rig.rest
    w = cfg['wing']
    rate = cfg.get('wing_rate', 1)
    for bone, side in WINGS.items():
        tip = bone in (16, 18)
        # the whole wing beats about the chest's z hinge: the arm is the stroke, the fan is the same stroke a little later
        # and larger, so it trails on the way down and the way up (one chain, one hinge axis, no sideways pitch)
        down = w['fan_centre'] + w['fan'] * stroke(phase - w['at'] - w['lag'], rate) if tip \
            else w['centre'] + w['arm'] * stroke(phase - w['at'], rate)
        down += w.get('ruffle', lambda p, t: 0.0)(phase, tip)
        pose[bone][5] = rest[bone][5] + round(side * down * DEG)
        if not tip:        # the arm stands a little off the body, so the raised wing clears the shoulder and neck
            pose[bone][4] = rest[bone][4] + round(side * w['sweep'] * DEG)
    pose[PELVIS][6] = rest[PELVIS][6] + cfg.get('shift', 0.0) * wave(phase, 0.05, 1)
    if cfg.get('sink'):        # settle into the paws and rise again (units)
        pose[PELVIS][7] += cfg['sink'](phase)
    if cfg.get('chest'):       # the chest pitches forward as it settles (degrees)
        pose[CHEST][3] += round(cfg['chest'](phase) * DEG)
    if cfg.get('flick'):       # a quick lagged flick along the tail chain (degrees at the first joint)
        for k, b in enumerate(PROFILE['tail']):
            pose[b][4] += round(cfg['flick'](phase - 0.02 * k) * (1 + 0.5 * k) * DEG)
    look = cfg.get('look')
    if look:
        pose[HEAD][4] += round(look(phase) * DEG)
        pose[NECK][4] += round(0.5 * look(phase - 0.02) * DEG)


def stroke(phase, rate):
    """A wing beat, -1 raised to +1 lowered: the downstroke takes about 40% of the beat and the upstroke the rest."""
    u = rate * phase
    return -math.cos(TAU * (u - 0.14 * math.cos(TAU * u)))


def ruffle(phase, tip):
    """A slow wing stretch: both wings rise and open wide, hold, then fold back with a small settling overshoot; the fan
    follows its arm a little late."""
    lag = 0.03 if tip else 0.0
    return -(24.0 if tip else 14.0) * bump(phase, 0.70 + lag, 0.34) + (3.0 if tip else 2.0) * bump(phase, 0.90 + lag, 0.1)


def glance(phase):
    """The beak scans: a wide slow turn to one side, a long hold, back through the middle to the other side, a small
    last glance."""
    return 8.0 * bump(phase, 0.20, 0.24) - 9.0 * bump(phase, 0.50, 0.22) + 4.0 * bump(phase, 0.88, 0.1)


def sink(phase):
    """Settling into the paws: the body dips once and rises."""
    return -14.0 * bump(phase, 0.38, 0.24)


def chest(phase):
    return 2.5 * bump(phase, 0.38, 0.2) - 2.0 * bump(phase, 0.72, 0.3)


def flick(phase):
    """One quick, small flick of the tail tip."""
    return 9.0 * bump(phase, 0.08, 0.07) - 5.0 * bump(phase, 0.13, 0.06)


WING_WALK = dict(at=0.0, lag=0.12, centre=-8.0, arm=24.0, fan_centre=0.0, fan=26.0, sweep=-5.0)
WING_TIRED = dict(at=0.2, lag=0.12, centre=8.0, arm=15.0, fan_centre=4.0, fan=16.0, sweep=-5.0)
WING_RUN = dict(at=0.0, lag=0.1, centre=-10.0, arm=28.0, fan_centre=0.0, fan=28.0, sweep=-8.0)
WING_IDLE = dict(at=0.15, lag=0.08, centre=0.0, arm=10.0, fan_centre=0.0, fan=15.0, sweep=-5.0, ruffle=ruffle)


def events(slot, total):
    """The open eyes, and one blink in the walks (the idle's own are added when it is made)."""
    base = (0, 'tex', dict(op='tex', frame=1, src=(48, 64), size=(4, 16), dst=(16, 32)))
    at = {2: 9, 3: 13, 4: 5}[slot]
    return [base] + [(at + k, 'tex', dict(op='tex', frame=at + k + 1, src=(x, 64 if x == 48 else 16), size=(4, 16), dst=(16, 32)))
                     for k, x in BLINK]


PROFILE = dict(
    species=SPECIES, name='Gryphonmon', source=SOURCE,
    parents=[-1, 0, 1, 2, 3, 4, 1, 6, 7, 6, 9, 10, 6, 12, 13, 6, 15, 6, 17, 1, 19, 20, 1, 22, 23],
    pelvis=PELVIS, chest=CHEST, neck=NECK, head=HEAD,
    # (upper, lower, paw, side (+1 right), front)
    legs={'RF': (9, 10, 11, 1, True), 'LF': (12, 13, 14, -1, True), 'RH': (19, 20, 21, 1, False), 'LH': (22, 23, 24, -1, False)},
    tail=(2, 3, 4, 5), loose=(),
    pole={True: [0.0, 0.0, 1.0], False: [0.0, 0.0, 1.0]},     # elbows and hocks fold backwards
    sole={True: [0, 46, -40], False: [0, 41, -50]},           # the middle of the flat paw (paw bone space)
    reach={'front': -45, 'hind': 5},
    fold={True: 95, False: 105},
    clear=3, extra=extra, events=events,
    gaits={
        2: dict(name='walk', kind='walk', ticks=22, speed=16, wing=WING_WALK,
                touchdown={'LH': 0.0, 'LF': 0.25, 'RH': 0.5, 'RF': 0.75},
                duty={'LH': 0.58, 'RH': 0.58, 'RF': 0.58, 'LF': 0.58},
                lift={'front': 50, 'hind': 36}, curl={'front': 24, 'hind': 12}, peel={'front': 16, 'hind': 16},
                reach={'front': 0, 'hind': 0}, out={'front': 10, 'hind': 8}, snap=False, slip=0.04, arc=0.8, jerk=0.7,
                track={'front': -10, 'hind': -25},
                height=4, tilt=0, chest_up=0, neck=14, nod=2.5, bob=3, pitch=1.2, flex=1.5, roll=3.5, yaw=3.5, head=0.9,
                lag=(0.06, 0.12), tail=9, tail_lag=0.07, tail_whip=0.5, steps=('LH', 'LF', 'RH', 'RF')),
        3: dict(name='tired walk', kind='walk', ticks=28, speed=11, wing=WING_TIRED,
                touchdown={'LH': 0.0, 'LF': 0.25, 'RH': 0.5, 'RF': 0.75},
                duty={'LH': 0.7, 'RH': 0.7, 'RF': 0.7, 'LF': 0.7},
                lift={'front': 26, 'hind': 22}, curl={'front': 10, 'hind': 8}, peel={'front': 10, 'hind': 10},
                reach={'front': 0, 'hind': 0}, out={'front': 4, 'hind': 4}, snap=False, slip=0.04, arc=0.8, jerk=0.7,
                track={'front': -10, 'hind': -25},
                height=-12, tilt=3, chest_up=-6, neck=-10, nod=3.5, bob=2.5, pitch=1.0, flex=1.0, roll=4, yaw=2.5, head=0.3,
                lag=(0.08, 0.16), tail=4, tail_lag=0.1, tail_whip=0.3, steps=('LH', 'LF', 'RH', 'RF')),
        4: dict(name='run', kind='gallop', ticks=16, speed=38, wing=WING_RUN,
                touchdown={'LH': 0.0, 'RH': 0.1, 'RF': 0.42, 'LF': 0.54},
                duty={'LH': 0.3, 'RH': 0.3, 'RF': 0.3, 'LF': 0.3},
                lift={'front': 55, 'hind': 45}, curl={'front': 20, 'hind': 14}, peel={'front': 16, 'hind': 16},
                reach={'front': 0, 'hind': 15}, out={'front': 40, 'hind': 12}, snap=True, slip=0.06,
                track={'front': -10, 'hind': -25},
                height=-4, tilt=0, chest_up=-3, neck=8, nod=1.5, bob=10, pitch=5, flex=6, roll=1.5, yaw=1.5, head=0.8,
                lag=(0.05, 0.1), tail=14, tail_lag=0.06, tail_whip=0.6, steps=('LH', 'RF')),
    },
)

IDLE = dict(name='idle', kind='walk', wing=WING_IDLE, wing_rate=2, ticks=IDLE_TICKS, look=glance, sink=sink, chest=chest, flick=flick, shift=2.0,
            height=0, tilt=0, chest_up=0, neck=0, nod=0.0, bob=0.9, pitch=0.6, flex=0.6, roll=0.5, yaw=0.5, head=0.2,
            lag=(0.04, 0.08), tail=3.0, tail_lag=0.06, tail_whip=0.4, breath=0.6, track={'front': -10, 'hind': -25})


def idle_frames(rig):
    """The idle: four planted paws at their neutral stance, the body breathing above them."""
    cfg = IDLE
    p = rig.p
    W = rig.still
    centres, tracks = {}, {}
    for name, (up, lo, paw, side, front) in p['legs'].items():
        key = 'front' if front else 'hind'
        ref = p['legs'][quadruped.MIRROR.get(name, name)]
        centres[name] = W[up][2][3] + p['reach'][key]
        tracks[name] = side * (abs(W[ref[2]][0][3]) + cfg['track'][key])
    frames, worst = [], 0.0
    hist = {}
    for t in range(IDLE_TICKS):
        phase = t / IDLE_TICKS
        pose = [list(v) for v in rig.rest]
        pose[0] = [4096, 4096, 4096, 0, 0, 0, 0, 0, 0]
        quadruped.body(rig, cfg, phase, pose, hist)
        extra(rig, cfg, phase, pose)
        for name, (up, lo, paw, side, front) in p['legs'].items():
            world = rig.paw(front, 0, name)
            wrist = quadruped.standing(rig, name, tracks[name], centres[name], world)
            lower, short = rig.solve(pose, name, wrist, hist)
            worst = max(worst, short)
            quadruped.set_rot(pose, paw, quadruped.mul(quadruped.tr(lower), world), hist)
        frames.append(pose)
    frames.append([list(b) for b in frames[0]])
    return frames, worst


def build(data, skeleton):
    """The idle (slot 0) and the three field gaits written into the model -> (bytes, report)."""
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError("Gryphonmon's clips require the reviewed source")
    if [b[1] for b in skeleton] != PROFILE['parents']:
        raise ValueError('Gryphonmon rig differs')
    n = len(skeleton)
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = n
    old = mmd.MMD.parse(data, n)
    old.type = SPECIES
    rig = quadruped.Rig(old, skeleton, PROFILE)
    frames, short = idle_frames(rig)
    assert short <= 0.5, short
    frames = [[[round(v) for v in b] for b in pose] for pose in frames]
    blinks = [(0, 'tex', dict(op='tex', frame=1, src=(48, 64), size=(4, 16), dst=(16, 32)))]
    for at in (18, 47, 80):
        blinks += [(at + k, 'tex', dict(op='tex', frame=at + k + 1, src=(x, 64 if x == 48 else 16), size=(4, 16), dst=(16, 32)))
                   for k, x in BLINK]
    idled = copy.deepcopy(old)
    idled.anims.anims[old.anims.table[0]] = mmd.encode_anim(frames, n, loop_sample=0, events=blinks, tol=1)
    idle_slots = [s for s, i in enumerate(old.anims.table) if i == old.anims.table[0]]
    data = idled.build()
    walked, report = quadruped.build(data, skeleton, dict(PROFILE, source=hashlib.sha256(data).hexdigest()))
    actual = mmd.MMD.parse(walked, n)
    actual.type = SPECIES
    changed = changed_programs(old, actual)
    assert changed == sorted(set(report['changed_slots'] + idle_slots)), changed
    assert actual.tmd.build() == old.tmd.build()
    played = animsheet.slot_frames(actual, n, 0)[0]
    floor = quadruped._floor(rig, played)
    assert floor <= quadruped.FLOOR, floor
    report.update(source_sha256=SOURCE, output_sha256=hashlib.sha256(walked).hexdigest(), changed_slots=changed,
                  idle=dict(ticks=IDLE_TICKS, slots=idle_slots, lowest_point=round(floor, 2)),
                  storage=motionstorage.require(walked, n))
    return walked, report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/293-gryphonmon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    text = json.dumps(proof, indent=2) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
