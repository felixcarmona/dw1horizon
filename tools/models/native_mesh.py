"""Frozen source mesh and first pose for binding onto a native DW1 skeleton.

Player replay uses only the standard library. The final model delta supplies
the reviewed binding and native animation programs; this source has no motion.
"""
from pathlib import Path

import animsheet
import dw3mmd
import mmd
import mmdport


def build(spec, log=print):
    model = dw3mmd.load(spec['dw3'], height=spec['height'],
                        maxp=15, quad_angle=spec['quad_angle'],
                        normal_angle=spec['normal_angle'], log=log)
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
    return source.build(), mmdport.build_tim(model.idx, model.pals), rig


def write(spec, out, log=print):
    model, texture, rig = build(spec, log)
    stem = Path(out) / spec['name']
    stem.parent.mkdir(parents=True, exist_ok=True)
    stem.with_suffix('.MMD').write_bytes(model)
    stem.with_suffix('.TIM').write_bytes(texture)
    return dict(skeleton=rig)
