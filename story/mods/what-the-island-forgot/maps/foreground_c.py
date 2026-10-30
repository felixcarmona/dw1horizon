"""Foreground silhouettes for screens 346–357, using their existing sprite TIM space.

Masks contain only our generated art. At build time each opaque pixel takes the exact
palette index from the finished TFS. Opaque black uses an unused palette entry;
index zero remains transparent. The background and foreground therefore agree
at every palette/time of day, without another quantization. Each object's ground
position controls draw order independently of its image rectangle.
"""
import json
import os
import struct

from mapbase import MOD, Cam, dwmap

DIRECTORY = os.path.join(MOD, 'maps', 'foreground-c')
CUTOUTS = os.path.join(MOD, 'art', 'foreground-c')


def apply(m, screen, background):
    path = os.path.join(DIRECTORY, str(screen) + '.json')
    cfg = json.load(open(path))
    tfs = dwmap.TfsFile(open(background, 'rb').read())
    width, height, pixels = tfs.image_indices(m)
    used = {v for _, tile in tfs.tiles for v in tile}
    unused = sorted(set(range(1, 256)) - used)
    if not unused:
        raise ValueError(f'{screen}: no unused background slot for opaque sprite black')
    black_index = unused[0]
    # Establish the alias before quantizing donor holes: a color used only in
    # those missing tiles must not later be overwritten with black.
    for palette in tfs.cluts:
        palette[black_index] = 0x8000
    with open(background, 'wb') as out:
        out.write(tfs.build())
    # Donors with 7x5 layouts omit five corner tiles to fit the 512 KB
    # load buffer. Render our missing corner art as background-depth sprites,
    # reusing the donor's existing TIM allocation instead of enlarging the TFS.
    missing = [i for i, tile in enumerate(m.tiles) if tile == -1]
    if missing:
        sw, sh, mode, source, _ = dwmap.png_read(os.path.join(MOD, 'art', cfg['source']))
        if (sw, sh) != (width, height) or mode != 'RGB':
            raise ValueError(f'{screen}: background source geometry changed')
        quant = dwmap.Requant(tfs.palette_rgb(0), tfs.cluts[0])
        for tile in missing:
            tx, ty = tile % m.width * 128, tile // m.width * 128
            for yy in range(ty, ty+128):
                for xx in range(tx, tx+128):
                    pixels[yy][xx] = quant(*source[yy][xx*3:xx*3+3])
    cam = Cam(m)
    pages = []
    raws = [bytearray(t) for t in m.tims]
    # Split TIMs at texture-page boundaries; leave a transparent right/bottom guard on cuts.
    for k, raw in enumerate(raws):
        tim = dwmap.TIM(bytes(raw))
        if tim.bpp != 8:
            continue
        if tim.y != 0:
            raise ValueError(f'{screen}: unexpected sprite TIM Y {tim.y}')
        start = 8 + struct.unpack_from('<I', raw, 8)[0] + 12
        stride = tim.w * 2
        for x in range(0, stride, 256):
            pages.append(dict(k=k, offset=start, stride=stride, x=x, y=0,
                              w=min(256, stride-x), h=tim.h, tex=(tim.x-384)*2))
    m.sprites = []
    m.instances = []
    cuts = []
    # 63 texels plus one guard texel fit four rectangles across a page.
    side = 31 if screen == 354 else 48 if screen == 348 else 63
    # Connected machinery can be selected by more than one SAM prompt.
    # Store shared texels once; the manifest prioritizes their physical owner.
    claimed = set()
    priority = {name: i for i, name in enumerate(cfg.get('atlas_priority', []))}
    objects = sorted(cfg['pieces'], key=lambda obj: priority.get(obj['name'], len(priority)))
    for obj in objects:
        w, h, mode, rows, _ = dwmap.png_read(os.path.join(CUTOUTS, obj['png']), alpha=True)
        if mode != 'RGBA':
            raise ValueError(f'{screen}: foreground must be RGBA')
        ox, oy = obj['at']
        gx, gz = cam.world(*obj['depth_px'])
        for y in range(0, h, side):
            for x in range(0, w, side):
                points = [(xx, yy) for yy in range(y, min(y+side, h))
                          for xx in range(x, min(x+side, w)) if rows[yy][xx*4+3] >= 128
                          and (ox+xx, oy+yy) not in claimed]
                claimed.update((ox+xx, oy+yy) for xx, yy in points)
                if not points:
                    continue
                left = min(p[0] for p in points)
                top = min(p[1] for p in points)
                right = max(p[0] for p in points)+1
                bottom = max(p[1] for p in points)+1
                cuts.append((right-left, bottom-top, left, top, points, ox, oy, gx, gz, obj['name']))
    # These opaque rectangles fill donor holes at the farthest draw order;
    # they are background tiles, never foreground occluders.
    for tile in missing:
        ox, oy = tile % m.width * 128, tile // m.width * 128
        for y in range(0, 128, 63):
            for x in range(0, 128, 63):
                points = [(xx, yy) for yy in range(y, min(y+63, 128)) for xx in range(x, min(x+63, 128))]
                cuts.append((min(63, 128-x), min(63, 128-y), x, y, points, ox, oy, 0, 0, '__background'))
    for w, h, left, top, points, ox, oy, gx, gz, name in sorted(cuts, key=lambda q: (-max(q[0], q[1]), -q[0]*q[1])):
        choices = [(p['w']*p['h'], i) for i, p in enumerate(pages) if w+1 <= p['w'] and h+1 <= p['h']]
        if not choices:
            raise ValueError(f'{screen}: existing sprite VRAM exhausted at {name} ({w}x{h}); total padded area {sum((q[0]+1)*(q[1]+1) for q in cuts)}, cuts {len(cuts)}')
        _, i = min(choices)
        p = pages.pop(i)
        x, y = p['x'], p['y']
        for yy in range(p['y'], p['y']+h+1):
            start = p['offset']+yy*p['stride']+p['x']
            raws[p['k']][start:start+w+1] = bytes(w+1)
        for xx, yy in points:
            u, v = ox+xx, oy+yy
            if not (0 <= u < width and 0 <= v < height):
                raise ValueError(f'{screen}: cut-out outside background')
            raws[p['k']][p['offset']+(y+yy-top)*p['stride']+x+xx-left] = pixels[v][u] or black_index
        idx = len(m.sprites)
        m.sprites.append(dict(texX=p['tex']+x, texY=y, width=w, height=h,
                              x=gx, y=10000 if name == '__background' else 0, z=gz, clut=-1, transparency=4))
        m.instances.append(dict(frames=[idx]+[-1]*7, times=[0]*8, x=ox+left, y=oy+top, flag=0))
        # Maximal free rectangles: split all intersecting rectangles, prune contained ones.
        pages.append(p)
        next_pages = []
        ax, ay, aw, ah = p['x'], p['y'], w+1, h+1
        for free in pages:
            fx, fy, fw, fh = (free[t] for t in ('x', 'y', 'w', 'h'))
            if free['k'] != p['k'] or ax >= fx+fw or ax+aw <= fx or ay >= fy+fh or ay+ah <= fy:
                next_pages.append(free)
                continue
            if ax > fx: next_pages.append(dict(free, w=ax-fx))
            if ax+aw < fx+fw: next_pages.append(dict(free, x=ax+aw, w=fx+fw-ax-aw))
            if ay > fy: next_pages.append(dict(free, h=ay-fy))
            if ay+ah < fy+fh: next_pages.append(dict(free, y=ay+ah, h=fy+fh-ay-ah))
        pages = [q for j, q in enumerate(next_pages) if not any(
            i != j and r['k'] == q['k'] and r['x'] <= q['x'] and r['y'] <= q['y']
            and r['x']+r['w'] >= q['x']+q['w'] and r['y']+r['h'] >= q['y']+q['h']
            and (r != q or i < j) for i, r in enumerate(next_pages))]
    if len(m.sprites) > 180 or len(m.instances) > 188:
        raise ValueError(f'{screen}: sprite table limit exceeded')
    m.tims = [bytes(t) for t in raws]
    for change in cfg.get('collision_tiles', []):
        tx, tz = change['tile']
        if m.collision[tz*100+tx] != change['was']:
            raise ValueError(f'{screen}: collision base changed at {tx},{tz}')
        m.collision[tz*100+tx] = change['value']
    print(f'{screen}: {len(cfg["pieces"])} foreground pieces, {len(cuts)} rectangles; '
          f'{sum(map(len, m.tims))} existing TIM bytes, no extra VRAM')
