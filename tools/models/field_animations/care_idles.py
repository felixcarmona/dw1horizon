"""Condition idles of imported species made from the species' own field idle: tired, sick, hungry, needs the toilet,
sleepy and unhappy must look different from the plain idle.

The game plays slot 1 (poor condition) while the partner is sleepy, tired, injured or sick, and 14-19 (sick, hungry,
needs the toilet, sleepy, tired, unhappy) as condition idles near the tamer (docs/reference/motion.md). The importer
gives them a DW1 donor's clips retargeted; where a field rework made slot 1 or 18 a copy of the new field idle, the
condition look is lost. This stage, the last of the provider (content/models/imports/species.py), makes those slots
again from the FINAL model's field idle (slot 0: the reviewed motion, the chibi proportions, the hover of a flyer) with
a posture and timing layer per condition:

  tired     the upper body slumps forward, the head hangs, arms, wings, ears and tail droop, the idle's own motion is
            damped and one slow heavy breath runs through the clip, the head and limbs following the chest late
  sick      a deeper hunch, the limbs drawn in, the motion damped more, and two short shudders a loop (a few ticks of
            a degree or two, eased in and out, the head a tick behind: never a continuous vibration)
  hungry    the head low, looking down at the belly and slowly from side to side
  toilet    restless: the body sways from side to side twice a loop, the head against it
  sleepy    the head sinks slowly and catches itself (two nods a loop), eased both ways
  unhappy   the head down and a slow sway of the head and chest

Only rotation channels of non-root bones change. Every channel of the legs and of the bones they hang from (pelvis,
hips: `keep`) stays the idle's, so the feet stay where the idle plants them; scale and translation channels (bone
lengths, the chibi reshape) are the idle's everywhere. A clip is the idle's cycle repeated a whole number of times
(`cycles`), so it closes where the idle closes; slot 1 keeps the idle's length (the condition timer counts against it).

Rotations are about the model's own axes (x the side, y down, z back) at each bone's joint, applied parent first, so a
child adds its own to its parent's (chest, neck and head together make the slump):

  lean      bones of the body and head that do not carry a leg: rotated about the side axis (the top goes forward,
            a head's front goes down), `lean` / `head` degrees of the body type split along the bones
  droop     the first bone of a limb chain (arm, wing, tail, ear): turned so its tip (a point in the bone's frame)
            goes down by `droop` degrees; a limb already hanging stays as it is

Profiles (content/models/imports/care-idles.json), per species: `body` (biped, quadruped, flyer, serpent, legless:
the degrees below), the bone lists, the slots and their condition, and an optional `gain` per condition. The planner
(`plan`, a developer command) reads the roles from the final model's geometry, makes the clips, measures them with
tools/models/care_qa.py and writes the rows; the build only applies the rows. Standard library only (deterministic
under tools/derive's correctly rounded math).

    python -m tools.models.field_animations.care_idles plan OUT.json ID FINAL.MMD [BASE.MMD MAIN.MMD]
"""
import copy
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

MANIFEST = ROOT / 'content/models/imports/care-idles.json'
CONDITION_SLOTS = (1, 14, 15, 16, 17, 18, 19)
DEFAULT = {1: 'tired', 14: 'sick', 15: 'hungry', 16: 'toilet', 17: 'sleepy', 18: 'tired', 19: 'unhappy'}
DEG = 4096 / 360

# degrees of the whole body's lean, of the head (on top of the lean) and of a limb's droop, per body type
BODY = {
    'biped': dict(lean=14.0, head=16.0, droop=26.0),
    'quadruped': dict(lean=6.0, head=22.0, droop=16.0),
    'flyer': dict(lean=10.0, head=16.0, droop=24.0),
    'serpent': dict(lean=8.0, head=18.0, droop=14.0),
    'legless': dict(lean=12.0, head=16.0, droop=22.0),
}
# per condition: multipliers of the body type's degrees, how much of the idle's own motion stays (damp) and the motion
# layered on top (degrees, counts per loop)
CONDITIONS = {
    'tired': dict(lean=1.0, head=.8, droop=1.0, damp=.55, breath=4.0, breaths=1),
    'sick': dict(lean=1.4, head=.5, droop=.2, tuck=.9, damp=.55, breath=2.0, breaths=2, shiver=1.8, bursts=2),
    'hungry': dict(lean=.6, head=1.8, droop=.3, tuck=.5, damp=.6, breath=1.2, breaths=1, look=10.0),
    'toilet': dict(lean=.5, head=.2, droop=.4, tuck=.6, damp=.8, sway=8.0, sways=2),
    'sleepy': dict(lean=.4, head=.9, droop=1.1, damp=.4, nod=22.0, nods=2),
    'unhappy': dict(lean=.9, head=1.6, droop=.8, damp=.6, sway=4.0, yaw=10.0, sways=1),
}
LAG = 2             # ticks a child's layered motion follows its parent's


# ------------------------------------------------------------------ small matrix helpers (lists, standard library)
def _mul(a, b):
    return [[a[i][0] * b[0][j] + a[i][1] * b[1][j] + a[i][2] * b[2][j] for j in range(3)] for i in range(3)]


def _tr(a):
    return [[a[j][i] for j in range(3)] for i in range(3)]


def _apply(m, v):
    return [m[i][0] * v[0] + m[i][1] * v[1] + m[i][2] * v[2] for i in range(3)]


def _axis_angle(axis, deg):
    x, y, z = axis
    n = math.sqrt(x * x + y * y + z * z)
    if n < 1e-9 or deg == 0:
        return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    x, y, z = x / n, y / n, z / n
    a = math.radians(deg)
    c, s, t = math.cos(a), math.sin(a), 1 - math.cos(a)
    return [[t * x * x + c, t * x * y - s * z, t * x * z + s * y],
            [t * x * y + s * z, t * y * y + c, t * y * z - s * x],
            [t * x * z - s * y, t * y * z + s * x, t * z * z + c]]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _norm(a):
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def _wrap(d):
    return (d + 2048) % 4096 - 2048


# ------------------------------------------------------------------ time shapes (periodic in u = tick / length)
def _bump(u, centre, width):
    """A Hann window around `centre` (fraction of the loop), `width` long, periodic."""
    d = (u - centre + 0.5) % 1.0 - 0.5
    return 0.5 + 0.5 * math.cos(math.pi * d / (width / 2)) if abs(d) < width / 2 else 0.0


def _nod(x):
    """One nod in x in [0, 1): the head sinks slowly (eased) for 70 % of it, then lifts again, eased, in 30 %."""
    x %= 1.0
    if x < 0.7:
        k = x / 0.7
        return k * k * (3 - 2 * k)
    k = (x - 0.7) / 0.3
    return 0.5 + 0.5 * math.cos(math.pi * k)


def layer(cond, u, n, depth):
    """(extra lean, extra head pitch, roll, yaw) in degrees at loop fraction u for a bone `depth` steps down the body
    (its motion follows the chest LAG ticks per step)."""
    c = CONDITIONS[cond]
    v = (u - depth * LAG / n) % 1.0
    lean = head = roll = yaw = 0.0
    if c.get('breath'):
        lean += c['breath'] * (0.5 - 0.5 * math.cos(2 * math.pi * c['breaths'] * v))
    if c.get('shiver'):
        env = sum(_bump(v, (k + 0.3) / c['bursts'], min(0.4, 16.0 / n)) for k in range(c['bursts']))
        roll += c['shiver'] * env * math.sin(2 * math.pi * v * n / 6.0)
    if c.get('look'):
        yaw += c['look'] * math.sin(2 * math.pi * v)
        head += 0.3 * c['look'] * (0.5 - 0.5 * math.cos(4 * math.pi * v))
    if c.get('sway'):
        roll += c['sway'] * math.sin(2 * math.pi * c['sways'] * v)
    if c.get('yaw'):
        yaw += c['yaw'] * math.sin(2 * math.pi * c['sways'] * v + 0.6)
    if c.get('nod'):
        head += c['nod'] * _nod(c['nods'] * v)
    return lean, head, roll, yaw


# ------------------------------------------------------------------ the clip
MAX_CYCLE = 120         # an idle cycle longer than this is resampled (a condition idle must stay under 127 ticks)


def _cycle(model, nb, cycles):
    frames, loop, events = animsheet.slot_frames(model, nb, 0)
    cyc = frames[loop:-1] if len(frames) - loop > 1 else frames[loop:]
    p = len(cyc)
    base = [[list(map(int, b)) for b in f] for f in cyc]
    ev = [(k - loop, kind, c) for k, kind, c in events if loop <= k < len(frames) - 1]
    if p > MAX_CYCLE:                                   # a little faster, the same motion
        q = MAX_CYCLE
        out = []
        for j in range(q):
            x = j * p / q
            i = int(x)
            w = x - i
            a, b = base[i], base[(i + 1) % p]
            out.append([[int(round(u + w * (_wrap(v - u) if 3 <= ch < 6 else v - u))) for ch, (u, v) in
                         enumerate(zip(ra, rb))] for ra, rb in zip(a, b)])
        base, ev, p = out, [(int(k * q / p), kind, c) for k, kind, c in ev], q
    samples = [copy.deepcopy(base[t % p]) for t in range(p * cycles)] + [copy.deepcopy(base[0])]
    ev = [(k + i * p, kind, c) for i in range(cycles) for k, kind, c in ev]
    return samples, ev, p


def _mean_angles(samples, bones):
    out = {}
    for b in bones:
        out[b] = []
        for ch in (3, 4, 5):
            ref = samples[0][b][ch]
            out[b].append(ref + sum(_wrap(f[b][ch] - ref) for f in samples[:-1]) / max(1, len(samples) - 1))
    return out


def condition_clip(samples, parents, row, cond, gain=1.0):
    """Per-tick poses of a condition idle from the idle's `samples` (the cycle repeated, closing pose last)."""
    body = BODY[row['body']]
    c = CONDITIONS[cond]
    n = len(samples) - 1
    lean_bones, head_bones = row['lean'], row['head']
    droop = {int(b): tip for b, tip in row['droop'].items()}
    moved = set(lean_bones) | set(head_bones) | set(droop) | set(row.get('damp', []))
    keep = set(row['keep'])
    order = []
    seen = set()

    def visit(b):
        if b not in seen and b >= 0:
            visit(parents[b])
            seen.add(b)
            order.append(b)
    for b in range(len(parents)):
        visit(b)
    mean = _mean_angles(samples, [b for b in moved if b not in keep])
    first = {}

    def world0(b):                                          # pure world rotation of bone b in the idle's first pose
        if b < 0:
            return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        if b not in first:
            first[b] = _mul(world0(parents[b]), mmd.rot_matrix(*samples[0][b][3:6]))
        return first[b]
    limb = {}                                               # per limb: (axis in the parent's frame, sin) per target
    for b, tip in droop.items():
        d = _apply(world0(b), tip)
        side = max(-1.0, min(1.0, d[0] / (0.4 * _norm(d) + 1e-9)))
        limb[b] = []
        for target in ((0.0, 1.0, 0.0), (-side, 0.5, -0.3)):    # down; in towards the body, down and forward
            axis = _cross(d, target)
            k = _norm(axis) / (_norm(d) * _norm(target))
            limb[b].append((_apply(_tr(world0(parents[b])), axis) if k > 1e-6 else None, k))
    depth = {b: i for i, b in enumerate(lean_bones + [h for h in head_bones if h not in lean_bones])}
    nl, nh = max(1, len(lean_bones)), max(1, len(head_bones))
    out = []
    for t, pose in enumerate(samples):
        u = (t % n) / n
        pose = [list(v) for v in pose]
        for b in mean:                                      # the idle's own motion, damped
            for i, ch in enumerate((3, 4, 5)):
                d = _wrap(pose[b][ch] - mean[b][i])
                pose[b][ch] = mean[b][i] + c['damp'] * d
        orig = [list(v) for v in pose]
        world = {}

        def rot(b):                                         # pure world rotation of bone b in the new pose
            if b < 0:
                return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
            if b not in world:
                world[b] = _mul(rot(parents[b]), mmd.rot_matrix(*pose[b][3:6]))
            return world[b]
        for b in order:
            if b == 0 or b in keep or b not in moved:
                continue
            extra = []
            if b in depth:
                lean, head, roll, yaw = layer(cond, u, n, depth[b])
                deg = 0.0
                if b in lean_bones:
                    deg += (body['lean'] * c['lean'] * gain + lean) / nl
                if b in head_bones:
                    deg += (body['head'] * c['head'] * gain + head) / nh
                extra.append(([1.0, 0.0, 0.0], deg))
                if roll:
                    extra.append(([0.0, 0.0, 1.0], roll / (nl + nh)))
                if yaw and b in head_bones:
                    extra.append(([0.0, 1.0, 0.0], yaw / nh))
            if b in droop:
                lean, _, _, _ = layer(cond, u, n, len(depth) + 1)
                P = rot(parents[b])
                for (axis, k), deg in zip(limb[b], (body['droop'] * c['droop'] * gain + 0.5 * lean,
                                                    body['droop'] * c.get('tuck', 0.0) * gain)):
                    if deg and axis:
                        extra.append((_apply(P, axis), deg * k))
            if not extra:
                if b in mean:
                    world.pop(b, None)
                continue
            P = rot(parents[b])
            L = mmd.rot_matrix(*pose[b][3:6])
            Wm = _mul(P, L)
            for axis, deg in extra:
                Wm = _mul(_axis_angle(axis, deg), Wm)
            new = _mul(_tr(P), Wm)
            pose[b][3:6] = mmd.matrix_euler(new, prev=orig[b][3:6])
            for k in [k for k in world if k == b or _descends(parents, k, b)]:
                del world[k]
        out.append([[int(round(x)) for x in v] for v in pose])
    out[-1] = [list(v) for v in out[0]]
    return out


def _descends(parents, c, b):
    while c >= 0:
        c = parents[c]
        if c == b:
            return True
    return False


def cycles_for(slot, p):
    """Whole idle cycles in a condition clip: slot 1 keeps the idle's length; the others last about 3-6 seconds."""
    if slot == 1:
        return 1
    k = max(1, round(72 / p))
    while k > 1 and k * p > 120:
        k -= 1
    return k


def tame(frames, factors):
    """A care clip whose bones in `factors` keep only that fraction of their swing about the clip's own mean pose
    (rotation channels; a retargeted donor clip that turns a bone far beyond anything the species does)."""
    poses = [[list(map(int, b)) for b in f] for f in frames]
    for b, f in factors.items():
        for ch in (3, 4, 5):
            ref = poses[0][b][ch]
            mean = ref + sum(_wrap(p[b][ch] - ref) for p in poses) / len(poses)
            for p in poses:
                p[b][ch] = int(round(mean + f * _wrap(p[b][ch] - mean)))
    return poses


def apply(data, skeleton, row):
    """The final model with the condition idles of `row` (and its tamed care clips) -> (bytes, report)."""
    nb = len(skeleton)
    parents = [p for _, p in skeleton]
    if row.get('parents') and row['parents'] != parents:
        raise ValueError('care idles: the skeleton differs from the profile\'s')
    model = mmd.MMD.parse(data, nb)
    table = model.anims.table
    before = {s: model.anims.anims[table[s]].build() if hasattr(model.anims.anims[table[s]], 'build') else None
              for s in range(len(table)) if table[s] is not None}
    made, report = {}, {}
    for slot_text, cond in sorted(row['slots'].items(), key=lambda kv: int(kv[0])):
        slot = int(slot_text)
        p = len(_cycle(model, nb, 1)[0]) - 1
        k = cycles_for(slot, p)
        key = (cond, k)
        if key not in made:
            samples, events, _ = _cycle(model, nb, k)
            poses = condition_clip(samples, parents, row, cond, row.get('gain', {}).get(cond, 1.0))
            made[key] = mmd.encode_anim(poses, nb, 0, events, tol=row.get('tol', 1), repeats=k > 1)
        table[slot] = len(model.anims.anims)
        model.anims.anims.append(made[key])
        report[slot] = dict(condition=cond, ticks=k * p + 1, cycles=k)
    for slot_text, factors in sorted(row.get('tame', {}).items(), key=lambda kv: int(kv[0])):
        slot = int(slot_text)
        frames, loop, events = animsheet.slot_frames(model, nb, slot)
        poses = tame(frames, {int(b): f for b, f in factors.items()})
        table[slot] = len(model.anims.anims)
        model.anims.anims.append(mmd.encode_anim(poses, nb, loop, events, tol=1, repeats=False))
        report[slot] = dict(tamed=factors, ticks=len(poses))
    model.anims.anims, model.anims.table = motioncyclelayer.share_identical_streams(model.anims.anims, model.anims.table)
    out = model.build()
    check = mmd.MMD.parse(out, nb)
    for s, b in before.items():
        if str(s) in row['slots'] or str(s) in row.get('tame', {}) or b is None:
            continue
        if check.anims.anims[check.anims.table[s]].build() != b:
            raise ValueError(f'care idles: slot {s} changed')
    report['storage'] = motionstorage.require(out, nb)['resident_bytes']
    return out, report


def rows():
    return json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
