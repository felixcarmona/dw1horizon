#!/usr/bin/env python3
"""Puppetmon's field acting (species 181): planted soles under the original's own body, and loose, weighted, overlapped limbs.

The original's walk, condition walk and run keep their lengths, speeds and lean (16 ticks at 22.5 units per tick, 20 at 15, 12 at 45);
the idle keeps its 104-tick loop. This stage writes slots 0, 2, 3 and 4 again:

* the legs come from `quadruped.py`: each sole stands still in the world through its stance (two-bone solves on the thigh and
  shin, the sole flat), so nothing slides over the floor;
* the pelvis keeps the original's own lean, twist and bob, lined up with the new footfalls;
* the chest, head, arms and the hammer are made here from damped springs that follow the pelvis and the stride: the chest answers
  the pelvis a little late, the head later still, every arm joint lags the one above it, and the hammer swings on after the
  hand like a pendulum on a string. The two arms are not alike (the left one carries the hammer), the loop is two strides long and
  the second differs from the first, and the idle breathes, shifts its weight and tilts its head over its 104 ticks;
* tired is a heavy droop (slow, damped, the head down, the arms hanging), the run an eager lean with pumping arms.

Legs and pelvis are in the solved cycle; everything above the pelvis is written afterwards from the springs, so it never moves a sole.

Offline: `python -m tools.models.field_animations.puppetmon_field --specimen content/species/181-puppetmon.json --out DIR`.
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
import numeric as np  # noqa: E402
from tools.models.field_animations import quadruped  # noqa: E402
from tools.models.field_animations.war_greymon import rotation, set_rotation  # noqa: E402

SOURCE_SHA256 = '2834a5f401362586a350ab6c4839c9231542dbfdec420b594fad964f13753572'
SPECIES = 181
DEG = quadruped.DEG
LEGS = {'RH': (12, 13, 14, 1, False), 'LH': (15, 16, 17, -1, False)}
PELVIS, TORSO, HEAD = 1, 2, 3
RIGHT, LEFT = (5, 6, 7), (9, 10, 11)       # shoulder, elbow, hand; the left hand holds the hammer
DONOR = {}         # slot -> the original's played frames (filled by `build`)
MODEL = {}


def donor_at(slot, phase):
    """The original's pose of `slot` at a cycle phase, interpolated between its ticks (angles the short way)."""
    frames = DONOR[slot]
    n = len(frames) - 1
    x = (phase % 1.0) * n
    i = int(x)
    f = x - i
    a, b = frames[i], frames[i + 1 if i + 1 <= n else 0]
    pose = []
    for ba, bb in zip(a, b):
        row = list(ba)
        for k in range(3, 6):
            row[k] = ba[k] + ((bb[k] - ba[k] + 2048) % 4096 - 2048) * f
        for k in range(6, 9):
            row[k] = ba[k] + (bb[k] - ba[k]) * f
        pose.append(row)
    return pose


def body(rig, cfg, phase, pose, hist):
    """The pelvis as the original has it (lean, twist and bob), at this phase of the new stride."""
    rest = rig.rest
    d = donor_at(cfg['slot'], phase + cfg['shift'])
    mean = cfg['mean']
    for k in range(3, 6):
        pose[PELVIS][k] = d[PELVIS][k] + cfg['sway'] * (math.sin(2 * math.pi * phase) if k == 5 else 0.0) * DEG
    pose[PELVIS][7] = rest[PELVIS][7] - cfg['height'] + cfg['bob'] * (d[PELVIS][7] - mean[PELVIS][7])


def spring(series, period, zeta, repeats=8):
    """A damped spring that chases a periodic `series` (one value per tick): its steady-state loop, lagging and overshooting."""
    n = len(series)
    w = 2 * math.pi / period
    sub = 10
    dt = 1.0 / sub
    x, v = series[0], 0.0
    out = []
    for r in range(repeats):
        out = []
        for i in range(n):
            a, b = series[i], series[(i + 1) % n]
            for s in range(sub):
                target = a + (b - a) * s / sub
                v += (w * w * (target - x) - 2 * zeta * w * v) * dt
                x += v * dt
            out.append(x)
    return out


def lagged(series, ticks):
    """The series `ticks` later (fractions interpolate), as a loop."""
    n = len(series)
    out = []
    for i in range(n):
        x = (i - ticks) % n
        j = int(x)
        out.append(series[j] + (series[(j + 1) % n] - series[j]) * (x - j))
    return out


def vary(rig, cfg, frames):
    """Chest, head, arms and hammer of every tick of the (several-cycle) clip, from the springs."""
    T = len(frames) - 1
    ticks, cycles = cfg['ticks'], cfg.get('cycles', 1)
    A = cfg['acting']
    old = MODEL['old']
    sk = MODEL['sk']
    # per-tick drivers (degrees): the stride phase, with each cycle a little different
    cyc = lambda t: (t // ticks) % cycles
    ph = [(t % ticks) / ticks for t in range(T)]
    mod = [A['mods'][cyc(t) % len(A['mods'])] for t in range(T)]
    tw = [2 * math.pi * (ph[t] + A.get('arm_phase', 0.0)) for t in range(T)]
    slow = [2 * math.pi * t / T for t in range(T)]
    d = {}
    # forward swing of each shoulder: opposite to its own side's leg; the hammer arm swings less and late
    for name, sign in (('R', 1), ('L', -1)):
        amp = A['swing'][name]
        raw = [-sign * amp * mod[t][0] * (math.cos(tw[t]) + A['second'] * math.cos(2 * tw[t] - 0.9)) for t in range(T)]
        d['sh' + name] = spring(raw, A['arm_period'][name], A['zeta'])
        flex = [A['elbow'][name] + A['elbow_swing'][name] * math.cos(tw[t] - sign * 0.2) * mod[t][1] for t in range(T)]
        pre = [sh for sh in d['sh' + name]]
        vel = [(pre[(t + 1) % T] - pre[t - 1]) / 2 for t in range(T)]
        flex = [flex[t] + A['elbow_follow'] * max(0.0, -sign * vel[t]) for t in range(T)]
        d['el' + name] = spring(flex, A['arm_period'][name] * 0.8, A['zeta'] * 0.9)
        roll = [A['out'] + A['out_swing'] * math.sin(tw[t] + sign) for t in range(T)]
        d['ro' + name] = spring(roll, A['arm_period'][name] * 1.1, A['zeta'])
    # hammer: a pendulum about the wrist, driven by the arm's swing and its own sway
    wrist = [(-A['hammer'] * d['shL'][t]) for t in range(T)]
    d['wr'] = spring(wrist, A['hammer_period'], A['hammer_zeta'])
    drift = [A['hammer_sway'] * math.sin(slow[t] * cycles * ticks / ticks + 0.4) for t in range(T)]
    d['hs'] = spring(drift, A['hammer_period'] * 1.3, A['hammer_zeta'])
    # chest: follows the pelvis' twist late, with its own roll on the double beat and a breath
    pel = [frames[t][PELVIS][4] / DEG for t in range(T)]
    d['cy'] = spring([-A['counter'] * p for p in pel], A['chest_period'], A['zeta'])
    d['cr'] = spring([A['chest_roll'] * mod[t][2] * math.sin(4 * math.pi * (ph[t] + 0.05) + 0.6) + A['chest_roll1'] * math.sin(tw[t] + 0.7)
                      + A['breath'] * math.sin(slow[t] * A['breath_n']) for t in range(T)], A['chest_period'], A['zeta'])
    d['cp'] = spring([A['chest_pitch'] + A['chest_nod'] * math.cos(4 * math.pi * (ph[t] + 0.02)) * mod[t][2]
                      + A['breath'] * 1.6 * math.sin(slow[t] * A['breath_n'] - 0.5) + A['idle_pitch'] * math.sin(slow[t]) for t in range(T)],
                     A['chest_period'], A['zeta'])
    # head: follows the chest later, tilts a little off the beat, looks about
    d['hy'] = spring([-0.7 * d['cy'][t] + A['look'] * math.sin(slow[t] * A['look_n'] + 1.1) for t in range(T)], A['head_period'], A['head_zeta'])
    d['hp'] = spring([A['head_pitch'] - 0.5 * (d['cp'][t] - A['chest_pitch']) + A['head_nod'] * math.cos(4 * math.pi * (ph[t] + 0.12))
                      + A['look_pitch'] * math.sin(slow[t] * 2 + 0.3) for t in range(T)], A['head_period'], A['head_zeta'])
    d['hr'] = spring([-0.8 * d['cr'][t] + A['tilt'] * math.sin(slow[t] * A['tilt_n'] + 2.0) for t in range(T)], A['head_period'], A['head_zeta'])
    out = []
    hist = {}
    for t, pose in enumerate(frames):
        p = [list(b) for b in pose]
        i = t % T
        if t == T:
            p[1:] = [list(b) for b in out[0][1:]]
            out.append(p)
            continue
        base = donor_at(cfg['slot'], ph[i] + cfg['shift'])
        orig = np.array(mmd.bone_matrices(MODEL['old'], base))
        # chest on the original's own chest, then the springs' deltas
        set_rotation(p, TORSO, np.array(mmd.rot_matrix(*base[TORSO][3:6])) @ rotation([d['cp'][i], d['cy'][i], d['cr'][i]]), hist)
        world = np.array(mmd.bone_matrices(old, p))
        parent = world[sk[HEAD][1], :3, :3]
        set_rotation(p, HEAD, parent.T @ orig[HEAD, :3, :3] @ rotation([d['hp'][i], d['hy'][i], d['hr'][i]]), hist)
        for (sh, el, hand), side, sign in ((RIGHT, 'R', 1), (LEFT, 'L', -1)):
            p[sh - 1][3:6] = [0, 0, 0]
            p[sh][3:6] = [round((A['shoulder'] + (A['shoulder_L'] if side == 'L' else 0.0) + d['sh' + side][i]) * DEG), 0, round(-sign * d['ro' + side][i] * DEG)]
            p[el][3:6] = [round(-d['el' + side][i] * DEG), 0, 0]
        for hand, side in ((7, 'R'), (11, 'L')):
            world = np.array(mmd.bone_matrices(old, p))
            parent = world[sk[hand][1], :3, :3]
            extra = [d['wr'][i] + d['hs'][i], 0, 0] if side == 'L' else [0.35 * d['wr'][i], 0, 0]
            set_rotation(p, hand, parent.T @ orig[hand, :3, :3] @ rotation(extra), hist)
        out.append(p)
    return out


def row(slot, name, ticks, speed, duty, **extra):
    base = dict(
        kind='walk', snap=False, arc=0.5, clear_ease=0.15, world_ease=True, fold_soft=10, slip=0.0, heel=0, steps=('LH', 'RH'),
        reach={'front': 0, 'hind': 0}, lift={'front': 0, 'hind': 30}, curl={'front': 0, 'hind': 0}, peel={'front': 0, 'hind': 0},
        out={'front': 0, 'hind': 0}, wide={'front': 0, 'hind': 0}, track={'front': 0, 'hind': 0},
        touchdown={'LH': 0.0, 'RH': 0.5}, bob=1.0, swing={}, rx={}, height=0, shift=0.0, sway=0.0,
        slot=slot, name=name, ticks=ticks, speed=speed, duty={'LH': duty, 'RH': duty})
    base.update(extra)
    return base


def acting(**kw):
    a = dict(mods=[(1.0, 1.0, 1.0), (0.84, 0.9, 1.15)], swing={'R': 14.0, 'L': 6.0}, second=0.25, arm_period={'R': 5.0, 'L': 6.5}, zeta=0.45,
             elbow={'R': 42.0, 'L': 57.0}, elbow_swing={'R': 6.0, 'L': 3.0}, elbow_follow=0.8, out=20.0, out_swing=3.0, shoulder=-8.0, shoulder_L=0.0,
             hammer=0.5, hammer_period=7.0, hammer_zeta=0.3, hammer_sway=2.0,
             counter=0.8, chest_period=4.5, chest_roll=1.2, chest_roll1=1.2, breath=0.0, breath_n=4, chest_pitch=0.0, chest_nod=1.0,
             idle_pitch=0.0, head_period=6.5, head_zeta=0.4, look=0.0, look_n=1, head_pitch=0.0, head_nod=1.0, look_pitch=0.0, tilt=1.5, tilt_n=1)
    a.update(kw)
    return a


PROFILE = dict(
    species=SPECIES, name='Puppetmon', source=SOURCE_SHA256,
    parents=[-1, 0, 1, 2, 2, 4, 5, 6, 2, 8, 9, 10, 1, 12, 13, 1, 15, 16],
    pelvis=PELVIS, chest=TORSO, neck=None, head=HEAD, tail=(), loose=(),
    legs=LEGS, pole_world=True, rest_plane=True, pole={False: [0.0, 0.0, -1.0]},
    paw_rest={}, sole={False: [0, 0, 0]},
    reach={'front': 0, 'hind': 0}, fold={False: 60}, clear=2, floor=9, stance_slip=0.2,
    speed_range={0: (0, 0), 2: (15, 31), 3: (10, 20), 4: (35, 52)},
    body=body, vary=vary, gaits={}, tol=4,
)
PROFILE['gaits'] = {
    0: row(0, 'idle', 52, 0, 1.0, cycles=2, steps=(), sway=1.2, bob=1.0, height=0,
           acting=acting(mods=[(1, 1, 1), (1, 1, 1)], swing={'R': 0.0, 'L': 0.0}, second=0.0, elbow_swing={'R': 0.0, 'L': 0.0}, out_swing=0.0,
                         counter=0.0, chest_roll=0.0, chest_roll1=0.8, breath=0.8, chest_nod=0.0, idle_pitch=0.0, look=3.0, look_n=1, look_pitch=1.2,
                         tilt=2.5, tilt_n=1, head_nod=0.0, chest_period=9.0, head_period=11.0, hammer=0.0, hammer_sway=1.5, hammer_period=11.0)),
    2: row(2, 'walk', 14, 22.0, 0.56, cycles=2, arc=0.6, acting=acting()),
    3: row(3, 'tired walk', 18, 12.0, 0.56, cycles=2, lift={'front': 0, 'hind': 20}, sway=1.5, bob=1.2,
           acting=acting(swing={'R': 7.0, 'L': 3.0}, arm_period={'R': 7.0, 'L': 8.5}, zeta=0.6, elbow={'R': 46.0, 'L': 72.0}, shoulder_L=30.0, out=44.0, out_swing=1.5,
                         shoulder=6.0, chest_pitch=9.0, chest_nod=1.8, head_pitch=14.0, head_nod=2.2, head_period=8.0, hammer=0.2, hammer_period=9.0,
                         chest_period=6.0, chest_roll=2.0, elbow_follow=0.5)),
    4: row(4, 'run', 10, 42.0, 0.3, cycles=2, kind='trot', lift={'front': 0, 'hind': 36},
           acting=acting(swing={'R': 28.0, 'L': 12.0}, arm_period={'R': 4.0, 'L': 5.0}, zeta=0.5, elbow={'R': 78.0, 'L': 70.0}, elbow_swing={'R': 6.0, 'L': 4.0},
                         shoulder=-12.0, chest_pitch=7.0, chest_nod=1.0, head_pitch=-6.0, head_nod=1.0, hammer=0.45, hammer_period=5.5, chest_period=3.5,
                         head_period=5.0, chest_roll=1.8, out=14.0)),
}


def prepare(model, rig):
    """Read off the rig how each foot stands in the idle: the direction of its toes in the foot bone's space, and the middle of
    its lowest points (the sole)."""
    PROFILE['paw_rest'], PROFILE['sole'] = {}, {False: [0, 0, 0]}
    r = quadruped.Rig(model, rig, PROFILE)
    for name, (up, lo, paw, side, front) in LEGS.items():
        flat = r.R(r.still, paw)
        PROFILE['paw_rest'][name] = list(quadruped.mv(quadruped.tr(flat), [0.0, 0.0, -1.0]))
        pts = r.verts[paw]
        low = max(quadruped.mv(flat, p)[1] for p in pts)
        near = [p for p in pts if quadruped.mv(flat, p)[1] > low - 12]
        if name == 'RH':
            PROFILE['sole'][False] = [sum(p[i] for p in near) / len(near) for i in range(3)]


def lead_shift(old, slot):
    """Where in the original's cycle its left foot is furthest forward (the new strides' touchdown): a cycle fraction."""
    fs = DONOR[slot][:-1]
    worlds = [mmd.bone_matrices(old, p) for p in fs]
    sep = [w[14][2][3] - w[17][2][3] for w in worlds]
    return max(range(len(sep)), key=lambda i: sep[i]) / len(sep)


def build(data, sk):
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        raise ValueError('Puppetmon recipe requires its reviewed effective imported source')
    nb = len(sk)
    assert nb == 18
    exe = mmd.exe()
    exe.skeleton[SPECIES] = sk
    exe.bone_count[SPECIES] = nb
    old = mmd.MMD.parse(data, nb)
    old.type = SPECIES
    prepare(old, sk)
    profile = copy.deepcopy(PROFILE)
    profile['sole'], profile['paw_rest'] = PROFILE['sole'], PROFILE['paw_rest']
    profile['body'], profile['vary'] = body, vary
    MODEL.update(old=old, sk=sk)
    DONOR.clear()
    for slot in profile['gaits']:
        DONOR[slot] = animsheet.slot_frames(old, nb, slot)[0]
    for slot, cfg in profile['gaits'].items():
        frames = DONOR[slot][:-1]
        cfg['mean'] = [[sum(f[b][k] for f in frames) / len(frames) for k in range(9)] for b in range(nb)]
        cfg['shift'] = lead_shift(old, slot) if cfg['speed'] else 0.0
    return quadruped.build(data, sk, profile)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--specimen', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    import species
    s = json.loads(a.specimen.read_text())
    s['_path'] = str(a.specimen)
    raw, _ = species.species_model(s)
    data, report = build(raw, s['model']['skeleton'])
    a.out.mkdir(parents=True, exist_ok=False)
    (a.out / f'{s["id"]}-field.MMD').write_bytes(data)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
