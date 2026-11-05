#!/usr/bin/env python3
"""Restore Gallantmon's helmet eyes from the full-resolution source texture.

Authoring only: pass the World 2003 M369DUKE.BIN, the current MMD/TIM and an
output stem. Store the results with tools/models/edit.py put 318 MMD TIM.
The player build replays the resulting plain deltas.
"""
import argparse
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import mmd
from tools.derive.importers.vendor.dw3.model import parse_model


def restore(model_data, texture_data, source_data):
    source = parse_model(source_data)
    model = mmd.MMD.parse(model_data, 28)
    texture = mmd.Tim4(texture_data)
    # This free rectangle keeps all 56x32 source pixels, rather than the
    # importer's 38x21 packing of the eye and snout patch.
    target_x, width, height = 125, 56, 32
    for obj in model.tmd.objects:
        for prim in obj.prims:
            uv = prim.decode()['uv']
            if uv:
                assert (max(u for u, v in uv) < target_x or
                        min(u for u, v in uv) >= target_x + width or
                        min(v for u, v in uv) >= height), 'destination is occupied'
    uv_by_vertex = {}
    for prim in source.bones[5].mesh.prims:
        if list(prim.material[:5]) == [136, 0, 0, 0, 248]:
            for vertex, uv in zip(prim.verts, prim.uvs):
                assert vertex not in uv_by_vertex or uv_by_vertex[vertex] == uv
                uv_by_vertex[vertex] = uv
    faces = 0
    for i, prim in enumerate(model.tmd.objects[5].prims):
        face = prim.decode()
        if face['uv'] and all(154 <= u <= 192 and 105 <= v <= 126 for u, v in face['uv']):
            face['uv'] = [(target_x + uv_by_vertex[v][0], uv_by_vertex[v][1]) for v in face['verts']]
            model.tmd.objects[5].prims[i] = mmd.Prim.encode(face)
            faces += 1
    assert faces == 8
    # The source TIM stores 256x256 four-bit texels in a 16-bit pixel block.
    pixels = source.texture[20:]
    palette = list(struct.unpack_from('<16H', pixels, (248 * 64) * 2))
    assert palette == texture.pal[2], 'source palette differs'
    for y in range(height):
        for x in range(width):
            pixel = y * 256 + 136 + x
            texture.idx[y * 256 + target_x + x] = (pixels[pixel // 2] >> (4 * (pixel % 2))) & 15
    result = model.build(), texture.to_bytes()
    assert len(result[0]) == len(model_data) and len(result[1]) == len(texture_data)
    assert model.anims.build() == mmd.MMD.parse(model_data, 28).anims.build()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('model', type=Path)
    parser.add_argument('texture', type=Path)
    parser.add_argument('out', type=Path)
    args = parser.parse_args()
    model, texture = restore(args.model.read_bytes(), args.texture.read_bytes(), args.source.read_bytes())
    args.out.with_suffix('.MMD').write_bytes(model)
    args.out.with_suffix('.TIM').write_bytes(texture)


if __name__ == '__main__':
    main()
