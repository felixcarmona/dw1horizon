#!/usr/bin/env python3
"""Reproduce screens 358–368's foreground alpha from their recorded SAM prompts.

Run in the SAM authoring venv, with --checkpoint WEIGHTS --sources SOURCES.json
--out DIRECTORY [--screen ID ...]. SOURCES.json maps each recorded source basename
onto its full-resolution local file. No original-disc image is emitted or shipped.
The ordinary game build uses the committed RGBA pieces and needs no SAM packages.
"""

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / "tools").is_dir())))

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from tools.image import Image
import torch
from tools.maps.sam import SamPredictor, sam_model_registry

MOD = Path(__file__).resolve().parents[2]


def cleanup_mask(mask, recipe):
    mode = recipe.get('boundary_mode')
    if mode:
        source = mask.copy()
        mask[:] = False
        columns = range(8, 70) if mode == 'outside_lower_3' else range(mask.shape[1])
        for x in columns:
            ys = np.nonzero(source[:, x])[0]
            if not len(ys):
                continue
            edge = ys.max()
            if mode == 'outside_lower_3':
                mask[edge + 1:min(edge + 4, mask.shape[0]), x] = True
            else:
                mask[max(0, edge - 8):edge + 1, x] = source[max(0, edge - 8):edge + 1, x]
    c = recipe['cleanup']
    n, labels, stats, _ = cv2.connectedComponentsWithStats((~mask).astype(np.uint8))
    for k in range(1, n):
        x, y, w, h, area = stats[k]
        if x == 0 or y == 0 or x + w == mask.shape[1] or y + h == mask.shape[0]:
            continue
        if (c['fill_holes'] or
                (c['fill_holes_above'] is not None and y + h <= c['fill_holes_above']) or
                area <= c['fill_small_holes']):
            mask[labels == k] = True
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8))
    for k in range(1, n):
        if stats[k, cv2.CC_STAT_AREA] < c['min_component']:
            mask[labels == k] = False
    if c.get('largest_component'):
        n, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8))
        mask = labels == 1 + stats[1:, cv2.CC_STAT_AREA].argmax()
    return mask


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', required=True)
    parser.add_argument('--sources', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--screen', action='append', type=int)
    args = parser.parse_args()
    sources = json.loads(args.sources.read_text())
    cv2.setNumThreads(1)
    torch.set_num_threads(3)
    predictor = SamPredictor(sam_model_registry['vit_h'](checkpoint=args.checkpoint))
    embeddings = {}
    args.out.mkdir(parents=True, exist_ok=True)
    for path in sorted((MOD / 'maps/district-foreground').glob('*.json')):
        manifest = json.loads(path.read_text())
        if args.screen and manifest['screen'] not in args.screen:
            continue
        for piece in manifest['pieces']:
            recipe = piece['segmentation']
            w, h = recipe['native_size']
            mask = np.zeros((h, w), bool)
            art = Image.open(MOD / 'art' / recipe['source_art']).convert('RGBA')
            alpha = np.array(art)[:, :, 3] >= 128
            for c in recipe['components']:
                src = Path(sources[c['source']])
                if c['source'] not in embeddings:
                    assert hashlib.sha1(src.read_bytes()).hexdigest() == c['source_sha1'], src
                    predictor.set_image(np.array(Image.open(src).convert('RGB')))
                    embeddings[c['source']] = (predictor.features, predictor.original_size, predictor.input_size)
                predictor.features, predictor.original_size, predictor.input_size = embeddings[c['source']]
                predictor.is_image_set = True
                matrix = np.array(c['native_to_source'])
                def transform(points):
                    return np.c_[np.array(points), np.ones(len(points))] @ matrix.T
                x0, y0, x1, y1 = c['box']
                points = transform(c['positive'] + c['negative'])
                labels = np.array([1] * len(c['positive']) + [0] * len(c['negative']))
                masks, scores, _ = predictor.predict(point_coords=points, point_labels=labels,
                    box=transform([[x0, y0], [x1, y1]]).flatten(), multimask_output=True)
                small = cv2.warpAffine(masks[int(scores.argmax())].astype(np.float32), matrix, (w, h),
                    flags=cv2.WARP_INVERSE_MAP | cv2.INTER_AREA) > .5
                n, component, stats, _ = cv2.connectedComponentsWithStats(small.astype(np.uint8))
                for k in range(1, n):
                    if stats[k, cv2.CC_STAT_AREA] < 3:
                        small[component == k] = False
                mask |= small & alpha
            mask = cleanup_mask(mask, recipe) & alpha
            rgba = np.array(art)
            rgba[:, :, 3] = mask.astype(np.uint8) * 255
            cutout = Image.fromarray(rgba)
            box = cutout.getbbox()
            assert box, piece['png']
            offset = recipe['source_offset']
            assert piece['at'] == [offset[0] + box[0], offset[1] + box[1]], piece['png']
            dest = args.out / piece['png']
            cutout.crop(box).save(dest)
            print(manifest['screen'], dest, int(mask.sum()), flush=True)


if __name__ == '__main__':
    main()
