#!/usr/bin/env python3
"""Validate authored 300–311 cutouts against reference and rebuilt MAP/TFS files.

Run from the repository root:
    python story/mods/what-the-island-forgot/maps/author/check_foreground_depth_a.py REFERENCE_DIR REBUILT_DIR
Neither directory nor any original-disc pixels are distributed with the mod.
"""
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5] if 'author' in str(Path(__file__).parent) else Path.cwd()
sys.path.insert(0, str(ROOT / 'tools'))
import dwmap


def pixels(m):
    result = {}
    for raw in m.tims:
        t = dwmap.TIM(raw)
        for y in range(t.h):
            for x in range(t.w * (2 if t.bpp == 8 else 4)):
                if t.bpp == 8:
                    result[(t.x * 2 + x, t.y + y)] = t.pixels[y * t.w * 2 + x]
    return result


def main(reference, rebuilt):
    mod = ROOT / 'story/mods/what-the-island-forgot'
    pieces = total = 0
    for manifest in sorted((mod / 'maps/foreground-depth-a').glob('*.json')):
        d = json.loads(manifest.read_text())
        assert 300 <= d['screen'] <= 311
        name = manifest.stem
        old = dwmap.MapFile((reference / (name + '.MAP')).read_bytes())
        new = dwmap.MapFile((rebuilt / (name + '.MAP')).read_bytes())
        oldpix, newpix = pixels(old), pixels(new)
        assert new.build() == dwmap.MapFile(new.build()).build(), name
        assert old.warps == new.warps, (name, 'warp changed')
        assert len(old.tims) == len(new.tims), (name, 'TIM count changed')
        for a, b in zip(old.tims, new.tims):
            ta, tb = dwmap.TIM(a), dwmap.TIM(b)
            assert (ta.bpp, ta.x, ta.y, ta.w, ta.h) == (tb.bpp, tb.x, tb.y, tb.w, tb.h)
            # Keep every palette and upload rectangle; only sprite texture pixels may change.
            start = 8 + (struct.unpack_from('<I', a, 8)[0] if ta.flag & 8 else 0) + 12
            assert a[:start] == b[:start], (name, 'palette changed')
            if ta.bpp != 8:
                assert a == b, (name, 'four-bit donor texture changed')
        active = set()
        for inst in old.instances:
            if inst['flag'] == 1:
                continue
            assert inst in new.instances, (name, 'original animation instance lost')
            active.update(f for f in inst['frames'] if f >= 0)
        for idx in active:
            a = old.sprites[idx]
            assert a == new.sprites[idx], (name, 'original frame changed')
            if a['clut'] == -1 or a['clut'] >= 16:
                for y in range(a['height']):
                    for x in range(a['width']):
                        at = (768 + a['texX'] + x, a['texY'] + y)
                        assert oldpix[at] == newpix[at], (name, 'original texture overwritten')
        bgpath = reference / (name + '.TFS')
        tfs = dwmap.TfsFile(bgpath.read_bytes())
        newtfs = dwmap.TfsFile((rebuilt / (name + '.TFS')).read_bytes())
        width, height, bg = tfs.image_indices(new)
        assert (width, height, bg) == newtfs.image_indices(new), (name, 'background indices changed')
        used = {v for row in bg for v in row}
        for a, b in zip(tfs.cluts, newtfs.cluts):
            assert all(a[i] == b[i] for i in used), (name, 'visible background colour changed')
            assert b[0] == 0 or not d['pieces'], (name, 'opaque transparent index')
        expected = set()
        for piece in d['pieces']:
            w, h, mode, rows, _ = dwmap.png_read(str(mod / 'art/foreground-depth-a' / piece['png']), alpha=True)
            x0, y0 = piece['at']
            expected.update((x0 + x, y0 + y) for y in range(h) for x in range(w) if rows[y][4*x+3] >= 128)
        actual = set()
        for inst in new.instances:
            if inst['flag'] == 1:
                continue
            for idx in inst['frames']:
                if idx < 0 or idx in active:
                    continue
                sp = new.sprites[idx]
                assert sp['clut'] == -1 and sp['transparency'] == 4
                assert sp['texX'] % 256 + sp['width'] <= 256
                assert sp['texY'] + sp['height'] <= 256
                for y in range(sp['height']):
                    for x in range(sp['width']):
                        c = newpix[(768 + sp['texX'] + x, sp['texY'] + y)]
                        xx, yy = inst['x'] + x, inst['y'] + y
                        if c:
                            assert 0 <= xx < width and 0 <= yy < height
                            assert (xx, yy) in expected, (name, 'opaque pixel outside mask', xx, yy)
                            for before, after in zip(tfs.cluts, newtfs.cluts):
                                assert after[c] != 0, (name, 'transparent colour inside mask', xx, yy)
                                assert after[c] & 0x7fff == before[bg[yy][xx]] & 0x7fff, (name, 'cutout palette seam', xx, yy)
                            actual.add((xx, yy))
                            total += 1
        assert actual == expected, (name, 'mask lost pixels', len(expected - actual))
        for edit in d['collision']:
            x, z = edit['tile']
            assert old.collision[z * 100 + x] == edit['before']
            assert new.collision[z * 100 + x] == edit['after']
            assert edit['reason']
        edits = {z * 100 + x for e in d['collision'] for x, z in [e['tile']]}
        assert all(a == b or i in edits for i, (a, b) in enumerate(zip(old.collision, new.collision)))
        for piece in d['pieces']:
            w, h, mode, rows, _ = dwmap.png_read(str(mod / 'art/foreground-depth-a' / piece['png']), alpha=True)
            assert mode == 'RGBA'
            aw, ah, amode, art, _ = dwmap.png_read(str(mod / 'art' / (d['art'] + '.png')), alpha=True)
            assert amode in ('RGB', 'RGBA')
            stride = 4 if amode == 'RGBA' else 3
            x0, y0 = piece['at']
            for y, row in enumerate(rows):
                for x in range(w):
                    assert row[x * 4:x * 4 + 3] == art[y0 + y][(x0 + x) * stride:(x0 + x) * stride + 3]
            pieces += 1
        assert len(new.sprites) <= 180 and len(new.instances) <= 188
        assert len(new.build()) <= 0x80000
        print(f'{d["screen"]}: palettes, active sprites, warps, collision log, RAM/VRAM and source RGB verified')
    print(f'PASS: {pieces} own-art cutouts; {total} opaque pixels match every background CLUT; exact alpha coverage')


if __name__ == '__main__':
    main(Path(sys.argv[1]), Path(sys.argv[2]))
