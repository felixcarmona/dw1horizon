"""Antylamon's walk (species 309, slot 2): the imported clip, reshaped by `chibi.py`, with its stray arm key and its
lift-off kinks smoothed.

Antylamon (a tall rabbit-eared Deva) is an imported partner reshaped to Digimon World's proportions by `chibi.py`
(overlay `antylamon-chibi`). Two things in its walk read badly:

- Each shoulder has one key that is out of line: the left shoulder (bone 13) at tick 14 and the right one (bone 16) at
  tick 6, half a loop apart. The key sits about 24 degrees off the middle of its neighbours (all three channels at once, it
  is a stray pose, not an angle wrap) and the arm snaps out and back in two ticks: the hand moves 130 to 145 units in each
  step against a median of 12. The key is already in the import.
- The legs lift off with a kink: at the step before each foot leaves the floor the shin turns 70 degrees per tick per
  tick, the foot 52 and the thigh 38 (the median is 12), then the swing runs on at once. It is the same two ticks in each
  leg (ticks 3 and 11).

`build` runs the reshaping and then rewrites slot 2 alone, with the same number of ticks, the same root motion and the
same sounds. What is touched, and nothing else:

- The stray shoulder key (and its neighbour that was pulled off with it) is replaced by a cubic curve through the keys
  around it, in the angles, so the arm swings through instead of snapping.
- Thighs, shins and ankles (bones 3 to 5 and 7 to 9) are eased where they kink: each bone's turn is blended towards the
  middle of its neighbours' turns, by a weight that is zero while the foot stands on the floor (the stance stays planted
  where the clip put it) and grows to its full value over the ticks around lift-off and landing. Both legs run the same
  weights half a loop apart, so they stay the mirror of each other.

Idle (slots 0 and 33), tired walk and run are the chibi overlay's, byte for byte.

Offline: this runs on the reshaped model inside the overlay (tools/derive's overlays step); nothing is stored but the
overlay's recipe name in content/models/imports/species.py.
"""
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
from tools.models.field_animations.okuwamon_limbs import exp_so3, log_so3  # noqa: E402

SPECIES, NB = 309, 22
SLOT = 2
SHOULDERS = (13, 16)                     # the arms hang from these two bones; their elbows and hands do not turn
LEGS = ((3, 4, 5, 6), (7, 8, 9, 10))     # thigh, shin, ankle, toes
SPIKE = 15.0                             # degrees a shoulder key may sit off the middle of its neighbours before it is a stray
SPAN = 6.0                               # degrees: the keys beside a stray one that are pulled off with it
SMOOTH = 0.5                             # share of the way to the middle of the neighbours' turns, at full weight
STANCE_Y = 6.0                           # units: a foot whose lowest vertex is within this of the floor is standing
EASE = 1.0                               # ticks the weight takes to rise from the stance to its full value


def rot(pose, bone):
    return np.array(mmd.rot_matrix(*pose[bone][3:6]), float)[:3, :3]


def deviation(rots, t):
    """Degrees the rotation of tick t lies from the middle of its two neighbours' (cyclic)."""
    n = len(rots)
    a, c = rots[t - 1], rots[(t + 1) % n]
    mid = a @ exp_so3(0.5 * log_so3(a.T @ c))
    return math.degrees(float(np.linalg.norm(log_so3(mid.T @ rots[t]))))


def hermite(p0, p1, m0, m1, u):
    return ((2 * u**3 - 3 * u**2 + 1) * p0 + (u**3 - 2 * u**2 + u) * m0
            + (-2 * u**3 + 3 * u**2) * p1 + (u**3 - u**2) * m1)


def stray_keys(frames, bone):
    """The ticks of a stray key and of the keys beside it that were pulled off with it, [] when there is none."""
    n = len(frames) - 1
    rots = [rot(f, bone) for f in frames[:n]]
    dev = [deviation(rots, t) for t in range(n)]
    worst = max(range(n), key=lambda t: dev[t])
    if dev[worst] < SPIKE:
        return []
    span = [worst]
    t = worst - 1
    while dev[t % n] > SPAN and len(span) < 4:
        span.insert(0, t % n)
        t -= 1
    t = worst + 1
    while dev[t % n] > SPAN and len(span) < 4:
        span.append(t % n)
        t += 1
    return span


def repair_stray(frames, bone):
    """Replace a stray shoulder key with a cubic curve through the keys round it (each angle channel on its own, the
    short way round). The curve runs from the last good key before the span to the first one after it."""
    n = len(frames) - 1
    span = stray_keys(frames, bone)
    if not span:
        return frames, []
    # the span can only be a few ticks; the keys before and after it are the ends of the curve
    before, after = (span[0] - 1) % n, (span[-1] + 1) % n
    gap = len(span) + 1
    out = copy.deepcopy(frames)
    for ch in range(3, 6):
        def val(t, ref):
            v = frames[t % n][bone][ch]
            return ref + (v - ref + 2048) % 4096 - 2048
        p0 = frames[before][bone][ch]
        p1 = val(after, p0)
        m0 = (p0 - val(before - 1, p0)) * gap
        m1 = (val(after + 1, p1) - p1) * gap
        for k, t in enumerate(span, 1):
            out[t][bone][ch] = round(hermite(p0, p1, m0, m1, k / gap))
    out[n] = copy.deepcopy(out[0])
    out[n][0] = list(frames[n][0])
    return out, span


def stance_weights(model, frames, bones, mesh):
    """Per tick, how much of the smoothing a leg takes: 0 while its foot stands flat (the ankle block and the toes both
    within STANCE_Y of the floor), 1 away from it, with a ramp of EASE ticks."""
    n = len(frames) - 1
    parts = [np.concatenate([np.arange(a, a + k) for b, a, k in mesh.slices if b in bones[2:]])]
    standing = []
    for pose in frames[:n]:
        p = copy.deepcopy(pose)
        p[0] = [4096] * 3 + [0] * 6
        world = mesh.world(mmd.bone_matrices(model, p)).astype(float)
        standing.append(all(float(world[idx][:, 1].max()) > -STANCE_Y for idx in parts))
    weights = []
    for t in range(n):
        d = min((min((t - s) % n, (s - t) % n) for s in range(n) if standing[s]), default=n)
        weights.append(min(1.0, d / EASE))
    return weights


def ease_leg(frames, bones, weights, share):
    """Blend each bone's turn towards the middle of its neighbours' turns, tick by tick, with the leg's weights."""
    n = len(frames) - 1
    out = copy.deepcopy(frames)
    for b in bones:
        rots = [rot(f, b) for f in frames[:n]]
        for t in range(n):
            w = share * weights[t]
            if w <= 0:
                continue
            a, c = rots[t - 1], rots[(t + 1) % n]
            mid = a @ exp_so3(0.5 * log_so3(a.T @ c))
            new = rots[t] @ exp_so3(w * log_so3(rots[t].T @ mid))
            ref = out[t][b][3:6]
            out[t][b][3:6] = [round(x) for x in mmd.matrix_euler(new.tolist(), ref)]
    out[n] = copy.deepcopy(out[0])
    out[n][0] = list(frames[n][0])
    return out


def rewrite(model, frames, mesh):
    out = frames
    fixed = {}
    for b in SHOULDERS:
        out, span = repair_stray(out, b)
        fixed[b] = span
    n = len(frames) - 1
    for k, bones in enumerate(LEGS):
        w = stance_weights(model, out, bones, mesh)
        out = ease_leg(out, bones[:3], w, SMOOTH)
    # the closing frame repeats the first
    for b in range(1, len(out[0])):
        out[n][b] = list(out[0][b])
    return [[[round(x) for x in bone] for bone in pose] for pose in out], fixed


def build(data, skeleton):
    from tools.models.field_animations import chibi
    import animstudio
    result, proof = chibi.build(data, skeleton)
    old = mmd.MMD.parse(result, NB)
    old.type = SPECIES
    new = mmd.MMD.parse(result, NB)
    new.type = SPECIES
    mesh = animstudio.FastMesh(type('M', (), dict(m=old, skel=skeleton))())
    frames, loop, events = animsheet.slot_frames(old, NB, SLOT)
    out, fixed = rewrite(old, frames, mesh)
    animation = mmd.encode_anim(out, NB, loop_sample=loop, events=events, tol=0, repeats=False)
    index = old.anims.table[SLOT]
    new.anims.anims[index] = animation
    final = new.build()
    actual = mmd.MMD.parse(final, NB)
    assert old.tmd.build() == actual.tmd.build()
    assert changed_programs(old, actual) == [SLOT], changed_programs(old, actual)
    storage = motionstorage.require(final, NB)
    proof = dict(proof, output_sha256=hashlib.sha256(final).hexdigest(), changed_slots=[SLOT], storage=storage,
                 stray_keys=fixed, resident_bytes=[storage['resident_bytes'], storage['resident_limit']])
    proof['bytes'] = [proof['bytes'][0], len(final)]
    return final, proof
