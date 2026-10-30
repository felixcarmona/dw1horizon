"""Build foreground cutouts from our RGBA art using the background's exact palette indices.

The manifest stores pixel placement, a ground-plane depth anchor (or a locally sorted
near face), and individually reviewed collision cells. No original disc pixels are shipped.
Transparent entries are reserved without changing the rendered backgrounds.
Texture uploads stay inside the donor's existing 384..767 x 0..255 sprite VRAM area.
"""
import json
import os
import struct

from mapbase import Cam, MOD, check_arrivals, dwmap


def _new_tim(x, palette, width=128, height=256):
    clut = struct.pack('<I4H256H', 524, 0, 480, 256, 1, *palette)
    image = struct.pack('<I4H', 12 + width * height * 2, x, 0, width, height) + bytes(width * height * 2)
    return struct.pack('<II', 16, 9) + clut + image


def apply(m, name, tfs_path):
    """Apply a screen's explicit foreground manifest after importing its TFS."""
    manifest = os.path.join(MOD, 'maps', 'district-foreground', name + '.json')
    if not os.path.isfile(manifest):
        return
    data = json.load(open(manifest))
    tfs = dwmap.TfsFile(open(tfs_path, 'rb').read())
    transparent = data.get('transparent', 0)
    if data.get('reserve_transparency'):
        replacement = data.get('replace_index')
        table = bytearray(range(256))
        if replacement is not None:
            assert all(c[transparent] == c[replacement] for c in tfs.cluts)
            table[transparent] = replacement
            tfs.tiles = [(pre, px.translate(table)) for pre, px in tfs.tiles]
            for k, raw in enumerate(m.tims):
                tim = dwmap.TIM(raw)
                if tim.bpp != 8:
                    continue
                assert all(sp['clut'] == -1 for inst in m.instances if inst['flag'] != 1
                           for f in inst['frames'] if f >= 0
                           for sp in [m.sprites[f]] if sp['clut'] < 0 or sp['clut'] >= 16)
                off = 8 + (struct.unpack_from('<I', raw, 8)[0] if tim.flag & 8 else 0) + 12
                raw = bytearray(raw)
                raw[off:off + len(tim.pixels)] = tim.pixels.translate(table)
                m.tims[k] = bytes(raw)
        else:
            assert all(transparent not in px for _, px in tfs.tiles)
            assert not m.tims
        for c in tfs.cluts:
            c[transparent] = 0
        open(tfs_path, 'wb').write(tfs.build())
    assert all(c[transparent] == 0 for c in tfs.cluts), name
    W, H, bg = tfs.image_indices(m)
    # Keep every original transparent CLUT entry intact. A foreground pixel that
    # becomes black in ANY time-of-day palette needs a private nonzero alias;
    # changing the original entry would make old animation padding opaque.
    images = {}
    foreground_colors = set()
    for piece in data['pieces']:
        png = os.path.join(MOD, 'art', 'foreground', piece['png'])
        w, h, mode, rows, pal = dwmap.png_read(png, alpha=True)
        assert mode == 'RGBA'
        x0, y0 = piece['at']
        assert 0 <= x0 < x0 + w <= W and 0 <= y0 < y0 + h <= H
        images[piece['png']] = (w, h, rows)
        for y in range(h):
            for x in range(w):
                if rows[y][4 * x + 3] >= 128:
                    foreground_colors.add(tuple(c[bg[y0 + y][x0 + x]] for c in tfs.cluts))
    reserved = {transparent}
    aliases = {}
    for colors in sorted(foreground_colors):
        if all(colors):
            continue
        opaque = tuple(value or 0x8000 for value in colors)
        alias = next((i for i in range(256) if
                      tuple(c[i] for c in tfs.cluts) == opaque), None)
        if alias is None:
            used = {v for _, px in tfs.tiles for v in px}
            used.update(v for raw in m.tims if dwmap.TIM(raw).bpp == 8
                        for v in dwmap.TIM(raw).pixels)
            alias = next((i for i in range(256) if i not in reserved and i not in used), None)
            if alias is None:
                duplicate = next(((i, j) for i in range(256) if i not in reserved
                                  for j in range(i) if all(c[i] == c[j] for c in tfs.cluts)), None)
                if duplicate is None:
                    raise ValueError(f'{name}: no palette entry for opaque foreground {colors}')
                alias, replacement = duplicate
                table = bytearray(range(256))
                table[alias] = replacement
                tfs.tiles = [(pre, px.translate(table)) for pre, px in tfs.tiles]
                for k, raw in enumerate(m.tims):
                    tim = dwmap.TIM(raw)
                    if tim.bpp != 8:
                        continue
                    p = 8 + (struct.unpack_from('<I', raw, 8)[0] if tim.flag & 8 else 0) + 12
                    raw = bytearray(raw)
                    raw[p:p + len(tim.pixels)] = tim.pixels.translate(table)
                    m.tims[k] = bytes(raw)
            for c, value in zip(tfs.cluts, opaque):
                c[alias] = value
        reserved.add(alias)
        aliases[colors] = alias
    assert all(c[transparent] == 0 for c in tfs.cluts)
    W, H, bg = tfs.image_indices(m)
    open(tfs_path, 'wb').write(tfs.build())
    cam = Cam(m)
    for edit in data['collision']:
        tx, tz = edit['tile']
        assert m.collision[tz * 100 + tx] == edit['before'], (name, edit)
        m.collision[tz * 100 + tx] = edit['after']
    check_arrivals(m, name)
    for spec in data.get('new_pages', []):
        x = spec['x']
        assert all(not (dwmap.TIM(t).x <= x < dwmap.TIM(t).x + dwmap.TIM(t).w) for t in m.tims)
        m.tims.insert(sum(dwmap.TIM(t).bpp == 8 for t in m.tims), _new_tim(x, tfs.cluts[0], spec['width'], spec['height']))
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
        w, h, rows = images[piece['png']]
        x0, y0 = piece['at']
        # A narrow strip on a long sloped shelf has its own depth. This avoids one
        # near end covering characters standing in front of a more distant end.
        strip_width = piece.get('strip_width', 16)
        assert 1 <= strip_width <= 16
        strip_height = piece.get('strip_height', 256)
        assert 1 <= strip_height <= 256
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
                pix = [bytearray([transparent]) * cw for _ in range(ch)]
                for x, y in points:
                    value = bg[y0 + y][x0 + x]
                    colors = tuple(c[value] for c in tfs.cluts)
                    pix[y - ya][x - xa] = aliases.get(colors, value)
                # Width is padded with transparent pixels to the GPU's 2-pixel alignment.
                if piece.get('depth') is not None:
                    depth = piece['depth']
                else:
                    depth = [x0 + (xa + xb) / 2, y0 + yb]
                gx, gz = cam.world(*depth)
                gy = 0
                if piece.get('vertical_face'):
                    # A tall near face has depth at its height, not only at its feet.
                    # Evaluate each band's height over the reviewed ground base
                    # so actor limbs cannot pierce the upright surface.
                    gx, gz = cam.world(x0 + (xa + xb) / 2, depth[1])
                    vp, bx, by, bz = cam.basis
                    relative = [gx - vp[0], -vp[1], gz - vp[2]]
                    cy = (y0 + (ya + yb) / 2 - cam.H / 2) / m.projection
                    ey = sum(a * b for a, b in zip(relative, by))
                    ez = sum(a * b for a, b in zip(relative, bz))
                    gy = round((cy * ez - ey) / (by[1] - cy * bz[1]))
                chunks.append(dict(w=cw, h=ch, at=[x0 + xa, y0 + ya],
                                   world=[gx, gy, gz], pixels=pix))
    for chunk in sorted(chunks, key=lambda c: (-c['h'], -c['w'])):
        w, h = chunk['w'], chunk['h']
        placed = None
        for page in pages:
            # At an exact 256-pixel page edge the engine subtracts one from
            # BOTH UV spans. That stretches thin cut-outs and their alpha.
            # Leave a texel of guard space so buildMapOverlayPrim uses its
            # ordinary, pixel-for-pixel UV branch.
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
        gx, gy, gz = chunk['world']
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
    print(f'{name}: {len(data["pieces"])} foreground pieces, {len(chunks)} strips, '
          f'{len(m.sprites)}/180 definitions, {len(m.instances)}/188 instances')
