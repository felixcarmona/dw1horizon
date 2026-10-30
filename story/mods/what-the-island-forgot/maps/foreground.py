"""Build foreground cutouts from our RGBA art using the background palette.

The manifest stores pixel placement, a ground-plane depth anchor (or a locally sorted
near face), and individually reviewed collision cells. No original disc pixels are shipped.
Texture uploads stay inside the donor's existing 384..767 x 0..255 sprite VRAM area.
"""
import json
import os
import struct

from mapbase import Cam, MOD, check_arrivals, dwmap


def _new_tim(x, palette):
    clut = struct.pack('<I4H256H', 524, 0, 480, 256, 1, *palette)
    image = struct.pack('<I4H', 65548, x, 0, 128, 256) + bytes(65536)
    return struct.pack('<II', 16, 9) + clut + image


def _fill_background_tiles(m, tfs, name):
    """Fill donor holes from our art without changing any existing tile or colour."""
    w, h, mode, rows, _ = dwmap.png_read(os.path.join(MOD, 'art', name + '.png'))
    assert (w, h, mode) == (m.width * 128, m.height * 128, 'RGB'), name
    used = sorted({index for _, pixels in tfs.tiles for index in pixels})
    palette = tfs.palette_rgb()
    nearest = dwmap.Requant([palette[i] for i in used])
    old = iter(tfs.tiles)
    tiles = []
    for i, tile_id in enumerate(m.tiles):
        if tile_id != -1:
            tiles.append(next(old))
            continue
        col, row = i % m.width, i // m.width
        pixels = bytearray()
        for y in range(row * 128, (row + 1) * 128):
            for x in range(col * 128, (col + 1) * 128):
                pixels.append(used[nearest(*rows[y][3 * x:3 * x + 3])])
        tiles.append([struct.pack('<HH', col * 64, row * 128), pixels])
    assert next(old, None) is None
    assert len(tiles) <= 35, name
    tfs.tiles = tiles
    m.tiles = list(range(len(tiles)))


def apply(m, name, tfs_path):
    """Apply a screen's explicit foreground manifest after importing its TFS."""
    manifest = os.path.join(MOD, 'maps', 'foreground', name + '.json')
    if not os.path.isfile(manifest):
        return
    data = json.load(open(manifest))
    tfs = dwmap.TfsFile(open(tfs_path, 'rb').read())
    if data.get('fill_background_tiles'):
        _fill_background_tiles(m, tfs, name)
    W, H, bg = tfs.image_indices(m)
    cam = Cam(m)
    # Transparent padding must resolve to 0x0000, while black inside an object
    # must resolve to opaque 0x8000. Reserve an unused background index so the
    # shared day/evening/night CLUTs preserve both without changing the art.
    assert all(palette[0] == 0 for palette in tfs.cluts), name
    opaque_black = None
    if data['pieces']:
        used = {index for _, pixels in tfs.tiles for index in pixels}
        opaque_black = next((i for i in range(1, 256) if i not in used), None)
        if opaque_black is None:
            raise ValueError(f'{name}: no unused palette entry for opaque black')
        for palette in tfs.cluts:
            palette[opaque_black] = 0x8000
        with open(tfs_path, 'wb') as out:
            out.write(tfs.build())
    for edit in data['collision']:
        tx, tz = edit['tile']
        assert m.collision[tz * 100 + tx] == edit['before'], (name, edit)
        m.collision[tz * 100 + tx] = edit['after']
    check_arrivals(m, name)
    for x in data.get('new_pages', []):
        assert all(not (dwmap.TIM(t).x <= x < dwmap.TIM(t).x + dwmap.TIM(t).w) for t in m.tims)
        m.tims.insert(sum(dwmap.TIM(t).bpp == 8 for t in m.tims), _new_tim(x, tfs.cluts[0]))
    m.has_sprites = bool(m.tims)
    # All active animation frames are reserved. Scrubbed donor definitions are harmless;
    # reuse their hidden slots before growing the engine's fixed definition/instance tables.
    active = {f for i in m.instances if i['flag'] != 1 for f in i['frames'] if f >= 0}
    free_defs = [i for i in range(len(m.sprites)) if i not in active]
    free_instances = [i for i, inst in enumerate(m.instances) if inst['flag'] == 1]
    # A donor TIM may span several GPU pages (TUNN04 has one 768-pixel
    # image); another may cover half a page. Pack in GPU page coordinates,
    # then copy pixels back into exactly the donor's existing TIM layout.
    vram = [bytearray(768) for _ in range(256)]
    available = [bytearray(768) for _ in range(256)]
    for raw in m.tims:
        tim = dwmap.TIM(raw)
        assert 384 <= tim.x < tim.x + tim.w <= 768 and 0 <= tim.y < tim.y + tim.h <= 256
        if tim.bpp != 8:
            continue
        left, width = (tim.x - 384) * 2, tim.w * 2
        for y in range(tim.h):
            vram[tim.y + y][left:left + width] = tim.pixels[y * width:(y + 1) * width]
            available[tim.y + y][left:left + width] = bytes([1]) * width
    for tim in map(dwmap.TIM, m.tims):
        if tim.bpp == 8:
            continue
        left, width = (tim.x - 384) * 2, tim.w * 2
        for y in range(tim.y, tim.y + tim.h):
            available[y][left:left + width] = bytes(width)
    pages = []
    for page in range(3):
        occupied = [sum((1 << x) for x in range(256) if not available[y][page * 256 + x])
                    for y in range(256)]
        for idx in active:
            sp = m.sprites[idx]
            if 0 <= sp['clut'] < 16 or sp['texX'] // 256 != page:
                continue
            left = sp['texX'] % 256
            for y in range(sp['texY'], sp['texY'] + sp['height']):
                occupied[y] |= ((1 << sp['width']) - 1) << left
        pixels = bytearray(b''.join(row[page * 256:(page + 1) * 256] for row in vram))
        pages.append(dict(x=384 + page * 128, occupied=occupied, pixels=pixels))
    chunks = []
    for piece in data['pieces']:
        png = os.path.join(MOD, 'art', 'foreground', piece['png'])
        w, h, mode, rows, pal = dwmap.png_read(png, alpha=True)
        assert mode == 'RGBA'
        x0, y0 = piece['at']
        assert 0 <= x0 < x0 + w <= W and 0 <= y0 < y0 + h <= H
        # A narrow strip on a long sloped shelf has its own depth. This avoids one
        # near end covering characters standing in front of a more distant end.
        strip_width = piece.get('strip_width', 32)
        strip_height = piece.get('strip_height', 255)
        for sx in range(0, w, strip_width):
            for sy in range(0, h, strip_height):
                sw, sh = min(strip_width, w - sx), min(strip_height, h - sy)
                points = [(x, y) for y in range(sy, sy + sh) for x in range(sx, sx + sw)
                          if rows[y][4 * x + 3] >= 128]
                if not points:
                    continue
                xa, ya = min(x for x, y in points), min(y for x, y in points)
                xb, yb = max(x for x, y in points) + 1, max(y for x, y in points) + 1
                cw = (xb - xa + 1) // 2 * 2
                ch = yb - ya
                pix = [bytearray(cw) for _ in range(ch)]
                for x, y in points:
                    index = bg[y0 + y][x0 + x]
                    pix[y - ya][x - xa] = (opaque_black if tfs.cluts[0][index] == 0 else index)
                # Width is padded with transparent pixels to the GPU's 2-pixel alignment.
                if piece.get('depth') is not None:
                    depth = piece['depth']
                else:
                    depth = [x0 + (xa + xb) / 2, y0 + yb]
                chunks.append(dict(w=cw, h=ch, at=[x0 + xa, y0 + ya], depth=depth, pixels=pix,
                                   vertical_face=piece.get('vertical_face', False),
                                   centre=[x0 + sx + sw / 2, y0 + sy + sh / 2]))
    for chunk in sorted(chunks, key=lambda c: (-c['h'], -c['w'])):
        w, h = chunk['w'], chunk['h']
        placed = None
        for page in pages:
            # The engine shortens UVs by one when either far edge reaches 256.
            # Leave the last texel unused so silhouette pixels stay aligned.
            for y in range(256 - h):
                used = 0
                for row in page['occupied'][y:y + h]:
                    used |= row
                for x in range(0, 256 - w, 2):
                    bits = ((1 << w) - 1) << x
                    if used & bits:
                        continue
                    for yy in range(y, y + h):
                        page['occupied'][yy] |= bits
                    for yy, line in enumerate(chunk['pixels']):
                        off = (y + yy) * 256 + x
                        page['pixels'][off:off + w] = line
                    placed = page, x, y
                    break
                if placed:
                    break
            if placed:
                break
        if placed is None:
            raise ValueError(f'{name}: foreground exceeds donor sprite VRAM; shrink/split masks')
        page, x, y = placed
        depth = chunk['depth']
        if chunk['vertical_face']:
            depth = (chunk['centre'][0], depth[1])
        gx, gz = cam.world(*depth)
        sort_y = 0
        if chunk['vertical_face']:
            # Match the upright rock bands used by foreground_depth_b: raised
            # actor polygons must sort against the face at their own height.
            vp, bx, by, bz = cam.basis
            rel = (gx - vp[0], -vp[1], gz - vp[2])
            py = sum(by[i] * rel[i] for i in range(3))
            pz = sum(bz[i] * rel[i] for i in range(3))
            sy = (chunk['centre'][1] - m.height * 64) / m.projection
            sort_y = round((sy * pz - py) / (by[1] - sy * bz[1]))
        sp = dict(texX=(page['x'] - 384) * 2 + x, texY=y, width=w, height=h,
                  x=gx, y=sort_y, z=gz, clut=-1, transparency=4)
        if free_defs:
            idx = free_defs.pop(0)
            m.sprites[idx] = sp
        else:
            idx = len(m.sprites)
            m.sprites.append(sp)
        inst = dict(frames=[idx] + [-1] * 7, times=[0] * 8,
                    x=chunk['at'][0], y=chunk['at'][1], flag=0)
        if free_instances:
            m.instances[free_instances.pop(0)] = inst
        else:
            m.instances.append(inst)
    for page in pages:
        left = (page['x'] - 384) * 2
        for y in range(256):
            vram[y][left:left + 256] = page['pixels'][y * 256:(y + 1) * 256]
    for k, old in enumerate(m.tims):
        tim = dwmap.TIM(old)
        if tim.bpp != 8:
            continue
        raw = bytearray(old)
        p = 8 + (struct.unpack_from('<I', old, 8)[0] if tim.flag & 8 else 0) + 12
        left, width = (tim.x - 384) * 2, tim.w * 2
        pix = b''.join(row[left:left + width] for row in vram[tim.y:tim.y + tim.h])
        raw[p:p + len(pix)] = pix
        m.tims[k] = bytes(raw)
    assert len(m.sprites) <= 180 and len(m.instances) <= 188, name
    assert len(m.build()) <= 0x80000, name
    print(f'{name}: {len(data["pieces"])} foreground pieces, {len(chunks)} strips, '
          f'{len(m.sprites)}/180 definitions, {len(m.instances)}/188 instances')
