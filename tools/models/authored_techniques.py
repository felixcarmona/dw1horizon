"""Eased final-rig technique keys with delayed source follow-through."""
import copy
import math

import animsheet
import mmd
import motionstorage
from motiontailspace import interpolate_pose
from tools.models import clip_repair
from tools.models.authored_battle import _clean
from tools.models.battle_finishes import _ground_frames
from tools.models.field_animations import quadruped as q
from tools.models.field_animations import native_battle

PROFILES = {241: {slot: dict(factor=1, final_frames=26, source_ticks=27,
                                grounded_feet=(21, 24)) for slot in (46, 47, 48, 56)},
            232: {47: dict(factor=1, mix=.25, source_ticks=31,
                                tolerance=5, ops=[dict(op='wave', bone=17, axis='x', deg=-6, cycles=1,
                                          phase=.15, ticks=[0, 3, 27, 30])], floor_offset=1),
                  54: dict(factor=1.4, mix=.12, source_ticks=45, tolerance=5)},
            242: {55: dict(factor=1.4, mix=.12, source_ticks=51, tolerance=5,
                           final_frames=107, cast_staff=True, support_feet=(21, 24))},
            333: {52: dict(factor=1, mix=.25, source_ticks=61, tolerance=5,
                           ops=[{'op': 'wave', 'bone': 6, 'axis': 'x', 'deg': 34, 'cycles': 1, 'phase': 0.25, 'ticks': [0, 3, 41, 44]}, {'op': 'wave', 'bone': 7, 'axis': 'x', 'deg': -34, 'cycles': 1, 'phase': 0.25, 'ticks': [0, 3, 41, 44]}], support_feet=(14, 17)),
                  54: dict(factor=1.2, mix=.25, source_ticks=37, tolerance=5,
                           ops=[dict(op='smooth', bone=16, passes=1),
                                dict(op='smooth', bone=17, passes=1)],
                           support_feet=(14, 17))}}


def author(data, skeleton, sid, raw):
    if sid == 241:
        from tools.models import wizardmon_cast
        return wizardmon_cast.author(data, skeleton, PROFILES[sid])
    nb = len(skeleton)
    mmd.exe().add_type(9400, skeleton)
    model, source = [mmd.MMD.parse(blob, nb) for blob in (data, raw)]
    model.type = 9400
    local = {b: [v[:3] for v in model.tmd.obj_verts(o)]
             for b, (o, _) in enumerate(skeleton) if o >= 0}
    children = {b: [i for i, (_, p) in enumerate(skeleton) if p == b] for b in range(nb)}
    delayed = {b: 1 + b % 3 for b in range(3, nb) if len(children[b]) <= 1}
    times = [0, .12, .28, .48, .66, .82, 1]

    def floor(pose):
        pose = copy.deepcopy(pose)
        pose[0] = [4096]*3 + [0]*6
        world = mmd.bone_matrices(model, pose)
        return max(sum(world[b][1][j] * v[j] for j in range(3)) + world[b][1][3]
                   for b in local for v in local[b])

    for slot, profile in PROFILES[sid].items():
        original, _, events = animsheet.slot_frames(model, nb, slot)
        source_frames = animsheet.slot_frames(source, nb, slot)[0]
        n = math.floor((len(original)-1) * profile['factor']) + 1
        duration = n-1
        keys = [copy.deepcopy(original[round(u*(len(original)-1))]) for u in times]
        for previous, current in zip(keys, keys[1:]):
            for b in range(1, nb):
                current[b][3:6] = [round(v) for v in mmd.matrix_euler(
                    mmd.rot_matrix(*current[b][3:6]), previous[b][3:6])]

        def at(tick, bone):
            u = max(0, min(1, tick/duration))
            i = next((i for i in range(len(times)-1) if times[i] <= u <= times[i+1]), len(times)-2)
            return interpolate_pose(keys[i], keys[i+1],
                                    round(q.smooth((u-times[i])/(times[i+1]-times[i]))*4096))[bone]

        frames = []
        for tick in range(n):
            u = tick/duration
            envelope = math.sin(math.pi*u)**2
            pose = [at(tick-delayed.get(b, 0)*math.sin(math.pi*u), b) for b in range(nb)]
            reference = source_frames[round(u*(len(source_frames)-1))]
            for b in delayed:
                for axis in range(3, 6):
                    difference = (reference[b][axis]-pose[b][axis]+2048) % 4096-2048
                    pose[b][axis] += round(difference * profile['mix'] * envelope)
                pose[b][3] += round(q.DEG * envelope * math.sin((tick-delayed[b])*.42))
            pose[0] = [4096]*3 + [0]*6
            pose[1][7] -= math.ceil(floor(pose)+2)
            frames.append(pose)
        model.anims.table[slot] = len(model.anims.anims)
        model.anims.anims.append(mmd.encode_anim(
            frames, nb, None, native_battle.scaled_events(events, len(original), n), tol=2, repeats=False))
        frames, loop, shifted_events = animsheet.slot_frames(model, nb, slot)
        frames = copy.deepcopy(frames)
        _ground_frames(frames, floor)
        model.anims.table[slot] = len(model.anims.anims)
        model.anims.anims.append(mmd.encode_anim(frames, nb, loop, shifted_events, tol=1, repeats=False))
        if profile.get('ops'):
            frames, loop, shifted_events = animsheet.slot_frames(model, nb, slot)
            frames = clip_repair.apply_ops(copy.deepcopy(frames), [p for _, p in skeleton], profile['ops'])
            _ground_frames(frames, floor)
            for pose in frames:
                pose[1][7] += profile.get('floor_offset', 0)
            model.anims.table[slot] = len(model.anims.anims)
            model.anims.anims.append(mmd.encode_anim(
                frames, nb, loop, shifted_events, tol={1: 0, None: 1}, repeats=False))
        if profile.get('tolerance'):
            frames, loop, shifted_events = animsheet.slot_frames(model, nb, slot)
            model.anims.table[slot] = len(model.anims.anims)
            model.anims.anims.append(mmd.encode_anim(
                frames, nb, loop, shifted_events,
                tol={0: 0, 1: 0, None: profile['tolerance']}, repeats=False))
    output = _clean(model)
    for slot, profile in PROFILES[sid].items():
        if profile.get('cast_staff'):
            from tools.models.sorcermon_cast import repair
            output = repair(output, skeleton, slot, profile['final_frames'])
        if profile.get('support_feet'):
            from tools.models.battle_support import fit
            output = fit(output, skeleton, slot, profile['support_feet'], data)
    return output


def build(data, skeleton, sid, context):
    profiles = PROFILES[sid]
    raw, _ = native_battle.apply(data, context, profiles,
                                ticks={str(s): p['source_ticks'] for s, p in profiles.items()})
    if sid == 241:
        raw, _ = native_battle.compact(raw, len(skeleton), dict(tol=5))
    if sid == 242:
        raw, _ = native_battle.compact(raw, len(skeleton), dict(tol=5, slot_tol={'19': 2}))
    if sid == 333:
        raw, _ = native_battle.compact(raw, len(skeleton), dict(tol=5, preserve_field=True))
    output = author(data, skeleton, sid, raw)
    return output, dict(slots=sorted(profiles), storage=motionstorage.require(output, len(skeleton)))
