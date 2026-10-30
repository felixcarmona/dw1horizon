"""Foreground pieces for screens 323–334, cut from their own generated backgrounds.

Uses only the donor's existing 8-bit TIM pages, and the imported TFS indices/palette
(the pieces must match the background exactly, including at night). RGBA files are
our art only; no disc pixels are saved in the mod. Sorting uses object ground
anchors, local ground lines or per-band surface heights independently of pixel
placement.
"""
import json
import os
import struct
from mapbase import Cam, MOD, dwmap


def apply(m, name, tfs_path):
    path = os.path.join(MOD, 'maps', 'foreground', name + '.json')
    if not os.path.isfile(path):
        return
    spec = json.load(open(path))
    tfs = dwmap.TfsFile(open(tfs_path, 'rb').read())
    positions, _, _ = tfs.layout(m)
    tiles = {p: tile[1] for p, tile in zip(positions, tfs.tiles)}
    # The background's reserved index zero looks black against the cleared frame,
    # but would leave holes over an actor. Prefer an existing opaque black index.
    black_index = next((i for i in range(1, 256)
                        if all(c[i] == 0x8000 for c in tfs.cluts)), None)
    def background_index(u, v):
        return tiles[(u // 128, v // 128)][(v % 128) * 128 + u % 128]
    pages = {}
    for k, raw in enumerate(m.tims):
        tim = dwmap.TIM(raw)
        if tim.bpp != 8 or tim.y != 0:
            continue
        for dx in range(0, tim.w * 2, 256):
            page = (tim.x - 384) * 2 // 256 + dx // 256
            pages[page] = (k, dx, tim)
    assert pages, name + ': no reusable 8-bit sprite pages'
    heights = {p: [0] * 255 for p in pages}
    buffers = {k: bytearray(dwmap.TIM(raw).pixels) for k, raw in enumerate(m.tims)}
    chunks = []; needs_black_clut = False
    for piece in spec['pieces']:
        w, h, mode, rows, _ = dwmap.png_read(os.path.join(MOD, 'art', 'foreground', piece['image']), alpha=True)
        assert mode == 'RGBA'
        ox, oy = piece['at']
        strip = piece.get("strip_width", 64)
        band = piece.get("strip_height", 64)
        for top in range(0, h, band):
            for left in range(0, w, strip):
                points = [(x, y) for y in range(top, min(top + band, h))
                          for x in range(left, min(left + strip, w)) if rows[y][x * 4 + 3]]
                groups = [(False, points)]
                if black_index is None:
                    regular = []; black = []
                    for x, y in points:
                        (regular if background_index(ox+x, oy+y) else black).append((x, y))
                    groups = [(False, regular), (True, black)]
                for is_black, group in groups:
                    if not group:
                        continue
                    needs_black_clut |= is_black
                    x0 = min(x for x, y in group); y0 = min(y for x, y in group)
                    x1 = max(x for x, y in group) + 1; y1 = max(y for x, y in group) + 1
                    chunks.append((x1-x0, y1-y0, ox+x0, oy+y0, group, piece, x0, y0, is_black,
                                   piece["at"][0]+left+min(strip,w-left)/2,
                                   piece["at"][1]+top+min(band,h-top)/2))
    cam = Cam(m)
    sprites = []; instances = []
    for w, h, ox, oy, points, piece, x0, y0, is_black, cell_x, cell_y in sorted(chunks, key=lambda c: (-c[1], -c[0], c[3], c[2])):
        choices = [(max(heights[p][x:x+w]), p, x) for p in pages for x in range(256-w)
                   if max(heights[p][x:x+w]) + h <= 255]
        assert choices, name + ': foreground exceeds donor VRAM'
        ty, page, tx = min(choices)
        heights[page][tx:tx+w] = [ty+h] * w
        k, dx, tim = pages[page]
        stride = tim.w * 2
        for x, y in points:
            u, v = ox+x-x0, oy+y-y0
            index = 1 if is_black else background_index(u, v) or black_index
            assert index is not None
            buffers[k][(ty+y-y0)*stride+dx+tx+x-x0] = index
        anchor = piece['depth']
        if 'depth_line' in piece:
            line = piece['depth_line']; cx = cell_x if piece.get('vertical_face') else ox + w / 2
            a, b = next(((a, b) for a, b in zip(line, line[1:]) if a[0] <= cx <= b[0]),
                        (line[0], line[1]) if cx < line[0][0] else (line[-2], line[-1]))
            anchor = (cx, a[1] + (cx-a[0]) * (b[1]-a[1]) / (b[0]-a[0]))
        if piece.get('vertical_face'):
            anchor = (cell_x, anchor[1])
        gx, gz = cam.world(*anchor)
        sort_y = piece.get('sort_y', 0)
        if piece.get('vertical_face'):
            # An upright surface sorts at the height of each texture band.
            # Sorting a whole tall face at ground level lets raised model
            # triangles pierce it; a constant bias can then cover front walkers.
            # Solve the camera projection at this band's centre for world Y.
            vp, bx, by, bz = cam.basis
            rel = (gx-vp[0], -vp[1], gz-vp[2])
            py = sum(by[i]*rel[i] for i in range(3))
            pz = sum(bz[i]*rel[i] for i in range(3))
            sy = (cell_y-m.height*64)/m.projection
            sort_y += round((sy*pz-py)/(by[1]-sy*bz[1]))
        # Model polygons sort at their own height, not just at the actor's feet.
        # A raised face can therefore need a nearer sort plane than its base.
        # This affects ordering only: instance x/y still place the exact cut-out.
        sprites.append(dict(texX=page*256+tx, texY=ty, width=w, height=h,
                            x=gx, y=sort_y, z=gz,
                            clut=16 if is_black else -1, transparency=4))
        instances.append(dict(frames=[len(sprites)-1]+[-1]*7, times=[0]*8, x=ox, y=oy, flag=0))
    assert len(sprites) <= 180, name + ': engine sprite definition limit'
    assert len(instances) <= 188, name + ': engine instance limit'
    for k, pixels in buffers.items():
        raw = bytearray(m.tims[k]); tim = dwmap.TIM(raw)
        offset = 8 + (struct.unpack_from('<I', raw, 8)[0] if tim.flag & 8 else 0) + 12
        raw[offset:offset+len(pixels)] = pixels
        m.tims[k] = bytes(raw)
    if needs_black_clut:
        # Row 484 is in the engine's reserved 8-bit map-sprite CLUT area. Reuse
        # one donor palette block, which otherwise points at background row 480
        # and is deliberately not uploaded by loadMapImage. Black stays black at
        # every hour; all coloured fragments still use the live background CLUT.
        k = min(k for k, _, _ in pages.values())
        raw = bytearray(m.tims[k]); tim = dwmap.TIM(raw)
        assert tim.clut and tim.clut[2:4] == (256, 1)
        struct.pack_into('<4H', raw, 12, 0, 484, 256, 1)
        struct.pack_into('<256H', raw, 20, 0, 0x8000, *([0] * 254))
        m.tims[k] = bytes(raw)
    # Keep the donor's allocation where possible; append only if more fragments are needed.
    m.sprites[:len(sprites)] = sprites
    m.instances[:len(instances)] = instances
    print(f'{name}: {len(spec["pieces"])} foreground objects, {len(instances)} fragments, '
          f'{len(pages)*65536} existing VRAM bytes, MAP {len(m.build())} bytes')
