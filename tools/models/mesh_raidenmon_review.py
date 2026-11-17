"""Exhaustive Raidenmon-only evidence with a checked PSX-rule rasterizer.

The native helper accelerates the existing orthographic psx_blend rules; it is
not a runtime GPU emulator. The Python reference remains the equivalence oracle.
"""
import ctypes
import hashlib
import math
from pathlib import Path
import subprocess
import tempfile

import numpy as np
from tools.models import meshcheck as MC


class Renderer:
    def __init__(self, model):
        self.model = model
        source = Path(__file__).with_name('mesh_raidenmon_render.cpp')
        digest = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
        library = Path(tempfile.gettempdir()) / f'raidenmon-render-{digest}.so'
        if not library.exists():
            # Each process compiles to a separate temporary target before the
            # atomic install, allowing parallel evidence workers to start.
            import os
            target = library.with_suffix(f'.{os.getpid()}.so')
            subprocess.run(['c++', '-O3', '-shared', '-fPIC', '-std=c++17', '-ffp-contract=off',
                            str(source), '-o', str(target)], check=True)
            target.replace(library)
        self.library = ctypes.CDLL(str(library))
        self.call = self.library.raiden_render
        pointer = ctypes.c_void_p
        self.call.argtypes = [pointer, pointer, pointer, pointer, ctypes.c_int,
                              pointer, ctypes.c_int, ctypes.c_int, pointer, ctypes.c_int,
                              ctypes.c_double, ctypes.c_double, ctypes.c_double,
                              ctypes.c_double, ctypes.c_int, pointer]
        self.call.restype = None
        groups, uv, colors = {}, [], []
        for k, tri in enumerate(model.tris):
            groups.setdefault(tri[:3], []).append(k)
            d = model.m.tmd.objects[tri[1]].prims[tri[2]].decode()
            uv.append(tri[4] if tri[4] is not None else [(0, 0)]*3)
            cs = d['colors']
            colors.append([cs[min(d['verts'].index(vi), len(cs)-1)][:3] for vi in tri[3]]
                          if cs else [(0, 0, 0)]*3)
        packets = []
        for (_, oi, pi), indices in groups.items():
            d = model.m.tmd.objects[oi].prims[pi].decode()
            packets.append([indices[0], indices[1] if len(indices) == 2 else -1,
                            bool(d['mode'] & 2), ((d['tsb'] or 0) >> 5) & 3,
                            model.tris[indices[0]][4] is not None,
                            model.tris[indices[0]][5] or 0])
        self.packets = np.ascontiguousarray(packets, dtype=np.int32)
        self.uv = np.ascontiguousarray(uv, dtype=np.float64)
        self.colors = np.ascontiguousarray(colors, dtype=np.float64)
        self.texture = np.ascontiguousarray(model.tex[0], dtype=np.uint8)
        self.palettes = np.ascontiguousarray(model.tex[1], dtype=np.uint16)

    def render(self, yaw=0, pitch=0, size=128, frame=None, pose=None, depth_offset=0):
        m = self.model
        xyz = m.tri_array(m.world(m.rest() if pose is None else pose))
        points = np.ascontiguousarray(MC._rotate(xyz, yaw, pitch), dtype=np.float64)
        if frame is None:
            low, high = points[..., :2].reshape(-1, 2).min(0), points[..., :2].reshape(-1, 2).max(0)
            scale = (size-24)/max(high-low)
            frame = scale, size/2-(low+high)/2*scale
        scale, offset = frame
        output = np.empty((size, size, 3), np.uint8)
        def address(a):
            return a.ctypes.data
        self.call(address(points), address(self.uv), address(self.colors), address(self.packets),
                  len(self.packets), address(self.texture), self.texture.shape[1], self.texture.shape[0],
                  address(self.palettes), self.palettes.shape[1], scale, *offset,
                  depth_offset, size, address(output))
        return output, frame


def clip_evidence(job):
    """Eight fixed-camera views at every decoded frame, both OT-bin phases."""
    import json
    from tools.models.mesh_round4 import load
    before, after, out, slot, size = job
    models = [load(Path(folder), 336) for folder in (before, after)]
    renderers = [Renderer(m) for m in models]
    poses = [m.poses(slot, 6000) for m in models]
    if len(poses[0]) != len(poses[1]) or len(poses[0]) >= 6000:
        raise ValueError('render coverage requires identical, fully decoded clips')
    # The diagnostic camera tracks only the common root translation. Keep the
    # complete action's rotation and use a single common scale across the clip.
    for stream in poses:
        for pose in stream:
            pose[0][6:9] = [0, 0, 0]
    images = np.empty((4, 8, len(poses[0]), size, size, 3), dtype=np.uint8)
    frames, rows = [], []
    for view in range(8):
        yaw, pitch = view*math.pi/4, math.pi/6
        points = np.concatenate([MC._rotate(m.tri_array(m.world(p)), yaw, pitch)[..., :2].reshape(-1, 2)
                                 for m, ps in zip(models, poses) for p in ps])
        lo, hi = points.min(0), points.max(0)
        scale = (size-24)/max(hi-lo)
        frame = scale, size/2-(lo+hi)/2*scale
        frames.append([float(scale), frame[1].tolist()])
        for tick in range(len(poses[0])):
            for stage, renderer in enumerate(renderers):
                for phase in (0, 1):
                    images[stage*2+phase, view, tick] = renderer.render(
                        yaw, pitch, size=size, frame=frame, pose=poses[stage][tick], depth_offset=phase*2)[0]
            a, ap, b, bp = images[:, view, tick]
            row = dict(slot=slot, tick=tick, view=view,
                       changed_pixels=int(np.any(a != b, axis=2).sum()),
                       before_bin_phase_pixels=int(np.any(a != ap, axis=2).sum()),
                       after_bin_phase_pixels=int(np.any(b != bp, axis=2).sum()))
            if tick:
                row['before_temporal_pixels'] = int(np.any(a != images[0, view, tick-1], axis=2).sum())
                row['after_temporal_pixels'] = int(np.any(b != images[2, view, tick-1], axis=2).sum())
            rows.append(row)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out/f'{slot}.npz', images=images)
    (out/f'{slot}.json').write_text(json.dumps(dict(slot=slot, frames=frames, rows=rows))+'\n')
    print(f'rendered slot {slot}: {len(poses[0])} frames x 8 views x 4 states', flush=True)
    return rows


def render_all(before, after, out, jobs=4, size=128):
    import json
    from concurrent.futures import ProcessPoolExecutor
    from tools.models.mesh_round4 import load
    slots = load(Path(before), 336).slots()
    tasks = [(str(before), str(after), str(out), slot, size) for slot in slots]
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        rows = [r for batch in pool.map(clip_evidence, tasks) for r in batch]
    report = dict(species=336, slots=len(slots), frames=len(rows)//8,
                  views=8, size=size, rendered_images=4*len(rows),
                  root_translation_camera_tracking=True, common_fixed_frame_per_clip_view=True,
                  rows=rows)
    for key in ('changed_pixels', 'before_bin_phase_pixels', 'after_bin_phase_pixels',
                'before_temporal_pixels', 'after_temporal_pixels'):
        report[key] = sum(r.get(key, 0) for r in rows)
    (Path(out)/'metrics.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


def reference_equivalence(folder):
    """Compare every clip plus the worst arm/plate poses to the Python oracle."""
    from tools.models.mesh_round4 import load
    from tools.models import psx_blend
    m = load(Path(folder), 336)
    renderer, rows = Renderer(m), []
    cases = [(slot, 0, slot % 8, (slot % 2)*2) for slot in m.slots()]
    cases += [(slot, tick, view, phase) for slot, tick in ((43, 36), (43, 39), (61, 10), (9, 41))
              for view in range(8) for phase in (0, 2)]
    for slot, tick, view, phase in cases:
        pose = m.poses(slot, 6000)[tick]
        args = dict(yaw=view*math.pi/4, pitch=math.pi/6, size=128, pose=pose, depth_offset=phase)
        image, frame = renderer.render(**args)
        expected, _ = psx_blend.render(m, frame=frame, **args)
        different = int(np.any(image != expected, axis=2).sum())
        rows.append(dict(slot=slot, tick=tick, view=view, phase=phase, different_pixels=different))
    return dict(cases=len(rows), different_pixels=sum(r['different_pixels'] for r in rows), rows=rows)


def main():
    import argparse
    import json
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('before', type=Path)
    p.add_argument('after', type=Path)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--jobs', type=int, default=4)
    p.add_argument('--size', type=int, default=128)
    p.add_argument('--reference-only', action='store_true')
    a = p.parse_args()
    if a.reference_only:
        report = {stage: reference_equivalence(folder) for stage, folder in
                  (('before', a.before), ('after', a.after))}
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(report, indent=2)+'\n')
        if any(r['different_pixels'] for r in report.values()):
            raise SystemExit('native/reference rasterizer mismatch')
    else:
        if a.jobs <= 0 or a.size < 32:
            p.error('jobs must be positive and size at least 32')
        render_all(a.before, a.after, a.out, a.jobs, a.size)


if __name__ == '__main__':
    main()
