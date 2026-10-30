"""Build foreground cutouts from our RGBA art using the background's exact palette indices.

The manifest stores pixel placement, a ground-plane depth anchor (or a locally sorted
near face), and individually reviewed collision cells. No original disc pixels are shipped.
Texture uploads stay inside the donor's existing 384..767 x 0..255 sprite VRAM area.
"""
import json
import os
import struct

from mapbase import Cam, MOD, check_arrivals, dwmap


def apply(m, name, tfs_path):
    """Apply a screen's explicit foreground manifest after importing its TFS."""
    manifest = os.path.join(MOD, 'maps', 'foreground-depth-a', name + '.json')
    if not os.path.isfile(manifest):
        return
    data = json.load(open(manifest))
    tfs = dwmap.TfsFile(open(tfs_path, 'rb').read())
    W, H, bg = tfs.image_indices(m)
    # Transparent pixels must map to colour 0x0000. Opaque black inside an
    # object needs 0x8000 instead, even though both decode to the same RGB.
    # Reuse an alias valid at every time of day, or reserve a background-unused
    # index. This changes no displayed background pixel and needs no new CLUT.
    black = next((i for i in range(1, 256)
                  if all(c[i] == 0x8000 for c in tfs.cluts)), None)
    needs_black = False
    cam = Cam(m)
    for edit in data['collision']:
        tx, tz = edit['tile']
        assert m.collision[tz * 100 + tx] == edit['before'], (name, edit)
        m.collision[tz * 100 + tx] = edit['after']
    check_arrivals(m, name)
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
    bands = data.get('depth_planes')
    for piece in data['pieces']:
        png = os.path.join(MOD, 'art', 'foreground-depth-a', piece['png'])
        w, h, mode, rows, pal = dwmap.png_read(png, alpha=True)
        assert mode == 'RGBA'
        x0, y0 = piece['at']
        assert 0 <= x0 < x0 + w <= W and 0 <= y0 < y0 + h <= H
        # A narrow strip on a long sloped shelf has its own depth. This avoids one
        # near end covering characters standing in front of a more distant end.
        strip_w, strip_h = (bands['width'], bands['height']) if bands else (32, 255)
        for sx in range(0, w, strip_w):
            # Ground contact belongs to the whole column, not to each elevated band.
            column_bottom = max((y for y in range(h) for x in range(sx, min(w, sx + strip_w))
                                 if rows[y][4 * x + 3] >= 128), default=-1)
            for sy in range(0, h, strip_h):
                sw, sh = min(strip_w, w - sx), min(strip_h, h - sy)
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
                    c = bg[y0 + y][x0 + x]
                    if c == 0:
                        needs_black = True
                        if black is None:
                            used = {v for row in bg for v in row}
                            for idx in active:
                                sp = m.sprites[idx]
                                if sp['clut'] != -1:
                                    continue
                                for yy in range(sp['texY'], sp['texY'] + sp['height']):
                                    used.update(vram[yy][sp['texX']:sp['texX'] + sp['width']])
                            black = next(i for i in range(1, 256) if i not in used)
                            for clut in tfs.cluts:
                                clut[black] = 0x8000
                        c = black
                    pix[y - ya][x - xa] = c
                # Width is padded with transparent pixels to the GPU's 2-pixel alignment.
                if piece.get('depth') is not None:
                    depth = piece['depth']
                else:
                    depth = [x0 + (xa + xb) / 2, y0 + (column_bottom + 1 if bands else yb)]
                world = None
                if bands:
                    # Intersect the band's viewing ray with a vertical surface through
                    # the prop's ground contact. A whole tall quad sorted at its base
                    # sits behind nearer actor head/torso polygons and lets them pierce it.
                    gx, gz = cam.world(*depth)
                    vp, bx, by, bz = cam.basis
                    u, v = x0 + (xa + xb) / 2, y0 + (ya + yb) / 2
                    cx, cy = (u - W / 2) / m.projection, (v - H / 2) / m.projection
                    ray = [bz[i] + bx[i] * cx + by[i] * cy for i in range(3)]
                    den = bz[0] * ray[0] + bz[2] * ray[2]
                    distance = (bz[0] * (gx - vp[0]) + bz[2] * (gz - vp[2])) / den
                    world = [round(vp[i] + distance * ray[i]) for i in range(3)]
                    assert all(-32768 <= n <= 32767 for n in world), (name, piece['name'])
                chunks.append(dict(w=cw, h=ch, at=[x0 + xa, y0 + ya], depth=depth, world=world, pixels=pix))
    for chunk in sorted(chunks, key=lambda c: (-c['h'], -c['w'])):
        w, h = chunk['w'], chunk['h']
        placed = None
        for page in pages:
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
        if chunk['world']:
            gx, gy, gz = chunk['world']
        else:
            gx, gz = cam.world(*chunk['depth'])
            gy = 0
        sp = dict(texX=(page['x'] - 384) * 2 + x, texY=y, width=w, height=h,
                  x=gx, y=gy, z=gz, clut=-1, transparency=4)
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
    if needs_black:
        assert all(c[0] == 0 and c[black] == 0x8000 for c in tfs.cluts), name
        with open(tfs_path, 'wb') as f:
            f.write(tfs.build())
    print(f'{name}: {len(data["pieces"])} foreground pieces, {len(chunks)} strips, '
          f'{len(m.sprites)}/180 definitions, {len(m.instances)}/188 instances')
