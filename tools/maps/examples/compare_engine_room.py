#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare regenerated Engine Room silhouettes and every time-of-day colour.

Usage: build/sam-venv/bin/python tools/maps/examples/compare_engine_room.py \
    build/engine-original/ENGN01.MAP build/engine-original/ENGN01.TFS build/engine-review
"""
import json
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import dwmap


def main():
    map_path, tfs_path, output = map(Path, sys.argv[1:])
    old = dwmap.MapFile(map_path.read_bytes())
    new = dwmap.MapFile((output/'candidate.MAP').read_bytes())
    before = dwmap.TfsFile(tfs_path.read_bytes())
    after = dwmap.TfsFile((output/'candidate.TFS').read_bytes())
    masks = np.load(output/'masks.npz', allow_pickle=False)
    placements = json.loads((output/'placements.json').read_text())
    _, _, rows = before.image_indices(old)
    background = np.array([list(row) for row in rows], dtype='uint8')
    report = {}
    for name, instance in [('br-crates', 1), ('wreck', 2)]:
        inst = old.instances[instance]; sprite = old.sprites[inst['frames'][0]]
        # The old Engine Room uses 8 bpp TIM 0 at VRAM (512,0), texX 256.
        tim = dwmap.TIM(old.tims[0])
        pixels = np.frombuffer(tim.pixels, np.uint8).reshape(tim.h, tim.w*2)
        x, y = sprite['texX']-256, sprite['texY']
        width = min(sprite['width'], old.width*128-inst['x']); height = sprite['height']
        reference = np.zeros((old.height*128, old.width*128), dtype=bool)
        old_cut = pixels[y:y+height,x:x+width]
        reference[inst['y']:inst['y']+height, inst['x']:inst['x']+width] = old_cut != 0
        old_colour_errors = 0
        for palette in before.cluts:
            colours = np.array(palette,dtype='uint16') & 0x7fff
            source = background[inst['y']:inst['y']+height,inst['x']:inst['x']+width]
            old_colour_errors += int(np.count_nonzero((colours[old_cut]!=colours[source])&(old_cut!=0)))
        actual = masks[name].astype(bool)
        added, removed = int((actual&~reference).sum()), int((reference&~actual).sum())
        colour_errors = 0
        for place in [p for p in placements if p['name']==name]:
            t = dwmap.TIM(new.tims[place['tim']]); tx,ty = place['texture']; ox,oy,w,h=place['source']
            packed = np.frombuffer(t.pixels,np.uint8).reshape(t.h,t.w*2)[ty:ty+h,tx:tx+w]
            opaque = actual[oy:oy+h,ox:ox+w]
            for a,b in zip(before.cluts,after.cluts):
                expected = np.array(a,dtype='uint16')[background[oy:oy+h,ox:ox+w]] & 0x7fff
                got = np.array(b,dtype='uint16')[packed] & 0x7fff
                colour_errors += int(np.count_nonzero((expected!=got)&opaque))
        report[name] = dict(reference_pixels=int(reference.sum()),regenerated_pixels=int(actual.sum()),
                            added=added,removed=removed,reference_colour_errors=old_colour_errors,
                            palettes_checked=len(before.cluts),time_of_day_colour_errors=colour_errors)
    print(json.dumps(report,indent=2))
    if any(r['added'] or r['removed'] or r['time_of_day_colour_errors'] for r in report.values()):
        raise SystemExit('FAIL: Engine Room differs; inspect before accepting')


if __name__=='__main__':main()
