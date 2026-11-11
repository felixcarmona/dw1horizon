"""DarkTyrannomon's field idle (slot 0), authored from scratch: a slow, heavy breathing loop.

The imported idle was the donor's 21-tick fidget played as a loop: every 0.7 seconds the torso yawed 30 degrees, the
head swept 38 degrees and the jaw snapped open and shut, the arms and tail swung at their own quick phases (the tail
42 degrees), the four feet lifted and dropped with a 30-unit bounce of the pelvis, and several bones snapped in a few
ticks. It read as convulsions. The new idle is 96 ticks (3.2 seconds): two breaths that swell and fade (chest 11 degrees), a tail (bones 3, 4, 5: base, middle and tip; 25, 28 and 34 degrees) that sways with the glances and flicks with the yawns, a head (bone 20) that nods and glances a little (17), a lower jaw (bone 21, pitch only, the chin straight down in the head's frame) that opens twice a loop, a small and a wide yawn, shutting between them (25 degrees at most, the chin 33 and 55 units down), and above all the arms: bones 12-15 and 16-19, the big outer limbs with the long claws, swing free (shoulders forward/back and a little outward, elbows flexing, hands and claws following with a lag, a different phase per arm), through springs at their periodic steady state. The feet are bones 6-8 and 9-11 (the short limbs at the centre) with the pelvis (1): solved once onto the floor and bit for bit the same in every tick; the loop closes
exactly. Every other slot keeps its program, including slot 33 (the battle idle), which shared the old idle's program.

Offline: `tools/models/edit.py get 265` on the commit before this change, then
`python3 -m tools.models.field_animations.darktyrannomon_idle --source THAT.MMD --out AFTER.MMD` and `edit.py put 265 AFTER.MMD`.
"""
import cmath
import copy
import hashlib
import math

import animsheet
import mmd
import motionstorage
import numeric as np
from tools.models.field_animations.triceramon_gait import Body, wave
from tools.models.field_animations.war_greymon import align, rotation, set_rotation

SPECIES = 265
NB = 22
SOURCE = 'd9287751a1d91b6c739947a40f8b341f463761263bc0a9114219fded7a7d8e6a'   # edit.py get 265 before this change
PARENTS = [-1, 0, 1, 1, 3, 4, 1, 6, 7, 1, 9, 10, 1, 12, 13, 13, 1, 16, 17, 17, 1, 20]
PI = math.pi
PELVIS, CHEST, NECK, HEAD, JAW = 1, 2, 3, 4, 5
HEAD_TOP, LOWER_JAW = 20, 21           # the real head and its lower jaw (bones 3-5 are the tail: base, middle and tip)
CHAINS = {'legL': (12, 13, 14), 'legR': (16, 17, 18), 'armR': (6, 7, 8), 'armL': (9, 10, 11)}
FEET = {k: v for k, v in CHAINS.items() if k.startswith('arm')}      # bones 6-8 and 9-11: the short limbs at the centre are the feet
FEET_BONES = (6, 7, 8, 9, 10, 11)    # with the pelvis (1) they never move: the same in every tick
IDLE_TICKS = 96
CLOSED_JAW_TICK = 10                 # the import's tick where the jaw is shut
AMP = 0.68                            # arm sway scale
FLOOR_GAP = 1.3                       # units between the lowest vertex of a planted foot or hand and the floor


def rot_y(deg):
    return rotation([0, deg, 0])


class Rig:
    """The rest pose (the import's first idle tick, jaw shut) and what the clip is built from."""

    def __init__(self, body, rest, closed_pose):
        self.body = body
        self.rest = copy.deepcopy(rest)
        self.rest[0] = [4096]*3 + [0]*6
        self.rest[JAW][3:6] = closed_pose[JAW][3:6]          # (the tail's tip keeps the pose it has when the import's mouth is shut)
        self.rest[LOWER_JAW][3:6] = closed_pose[LOWER_JAW][3:6]       # the mouth shut: only the lower jaw's pitch differs from the first tick
        self.w0 = body.world(self.rest)
        self.rm = [np.array(mmd.rot_matrix(*self.rest[b][3:6])) for b in range(NB)]
        self.base = [list(self.rest[b][6:9]) for b in range(NB)]
        self.link = {b: float(np.linalg.norm(self.rest[b][6:9])) for b in range(NB)}
        self.pole = {}
        for name, (hip, knee, end) in CHAINS.items():
            h, k, a = (self.w0[i, :3, 3] for i in (hip, knee, end))
            d = (a - h)/np.linalg.norm(a - h)
            p = (k - h) - d*float((k - h) @ d)
            self.pole[hip] = p/np.linalg.norm(p)
        self.goals = {}
        for name, (hip, knee, end) in CHAINS.items():
            rf = self.w0[end, :3, :3].copy()
            a = self.w0[end, :3, 3].copy()
            a[1] = -self.sole(end, rf) - FLOOR_GAP
            self.goals[end] = (a, rf)

    def sole(self, bone, rf):
        return float((self.body.verts[bone] @ rf.T)[:, 1].max())


def solve_chains(rig, f, swing, reach, hist, chains):
    """Two-bone IK of every limb onto its planted goal; `swing` = {root bone: degrees the middle joint rocks about
    the root-to-end axis}; `reach` = {end bone: (dx, lift, dz, curl)}: a free hand's goal moves from its resting point
    (dx outward, dz forward, lift up, all in units) and its claws curl by `curl` degrees; a hand never goes under the floor.
    f already has pelvis, chest, tail and head."""
    w = rig.body.world(f)
    solved = {}
    for name, (hip, knee, end) in chains.items():
        h = w[hip, :3, 3]
        la, lb = rig.link[knee], rig.link[end]
        goal, rf = rig.goals[end]
        if end in reach:
            dx, lift, dz, curl = reach[end]
            side = 1 if rig.rest[hip][6] > 0 else -1
            rf = rf @ rotation([curl, 0, 0])
            goal = np.array([goal[0] + side*dx, -rig.sole(end, rf) - FLOOR_GAP - max(0, lift), goal[2] + dz], float)
        delta = np.array(goal, float) - h
        dist = float(np.linalg.norm(delta))
        if not abs(la - lb) + 1 < dist < (la + lb)*.985:
            raise ValueError(('reach', hip, round(dist, 1), round(la + lb, 1)))
        direct = delta/dist
        pole = rig.pole[hip]
        pp = pole - direct*float(pole @ direct)
        pp /= np.linalg.norm(pp)
        a = math.radians(swing.get(hip, 0))
        pp = pp*math.cos(a) + np.cross(direct, pp)*math.sin(a)
        along = (la*la - lb*lb + dist*dist)/(2*dist)
        joint = h + direct*along + pp*math.sqrt(max(0, la*la - along*along))
        rw = rig.w0
        rh = align(rw[hip, :3, :3] @ np.array(rig.rest[knee][6:9]), joint - h) @ rw[hip, :3, :3]
        rk = align(rw[knee, :3, :3] @ np.array(rig.rest[end][6:9]), goal - joint) @ rw[knee, :3, :3]
        solved[hip] = (rh, rk, np.array(rf), knee, end)
    for hip, (rh, rk, rf, knee, end) in solved.items():
        set_rotation(f, hip, rig.body.world(f)[PARENTS[hip], :3, :3].T @ rh, hist)
        set_rotation(f, knee, rig.body.world(f)[hip, :3, :3].T @ rk, hist)
        set_rotation(f, end, rig.body.world(f)[knee, :3, :3].T @ rf, hist)


def set_world(rig, f, bone, world_rotation, hist):
    set_rotation(f, bone, rig.body.world(f)[PARENTS[bone], :3, :3].T @ world_rotation, hist)


def local_delta(rig, f, bone, degrees, hist):
    set_rotation(f, bone, rotation(degrees) @ rig.rm[bone], hist)


def pulse(t, n, centre, width):
    """A raised-cosine bump (0 to 1 to 0) of the given width in ticks, repeated every n ticks: eases in and out."""
    d = ((t - centre + n/2) % n) - n/2
    return .5 + .5*math.cos(PI*d/(width/2)) if abs(d) < width/2 else 0.


def follow(values, fn, zeta=.5):
    """The loop of `values` (one per tick) through a spring of natural frequency fn cycles a loop, at its periodic steady
    state: the response trails and overshoots a little, and the loop still closes."""
    n = len(values)
    out = [0.]*n
    for k in range(n//2 + 1):
        z = sum(v*cmath.exp(-2j*PI*k*i/n) for i, v in enumerate(values))/n
        r = k/fn
        z /= (1 - r*r + 2j*zeta*r)
        w = 1 if k in (0, n/2) else 2
        for i in range(n):
            out[i] += w*(z*cmath.exp(2j*PI*k*i/n)).real
    return out


def signals(n):
    """Every motion of the loop as one value per tick. The rhythm is not one wave: two breaths a loop whose depth
    swells and fades, a glance to one side and a shorter one to the other with a pause between, a roar once a loop
    (chest fills, head lifts, jaw opens and shuts), weight that moves in eased steps, and a tail that sweeps slowly."""
    T = range(n)
    th = [2*PI*t/n for t in T]
    depth = [1 + .3*math.cos(x + 1.2) for x in th]
    breath = [depth[t]*(math.sin(2*x - .5) + .22*math.sin(4*x - 1.2)) for t, x in enumerate(th)]
    inflate = [pulse(t, n, 50, 30) for t in T]                          # the breath in before the roar
    roar = [pulse(t, n, 62, 18)**1.5 for t in T]
    snort = [pulse(t, n, 70, 8) for t in T]
    yawn1 = [pulse(t, n, 66, 40)**.8 for t in T]                       # the wide yawn, held a moment at the top
    yawn2 = [pulse(t, n, 22, 30)**.8 for t in T]                        # a smaller opening earlier in the loop
    glance = [1.0*pulse(t, n, 24, 44) - .55*pulse(t, n, 82, 34) for t in T]
    sway = [math.sin(x + .3) + .3*math.sin(2*x + 1.1) for x in th]
    shift = [math.tanh(3.0*math.sin(x + .6)) + .15*math.sin(2*x) for x in th]
    return dict(breath=breath, inflate=inflate, roar=roar, snort=snort, glance=glance, sway=sway, shift=shift,
                head_yaw=follow([36*g for g in glance], 3.2, .45),
                neck_yaw=follow([17*g for g in glance], 2.4, .55),
                head_nod=follow([-8*r + 3.5*i + 3.0*g - 4*y1 - 2.5*y2 for r, i, g, y1, y2 in zip(roar, inflate, glance, yawn1, yawn2)], 3.0, .45),
                jaw=follow([34*y1 + 22*y2 + 2*sn for y1, y2, sn in zip(yawn1, yawn2, snort)], 3.2, .7),
                mouth=follow([26*y1 + 17*y2 for y1, y2 in zip(yawn1, yawn2)], 3.2, .7),
                elbow=follow(shift, 1.8, .5),
                armR=follow([math.sin(x) + .3*math.sin(2*x + .4) for x in th], 2.0, .5),
                armL=follow([math.sin(x + 2.5) + .3*math.sin(2*x + 1.9) for x in th], 2.0, .5),
                handR=follow([math.sin(x + 2.2) for x in th], 1.6, .4),
                handL=follow([math.sin(x + 5.0) for x in th], 1.6, .4),
                curlR=follow([math.sin(x + 1.3) for x in th], 2.4, .5),
                curlL=follow([math.sin(x + 3.9) for x in th], 2.4, .5),
                bob=follow(breath, 2.2, .5))


def author_idle(rig, ticks=IDLE_TICKS):
    n = ticks
    sg = signals(n)
    frames = []
    hist = {}
    # the feet (bones 6-11, the short limbs at the centre): solved once, onto feet that stand on the floor, then the same in every tick
    stand = copy.deepcopy(rig.rest)
    solve_chains(rig, stand, {}, {}, hist, FEET)
    for t in range(n):
        f = copy.deepcopy(rig.rest)
        breath, inflate, roar, glance, shift = (sg[k][t] for k in ('breath', 'inflate', 'roar', 'glance', 'shift'))
        breath += 1.2*inflate - .6*roar
        # pelvis and hind legs: the rest pose, identical every tick (the arms hang from the pelvis and sway on their own)
        # chest: swells with the breath (pitches back and up) and rises a little
        cx, cy, cz = rig.base[CHEST]
        f[CHEST][6:9] = [round(cx), round(cy - 1.5*breath), round(cz + 1.0*breath)]
        local_delta(rig, f, CHEST, [-4.9*breath, 2.6*glance, 1.8*shift], hist)
        set_world(rig, f, NECK, rotation([1.8*sg['head_nod'][t]/3 - 1.2*breath, sg['neck_yaw'][t], 1.2*shift]) @ rig.w0[NECK, :3, :3], hist)
        set_world(rig, f, HEAD, rotation([sg['head_nod'][t] - .8*breath, sg['head_yaw'][t], 2.0*shift + 1.5*glance]) @ rig.w0[HEAD, :3, :3], hist)
        local_delta(rig, f, JAW, [-sg['jaw'][t], 0, 0], hist)       # the tail's tip flicks with the yawns
        # the head (bone 20) nods and glances a little; the lower jaw (bone 21) only pitches: positive opens the mouth, yaw and roll stay 0
        local_delta(rig, f, HEAD_TOP, [.8*sg['head_nod'][t] - 1.0*breath, .33*sg['head_yaw'][t], 0], hist)
        local_delta(rig, f, LOWER_JAW, [sg['mouth'][t], 0, 0], hist)
        e = sg['elbow'][t]
        for b in FEET_BONES:
            f[b][3:9] = stand[b][3:9]
        ar, al, kr, kl, hr, hl = (sg[k][t] for k in ('armR', 'armL', 'curlR', 'curlL', 'handR', 'handL'))
        # the arms (bones 12-15 and 16-19) swing free, rotation only: shoulders forward/back and a little outward, elbows flex,
        # hands and claws follow with a lag; each arm has its own phase
        for sh, el, hand, claw, a_, k_, h_, out in ((12, 13, 14, 15, al, kl, hl, 1), (16, 17, 18, 19, ar, kr, hr, -1)):
            local_delta(rig, f, sh, [AMP*(-9 - 9*a_), out*AMP*(4 + 4*k_), 0], hist)
            local_delta(rig, f, el, [AMP*(-14 - 14*k_ + 3*e), 0, 0], hist)
            local_delta(rig, f, hand, [AMP*12*h_, 0, 0], hist)
            local_delta(rig, f, claw, [AMP*10*h_, 0, 0], hist)
        frames.append(f)
    frames.append(copy.deepcopy(frames[0]))
    return frames


TOLERANCE = {b: 1 for b in range(1, NB)}
TOLERANCE[None] = 2
for _b in (2, 3, 4, 5, 20, 21):
    TOLERANCE[_b] = 2
for _b in (6, 7, 8, 9, 10, 11):
    TOLERANCE[_b] = 0


def pack(frames, events):
    samples = [[[int(round(x)) for x in bone] for bone in pose] for pose in frames]
    return mmd.encode_anim(samples, NB, loop_sample=0, events=events, tol=TOLERANCE, repeats=False)


def make_model(data, skeleton):
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = len(skeleton)
    model = mmd.MMD.parse(data, NB)
    model.type = SPECIES
    body = Body(model, skeleton)
    old = animsheet.slot_frames(model, NB, 0)
    return model, body, Rig(body, old[0][0], old[0][CLOSED_JAW_TICK]), old[2]


def build(data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE or [b[1] for b in skeleton] != PARENTS:
        raise ValueError("DarkTyrannomon's idle is written over the model the importer and the reviewed delta produced")
    model, body, rig, old_events = make_model(data, skeleton)
    frames = author_idle(rig)
    tex = [e for e in old_events if e[1] == 'tex']
    events = [(tex[0][0], 'tex', dict(tex[0][2]))]
    model.anims.table[0] = len(model.anims.anims)      # slot 33 (the battle idle) keeps the old program
    model.anims.anims.append(pack(frames, events))
    used = sorted({i for i in model.anims.table if i is not None})
    renumber = {old: i for i, old in enumerate(used)}
    model.anims.anims = [model.anims.anims[i] for i in used]
    model.anims.table = [None if i is None else renumber[i] for i in model.anims.table]
    result = model.build()
    return result, dict(species=SPECIES, source_sha256=SOURCE, changed_slots=[0], storage=motionstorage.require(result, NB))


def main():
    import argparse
    import json
    from pathlib import Path
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    rig = json.loads(Path('content/species/265-darktyrannomon.json').read_text())['model']['skeleton']
    data, report = build(Path(args.source).read_bytes(), rig)
    Path(args.out).write_bytes(data)
    print(args.out, len(data), 'B', report['storage'])


if __name__ == '__main__':
    main()
