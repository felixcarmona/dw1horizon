"""Final-provider WarGreymon evidence; orthographic PSX rules, not GTE proof.

python3 -m tools.models.wargreymon_review build/wargreymon/before build/wargreymon/after --out shots
Both folders contain 373.MMD, 373.TIM and index.json (meshcheck format).
"""
import argparse
import copy
import json
import math
from pathlib import Path

import numpy as np
from tools.image import Image, ImageDraw, ImageFont
from tools.models import meshcheck as C, psx_blend as R, mesh_stability as S


def label(pixels, text):
    canvas = Image.new('RGB', (pixels.shape[1], pixels.shape[0]+28), '#182028')
    canvas.paste(Image.fromarray(pixels), (0, 28))
    ImageDraw.Draw(canvas).text((8, 4), text, fill='white', font=ImageFont.load_default(size=18))
    return np.asarray(canvas)


def shield_errors(model, pose, yaw, phase):
    _, frame, actual = R.render(model, yaw, math.pi/6, size=192, pose=pose,
                                 depth_offset=phase, return_ids=True)
    reference = C.render(model, model.tri_array(model.world(pose)), yaw, math.pi/6,
                         size=192, frame=frame)[4]
    obj = np.array([t[1] for t in model.tris]+[-1])
    target = np.isin(obj[reference], [18, 19])
    # The reported defect is inside the crest's central circle; retain a
    # separate, clearly scoped probe rather than counting shoulder contacts.
    matrices = model.matrices(pose)
    # Crest centre is about local Y=120 (the fan vertex at Y=85 sits above
    # it). Use bone space so final pool compaction cannot move the probe.
    centres = []
    for bone, x in ((19, 6), (20, -6)):
        centres.append((matrices[bone] @ [x, 120, 0, 1])[:3])
    spine = C._rotate(np.mean(centres, axis=0), yaw, math.pi/6)[:2]
    centre = spine*frame[0]+frame[1]
    yy, xx = np.mgrid[:192, :192]
    target &= (xx+.5-centre[0])**2+(yy+.5-centre[1])**2 < (25*frame[0])**2
    # Exclude raster-edge convention differences from the interior probe.
    padded = np.pad(target, 1)
    target &= np.logical_and.reduce([padded[y:y+192, x:x+192] for y in range(3) for x in range(3)])
    bad = target & np.isin(obj[actual], [0, 1])
    hits, counts = np.unique(actual[bad], return_counts=True)
    faces = {}
    for i, n in zip(hits, counts):
        key = str(tuple(model.tris[i][1:3]))
        faces[key] = faces.get(key, 0)+int(n)
    return int(bad.sum()), faces


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('before', type=Path); p.add_argument('after', type=Path)
    p.add_argument('--out', type=Path, default=Path('shots'))
    a = p.parse_args(); a.out.mkdir(exist_ok=True, parents=True)
    bones = json.loads((a.before/'index.json').read_text())['373']['bones']
    models = [C.Model((d/'373.MMD').read_bytes(), bones, (d/'373.TIM').read_bytes())
              for d in (a.before, a.after)]
    result = dict(cameras_degrees=[160, 180, 200], pitch_degrees=30,
                  note='all decoded ticks, eight views for flicker; central 25-unit crest radius, all slot-1 ticks, three views and four OT phases for shield pixels')
    slots = [s for s in models[0].slots() if s <= 4 or s >= 33]
    for name, model in zip(('before', 'after'), models):
        import coldsplit
        flicker = C.flicker(model, slots=slots)
        (a.out/f'wargreymon-{name}-stability.json').write_text(json.dumps(flicker, indent=2)+'\n')
        result[name] = dict(resident=len(coldsplit.split(model.m.build(), len(bones))[0]),
                            bent_quads=len(S.bent_quads(model.m)), clips={})
        for slot, row in flicker['clips'].items():
            result[name]['clips'][str(slot)] = dict(frames=row['frames'],
                opposing_half_ticks=sum(q['count'] for q in row['quad_facing']),
                glove_opposing_half_ticks=sum(q['count'] for q in row['quad_facing'] if q['bone'] in (7, 9)),
                facing_changes=row['facing_changes'], collapsed=len(row['collapsed_triangles']))
        pixels, maximum, faces = 0, 0, {}
        for pose in model.poses(1):
            for yaw in (160, 180, 200):
                for phase in range(4):
                    count, winners = shield_errors(model, pose, math.radians(yaw), phase)
                    pixels += count; maximum = max(maximum, count)
                    for key, n in winners.items():
                        faces[key] = faces.get(key, 0)+n
        result[name]['shield_wrong_torso_pixels'] = dict(total=pixels, maximum=maximum, faces=faces)
        print(name, result[name]['resident'], result[name]['shield_wrong_torso_pixels'], flush=True)
    for slot in (0, 1, 2, 3, 4, 33, 34, 46, 53, 63):
        if slot not in slots:
            continue
        poses = [m.poses(slot, 6000) for m in models]
        ticks = sorted({0, len(poses[0])//2, len(poses[0])-1})
        rows = []
        for yaw in (160, 180, 200):
            for tick in ticks:
                before, frame = R.render(models[0], math.radians(yaw), math.pi/6,
                                         size=320, pose=poses[0][tick])
                after, _ = R.render(models[1], math.radians(yaw), math.pi/6,
                                    size=320, pose=poses[1][tick], frame=frame)
                rows.append(label(np.concatenate([before, after], 1),
                                  f'BEFORE / AFTER   slot {slot} tick {tick} yaw {yaw}'))
        names = {0:'idle', 1:'closed-shield', 2:'walk', 3:'tired', 4:'run'}
        C.png(str(a.out/f'wargreymon-{names.get(slot, "battle-"+str(slot))}-before-after.png'), np.concatenate(rows))
    glove_rows = []
    isolated = []
    for stage, model in enumerate(models):
        mesh = copy.deepcopy(model.m)
        for oi, obj in enumerate(mesh.tmd.objects):
            if oi != 6:
                obj.prims = []
            else:
                obj.prims = obj.prims[36:38 if stage == 0 else 40]
        isolated.append(C.Model(mesh, model.bones, model.tim))
    # Decoded ticks where the old left socket halves have opposing facings.
    for slot, tick, yaw in ((0, 40, 0), (2, 42, 180), (4, 11, 180), (33, 56, 45)):
        pose = models[0].poses(slot)[tick]
        before, frame = R.render(isolated[0], math.radians(yaw), math.pi/6, size=512, pose=pose)
        after, _ = R.render(isolated[1], math.radians(yaw), math.pi/6, size=512, pose=pose, frame=frame)
        socket = models[0].world(pose)[7][models[0].local[7][:, 1] < 40]
        xy = C._rotate(socket, math.radians(yaw), math.pi/6)[:, :2]*frame[0]+frame[1]
        lo = np.maximum(np.floor(xy.min(0)-12).astype(int), 0)
        hi = np.minimum(np.ceil(xy.max(0)+12).astype(int), 512)
        parts = [im[lo[1]:hi[1], lo[0]:hi[0]] for im in (before, after)]
        # Identical crop and scale for both panels; isolate the glove to expose
        # socket culling that the shield can obscure in a whole-model view.
        panels = []
        for part in parts:
            h, w = part.shape[:2]
            scale = min(320/w, 256/h)
            canvas = Image.new('RGB', (320, 256), '#181818')
            canvas.paste(Image.fromarray(part).resize((round(w*scale), round(h*scale))), (0, 0))
            panels.append(np.asarray(canvas))
        glove_rows.append(label(np.concatenate(panels, 1), f'BEFORE / AFTER socket faces only slot {slot} tick {tick}'))
    C.png(str(a.out/'wargreymon-glove-before-after.png'), np.concatenate(glove_rows))
    (a.out/'wargreymon-audit.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
