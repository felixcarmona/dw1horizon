"""Pukumon's field clips (species 401): an idle and a walk, tired walk and run on its two big fists.

Pukumon is a spiked puffer fish that floats on two arms. Bones: 1 the shell (2 its other half, 14 and 15 the belly under
them), 3 and 4 the rear fins, 5 and 6 the tail, 7-8-9 the left arm (shoulder, forearm, fist), 10-11-12 the right arm,
13 the lower jaw. Forward is -z.

The imported clips all hold the LEFT arm up beside the head (shoulder pitched back 80-85 degrees, forearm another 95) while
the right arm hangs, and all four field clips share one fin and tail flap, one jaw and a body that hardly moves: one
animation for everything. The cause is in the source clips (every program of the model, attacks included, starts
from that pose), not in the rig: the two arms' meshes and offsets mirror exactly. Here the fists are the feet:

- Each fist has a stance and a swing. In stance the fist stands flat on the floor and stays still in the world while the
  body vaults over it; in the swing it lifts, reaches ahead and lands. The left arm is solved like the right one mirrored
  in the world (`quadruped.Rig`'s two-bone solve, the left reference being the right arm's mirror), so no arm is held up.
- The body is written from the fists up: it stands as high as the arms allow, dips at each landing, surges and sways
  over the loaded fist, leans into the pace; the tail beats with the pace (lazy, steady, heavy, fast), the fins flutter
  and the jaw works with the breath, each at its own rate in each clip.

  idle      96 ticks: both fists on the floor, three slow breaths, the weight passing from side to side, the unloaded fist
            rocking, the tail and fins drifting, a yawn
  walk      16 ticks, 19 units a tick: alternating fists, short flight between them, a bobbing, swaying body
  tired     24 ticks, 12 units a tick: the body low and slumped forward, the fists hauled forward just clear of the floor,
            heavy dips, the tail drooping and the jaw hanging
  run       12 ticks, 38 units a tick: a leaning bound from fist to fist with a flight between them, the tail streaming back

Offline: `tools/models/edit.py get 401` on the commit before this change, then
`python3 -m tools.models.field_animations.pukumon_gait --source THAT.MMD --out AFTER.MMD` and `edit.py put 401 AFTER.MMD`.
The mesh and every other program (attacks, battle idle, care clips) are kept as they are; the clips that share a program
with a slot this module changes (the battle idle 33, the battle walk 35 and run 36) keep their own copy.
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
import motioncyclelayer  # noqa: E402
import motionstorage  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402
from tools.models.field_animations import quadruped  # noqa: E402
from tools.models.field_animations.quadruped import mul, tr, rot, set_rot  # noqa: E402

SPECIES = 401
SOURCE = '277100ba2719cc8d80c4eeb9141162a269885aefed99b4f1d5f8d62cdac0e6f7'   # `edit.py get 401` before this change
PARENTS = [-1, 0, 1, 1, 1, 1, 5, 1, 7, 8, 1, 10, 11, 1, 1, 2]
NB = 16
DEG = 4096 / 360
TAU = 2 * math.pi
SLOTS = (0, 2, 3, 4)
BODY, FIN_L, FIN_R, TAIL, TAIL2, JAW = 1, 3, 4, 5, 6, 13
ARMS = {'LF': (7, 8, 9, -1, True), 'RF': (10, 11, 12, 1, True)}
PROFILE = dict(species=SPECIES, legs=ARMS, pole={True: [0.45, 0.25, 1.0]}, sole={True: [0, 0, 0]}, clear=0, name='Pukumon')
FIST_HEIGHT = 61           # the fist's bottom below its bone, at rest
SHOULDER_X = 76
REACH = 0.9                # of the arm's length: the farthest the solve is asked to stretch
LA, LB = 60.8, 63.0        # upper arm and forearm lengths
CLEAR = 2.0                # a planted fist's sole stands this far above the floor (the encoding rounds by up to 1)

# One row per clip. period/stance in ticks; speed in units a tick; height = the shoulders' standing height; lift = the
# swinging fist's peak above the floor; ahead = how far ahead of the shoulders a fist lands past the middle of its
# stance; dip = the dip at a landing; hop = the flight arc's height; surge = the body's lead and lag over its steady
# travel; sway/roll/yaw = the body's side shift (units) and turns (degrees); lean = nose-down pitch.
GAITS = {
    2: dict(name='walk', period=16, stance=6, speed=19, height=150, lift=46, ahead=14, dip=7, hop=8, surge=6, sway=9,
            roll=3.0, yaw=4.0, lean=5, lean_step=2.5, tail=11, tail_rate=1, tail_pitch=9, fin=9, fin_rate=2, fin_pitch=-6,
            jaw=7, jaw_rate=2, jaw_base=6, swing_q=1.0, bulge=14, curl=26, toe_in=18),
    3: dict(name='tired walk', period=24, stance=10, speed=12, height=126, lift=11, ahead=8, dip=9, hop=0, surge=5,
            sway=10, roll=4.0, yaw=2.5, lean=15, lean_step=3.0, tail=5, tail_rate=1, tail_pitch=-6, fin=4, fin_rate=1,
            fin_pitch=-16, jaw=4, jaw_rate=1, jaw_base=21, swing_q=1.0, bulge=8, curl=12, toe_in=12),
    4: dict(name='run', period=12, stance=3, speed=38, height=146, lift=50, ahead=10, dip=10, hop=30, surge=10, sway=7,
            roll=2.5, yaw=5.0, lean=14, lean_step=3.5, tail=15, tail_rate=2, tail_pitch=15, fin=14, fin_rate=2,
            fin_pitch=14, jaw=10, jaw_rate=2, jaw_base=22, swing_q=0.7, bulge=18, curl=34, toe_in=20),
}
IDLE_TICKS = 96


# ------------------------------------------------------------------ curves
def smooth(u):
    return quadruped.smooth(u)


def lowpass(values, passes=1):
    """A periodic 1-2-1 smoothing of a closed series."""
    out = list(values)
    n = len(out)
    for _ in range(passes):
        out = [0.25 * out[(i - 1) % n] + 0.5 * out[i] + 0.25 * out[(i + 1) % n] for i in range(n)]
    return out


def softmin(a, b, k=6.0):
    """A smooth minimum that never exceeds either."""
    m = min(a, b)
    return m - k * math.log(math.exp(-(a - m) / k) + math.exp(-(b - m) / k))


def reach_height(d, e, fist_y):
    """The highest the shoulders can stand over a fist at fore-aft distance d, sideways e, bone height fist_y."""
    r = REACH * (LA + LB)
    return fist_y + math.sqrt(max(r * r - d * d - e * e, 1.0))


# ------------------------------------------------------------------ the rig
class Pukumon:
    def __init__(self, model, skeleton):
        self.m = model
        self.rig = quadruped.Rig(model, skeleton, PROFILE)
        idle = animsheet.slot_frames(model, NB, 0)[0]
        self.rest = [list(v) for v in idle[0]]
        self.rest[0] = [4096] * 3 + [0] * 6
        for b in (FIN_L, FIN_R, TAIL, TAIL2, JAW):
            self.rest[b][3:6] = [round(sum(f[b][c] for f in idle) / len(idle)) for c in (3, 4, 5)]
        self.rest[JAW][3] = 26                          # closed
        self.rest[BODY][3:6] = [0, 0, 0]
        self.hist = {}
        self.clear = CLEAR

    def fist_rot(self, side, pitch, toe_in):
        return rot([pitch, -side * toe_in, 0])

    def planted_y(self, name, pitch, toe_in):
        """The fist bone's height above the floor that rests the fist's lowest vertex CLEAR above it."""
        paw, side = ARMS[name][2], ARMS[name][3]
        world = self.fist_rot(side, pitch, toe_in)
        return max(sum(world[1][k] * v[k] for k in range(3)) for v in self.rig.verts[paw]) + self.clear

    def pose(self, body, fists, sec):
        """One tick. body: height of the shoulders over the floor, sideways shift, z of the body bone, pitch/yaw/roll;
        fists: {arm: (x, height of the fist bone, z, pitch, toe-in)}; sec: the tail, fins and jaw (degrees)."""
        pose = copy.deepcopy(self.rest)
        hist = self.hist
        pose[BODY][6:9] = [round(body['x']), round(-body['height']), round(body['z'])]
        set_rot(pose, BODY, rot([body['pitch'], body['yaw'], body['roll']]), hist)
        for name, (x, y, z, pitch, toe_in) in fists.items():
            up, lo, paw, side, front = ARMS[name]
            lower, short = self.rig.solve(pose, name, [x, -y, z], hist)
            set_rot(pose, paw, mul(tr(lower), self.fist_rot(side, pitch, toe_in)), hist)
        for b, (rx, ry, rz) in sec.items():
            for c, d in zip((3, 4, 5), (rx, ry, rz)):
                pose[b][c] = self.rest[b][c] + round(d * DEG)
        return pose


# ------------------------------------------------------------------ secondary parts
def secondary(g, phi, lag_bob):
    """Tail, fins and jaw at a cycle phase; lag_bob is the body's recent vertical speed (units a tick, up positive)."""
    tail = lambda k: g['tail'] * (1 + 0.5 * k) * math.sin(TAU * (g['tail_rate'] * phi - 0.12 * k))
    pitch = g['tail_pitch'] - 0.35 * lag_bob
    flap = lambda d: g['fin'] * math.sin(TAU * (g['fin_rate'] * phi - d)) + g['fin_pitch']
    return {
        TAIL: (pitch + 0.3 * tail(0), tail(0), 0.0),
        TAIL2: (0.4 * pitch + 0.3 * tail(1), tail(1), 0.0),
        FIN_L: (flap(0.0), 0.4 * flap(0.1) - 4, 0.3 * flap(0.2)),
        FIN_R: (flap(0.05), -0.4 * flap(0.15) + 4, -0.3 * flap(0.25)),
        JAW: (g['jaw_base'] - 26 + g['jaw'] * (0.5 + 0.5 * math.sin(TAU * (g['jaw_rate'] * phi - 0.3))), 0.0, 0.0),
    }


# ------------------------------------------------------------------ the gaits
def gait(pk, slot):
    g = GAITS[slot]
    P, s, v = g['period'], g['stance'], g['speed']
    half = v * s / 2
    toe = g['toe_in']
    flat = {name: pk.planted_y(name, 0, toe) for name in ARMS}
    first = {'RF': 0.0, 'LF': 0.5}                       # the cycle fraction at which each fist lands

    def surge(t):
        return g['surge'] * math.sin(TAU * (2 * t / P - 0.1))

    def X(t):
        return v * t + surge(t)                           # the body's forward travel in the world

    def fist(name, t):
        """(world forward distance, lift above the floor, swing fraction or None while planted)."""
        k, u = divmod(t / P - first[name], 1.0)
        td = (k + first[name]) * P
        F = X(td) + half + g['ahead']
        if u * P < s:
            return F, 0.0, None
        w = (u * P - s) / (P - s)
        F2 = X(td + P) + half + g['ahead']
        return F + (F2 - F) * w * w * (3 - 2 * w), g['lift'] * math.sin(math.pi * w) ** g['swing_q'], w

    heights = []
    for t in range(P):
        limit, planted = 1e9, 0
        for name in ARMS:
            z, lift, w = fist(name, t)
            limit = min(limit, reach_height(z - X(t), 12, flat[name] + lift))
            planted = max(planted, 1.0 if w is None else 0.0)
        mid = s / (2 * P)
        landed = (0.5 + 0.5 * math.cos(TAU * 2 * (t / P - 0.03))) ** 2
        free = g['height'] - g['dip'] * landed + g['hop'] * (1 - planted)
        heights.append(softmin(free, limit))
    heights = lowpass(heights, 1)
    frames = []
    for t in range(P + 1):
        tt = t % P
        phi = tt / P
        mid = s / (2 * P)
        loaded = math.cos(TAU * (phi - mid))               # +1 over the right fist's stance, -1 over the left's
        vb = (heights[tt] - heights[(tt - 1) % P])
        body = dict(height=heights[tt], x=g['sway'] * loaded, z=-2 - surge(t),
                    pitch=g['lean'] + g['lean_step'] * math.cos(TAU * 2 * (phi - mid - 0.1)),
                    yaw=g['yaw'] * math.sin(TAU * (phi - mid)), roll=g['roll'] * loaded)
        fists = {}
        for name, (up, lo, paw, side, front) in ARMS.items():
            z, lift, w = fist(name, t)
            pitch = 0.0 if w is None else g['curl'] * math.sin(math.pi * w) - 4 * smooth((w - 0.8) / 0.2)
            x = side * (SHOULDER_X + 10 + (0 if w is None else g['bulge'] * math.sin(math.pi * w)))
            fists[name] = (x, pk.planted_y(name, pitch, toe) + lift, -(z - v * t), pitch, toe)
        frames.append((pk.pose(body, fists, secondary(g, phi, vb)), v * t))
    return frames


def idle(pk):
    n = IDLE_TICKS
    toe = 14
    flat = {name: pk.planted_y(name, 0, toe) for name in ARMS}
    frames = []
    g = dict(tail=7, tail_rate=2, tail_pitch=2, fin=5, fin_rate=4, fin_pitch=-2, jaw=3, jaw_rate=3, jaw_base=27)
    for t in range(n + 1):
        tt = t % n
        phi = tt / n
        breath = 0.5 - 0.5 * math.cos(TAU * 3 * phi)
        shift = math.sin(TAU * phi)
        yawn = smooth((tt - 54) / 8) * (1 - smooth((tt - 70) / 10))
        body = dict(height=154 + 3.5 * breath + 1.5 * yawn, x=11 * shift, z=-2, pitch=1.0 - 4.0 * yawn + 1.2 * math.sin(TAU * 3 * phi),
                    yaw=3 * math.sin(TAU * (2 * phi + 0.1)), roll=2.2 * shift)
        fists = {}
        for name, (up, lo, paw, side, front) in ARMS.items():
            unload = smooth(max(0.0, -side * shift) / 0.8)          # the unloaded fist rocks; the loaded one stays put
            rock = 7 * math.sin(TAU * (2 * phi + (0 if side > 0 else 0.25)))
            lift = 7 * unload
            pitch = -10 * unload
            fists[name] = (side * (SHOULDER_X + 10 + 4 * unload), pk.planted_y(name, pitch, toe) + lift,
                           -12 - rock * unload, pitch, toe)
        sec = secondary(g, phi, 0.0)
        sec[JAW] = (-26 + 26 + 4 + 30 * yawn + 2.5 * breath, 0.0, 0.0)
        frames.append((pk.pose(body, fists, sec), 0))
    return frames


# ------------------------------------------------------------------ build
def _parse(data, skeleton):
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = len(skeleton)
    model = mmd.MMD.parse(data, len(skeleton))
    model.type = SPECIES
    return model


def clips(old, skeleton):
    pk = Pukumon(old, skeleton)
    out = {}
    for slot in SLOTS:
        pk.hist = {}
        pk.clear = 5.0 if slot == 4 else CLEAR      # the run's landings overshoot a little
        rows = idle(pk) if slot == 0 else gait(pk, slot)
        frames = []
        for pose, forward in rows:
            pose[0][8] = -round(forward)
            frames.append([[int(round(x)) for x in b] for b in pose])
        out[slot] = frames
    return out


def author(data, skeleton):
    old = _parse(data, skeleton)
    new = copy.deepcopy(old)
    report = []
    for slot, frames in clips(old, skeleton).items():
        events = [(t, kind, e) for t, kind, e in animsheet.slot_frames(old, NB, slot)[2] if kind == 'tex' and t == 0]
        mmd.close_loop(frames, 0)
        anim = mmd.encode_anim(frames, NB, 0, events, tol=1)
        new.anims.table[slot] = len(new.anims.anims)      # a program of its own: the battle clips that shared it keep theirs
        new.anims.anims.append(anim)
        n = len(frames) - 1
        report.append(dict(slot=slot, ticks=n, units_per_tick=round(abs(frames[-1][0][8] - frames[0][0][8]) / n, 2),
                           stream_bytes=len(anim.build())))
    for anim in new.anims.anims:
        anim.tail = b''
    new.anims.anims, new.anims.table = motioncyclelayer.share_identical_streams(new.anims.anims, new.anims.table)
    output = new.build()
    actual = _parse(output, skeleton)
    assert actual.tmd.build() == old.tmd.build()
    assert changed_programs(old, actual) == list(SLOTS), changed_programs(old, actual)
    return output, report


def build(data, skeleton):
    if hashlib.sha256(data).hexdigest() != SOURCE or [b[1] for b in skeleton] != PARENTS:
        raise ValueError('Pukumon needs the reviewed sixteen-bone model it had before this change')
    output, report = author(data, skeleton)
    return output, dict(species=SPECIES, source_sha256=SOURCE, output_sha256=hashlib.sha256(output).hexdigest(),
                        changed_slots=list(SLOTS), clips=report, storage=motionstorage.require(output, NB))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    skeleton = json.loads((ROOT / 'content/species/401-pukumon.json').read_text())['model']['skeleton']
    data, proof = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    print(json.dumps(proof, indent=1, default=str))


if __name__ == '__main__':
    main()
