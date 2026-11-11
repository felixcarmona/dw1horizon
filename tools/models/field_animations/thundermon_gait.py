"""Thundermon's idle, walk, condition walk and run, written for its own 13-bone rig (field slots 0, 2, 3, 4).

Offline only (player builds replay the pinned delta): `tools/models/edit.py get 252` on the commit before this change,
then `python3 -m tools.models.field_animations.thundermon_gait --source THAT.MMD --out AFTER.MMD --report R.json` and
`edit.py put 252 AFTER.MMD`.

What was wrong. The clips came with the import: the fists hung over the round body in the idle and the walk, the boots
rolled over each other and overlapped (the run's stance slid one foot at 124 %), the walks were 17 / 21 / 21 ticks of
20 / 10 / 35 units a tick that matched no stride, and the idle replayed a 97 tick performance.

What the clips are now. Every piece of the rig is rigid and zero rotations are its standing pose (face to -z, bolt up,
arms hanging, boots flat), so each clip is written as rotations and offsets about it:
- the body is a ball that bobs (it dips as a boot lands and rises over the step; translation only, nothing is scaled),
  rolls toward the standing boot and twists a little against the stride. Every channel is a harmonic of one step phase,
  so the loops close exactly and the body travels at one constant speed;
- each boot plants where it lands, keeps the speed of the ground while it supports (it rolls heel to toe about the sole's
  edge) and swings forward lifted and toe up to land on the heel. The boots stay a boot's width apart so they never
  overlap, and the hip stubs stay under the ball;
- the shoulders sit on the ball's surface and turn with it; each arm swings against the opposite boot, its forearm and
  glove following the shoulder late (damped springs solved over the loop, `follow`). The arms are held out from the
  body, never over it;
- the bolt follows the body's turn and bounce with a lag.
The tired walk is slower, lower and shorter-stepped with the arms drooping and nearly still, the run leans forward with a
flight phase and wide arm swings. The idle breathes, shifts its weight and lets the arms and the bolt sway.
"""
import argparse
import cmath
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
from tools.models.field_animations import thundermon_face as face  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402

SPECIES, NB = 252, 13
SOURCE = 'ac3701cdf3096a1ab5374c34f8235093fd35024e8de5b962c373b9fa97bdef60'     # edit.py get 252 before this change
SOURCE_TIM = 'ad17393df5334c8c07b359828c6f855f9e7cd09dfc047dd369635dc9f2baf268'     # the texture before this change
SLOTS = (0, 2, 3, 4)
# The eyes' plan per clip: (tick, state) changes inside the clip, ending in open eyes. The idle blinks twice in a row once
# a loop; the walk and the run blink once, the tired walk slowly (heavy lids).
FACE = {0: face.blink(30) + face.blink(38), 2: face.blink(9), 3: face.blink(22, long=True), 4: face.blink(12)}
PARENTS = [-1, 0, 1, 1, 3, 4, 1, 6, 7, 1, 9, 1, 11]
BODY, BOLT = 1, 2
ARMS = ((3, 4, 5, 1), (6, 7, 8, -1))               # shoulder, elbow, glove, side (+1 is the +x side)
LEGS = ((9, 10, 1), (11, 12, -1))                  # hip stub, boot, side
TOLERANCE = 1
GROUND = 0.0
BODY_Y = -107.0                                    # the body origin's height at rest (y is down): the ball clears the boots
BOOT_X = 38.0                                      # centre of each boot sideways
BOOT_Z = -8.0                                      # centre of a boot fore and aft at mid stance (the toe peeks out)
SHOULDER = (57.0, -6.0, 0.0)                       # in the body's frame
STUB = (BOOT_X, 32.0, 0.0)
BOLT_AT = (0.0, -51.0, -55.0)
BOLT_TILT = -36                                    # the bolt's rest tilt, 1/4096 turn about x
ELBOW_AT, GLOVE_AT = (22.0, 34.0, 0.0), (1.0, 32.0, 1.0)

# One row per slot. cycles: gait cycles in the loop; period = n / cycles (a cycle is two steps); duty: share of a cycle a
# boot supports; lift: height a boot clears the ground; heel / toe: sole pitch at landing (toe up) and toe-off, degrees;
# dip: how far the body drops as a boot lands; roll / twist / lean: body angles in degrees; arm: swing of the shoulders
# (degrees, forward positive), out: how far the arms stand out from the body, elbow: the forearm's bend forward,
# wrist: the glove's pitch forward.
GAIT = {
    0: dict(n=97, cycles=1, speed=0.0, still=True),
    2: dict(n=24, cycles=2, speed=16.0, stance=6, lift=20, heel=9, toe=12, dip=12, roll=7.0, twist=5.0, lean=4.0,
            arm=28, out=28, fwd=4, elbow=62, wrist=6),
    3: dict(n=40, cycles=2, speed=10.0, stance=12, lift=12, heel=5, toe=8, dip=12, roll=8.0, twist=3.0, lean=9.0,
            arm=12, out=18, fwd=10, elbow=32, wrist=14),
    4: dict(n=20, cycles=2, speed=36.0, stance=4, lift=30, heel=6, toe=16, dip=14, roll=5.0, twist=6.0, lean=13.0,
            arm=34, out=34, fwd=0, elbow=58, wrist=6),
}


def rx(d):
    a = math.radians(d)
    c, s = math.cos(a), math.sin(a)
    return [[1, 0, 0], [0, c, -s], [0, s, c]]


def ry(d):
    a = math.radians(d)
    c, s = math.cos(a), math.sin(a)
    return [[c, 0, s], [0, 1, 0], [-s, 0, c]]


def rz(d):
    a = math.radians(d)
    c, s = math.cos(a), math.sin(a)
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]


def mul(*ms):
    out = ms[0]
    for m in ms[1:]:
        out = [[sum(out[i][k] * m[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    return out


def tr(m):
    return [[m[j][i] for j in range(3)] for i in range(3)]


def app(m, v):
    return [sum(m[i][j] * v[j] for j in range(3)) for i in range(3)]


def add(a, b):
    return [x + y for x, y in zip(a, b)]


def sub(a, b):
    return [x - y for x, y in zip(a, b)]


def smooth(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def spring(samples, fn, zeta):
    """A damped spring's steady-state response to an endless loop of `samples`: the loop's harmonics one by one, each
    scaled and delayed by the spring (natural frequency `fn` in cycles a loop), so the result closes on itself."""
    n = len(samples)
    spectrum = [sum(samples[t] * cmath.exp(-2j * math.pi * k * t / n) for t in range(n)) for k in range(n)]
    for k in range(n):
        h = min(k, n - k) * (1 if k <= n // 2 else -1)
        r = h / fn
        spectrum[k] /= (1 - r * r + 2j * zeta * r)
    return [sum(spectrum[k] * cmath.exp(2j * math.pi * k * t / n) for k in range(n)).real / n for t in range(n)]


class Rig:
    def __init__(self, model, skeleton):
        self.model, self.skeleton = model, skeleton
        self.verts = {b: [v[:3] for v in model.tmd.obj_verts(o)] for b, (o, _) in enumerate(skeleton) if o >= 0}

    def sole(self, side):
        return self.verts[10 if side > 0 else 12]

    def rolling(self, side, pitch_up, yaw=0.0):
        """Boot orientation for a sole pitched `pitch_up` degrees toe up: its rotation, the origin's fore-and-aft shift
        that keeps the sole's lowest vertex where the flat boot had it, and the origin's height over the ground."""
        flat = ry(yaw)
        rot = mul(flat, rx(-pitch_up))
        low = [app(rot, v) for v in self.sole(side)]
        i = max(range(len(low)), key=lambda k: low[k][1])
        return rot, app(flat, self.sole(side)[i])[2] - low[i][2], -low[i][1]


def euler(m, history, bone):
    angle = mmd.matrix_euler(m, history.get(bone))
    history[bone] = angle
    return [round(v) for v in angle]


class Pose:
    """One tick: world rotations and origins per bone, written as the model's local pose."""

    def __init__(self):
        self.rot = {0: [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}
        self.pos = {0: [0.0, 0.0, 0.0]}
        self.local = {}

    def put(self, bone, rot_world, pos_world):
        self.rot[bone], self.pos[bone] = rot_world, pos_world

    def child(self, bone, local_rot, local_pos):
        p = PARENTS[bone]
        self.put(bone, mul(self.rot[p], local_rot), add(self.pos[p], app(self.rot[p], local_pos)))

    def frame(self, history, root=0.0):
        f = [[4096, 4096, 4096, 0, 0, 0, 0, 0, round(root)]]
        for b in range(1, NB):
            p = PARENTS[b]
            local = mul(tr(self.rot[p]), self.rot[b])
            t = app(tr(self.rot[p]), sub(self.pos[b], self.pos[p]))
            f.append([4096, 4096, 4096] + euler(local, history, b) + [round(v) for v in t])
        return f


def foot_cycle(g, tick, offset):
    """One boot at a loop tick: (fore-and-aft offset about mid stance in the body's frame, height over the ground, toe-up
    pitch). z forward is negative; the ground runs back at `speed`. A cycle is `period` ticks: `stance` ticks with the boot
    on the ground, then the swing, whose ticks sit between its ends so the boot is already off the ground on the first
    and has not landed on the last."""
    period, speed = g['n'] // g['cycles'], g['speed']
    stance = g['stance']
    swing = period - stance
    i = (tick + offset) % period
    reach = speed * stance / 2
    if i < stance:                                # support: the boot keeps the ground's speed
        return -reach + 2 * reach * i / stance, 0.0, 0.0
    q = (i - stance + 1) / (swing + 1)
    m = speed * (swing + 1)                       # it leaves and lands at the ground's speed: no scuffing
    z = ((2 * q ** 3 - 3 * q * q + 1) * reach + (q ** 3 - 2 * q * q + q) * m
         + (3 * q * q - 2 * q ** 3) * -reach + (q ** 3 - q * q) * m)
    lift = g['lift'] * math.sin(math.pi * q) ** .6
    pitch = -g['toe'] * smooth(1 - 2 * q) + g['heel'] * smooth(2 * q - 1)
    return z, lift, pitch


def author(rig, slot):
    g = GAIT[slot]
    n = g['n']
    still = g.get('still')
    speed = g['speed']
    hist = {}
    poses, notes = [], dict(body_y=[], reach=[], feet=[])
    # body channels first (the followers need them whole)
    body = []
    for t in range(n):
        phase = t * g['cycles'] / n                           # cycles elapsed
        if still:
            w = 2 * math.pi * t / n
            body.append(dict(dy=-2.6 * math.sin(w) + .8 * math.sin(2 * w + 1), dx=3.0 * math.sin(w + .7), roll=3.0 * math.sin(w + .7),
                             yaw=4.0 * math.sin(w + 2.0) + 1.0 * math.sin(3 * w), pitch=1.5 * math.sin(w - .3) + .5 * math.sin(2 * w), phase=0.0))
            continue
        step = (2 * phase) % 1.0                              # 0 as a boot lands
        w = 2 * math.pi * phase
        th = 2 * math.pi * step
        # the bounce: a hard drop as a boot lands, a slow rise and a small second bump before the next one (anticipation, settle)
        dy = g['dip'] * (.5 * math.cos(th) + .2 * math.cos(2 * th + .9)) - g['dip'] * .0
        if speed >= 30:                                       # the run: highest in flight
            dy = -g['dip'] * (.5 * math.cos(th - .6) + .15 * math.cos(2 * th - .2))
        body.append(dict(dy=dy, dx=.6 * g['roll'] * math.sin(w - .25), roll=g['roll'] * (math.sin(w - .25) + .18 * math.sin(3 * w + .5)),
                         yaw=-g['twist'] * math.sin(w - .5), pitch=-g['lean'] + .22 * g['roll'] * math.cos(th + .7), phase=phase))
    n_ = n
    bolt_drive = [[b['pitch'], b['roll'], b['yaw']] for b in body]
    accel = [body[(t + 1) % n_]['dy'] - 2 * body[t]['dy'] + body[(t - 1) % n_]['dy'] for t in range(n_)]
    # the bolt: a spring about the body's turn
    fnb = 2.0 * g['cycles']
    mean = [sum(d[k] for d in bolt_drive) / n_ for k in range(3)]
    lag = [spring([d[k] - mean[k] for d in bolt_drive], fnb, .35) for k in range(3)]
    flap = spring(accel, fnb, .35)
    # the arms: late springs about the shoulder swing
    arm_drive = {}
    for side in (1, -1):
        if still:
            w = lambda t: 2 * math.pi * t / n
            shoulder = [g_ * 0 + 3.0 * math.sin(w(t) + (0 if side > 0 else .6) + 1.0) for g_, t in zip(range(n), range(n))]
        else:
            shoulder = [-side * g['arm'] * (math.cos(2 * math.pi * (t * g['cycles'] / n) + .3) + .28 * math.sin(4 * math.pi * (t * g['cycles'] / n) + (.4 if side > 0 else 1.5))) for t in range(n)]
        arm_drive[side] = shoulder
    follow = {}
    lagroll = spring([b['roll'] for b in body], 2.2 * g['cycles'], .4)
    for side in (1, -1):
        s = arm_drive[side]
        follow[side] = dict(elbow=spring(s, 3.6 * g['cycles'] if not still else 3.0, .4), wrist=spring(s, 2.6 * g['cycles'] if not still else 2.5, .35))
    for t in range(n):
        b = body[t]
        p = Pose()
        centre_y = BODY_Y + b['dy']
        rb = mul(ry(b['yaw']), rx(b['pitch']), rz(b['roll']))
        p.put(1, rb, [b['dx'], centre_y, 0.0])
        # the bolt
        rbolt = mul(rx(-lag[0][t] * 1.0 + flap[t] * 1.2), ry(-lag[2][t] * 1.2), rz(-lag[1][t] * 1.8 + (b['roll'] - lag[1][t]) * 0.0))
        p.child(2, mul(mmd.rot_matrix(BOLT_TILT, 0, 0), rbolt), BOLT_AT)
        # arms
        for (sh, el, gl, side) in ARMS:
            f = follow[side]
            swing = arm_drive[side][t]
            out = g.get('out', 14) if not still else 16
            fwd = g.get('fwd', 8) if not still else 8
            elbow_b = (g.get('elbow', 34) if not still else 44) + (0.0 if still else .45 * f['elbow'][t])
            wrist_b = (g.get('wrist', 10) if not still else 10) - .5 * (f['wrist'][t] if not still else f['wrist'][t])
            p.child(sh, mul(rx(-(fwd + swing)), rz(-side * (out + (b['roll'] - lagroll[t]) * 0.9))), [side * SHOULDER[0], SHOULDER[1], SHOULDER[2]])
            p.child(el, rx(-(elbow_b + (0.35 * swing if not still else 0))), [side * ELBOW_AT[0], ELBOW_AT[1], ELBOW_AT[2]])
            p.child(gl, rx(-wrist_b), [side * GLOVE_AT[0], GLOVE_AT[1], GLOVE_AT[2]])
        # legs
        for hip, boot, side in LEGS:
            p.child(hip, [[1, 0, 0], [0, 1, 0], [0, 0, 1]], [side * STUB[0], STUB[1], STUB[2]])
            # world rotation of the stub = the body's
            if still:
                z, lift, pitch = 0.0, 0.0, 0.0
            else:
                z, lift, pitch = foot_cycle(g, t, 0 if side > 0 else g['n'] // g['cycles'] // 2)
            rot, dz, py = rig.rolling(side, pitch, yaw=-side * 2.0)
            origin = [side * (BOOT_X - 7.0), GROUND + py - lift, BOOT_Z + 33.0 + z + dz]
            p.put(boot, rot, origin)
        poses.append(p)
        notes['body_y'].append(centre_y)
    hist = {}
    frames = []
    for t, p in enumerate(poses):
        frames.append(p.frame(hist, root=-speed * t))
    frames.append(copy.deepcopy(frames[0]))
    frames[-1][0][8] = round(-speed * n)
    mmd.close_loop(frames, 0)
    return frames, notes


def landings(slot):
    g = GAIT[slot]
    if g.get('still'):
        return []
    period = g['n'] / g['cycles']
    return sorted({round(c * period + (0.5 * period if h else 0)) % g['n'] for c in range(g['cycles']) for h in (0, 1)})


def parse(data, skeleton):
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = len(skeleton)
    model = mmd.MMD.parse(data, len(skeleton))
    model.type = SPECIES
    return model


def build(data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE or [b[1] for b in skeleton] != PARENTS:
        raise ValueError('Thundermon gait requires the 13-bone import as `edit.py get 252` gave it before this change')
    model = parse(data, skeleton)
    rig = Rig(model, skeleton)
    result = copy.deepcopy(model)
    checks = []
    for slot in SLOTS:
        frames, notes = author(rig, slot)
        note = {0: 11, 2: 11, 3: 16, 4: 16}[slot]
        events = [(t, 'sound', dict(op='sound', bank=1, note=note, frame=t + 1)) for t in landings(slot)]
        events += face.events(FACE[slot], GAIT[slot]['n'])
        program = mmd.encode_anim(frames, NB, 0, events, tol=TOLERANCE, repeats=False)
        index = model.anims.table[slot]
        if sum(1 for v in model.anims.table if v == index) > 1:           # a program shared with another slot
            index = len(result.anims.anims)
            result.anims.anims.append(program)
            result.anims.table[slot] = index
        else:
            result.anims.anims[index] = program
        checks.append(dict(slot=slot, ticks=GAIT[slot]['n'], units_per_tick=GAIT[slot]['speed'], landing_ticks=landings(slot)))
    for animation in result.anims.anims:
        animation.tail = b''
    output = result.build()
    effective = parse(output, skeleton)
    assert effective.tmd.build() == model.tmd.build()
    return output, dict(species=SPECIES, source_sha256=SOURCE, output_sha256=hashlib.sha256(output).hexdigest(),
                        changed_slots=changed_programs(model, effective), checks=checks,
                        storage=motionstorage.require(output, NB))


def texture(tim):
    """The texture before this change (SOURCE_TIM) -> the same with the eye frames in their spare texels."""
    if hashlib.sha256(tim).hexdigest() != SOURCE_TIM:
        raise ValueError('the texture is not the import as `edit.py get 252` gave it before this change')
    result = mmd.Tim4(tim)
    face.stamp(result)
    return result.to_bytes()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, default=ROOT / 'build/imported-model-edit/edit/252-Thundermon.MMD')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--tim', type=Path, default=ROOT / 'build/imported-model-edit/edit/252-Thundermon.TIM')
    p.add_argument('--tim-out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    a = p.parse_args()
    sk = json.loads(next((ROOT / 'content/species').glob('252-*.json')).read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), sk)
    a.out.write_bytes(data)
    a.tim_out.write_bytes(texture(a.tim.read_bytes()))
    if a.report:
        a.report.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({k: proof[k] for k in ('changed_slots',)}), proof['storage']['resident_bytes'], len(data))


if __name__ == '__main__':
    main()
