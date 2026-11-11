"""Syakomon's field idle, walk, tired walk and run: a clam that hops on its shell (species 283).

The import's four clips were one 43-tick performance (the shell lifting 60 units and the mouth opening and closing once)
with only the root faster, so the walk, the tired walk and the run were the idle sliding over the ground (the lowest
point of the shell slipped 99 to 135 % of the root's speed). Offline only (player builds replay the pinned delta):
`tools/models/edit.py get 283` on the commit before this change, then
`python3 -m tools.models.field_animations.syakomon_hop --source THAT.MMD --out AFTER.MMD` and `edit.py put 283 AFTER.MMD`.

The model has three visible pieces, all hinged at the back of the shell: bone 1 the lower shell (the body: the other two
hang from it), bone 6 the upper shell with its row of teeth (the mouth is the gap between the two, at the front, towards
-z) and bone 2 the purple tail fin at the back. Bones 3, 4 and 5 are tiny hidden pieces and stay as they were; the eyes
are painted on the shell, so the blink (texture moves) of every clip is kept as it was.

Every clip is written as a whole loop of body terms (the body's turn about its middle, its height, its place along the
ground, the mouth's angle, the fin's three turns), and the lower shell is then lowered or lifted so that its lowest point
is exactly at the floor in a stance and clear of it in the air:

- Walk (28 ticks, two hops at 16 units a tick): the shell crouches on the floor, rocks back, then springs forward in a hop of about
  30 units, landing nose down. Stance is planted: the body moves back against the root as fast as the root goes forward, so
  the ground under it does not slide; the flight is faster than the root to cover the stride. The mouth opens in the rise,
  late, and claps shut a little after landing; the fin trails the rise and whips on the landing; the hops alternate sides
  (roll, a little yaw, sideways sway), so the pair of hops is the loop.
- Tired walk (36 ticks, two hops at 11 units): a long low shuffle, 9 ticks of the 18 on the floor dragging at a quarter of the
  root's speed and low hops of 9 units, the nose down, the mouth half shut and drooping, the fin dragging.
- Run (27 ticks, three hops at 38 units): short crouch, long bounds of 46 units pitched 8 degrees forward, the mouth flapping
  fast and wide (second flap on the landing), the fin whipping.
- Idle (96 ticks): three slow breaths, the mouth opening a few degrees and closing late, the body rising and falling a few
  units and turning slowly, the fin swaying about its front end with its own longer rhythm. The lowest point stays at the floor.

Every motion is a sum of a fundamental and its second harmonic, or a damped spring following a drive (mouth, fin), so
nothing is a pure sinusoid and the follow-through arrives later than the body. Every clip repeats exactly (the last
sample is the first with the root travelled), the root moves the same distance every tick, and slots 1, 18 and 33,
which share the idle's program, follow it.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet  # noqa: E402
import mmd  # noqa: E402
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402

SPECIES, NB = 283, 7
SOURCE = '1a819e38e826c50cfe7083568bf6165fb20e2c4955d698754376e2202572f75e'   # edit.py get 283 before this change
SLOTS = (0, 2, 3, 4)
SHARED_WITH_IDLE = (1, 18, 33)
CLIP_OF_SLOT = {0: 'idle', 2: 'walk', 3: 'tired', 4: 'run'}
LOWER, FIN, UPPER = 1, 2, 6
SHELL = (LOWER, FIN, UPPER)
HINGE = np.array([0., -168., 99.])         # where the shell is hinged, in the model's rest frame (y down, front towards -z)
BODY_CENTRE = np.array([0., -135., -10.])  # the body turns about it
FIN_ROOT = np.array([0., -10., -22.])      # the fin turns about its front end (relative to the hinge)
FIN_PITCH = (4., 22.)                     # degrees the fin may turn (positive raises its tail)
FLOOR = -74.0                              # the import's lowest shell point at rest: the floor the clips keep to
D = 4096 / 360.0
SUPPORT = 7.0                             # softness (units) of the support point
ALT = .15                                  # hops alternate in size by this share
SUB = 8                                    # sub-steps of a tick for the springs

# n: ticks of the loop; hops: hops in it; v: root units a tick; stand: share of a hop on the floor; drag: ground speed
# in that stance as a share of v; hop: height (units); pitch: (land nose down, take off nose up, mean lean) degrees;
# roll/yaw/sway: the alternating waddle (degrees, degrees, units); gape: mouth angle (rest, flight peak, spring period
# in ticks, damping); fin: (pitch drive, mean pitch, roll, spring period); blink: tick of the blink (None: none)
CLIPS = {
    'walk': dict(n=28, hops=2, v=16., stand=.4, drag=0., hop=30., pitch=(7., 9., 0.), roll=4.5, yaw=3.5, sway=4.5,
                 gape=(2.5, 17., 6., .55), fin=(2.0, 10., 5., 6.5), blink=17),
    'tired': dict(n=36, hops=2, v=11., stand=.5, drag=.25, hop=12., pitch=(5., 4., 7.), roll=3., yaw=2., sway=2.5,
                  gape=(2.5, 8., 9., .8), fin=(1.0, 6., 3.5, 10.), blink=24),
    'run': dict(n=27, hops=3, v=38., stand=.28, drag=0., hop=46., pitch=(9., 10., 8.), roll=3.5, yaw=3., sway=3.5,
                gape=(2.5, 24., 4.5, .5), fin=(2.6, 12., 5., 4.5), blink=15),
}
IDLE = dict(n=96)


def smooth(q):
    q = min(1.0, max(0.0, q))
    return q * q * q * (q * (6 * q - 15) + 10)


def spring(drive, period, zeta):
    """The steady state of a damped spring (natural period in ticks) following a periodic drive sampled per tick."""
    n = len(drive)
    w = 2 * math.pi / period
    dt = 1.0 / SUB
    x = v = float(drive[0])
    v = 0.
    out = []
    for loop in range(6):
        out = []
        for i in range(n):
            a, b = drive[i], drive[(i + 1) % n]
            for k in range(SUB):
                target = a + (b - a) * k / SUB
                v += (w * w * (target - x) - 2 * zeta * w * v) * dt
                x += v * dt
            out.append(x)
    return np.array(out)


def harmonics(t, n, cycles, ph=0., second=0.3, ph2=0.7):
    """A loose periodic wave: `cycles` of the fundamental in n ticks plus a second harmonic."""
    a = 2 * math.pi * cycles * np.asarray(t, float) / n
    return np.sin(a + ph) + second * np.sin(2 * a + ph2 + 2 * ph)


class Shell:
    """Poses the three pieces and keeps the shell's lowest point on the floor."""

    def __init__(self, model, skeleton, base):
        self.model, self.base = model, base
        self.verts = {b: np.array(model.tmd.obj_verts(skeleton[b][0]))[:, :3].astype(float) for b in SHELL}

    @staticmethod
    def rmat(rx=0., ry=0., rz=0.):
        return np.array(mmd.rot_matrix(rx * D, ry * D, rz * D))

    def world(self, body, off, gape, fin):
        """Vertices of the shell pieces for the body turn (pitch, yaw, roll degrees), offset, mouth angle and fin turn."""
        R = self.rmat(*body)
        R6 = self.rmat(-gape, 0, 0)
        R2 = self.rmat(*fin)
        t2 = FIN_ROOT - R2 @ FIN_ROOT
        t1 = R @ (HINGE - BODY_CENTRE) + BODY_CENTRE + off
        out = {LOWER: self.verts[LOWER] @ R.T + t1,
               UPPER: (self.verts[UPPER] @ R6.T) @ R.T + t1,
               FIN: ((self.verts[FIN] @ R2.T) + t2) @ R.T + t1}
        return out, (R, R6, R2, t1, t2)

    def pose(self, body, off, lift, gape, fin, ground=None):
        """The pose with the lowest point of the shell `lift` units above the floor. `ground`: where the shell's support
        point (the weighted mean of its lowest vertices) is along z, against the root; the body is moved to put it there."""
        off = np.array(off, float)
        world, _ = self.world(body, off, gape, fin)
        low = max(float(w[:, 1].max()) for w in world.values())
        off[1] += FLOOR - lift - low
        if ground is not None:
            world, _ = self.world(body, off, gape, fin)
            pts = np.concatenate([world[b] for b in SHELL])
            wgt = np.exp((pts[:, 1] - pts[:, 1].max()) / SUPPORT)
            off[2] += ground - float((wgt * pts[:, 2]).sum() / wgt.sum())
        _, (R, R6, R2, t1, t2) = self.world(body, off, gape, fin)
        p = copy.deepcopy(self.base)
        p[0] = [4096] * 3 + [0] * 6
        p[LOWER][3:9] = [*(a * D for a in body), *t1]
        p[UPPER][3:9] = [-gape * D, 0, 0, 0, 0, 0]
        p[FIN][3:9] = [*(a * D for a in fin), *t2]
        return p


def blink_events(tick, slow=False):
    """The eye's texture moves: open at tick 0, then half shut, shut, half shut and open from `tick`."""
    def move(frame, a, b):
        return [(frame - 1, 'tex', dict(op='tex', frame=frame, src=a, size=(4, 16), dst=(24, 0))),
                (frame - 1, 'tex', dict(op='tex', frame=frame, src=b, size=(6, 20), dst=(1, 82)))]
    open_, half, shut = ((24, 16), (22, 80)), ((24, 32), (16, 80)), ((24, 48), (10, 80))
    seq = [half] + [shut] * (3 if slow else 1) + [half, open_]
    ev = move(1, *open_)
    for i, (a, b) in enumerate(seq):
        ev += move(tick + i + 1, a, b)
    return ev


def hop_series(c):
    """Per-tick drives of a hopping clip."""
    n, T = c['n'], c['n'] / c['hops']
    t = np.arange(n, dtype=float)
    phase = (t / T) % 1.0
    d = c['stand']
    lift = np.zeros(n)
    flight_u = np.zeros(n)
    stance_u = np.zeros(n)
    for i, f in enumerate(phase):
        if f < d:
            stance_u[i] = f / d
        else:
            u = (f - d) / (1 - d)
            flight_u[i] = u
            lift[i] = c['hop'] * (1 + ALT * (-1) ** int(t[i] // T)) * math.sin(math.pi * u ** .95) ** 1.25
    # ground speed: the stance drags at `drag` of the root's speed, the flight covers the rest of the stride
    sub = 16
    fine = np.arange(n * sub) / sub
    ph = (fine / T) % 1.0
    flight = ph >= d
    w = np.where(flight, .6 + .4 * np.sin(math.pi * np.clip((ph - d) / (1 - d), 0, 1)), c['drag'])
    stride = c['v'] * T
    per_cycle = w.sum() / sub / c['hops']
    w = w * (stride / per_cycle)
    s = np.concatenate([[0.], np.cumsum(w) / sub])[::sub][:n]
    ahead = s - c['v'] * t                      # the body's place along the ground against the root (forward positive)
    ahead -= ahead.mean()
    # pitch: nose down at the landing, rocking back through the stance to nose up at the take-off, then forward in flight
    land0, off0, lean = c['pitch']
    pitch = np.zeros(n)
    for i, f in enumerate(phase):
        k = (1 + ALT * (-1) ** int(t[i] // T))              # every other hop a little bigger
        land, off = land0 * k, off0 * k
        if f < d:
            pitch[i] = lean + land + (-off - land) * smooth(f / d) ** 1.7
        else:
            pitch[i] = lean - off + (off + land) * smooth((f - d) / (1 - d)) ** .6
        pitch[i] += .45 * land * math.exp(-((f - .06) / .07) ** 2)         # the nose dips a little further on the landing
    return dict(t=t, T=T, phase=phase, lift=lift, flight_u=flight_u, ahead=ahead, pitch=pitch)


def hop_clip(name, model_shell):
    c = CLIPS[name]
    n, T = c['n'], c['n'] / c['hops']
    s = hop_series(c)
    t = s['t']
    lift = s['lift']
    vy = np.gradient(np.concatenate([lift, lift[:1]]))[:n] * 1.0
    # mouth: opens in the rise (late), snaps shut a little after the landing
    gape_rest, gape_peak, period, zeta = c['gape']
    drive = np.array([gape_rest + (gape_peak - gape_rest) * (math.sin(math.pi * min(1., u * 1.25)) ** 1.3 if u > 0 else 0.)
                      for u in s['flight_u']])
    if name == 'run':
        drive += np.array([5. * math.exp(-((f - c['stand'] * .6) / .09) ** 2) for f in s['phase']])    # second flap on the landing
    gape = np.maximum(spring(drive, period, zeta), 1.2)
    # fin (it never yaws: the yawed fan cuts the shell deeper than the import's does): its tail trails the vertical motion
    # and whips up on the landing, rolls from side to side across the hops
    fpd, fmean, froll, fper = c['fin']
    fin_pitch = spring(fmean - fpd * vy + .35 * fpd * np.roll(vy, 2), fper, .4)
    fin_pitch = np.clip(fin_pitch, FIN_PITCH[0], np.clip(FIN_PITCH[1] - .9 * (gape - 8.), 8., FIN_PITCH[1]))
    sweep = np.zeros(n)
    fin_roll = spring(froll * harmonics(t, n, c['hops'] / 1.0, .4, .35) + .5 * froll * harmonics(t, n, c['hops'] / 2.0, 2.0, .3),
                      fper, .5) * np.clip(1 - np.maximum(gape - 12., 0.) / 10., 0., 1.)       # a wide mouth leaves the fin square
    # the waddle: alternates every hop
    roll = c['roll'] * harmonics(t, n, c['hops'] / 2.0, 0., .25, .5)
    yaw = c['yaw'] * harmonics(t, n, c['hops'] / 2.0, 1.2, .3, 1.0)
    sway = c['sway'] * harmonics(t, n, c['hops'] / 2.0, .3, .25, .4)
    frames = []
    for i in range(n):
        body = (s['pitch'][i], yaw[i], roll[i])
        off = (sway[i], 0., 0.)
        frames.append(model_shell.pose(body, off, lift[i], gape[i], (fin_pitch[i], sweep[i], fin_roll[i]), ground=-s['ahead'][i]))
    return frames, c


def idle_clip(model_shell):
    n = IDLE['n']
    t = np.arange(n, dtype=float)
    breath = .5 - .5 * np.cos(2 * math.pi * 3 * t / n + .0) + .12 * np.sin(2 * math.pi * 6 * t / n + 1.1)
    gape = np.maximum(spring(2. + 6.5 * breath, 8., .75), 1.5)
    lift = 3.2 * spring(breath, 6., .8)
    lift -= lift.min()
    pitch = 1.2 + 1.6 * harmonics(t, n, 3, 1.4, .3) + 1.0 * harmonics(t, n, 1, .5, .3)
    roll = 1.7 * harmonics(t, n, 1, 0., .3) + .5 * harmonics(t, n, 2, 1., .2)
    yaw = 2.6 * harmonics(t, n, 1, 2., .3, .6)
    fin_yaw = np.zeros(n)
    fin_pitch = np.clip(spring(10. + 5. * harmonics(t, n, 3, 2.2, .3) + 3. * harmonics(t, n, 2, 0.4, .3), 8., .6), FIN_PITCH[0], 20.)
    fin_roll = spring(3.5 * harmonics(t, n, 2, 1.7, .3) + 1.5 * harmonics(t, n, 1, 0., .2), 10., .5)
    sx = 2.5 * harmonics(t, n, 1, .8, .25)
    sz = 3.0 * harmonics(t, n, 1, 2.4, .25)
    frames = [model_shell.pose((pitch[i], yaw[i], roll[i]), (sx[i], 0., sz[i]), lift[i], gape[i],
                               (fin_pitch[i], fin_yaw[i], fin_roll[i])) for i in range(n)]
    return frames


def author(data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError("Syakomon's hopping clips are written over the reviewed import")
    mmd.exe().add_type(SPECIES, skeleton)
    old = mmd.MMD.parse(data, NB)
    old.type = SPECIES
    base = [[round(x) for x in v] for v in animsheet.slot_frames(old, NB, 0)[0][0]]
    shell = Shell(old, skeleton, base)
    result = copy.deepcopy(old)
    streams, ticks = {}, {}
    for slot in SLOTS:
        name = CLIP_OF_SLOT[slot]
        frames_, loop, _ = animsheet.slot_frames(old, NB, slot)
        assert loop == 0, (slot, loop)
        if name == 'idle':
            poses, speed, blink = idle_clip(shell), 0., (30, 70)
            ev = blink_events(30) + blink_events(70)[2:] + blink_events(77)[2:]
        else:
            poses, c = hop_clip(name, shell)
            speed = c['v']
            ev = blink_events(c['blink'], slow=(name == 'tired'))
        n = len(poses)
        out = []
        for i, p in enumerate(poses):
            q = [[round(x) for x in b] for b in p]
            q[0] = [4096] * 3 + [0, 0, 0, 0, 0, -round(speed * i)]
            out.append(q)
        out.append(copy.deepcopy(out[0]))
        out[-1][0] = [4096] * 3 + [0, 0, 0, 0, 0, -round(speed * n)]
        mmd.close_loop(out, 0)
        ev = sorted(ev, key=lambda e: e[0])
        streams[slot] = len(result.anims.anims)
        result.anims.anims.append(mmd.encode_anim(out, NB, 0, ev, tol=1, repeats=False))
        ticks[slot] = n
    for slot in SHARED_WITH_IDLE:
        result.anims.table[slot] = streams[0]
    for slot in SLOTS:
        result.anims.table[slot] = streams[slot]
    for anim in result.anims.anims:
        anim.tail = b''
    used = sorted({i for i in result.anims.table if i is not None})
    renumber = {i: k for k, i in enumerate(used)}
    result.anims.anims = [result.anims.anims[i] for i in used]
    result.anims.table = [None if i is None else renumber[i] for i in result.anims.table]
    output = result.build()
    effective = mmd.MMD.parse(output, NB)
    effective.type = SPECIES
    assert effective.tmd.build() == old.tmd.build()
    changed = changed_programs(old, effective)
    assert set(changed) == set(SLOTS) | set(SHARED_WITH_IDLE), changed
    return output, dict(ticks=ticks, storage=motionstorage.audit(output, NB), species=SPECIES, source_sha256=SOURCE,
                        changed_slots=changed)


def build(data, skeleton):
    output, report = author(data, skeleton)
    return output, dict(report, output_sha256=hashlib.sha256(output).hexdigest())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    skeleton = [tuple(b) for b in json.loads((ROOT / 'content/species/283-syakomon.json').read_text())['model']['skeleton']]
    data, report = build(args.source.read_bytes(), skeleton)
    args.out.write_bytes(data)
    print(args.out, len(data), 'B', json.dumps(report, default=str))


if __name__ == '__main__':
    main()
