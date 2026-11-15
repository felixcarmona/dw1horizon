"""Authored faint/recovery keys on reviewed final native bindings.

The unmodified final-rig clip supplies the support poses and sound clock; the
retargeted source supplies the open-arm preparation. No source-disc access.
Field programs, geometry and unrelated programs are preserved exactly.
"""
import copy
import hashlib
import math

import animsheet
import mmd
import motioncyclelayer
import motionstorage
import retarget
from motiontailspace import interpolate_pose
from tools.models import clip_repair
from tools.models.field_animations import quadruped as q
from tools.models.field_animations.native_battle import scaled_events

SLOTS = {260: (43, 44), 270: (43,), 402: (42,)}


def _ground_frames(frames, floor):
    """Fit carrier keys to this rig's display floor, preferring close contact.

    Six units is the preferred clearance of the reviewed clips, not a limit on
    the floor curvature a different binding may produce. If that band cannot
    be met, lift only as far as the actual mesh at each blend requires.
    """
    # Fit the carrier against every display blend, without lifting both ends
    # by an entire interval's worst excess (which would leave a floating hold).
    constraints = []
    heights = [float(pose[1][7]) for pose in frames]
    flat = copy.deepcopy(frames)
    for pose in flat:
        pose[1][7] = 0
    for i, (first, second) in enumerate(zip(flat, flat[1:])):
        for alpha in (0, 1365, 2730, 4096):
            weight = alpha / 4096
            level = floor(interpolate_pose(first, second, alpha))
            constraints.append((i, 1-weight, weight, -6-level, -level))
    for iteration in range(1000):
        violation = 0.
        for i, first, second, low, high in constraints:
            height = first*heights[i] + second*heights[i+1]
            error = min(high, max(low, height)) - height
            violation = max(violation, abs(error))
            correction = error / (first*first + second*second)
            heights[i] += correction*first
            heights[i+1] += correction*second
        if violation < .05:
            break
    if violation > .25:
        # A changed rig can have more floor curvature between keys than the
        # preferred contact band permits. Plant against its measured floor:
        # project only the remaining penetrations, sharing the necessary lift
        # between the two carrier keys. Every correction lifts both ends, so
        # it preserves all earlier floor constraints in this sweep.
        for i, first, second, low, high in constraints:
            height = first*heights[i] + second*heights[i+1]
            lift = max(0., height - high) / (first*first + second*second)
            heights[i] -= lift*first
            heights[i+1] -= lift*second
    for pose, height in zip(frames, heights):
        pose[1][7] = round(height)


def author(data, sk, sid, raw):
    """Key the final rig from its weight-bearing poses and the source arm gesture.

 Eased compression precedes the fall. Delayed head, jaw, arms and tail react
 independently; folded cannons and toes let the jaw/chest bear the landing.
 Recovery transfers weight from the arms to planted feet. The original donor
 sounds keep their relative times, and only the selected slots are replaced.
 """
    if sid == 402:
        from tools.models.battle_finish_keys import author_keys
        return author_keys(data, sk, sid, raw, SLOTS[sid])
    if sid not in SLOTS:
        raise ValueError(f'No reviewed battle finish for species {sid}')
    nb = len(sk)
    mmd.exe().add_type(9400, sk)
    m = mmd.MMD.parse(data, nb)
    m.type = 9400
    r = mmd.MMD.parse(raw, nb)
    out = copy.deepcopy(m)
    legs = {260: ((21, 22, 23), (24, 25, 26)), 270: ((12, 13, 14), (16, 17, 18))}[sid]
    delays = {260: {3: 2, 4: 3, 5: 1, 6: 2, 11: 2, 12: 3, 18: 1, 19: 2, 20: 3}, 270: {3: 1, 4: 2, 5: 3, 7: 2, 8: 3, 9: 3}}[sid]
    arms = {260: (5, 6, 11, 12), 270: (3, 4, 5, 7, 8, 9)}[sid]
    local = {b: [v[:3] for v in m.tmd.obj_verts(o)] for b, (o, _) in enumerate(sk) if o >= 0}

    def floor(p, bones=None):
        p = copy.deepcopy(p)
        p[0] = [4096] * 3 + [0] * 6
        w = mmd.bone_matrices(m, p)
        return max((sum((w[b][1][j] * v[j] for j in range(3))) + w[b][1][3] for b in bones or local for v in local[b]))

    def ground(p):
        p[1][7] -= math.ceil(floor(p) + 2)
    fall_end = None
    for s in [43, 44] if sid != 270 else [43]:
        original, loop, events = animsheet.slot_frames(m, nb, s)
        source, _, _ = animsheet.slot_frames(r, nb, s)
        factor = 1.58 if sid == 260 and s == 43 else 1.4
        n = round((len(original) - 1) * factor) + 1
        T = n - 1
        keytimes = [0, 0.17, 0.36, 0.6, 0.74, 0.84, 1]
        samples = [0, 0.19, 0.38, 0.65, 0.8, 0.88, 1] if s == 43 else [0, 0.12, 0.3, 0.5, 0.68, 0.83, 1]
        keys = [copy.deepcopy(original[round(u * (len(original) - 1))]) for u in samples]
        # Choose continuous Euler representations before easing between keys.
        for previous, current in zip(keys, keys[1:]):
            for bone in range(1, nb):
                current[bone][3:6] = [round(v) for v in mmd.matrix_euler(mmd.rot_matrix(*current[bone][3:6]), previous[bone][3:6])]
        if s == 43:
            keys[4] = copy.deepcopy(keys[6])
            keys[5] = copy.deepcopy(keys[6])
            if sid == 260:
                keys[5][3][3] += round(3 * q.DEG)
            if sid == 270:
                keys[5][10][3] += round(1 * q.DEG)
        if s == 43:
            for b, sign in zip([legs[0][0], legs[1][0]], [1, -1]):
                keys[1][b][4] += round(sign * 4 * q.DEG)
        if sid == 260:
            for index, p in enumerate(keys):
                blend = q.smooth((keytimes[index] - 0.38) / 0.36) if s == 43 else 1 - q.smooth(keytimes[index] / 0.6)
                for elbow in (6, 12):
                    p[elbow][5] += round(24 * q.DEG * blend)
                for foot in (23, 26):
                    p[foot][5] -= round(7 * q.DEG * blend)

        def at(t, b):
            u = max(0, min(1, t / T))
            i = next((i for i in range(len(keytimes) - 1) if keytimes[i] <= u <= keytimes[i + 1]), len(keytimes) - 2)
            return interpolate_pose(keys[i], keys[i + 1], round(q.smooth((u - keytimes[i]) / (keytimes[i + 1] - keytimes[i])) * 4096))[b]
        frames = []
        for t in range(n):
            p = [at(t - delays.get(b, 0) * math.sin(math.pi * t / T), b) for b in range(nb)]
            env = math.sin(math.pi * t / T) ** 2
            for b in delays:
                p[b][3] += round(2 * q.DEG * env * math.sin((t - delays[b]) * 0.42))
            u = t / T
            mix = 0.16 * math.sin(math.pi * u) ** 2 * (1 - q.smooth((u - 0.55) / 0.18))
            rp = source[min(len(source) - 1, round(u * (len(source) - 1)))]
            for b in arms:
                current = mmd.rot_matrix(*p[b][3:6])
                target = mmd.rot_matrix(*rp[b][3:6])
                desired = q.mul(retarget.scale_rot(q.mul(target, q.tr(current)), mix), current)
                p[b][3:6] = [round(v) for v in mmd.matrix_euler(desired, p[b][3:6])]
            if sid == 260 and s == 43:
                wave = math.sin(2 * math.pi * u) * q.smooth(u / 0.1) * (1 - q.smooth((u - 0.35) / 0.25))
                for hip, knee, foot in legs:
                    p[hip][5] += round(40 * q.DEG * wave)
                    p[knee][5] -= round(80 * q.DEG * wave)
            if sid == 260:
                rw = mmd.bone_matrices(m, animsheet.slot_frames(m, nb, 0)[0][0])
                for b in (7, 8, 9, 10, 13, 14, 15, 16):
                    w = mmd.bone_matrices(m, p)
                    parent = sk[b][1]
                    q.set_rot(p, b, q.mul(q.tr([row[:3] for row in w[parent][:3]]), [row[:3] for row in rw[b][:3]]), {})
            p[0] = [4096] * 3 + [0] * 6
            ground(p)
            frames.append(p)
        if sid == 260:
            # Open the cannons away from the chest; both relax as the feet take weight.
            window = [0, 6, T, T] if s == 43 else [0, 0, 0, round(T * .6)]
            frames = clip_repair.apply_ops(frames, [parent for _, parent in sk], [
                dict(op='turn', bone=5, axis='z', deg=-10, ticks=window),
                dict(op='turn', bone=11, axis='z', deg=10, ticks=window)])
            for pose in frames:
                ground(pose)
        if s == 44 and fall_end:
            frames[0] = copy.deepcopy(fall_end)
        if s == 44:
            reference = copy.deepcopy(frames[-1])
            m.anims.anims[m.anims.table[0]] = mmd.encode_anim([reference, reference], nb)
            profile = dict(legs={f'L{i}': (*leg, 1, False) for i, leg in enumerate(legs)}, pole={False: [0, 0, -1]}, pole_world=True)
            rig = q.Rig(m, sk, profile)
            W = rig.still
            for t, p in enumerate(frames):
                if t < round(T * 0.6):
                    continue
                weight = q.smooth((t / T - 0.6) / 0.15)
                before = copy.deepcopy(p)
                for name, (hip, knee, foot, _, _) in profile['legs'].items():
                    anchor = [W[foot][i][3] for i in range(3)]
                    pole = [W[knee][i][3] - (W[hip][i][3] + W[foot][i][3]) / 2 for i in range(3)]
                    rotation, short = rig.solve(p, name, anchor, {}, pole=pole)
                    target = [row[:3] for row in W[foot][:3]]
                    q.set_rot(p, foot, q.mul(q.tr(rotation), target), {})
                frames[t] = interpolate_pose(before, p, round(weight * 4096))
                ground(frames[t])
        _ground_frames(frames, floor)
        if s == 43:
            fall_end = copy.deepcopy(frames[-1])
        out.anims.table[s] = len(out.anims.anims)
        out.anims.anims.append(mmd.encode_anim(frames, nb, None, scaled_events(events, len(original), n), tol=2, repeats=False))
    used = sorted(set((i for i in out.anims.table if i is not None)))
    ren = {old: new for new, old in enumerate(used)}
    out.anims.anims = [out.anims.anims[i] for i in used]
    out.anims.table = [ren.get(i) for i in out.anims.table]
    out.anims.anims, out.anims.table = motioncyclelayer.share_identical_streams(out.anims.anims, out.anims.table)
    return out.build()


def build(data, rig, sid, context):
    """Replay the keys after native binding and exact compaction."""
    from tools.models.field_animations import native_battle
    raw, _ = native_battle.apply(data, context, SLOTS[sid])
    result = author(data, rig, sid, raw)
    return result, dict(slots=list(SLOTS[sid]),
                        input_sha256=hashlib.sha256(data).hexdigest(),
                        reference_sha256=hashlib.sha256(raw).hexdigest(),
                        output_sha256=hashlib.sha256(result).hexdigest(),
                        storage=motionstorage.require(result, len(rig)))
