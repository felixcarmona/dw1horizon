"""MarineAngemon's (species 248) field clips: four different loops of a fairy that beats its wings, swings its arms, flicks its
long ears and blinks.

Offline authoring script (the model it makes is stored with `tools/models/edit.py put 248 MMD TIM`, like RedOtamamon's).
The previous model held one still pose in the idle, the walk, the condition walk and the run (every bone constant, only the
root moved); the two ear feelers, the two wings, the two arms and the tail ribbon never moved. Every clip is authored here
from the rest pose by turning bones about world axes (the rig's local axes are tilted, so a delta is conjugated into each
bone's parent frame), each part on its own phase of the clip, with whole cycles per loop:

  idle   48 ticks, no travel: a calm hover. The wings beat four times (12 ticks), the body rises and sinks twice,
         the ears sway and trail, the arms drift, the tail ribbon swishes, the head looks around once and nods;
         the eyes blink (a lone blink and a quick double blink)
  walk   24 ticks, 17.5 units a tick: a forward float. Three wing beats, two bobs, the arms swing against each other
         once (a full swing per loop), a few degrees of forward lean, the ears stream back and lag with overshoot,
         the tail trails; one blink
  tired  28 ticks, 13 units a tick: a heavy float. The wings hang low and beat slowly (two beats), the head
         and ears droop, the arms hang and sway, the tail drags; two slow blinks with heavy lids
  run    18 ticks, 38 units a tick: a fast dash. The body leans well forward, three quick wing beats, the arms
         pump (three swings), the ears and the tail stream behind, a banking roll; the eyes squint

Each part is delayed behind the one it hangs from and overshoots a little: the forearm behind the upper arm, the outer wing
segment behind the inner one, every ear and tail segment behind the one before. The right and the left side differ a little
in phase and amplitude so that nothing mirrors exactly.

The eyes blink through texture moves (marine_angemon_face.py); every clip sets its first face at tick 0.

    python tools/models/field_animations/marine_angemon.py --source SRC.MMD --tex SRC.TIM --out-dir DIR
where SRC is the previously stored model and texture (sha256 below).
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
from tools.models.field_animations import marine_angemon_face as face  # noqa: E402
from motiondiscidentity import changed_programs  # noqa: E402

SPECIES = 248
SOURCE = '9b329de6a03af00aed9845dc1fd5e2600fcab852e5e05eebbe0a844e000281fd'      # the previous model
TEX_SOURCE = '459d67339592cf6042db4196aac17fdcd374f6809ff6738dba93cff34e886fa2'  # its texture
HIPS, TORSO, HEAD, COLLAR = 1, 2, 3, 25
ARM = {'R': (4, 5, 6), 'L': (7, 8, 9)}
EAR = {'R': (10, 11, 12), 'L': (13, 14, 15)}
WING = {'R': (16, 17), 'L': (18, 19)}
TAIL = (20, 21, 22, 23, 24)
SIDE = {'R': 1, 'L': -1}
SLOTS = (0, 2, 3, 4)
TWO_PI = 2 * math.pi


def wave(x):
    """sin of a phase in cycles."""
    return math.sin(TWO_PI * x)


def smooth(x):
    x = max(0., min(1., x))
    return x * x * (3 - 2 * x)


def mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def tr(a):
    return [[a[j][i] for j in range(3)] for i in range(3)]


def turn(rx=0., ry=0., rz=0.):
    """Rotation matrix of degrees about world x, y, z (Rx . Ry . Rz, the engine's order)."""
    k = 4096 / 360
    return mmd.rot_matrix(rx * k, ry * k, rz * k)


class Rig:
    def __init__(self, model, skeleton):
        self.n = len(skeleton)
        self.parent = [s[1] for s in skeleton]
        self.model = model
        pose = animsheet.slot_frames(model, self.n, 0)[0][0]
        self.rest = [list(b) for b in pose]
        self.rest[0] = [4096] * 3 + [0] * 6
        self.local = [mmd.rot_matrix(*v[3:6]) for v in self.rest]
        self.world = [None] * self.n
        for b in range(self.n):
            p = self.parent[b]
            self.world[b] = self.local[b] if p < 0 else mul(self.world[p], self.local[b])
        self.prev = {}

    def pose(self, deltas, move=(0., 0., 0.)):
        """deltas: {bone: (rx, ry, rz) degrees about the world axes of the parent's deformed frame}; move: hips offset."""
        out = [list(v) for v in self.rest]
        for b in range(1, self.n):
            d = deltas.get(b)
            if not d or not any(d):
                continue
            wp = self.world[self.parent[b]]
            local = mul(mul(tr(wp), mul(turn(*d), wp)), self.local[b])
            e = mmd.matrix_euler(local, self.prev.get(b, self.rest[b][3:6]))
            self.prev[b] = e
            out[b][3:6] = list(e)
        for i in range(3):
            out[HIPS][6 + i] = self.rest[HIPS][6 + i] + move[i]
        return out

    def lowest_highest(self, pose):
        mats = mmd.bone_matrices(self.model, pose)
        low, high = -1e9, 1e9
        skeleton = mmd.exe().skeleton[SPECIES]
        for b, (obj, _) in enumerate(skeleton):
            if obj < 0:
                continue
            M = mats[b]
            for x, y, z, _ in self.model.tmd.obj_verts(obj):
                v = M[1][0] * x + M[1][1] * y + M[1][2] * z + M[1][3]
                low, high = max(low, v), min(high, v)
        return low, high


def beat(x, skew=0.2):
    """A wing beat from a phase in cycles: down-stroke fast, up-stroke slower (+1 = the highest, -1 = the lowest point)."""
    t = TWO_PI * x
    return math.sin(t) + skew * math.sin(2 * t + 1.1)


CLIPS = {
    0: dict(name='idle', floor=-62, ticks=48, speed=0.0,
            beats=4, wing_env=0.25, wing_rest=-6.0, wing_amp=17.0, wing_out=12.0, wing_lag=0.11, wing_sweep=6.0, wing_twist=6.0,
            bob=2, bob_amp=5.0, bob_phase=0.2, drop=0.0,
            pitch=0.0, pitch_amp=1.6, roll_amp=2.0, roll_cycles=1,
            head_yaw=9.0, head_pitch=3.0, head_roll=2.5, head_look=1,
            ear_cycles=2, ear_out=10.0, ear_fore=7.0, ear_rest=0.0, ear_back=0.0, ear_lag=0.09,
            arm_cycles=1, arm_swing=14.0, arm_lift=9.0, arm_rest=(0.0, 0.0), arm_lag=0.10,
            tail_cycles=1, tail_yaw=9.0, tail_pitch=7.0, tail_rest=0.0, tail_lag=0.07,
            sound=()),
    2: dict(name='walk', floor=-62, ticks=24, speed=18.0,
            beats=3, wing_env=0.12, wing_rest=-6.0, wing_amp=25.0, wing_out=20.0, wing_lag=0.12, wing_sweep=9.0, wing_twist=8.0,
            bob=2, bob_amp=6.5, bob_phase=0.15, drop=0.0,
            pitch=7.0, pitch_amp=2.5, roll_amp=3.5, roll_cycles=1,
            head_yaw=5.0, head_pitch=3.5, head_roll=2.5, head_look=1,
            ear_cycles=2, ear_out=9.0, ear_fore=8.0, ear_rest=0.0, ear_back=12.0, ear_lag=0.10,
            arm_cycles=1, arm_swing=26.0, arm_lift=10.0, arm_rest=(0.0, 4.0), arm_lag=0.11,
            tail_cycles=1, tail_yaw=12.0, tail_pitch=8.0, tail_rest=-3.0, tail_lag=0.08,
            sound=(5, 17)),
    3: dict(name='condition walk', floor=-50, ticks=28, speed=13.0,
            beats=2, wing_env=0.15, wing_rest=22.0, wing_amp=20.0, wing_out=14.0, wing_lag=0.15, wing_sweep=5.0, wing_twist=5.0,
            bob=1, bob_amp=6.0, bob_phase=0.1, drop=14.0,
            pitch=9.0, pitch_amp=2.0, roll_amp=4.0, roll_cycles=1, head_comp=-0.25,
            head_yaw=3.0, head_pitch=3.0, head_roll=4.0, head_look=1,
            ear_cycles=1, ear_out=7.0, ear_fore=6.0, ear_rest=38.0, ear_back=0.0, ear_lag=0.12,
            arm_cycles=1, arm_swing=12.0, arm_lift=6.0, arm_rest=(0.0, 28.0), arm_lag=0.13,
            tail_cycles=1, tail_yaw=7.0, tail_pitch=5.0, tail_rest=-22.0, tail_lag=0.09,
            sound=(6, 20)),
    4: dict(name='run', floor=-62, ticks=18, speed=38.0,
            beats=3, wing_env=0.1, wing_rest=-10.0, wing_amp=21.0, wing_out=16.0, wing_lag=0.10, wing_sweep=8.0, wing_twist=9.0,
            bob=3, bob_amp=7.5, bob_phase=0.18, drop=-4.0,
            pitch=21.0, pitch_amp=3.0, roll_amp=6.0, roll_cycles=1,
            head_yaw=3.0, head_pitch=3.0, head_roll=3.0, head_look=1,
            ear_cycles=3, ear_out=6.0, ear_fore=5.0, ear_rest=0.0, ear_back=32.0, ear_lag=0.08,
            arm_cycles=3, arm_swing=21.0, arm_lift=8.0, arm_rest=(-6.0, 10.0), arm_lag=0.10,
            tail_cycles=3, tail_yaw=9.0, tail_pitch=8.0, tail_rest=18.0, tail_lag=0.06,
            sound=(4, 13)),
}


def clip(rig, cfg):
    """One loop: ticks + 1 poses, the last one the first with the root a loop's travel on."""
    T, v = cfg['ticks'], cfg['speed']
    frames = []
    rig.prev = {}
    for t in range(T):
        ph = t / T
        d = {}
        # --- body: hover bob, lean, roll, head
        bob = cfg['bob_amp'] * wave(cfg['bob'] * ph + cfg['bob_phase'])
        pitch = cfg['pitch'] + cfg['pitch_amp'] * wave(cfg['bob'] * ph + 0.35)
        roll = cfg['roll_amp'] * wave(cfg['roll_cycles'] * ph + 0.05)
        d[HIPS] = (pitch * 0.6, 3.0 * wave(cfg['roll_cycles'] * ph + 0.3), roll)
        d[TORSO] = (pitch * 0.4 + 1.2 * wave(cfg['bob'] * ph + 0.55), 0.0, -0.5 * roll)
        look = wave(cfg['head_look'] * ph)
        d[HEAD] = (-pitch * cfg.get('head_comp', 0.55) + cfg['head_pitch'] * wave(cfg['bob'] * ph + 0.45),
                   cfg['head_yaw'] * look, cfg['head_roll'] * wave(cfg['head_look'] * ph + 0.22) - 0.4 * roll)
        d[COLLAR] = (4.0 * wave(cfg['bob'] * ph + 0.62), 0.0, 3.0 * wave(cfg['roll_cycles'] * ph + 0.4))
        # --- wings: flap about the front-to-back axis, the outer segment trailing the inner, a sweep and a twist
        for name, (inner, outer) in WING.items():
            s = SIDE[name]
            asym = 0.0 if name == 'R' else 0.025
            amp = 1.0 if name == 'R' else 0.93
            x = cfg['beats'] * ph - asym
            env = 1.0 + cfg.get('wing_env', 0.0) * wave(ph + 0.1)      # a slow swell: no two beats are the same
            flap = cfg['wing_rest'] + cfg['wing_amp'] * amp * env * beat(x)
            flap_out = cfg['wing_out'] * amp * env * beat(x - cfg['wing_lag'])
            sweep = cfg['wing_sweep'] * wave(x + 0.18)
            twist = cfg['wing_twist'] * wave(x - cfg['wing_lag'] - 0.05)
            d[inner] = (0.0, s * sweep, s * flap)
            d[outer] = (s * twist, s * 0.5 * sweep, s * flap_out)
        # --- arms: swing forward and back against each other, lifting a little, the forearm and hand trailing
        for name, chain in ARM.items():
            s = SIDE[name]
            ph_a = cfg['arm_cycles'] * ph + (0.0 if name == 'R' else 0.5) + (0.02 if name == 'L' else 0.0)
            amp = 1.0 if name == 'R' else 0.92
            for i, b in enumerate(chain):
                lag = cfg['arm_lag'] * i
                gain = (1.0, 1.25, 1.35)[i]
                swing = cfg['arm_swing'] * amp * gain * wave(ph_a - lag)
                lift = cfg['arm_lift'] * amp * gain * wave(ph_a - lag - 0.2)
                rest_y, rest_z = cfg['arm_rest'] if i == 0 else (0.0, 0.0)
                d[b] = (0.0, s * (swing + rest_y), s * (lift + rest_z))
        # --- ears: sway outward and fore-and-aft, each segment behind the one before and larger
        for name, chain in EAR.items():
            s = SIDE[name]
            ph_e = cfg['ear_cycles'] * ph + (0.0 if name == 'R' else 0.13)
            amp = 1.0 if name == 'R' else 0.9
            for i, b in enumerate(chain):
                lag = cfg['ear_lag'] * (i + 1)
                gain = (1.0, 1.4, 1.7)[i]
                out = cfg['ear_out'] * amp * gain * wave(ph_e - lag)
                fore = cfg['ear_fore'] * amp * gain * wave(ph_e - lag - 0.27)
                rest_out = cfg['ear_rest'] * (1.0, 0.7, 0.5)[i]
                back = cfg['ear_back'] * (0.7, 0.5, 0.3)[i] * (1 + 0.15 * wave(ph_e - lag))
                d[b] = (fore - back, 0.0, s * (out + rest_out))
        # --- tail ribbon: a travelling wave, yaw and pitch
        for i, b in enumerate(TAIL):
            lag = cfg['tail_lag'] * (i + 1)
            gain = (0.6, 0.9, 1.2, 1.5, 1.8)[i]
            yaw = cfg['tail_yaw'] * gain * wave(cfg['tail_cycles'] * ph - lag)
            pit = cfg['tail_pitch'] * gain * wave(cfg['tail_cycles'] * ph - lag - 0.25) + cfg['tail_rest'] * (0.5 if i else 0.3)
            d[b] = (pit, yaw, 0.0)
        move = (3.0 * wave(cfg['roll_cycles'] * ph + 0.3), cfg['drop'] - bob, 0.0)
        pose = rig.pose(d, move)
        pose[0][8] = -v * t
        frames.append(pose)
    closing = [list(b) for b in frames[0]]
    closing[0][8] = -v * T
    frames.append(closing)
    # the whole clip rises or sinks by one constant so that its lowest point (the tail's tip) hovers at cfg['floor']
    low = max(rig.lowest_highest(f)[0] for f in frames)
    lift = round(cfg['floor'] - low)
    for f in frames:
        f[HIPS][7] += lift
    return frames


# The eye's plan per clip: (tick, state) changes inside the clip, ending in its first face, so a loop closes and a clip
# left mid-blink is repaired by the next clip's tick 0.
FACE = {0: face.blink(10) + face.blink(33) + face.blink(38),
        2: face.blink(7),
        3: face.blink(3, slow=True) + face.blink(18, slow=True),
        4: [(1, face.HALF), (14, face.OPEN)]}


def _tolerance():
    """Encoding tolerance per bone in 1/4096 turn: wide where the part is a thin or far appendage (a unit of angle moves
    the wing tip 0.3 of a unit, the model is about 6 units to the pixel), tight on the body, head and the arms' roots."""
    tol = {None: 10}
    tol.update({b: 7 for b in (HIPS, TORSO)})
    tol[HEAD] = 8
    tol.update({b: 14 for b in WING['R'] + WING['L'][:1]})
    tol.update({b: 18 for b in (17, 19)})
    tol.update({b: 11 for b in ARM['R'] + ARM['L']})
    tol.update({b: 16 for b in EAR['R'] + EAR['L']})
    tol.update({b: 19 for b in TAIL})
    tol[COLLAR] = 16
    return tol


ENCODE_TOL = _tolerance()


def sounds(slot):
    return [(t, 'sound', dict(bank=1, note=18)) for t in CLIPS[slot]['sound']]


def build(data, tex):
    if hashlib.sha256(tex).hexdigest() != TEX_SOURCE:
        raise ValueError('MarineAngemon\'s eyes require the reviewed texture')
    if hashlib.sha256(data).hexdigest() != SOURCE:
        raise ValueError('MarineAngemon\'s clips require the reviewed source')
    skeleton = [tuple(b) for b in json.loads((ROOT / 'content/species/248-marineangemon.json').read_text())['model']['skeleton']]
    n = len(skeleton)
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = n
    old = mmd.MMD.parse(data, n)
    old.type = SPECIES
    rig = Rig(old, skeleton)
    new = copy.deepcopy(old)
    out = {slot: clip(rig, cfg) for slot, cfg in CLIPS.items()}
    changed = set()
    for slot, frames in out.items():
        frames = [[[round(x) for x in b] for b in pose] for pose in frames]
        events = face.events(FACE[slot], len(frames) - 1) + sounds(slot)
        animation = mmd.encode_anim(frames, n, loop_sample=0, events=events, tol=ENCODE_TOL)
        index = old.anims.table[slot]
        new.anims.anims[index] = animation
        changed |= {s for s, i in enumerate(old.anims.table) if i == index}
    result = new.build()
    actual = mmd.MMD.parse(result, n)
    actual.type = SPECIES
    assert old.tmd.build() == actual.tmd.build()
    assert changed_programs(old, actual) == sorted(changed), (changed_programs(old, actual), sorted(changed))
    storage = motionstorage.require(result, n)
    tim = mmd.Tim4(tex)
    face.stamp(tim)
    new_tex = tim.to_bytes()
    assert len(new_tex) == len(tex)
    return result, new_tex, dict(species=SPECIES, changed_slots=sorted(changed), storage=storage,
                                 output_sha256=hashlib.sha256(result).hexdigest())


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--tex', type=Path, required=True)
    p.add_argument('--out-dir', type=Path, required=True)
    a = p.parse_args()
    data, tex, proof = build(a.source.read_bytes(), a.tex.read_bytes())
    a.out_dir.mkdir(parents=True, exist_ok=True)
    (a.out_dir / '248-MarineAngemon.MMD').write_bytes(data)
    (a.out_dir / '248-MarineAngemon.TIM').write_bytes(tex)
    print(json.dumps(proof, indent=2, default=str))


if __name__ == '__main__':
    main()
