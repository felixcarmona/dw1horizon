"""Quetzalmon's field idle, walk, condition walk and run as four different flights.

The import kept all of its field slots (idle 0 and 1, walk 2, condition walk 3, run 4) as one frozen pose: not one
bone moved, only the root travelled, so the winged serpent slid along like a statue. This writes those five slots
again (every other slot, the mesh, the rig and the hover height stay):

- Idle: a hover in place, 54 ticks, two slow wing beats. The coiled body rises a little with each downstroke and
  breathes, a wave runs up the neck, the head holds level and glances about, the tail and crest sway.
- Walk: a leaning flight, the body stretched out and leaning far forward, three slow strong beats in 48 ticks
  (the earlier 24-tick walk twice), the tail dragging behind the heave.
- Condition walk: low and heavy, one slow beat per loop, the wings hanging low and lifted slowly, the head
  nodding forward, the body leaning and swaying, the tail trailing near the floor.
- Run: a lighter flight, the body leaning a little, two beats in 20 ticks, a wave running down the tail, the
  head level.

In every clip the wings flap near the horizontal and stay spread (the upstroke stops a little above it).

The wings are one rigid mesh each, hinged at the head. Each beat is a held top, a quick power downstroke and a slower
recovery (the beats of a loop differ a little in length and depth, the left wing trails the right, the stroke is chased by
a spring so it overshoots softly). Everything else is secondary motion: the body's rise is a soft spring on the stroke
(it peaks as the downstroke ends), and the neck coil, the tail and the crest are chains of springs that follow that heave
link after link; the head turns back against the neck so it stays steady. Every clip repeats its pose cycle exactly (the
last tick equals the first); the root travels the same distance on every tick; the tick counts of the earlier walk,
condition walk and run, their distances and their footstep sounds are kept.
"""
import copy
import hashlib
import math

import animsheet
import mmd
import motioncyclelayer
import motionstorage
from motiondiscidentity import changed_programs
from tools.models.field_animations.lillymon_flight import Rig, swing

SPECIES = 249
NB = 16
SLOTS = (0, 1, 2, 3, 4)
NECK = (2, 3, 4, 5)
HEAD, CREST = 6, (7, 8)
WING_R, WING_L = 9, 10
TAIL = (11, 12, 13, 14, 15)

#   per clip: ticks (None: the earlier clip's, repeated `loops` times), the beats per loop and the share of the loop
#   each takes, the share of a beat the downstroke takes, the wing angle at the top and the bottom of the stroke
#   (degrees about the front-to-back axis from the folded rest; about 70 is level), the body's rise (units), its
#   lean (degrees forward) and nose-up pitch with the rise, the neck's bend and its sway to the heave, the head's
#   levelling and nod, the tail's drag and its side swish, the crest flick, and the height of the lowest point of the
#   mesh above the floor.
CLIPS = {
    'idle': dict(n=54, loops=1, beats=(1.08, .92), down=.5, top=44, bot=82, amp=(1., .94), bob=26, lean=0, pitch=5,
                 neck=0, heave=11, level=.8, nod=0, glance=7, drag=9, swish=7, crest=7, flutter=7, clear=22, roll=1.5,
                 wing=.15, bodyw=.8, sway=4, cyc=1),
    'run': dict(n=None, loops=1, beats=(1.05, .95), down=.46, top=48, bot=84, amp=(1., .94), bob=30, lean=15, pitch=6,
                neck=-10, heave=12, level=.85, nod=0, glance=0, drag=10, swish=8, crest=8, flutter=8, clear=26, roll=2.5,
                wing=.15, bodyw=.8, sway=3, cyc=1),
    'tired': dict(n=None, loops=1, beats=(1.,), down=.62, top=52, bot=88, amp=(1.,), bob=12, lean=20, pitch=4,
                  neck=-14, heave=7, level=.3, nod=-18, glance=0, drag=6, swish=6, crest=3, flutter=4, clear=8, roll=3,
                  wing=.2, bodyw=.9, sway=3, cyc=1),
    'walk': dict(n=None, loops=2, beats=(1.06, .94, 1.0), down=.5, top=42, bot=84, amp=(1., .93, 1.04), bob=28, lean=30,
                 pitch=6, neck=-20, heave=12, level=.9, nod=0, glance=0, drag=9, swish=6, crest=5, flutter=6, clear=36,
                 roll=2, wing=.15, bodyw=.8, sway=4, cyc=2),
}
CLIP_OF_SLOT = {0: 'idle', 1: 'idle', 2: 'walk', 3: 'tired', 4: 'run'}


def smooth(x):
    x = min(1., max(0., x))
    return x * x * x * (x * (6 * x - 15) + 10)


def beat_phase(c, u):
    """(beat index, 0..1 through it, beat length in loops) at u (0..1 of the loop); the beats are of unequal length."""
    lens = [b / sum(c['beats']) for b in c['beats']]
    start = 0.
    for i, ln in enumerate(lens):
        if u < start + ln - 1e-9 or i == len(lens) - 1:
            return i, (u - start) / ln, ln
        start += ln


def wing_target(c, u, lag=0.):
    """0 at the top of the stroke, 1 at the bottom: a held top, a quick power downstroke, a slower recovery."""
    i, q, _ = beat_phase(c, (u - lag) % 1.0)
    d = c['down']
    return (smooth(q / d) if q < d else 1 - smooth((q - d) / (1 - d))) * c['amp'][i]


def follow(sig, n, omega, zeta, sub=8, loops=8):
    """A damped spring chasing the periodic signal sig(t) (ticks, period n), settled: the samples of one loop."""
    x, v, dt = sig(0.), 0., 1. / sub
    out = None
    for k in range(loops * n * sub + 1):
        t = k * dt
        x, v = (lambda a: (x + v * dt + a * dt * dt, v + a * dt))(omega * omega * (sig(t) - x) - 2 * zeta * omega * v)
        if k >= (loops - 1) * n * sub and k % sub == 0:
            out = out or []
            out.append(x)
    return out


def tracks(c, n):
    """Every driven quantity of a clip, as lists over ticks 0..n (the last equal to the first)."""
    beat = n / len(c['beats'])
    wf = lambda lag: follow(lambda t: wing_target(c, (t / n) % 1.0, lag), n, 2 * math.pi / (.55 * beat), .6)  # noqa: E731
    wr, wl = wf(0.), wf(.03)
    # the body rises through the downstroke and peaks as it ends: a soft spring on the stroke
    h = follow(lambda t: wing_target(c, (t / n) % 1.0), n, 2 * math.pi / (1.6 * beat), .45)
    lo, hi = min(h), max(h)
    h = [(x - lo) / (hi - lo) - .5 for x in h[:-1]]
    h.append(h[0])
    hv = [(h[(k + 1) % n] - h[k - 1]) / 2 for k in range(n)]
    hv.append(hv[0])
    scale = max(abs(x) for x in hv) or 1.
    hv = [x / scale for x in hv]
    chain = lambda src, ln, w, z: follow(lambda t: src[int(t) % n] * (1 - t % 1) + src[(int(t) + 1) % n] * (t % 1), n, w, z)  # noqa: E731,E501
    neck, tail, crest = [hv], [hv], [hv]
    for _ in range(4):
        neck.append(chain(neck[-1], n, 2 * math.pi / (.9 * beat), .5))
    for _ in range(5):
        tail.append(chain(tail[-1], n, 2 * math.pi / (.8 * beat), .45))
    for _ in range(2):
        crest.append(chain(crest[-1], n, 2 * math.pi / (.5 * beat), .4))
    for lst in [wr, wl] + neck[1:] + tail[1:] + crest[1:]:
        lst[-1] = lst[0]                                    # the settled spring is the loop's own start
    return dict(wr=wr, wl=wl, h=h, hv=hv, neck=neck[1:], tail=tail[1:], crest=crest[1:])


def pose_at(rig, rest, root, c, tr, t, n):
    u = t / n
    pose = copy.deepcopy(rest)
    pose[0] = list(root)
    h = tr['h'][t]
    pose[1][7] = round(rest[1][7] - c['bob'] * (h + .5))
    pose[1][6] = round(rest[1][6] + 3 * swing(u, .2))
    # nose up as the body rises, forward lean otherwise, a slow roll that follows the wings' unevenness
    roll = c['roll'] * (swing(u, .1) * .6 + 6 * (tr['wl'][t] - tr['wr'][t]))
    pitch = -c['lean'] + c['pitch'] * h
    rig.turn(pose, 1, x=pitch, z=roll)
    total = pitch
    # the neck trails the heave link after link, the head turns back against it so it stays level
    for k, b in enumerate(NECK):
        a = c['neck'] / 4 - c['heave'] * (.6 + .25 * k) * tr['neck'][k][t] + .6 * swing(u, .1 + .05 * k)
        rig.turn(pose, b, x=a, z=c['sway'] * (.5 + .25 * k) * swing(c['cyc'] * u, .09 * k))
        total += a
    glance = c['glance'] * (.7 * swing(u, .1) + .4 * swing(2 * u, .3))
    rig.turn(pose, HEAD, x=c['nod'] - c['level'] * total, y=glance, z=.25 * glance)
    for k, b in enumerate(CREST):
        rig.turn(pose, b, x=c['crest'] * (1 + k) * tr['crest'][k][t], z=.4 * c['crest'] * swing(u, .2 + .1 * k))
    # wings: the stroke, the leading edge trailing the stroke (twist), swept back on the recovery
    for bone, sign, key, scale in ((WING_R, 1, 'wr', 1.), (WING_L, -1, 'wl', .96)):
        s = tr[key][t]
        angle = c['top'] + (c['bot'] - c['top']) * s * scale
        v = (tr[key][(t + 1) % n] - tr[key][(t - 1) % n]) / 2
        v *= n / (2 * len(c['beats']))
        rig.turn(pose, bone, x=-c['wing'] * 14 * v, y=sign * (c['wing'] * 10 * (s - .5) - c['wing'] * 8 * v), z=sign * angle)
    # the tail drags behind the heave and swishes from side to side
    for k, b in enumerate(TAIL):
        a = c['drag'] * (.5 + .3 * k) * tr['tail'][k][t] * .3 + .0
        y = c['swish'] * (.4 + .3 * k) * swing(u, .2 + .09 * k) + (c['flutter'] * swing(2 * u, .2 + .1 * k) if k == 4 else 0)
        rig.turn(pose, b, x=a, y=y)
    return pose


def root_at(frames, c, t, n):
    """The root pose at tick t: the same distance every tick (the field speed), no easing inside the loop."""
    root = list(frames[0][0])
    if c['n'] is None:
        root[8] = frames[0][0][8] + round((frames[-1][0][8] - frames[0][0][8]) * c['loops'] * t / n)
    return root


SOURCE = 'b7f5c4e585512ef636fdc88d79c41b76120564f85a49f0c2879ecc08efe3f033'


def author(model, skeleton):
    """`model` with the five field slots replaced -> (bytes, checks)."""
    if hashlib.sha256(model).hexdigest() != SOURCE:
        raise ValueError('Quetzalmon flight requires the reviewed pinned source')
    mmd.exe().add_type(SPECIES, skeleton)
    old = mmd.MMD.parse(model, NB)
    old.type = SPECIES
    rest = [list(v) for v in animsheet.slot_frames(old, NB, 0)[0][0]]
    result = copy.deepcopy(old)
    streams, checks = {}, []
    for slot in (0, 2, 3, 4):
        c = CLIPS[CLIP_OF_SLOT[slot]]
        frames, loop, events = animsheet.slot_frames(old, NB, slot)
        assert loop == 0, (slot, loop)
        period = len(frames) - 1
        n = c['n'] or period * c['loops']
        # a longer loop plays the earlier one again: its footstep sounds repeat, the root's step per tick stays
        events = [(e[0] + k * period, e[1], dict(e[2], frame=e[2]['frame'] + k * period))
                  for k in range(1 if c['n'] else c['loops']) for e in events]
        rig = Rig(old, skeleton)
        tr = tracks(c, n)
        out = [pose_at(rig, rest, root_at(frames, c, t, n), c, tr, t, n) for t in range(n + 1)]
        out = [[[round(x) for x in v] for v in pose] for pose in out]
        # one constant lift for the whole loop puts the lowest point of the mesh `clear` units above the floor
        low = max(max(v[1] for tri in animsheet.world_tris(old, [[4096, 4096, 4096, 0, 0, 0, 0, 0, 0]] + pose[1:], skeleton)
                      for v in tri[0]) for pose in out)
        for pose in out:
            pose[1][7] += round(-c['clear'] - low)
        mmd.close_loop(out, 0)
        streams[slot] = len(result.anims.anims)
        result.anims.anims.append(mmd.encode_anim(out, NB, 0, list(events), tol=1))
    streams[1] = streams[0]
    for slot in SLOTS:
        result.anims.table[slot] = streams[slot]
    for anim in result.anims.anims:
        anim.tail = b''
    result.anims.anims, result.anims.table = motioncyclelayer.share_identical_streams(result.anims.anims,
                                                                                    result.anims.table)
    output = result.build()
    effective = mmd.MMD.parse(output, NB)
    effective.type = SPECIES
    assert effective.tmd.build() == old.tmd.build()
    assert changed_programs(old, effective) == list(SLOTS), changed_programs(old, effective)
    for slot in SLOTS:
        samples, loop, _ = animsheet.slot_frames(effective, NB, slot)
        assert loop == 0
        checks.append(dict(slot=slot, ticks=len(samples) - 1,
                           root_per_tick=round((samples[-1][0][8] - samples[0][0][8]) / (len(samples) - 1), 1)))
    return output, dict(checks=checks, storage=motionstorage.require(output, NB))


def build(data, skeleton):
    output, extra = author(data, skeleton)
    return output, dict(field_flight=extra, output_sha256=hashlib.sha256(output).hexdigest())
