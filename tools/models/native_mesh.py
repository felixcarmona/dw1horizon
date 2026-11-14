"""Frozen source mesh and first pose for binding onto a native DW1 skeleton.

Player replay uses only the standard library. The final model delta supplies
the reviewed binding and native animation programs; this source has no motion.

A `native-battle-source-v1` spec (battle_source) makes the same source with the
source game's own clips in DW1 battle slots, the frozen clip choices of the spec
(import_batch.analyse_clips_dw3's, made once): its mesh is byte for byte the
motionless source's, slot 0 is the same one-tick bind pose. A species bound
offline (content/models/imports/bound-battle.json) plays them on its native rig
(tools/models/field_animations/bound_battle.py).
"""
from pathlib import Path

import animsheet
import dw3mmd
import mmd
import mmdport

MESH = ('dw3', 'type', 'height', 'animation', 'frame', 'quad_angle', 'normal_angle')


def _load(spec, log):
    return dw3mmd.load(spec['dw3'], height=spec['height'],
                       maxp=15, quad_angle=spec['quad_angle'],
                       normal_angle=spec['normal_angle'], log=log)


def _source(spec, log):
    """(source MMD with the one-tick bind pose, the dw3 model, rig, scale factor)."""
    model = _load(spec, log)
    source = mmdport.base_mmd(model, spec['type'], log)
    frames = model.anims[spec['animation']].frames
    first = frames[spec['frame']]
    animation = mmd.Anim()
    animation.has_scale = True
    animation.frame_count = 1
    animation.pose = [
        [round(v * 4096) for v in scale]
        + [round(v) for v in mmd.matrix_euler(mmd.quat_matrix(quat))]
        + [round(v) for v in translation]
        for quat, translation, scale in first
    ]
    animation.instrs = [dict(op='end')]
    source.anims.anims = [animation]
    source.anims.table = [0]
    rig = mmdport.skeleton(model)
    pose = [[4096, 4096, 4096, 0, 0, 0, 0, 0, 0]] + animation.pose
    ys = [v[1] for triangle in animsheet.world_tris(source, pose, rig) for v in triangle[0]]
    factor = spec['height'] / (max(ys) - min(ys))
    source.tmd.verts = [tuple([round(v * factor) for v in p[:3]] + [p[3]])
                        for p in source.tmd.verts]
    for bone in animation.pose:
        bone[-3:] = [round(v * factor) for v in bone[-3:]]
    return source, model, rig, factor


def build(spec, log=print):
    source, model, rig, _ = _source(spec, log)
    return source.build(), mmdport.build_tim(model.idx, model.pals), rig


def build_battle(spec, work, log=print):
    """The motionless source with the spec's clips (`clips`: {slot: mmdport.clip arguments}) in their slots -> (MMD, TIM,
    rig). `work`: a folder for the intermediate glTF."""
    import import_batch
    source, model, rig, factor = _source(spec, log)
    import_batch.dw3_getup(model)            # the fall (the get-up reversed), as the importer finds it
    clips, maps = {}, {}
    for slot, args in spec['clips'].items():
        args = dict(args)
        name = args.pop('anim')
        made = mmdport.clip(model, name, **args)
        made['frames'] = [[(q, tuple(v * factor for v in t), s) for q, t, s in f] for f in made['frames']]
        clips[f'{name}@{slot}'], maps[f'{name}@{slot}'] = made, int(slot, 16)
    for bone in model.bones:
        bone['offset'] = [v * factor for v in bone['offset']]
    bind = source.anims.anims[0]
    source.anims.table, source.anims.anims = [None] * (0x2E + 15), []
    Path(work).mkdir(parents=True, exist_ok=True)
    made, _ = mmdport.import_clips(source, model, clips, maps, str(Path(work) / f'{spec["name"]}.gltf'), tol=1,
                                   log=lambda *a: None)
    made.anims.table[0] = len(made.anims.anims)
    made.anims.anims.append(bind)
    return made.build(), mmdport.build_tim(model.idx, model.pals), rig


def write(spec, out, log=print):
    if spec.get('format') == 'native-battle-source-v1':
        model, texture, rig = build_battle(spec, out, log)
    else:
        model, texture, rig = build(spec, log)
    stem = Path(out) / spec['name']
    stem.parent.mkdir(parents=True, exist_ok=True)
    stem.with_suffix('.MMD').write_bytes(model)
    stem.with_suffix('.TIM').write_bytes(texture)
    return dict(skeleton=rig)
