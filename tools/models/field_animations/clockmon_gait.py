"""Clockmon's field clips (species 290): a calm ticking idle, a waddling walk, a heavy tired walk and a bounding run.

Offline authoring script (the model it makes is stored with `tools/models/edit.py put 290 MMD`).

The rig: a hooded rider (bone 1 and its head 13, key 20 and the arms 14-19 that carry the hammer) stands on a clock
chassis (bone 2, a child of the rider's bone) that carries two short legs (3-5 right, 6-8 left: a hip piece, a tall
foot block with a flat sole, and a toe wedge) and two arms (9-10 right, a nut-handed fist; 11-12 left, the cannon).

The imported clips swung the legs 70 degrees out from the hip and slid the feet over the ground at 70-140 % of the
travel, and the idle of the first repair kept only the chassis still. Everything is rebuilt here from the world down:

- The chassis (bone 2) is placed in the world each tick: height, sway, lean, roll and yaw; the rider's bone 1 follows it
  with a lagging rotation of its own about the chassis top (`rider`), so the rider, its hammer, its head and the key
  swing on after the chassis. Bone 1 is the parent of the chassis in the rig, so its local transform is solved from
  the two world transforms.
- A foot is a point on the floor (the toe bone's origin) that stays put in the world while the body passes over it. The
  foot block hangs 38 units below the hip piece, so the legs are straight at rest and short: the foot block pitches on a
  scheduled heel-to-push roll, the hip piece is turned from its rest direction towards the foot block, and the block's
  offset may telescope a few units (`EXT`). The chassis yaws so the hip of the stance foot travels back with it, which
  lets the short legs cover a stride at the speeds below; the chassis height is solved each tick so the planted feet
  stay at the link length. The generator reports the telescoping range and the build fails if it leaves `EXT`.
- The chassis arms swing against the legs about the chassis' own axes; the key and the rider's head follow late.

    python -m tools.models.field_animations.clockmon_gait --source SRC.MMD --out DIR
where SRC is the previously stored model (sha256 below).
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

SPECIES = 290
SOURCE = '5a859faa639782aea5a6387e8b3f3092799e9dda56da6bc0f366c57f8f42cd9e'   # `edit.py get 290` before this change
PARENTS = [-1, 0, 1, 2, 3, 4, 2, 6, 7, 2, 9, 2, 11, 1, 1, 14, 15, 1, 17, 18, 1]
RIDER, CHASSIS, HEAD, KEY = 1, 2, 13, 20
LEGS = {'R': (3, 4, 5, 1), 'L': (6, 7, 8, -1)}      # hip piece, foot block, toe wedge, side (+1 = x > 0)
ARMS = {'R': (9, 10, 1), 'L': (11, 12, -1)}
SLOTS = (0, 2, 3, 4)
FLOOR = -2.0              # the lowest vertex of the rest feet: the model's own ground
TAU = 2 * math.pi
RESIDENT_LIMIT = 100352


def rx(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def ry(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rz(a):
    c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def jerk(x):
    x = min(1.0, max(0.0, x))
    return x ** 3 * (10 - 15 * x + 6 * x * x)


def hold(t, keys):
    """Smooth interpolation through (tick, value) keys, flat tangents."""
    for (a, x), (b, y) in zip(keys, keys[1:]):
        if a <= t <= b:
            return x + (y - x) * smooth((t - a) / (b - a))
    return keys[-1][1]


def wave(phase, lag=0.0, rate=1, harmonic=0.0, h_lag=0.07):
    """A sine of the cycle phase (closed loop for whole `rate`s) with a second harmonic that sharpens it, so that
    nothing is a pure sinusoid."""
    return math.sin(TAU * rate * (phase - lag)) + harmonic * math.sin(TAU * 2 * rate * (phase - lag - h_lag))


class Rig:
    def __init__(self, model, skeleton):
        self.m = model
        self.n = len(skeleton)
        pose = animsheet.slot_frames(model, self.n, 0)[0][0]
        self.rest = [list(b) for b in pose]
        self.rest[0] = [4096] * 3 + [0] * 6
        self.Rl = [np.array(mmd.rot_matrix(*v[3:6])) for v in self.rest]
        self.off = [np.array(v[6:9], float) for v in self.rest]
        self.verts = {b: np.array([v[:3] for v in model.tmd.obj_verts(o)], float) for b, (o, _) in enumerate(skeleton) if o >= 0}
        self.Wr, self.Pr = self.fk({})
        self.hist = {}
        self.floor_y = {}
        # the foot block's reach: hip piece to foot block, foot block to toe point (in the foot block's rest frame)
        self.link = float(np.linalg.norm(self.off[4]))
        self.toe = self.off[5]

    def fk(self, driven):
        """World rotations and positions; `driven` {bone: (W, P or None)} replaces the inherited ones."""
        W, P = [None] * self.n, [None] * self.n
        for b in range(self.n):
            par = PARENTS[b]
            if par < 0:
                W[b], P[b] = np.eye(3), np.zeros(3)
                continue
            Wb, Pb = driven.get(b, (None, None))
            W[b] = Wb if Wb is not None else W[par] @ self.Rl[b]
            P[b] = Pb if Pb is not None else P[par] + W[par] @ self.off[b]
        return W, P

    def lowest(self, W, P, bones):
        return max(float((self.verts[b] @ W[b].T + P[b])[:, 1].max()) for b in bones)

    # -- one foot -----------------------------------------------------------------------------------------------
    def toe_in(self, foot_i):
        return self.toe


    # -- one foot: where its parts stand, independent of the chassis ---------------------------------------------
    def place_foot(self, side, spec):
        """The foot block, toe wedge and toe point of a foot whose toe point is `spec['S']` (the y is moved so the lowest
        vertex of the foot rests on the floor when planted, or is raised when it would sink) and whose foot block is
        pitched `spec['phi']` degrees (positive = toe down)."""
        hip_i, foot_i, toe_i, sd = LEGS[side]
        target = np.array(spec['S'], float)
        phi = spec['phi']
        for k in range(4):
            R4 = rx(phi) @ self.Wr[foot_i]
            P4 = target - R4 @ self.toe
            R5 = R4 @ rx(spec.get('toe', 0.0)) @ self.Rl[toe_i]
            low = self._foot_low(foot_i, toe_i, R4, P4, R5, target)
            if k < 3 and (spec.get('plant') or low > FLOOR) and abs(low - FLOOR) > 0.02:
                target = target + np.array([0.0, FLOOR - low, 0.0])
        return dict(R4=R4, P4=P4, R5=R5, S=target, phi=phi, plant=bool(spec.get('plant')))

    def hip(self, side, ch):
        Rc, Pc = chassis(self, ch)
        return Pc + Rc @ self.off[LEGS[side][0]]

    # -- a pose --------------------------------------------------------------------------------------------------
    def pose(self, ch, geoms, arms, rider, head, key):
        """ch: dict(p: chassis offset (x, y, z) from rest, yaw, pitch, roll degrees); geoms: place_foot results;
        arms: {'R': (shoulder pitch, shoulder roll, elbow pitch), ...}; rider: (pitch, roll, yaw) of the rider about the
        chassis top; head: (pitch, yaw, roll) in the rider's frame; key: (pitch, roll)."""
        Rc, Pc = chassis(self, ch)
        E = rx(rider[0]) @ rz(rider[1]) @ ry(rider[2])
        W1 = Rc @ E @ self.Wr[RIDER]
        P1 = Pc + Rc @ (self.Pr[RIDER] - self.Pr[CHASSIS])
        driven = {RIDER: (W1, P1), CHASSIS: (Rc, Pc)}
        ext = {}
        for side, (hip_i, foot_i, toe_i, sd) in LEGS.items():
            g = geoms[side]
            hip = Pc + Rc @ self.off[hip_i]
            d = g['P4'] - hip
            R3_ref = Rc @ self.Rl[hip_i]
            R3 = swing(R3_ref @ self.off[foot_i], d) @ R3_ref
            driven[hip_i] = (R3, hip)
            driven[foot_i] = (g['R4'], g['P4'])
            driven[toe_i] = (g['R5'], g['S'])
            ext[side] = float(np.linalg.norm(d)) - self.link
        for side, (sh, el, sd) in ARMS.items():
            a, roll, b = arms[side]
            D9 = rx(a) @ rz(roll)
            driven[sh] = (Rc @ D9 @ self.Wr[sh], None)
            driven[el] = (Rc @ D9 @ rx(b) @ self.Wr[el], None)
        driven[HEAD] = (W1 @ rx(head[0]) @ ry(head[1]) @ rz(head[2]) @ self.Rl[HEAD], None)
        driven[KEY] = (W1 @ rx(key[0]) @ rz(key[1]) @ self.Rl[KEY], None)
        W, P = self.fk(driven)
        return W, P, ext

    def _foot_low(self, foot_i, toe_i, R4, P4, R5, P5):
        pts = [self.verts[foot_i] @ R4.T + P4, self.verts[toe_i] @ R5.T + P5]
        return float(max(p[:, 1].max() for p in pts))

    def encode(self, W, P, root_z):
        """Engine pose entries from world transforms (euler angles continuous per bone through self.hist)."""
        pose = [[4096] * 3 + [0, 0, 0, 0, 0, root_z]]
        for b in range(1, self.n):
            par = PARENTS[b]
            L = W[par].T @ W[b]
            t = W[par].T @ (P[b] - P[par])
            e = mmd.matrix_euler(L.tolist(), self.hist.get(b))
            self.hist[b] = e
            pose.append([4096] * 3 + [int(round(x)) for x in e] + [int(round(x)) for x in t])
        return pose


def chassis(rig, ch):
    Rc = ry(ch.get('yaw', 0)) @ rx(ch.get('pitch', 0)) @ rz(ch.get('roll', 0))
    return Rc, rig.Pr[CHASSIS] + np.array(ch['p'], float)


def swing(a, b):
    """Shortest rotation taking direction a to direction b."""
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    v = np.cross(a, b)
    c = float(a @ b)
    if c < -1 + 1e-9:
        raise ValueError('a half turn')
    k = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + k + k @ k / (1 + c)


# --------------------------------------------------------------------------------------------------------- the clips
EXT = (-16.0, 11.0)    # how far a foot block may slide into (out of) the hip piece's link, in units
GAITS = {
    # T: ticks of one cycle (each foot steps once, so two steps); v: root speed in units a tick; duty: stance share
    2: dict(name='walk', T=12, v=15, duty=0.55, sway=10.0, yaw=15.0, roll=3.2, pitch0=1.0, pitch=2.2, pitch_at=0.1,
            lift=24.0, heel=-5.0, push=10.0, phi_lift=8.0, toe=14.0, spread=7.0,
            arm=19.0, arm_out=3.0, elbow=12.0, arm_lag=0.05, rider_pitch=2.0, rider_roll=2.2, rider_lag=0.09,
            head=(3.0, 5.0, 1.6), key=(5.0, 3.5), flight=0.0, lag_sm=1),
    3: dict(name='condition walk', T=14, v=10, duty=0.56, sway=8.0, yaw=14.0, roll=2.5, pitch0=6.0, pitch=1.5, pitch_at=0.12,
            lift=9.0, heel=-4.0, push=7.0, phi_lift=3.0, toe=6.0, spread=9.0,
            arm=7.0, arm_out=5.0, elbow=5.0, arm_lag=0.08, rider_pitch=3.5, rider_roll=2.0, rider_lag=0.14,
            head=(9.0, 3.0, 2.5), key=(3.0, 2.0), flight=0.0, lag_sm=1),
    4: dict(name='run', T=8, v=38, duty=0.30, sway=6.0, yaw=15.0, roll=2.4, pitch0=17.0, pitch=3.0, pitch_at=0.0,
            lift=42.0, heel=-6.0, push=14.0, phi_lift=12.0, toe=22.0, spread=6.0,
            arm=36.0, arm_out=2.0, elbow=30.0, arm_lag=0.04, rider_pitch=4.0, rider_roll=1.6, rider_lag=0.07,
            head=(-4.0, 3.0, 1.2), key=(8.0, 5.0), flight=26.0, lag_sm=1),
}


def foot_state(cfg, ph, td):
    """(planted?, fraction through the stance or swing) of a foot that lands at phase `td`."""
    u = (ph - td) % 1.0
    d = cfg['duty']
    return (True, u / d) if u < d else (False, (u - d) / (1 - d))


def solve_dy(rig, ch, geoms, goal=0.0):
    """The chassis height (offset from rest, y down) at which the planted feet's mean link length is `goal` off the link,
    or None when no foot is planted."""
    planted = [s for s in 'RL' if geoms[s]['plant']]
    if not planted:
        return None
    lo, hi = -40.0, 80.0
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        c = dict(ch, p=(ch['p'][0], mid, ch['p'][2]))
        e = np.mean([np.linalg.norm(geoms[s]['P4'] - rig.hip(s, c)) - rig.link for s in planted])
        if e > goal:
            lo = mid        # the link is too long: the hips must come down towards the feet
        else:
            hi = mid
    return 0.5 * (lo + hi)


def gait(rig, cfg):
    T, v, d = cfg['T'], cfg['v'], cfg['duty']
    sweep = v * d * T
    rig.hist = {}
    z_mid = -22.0         # where the stance sweep is centred, in the root frame, against the toe's rest z
    foot_x = {s: sd * (abs(rig.Pr[LEGS[s][2]][0]) + cfg['spread']) for s, (_, _, _, sd) in LEGS.items()}
    td = {'R': 0.0, 'L': 0.5}
    chs, geoms = [], []
    for t in range(T):
        body = t / T
        sx = cfg['sway'] * wave(body, 0.0, 1, 0.18)
        yaw = cfg['yaw'] * (math.cos(TAU * body) + 0.12 * math.cos(TAU * 3 * (body - 0.02)))
        roll = cfg['roll'] * wave(body, 0.02, 1, 0.2)
        pitch = cfg['pitch0'] + cfg['pitch'] * math.cos(4 * math.pi * (body - cfg['pitch_at']))
        chs.append(dict(p=(sx, 0.0, 0.0), yaw=yaw, pitch=pitch, roll=roll))
        feet = {}
        for side in 'RL':
            planted, f = foot_state(cfg, body, td[side])
            if planted:
                z, y, phi, toe = z_mid - sweep / 2 + sweep * f, -10.0, cfg['heel'] + (cfg['push'] - cfg['heel']) * f, 0.0
            else:
                z = z_mid - sweep / 2 + sweep * (1 - (0.5 * f + 0.5 * smooth(f)))
                y = -10.0 - cfg['lift'] * math.sin(math.pi * f ** 0.85) ** 0.9
                phi = cfg['push'] + (cfg['heel'] - cfg['push']) * smooth(min(1.0, 2.2 * f)) + cfg['phi_lift'] * math.sin(math.pi * f)
                toe = -cfg['toe'] * math.sin(math.pi * min(1, f / 0.9)) ** 1.2
            feet[side] = rig.place_foot(side, dict(S=(foot_x[side], y, z), phi=phi, plant=planted, toe=toe))
        geoms.append(feet)
    dys = [solve_dy(rig, ch, g) for ch, g in zip(chs, geoms)]
    known = [i for i, x in enumerate(dys) if x is not None]
    if len(known) < T:                      # flight: an arc between the last planted tick and the next one
        for i in range(T):
            if dys[i] is None:
                a = max(k for k in [(i - j) % T for j in range(1, T)] if dys[k] is not None)
                b = min((k for k in [(i + j) % T for j in range(1, T)] if dys[k] is not None), key=lambda k: (k - i) % T)
                n = (b - a) % T
                u = ((i - a) % T) / n
                dys[i] = dys[a] + (dys[b] - dys[a]) * smooth(u) - cfg['flight'] * math.sin(math.pi * u)
    for _ in range(cfg['lag_sm']):          # a light cyclic smoothing so the vault has no corners
        dys = [0.25 * dys[i - 1] + 0.5 * dys[i] + 0.25 * dys[(i + 1) % T] for i in range(T)]
    frames, rep = [], dict(ext=[99, -99], phi=[99, -99], dy=[min(dys), max(dys)], ticks=[])
    for t in range(T + 1):
        i = t % T
        body = i / T
        ch = dict(chs[i], p=(chs[i]['p'][0], dys[i], 0.0))
        yaw = ch['yaw']
        arms = {}
        for side, sg in (('R', 1), ('L', -1)):
            ph_a = body - cfg['arm_lag'] * (1.0 if side == 'R' else 1.35)
            a = cfg['arm'] * (math.cos(TAU * ph_a) + 0.15 * math.cos(TAU * 2 * (ph_a - 0.08))) * sg
            fold = cfg['elbow'] * (0.6 + 0.4 * sg * math.cos(TAU * (ph_a - 0.12)))
            arms[side] = (a, cfg['arm_out'] * sg * (1 + 0.3 * wave(body, 0.1, 2)), -fold)
        high = cfg['duty'] / 2
        rider = (cfg['rider_pitch'] * (wave(body, high + cfg['rider_lag'], 2, 0.2) - 1) / 2, -cfg['rider_roll'] * (wave(body, 0.02 + cfg['rider_lag'], 1, 0.2) + 1) / 2, -0.25 * (yaw + cfg['yaw']))
        head = (cfg['head'][0] + 1.8 * wave(body, high + 0.14, 2), -0.6 * cfg['head'][1] * wave(body, 0.3, 1) - 0.4 * yaw, cfg['head'][2] * wave(body, 0.2))
        key = (cfg['key'][0] * wave(body, high + 0.18, 2, 0.3), cfg['key'][1] * wave(body, 0.15, 1))
        W, P, ext = rig.pose(ch, geoms[i], arms, rider, head, key)
        for s, e in ext.items():
            rep['ext'] = [min(rep['ext'][0], e), max(rep['ext'][1], e)]
            rep['phi'] = [min(rep['phi'][0], geoms[i][s]['phi']), max(rep['phi'][1], geoms[i][s]['phi'])]
        rep['ticks'].append((t, round(ext['R'], 1), round(ext['L'], 1), round(dys[i], 1)))
        frames.append(rig.encode(W, P, -round(v * t)))
    return frames, rep


IDLE_TICKS = 90


def idle(rig, ticks=IDLE_TICKS):
    """A calm, living stand: two slow breaths, a slow tick-tock roll of the chassis with the rider swinging on after it,
    the arms swinging softly late, a look to each side, the winding key ticking now and then. Both feet stay put."""
    rig.hist = {}
    feet = {s: rig.place_foot(s, dict(S=(rig.Pr[LEGS[s][2]][0], -2.0, rig.Pr[LEGS[s][2]][2]), phi=0.0, plant=True)) for s in 'RL'}
    frames, rep = [], dict(ext=[99, -99], ticks=[])
    for t in range(ticks + 1):
        ph = (t % ticks) / ticks
        i = t % ticks
        breath = wave(ph, 0.0, 2, 0.2)
        tock = wave(ph, 0.1, 1, 0.25)
        look = hold(i, [(0, 0), (14, 0), (28, 1), (42, 1), (54, -0.7), (64, -0.7), (78, 0), (90, 0)])
        nod = hold(i, [(0, 0), (30, 0), (35, 1), (41, 1), (48, 0), (90, 0)])
        tick = hold(i, [(0, 0), (22, 0), (26, 1), (46, 1), (50, 0), (70, 0), (73, -0.6), (84, -0.6), (88, 0), (90, 0)])
        ch = dict(p=(1.6 * tock, -1.5 + 1.1 * breath, 0.0), yaw=2.2 * look - 0.6 * tock, pitch=0.5 * breath, roll=1.1 * tock)
        arms = {}
        for side, sg in (('R', 1), ('L', -1)):
            lag = 0.07 if side == 'R' else 0.12
            arms[side] = (2.6 * wave(ph, 0.35 + lag, 2, 0.25) * sg + 3.4 * wave(ph, 0.2 + lag, 1, 0.2) * sg,
                          1.0 * sg * wave(ph, 0.1 + lag, 1), -2.0 - 1.6 * wave(ph, 0.4 + lag, 2, 0.2))
        rider = (0.6 * (wave(ph, 0.1, 2, 0.2) - 1), -0.45 * (wave(ph, 0.16, 1, 0.25) + 1), 0.5 * (look - 1))
        head = (1.6 * wave(ph, 0.2, 2) + 3.0 * nod, 12.0 * look, 2.0 * look)
        key = (1.5 * wave(ph, 0.3, 2), 10.0 * tick)
        W, P, ext = rig.pose(ch, feet, arms, rider, head, key)
        for e in ext.values():
            rep['ext'] = [min(rep['ext'][0], e), max(rep['ext'][1], e)]
        frames.append(rig.encode(W, P, 0))
    return frames, rep


FOOT_SOUND = {2: 11, 3: 21, 4: 21}      # the sound note of a footfall, as the previous clips used


def build(data):
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError("Clockmon's gaits require the reviewed source")
    skeleton = [tuple(b) for b in json.loads((ROOT / 'content/species/290-clockmon.json').read_text())['model']['skeleton']]
    n = len(skeleton)
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = n
    old = mmd.MMD.parse(data, n)
    old.type = SPECIES
    rig = Rig(old, skeleton)
    new = copy.deepcopy(old)
    out, reach = {0: idle(rig)}, {}
    for slot, cfg in GAITS.items():
        out[slot] = gait(rig, cfg)
    changed = set()
    for slot, (frames, rep) in out.items():
        lo, hi = rep['ext']
        reach[slot] = [round(lo, 1), round(hi, 1)]
        if slot != 0 and (lo < EXT[0] - 1e-6 or hi > EXT[1] + 1e-6):
            raise ValueError(f'slot {slot}: the legs telescope {lo:.1f}..{hi:.1f}, outside {EXT}')
        frames = [[[round(x) for x in b] for b in pose] for pose in frames]
        events = [e for e in mmd.anim_events(old.anims.anims[old.anims.table[slot]], n, slot, ('tex',))]
        if slot in FOOT_SOUND:
            T = len(frames) - 1
            events += [(k, 'sound', dict(bank=1, note=FOOT_SOUND[slot])) for k in (0, T // 2)]
        animation = mmd.encode_anim(frames, n, loop_sample=0, events=events, tol=1)
        index = old.anims.table[slot]
        new.anims.anims[index] = animation
        changed |= {s for s, i in enumerate(old.anims.table) if i == index}
    result = new.build()
    actual = mmd.MMD.parse(result, n)
    actual.type = SPECIES
    assert old.tmd.build() == actual.tmd.build()
    assert changed_programs(old, actual) == sorted(changed), (changed_programs(old, actual), sorted(changed))
    assert sorted(changed) == list(SLOTS), sorted(changed)
    storage = motionstorage.require(result, n)
    return result, dict(species=SPECIES, changed_slots=sorted(changed), storage=storage, telescoping=reach,
                        output_sha256=hashlib.sha256(result).hexdigest())


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out-dir', type=Path, required=True)
    a = p.parse_args()
    data, proof = build(a.source.read_bytes())
    a.out_dir.mkdir(parents=True, exist_ok=True)
    (a.out_dir / '290-Clockmon.MMD').write_bytes(data)
    print(json.dumps(proof, indent=2, default=str))


if __name__ == '__main__':
    main()
