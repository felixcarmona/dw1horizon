"""Build foreground cutouts from our RGBA art using the background's exact palette colors.

The manifest stores pixel placement, a ground-plane depth anchor (or a locally sorted
near face), and individually reviewed collision cells. No original disc pixels are shipped.
Texture uploads stay inside the donor's existing 384..767 x 0..255 sprite VRAM area.
"""
import json
import os
import struct

from mapbase import Cam, MOD, check_arrivals, dwmap


def _new_tim(x, palette, width=256, height=256):
    clut = struct.pack('<I4H256H', 524, 0, 480, 256, 1, *palette)
    assert width % 2 == 0 and 0 < width <= 256 and 0 < height <= 256
    image = struct.pack('<I4H', 12 + width * height, x, 0, width // 2, height) + bytes(width * height)
    return struct.pack('<II', 16, 9) + clut + image


def apply(m, name, tfs_path):
    """Apply a screen's explicit foreground manifest after importing its TFS."""
    manifest = os.path.join(MOD, 'maps', 'foreground', name + '.json')
    if not os.path.isfile(manifest):
        return
    data = json.load(open(manifest))
    tfs = dwmap.TfsFile(open(tfs_path, 'rb').read())
    W, H, bg = tfs.image_indices(m)
    cam = Cam(m)
    for edit in data['collision']:
        tx, tz = edit['tile']
        assert m.collision[tz * 100 + tx] == edit['before'], (name, edit)
        m.collision[tz * 100 + tx] = edit['after']
    check_arrivals(m, name)
    for page in data.get('new_pages', []):
        x = page['x'] if isinstance(page, dict) else page
        width = page.get('width', 256) if isinstance(page, dict) else 256
        height = page.get('height', 256) if isinstance(page, dict) else 256
        assert all(not (dwmap.TIM(t).x <= x < dwmap.TIM(t).x + dwmap.TIM(t).w) for t in m.tims)
        m.tims.insert(sum(dwmap.TIM(t).bpp == 8 for t in m.tims), _new_tim(x, tfs.cluts[0], width, height))
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
        # buildMapOverlayPrim shrinks BOTH UV extents at a page edge. Reserve
        # that edge so every opaque art pixel keeps its exact one-to-one sample.
        occupied = [row | (3 << 254) for row in occupied]
        occupied[255] = (1 << 256) - 1
        pixels = bytearray(b''.join(row[page * 256:(page + 1) * 256] for row in vram))
        pages.append(dict(x=384 + page * 128, occupied=occupied, pixels=pixels))
    # Background index 0 displays black, but a sprite treats it as transparent.
    # Reuse an opaque-black background entry when it stays black at every time
    # of day. Otherwise a sparse second sprite uses a fixed opaque-black CLUT.
    black_alias = next((i for i in range(1, 256)
                        if all(pal[i] == 0x8000 for pal in tfs.cluts)), None)
    sprite_palette = None
    remap = {}
    if len(tfs.cluts) == 1 and black_alias is None:
        # Interiors have a fixed palette. A duplicate entry supplies opaque
        # black without a second sprite or any changed background bytes.
        pal = tfs.cluts[0]
        spare, same = next((i, j) for i in range(255, 0, -1)
                           for j in range(1, i) if pal[i] == pal[j])
        sprite_palette = list(pal)
        sprite_palette[spare] = 0x8000
        remap = {i: spare for i, color in enumerate(pal) if color == 0}
        remap[spare] = same
    chunks = []
    black_chunks = []
    for piece in data['pieces']:
        png = os.path.join(MOD, 'art', 'foreground', piece['png'])
        w, h, mode, rows, pal = dwmap.png_read(png, alpha=True)
        assert mode == 'RGBA'
        x0, y0 = piece['at']
        assert 0 <= x0 < x0 + w <= W and 0 <= y0 < y0 + h <= H
        # A narrow strip on a long sloped shelf has its own depth. This avoids one
        # near end covering characters standing in front of a more distant end.
        # Height bands are opt-in for a demonstrated surface-ordering defect.
        bands = piece.get('depth_planes')
        strip_w, strip_h = (bands['width'], bands['height']) if bands else (16, 240)
        for sx in range(0, w, strip_w):
            column_bottom = max((y for y in range(h)
                                 for x in range(sx, min(w, sx + strip_w))
                                 if rows[y][4 * x + 3] >= 128), default=-1) if bands else -1
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
                    color = bg[y0 + y][x0 + x]
                    pix[y - ya][x - xa] = remap.get(color, color) if sprite_palette else color or (black_alias or 0)
                # Width is padded with transparent pixels to the GPU's 2-pixel alignment.
                if piece.get('depth_line'):
                    (ax, ay), (bx, by) = piece['depth_line']
                    center = x0 + (xa + xb - 1) // 2
                    fraction = max(0, min(1, (center - ax) / (bx - ax)))
                    depth = [center, ay + fraction * (by - ay)]
                elif piece.get('depth') is not None:
                    depth = piece['depth']
                else:
                    center = (xa + xb - 1) // 2
                    edge = max(y for x, y in points if x == center) + 1 if any(x == center for x, y in points) else yb
                    depth = [x0 + center, y0 + (column_bottom + 1 if bands else edge)]
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
                chunks.append(dict(world=world, w=cw, h=ch, at=[x0 + xa, y0 + ya], depth=depth, pixels=pix, clut=16 if sprite_palette else -1))
                if black_alias is None and sprite_palette is None:
                    black = {(x, y) for x, y in points if bg[y0 + y][x0 + x] == 0}
                    # Small sparse patches keep the extra texture area bounded.
                    for bx in range(sx, sx + sw, 16):
                        for by in range(sy, sy + sh, 8):
                            bp = [(x, y) for x, y in black if bx <= x < bx + 16 and by <= y < by + 8]
                            if not bp:
                                continue
                            lx, ly = min(x for x, y in bp), min(y for x, y in bp)
                            rx, ry = max(x for x, y in bp) + 1, max(y for x, y in bp) + 1
                            bw, bh = (rx - lx + 1) // 2 * 2, ry - ly
                            pixels = [bytearray(bw) for _ in range(bh)]
                            for x, y in bp:
                                pixels[y - ly][x - lx] = 1
                            black_chunks.append(dict(w=bw, h=bh, at=[x0 + lx, y0 + ly],
                                                     depth=depth, world=world, pixels=pixels, clut=16))
    chunks += black_chunks
    for chunk in sorted(chunks, key=lambda c: (-c['h'], -c['w'])):
        w, h = chunk['w'], chunk['h']
        placed = None
        for page in pages:
            for y in range(257 - h):
                used = 0
                for row in page['occupied'][y:y + h]:
                    used |= row
                for x in range(0, 257 - w, 2):
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
        gx, gz = cam.world(*chunk['depth'])
        gx, gy, gz = chunk.get('world') or (gx, 0, gz)
        sp = dict(texX=(page['x'] - 384) * 2 + x, texY=y, width=w, height=h,
                  x=gx, y=gy, z=gz, clut=chunk['clut'], transparency=4)
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
    if black_chunks or sprite_palette:
        # Row 484 is the engine's first extra 8-bit sprite CLUT (clut=16).
        # Background day/night updates use 480; 4-bit sprite CLUTs use 486.
        assert not any(m.sprites[i]['clut'] == 16 for i in active), name
        k = next(k for k, raw in enumerate(m.tims) if dwmap.TIM(raw).bpp == 8)
        raw = bytearray(m.tims[k])
        assert dwmap.TIM(raw).clut[:4] == (0, 480, 256, 1)
        struct.pack_into('<H', raw, 14, 484)
        struct.pack_into('<256H', raw, 20, *(sprite_palette or [0, 0x8000] + [0] * 254))
        m.tims[k] = bytes(raw)
    assert len(m.sprites) <= 180 and len(m.instances) <= 188, name
    assert len(m.build()) <= 0x80000, name
    print(f'{name}: {len(data["pieces"])} foreground pieces, {len(chunks)} strips, '
          f'{len(m.sprites)}/180 definitions, {len(m.instances)}/188 instances')
