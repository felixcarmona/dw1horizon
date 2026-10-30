#!/usr/bin/env python3
"""Rebuild screens 323–334's foreground alpha with SAM ViT-H.

Requires torch, segment_anything, OpenCV, NumPy (authoring only).
Full-resolution PNGs are local inputs under art/full; no original-disc art is used.
The per-object box, positive/negative points and colour refinement are recorded in
maps/foreground/<screen>.json. Run from the repository root, passing the checkpoint.
RGB always comes from the unchanged generated map art. The build recipe subsequently
copies matching quantized TFS indices, preserving the live day/night palettes.
"""

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from tools.image import Image
import torch
from tools.maps.sam import SamPredictor, sam_model_registry


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--checkpoint', required=True)
    ap.add_argument('names', nargs='*')
    args = ap.parse_args()
    mod = Path(__file__).resolve().parents[2]
    specs = sorted((mod / 'maps/foreground').glob('*.json'))
    specs = [(p, json.loads(p.read_text())) for p in specs]
    specs = [(p, s) for p, s in specs if 323 <= s['screen'] <= 334
             and (not args.names or p.stem in args.names)]
    torch.set_num_threads(3)
    predictor = SamPredictor(sam_model_registry['vit_h'](checkpoint=args.checkpoint))
    for path, spec in specs:
        art = Image.open(mod / 'art' / (path.stem + '.png')).convert('RGBA')
        w, h = art.size
        source = mod / 'art/full' / spec['pieces'][0]['mask']['source']
        predictor.set_image(np.array(Image.open(source).convert('RGB')))
        for piece in spec['pieces']:
            prompt = piece['mask']
            left, top, cw, ch = prompt['crop']
            scale = np.array([cw / w, ch / h]); offset = np.array([left, top])
            pos, neg = prompt['positive'], prompt['negative']
            coords = np.array(pos + neg) * scale + offset
            labels = np.array([1] * len(pos) + [0] * len(neg))
            box = (np.array(prompt['box']).reshape(2, 2) * scale + offset).flatten()
            masks, scores, _ = predictor.predict(point_coords=coords, point_labels=labels,
                                                 box=box, multimask_output=True)
            mask = masks[int(np.argmax(scores))][top:top + ch, left:left + cw]
            for part in prompt.get('parts', []):
                coords = np.array(part['positive'] + part['negative']) * scale + offset
                labels = np.array([1] * len(part['positive']) + [0] * len(part['negative']))
                box = (np.array(part['box']).reshape(2, 2) * scale + offset).flatten()
                parts, part_scores, _ = predictor.predict(point_coords=coords, point_labels=labels,
                                                          box=box, multimask_output=True)
                mask |= parts[int(np.argmax(part_scores))][top:top + ch, left:left + cw]
            rgb = np.array(Image.open(source).convert('RGB'), dtype='int16')[top:top + ch, left:left + cw]
            red, green, blue = rgb.transpose(2, 0, 1)
            if prompt.get('refinement') == 'cyan-bars':
                mask &= (green > 145) & (blue > 150) & (green - red > 25) & (blue - red > 25)
            if prompt.get('refinement') == 'brown-iron':
                mask &= (red > blue + 3) & (red > green + 1)
            for window in prompt.get('colour_windows', []):
                x0, y0, x1, y1 = np.round(np.array(window['box']).reshape(2, 2) * scale).astype('int32').flatten()
                mask[y0:y1, x0:x1] &= (red - green)[y0:y1, x0:x1] < window['max_red_green']
            mask = (cv2.resize(mask.astype('float32'), (w, h),
                               interpolation=cv2.INTER_AREA) > .5).astype('uint8')
            count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
            for i in range(1, count):
                if stats[i, cv2.CC_STAT_AREA] < 12:
                    mask[labels == i] = 0
            if prompt.get('post_refinement') == 'cyan-core':
                rgb = np.array(art, dtype='int16')
                red, green, blue = rgb[:, :, :3].transpose(2, 0, 1)
                mask &= (((green > 210) & (blue > 225)) | ((green - red > 60) & (blue - red > 75))).astype('uint8')
            if prompt.get('component_policy') == 'prompted':
                expanded = cv2.dilate(mask, np.ones((3, 3), np.uint8))
                count, labels, stats, _ = cv2.connectedComponentsWithStats(expanded)
                keep = set()
                for x, y in prompt['positive']:
                    keep.update(int(v) for v in np.unique(labels[max(0, y-2):y+3, max(0, x-2):x+3]) if v)
                x0, y0, x1, y1 = prompt['box']
                candidates = [i for i in range(1, count) if (labels[y0:y1, x0:x1] == i).any()]
                if candidates:
                    keep.add(max(candidates, key=lambda i: int(((labels == i) & (mask > 0))[y0:y1, x0:x1].sum())))
                mask &= np.isin(labels, list(keep)).astype('uint8')
            if prompt.get('fill_holes'):
                padded = np.pad(mask, 1)
                cv2.floodFill(padded, None, (0, 0), 2)
                mask = (padded[1:-1, 1:-1] != 2).astype('uint8')
            alpha = Image.fromarray(mask * 255)
            bounds = alpha.getbbox()
            if bounds is None:
                raise ValueError(piece['image'] + ': empty mask')
            cut = art.crop(bounds); cut.putalpha(alpha.crop(bounds))
            cut.save(mod / 'art/foreground' / piece['image'])
            piece['at'] = list(bounds[:2])
            prompt['score'] = float(scores.max())
            prompt['area'] = int(mask.sum())
            print(spec['screen'], piece['image'], prompt['score'], prompt['area'])
        path.write_text(json.dumps(spec, indent=2) + '\n')


if __name__ == '__main__':
    main()
