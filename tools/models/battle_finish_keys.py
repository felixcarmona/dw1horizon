"""Eased final-rig victory keys with a planted support foot."""
import copy
import math
import mmd
import animsheet
import motioncyclelayer
from motiontailspace import interpolate_pose
from tools.models.field_animations import quadruped as q
from tools.models.field_animations.native_battle import scaled_events

def author_keys(data, sk, sid, raw, slots, factor=1.4, mix=0.12):
    """Ease the gesture, delay the extremities, and solve the weight-bearing leg."""
    nb = len(sk)
    mmd.exe().add_type(9400, sk)
    m = mmd.MMD.parse(data, nb)
    m.type = 9400
    r = mmd.MMD.parse(raw, nb)
    out = copy.deepcopy(m)
    local = {b: [v[:3] for v in m.tmd.obj_verts(o)] for b, (o, _) in enumerate(sk) if o >= 0}
    children = {b: [i for i, (_, p) in enumerate(sk) if p == b] for b in range(nb)}
    delayed = {b: 1 + b % 3 for b in range(3, nb) if not children[b] or len(children[b]) == 1}
    times = [0, 0.12, 0.28, 0.48, 0.66, 0.82, 1]
    target_floor = 0.0
    if sid == 236:
        levels = []
        for pose in animsheet.slot_frames(m, nb, 0)[0]:
            world = mmd.bone_matrices(m, pose)
            levels.append(max(sum(world[b][1][j] * v[j] for j in range(3)) + world[b][1][3]
                              for b in local for v in local[b]))
        target_floor = sum(levels) / len(levels)
    end = None
    for slot in slots:
        original, loop, events = animsheet.slot_frames(m, nb, slot)
        source = animsheet.slot_frames(r, nb, slot)[0]
        n = math.floor((len(original) - 1) * factor) + 1
        T = n - 1
        samples = times
        keys = [copy.deepcopy(original[round(u * (len(original) - 1))]) for u in samples]
        for prev, cur in zip(keys, keys[1:]):
            for b in range(1, nb):
                cur[b][3:6] = [round(v) for v in mmd.matrix_euler(mmd.rot_matrix(*cur[b][3:6]), prev[b][3:6])]

        def at(t, b):
            u = max(0, min(1, t / T))
            i = next((i for i in range(len(times) - 1) if times[i] <= u <= times[i + 1]), len(times) - 2)
            return interpolate_pose(keys[i], keys[i + 1], round(q.smooth((u - times[i]) / (times[i + 1] - times[i])) * 4096))[b]
        frames = []
        for t in range(n):
            u = t / T
            env = math.sin(math.pi * u) ** 2
            p = [at(t - delayed.get(b, 0) * math.sin(math.pi * u), b) for b in range(nb)]
            src = source[round(u * (len(source) - 1))]
            for b in delayed:
                for ax in range(3, 6):
                    d = (src[b][ax] - p[b][ax] + 2048) % 4096 - 2048
                    p[b][ax] += round(d * mix * env)
                p[b][3] += round(1.0 * q.DEG * env * math.sin((t - delayed[b]) * 0.42))
            if sid == 236:
                p[6][5] -= round(12 * q.DEG * env)
                p[9][5] += round(12 * q.DEG * env)
            p[0] = [4096] * 3 + [0] * 6
            w = mmd.bone_matrices(m, p)
            low = max((sum((w[b][1][j] * v[j] for j in range(3))) + w[b][1][3] for b in local for v in local[b]))
            p[1][7] -= math.ceil(low - target_floor + 2)
            frames.append(p)
        if sid == 292 and slot == 42:
            from tools.models import clip_repair
            from tools.models.battle_finishes import _ground_frames
            # The skull hand answers the central head, then settles behind it.
            frames = clip_repair.apply_ops(frames, [parent for _, parent in sk], [
                dict(op='wave', bone=14, axis='z', deg=55, cycles=1, phase=0,
                     ticks=[0, 4, n-5, n-1]),
                dict(op='wave', bone=14, axis='x', deg=30, cycles=1, phase=.25,
                     ticks=[0, 4, n-5, n-1])])

            def floor(pose):
                pose = copy.deepcopy(pose)
                pose[0] = [4096] * 3 + [0] * 6
                world = mmd.bone_matrices(m, pose)
                return max(sum(world[b][1][j] * v[j] for j in range(3)) + world[b][1][3]
                           for b in local for v in local[b])

            _ground_frames(frames, floor)
        if sid == 402 and slot == 42:
            ref = copy.deepcopy(frames[0])
            m.anims.anims[m.anims.table[0]] = mmd.encode_anim([ref, ref], nb)
            profile = dict(legs={'L': (13, 14, 15, 1, False)}, pole={False: [0, 0, -1]}, pole_world=True)
            rig = q.Rig(m, sk, profile)
            W = mmd.bone_matrices(m, ref)
            anchor = [W[15][i][3] for i in range(3)]
            pole = [W[14][i][3] - (W[13][i][3] + W[15][i][3]) / 2 for i in range(3)]
            # Compress the knee before the leg reaches full extension; the foot stays planted.
            for p in frames:
                world = mmd.bone_matrices(m, p)
                shoulder = [world[13][i][3] for i in range(3)]
                reach = q.norm(rig.link(p, 14)[0]) + q.norm(rig.link(p, 15)[0]) - 4
                horizontal = math.hypot(anchor[0] - shoulder[0], anchor[2] - shoulder[2])
                if horizontal >= reach:
                    raise ValueError('support foot is beyond horizontal reach')
                level = anchor[1] - math.sqrt(reach * reach - horizontal * horizontal)
                gap = level - shoulder[1]
                p[1][7] += round((gap + math.sqrt(gap * gap + 16)) / 2)
                rotation, short = rig.solve(p, 'L', anchor, {}, pole=pole)
                if short > 1:
                    raise ValueError(('unreached support', short))
                q.set_rot(p, 15, q.mul(q.tr(rotation), [row[:3] for row in W[15][:3]]), {})
                world = mmd.bone_matrices(m, p)
                low = max((sum((world[b][1][j] * v[j] for j in range(3))) + world[b][1][3] for b in local for v in local[b]))
                p[1][7] -= math.ceil(low + 2)
        if slot == 44 and end is not None:
            frames[0] = copy.deepcopy(end)
        if slot == 43:
            end = copy.deepcopy(frames[-1])
        out.anims.table[slot] = len(out.anims.anims)
        out.anims.anims.append(mmd.encode_anim(frames, nb, None, scaled_events(events, len(original), n), tol=0 if sid in (198, 402) else 2, repeats=False))
    used = sorted(set((i for i in out.anims.table if i is not None)))
    ren = {a: b for b, a in enumerate(used)}
    out.anims.anims = [out.anims.anims[i] for i in used]
    out.anims.table = [ren.get(i) for i in out.anims.table]
    out.anims.anims, out.anims.table = motioncyclelayer.share_identical_streams(out.anims.anims, out.anims.table)
    return out.build()
