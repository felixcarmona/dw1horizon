"""ShellNumemon's field idle, walk, condition walk and run as a snail that drags itself along.

The reviewed import (shell_numemon.py) kept the source's 104-tick clips: the four field slots moved only the small
front flaps and bobbed the body a few units, the head, mouth and eyes never moved and the root slid at a constant
speed, so the snail read as a still lump. This generator writes slots 0, 2, 3 and 4 again on the final model (every
other slot, the mesh, the rig and every scale stay).

The rig: the shell (bone 1) carries everything; under it the rear of the foot (2), the front of the foot (3, its
pivot is the seam with 2), the big head (8) with the upper teeth (9) and two eye stalks (10-11-12, 13-14-15, the
eyeballs last), and two small flaps at the front corners of the foot (4-5, 6-7). The head shares a ring of vertices
with the front of the foot and lies against the rear: turning it on them tears the mesh along the side of the body,
so the body (2, 3, 8) turns as one piece at the rear and the front only pitches a few degrees. The shell is turned
and slid on its own by turning bone 1 and solving bone 2 back to where it was, so only the shell moves.

Every crawl cycle is one wave running from the head back to the shell:

- reach: the body rises at the front, then leans forward and lays the head down ahead; it surges ahead of the
  steady root speed while the shell lags behind (it slides back on the body, making room for the head, and tips
  back), the eye stalks swing back from the push, the flaps sweep forward and the mouth opens with the effort;
- pull: the body settles, a small wave runs through the seam of the foot, the body slows and the shell is dragged
  after it (it slides forward to its place and rocks forward past it), the eye stalks swing forward and overshoot,
  the flaps press back, the mouth shuts.

The eye stalks hang like pendulums: every joint up a stalk swings wider and later than the one under it, pitching
with the surge and swaying sideways after the body's roll. The mouth has no jaw that could turn without opening
the mesh, so it opens through texture moves (shell_numemon_mouth.py). The body's world speed never drops below zero
(the belly glides, it never slides backward), the snail's lowest point stays on the ground on every tick, the shell
never comes closer to the head than at rest and no seam between touching pieces opens wider than on the model
before. No bone scale changes (the scale audit keeps every imported scale constant), so the squash and stretch is
made of the surge, the lean and the shell's drag.

- Idle (104 ticks): four slow breaths, the body turning a little, the eye stalks looking around each on its own,
  one quick dip of both stalks with the eyes wobbling as they come back up, two chomps and a slow yawn, the shell
  swaying a little, the flaps twitching.
- Walk (24 ticks, one wave): a steady crawl at the importer's 19.25 units per tick.
- Condition walk (32 ticks, one wave): slower and heavier, the stalks drooping, the mouth hanging open longer, the
  shell dragged further behind (12.84 units per tick).
- Run (18 ticks, one wave): long waves at 35 units per tick, the mouth wide open, the shell bouncing twice per wave.

The movement cue (bank 1, note 13) plays twice per wave, at the reach and at the pull.

Offline authoring (the player's build replays the plain delta): `tools/models/edit.py get 231`, then
`python3 -m tools.models.field_animations.shell_numemon_gait --source build/imported-model-edit/edit/231-ShellNumemon.MMD
--tex build/imported-model-edit/edit/231-ShellNumemon.TIM --out AFTER.MMD --out-tex AFTER.TIM` and
`tools/models/edit.py put 231 AFTER.MMD AFTER.TIM`. The sources must be the model and texture this module started from.
"""
import copy
import hashlib
import math

import animsheet
import mmd
import motioncyclelayer
import motionstorage
from motiondiscidentity import changed_programs
from tools.models.field_animations import shell_numemon_mouth as mouth
from tools.models.field_animations.magnadramon_flight import Rig, ease, swing

SPECIES = 231
NB = 16
SLOTS = (0, 2, 3, 4)
SOURCE = 'f14098b1a75c56d41e975e1f05fdc7e53cb3293e3e372f9fa14f64d2e0433494'   # the model before this change
TEX_SOURCE = '4a319c39ebd2278cf6c02b2e7934414003426ca0d2d32251f5f79f7654f84333'   # and its texture
PARENTS = [-1, 0, 1, 2, 3, 4, 3, 6, 3, 8, 8, 10, 11, 8, 13, 14]
SHELL, REAR, FRONT, HEAD = 1, 2, 3, 8
STALKS = ((10, 11, 12), (13, 14, 15))     # right, left
FLAPS = ((4, 5, 1), (6, 7, -1))           # right, left, the side's mirror sign
BELLY = (1, 2, 3)                         # the bones that rest on the ground
GROUND_BONES = (1, 2, 3, 5, 7)

# Rig.turn angles in degrees about the world axes (x across, y down, z back; the snail faces -z):
# +x leans the head and stalks forward, -x lifts the front of a foot piece, +x on the shell tips its top forward.
# The head (8) shares a ring of vertices with the front of the foot (3), and both lie against the rear (2): turning
# the head on the foot by 1 degree opens that ring by 1.5-2 units, rolling or yawing the front on the rear by 2
# units a degree. So the body (2, 3, 8) moves as one piece (turned at the rear, which carries the rest), the front
# only pitches a few degrees on the rear and the head never turns on the front.
SHELL_ROOM = 3.5       # units the shell slides back per degree the body rises (the head is ~200 tall)
FRONT_MAX = 3.          # the front's pitch on the rear, degrees (the seams with the rear open about .8 a degree)
CLIPS = {
    'walk': dict(n=24, surge=.55, lift=6, reach=5, wave=3, lag=12, rock=4.0, roll=1.5, body_roll=1.5, bounce=0,
                 stalk=-4, stalk_swing=14, sway=7, look=6, flap=16, flap_lift=6),
    'tired': dict(n=32, surge=.50, lift=3, reach=7, wave=2, lag=14, rock=3.5, roll=2.0, body_roll=2.0, bounce=0,
                  stalk=14, stalk_swing=10, sway=9, look=4, flap=9, flap_lift=3),
    'run': dict(n=18, surge=.62, lift=8, reach=6, wave=3, lag=12, rock=5.0, roll=1.5, body_roll=1.5, bounce=7,
                stalk=-14, stalk_swing=15, sway=6, look=3, flap=17, flap_lift=7),
}
IDLE = dict(n=104, breaths=4, breath=1.0, look=17, dip=16, roll=1.5, flap=6, turn=2.0)
STALK_CHAIN = ((.5, .05), (.75, .14), (1., .24))     # (share of the swing, lag in waves) from the base to the eye
CLIP_OF_SLOT = {2: 'walk', 3: 'tired', 4: 'run'}
CUES = (.05, .55)     # the phases of the movement cues in a wave
# the mouth (tick, state): two quick chomps and a slow yawn in the idle; it opens with the effort of the reach
MOUTH = {
    0: [(20, mouth.HALF), (21, mouth.OPEN), (23, mouth.HALF), (24, mouth.REST), (27, mouth.HALF), (28, mouth.OPEN),
        (30, mouth.REST), (74, mouth.HALF), (77, mouth.OPEN), (88, mouth.HALF), (91, mouth.REST)],
    2: [(5, mouth.HALF), (8, mouth.OPEN), (11, mouth.HALF), (14, mouth.REST)],
    3: [(4, mouth.HALF), (9, mouth.OPEN), (17, mouth.HALF), (24, mouth.REST)],
    4: [(2, mouth.HALF), (4, mouth.OPEN), (9, mouth.HALF), (11, mouth.REST)],
}


def _parse(data, skeleton):
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = len(skeleton)
    model = mmd.MMD.parse(data, len(skeleton))
    model.type = SPECIES
    return model


def bump(u, a, b, c, d):
    """0 before a, easing up to 1 by b, held to c, easing back to 0 by d; u, a..d are phases, cyclic."""
    u = (u - a) % 1.
    b, c, d = b - a, c - a, d - a
    if u < b:
        return ease(u / b)
    if u < c:
        return 1.
    if u < d:
        return 1 - ease((u - c) / (d - c))
    return 0.


def shell_lag(u):
    """How far the shell trails the body in a wave, 0..1: it falls behind through the reach and is dragged back
    to its place in the pull."""
    return bump(u, 0., .50, .55, .88)


def _matrices(model, pose):
    p = [list(v) for v in pose]
    p[0] = [4096] * 3 + [0] * 6
    return mmd.bone_matrices(model, p)


def _inverse(m):
    r = [[m[j][i] for j in range(3)] for i in range(3)]
    t = [-sum(r[i][k] * m[k][3] for k in range(3)) for i in range(3)]
    return [r[i] + [t[i]] for i in range(3)] + [[0, 0, 0, 1]]


def move_shell(model, rig, pose, x=0., z=0., back=0., up=0.):
    """Turns the shell about its pivot (world degrees) and slides it `back` and `up` (units) without moving the
    body under it: bone 2 is solved to keep its world matrix."""
    rear = _matrices(model, pose)[REAR]
    rig.turn(pose, SHELL, x=x, z=z)
    pose[SHELL][8] += back
    pose[SHELL][7] -= up
    local = mmd.mat_mul(_inverse(_matrices(model, pose)[SHELL]), rear)
    angles = mmd.matrix_euler([row[:3] for row in local[:3]], pose[REAR][3:6])
    pose[REAR][3:6] = list(angles)
    pose[REAR][6:9] = [local[i][3] for i in range(3)]


def lowest(model, verts, pose, bones=BELLY):
    w = _matrices(model, pose)
    return max(w[b][1][0] * x + w[b][1][1] * y + w[b][1][2] * z + w[b][1][3] for b in bones for x, y, z in verts[b])


def crawl_pose(model, rig, rest, c, t, speed):
    """Clip c at tick t: (pose without the root, the body's forward surge in units)."""
    n = c['n']
    u = t / n
    pose = copy.deepcopy(rest)
    # the body surges: fastest early in the reach, slowest in the pull; the amplitude is a share of the largest one
    # that keeps the body's world speed at or above zero
    amp = c['surge'] * speed * n / (2 * math.pi)
    surge = amp * math.sin(2 * math.pi * (u - .05))     # forward offset: fastest at the start of the reach
    pose[SHELL][8] -= surge
    lift = bump(u, .0, .18, .26, .46)              # the front of the body rises
    reach = bump(u, .30, .45, .50, .75)            # then it leans forward and lays the head down ahead
    hump = bump(u, .40, .55, .58, .78)             # a small wave at the seam of the foot
    lag = shell_lag(u)
    # the whole body (rear, front and head as one piece) rises and leans, rolling a little with the wave
    body = -c['lift'] * lift + c['reach'] * reach
    front = max(-FRONT_MAX, min(FRONT_MAX, c['wave'] * (hump - lift)))
    roll = c['body_roll'] * swing(u, .2)
    rig.turn(pose, REAR, x=body, z=roll)
    rig.turn(pose, FRONT, x=front)
    _stalks(rig, pose, u, c['stalk'], c['stalk_swing'], c['sway'], c['look'])
    # the flaps sweep forward and lift in the reach, press down and back in the pull
    for a, b, sign in FLAPS:
        sweep = swing(u, .0)
        rig.turn(pose, a, y=sign * c['flap'] * sweep, z=-sign * c['flap_lift'] * (.4 + .6 * max(0., sweep)))
        rig.turn(pose, a, x=-.9 * (body + front), z=-roll)          # kept level while the body pitches and rolls
        rig.turn(pose, b, x=.2 * c['flap'] * (1 + swing(u, .1)))     # the tip curls up, never into the floor
    # the shell: trails and tips back through the reach, is dragged forward and rocks past its place, sways
    rock = c['rock'] * (-lag * .7 + 1.2 * bump(u, .62, .76, .78, .98))
    bounce = c['bounce'] * abs(math.sin(2 * math.pi * (u - .1)))
    # rising tips the top of the head back: the shell makes room for it
    back = c['lag'] * lag + SHELL_ROOM * c['lift'] * lift
    move_shell(model, rig, pose, x=rock, z=c['roll'] * swing(u, .3), back=back, up=bounce)
    return pose, surge


def _stalks(rig, pose, u, droop, amount, sway, look):
    """The eye stalks hang like pendulums from the head: they swing back as the body speeds up and forward as it
    slows, and sway sideways after the body's roll; every joint up the stalk swings wider and later than the one
    under it, so the eyes trail and overshoot."""
    for side, chain in enumerate(STALKS):
        sign = 1 if side == 0 else -1
        for k, (bone, (share, lag)) in enumerate(zip(chain, STALK_CHAIN)):
            pitch = -amount * share * math.cos(2 * math.pi * (u - .05 - lag))
            roll = sway * share * swing(u, .2 + lag + .04 * side)
            yaw = sign * look * swing(u, .1 + .5 * side) if k == 0 else 0.
            rig.turn(pose, bone, x=droop * (.6, .4, 0.)[k] + pitch, y=yaw, z=roll)


def idle_pose(model, rig, rest, c, t):
    n = c['n']
    u = t / n
    pose = copy.deepcopy(rest)
    breath = math.sin(2 * math.pi * c['breaths'] * u)
    # the whole body breathes (rises a little at the front) and turns slowly to look about
    turn = c['turn'] * swing(u, .2)
    rig.turn(pose, REAR, x=-c['breath'] * breath, y=turn, z=.8 * swing(2 * u, .1))
    rig.turn(pose, FRONT, x=.6 * c['breath'] * breath)
    for side, chain in enumerate(STALKS):
        sign = 1 if side == 0 else -1
        look = c['look'] * (swing(u, .05) if side == 0 else .8 * swing(2 * u, .3))
        for k, (bone, (share, lag)) in enumerate(zip(chain, STALK_CHAIN)):
            # the dip reaches each joint later, and the eyes wobble back and forth as they come up again
            d = bump(u - lag * .08, .62, .66, .69, .80)
            ring = share * math.sin(2 * math.pi * (u - .72) * 10) * bump(u, .70, .74, .80, .95) if k else 0.
            breathe = 2 * share * math.sin(2 * math.pi * (c['breaths'] * u - .2 - lag))
            sway = 5 * share * swing(u, .35 + .2 * side + lag * .3)
            rig.turn(pose, bone, x=breathe + c['dip'] * (.8 if k == 0 else .5) * d - 6 * ring,
                     y=sign * look if k == 0 else 0., z=sign * sway)
    for a, b, sign in FLAPS:
        rig.turn(pose, a, y=sign * c['flap'] * swing(2 * u, .2 + .25 * (sign < 0)))
        rig.turn(pose, b, x=.25 * c['flap'] * (1 + swing(2 * u, .3 + .25 * (sign < 0))))
    # the shell makes room for the back of the head as the body rises and turns
    room = SHELL_ROOM * c['breath'] * max(0., breath) + 2.5 * abs(turn)
    move_shell(model, rig, pose, x=.8 * math.sin(2 * math.pi * (c['breaths'] * u - .25)), z=c['roll'] * swing(2 * u, .15),
               back=room)
    return pose


def author(model, skeleton):
    """`model` (the final model's bytes) with the four field slots replaced -> (bytes, proof)."""
    old = _parse(model, skeleton)
    native, _, _ = animsheet.slot_frames(old, NB, 0)
    assert len(native) == 105
    verts = {b: [tuple(v[:3]) for v in old.tmd.obj_verts(o)] for b, (o, _) in enumerate(skeleton) if o >= 0}
    # the rest pose: the mean of the native idle on every channel (its scales are the constant imported ones)
    rest = [[round(sum(f[b][i] for f in native[:-1]) / (len(native) - 1)) for i in range(9)] for b in range(NB)]
    assert all(f[b][:3] == rest[b][:3] for f in native for b in range(NB))
    floor = lowest(old, verts, rest)
    result = copy.deepcopy(old)
    streams, checks = {}, []
    for slot in SLOTS:
        frames, loop, events = animsheet.slot_frames(old, NB, slot)
        assert loop == 0 and len(frames) == 105
        c = IDLE if slot == 0 else CLIPS[CLIP_OF_SLOT[slot]]
        n = c['n']
        speed = 0. if slot == 0 else (frames[0][0][8] - frames[-1][0][8]) / 104   # the importer's speed, forward
        rig = Rig(old, skeleton)
        out, surges = [], []
        def pose_at(t):
            if slot == 0:
                pose, surge = idle_pose(old, rig, rest, c, t % n), 0.
            else:
                pose, surge = crawl_pose(old, rig, rest, c, t % n, speed)
            # the lowest point of the belly stays on the floor
            pose[SHELL][7] += floor - lowest(old, verts, pose)
            return pose, surge

        def raise_flaps(pose, lifts=None):
            """Raises a flap whose tip would dip under the floor at its root -> the angles (degrees) it took."""
            took = []
            for k, (a, b, sign) in enumerate(FLAPS):
                total = 0.
                if lifts:
                    rig.turn(pose, a, z=-sign * lifts[k])
                    total = lifts[k]
                for _ in range(8):
                    below = lowest(old, verts, pose, (b,)) - floor
                    if below <= .5:
                        break
                    rig.turn(pose, a, z=-sign * math.degrees(below / 60))
                    total += math.degrees(below / 60)
                took.append(total)
            return took

        # the lift a flap needs is eased in over the ticks around it, so the flap rises before the floor stops it
        need = [raise_flaps(pose_at(t)[0]) for t in range(n)]
        lifts = [[max(need[(t + d) % n][k] * w for d, w in ((-2, .35), (-1, .7), (0, 1.), (1, .7), (2, .35)))
                  for k in range(len(FLAPS))] for t in range(n)]
        for t in range(n + 1):
            pose, surge = pose_at(t)
            raise_flaps(pose, lifts[t % n])
            pose[0] = list(frames[0][0])
            pose[0][8] = round(frames[0][0][8] - speed * t)
            out.append([[round(x) for x in v] for v in pose])
            surges.append(surge)
        mmd.close_loop(out, 0)
        cues = mouth.events(MOUTH[slot], n)
        if slot:
            sound = next(e for e in events if e[1] == 'sound')
            for phase in CUES:
                frame = round(phase * n) + 1
                cues.append((frame - 1, 'sound', dict(sound[2], frame=frame)))
        streams[slot] = len(result.anims.anims)
        cues.sort(key=lambda e: e[0])
        result.anims.anims.append(mmd.encode_anim(out, NB, 0, cues, tol=1))
        body = [speed - (surges[(t + 1) % n] - surges[t]) for t in range(n)] if slot else [0.]
        checks.append(dict(slot=slot, ticks=n, root_per_tick=round(speed, 2), cues=sum(1 for e in cues if e[1] == 'sound'), mouth_moves=sum(1 for e in cues if e[1] == 'tex'),
                           body_speed=(round(min(body), 1), round(max(body), 1))))
    for slot in SLOTS:
        result.anims.table[slot] = streams[slot]
    for anim in result.anims.anims:
        anim.tail = b''
    result.anims.anims, result.anims.table = motioncyclelayer.share_identical_streams(result.anims.anims,
                                                                                    result.anims.table)
    output = result.build()
    effective = _parse(output, skeleton)
    assert effective.tmd.build() == old.tmd.build()
    assert changed_programs(old, effective) == list(SLOTS), changed_programs(old, effective)
    return output, dict(checks=checks, storage=motionstorage.require(output, NB))


def build(data, tex, skeleton):
    """(model bytes, texture bytes) -> (new model, new texture, proof)."""
    if (hashlib.sha256(data).hexdigest() != SOURCE or hashlib.sha256(tex).hexdigest() != TEX_SOURCE
            or [b[1] for b in skeleton] != PARENTS or [b[0] for b in skeleton] != list(range(-1, 15))):
        raise ValueError('ShellNumemon needs the reviewed 16-bone model and texture it had before this change')
    output, extra = author(data, skeleton)
    tim = mmd.Tim4(tex)
    mouth.stamp(tim)
    new_tex = tim.to_bytes()
    assert len(new_tex) == len(tex)
    return output, new_tex, dict(species=SPECIES, source_sha256=SOURCE, output_sha256=hashlib.sha256(output).hexdigest(),
                                 tex_output_sha256=hashlib.sha256(new_tex).hexdigest(), changed_slots=list(SLOTS),
                                 field=extra)


if __name__ == '__main__':
    import argparse
    import sys
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--source', required=True)
    parser.add_argument('--tex', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--out-tex', required=True)
    args = parser.parse_args()
    sys.path.insert(0, 'tools')
    skeleton = [(i - 1, p) for i, p in enumerate(PARENTS)]
    data, tex, proof = build(open(args.source, 'rb').read(), open(args.tex, 'rb').read(), skeleton)
    open(args.out, 'wb').write(data)
    open(args.out_tex, 'wb').write(tex)
    print(len(data), 'bytes', proof['field'])
