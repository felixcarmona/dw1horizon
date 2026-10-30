#!/usr/bin/env python3
"""Recreate screens 312–322's silhouettes from their full-resolution generated art.

Requires torch, segment_anything, OpenCV and NumPy. Player-disc pixels are never read.
    python segment-depth-a2.py --checkpoint sam_vit_h_4b8939.pth --out BUILD_DIR [SCREEN ...]
Outputs cropped RGBA PNGs and full native-resolution mask archives for review. Copy an
approved PNG and its recorded placement into art/foreground and maps/foreground.
"""

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / "tools").is_dir())))

import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('screens', nargs='*', type=int)
    args = parser.parse_args()
    import cv2
    import numpy as np
    import torch
    from tools.image import Image
    from tools.maps.sam import SamPredictor, sam_model_registry

    torch.set_num_threads(3)
    cv2.setNumThreads(1)
    mod = Path(__file__).resolve().parents[2]
    root = mod.parents[2]
    args.out.mkdir(parents=True, exist_ok=True)
    predictor = SamPredictor(sam_model_registry['vit_h'](checkpoint=str(args.checkpoint)))
    for path in sorted((Path(__file__).parent / 'foreground-a2').glob('*.json')):
        data = json.loads(path.read_text())
        if args.screens and data['screen'] not in args.screens:
            continue
        masks = {}
        for record in data['records']:
            source = root / record['source']
            assert hashlib.sha1(source.read_bytes()).hexdigest() == record['source_sha1'], source
            # The input image is encoded once per screen, before any object prompts.
            if not masks:
                full = np.array(Image.open(source).convert('RGB'))
                predictor.set_image(full)
            art_name = next(json.loads(p.read_text())['art'] for p in (mod / 'maps/foreground').glob('*.json')
                            if json.loads(p.read_text())['screen'] == data['screen'])
            art = Image.open(mod / 'art' / (art_name + '.png')).convert('RGB')
            width, height = art.size
            left, top, cw, ch = record['crop']
            sx, sy = cw / width, ch / height
            mask = np.zeros((height, width), dtype=np.uint8)
            for part in [record] + record.get('parts', []):
                pos, neg = part['pos'], part.get('neg', [])
                box = part['box']
                candidates, scores, _ = predictor.predict(
                    point_coords=np.array([[left + x * sx, top + y * sy] for x, y in pos + neg]),
                    point_labels=np.array([1] * len(pos) + [0] * len(neg)),
                    box=np.array([left + box[0] * sx, top + box[1] * sy,
                                  left + box[2] * sx, top + box[3] * sy]),
                    multimask_output=part.get('multimask', True))
                selected = candidates[int(np.argmax(scores))].astype(np.uint8)
                if part.get('refine'):
                    # SAM locates the lattice. Its own full-resolution rust and floor
                    # colors resolve the thin bars and the grass between them.
                    ys, xs = np.nonzero(selected)
                    xa, xb = max(0, xs.min() - 8), min(full.shape[1], xs.max() + 9)
                    ya, yb = max(0, ys.min() - 8), min(full.shape[0], ys.max() + 9)
                    image = full[ya:yb, xa:xb]
                    semantic = selected[ya:yb, xa:xb] > 0
                    rgb = image.astype(np.float32)
                    ratio = rgb[:, :, 0] / np.maximum(1, rgb[:, :, 1])
                    gc = np.zeros(semantic.shape, dtype=np.uint8)
                    gc[semantic] = cv2.GC_PR_FGD
                    gc[semantic & (ratio > part['refine']['foreground_ratio'])] = cv2.GC_FGD
                    gc[semantic & (ratio < part['refine']['floor_ratio'])] = cv2.GC_BGD
                    cv2.grabCut(image, gc, None, np.zeros((1, 65)), np.zeros((1, 65)),
                                4, cv2.GC_INIT_WITH_MASK)
                    selected[:] = 0
                    selected[ya:yb, xa:xb] = ((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)).astype(np.uint8)
                best = selected[top:top + ch, left:left + cw]
                partial = (cv2.resize(best.astype(np.float32), (width, height),
                                      interpolation=cv2.INTER_AREA) > .5).astype(np.uint8)
                if part is not record and part.get('fill_holes'):
                    count, labels, stats, _ = cv2.connectedComponentsWithStats(1 - partial)
                    for component in range(1, count):
                        x, y, w, h, _ = stats[component]
                        if x > 0 and y > 0 and x + w < width and y + h < height:
                            partial[labels == component] = 1
                mask |= partial
            count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
            for component in range(1, count):
                if stats[component, cv2.CC_STAT_AREA] < 3:
                    mask[labels == component] = 0
            if record.get('components'):
                count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
                keep = sorted(range(1, count), key=lambda i: stats[i, cv2.CC_STAT_AREA],
                              reverse=True)[:record['components']]
                mask = np.isin(labels, keep).astype(np.uint8)
            if record.get('fill_holes'):
                count, labels, stats, _ = cv2.connectedComponentsWithStats(1 - mask)
                for component in range(1, count):
                    x, y, w, h, _ = stats[component]
                    if x > 0 and y > 0 and x + w < width and y + h < height:
                        mask[labels == component] = 1
            masks[record['piece']] = mask
            rgba = art.convert('RGBA')
            rgba.putalpha(Image.fromarray(mask * 255))
            bounds = rgba.getbbox()
            assert bounds is not None, record['piece']
            rgba.crop(bounds).save(args.out / record['png'])
            print(data['screen'], record['piece'], 'at', bounds[:2], 'pixels', int(mask.sum()), flush=True)
        np.savez_compressed(args.out / (str(data['screen']) + '-masks.npz'), **masks)


if __name__ == '__main__':
    main()
