#!/usr/bin/env python3
"""Replay the reviewed SAM prompts for screens 335–345 on their full-resolution art.

Requires torch, segment_anything, OpenCV and NumPy. The large full-resolution art
and model checkpoint are local authoring inputs, never disc textures.

    sam-foreground.py CHECKPOINT OUTPUT_DIR [SCREEN ...]

Outputs cropped RGBA pieces and placement metadata for review. It does not modify
manifests or collision data. Prompt coordinates use the screen's native art size.
"""

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import torch
from tools.image import Image
from tools.maps.sam import SamPredictor, sam_model_registry


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('checkpoint')
    ap.add_argument('output', type=Path)
    ap.add_argument('screens', nargs='*', type=int)
    args = ap.parse_args()
    torch.set_num_threads(3)
    cv2.setNumThreads(1)
    root = Path(__file__).resolve().parents[2]
    predictor = SamPredictor(sam_model_registry['vit_h'](checkpoint=args.checkpoint))
    args.output.mkdir(parents=True, exist_ok=True)
    for manifest in sorted((root / 'maps/foreground').glob('*.json')):
        data = json.loads(manifest.read_text())
        if not 335 <= data['screen'] <= 345 or not data['pieces']:
            continue
        if args.screens and data['screen'] not in args.screens:
            continue
        source = data['segmentation_source']
        full = root / source['source']
        assert hashlib.sha1(full.read_bytes()).hexdigest() == source['source_sha1']
        predictor.set_image(np.array(Image.open(full).convert('RGB')))
        art = Image.open(root / 'art' / (manifest.stem + '.png')).convert('RGBA')
        scale, top = source['scale'], source['top']
        placements = []
        for piece in data['pieces']:
            prompt = piece['segmentation']
            positive, negative = prompt['positive'], prompt['negative']
            points = np.array([[x * scale, y * scale + top] for x, y in positive + negative])
            labels = np.array([1] * len(positive) + [0] * len(negative))
            box = np.array(prompt['box'], dtype=float) * scale
            box[[1, 3]] += top
            masks, scores, _ = predictor.predict(point_coords=points, point_labels=labels,
                                                 box=box, multimask_output=True)
            best = int(np.argmax(scores))
            mask = masks[best][top:top + round(art.height * scale)].astype(np.float32)
            mask = (cv2.resize(mask, art.size, interpolation=cv2.INTER_AREA) > .5).astype(np.uint8)
            count, components, stats, _ = cv2.connectedComponentsWithStats(mask)
            for i in range(1, count):
                if stats[i, cv2.CC_STAT_AREA] < prompt.get('min_component_area', 12):
                    mask[components == i] = 0
            if prompt.get('max_hole_area'):
                count, holes, stats, _ = cv2.connectedComponentsWithStats(1 - mask)
                for i in range(1, count):
                    x, y, w, h, area = stats[i]
                    if (area <= prompt['max_hole_area'] and x > 0 and y > 0
                            and x + w < art.width and y + h < art.height):
                        mask[holes == i] = 1
            cut = art.copy()
            cut.putalpha(Image.fromarray(mask * 255))
            bounds = cut.getbbox()
            assert bounds, piece['png']
            cut.crop(bounds).save(args.output / piece['png'])
            placements.append(dict(png=piece['png'], at=list(bounds[:2]), score=float(scores[best])))
        (args.output / (manifest.stem + '.json')).write_text(json.dumps(placements, indent=2) + '\n')


if __name__ == '__main__':
    main()
