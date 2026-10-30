#!/usr/bin/env python3
"""Segment/check foreground cut-outs for screens 346–357 from our unmodified art.

    .venv/bin/python story/mods/what-the-island-forgot/maps/author/foreground-c.py [--check] [--built MAP_DIR]

Regenerate with --segment --checkpoint SAM_VIT_H --source-root FULLRES_ART_DIRECTORY.
The saved prompts operate on full-resolution generated art, as in the Engine Room.
Only the PNG alpha changes. Source RGB is copied exactly, with the source's existing alpha retained. The manifest
also records each changed collision tile and its object-specific reason; it is never derived by blocking a tile
merely because one corner touches a polygon. No extracted disc art is read or written by this authoring command.
"""

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import io
import json
import sys
from pathlib import Path
from tools.image import Image

MAPS=Path(__file__).resolve().parents[1]
MOD=MAPS.parent
DIRECTORY=MAPS/'foreground-c'
CUTOUTS=MOD/'art'/'foreground-c'

def render(cfg, obj):
    """Check the saved SAM alpha independently of the source RGB crop."""
    import hashlib
    source = Image.open(MOD/'art'/cfg['source']).convert('RGBA')
    actual = Image.open(CUTOUTS/obj['png']).convert('RGBA')
    mask = actual.getchannel('A')
    if set(mask.tobytes()) - {0, 255} or mask.getbbox() != (0, 0, *mask.size):
        raise ValueError(f'{cfg["screen"]} {obj["name"]}: nonbinary or untrimmed alpha')
    if list(mask.size) != obj['size']:
        raise ValueError(f'{cfg["screen"]} {obj["name"]}: cut-out size differs')
    if obj.get('mask_sha256') != hashlib.sha256(mask.tobytes()).hexdigest():
        raise ValueError(f'{cfg["screen"]} {obj["name"]}: SAM mask digest differs')
    x, y = obj['at']
    expected = source.crop((x, y, x+mask.width, y+mask.height))
    expected.putalpha(mask)
    return expected


def refine_edges(mask, original, prompt, scale, offset):
    """Snap narrow SAM-selected metal parts to full-resolution color edges.

    Foreground strokes and surrounding background points constrain GrabCut inside
    each object's box. This cleans floor from grille openings while retaining thin
    posts; it changes alpha only, never the source artwork.
    """
    import cv2
    import numpy as np
    box = (np.array(prompt['box']).reshape(2, 2)*scale+offset).ravel()
    bx0, by0, bx1, by1 = np.rint(box).astype(int)
    bx0, by0 = max(0, bx0-8), max(0, by0-8)
    bx1, by1 = min(original.shape[1], bx1+8), min(original.shape[0], by1+8)
    crop = original[by0:by1, bx0:bx1].copy()
    gc = np.where(mask[by0:by1, bx0:bx1], cv2.GC_PR_FGD, cv2.GC_PR_BGD).astype(np.uint8)
    gc[:2] = 0; gc[-2:] = 0; gc[:, :2] = 0; gc[:, -2:] = 0
    pos, neg = prompt['positive'], prompt.get('negative', [])
    if prompt.get('trace_axis'):
        corridor = np.zeros(gc.shape, dtype=np.uint8)
        points = np.rint(np.array(pos)*scale+offset-[bx0, by0]).astype(np.int32)
        cv2.polylines(corridor, [points], False, 1, round(prompt['trace_radius']*scale.mean()*2))
        gc[corridor == 0] = cv2.GC_BGD
        cv2.polylines(gc, [points], False, cv2.GC_FGD, max(2, round(scale.mean()*1.6)))
    for label, points in [(cv2.GC_BGD, neg), (cv2.GC_FGD, pos)]:
        for point in points:
            q = np.rint(np.array(point)*scale+offset-[bx0, by0]).astype(int)
            if 0 <= q[0] < crop.shape[1] and 0 <= q[1] < crop.shape[0]:
                cv2.circle(gc, tuple(q), 2, label, -1)
    cv2.setRNGSeed(0)
    cv2.grabCut(crop, gc, None, np.zeros((1, 65)), np.zeros((1, 65)), 5, cv2.GC_INIT_WITH_MASK)
    result = np.zeros(mask.shape, dtype=bool)
    result[by0:by1, bx0:bx1] = (gc == 1) | (gc == 3)
    return result


def segment(paths):
    """Engine Room method: full-resolution SAM, object boxes/points, best score,
    area downsampling and speck removal. Load ViT-H once for the whole range.
    Third-party authoring dependencies are needed only for --segment.
    """
    import hashlib
    import numpy as np
    import cv2
    import torch
    from tools.maps.sam import sam_model_registry, SamPredictor
    torch.set_num_threads(3)
    cv2.setNumThreads(3)
    checkpoint = Path(sys.argv[sys.argv.index('--checkpoint')+1])
    source_root = Path(sys.argv[sys.argv.index('--source-root')+1])
    model = sam_model_registry['vit_h'](checkpoint=str(checkpoint))
    predictor = SamPredictor(model)
    for path in paths:
        cfg = json.loads(path.read_text())
        spec = cfg['sam_source']
        source = (MAPS.parents[3] if spec.get('repo_relative') else source_root)/spec['path']
        if hashlib.sha1(source.read_bytes()).hexdigest() != spec['sha1']:
            raise ValueError(f'{source}: full-resolution source differs')
        art = Image.open(MOD/'art'/cfg['source']).convert('RGBA')
        w, h = art.size
        x0, y0, x1, y1 = spec['crop']
        scale = np.array([(x1-x0)/w, (y1-y0)/h])
        offset = np.array([x0, y0])
        original = np.array(Image.open(source).convert('RGB'))
        predictor.set_image(original)
        for obj in cfg['pieces']:
            mask = np.zeros((h, w), dtype=np.uint8)
            prompts = [(False, p) for p in obj['sam']]
            # A loose sheet on walkable floor must stay in the background.
            prompts += [(True, p) for p in obj.get('subtract_sam', [])]
            for subtract, prompt in prompts:
                pos, neg = prompt['positive'], prompt.get('negative', [])
                coords = np.array(pos+neg)*scale+offset
                labels = np.array([1]*len(pos)+[0]*len(neg))
                box = (np.array(prompt['box']).reshape(2, 2)*scale+offset).ravel()
                masks, scores, _ = predictor.predict(point_coords=coords, point_labels=labels,
                                                     box=box, multimask_output=prompt.get('multimask', True))
                best = int(scores.argmax())
                selected = masks[best]
                if prompt.get('edge_refine'):
                    selected = refine_edges(selected, original, prompt, scale, offset)
                picked = (cv2.resize(selected[y0:y1, x0:x1].astype(np.float32),
                                    (w, h), interpolation=cv2.INTER_AREA) > .5).astype(np.uint8)
                mask = mask & (1-picked) if subtract else mask | picked
                prompt.update(scores=scores.tolist(), best=best)
            count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
            for i in range(1, count):
                if stats[i, cv2.CC_STAT_AREA] < obj.get('min_component', 3):
                    mask[labels == i] = 0
            if obj.get('component_at'):
                _, labels = cv2.connectedComponents(mask)
                sx, sy = obj['component_at']
                label = labels[sy, sx]
                if not label:
                    raise ValueError(f'{cfg["screen"]} {obj["name"]}: component seed left its stone')
                mask = (labels == label).astype(np.uint8)
            fill = obj.get('fill_holes_max_area', 0)
            if fill:
                count, labels, stats, _ = cv2.connectedComponentsWithStats(1-mask)
                for i in range(1, count):
                    x, y, ww, hh, area = stats[i]
                    if x > 0 and y > 0 and x+ww < w and y+hh < h and area <= fill:
                        mask[labels == i] = 1
            alpha = Image.fromarray(mask*255)
            box = alpha.getbbox()
            if box is None:
                raise ValueError(f'{cfg["screen"]} {obj["name"]}: empty SAM mask')
            cut = art.crop(box)
            alpha = alpha.crop(box)
            cut.putalpha(alpha)
            cut.save(CUTOUTS/obj['png'])
            obj.update(at=list(box[:2]), size=list(cut.size),
                       mask_sha256=hashlib.sha256(alpha.tobytes()).hexdigest())
        path.write_text(json.dumps(cfg, indent=2)+'\n')


def check_built(cfg, folder):
    """Decode the engine's atlas rectangles and compare RGBA coverage/colors to the masks.

    This checks transparency as well as RGB: an opaque black source pixel must not
    accidentally become a transparent sprite texel. Check every time-of-day palette.
    """
    sys.path.insert(0, str(MAPS))
    from mapbase import dwmap
    screen = json.loads(next((MOD/'screens').glob(f'{cfg["screen"]}-*.json')).read_text())
    m = dwmap.MapFile((folder/(screen['file']+'.MAP')).read_bytes())
    tfs = dwmap.TfsFile((folder/(screen['file']+'.TFS')).read_bytes())
    width, height, pixels = tfs.image_indices(m)
    missing = [i for i, value in enumerate(m.tiles) if value == -1]
    if missing:
        source = Image.open(MOD/'art'/cfg['source']).convert('RGB')
        quant = dwmap.Requant(tfs.palette_rgb(0), tfs.cluts[0])
        for tile in missing:
            tx, ty = tile % m.width * 128, tile // m.width * 128
            for y in range(ty, ty+128):
                for x in range(tx, tx+128):
                    pixels[y][x] = quant(*source.getpixel((x, y)))
    indices = Image.frombytes('L', (width, height), b''.join(pixels))
    tims = [dwmap.TIM(raw) for raw in m.tims]
    assert len(m.sprites) <= 180 and len(m.instances) <= 188
    assert sum(t.bpp == 8 for t in tims) == screen['tims8']
    assert sum(t.bpp == 4 for t in tims) == screen['tims4']
    for palette in tfs.cluts:
        assert palette[0] == 0, 'sprite transparency must stay zero'
        rgb = [dwmap.bgr555_to_rgb(c) for c in palette]
        lut = [tuple(rgb[i])+(0 if palette[i] == 0 else 255,) for i in range(256)]
        background = Image.new('RGB', (width, height))
        background.putdata([rgb[i] for i in indices.getdata()])
        expected = Image.new('RGBA', (width, height))
        actual = Image.new('RGBA', (width, height))
        for tile in missing:
            x, y = tile % m.width * 128, tile // m.width * 128
            expected.paste(background.crop((x, y, x+128, y+128)).convert('RGBA'), (x, y))
        for obj in cfg['pieces']:
            mask = Image.open(CUTOUTS/obj['png']).getchannel('A')
            x, y = obj['at']
            cut = background.crop((x, y, x+mask.width, y+mask.height)).convert('RGBA')
            cut.putalpha(mask)
            expected.alpha_composite(cut, (x, y))
        for inst in m.instances:
            assert inst['flag'] == 0
            sp = m.sprites[inst['frames'][0]]
            assert sp['clut'] == -1 and sp['transparency'] == 4
            page = 384+(sp['texX']//256)*128
            tim = next(t for t in tims if t.bpp == 8 and t.x <= page < t.x+t.w)
            x = (page-tim.x)*2+sp['texX']%256
            y, w, h = sp['texY'], sp['width'], sp['height']
            assert sp['texX']%256+w < 256 and y+h < 256
            atlas = Image.frombytes('L', (tim.w*2, tim.h), bytes(tim.pixels))
            values = atlas.crop((x, y, x+w, y+h))
            cut = Image.new('RGBA', (w, h)); cut.putdata([lut[i] for i in values.getdata()])
            actual.alpha_composite(cut, (inst['x'], inst['y']))
        if actual.tobytes() != expected.tobytes():
            raise ValueError(f'{cfg["screen"]}: encoded foreground differs in color or alpha')
    print(f'{cfg["screen"]}: encoded RGBA matches all {len(tfs.cluts)} palettes; '
          f'{len(m.instances)}/188 instances, {sum(len(t.raw) for t in tims)} existing TIM bytes')


def main():
    count=0
    paths = sorted(DIRECTORY.glob('*.json'))
    if '--screen' in sys.argv:
        selected = sys.argv[sys.argv.index('--screen')+1]
        paths = [p for p in paths if p.stem == selected]
    if '--segment' in sys.argv:
        segment(paths)
    for path in paths:
        cfg=json.loads(path.read_text())
        for obj in cfg['pieces']:
            expected=render(cfg,obj);target=CUTOUTS/obj['png']
            if '--check' in sys.argv:
                actual=Image.open(target).convert('RGBA')
                if actual.size!=expected.size or actual.tobytes()!=expected.tobytes():
                    raise ValueError(f'{target}: differs from unmodified source/mask')
            else:expected.save(target)
            count+=1
        if '--built' in sys.argv:
            check_built(cfg, Path(sys.argv[sys.argv.index('--built')+1]))
    print(f'{count} foreground cut-outs: source RGB and silhouette match')

if __name__=='__main__':main()
