#!/usr/bin/env python3
"""Reproduce the reviewed foreground alpha masks for screens 300–311.

Run with the SAM venv; MODEL is sam_vit_h_4b8939.pth:
    python maps/author/sam_foreground_depth_a.py MODEL OUT [--screens 301 304]

The manifests record full-resolution source/crop transforms and screen-space
box/positive/negative prompts. Outputs are drafts for visual review, never
installed automatically. RGB comes only from the finished, unmodified art.
No original-disc data or model weights are written to the mod.
"""

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import argparse
import json
from pathlib import Path


def main():
    import cv2
    import numpy as np
    import torch
    from tools.image import Image
    from tools.maps.sam import SamPredictor, sam_model_registry

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('model', type=Path)
    ap.add_argument('out', type=Path)
    ap.add_argument('--screens', type=int, nargs='+', default=list(range(300, 312)))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    mod = Path(__file__).resolve().parents[2]
    torch.set_num_threads(3)
    cv2.setNumThreads(1)
    pred = SamPredictor(sam_model_registry['vit_h'](checkpoint=str(args.model)))
    for f in sorted((mod / 'maps/foreground-depth-a').glob('*.json')):
        d = json.loads(f.read_text())
        if d['screen'] not in args.screens or not d['pieces']:
            continue
        art = Image.open(mod / 'art' / (d['art'] + '.png')).convert('RGB')
        width, height = art.size
        first = d['pieces'][0]['sam']
        pred.set_image(np.array(Image.open(mod / first['source']).convert('RGB')))
        # Retain the image embedding so a review can adjust prompts without
        # repeating the expensive encoder. This is an untracked scratch artifact.
        np.savez_compressed(args.out / (f.stem + '-embedding.npz'),
                            features=pred.features.cpu().numpy(),
                            original_size=pred.original_size, input_size=pred.input_size)
        masks = {}
        overlay = np.array(art)
        draft = json.loads(f.read_text())
        for piece in draft['pieces']:
            prompt = piece['sam']
            assert prompt['source'] == first['source']
            left, top, cw, ch = prompt['crop']
            sx, sy = cw / width, ch / height
            pos, neg = prompt['positive'], prompt['negative']
            pts = np.array([(x * sx + left, y * sy + top) for x, y in pos + neg])
            x0, y0, x1, y1 = prompt['box']
            box = np.array([x0 * sx + left, y0 * sy + top,
                            x1 * sx + left, y1 * sy + top])
            with torch.inference_mode():
                raw, scores, _ = pred.predict(
                    point_coords=pts, point_labels=np.array([1] * len(pos) + [0] * len(neg)),
                    box=box, multimask_output=True)
            selected = int(np.argmax(scores))
            small = cv2.resize(raw[selected, top:top + ch, left:left + cw].astype(np.float32),
                               (width, height), interpolation=cv2.INTER_AREA) > .5
            n, labels, stats, _ = cv2.connectedComponentsWithStats(small.astype(np.uint8))
            for i in range(1, n):
                if stats[i, cv2.CC_STAT_AREA] < prompt.get('min_component_area', 3):
                    small[labels == i] = False
            if prompt.get('largest_component'):
                small = labels == (1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA])))
            # Solid stone can have spurious pinholes from similar floor colours.
            # Skeleton/foliage/rigging gaps are real and remain transparent.
            if prompt.get('fill_holes'):
                flood = np.pad(small.astype(np.uint8), 1)
                cv2.floodFill(flood, None, (0, 0), 2)
                small |= flood[1:-1, 1:-1] == 0
            masks[piece['name']] = small
            rgba = art.convert('RGBA')
            rgba.putalpha(Image.fromarray(small.astype(np.uint8) * 255))
            bbox = rgba.getbbox()
            assert bbox, (f.stem, piece['name'], 'empty mask')
            rgba.crop(bbox).save(args.out / piece['png'])
            piece['at'] = list(bbox[:2])
            prompt['score'] = float(scores[selected])
            contours, _ = cv2.findContours(small.astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(overlay, contours, -1, (0, 255, 255), 1)
            print(f"{d['screen']} {piece['name']}: score {scores[selected]:.3f}, {small.sum()} pixels", flush=True)
        np.savez_compressed(args.out / (f.stem + '-masks.npz'), **masks)
        Image.fromarray(overlay).save(args.out / (f.stem + '-contours.png'))
        (args.out / f.name).write_text(json.dumps(draft, indent=2) + '\n')


if __name__ == '__main__':
    main()
