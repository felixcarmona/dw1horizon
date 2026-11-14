"""Veemon's idle, walk, tired walk and run (species 180, slots 0, 2, 3 and 4) as one
cheerful body on planted feet.

Veemon is a small, upright dragon boy with a tail, two ears on its head and a fist at the end of each arm (forward is -z).
Its rig has 20 bones: the pelvis (1, the belly, the parent of the legs and the tail) with the chest (2) on it; the head (3)
with its jaw (4); the two arms hung from the chest (5-7 right, 8-10 left: shoulder, forearm, fist); the tail (11-13); and
the two legs (14-16 right, 17-19 left: thigh, shin, the flat clawed foot).

What was wrong. The clips were written from a table of sines: a stride with one hip and knee solution, two arms that
swung as one pendulum each and the head, the chest and the tail that hardly moved. They walked like a machine (the
imported idle held the pose of one frame all along, the stance slip peaked at 144 % in the tired walk and 59 % in the run).

What the clips are now. The legs and the body come from `quadruped.py` (every sole stands still in its stance, two-bone
solves on thigh and shin, the body sinks to a leg that cannot reach) and `body` writes everything above them from the same
phase, the way a starter moves: the weight goes over the planted leg and the pelvis rolls and yaws against the chest, the chest
turns against it a little later, the head keeps its gaze and follows late and tilts about, the arms swing loosely against
the legs on their side with the elbow bent, the forearm and the fist a beat late, the jaw opens a little with the effort,
and the three tail segments follow one another (a wave runs down the tail) while a bounce passes up it at every step. Every
clip is two cycles long: cycle B differs from cycle A (one leg lifts higher, the body sinks a little more, one arm swings
wider), the clip eases from one to the other and back so that no two steps are alike and the loop still closes; the head,
arms, jaw and tail then follow through a loose second-order spring each.

Personality. The walk bounces (a springy second dip every step, the body rising on the push-off) and the arms swing wide;
cycle B carries a happy skip (the body rises, the arms go up, the head tips back, the tail whips). The tired walk droops:
head low, chest forward, the arms hang and drag late, the tail down, a yawn once a step pair. The run is eager: a forward
lean, the arms pumping in big arcs with the forearms driving, the head up, the tail streaming out. The idle (96 ticks, the
feet planted) breathes, shifts its weight from foot to foot, looks round with the head tilted, wags the tail in bursts,
bounces on the spot with its fists up, pumps a fist and stretches both arms, each at its own moment in the loop.

The battle slots 33, 35 and 36 keep the source game's own clips (35 and 36 rebuilt on our rig: content/models/imports/battle-rebuilds.json). The feet roll: the toes lift at touchdown, the heel
rises at the push-off with the toes still planted, and the toes curl in the swing (the run's roll is the curl only). Veemon blinks:
`veemon_face.py` stamps the eye frames into spare texels and every clip plays irregular texture-move blinks (a double one in the
idle, slow heavy lids in the tired walk). Nothing else changes: the mesh and every other program are exact; the texture only gains
the eye frames (`texture`).

`build` is the overlay's generator (`veemon-field` in content/models/imports/species.py). Offline: `python3 -m
tools.models.field_animations.veemon_gait --source EDIT.MMD --out AFTER.MMD` with EDIT.MMD the imported base model.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import mmd  # noqa: E402
from tools.models.field_animations import quadruped  # noqa: E402
from tools.models.field_animations import veemon_face as face  # noqa: E402
from tools.models.field_animations.quadruped import mul, tr, rot, set_rot  # noqa: E402

SPECIES = 180
SOURCE_TIM = '80fef9316ae20ba45cf13a3cb1e5652cd60dd7706bc54c89993332a5932b5469'     # the texture before the eye frames
SOURCE = 'eb42132f083e9cce2cd487f14f74e013782a364d25e08217d4482e6ee22bafb6'     # the imported base model
TAU = 2 * math.pi
DEG = 4096 / 360
PELVIS, CHEST, HEAD, JAW = 1, 2, 3, 4

TAIL = (11, 12, 13)
TAIL_REST = (-4, 18, 26)      # degrees of pitch per segment: the tail held up behind, as the import's own idle holds it
ARMS = {'R': (5, 6, 7, 1), 'L': (8, 9, 10, -1)}          # shoulder, forearm, fist, the side's sign in x
LEGS = {'RH': (14, 15, 16, 1, False), 'LH': (17, 18, 19, -1, False)}
PARENTS = [-1, 0, 1, 2, 3, 2, 5, 6, 2, 8, 9, 1, 11, 12, 1, 14, 15, 1, 17, 18]
# the eye (tick, state) plans of each clip, irregular on purpose (a double blink in the idle); the tired walk's lids are heavy
FACE = {
    0: face.blink(9, closed=2) + face.blink(41, closed=1) + face.blink(47, closed=2) + face.blink(78, closed=3),
    2: face.blink(3, closed=2) + face.blink(15, closed=1),
    3: face.blink(4, closed=3, heavy=True) + face.blink(22, closed=4, heavy=True),
    4: face.blink(5, closed=2),
}


def face_events(slot, total):
    return face.events(FACE[slot], total)


def texture(tim):
    """The texture before this change (SOURCE_TIM) -> the same with the eye frames in their spare texels."""
    if hashlib.sha256(tim).hexdigest() != SOURCE_TIM:
        raise ValueError('Veemon needs the texture it had before this change')
    t = mmd.Tim4(tim)
    face.stamp(t)
    out = t.to_bytes()
    assert len(out) == len(tim)
    return out


ALIASES = {}      # the battle walk and run (35, 36) are the source game's own clips, rebuilt (content/models/imports/battle-rebuilds.json)


def harm(phase, *terms):
    """A sum of cosines: terms are (amplitude, rate, delay in cycles)."""
    return sum(a * math.cos(TAU * rate * (phase - delay)) for a, rate, delay in terms)


def bell(phase, at, width):
    """A smooth cyclic bump: 1 at `at`, 0 further than `width` cycles away."""
    d = (phase - at + 0.5) % 1.0 - 0.5
    return 0.5 + 0.5 * math.cos(math.pi * d / width) if abs(d) < width else 0.0


def rest_fix(rest):
    """The bind pose: every bone turned by nothing. The imported idle's first tick caught the body mid-turn (yawed, one arm
    and one leg ahead of the other), which no gait should start from."""
    for b in range(1, len(rest)):
        rest[b][3:6] = [0, 0, 0]
    for side, other in ((5, 8), (6, 9), (7, 10), (14, 17), (15, 18), (16, 19)):     # the two sides mirror exactly
        rest[other][6:9] = [-rest[side][6], rest[side][7], rest[side][8]]


class Pose:
    """World-frame turns written as local rotations: a bone's turn is a delta on top of its parent's."""

    def __init__(self, rig, pose, hist):
        self.rig, self.pose, self.hist = rig, pose, hist
        self.W = {0: [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}

    def put(self, bone, delta, parent=None):
        rig = self.rig
        parent = rig.sk[bone][1] if parent is None else parent
        self.W[bone] = mul(delta, rig.R(rig.still, bone))
        set_rot(self.pose, bone, mul(tr(self.W[parent]), self.W[bone]), self.hist)


def idle_body(rig, c, ph, pose, hist):
    """A small hero standing about on planted feet: it breathes, shifts its weight, looks round with its head tilted, wags
    its tail in bursts, bounces on the spot with its fists up, pumps one fist and stretches. Every part has its own rate
    and moment in the loop, so no two of them repeat together."""
    rest = rig.rest
    P = Pose(rig, pose, hist)
    breath = math.sin(TAU * 4 * ph)
    shift = harm(ph, (1, 1, 0.1)) + 0.4 * harm(ph, (1, 2, 0.3))
    # two quick happy dips and rises on the spot (knees bend and spring back)
    spring = bell(ph, 0.8, 0.09) * (0.5 - 0.5 * math.cos(TAU * 5 * (ph - 0.71)))
    stretch = bell(ph, 0.56, 0.1)
    pump = bell(ph, 0.33, 0.07)
    pumping = pump * (0.5 - 0.5 * math.cos(TAU * 4 * (ph - 0.28)))
    pose[PELVIS][7] = rest[PELVIS][7] - 17.0 - 1.4 * breath + 5.0 * spring - 2.5 * stretch + 1.6 * pump
    pose[PELVIS][6] = rest[PELVIS][6] + 3.5 * shift
    roll = 1.6 * shift + 1.5 * bell(ph, 0.2, 0.1) - 1.2 * bell(ph, 0.46, 0.1)
    pitch = 0.9 * breath - 2.0 * spring + 2.5 * bell(ph, 0.82, 0.05) - 1.5 * stretch
    yaw = 2.2 * harm(ph, (1, 1, 0.55))
    P.put(PELVIS, rot([0.4 * pitch, 0.5 * yaw, 0.5 * roll]))
    chest = rot([pitch + 1.3 * breath - 5.0 * stretch + 3.0 * pump, yaw - 3.0 * bell(ph, 0.14, 0.14) + 2.0 * bell(ph, 0.53, 0.14), roll])
    P.put(CHEST, chest)
    look = 24 * bell(ph, 0.14, 0.15) - 20 * bell(ph, 0.52, 0.13) + 5 * math.sin(TAU * 2 * ph)
    tilt = 10 * bell(ph, 0.14, 0.12) - 8 * bell(ph, 0.52, 0.1) + 4 * bell(ph, 0.43, 0.03) - 4 * bell(ph, 0.465, 0.03) + 2 * shift
    nod = 5 * bell(ph, 0.81, 0.04) + 5 * bell(ph, 0.9, 0.04) - 3.5 * bell(ph, 0.14, 0.15) - 16 * stretch + 1.2 * breath
    P.put(HEAD, mul(chest, rot([-pitch * 0.8 + nod, look - 0.7 * yaw, tilt - 0.7 * roll])))
    pose[JAW][3] = rest[JAW][3] + round((5 * bell(ph, 0.84, 0.08) + 2 * pump + 6 * stretch) * DEG)
    for side, (sh, el, hand, sd) in ARMS.items():
        mine = pumping if side == 'R' else 0.0
        mine_up = pump if side == 'R' else 0.0
        swing = 3.0 * breath * sd + 2.5 * shift * sd - 38 * mine_up - 16 * bell(ph, 0.8, 0.09) - (60 * stretch)
        out = sd * (-24 - 8 * bell(ph, 0.8, 0.09) - 30 * stretch + 4 * math.sin(TAU * 4 * ph + (0 if sd > 0 else 1.7)))
        P.put(sh, mul(chest, rot([swing + 2, 0, out - sd * 4])))
        pose[el][3] = rest[el][3] + round((-30 - 55 * mine_up - 18 * mine - 10 * bell(ph, 0.8, 0.09) + 14 * stretch + 3 * math.sin(TAU * 4 * ph + 1.0 + (0 if sd > 0 else 1.2))) * DEG)
        pose[hand][3] = rest[hand][3] + round((-16 + 10 * mine * math.sin(TAU * 7 * ph) - 20 * mine_up + 3 * math.sin(TAU * 4 * ph + 2)) * DEG)
    burst = bell(ph, 0.72, 0.16) + 0.6 * bell(ph, 0.9, 0.08)
    for k, b in enumerate(TAIL):
        d = 0.045 * k
        pose[b][3] = rest[b][3] + round((TAIL_REST[k] + 3 * math.sin(TAU * (4 * ph - d * 2)) * (k + 1) / 2 - 3 * pump - 5 * burst * math.sin(TAU * (6 * ph - d))) * DEG)
        pose[b][4] = rest[b][4] + round((4 * math.sin(TAU * (2 * ph - d)) + 12 * (1 + 0.5 * k) * burst * math.sin(TAU * (8 * ph - 2 * d)) + 3 * shift) * DEG)


def body(rig, cfg, phase, pose, hist):
    """Height, sway and the turns of pelvis and chest, the head and jaw, the arms and the tail from one phase."""
    c, rest = cfg, rig.rest
    if c['kind'] == 'idle':
        return idle_body(rig, c, phase, pose, hist)
    P = Pose(rig, pose, hist)
    left = c['touchdown']['LH']                    # the left foot lands at this phase; the right one half a cycle later
    ph = phase - left
    bob = harm(ph, (c['bob'], 2, c['high']), (c['bob2'], 4, c['high'] + 0.03), (c['bob_side'], 1, c['high'] + 0.2))
    hop = c['hop'] * bell(ph, c['hop_at'], c['hop_w'])               # a happy skip (one cycle of the two)
    yawn = c['yawn'] * bell(ph, c['yawn_at'], 0.22)                  # the tired walk's yawn
    pose[PELVIS][7] = rest[PELVIS][7] - c['height'] - bob - 6 * hop
    over = harm(ph, (1, 1, 0.79 + c['roll_at']))                     # the weight over the planted leg: the right at 0.79, the left at 0.29
    pose[PELVIS][6] = rest[PELVIS][6] + c['shift'] * over + c['shift2'] * harm(ph, (1, 3, 0.79 + c['roll_at'] + 0.07))
    hy = harm(ph, (c['hip_yaw'], 1, 0.5 + c['yaw_at']), (c['hip_yaw2'], 3, 0.5 + c['yaw_at'] + 0.05))    # the leading hip is forward
    hr = -c['hip_roll'] * over + c['hip_roll2'] * harm(ph, (1, 2, c['pitch_at']))
    hp = c['hip_tilt'] + harm(ph, (c['hip_pitch'], 2, c['pitch_at'] + 0.05))
    P.put(PELVIS, rot([hp, hy, hr]))
    lag = c['lag']
    breath = c['breath'] * math.sin(TAU * (ph - 0.1))
    pitch = c['lean'] + harm(ph - lag, (c['pitch'], 2, c['pitch_at']), (c['pitch1'], 1, c['pitch_at'] + 0.12)) + breath - 2 * hop
    yaw = -c['counter'] * hy + harm(ph - lag, (c['yaw'], 1, 0.5 + c['yaw_at'] + 0.1))
    roll = c['roll'] * harm(ph - lag, (1, 1, 0.79 + c['roll_at'])) + c['roll2'] * harm(ph - lag, (1, 3, 0.79 + c['roll_at'] + 0.06))
    chest = rot([pitch - 0.5 * hp, yaw, roll - 0.5 * hr])
    P.put(CHEST, chest)
    # the head keeps most of its gaze against the body and follows what the body does late
    hl = c['head_lag']
    top = pitch - c['lean']
    nod = harm(ph - hl, (c['nod'], 2, c['pitch_at'] + 0.1), (c['nod1'], 1, 0.3))
    head_pitch = c['head'] - c['steady'] * top + nod + 0.4 * breath - 12 * hop + 9 * yawn
    head_yaw = -c['steady'] * yaw * 0.8 + c['look'] * harm(ph - hl, (1, 1, 0.5 + c['yaw_at'] + 0.2))
    head_roll = -c['steady'] * roll + c['head_roll'] * harm(ph - hl, (1, 1, 0.79 + c['roll_at'] + 0.1))
    P.put(HEAD, mul(chest, rot([head_pitch, head_yaw, head_roll])))
    pose[JAW][3] = rest[JAW][3] + round((c['jaw'] * (0.5 + 0.5 * math.sin(TAU * (c['jaw_rate'] * ph - 0.1))) - c['jaw_hold'] + 7 * hop + 14 * yawn) * DEG)
    # the arms: the shoulder swings against the leg on its side (the left arm is back when the left foot lands), the
    # forearm and the fist follow late and flex as the arm comes forward
    for side, (sh, el, hand, sd) in ARMS.items():
        at = (0.0 if side == 'L' else 0.5) + c.get('arm_phase', 0.0)
        swing = c['arm'] * harm(ph, (1, 1, at), (c['arm2'], 2, at + 0.1)) + c['arm_lift'] - 24 * hop
        out = sd * (c['arm_out'] + c['arm_pump'] * harm(ph, (1, 2, at + 0.05)) + 6 * hop) + c['arm_roll'] * (-over if side == 'L' else over)
        P.put(sh, mul(chest, rot([swing, 0, out])))
        flex = c['elbow'] * harm(ph, (1, 1, at + 0.5 + c['elbow_lag']), (c['elbow2'], 2, at + c['elbow_lag'] + 0.1))
        pose[el][3] = rest[el][3] + round((flex - c['elbow_base'] - 14 * hop) * DEG)
        wrist = c['wrist'] * harm(ph, (1, 1, at + 0.5 + 2 * c['elbow_lag']))
        pose[hand][3] = rest[hand][3] + round((0.5 * flex + wrist - c['wrist_hold']) * DEG)
    # the tail: its root turns against the hips and each segment follows the one before it a little later; a bounce
    # runs up it at every step
    for k, b in enumerate(TAIL):
        d = c['tail_lag'] * k
        pose[b][3] = rest[b][3] + round((TAIL_REST[k] + c['tail_out'] * (1 - 0.25 * k) + (1 + 0.5 * k) * c['tail_pitch'] * harm(ph - d, (1, 2, c['pitch_at'] + 0.15))
                                         + c['tail_pitch1'] * harm(ph - d, (1, 1, 0.3))) * DEG)
        pose[b][4] = rest[b][4] + round(((1 + 0.4 * k) * c['tail_yaw'] * harm(ph - d, (1, 1, 0.5 + c['yaw_at'] + 0.22)) + 16 * hop * math.sin(TAU * (4 * ph - d))) * DEG)
        pose[b][5] = rest[b][5] + round(c['tail_roll'] * harm(ph - d, (1, 1, 0.79 + c['roll_at'] + 0.15)) * DEG)


PROFILE = dict(
    species=SPECIES, name='Veemon', source=SOURCE, parents=PARENTS,
    pelvis=PELVIS, chest=None, neck=None, head=HEAD, tail=(), loose=(),
    legs=LEGS, pole_world=True, rest_plane=True, pole={False: [0.1, 0.0, -1.0]}, rest_fix=rest_fix,
    paw_flat={'RH': [0, 0, 0], 'LH': [0, 0, 0]},
    sole={False: [2, 20, -40]},                            # the middle of the flat foot, on its bottom
    reach={'front': 0, 'hind': -38},
    fold={False: 34}, clear=4,
    speed_range={0: (0, 0), 2: (15, 31), 3: (10, 20), 4: (35, 52)},
    body=body, events=face_events, floor=3, stance_slip=0.2, tol=3,
    gaits={},
)
COMMON = dict(
    hop=0, hop_at=0.0, hop_w=0.3, yawn=0, yawn_at=0.4,
    kind='walk', snap=False, arc=0.5, clear_ease=0.1, world_ease=True, fold_soft=8, slip=0.0, steps=('LH', 'RH'),
    reach={'front': 0, 'hind': 0}, lift={'front': 0, 'hind': 24}, curl={'front': 0, 'hind': 0}, peel={'front': 0, 'hind': 0},
    out={'front': 0, 'hind': 0}, wide={'front': 0, 'hind': 4}, track={'front': 0, 'hind': 4}, heel=3,
    high=0.29, bob=4, bob2=0.8, bob_side=0.8, height=22, shift=5, shift2=0.8, roll_at=0.0,
    hip_tilt=0, hip_pitch=1, hip_yaw=6, hip_yaw2=0.5, hip_roll=3, hip_roll2=0.6,
    lean=3, pitch=1.5, pitch1=0.5, pitch_at=0.1, yaw=1, counter=0.9, roll=4.5, roll2=0.6, yaw_at=0.03, lag=0.06, breath=0,
    head=0, steady=0.7, nod=1.5, nod1=0.5, look=2, head_lag=0.07, head_roll=1.5,
    jaw=2, jaw_rate=2, jaw_hold=0,
    arm=13, arm2=2, arm_lift=8, arm_out=-3, arm_pump=2, arm_roll=2, elbow=8, elbow2=2, elbow_base=45, elbow_lag=0.06, wrist=5, wrist_hold=16,
    tail_out=0, tail_pitch=4, tail_pitch1=2, tail_yaw=9, tail_roll=2, tail_lag=0.06,
)

FOLLOW = {5: (0.45, 0.5), 6: (0.5, 0.45), 7: (0.45, 0.45), 8: (0.45, 0.5), 9: (0.5, 0.45), 10: (0.45, 0.45),
          HEAD: (0.7, 0.55), JAW: (0.6, 0.5), 11: (0.6, 0.5), 12: (0.5, 0.45), 13: (0.45, 0.4)}     # (rad per tick, damping)


def spring(values, rate, damping):
    """A loose second-order follower of a cyclic sequence (run round three times so the loop settles)."""
    n = len(values)
    y, v = values[0], 0.0
    out = []
    for i in range(3 * n):
        x = values[i % n]
        v += (rate * rate * (x - y) - 2 * damping * rate * v)
        y += v
        out.append(y)
    return out[-n:]


def unwrap(values):
    """Euler angles (4096 to a turn) without the jump at the turn."""
    out = [values[0]]
    for v in values[1:]:
        out.append(out[-1] + (v - out[-1] + 2048) % 4096 - 2048)
    return out


def _axis_angle_blend(ma, mb, w):
    """The rotation w of the way from matrix ma to mb (a turn about the axis of ma^T mb)."""
    r = mul(tr(ma), mb)
    c = max(-1.0, min(1.0, (r[0][0] + r[1][1] + r[2][2] - 1) / 2))
    ang = math.acos(c)
    if ang < 1e-6:
        return ma
    k = [r[2][1] - r[1][2], r[0][2] - r[2][0], r[1][0] - r[0][1]]
    n = math.sqrt(sum(x * x for x in k))
    if n < 1e-9:
        return ma
    x, y, z = (v / n for v in k)
    a = ang * w
    cs, sn, t = math.cos(a), math.sin(a), 1 - math.cos(a)
    q = [[t * x * x + cs, t * x * y - sn * z, t * x * z + sn * y],
         [t * x * y + sn * z, t * y * y + cs, t * y * z - sn * x],
         [t * x * z - sn * y, t * y * z + sn * x, t * z * z + cs]]
    return mul(ma, q)


def blend(a, b, w, hist):
    """Two poses mixed through their rotation matrices (Euler angles of two cycles may sit on different branches)."""
    out = []
    for i, (ba, bb) in enumerate(zip(a, b)):
        row = list(ba)
        for k in range(6, 9):
            row[k] = ba[k] + (bb[k] - ba[k]) * w
        if i:
            m = _axis_angle_blend(mmd.rot_matrix(*ba[3:6]), mmd.rot_matrix(*bb[3:6]), w)
            ang = mmd.matrix_euler(m, hist.get(i))
            hist[i] = ang
            row[3:6] = list(ang)
        out.append(row)
    return out


def follow_through(out, cycles_ticks, cfg):
    follow = cfg.get('follow', 1.0)
    for b, (rate, damping) in FOLLOW.items():
        for ch in (3, 4, 5):
            seq = unwrap([out[i][b][ch] for i in range(cycles_ticks)])
            mixed = spring(seq, rate * cfg.get('spring', 1.0), damping)
            for i in range(cycles_ticks):
                out[i][b][ch] = seq[i] + (mixed[i] - seq[i]) * follow


def compose(rig, cfg, frames_a):
    """Two cycles from cycle A (`frames_a`) and the cycle the gait's `other` settings give, eased into each other."""
    ticks, speed = cfg['ticks'], cfg['speed']
    frames_b, _ = quadruped.gait(rig, dict(cfg, **cfg['other']))
    out = []
    hist = {}
    for i in range(2 * ticks):
        w = 0.5 - 0.5 * math.cos(math.pi * i / ticks)
        pose = blend(frames_a[i % ticks], frames_b[i % ticks], w, hist)
        pose[0][8] = -round(speed * i)
        out.append(pose)
    follow_through(out, 2 * ticks, cfg)
    closing = [list(v) for v in out[0]]
    closing[0][8] = -round(speed * 2 * ticks)
    out.append(closing)
    return out


def compose_idle(rig, cfg, frames):
    """The idle's one loop with its loose parts passed through a loose spring each."""
    ticks = cfg['ticks']
    out = [[list(b) for b in pose] for pose in frames[:ticks]]
    follow_through(out, ticks, cfg)
    out.append([list(v) for v in out[0]])
    return out


PROFILE['gaits'] = {
    0: dict(COMMON, kind='idle', name='idle', ticks=96, speed=0, steps=(), lean=0, compose=compose_idle, cycles=1,
            touchdown={'LH': 0.0, 'RH': 0.0}, duty={'LH': 1.0, 'RH': 1.0}, lift={'front': 0, 'hind': 0}, spring=0.8),
    2: dict(COMMON, name='walk', ticks=12, speed=16, peel={'front': 0, 'hind': 17}, curl={'front': 0, 'hind': 18}, heel=6,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.56, 'RH': 0.56},
            bob=8, bob2=1.4, shift=8, roll=7, hip_yaw=9, hip_roll=5, lean=5, nod=5, look=8, head_roll=7, head_lag=0.14,
            arm=26, arm_lift=-4, arm_out=-40, arm_pump=4, elbow=22, elbow_base=42, wrist=10, tail_yaw=18, tail_roll=5, tail_pitch=6, tail_lag=0.12),
    3: dict(COMMON, name='tired walk', ticks=18, speed=11, track={'front': 0, 'hind': 6}, peel={'front': 0, 'hind': 6}, curl={'front': 0, 'hind': 12}, heel=5,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.62, 'RH': 0.62}, height=10, lift={'front': 0, 'hind': 18},
            lean=12, head=9, arm=9, arm_lift=30, arm_out=-52, arm_pump=2, elbow=5, elbow_base=56, wrist=6, bob=3, roll=6, shift=7,
            hip_roll=4, tail_pitch=2, tail_out=-16, tail_yaw=9, tail_lag=0.12, nod=3, look=6, head_roll=6, head_lag=0.14, yawn=1),
    4: dict(COMMON, name='run', kind='trot', sink=-3, arm_phase=-0.07, heel=0, peel={'front': 0, 'hind': 0}, curl={'front': 0, 'hind': 14}, ticks=8, speed=38,
            touchdown={'LH': 0.0, 'RH': 0.5}, duty={'LH': 0.3, 'RH': 0.3}, height=20, arc=0.6, clear_ease=0.05, lift={'front': 0, 'hind': 34},
            bob=11, bob2=1.5, lean=15, head=-8, arm=44, arm_lift=-2, arm_out=-26, arm_pump=6, elbow=24, elbow_base=72, wrist=10, hip_yaw=6, hip_roll=2.5, roll=4.5, shift=4,
            wide={'front': 0, 'hind': 2}, tail_out=14, tail_yaw=14, tail_roll=4, tail_pitch=4, tail_lag=0.1, nod=5, look=5, head_roll=5),
}
OTHER = {      # cycle B: what changes from cycle A, as factors on A's numbers or the leg settings
    0: None,
    2: dict(scale=dict(bob=1.3, lean=1.2, hip_yaw=1.2, roll=1.25, arm=0.75, tail_yaw=1.3, head_roll=0.6, nod=1.4), leg_lift={'LH': 0.9, 'RH': 1.08},
            touchdown={'LH': 0.0, 'RH': 0.52}, settle=2.0, heel=4, hop=1.5),
    3: dict(scale=dict(bob=1.15, lean=0.95, arm=1.2, roll=1.1, shift=1.1), leg_lift={'LH': 0.88, 'RH': 1.1},
            touchdown={'LH': 0.0, 'RH': 0.51}, settle=2.0, heel=4),
    4: dict(scale=dict(lean=1.15, arm=0.85, hip_yaw=1.15, bob=1.2, head_roll=0.5), leg_lift={'LH': 0.8, 'RH': 1.0}, touchdown={'LH': 0.0, 'RH': 0.5}, settle=2.0, heel=0, hop=1),
}
for slot, spec in OTHER.items():
    if spec is None:
        continue
    cfg = PROFILE['gaits'][slot]
    other = {k: v for k, v in spec.items() if k != 'scale'}
    other.update({k: cfg[k] * f for k, f in spec['scale'].items()})
    cfg.update(cycles=2, compose=compose, other=other)


def aliased(data, n):
    """The model with its battle walk and run (35, 36) playing the field clips' programs."""
    m = mmd.MMD.parse(data, n)
    for alias, slot in ALIASES.items():
        m.anims.table[alias] = m.anims.table[slot]
    out = m.build()
    mmd.MMD.parse(out, n)
    return out


def build(data, skeleton):
    """The model with the four clips written on it -> (bytes, report)."""
    from tools.models.field_animations.reviewed import reviewed
    if reviewed(hashlib.sha256(data).hexdigest()) != SOURCE:
        raise ValueError("Veemon's gait requires the reviewed source")
    mmd.exe().skeleton[SPECIES] = skeleton
    mmd.exe().bone_count[SPECIES] = len(skeleton)
    shared = aliased(data, len(skeleton))
    profile = dict(PROFILE, source=hashlib.sha256(shared).hexdigest())
    result, report = quadruped.build(shared, skeleton, profile)
    report['source_sha256'] = hashlib.sha256(data).hexdigest()
    return result, report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--report', type=Path)
    p.add_argument('--tex', type=Path, help='the texture before the eye frames (edit.py get 180), with --out-tex')
    p.add_argument('--out-tex', type=Path)
    a = p.parse_args()
    skeleton = json.loads(next((ROOT / 'content/species').glob('180-*.json')).read_text())['model']['skeleton']
    data, report = build(a.source.read_bytes(), skeleton)
    a.out.write_bytes(data)
    if a.tex:
        a.out_tex.write_bytes(texture(a.tex.read_bytes()))
    text = json.dumps(report, indent=2, default=str) + '\n'
    if a.report:
        a.report.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
