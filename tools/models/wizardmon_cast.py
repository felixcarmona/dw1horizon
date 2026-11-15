"""A planted casting gesture shared by Wizardmon's four matching source spells."""
import copy
import math

import animsheet
import mmd
from tools.models import clip_repair
from tools.models.authored_battle import _clean
from tools.models.field_animations import quadruped as q
from tools.models.field_animations import wizardmon_native as wizard, native_battle

FRAMES = 26
SLOTS = (46, 47, 48, 56)


def _attachment(model, skeleton, rest, world, bone, top=False):
    points = [v[:3] for v in model.tmd.obj_verts(skeleton[bone][0])]
    rotation = [row[:3] for row in world[bone][:3]]
    values = [q.mv(rotation, v)[1] for v in points]
    level = min(values) if top else max(values)
    local = q.mv(q.tr(rotation), [0, level, 0])
    anchor = q.add(rest[bone][6:9], q.mv(mmd.rot_matrix(*rest[bone][3:6]), local))
    return local, anchor


def _keep_attachment(pose, bone, attachment):
    local, anchor = attachment
    pose[bone][6:9] = [round(v) for v in q.sub(
        anchor, q.mv(mmd.rot_matrix(*pose[bone][3:6]), local))]


def author(data, skeleton, slots=SLOTS):
    if tuple(slots) != SLOTS:
        raise ValueError('unreviewed Wizardmon spell family')
    nb = len(skeleton)
    mmd.exe().add_type(9400, skeleton)
    model = mmd.MMD.parse(data, nb)
    model.type = 9400
    rest = copy.deepcopy(animsheet.slot_frames(model, nb, 0)[0][0])
    rest[0] = [4096]*3 + [0]*6
    world = mmd.bone_matrices(model, rest)
    parents = [p for _, p in skeleton]
    profile = dict(legs={'L': (19, 20, 21, 1, False), 'R': (22, 23, 24, -1, False)},
                   pole={False: [0, 0, -1]}, pole_world=True, rest_plane=True)
    rig = q.Rig(model, skeleton, profile)
    head = _attachment(model, skeleton, rest, world, 3)
    cape = _attachment(model, skeleton, rest, world, 11, top=True)
    frames, history = [], {}
    for tick in range(FRAMES):
        u = tick/(FRAMES-1)
        envelope = math.sin(math.pi*u)**2
        acting = envelope*math.sin(2*math.pi*u)
        pose = copy.deepcopy(rest)
        pose[1][6] += round(30*acting)
        pose[1][7] += round(20*acting*acting + 2*envelope)
        turns = [(2, 'x', 14*acting), (2, 'z', -3*acting),
                 (3, 'x', 40*envelope*math.sin(2*math.pi*(u-.06))),
                 (3, 'z', 25*envelope*math.sin(2*math.pi*(u-.10))),
                 (4, 'z', -55*envelope), (4, 'x', 20*acting),
                 (7, 'z', .6*55*envelope), (7, 'x', -55*acting),
                 (8, 'x', 2*55*envelope), (9, 'x', -1.7*55*envelope),
                 (9, 'y', 12*acting)]
        for bone, axis, degrees in turns:
            pose = clip_repair.apply_ops([pose], parents,
                                         [dict(op='turn', bone=bone, axis=axis, deg=degrees)])[0]
        _keep_attachment(pose, 3, head)
        for name, (up, lo, foot, _, _) in profile['legs'].items():
            anchor = [world[foot][i][3] for i in range(3)]
            pole = [world[lo][i][3]-(world[up][i][3]+world[foot][i][3])/2 for i in range(3)]
            if q.norm(pole) < .1:
                pole = [0, 0, -1]
            rotation, short = rig.solve(pose, name, anchor, history, pole=pole)
            q.set_rot(pose, foot, q.mul(q.tr(rotation), [row[:3] for row in world[foot][:3]]), history)
            if short > 3:
                raise ValueError(('unreachable casting support', short))
        frames.append(pose)
    frames = wizard.follow(frames, None, skeleton, rest)
    for tick, pose in enumerate(frames):
        u = tick/(FRAMES-1)
        envelope = math.sin(math.pi*u)**2
        degrees = 70*envelope*math.sin(2*math.pi*(u-.08))
        pose = clip_repair.apply_ops([pose], parents,
                                     [dict(op='turn', bone=11, axis='x', deg=degrees)])[0]
        _keep_attachment(pose, 11, cape)
        pose[1][7] -= 1
        frames[tick] = pose
    frames = [[[round(v) for v in bone] for bone in pose] for pose in frames]
    # Quantize one shared gesture, then give each spell its own unchanged sound cues.
    leader = copy.deepcopy(model)
    original, _, events = animsheet.slot_frames(model, nb, SLOTS[0])
    leader.anims.table[SLOTS[0]] = len(leader.anims.anims)
    leader.anims.anims.append(mmd.encode_anim(
        frames, nb, None, native_battle.scaled_events(events, len(original), FRAMES),
        tol={0: 0, 1: 0, None: 5}, repeats=False))
    master = mmd.MMD.parse(_clean(leader), nb)
    shared = copy.deepcopy(animsheet.slot_frames(master, nb, SLOTS[0])[0])
    for pose in shared:
        pose[1][7] -= 1
    for slot in SLOTS:
        original, _, events = animsheet.slot_frames(model, nb, slot)
        model.anims.table[slot] = len(model.anims.anims)
        model.anims.anims.append(mmd.encode_anim(
            shared, nb, None, native_battle.scaled_events(events, len(original), FRAMES),
            tol={0: 0, 1: 1, None: 5}, repeats=False))
    return _clean(model)
