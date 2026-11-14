"""Floramon's (species 273) calm idle and loose walk, and a blink in every field clip.

Runs after pace.py on the paced model (the `after_generator` of its row in content/models/imports/pace.json). The legs of
the paced walk stepped ten times faster than the body could carry them (the feet slid at 73 % of the body's speed) and
every channel moved by large, even sinusoids; the idle swung the arms through 60 degrees. This layer writes the two clips
again from the rig:

* idle (slot 0, a new program: slot 33 keeps the old one): a 9 second loop. The feet stay planted and the body breathes
  (the pelvis tips a degree, at a constant whole-unit height so the knees do not step), the chest follows the breath a little later, the head turns and
  tilts slowly and lags the chest, the arms hang with a soft sway that grows towards the flower hands and the curled
  tendrils, the leaf tail trails. Every swing is a few degrees; each channel runs a whole number of cycles per loop;
* walk (slot 2, 26 ticks at 16 units a tick; the paced one was 28 ticks): a bouncy skip, the run's idea made slower and
  lower. Two hops of 13 ticks (the run's are 10) with a short planted stance (5 ticks, solved by IK so the foot does not
  slide), a long flight with both feet off the ground (alternating, like a skip) and the pelvis rising about 34 units
  (the run's rise is 61). The pelvis crouches on landing and its pitch follows the hops, it turns and sways with the
  leading leg, the chest counter-turns later and the head later still; arms swing with the legs and lift with each hop;
  flower, tendril and tail trail the arms. The swing's end tangents are scaled (`tang`) because the long swing would
  otherwise overshoot the leg's reach.

The blink uses the model's own eye frames (open, half shut, shut: one texture move over the painted eyes each, the frames
stored in texels no face samples), so the texture is unchanged. Every clip starts with open eyes and ends open; the idle
blinks every two to three seconds with a double blink once a loop, the walk and the tired walk once a loop (the tired walk, slot 3, keeps its legs, arms and root; its chest leans and its head hangs about 25 degrees lower, bobbing slowly), the run once every three
loops (its bones and root are untouched: its program is only repeated three times so that the blink is not repeated every
second).

Slot 3 (tired walk) has its own program and changes only in the chest, the head and the blink. Slot 4 (run) keeps its poses and root exactly and gains the blink; slots 1, 14-18, 33, 34, 36 (the source's own battle run, rebuilt: content/models/imports/battle-rebuilds.json) and the rest are not touched.
"""
import copy
import hashlib
import math

import numeric as np
import animsheet
import mmd
import motionsecondary
import motionstorage
from motiondiscidentity import changed_programs
from tools.models.field_animations.rosemon_gait import Gait as _Gait, _swing_pitch, mul, rx, ry, rz, smooth, softmax
from tools.models.field_animations.war_greymon import set_rotation

R = motionsecondary.R
SPECIES = 273
NB = 20
SOURCE = 'caca90e1cd48d289d1869fbf3c100fc5e6e355c92e169d6d80e49524ed076b04'      # the paced model
PELVIS, CHEST, HEAD = 1, 2, 3
ARMS = ((4, 5, 6, 7, 1), (8, 9, 10, 11, -1))        # arm, wrist, flower, tendril, side (x > 0 is the right)
TAIL = (12, 13)
LEGS = ((14, 15, 16, 1), (17, 18, 19, -1))          # hip, knee, ankle, side
FLOOR = 0.0
BODY_Z = 19
RUN = 4
TIRED = 3
RUN_REPEATS = 3
IDLE_TICKS = 180
TIRED_LEAN, TIRED_DROOP, TIRED_SIGN = 12., 12., 1     # degrees: the chest leans and the head hangs forward and down
WALK_TICKS, WALK_SPEED = 26, 16           # two hops of 13 ticks (the run's are 10), 16 units a tick

# eye frames (texture units: x in 4-pixel words) over the painted eyes at (0, 0), 14 x 28
EYE_SIZE = (14, 28)
EYE_FRAMES = {'open': (32, 88), 'half': (46, 88), 'shut': (46, 60)}

# One row per slot. cycles: strides a loop; duty: share of a stride a foot supports; lift: swing clearance of the sole;
# heel/toe: sole pitch at heel strike (toe up) and toe-off (heel up), degrees; height: pelvis y at its preferred (rest -119);
# bob: its swing twice a stride. Angles are degrees, lengths game units.

class Gait(_Gait):
    """Rosemon's foot path with the swing's end tangents scaled by `tang` (its long swings overshoot the leg's reach)."""

    def at(self, phase):
        g = self.g
        if phase < g['duty']:
            return _Gait.at(self, phase)
        q = (phase - g['duty']) / (1 - g['duty'])
        m = g.get('tang', .6) * self.speed * self.swing
        z = ((2 * q ** 3 - 3 * q * q + 1) * self.half + (q ** 3 - 2 * q * q + q) * m
             + (-2 * q ** 3 + 3 * q * q) * -self.half + (q ** 3 - q * q) * m)
        return z, g['lift'] * math.sin(math.pi * q ** g.get('kick', 1.0)) ** 0.8, _swing_pitch(q, g), False


GAIT = {
    0: dict(still=True, cycles=1, duty=.5, lift=0, heel=0, toe=0, offset=-4, stance_x=29, height=-118, bob=0., breath=1.8,
            sway=2.2, yaw=2.4, roll=1.6, chest=3.0, head_yaw=9., head_tilt=3.8, head_nod=3.0, arm=5.5, abduct=3.5, wrist=5.,
            flower=10., tendril=19., tail=10., tail_lift=4.5),
    2: dict(cycles=1, duty=.19, tang=.15, lift=38, heel=7, toe=9, offset=-4, stance_x=29, height=-110, bob=0., hop=40., dip=7.,
            yaw=5., roll=3.5, sway=4., chest_yaw=7., chest_roll=3.5, lean=2.5, head_yaw=6., head_tilt=16.,
            nod=9., arm=10., armhop=14., abduct=2., wrist=8., flower=16., tendril=30., tail=10., tail_lift=7., droop=0.),
}

# blinks: (tick, state) over each clip (sample numbers); every plan ends open
def _blink(at, slow=False):
    if slow:
        return [(at, 'half'), (at + 1, 'shut'), (at + 3, 'half'), (at + 4, 'open')]
    return [(at, 'half'), (at + 1, 'shut'), (at + 2, 'half'), (at + 3, 'open')]


EYES = {
    0: _blink(48) + _blink(112) + _blink(158) + _blink(165),     # every 3.2 s, 2.4 s, then a double blink
    2: _blink(13),
    3: _blink(17, slow=True),
    4: _blink(21),
}


def eye_move(state):
    return dict(op='tex', src=EYE_FRAMES[state], size=EYE_SIZE, dst=(0, 0))


def eye_events(plan, ticks):
    """(sample, 'tex', move): open eyes at tick 0, then the plan; inside the clip, in order, ending open."""
    assert all(0 < t < ticks for t, _ in plan) and [t for t, _ in plan] == sorted(t for t, _ in plan)
    assert not plan or plan[-1][1] == 'open'
    return [(0, 'tex', eye_move('open'))] + [(t, 'tex', eye_move(s)) for t, s in plan]


def _parse(data, sk):
    mmd.exe().skeleton[SPECIES] = sk
    mmd.exe().bone_count[SPECIES] = len(sk)
    model = mmd.MMD.parse(data, len(sk))
    model.type = SPECIES
    return model


class Rig:
    def __init__(self, model, sk):
        self.model, self.sk = model, sk
        self.verts = {b: np.array(model.tmd.obj_verts(o))[:, :3] for b, (o, _) in enumerate(sk) if o >= 0}
        self.bind = copy.deepcopy(animsheet.slot_frames(model, NB, 0)[0][0])
        assert all(abs(x) <= 1 for v in self.bind[1:] for x in v[3:6]), 'the idle opens on the bind pose'
        for v in self.bind[1:]:
            v[3:6] = [0, 0, 0]
        self.ref_world = self.world(self.bind)
        self.sole = {1: self.verts[16].tolist(), -1: self.verts[19].tolist()}

    def world(self, pose):
        p = copy.deepcopy(pose)
        p[0] = [4096] * 3 + [0] * 6
        return np.array(mmd.bone_matrices(self.model, p))

    def foot(self, side, pitch):
        return motionsecondary.rolling_foot(self.sole[side], np.eye(3).tolist(), pitch)


def _author(rig, slot, ticks, speed):
    """The loop's poses (ticks + 1, the last the first again), the bones' world checks and the notes."""
    g = GAIT[slot]
    n, K = ticks, g['cycles']
    still = g.get('still', False)
    gait = None if still else Gait(g, n / K, speed)
    mid = math.pi * g['duty']
    neutral = copy.deepcopy(rig.bind)
    neutral[PELVIS][7] = round(g['height'])
    wn = rig.world(neutral)
    hz0 = {hip: float(wn[hip, 2, 3]) for hip, _, _, _ in LEGS}
    out, hist, notes = [], {}, dict(pelvis_y=[], reach=0.)
    for t in range(n + 1):
        tt = t % n
        th = 2 * math.pi * K * tt / n            # the step phase (breath, in the idle: K cycles of it)
        loop = 2 * math.pi * tt / n
        c = lambda lag=0., k=1: math.cos(k * (th - lag))
        duty = g['duty']

        def hopc(lag):
            """The body's hop curve, twice a cycle (a hop per foot): +0.7 in the landing crouch, -0.5 at the top of the flight."""
            r = (((th - lag) / (2 * math.pi)) % .5)
            if r < duty:
                return .7 * math.sin(math.pi * r / duty)
            return -.5 * math.sin(math.pi * (r - duty) / (.5 - duty))
        cl = lambda lag=0., k=1: math.cos(k * (loop - lag))
        f = copy.deepcopy(rig.bind)
        if still:
            breath = 4 * loop / 1                    # four breaths in the 180 ticks (2.25 s each)
            b1 = lambda lag=0.: math.cos(breath - lag)
            yaw = g['yaw'] * cl(.4, 1)
            roll = g['roll'] * cl(1.3, 2) * .8
            pitch = .35 * g['breath'] * b1(.3)
            sway = g['sway'] * cl(.9, 1)
        else:
            yaw = g['yaw'] * c(.05)
            roll = -g['roll'] * c(mid)
            pitch = g['lean'] * .5 + g['nod'] * hopc(0.)
            sway = g['sway'] * c(mid + .1)
        Rp = mul(ry(yaw), rx(pitch), rz(roll))
        set_rotation(f, PELVIS, Rp, hist)
        Rp = np.array(mmd.rot_matrix(*f[PELVIS][3:6])).tolist()
        f[PELVIS][6], f[PELVIS][8] = round(sway), BODY_Z
        f[PELVIS][7] = round(g['height'])
        w = rig.world(f)
        goals = []
        for hip, knee, ankle, side in LEGS:
            phase = ((th / (2 * math.pi)) + (0. if side == 1 else .5)) % 1.
            if still:
                dz, lift, p, support = 0., 0., 0., True
            else:
                dz, lift, p, support = gait.at(phase)
            rf, shift, depth = rig.foot(side, p)
            x = side * g['stance_x'] + (side * 2. * math.sin(math.pi * ((phase - g['duty']) / (1 - g['duty']))) ** 2 if not support else 0.)
            goals.append(dict(hip=hip, knee=knee, ankle=ankle, side=side, support=support, rf=rf,
                              goal=[x, FLOOR - depth - lift, hz0[hip] + g['offset'] + dz + shift]))
        limit = .975 * (np.linalg.norm(f[15][6:9]) + np.linalg.norm(f[16][6:9]))
        bound = -1e9
        for foot in goals:
            h = [float(w[foot['hip'], i, 3]) for i in range(3)]
            d2 = (foot['goal'][0] - h[0]) ** 2 + (foot['goal'][2] - h[2]) ** 2
            assert d2 < limit * limit, (slot, t, foot['side'], 'horizontal reach', d2 ** .5, limit)
            drop = h[1] - f[PELVIS][7]
            bound = max(bound, foot['goal'][1] - math.sqrt(limit * limit - d2) - drop)
        if still:
            preferred = g['height']
        else:
            r = ((th / (2 * math.pi)) % .5)
            air = math.sin(math.pi * (r - duty) / (.5 - duty)) ** .8 if r >= duty else 0.
            crouch = math.sin(math.pi * r / duty) if r < duty else 0.
            preferred = g['height'] + g['dip'] * crouch - g['hop'] * air
        y = round(g['height']) if still else softmax(bound, preferred)       # a standing pelvis keeps a whole-unit height: the knees do not step
        notes['pelvis_y'].append(y)
        f[PELVIS][7] = round(y)
        for foot in goals:
            hip, knee, ankle, side = foot['hip'], foot['knee'], foot['ankle'], foot['side']
            w = rig.world(f)
            h = w[hip, :3, 3]
            a, b = float(np.linalg.norm(f[knee][6:9])), float(np.linalg.norm(f[ankle][6:9]))
            goal = np.array(foot['goal'])
            delta = goal - h
            dist = float(np.linalg.norm(delta))
            assert dist < a + b - .3, (slot, t, side, 'reach', dist, a + b)
            direction = delta / dist
            pole = np.array([.12 * side, 0., -1.])
            pp = pole - direction * float(pole @ direction)
            pp /= np.linalg.norm(pp)
            along = (a * a - b * b + dist * dist) / (2 * dist)
            joint = h + direction * along + pp * math.sqrt(max(0., a * a - along * along))
            rw = rig.ref_world
            rh, rs = map(np.array, motionsecondary.native_plane_rotations(
                [rw[v, :3, 3].tolist() for v in (hip, knee, ankle)], [h.tolist(), joint.tolist(), goal.tolist()],
                [rw[v, :3, :3].tolist() for v in (hip, knee)]))
            set_rotation(f, hip, np.array(Rp).T @ rh, hist)
            w = rig.world(f)
            set_rotation(f, knee, w[hip, :3, :3].T @ rs, hist)
            w = rig.world(f)
            set_rotation(f, ankle, w[knee, :3, :3].T @ np.array(foot['rf']), hist)
            notes['reach'] = max(notes['reach'], float(np.linalg.norm(rig.world(f)[ankle, :3, 3] - goal)))

        def world_turn(bone, parent, target):
            w = rig.world(f)
            set_rotation(f, bone, w[parent, :3, :3].T @ np.array(target), hist)
        if still:
            world_turn(CHEST, PELVIS, mul(rx(-g['chest'] * b1(.9) - .3 * g['chest']), ry(-.6 * g['yaw'] * cl(1.2)), rz(.5 * g['chest'] * cl(2., 2))))
            world_turn(HEAD, CHEST, mul(rx(g['head_nod'] * b1(1.6) * .8 + .4 * g['head_nod'] * cl(.5, 3)),
                                        ry(g['head_yaw'] * (cl(1.4) + .35 * cl(.2, 2))),
                                        rz(g['head_tilt'] * cl(2.1) + .4 * g['head_tilt'] * cl(.6, 3))))
        else:
            world_turn(CHEST, PELVIS, mul(ry(-g['chest_yaw'] * c(.35)), rx(g['lean'] + .6 * g['nod'] * hopc(.35)),
                                          rz(g['chest_roll'] * c(mid + .45))))
            world_turn(HEAD, CHEST, mul(ry(g['head_yaw'] * c(.9)), rx(-.35 * g['lean'] + g['droop'] - .6 * g['nod'] * hopc(.7)),
                                        rz(-.8 * g['chest_roll'] * c(mid + .8) + g['head_tilt'] * math.cos(loop - .9))))
        for arm, wrist, flower, tendril, side in ARMS:
            if still:
                u = lambda lag: 2 * loop - lag + (0. if side == 1 else 1.1)
                set_rotation(f, arm, mul(rx(g['arm'] * math.cos(u(.2)) + .5 * g['arm'] * b1(.8)), rz(-side * (g['abduct'] * math.cos(u(.9) - .4) + .4 * g['abduct'] * b1(.5)))), hist)
                set_rotation(f, wrist, mul(rx(g['wrist'] * math.cos(u(.9))), rz(side * .5 * g['wrist'] * math.cos(u(1.5)))), hist)
                set_rotation(f, flower, mul(rx(g['flower'] * math.cos(u(1.7))), rz(side * .6 * g['flower'] * math.cos(u(2.3))),
                                            ry(.3 * g['flower'] * math.cos(2 * loop - 2.8))), hist)
                set_rotation(f, tendril, mul(rx(g['tendril'] * math.cos(u(2.6) - .4) + .3 * g['tendril'] * math.cos(2 * u(3.2))),
                                             rz(side * .5 * g['tendril'] * math.cos(u(3.4)))), hist)
                continue
            u = th - .25 + (0. if side == 1 else math.pi)
            back = g['arm'] * (math.cos(u) + .12 * math.sin(2 * u)) - g['armhop'] * hopc(.2)
            set_rotation(f, arm, mul(rx(back), rz(-side * (g['abduct'] + .8 * math.cos(2 * (th - mid) + (0. if side == 1 else .6))))), hist)
            set_rotation(f, wrist, mul(rx(g['wrist'] * math.cos(u - .55)), rz(side * .4 * g['wrist'] * math.cos(u - 1.0))), hist)
            set_rotation(f, flower, mul(rx(g['flower'] * math.cos(u - 1.2)), rz(side * .6 * g['flower'] * math.cos(u - 1.7)),
                                        ry(.25 * g['flower'] * math.cos(2 * (u - 1.2)))), hist)
            set_rotation(f, tendril, mul(rx(g['tendril'] * (math.cos(u - 2.0) + .35 * math.cos(2 * (u - 2.4)))),
                                         rz(side * .5 * g['tendril'] * math.cos(u - 2.6))), hist)
        for i, bone in enumerate(TAIL):
            if still:
                lag = 1.2 + .8 * i
                set_rotation(f, bone, mul(rx(g['tail_lift'] * (.7 + .3 * i) * math.cos(breath - lag)), rz(g['tail'] * (.6 + .4 * i) * cl(lag + .5, 3))), hist)
            else:
                lag = .7 + .7 * i
                set_rotation(f, bone, mul(rx(g['tail_lift'] * (.7 + .4 * i) * c(lag + .2, 2) - .3 * g['lean']), rz(g['tail'] * (.5 + .5 * i) * c(lag + .1))), hist)
        out.append(f)
    out[-1][1:] = copy.deepcopy(out[0][1:])
    return out, notes


def _ints(poses):
    return [[[int(round(v)) for v in bone] for bone in pose] for pose in poses]


def _samples(rig, slot, source):
    """Poses of the loop with the root travel of `source` (the paced clip's frames)."""
    n = WALK_TICKS
    speed = WALK_SPEED
    poses, notes = _author(rig, slot, n, speed)
    for t, f in enumerate(poses):
        f[0] = copy.deepcopy(source[0][0])
        f[0][8] = int(round(source[0][0][8] - speed * t))
    return _ints(poses), notes, speed


def _tired_samples(source):
    """The tired walk's frames with the chest leaning forward and the head hanging down, both bobbing slowly (two a loop)."""
    n = len(source) - 1
    history = {}
    out = []
    for t, frame in enumerate(source):
        f = [list(b) for b in frame]
        loop = 2 * math.pi * (t % n) / n
        for bone, base, bob, lag in ((CHEST, TIRED_LEAN, 1.5, .3), (HEAD, TIRED_DROOP, 4., .8)):
            r = mmd.rot_matrix(*f[bone][3:6])
            set_rotation(f, bone, mul(rx(TIRED_SIGN * (base + bob * math.cos(2 * loop - lag))), r), history)
        out.append(f)
    return _ints(out)


def _idle_samples(rig):
    poses, notes = _author(rig, 0, IDLE_TICKS, 0.)
    for f in poses:
        f[0] = [4096] * 3 + [0] * 6
    return _ints(poses), notes


def _played(animation, ticks, slot, loops=1):
    player = mmd.AnimPlayer(animation, NB, slot)
    out = []
    for _ in range(ticks * loops + 1):
        assert player.tick(stop_at_infinite_loop=False)
        pose = [list(v) for v in player.pose]
        pose[0][6:9] = list(player.root)
        out.append(pose)
    return out


def _with_events(animation, events, keep_sounds=True):
    """The program with its texture moves replaced by `events` (tick, 'tex', move); sounds and keys stay."""
    result = copy.deepcopy(animation)
    result.instrs = [i for i in result.instrs if i['op'] != 'tex']
    for t, _, move in events:
        frame = t + 1
        at = next(k for k, i in enumerate(result.instrs) if i['op'] == 'key' and i['frame'] == frame)
        end = at + 1
        while end < len(result.instrs) and result.instrs[end]['op'] in ('tex', 'sound') and result.instrs[end].get('frame') == frame:
            end += 1
        result.instrs.insert(end, dict(move, frame=frame))
    return result


def _repeat(animation, repeats):
    """The same program played `repeats` loops long: the first loop's instructions copied with their frames shifted."""
    result = copy.deepcopy(animation)
    period = animation.frame_count - 1
    inner = [i for i in animation.instrs if i['op'] not in ('loop_start', 'loop_end', 'end')]
    body = list(inner)
    for k in range(1, repeats):
        for i in inner:
            if i['op'] == 'tex':
                continue
            c = copy.deepcopy(i)
            c['frame'] += k * period
            body.append(c)
    loop_start = [i for i in animation.instrs if i['op'] == 'loop_start']
    loop_end = next(i for i in animation.instrs if i['op'] == 'loop_end')
    tail = dict(loop_end, frame=animation.frame_count + (repeats - 1) * period)
    result.instrs = loop_start + body + [tail, dict(op='end')]
    result.frame_count = tail['frame']
    return result


def build(data, skeleton, species=SPECIES):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError('Floramon gait requires the paced Floramon model')
    model = _parse(data, skeleton)
    rig = Rig(model, skeleton)
    result = copy.deepcopy(model)
    checks = []
    for slot in (2,):
        source, loop, events = animsheet.slot_frames(model, NB, slot)
        assert loop == 0
        poses, notes, speed = _samples(rig, slot, source)
        n = WALK_TICKS
        index = model.anims.table[slot]
        assert sum(1 for v in model.anims.table if v == index) == 1, 'a walk shared with another slot'
        animation = mmd.encode_anim(poses, NB, loop_sample=0, events=eye_events(EYES[slot], n), tol=1)
        result.anims.anims[index] = animation
        checks.append(dict(slot=slot, ticks=n, units_per_tick=round(speed, 2), pelvis_y=[round(min(notes['pelvis_y']), 1), round(max(notes['pelvis_y']), 1)],
                           ankle_error=round(notes['reach'], 2)))
    # the tired walk: its legs, arms and root stay exactly; the head and the top of the body droop, and the blink is replaced
    index = model.anims.table[TIRED]
    assert sum(1 for v in model.anims.table if v == index) == 1, 'a tired walk shared with another slot'
    source, loop, events = animsheet.slot_frames(model, NB, TIRED)
    assert loop == 0
    n = len(source) - 1
    keep = [e for e in events if e[1] != 'tex']
    result.anims.anims[index] = mmd.encode_anim(_tired_samples(source), NB, loop_sample=0,
                                                events=eye_events(EYES[TIRED], n) + keep, tol=0)
    checks.append(dict(slot=TIRED, ticks=n))
    poses, notes = _idle_samples(rig)
    idle = mmd.encode_anim(poses, NB, loop_sample=0, events=eye_events(EYES[0], IDLE_TICKS), tol=1)
    result.anims.table[0] = len(result.anims.anims)
    result.anims.anims.append(idle)
    checks.append(dict(slot=0, ticks=IDLE_TICKS, pelvis_y=[round(min(notes['pelvis_y']), 1), round(max(notes['pelvis_y']), 1)]))
    # the run: the same program three loops long with one blink
    index = model.anims.table[RUN]
    run = _repeat(_with_events(model.anims.anims[index], []), RUN_REPEATS)
    ticks = run.frame_count - 1
    run = _with_events(run, eye_events(EYES[RUN], ticks))
    result.anims.anims[index] = run
    checks.append(dict(slot=RUN, ticks=ticks, shared_by=[s for s, v in enumerate(model.anims.table) if v == index]))
    for animation in result.anims.anims:
        animation.tail = b''
    output = result.build()
    effective = _parse(output, skeleton)
    assert effective.tmd.build() == model.tmd.build()
    changed = changed_programs(model, effective)
    return output, dict(species=SPECIES, source_sha256=SOURCE, output_sha256=hashlib.sha256(output).hexdigest(),
                        changed_slots=changed, checks=checks, storage=motionstorage.require(output, NB))
