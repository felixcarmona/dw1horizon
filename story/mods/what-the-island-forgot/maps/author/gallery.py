#!/usr/bin/env python3
"""The Galleries arc's screens (and, with GALLERY_SET=district, File City's new district's) from one description each (maps/author/<set>/<name>.json): the guide for the
generator and, once the art exists, the map data (collision, exits) and the zones image. Run by hand (needs numpy,
cv2):

    python3 author/gallery.py guide  NAME OUT.png      the grey layout guide at the screen's camera (the design in world units)
    python3 author/gallery.py layout NAME OUT_DIR      maps/<name>-data.json + OUT_DIR/<FILE>-zones.png from the art and the design
    python3 author/gallery.py screen NAME              screens/<id>-<name>.json

A description: {"id", "file", "name", "donor", "size": [W, H], "pad": 16, "camera": [dist, pitch], "projection",
"caption", "sound_bank", "tims8", "tims4", "day_night", "design": {...}, "floor_px": [[[u, v], ...], ...], "blocked_px": {"what": [[u, v], ...]}}.
"floor_px" (optional) replaces the design's floor with polygons traced on the finished art; the exits' bands are added to it.
The design, in world units (z up the screen, the look-at point at the centre):
  "bands":  [{"a": [x, z], "b": [x, z], "half": w, "role": "floor"|"decor"|"blocked", "t0": -0.05, "t1": 1.05}]  straight strips
  "discs":  [{"c": [x, z], "r": [rx, rz], "role": ...}]                                                            ellipses
  "polys":  [{"pts": [[x, z], ...], "role": ...}]                                                                  any shape
  "exits":  [{"warp": k, "edge": "S"|"N"|"W"|"E", "at": v, "half": w, "target": [map, exit]}]                      a band to the edge
            or {"warp": k, "box_px": [x0, y0, x1, y1], "spawn_px": [u, v], "face_px": [u, v], "target": [map, exit]}  a mouth in the picture
            "step": N on either: the tiles run the screen's on_step(N) (tile 51 + N) instead of leaving by themselves, for an
            exit whose destination the story decides (File City's lower town has 24 screens); the warp keeps its arrival
  "sticks": [[x, z], ...]                                                                                           scale posts
Roles: floor = walkable (light grey), decor = walkable but drawn darker (a turntable, a puddle), blocked = not walkable
(very dark). "blocked_px" are pixel polygons traced on the finished art (props the generator put on the floor).
"""

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from mapbase import base_map, Cam, MOD, check_arrivals
import dwmap

HERE = os.path.join(MOD, 'maps', 'author', os.environ.get('GALLERY_SET', 'galleries'))   # GALLERY_SET=district: File City's new district
GREY = {'floor': (128, 128, 128), 'decor': (100, 100, 100), 'blocked': (18, 18, 18)}
EXIT_DEPTH = 400                                         # world units: the exit tiles are the band's tiles this close to the edge (four tiles)
SPAWN_IN = 700                                           # world units from the edge to the arrival point (three tiles past the exit tiles)


class Screen:
    def __init__(self, name):
        self.cfg = json.load(open(os.path.join(HERE, name + '.json')))
        c = self.cfg; self.W, self.H = c['size']; self.PAD = c.get('pad', 0)
        self.m = base_map(c['donor'], *c['camera']); self.m.projection = c['projection']
        self.cam = Cam(self.m); self.basis = dwmap.camera_basis(self.m)
        self.TOP = self.cam.world(self.W // 2, 0)[1]; self.BOT = self.cam.world(self.W // 2, self.H - 1)[1]
        self.LEFT = self.cam.world(0, self.H // 2)[0]; self.RIGHT = self.cam.world(self.W - 1, self.H // 2)[0]

    def P(self, x, y, z): return dwmap.project(self.m, self.basis, (x, y, z))
    def Q(self, x, z, pad=0):
        p = self.P(x, 0, z); return (p[0], p[1] + pad)

    def band(self, a, b, half, t0=-0.05, t1=1.05, pad=0):
        dx, dz = b[0] - a[0], b[1] - a[1]; L = math.hypot(dx, dz) or 1.0; nx, nz = -dz / L, dx / L
        al = lambda t, s: (a[0] + dx * t + nx * s, a[1] + dz * t + nz * s)
        return [self.Q(*al(t, half), pad) for t in (t0, t1)] + [self.Q(*al(t, -half), pad) for t in (t1, t0)]

    def disc(self, c, r, n=40, pad=0):
        return [self.Q(c[0] + r[0] * math.cos(2 * math.pi * k / n), c[1] + r[1] * math.sin(2 * math.pi * k / n), pad) for k in range(n)]

    def edge_coord(self, e):
        """Where the screen's edge really is, in world units, on the exit's own row or column (the edges are not straight
        in world terms: the visible left edge is nearer the centre at the bottom of the picture than at mid-height)."""
        edge, at = e['edge'], e['at']
        if edge in ('W', 'E'):
            x0 = self.LEFT if edge == 'W' else self.RIGHT
            p = self.P(x0, 0, at); v = min(max(int(p[1]), 0), self.H - 1) if p else self.H // 2
            return self.cam.world(0 if edge == 'W' else self.W - 1, v)[0]
        z0 = self.TOP if edge == 'N' else self.BOT
        p = self.P(at, 0, z0); u = min(max(int(p[0]), 0), self.W - 1) if p else self.W // 2
        return self.cam.world(u, 0 if edge == 'N' else self.H - 1)[1]

    def exit_geometry(self, e):
        """The exit band (to past the edge), the arrival point and the point it faces, in world units."""
        edge, at = e['edge'], e['at']; c = self.edge_coord(e); e['edge_coord'] = c
        if edge == 'S': a, b, spawn, face = (at, c + 600), (at, c - 400), (at, c + SPAWN_IN), (at, c + 2500)
        elif edge == 'N': a, b, spawn, face = (at, c - 600), (at, c + 400), (at, c - SPAWN_IN), (at, c - 2500)
        elif edge == 'W': a, b, spawn, face = (c + 600, at), (c - 400, at), (c + SPAWN_IN, at), (c + 2500, at)
        else: a, b, spawn, face = (c - 600, at), (c + 400, at), (c - SPAWN_IN, at), (c - 2500, at)
        return a, b, spawn, face

    def shapes(self, pad=0):
        """[(role, polygon px)] of the design, floor first; exits add a floor band to the edge."""
        d = self.cfg['design']; out = []
        for role in ('floor', 'decor', 'blocked'):
            for s in d.get('bands', []):
                if s.get('role', 'floor') == role: out.append((role, self.band(s['a'], s['b'], s['half'], s.get('t0', -0.05), s.get('t1', 1.05), pad)))
            for s in d.get('discs', []):
                if s.get('role', 'floor') == role: out.append((role, self.disc(s['c'], s['r'], pad=pad)))
            for s in d.get('polys', []):
                if s.get('role', 'floor') == role: out.append((role, [self.Q(x, z, pad) for x, z in s['pts']]))
            if role == 'floor':
                for e in d.get('exits', []):
                    if 'box_px' in e: continue
                    a, b, _, _ = self.exit_geometry(e); out.append(('floor', self.band(a, b, e['half'], 0, 1, pad)))
        return out

    def guide(self, out):
        from tools.image import Image, ImageDraw
        W, H, PAD = self.W, self.H, self.PAD
        img = Image.new('RGB', (W, H + 2 * PAD), (40, 40, 40))
        shapes = self.shapes(PAD)
        floor_mask = Image.new('L', img.size, 0); fm = ImageDraw.Draw(floor_mask)
        for role, poly in shapes:
            if role in ('floor', 'decor'): fm.polygon(poly, fill=255)
        grid = Image.new('RGB', img.size, (40, 40, 40)); gd = ImageDraw.Draw(grid)
        grid_in = Image.new('RGB', img.size, GREY['floor']); gdi = ImageDraw.Draw(grid_in)
        def seg(a, b, col_out, col_in, n=60):
            pts = [self.P(a[0] + (b[0] - a[0]) * k / n, 0, a[2] + (b[2] - a[2]) * k / n) for k in range(n + 1)]
            pts = [(p[0], p[1] + PAD) if p else None for p in pts]
            for p, q in zip(pts, pts[1:]):
                if p and q: gd.line([p, q], fill=col_out); gdi.line([p, q], fill=col_in)
        for v in range(-7000, 7001, 250):
            bold = v % 1000 == 0
            seg((v, 0, -7000), (v, 0, 7000), (52, 52, 52) if bold else (46, 46, 46), (200, 200, 200) if bold else (150, 150, 150))
            seg((-7000, 0, v), (7000, 0, v), (52, 52, 52) if bold else (46, 46, 46), (200, 200, 200) if bold else (150, 150, 150))
        img = Image.composite(grid_in, grid, floor_mask); d = ImageDraw.Draw(img)
        for role, poly in shapes:
            if role in ('decor', 'blocked'): d.polygon(poly, fill=GREY[role])
        for e in self.cfg['design'].get('exits', []):
            if 'box_px' in e: continue
            a, b, _, _ = self.exit_geometry(e)
            edge = e['edge']; c = e['edge_coord']
            if edge == 'S': a = (a[0], c - 60)
            elif edge == 'N': a = (a[0], c + 60)
            elif edge == 'W': a = (c + 60, a[1])
            else: a = (c - 60, a[1])
            d.polygon(self.band(a, b, e['half'], 0, 1, PAD), fill=(0, 0, 0))
        for x, z in self.cfg['design'].get('sticks', []):
            a, b = self.P(x, 0, z), self.P(x, -200, z)
            d.line([(a[0], a[1] + PAD), (b[0], b[1] + PAD)], fill=(215, 215, 215), width=2)
        img.save(out)
        n = sum(1 for tx, tz, u, v in self.cam.tiles() if u is not None and 0 <= u < W and 0 <= v < H and floor_mask.getpixel((u, v + PAD)) > 0)
        print(f'{out} {img.size}: floor tiles about {n}, stick px {round(self.P(0, 0, 0)[1] - self.P(0, -200, 0)[1], 1)}, '
              f'z top {self.TOP} bottom {self.BOT}, x left {self.LEFT} right {self.RIGHT}')

    def layout(self, out):
        import numpy as np, cv2
        from tools.image import Image
        from maps import reach
        c = self.cfg; W, H = self.W, self.H
        art = os.path.join(MOD, 'art', c['name'] + '.png')
        floor = np.zeros((H, W), np.uint8)
        if c.get('floor_px'):                      # the floor traced on the finished art (the generator widened or moved the band)
            for poly in c['floor_px']: cv2.fillPoly(floor, [np.array(poly, np.int32)], 1)
            for e in c['design'].get('exits', []):
                if 'box_px' in e: continue
                a, b, _, _ = self.exit_geometry(e); cv2.fillPoly(floor, [np.array(self.band(a, b, e['half'], 0, 1), np.int32)], 1)
        else:
            for role, poly in self.shapes(0):
                if role in ('floor', 'decor'): cv2.fillPoly(floor, [np.array(poly, np.int32)], 1)
        for role, poly in self.shapes(0):
            if role == 'blocked': cv2.fillPoly(floor, [np.array(poly, np.int32)], 0)
        for poly in c.get('blocked_px', {}).values(): cv2.fillPoly(floor, [np.array(poly, np.int32)], 0)
        n, lbl, st, _ = cv2.connectedComponentsWithStats(floor)
        if n > 1: floor = (lbl == 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
        m, cam = self.m, self.cam
        exits = c['design'].get('exits', [])
        boxes = {}
        for e in exits:
            if 'box_px' in e:                       # a mouth inside the picture: the floor tiles in the box, the arrival at spawn_px
                x0, y0, x1, y1 = e['box_px']; strip = (x0, y0, x1 + 1, y1 + 1); band = np.ones((H, W), np.uint8)
                e['spawn_world'] = cam.world(*e['spawn_px']); e['face_world'] = cam.world(*e['face_px'])
            else:
                a, b, spawn, face = self.exit_geometry(e)
                strip = (e['edge'], e['edge_coord'])    # the exit tiles: the band's tiles within EXIT_DEPTH world units of the edge
                band = np.zeros((H, W), np.uint8); cv2.fillPoly(band, [np.array(self.band(a, b, e['half'], 0, 1), np.int32)], 1)
                e['spawn_world'] = spawn; e['face_world'] = face
            boxes[e['warp']] = (strip, band, 51 + e['step'] if 'step' in e else 110 + e['warp'])
        col = [0x80] * 10000
        for tx, tz, u, v in cam.tiles():
            if u is None or not (0 <= u < W and 0 <= v < H): continue
            if floor[v, u]:
                col[tz * 100 + tx] = 0
                wx, wz = tx * 100 - 4950, 4950 - tz * 100
                for k, (strip, band, tile) in boxes.items():
                    if isinstance(strip, tuple) and isinstance(strip[0], str):
                        edge, ec = strip
                        at_edge = {'S': wz < ec + EXIT_DEPTH, 'N': wz > ec - EXIT_DEPTH, 'W': wx < ec + EXIT_DEPTH, 'E': wx > ec - EXIT_DEPTH}[edge]
                    else:
                        at_edge = strip[0] <= u < strip[2] and strip[1] <= v < strip[3]
                    if at_edge and band[v, u]: col[tz * 100 + tx] = tile
        m.collision = col
        for e in exits:
            x, z = e['spawn_world']
            m.warps[e['warp']].update({'x': x, 'y': 0, 'z': z, 'rotation': cam.rotation((x, z), e['face_world']),
                                       'targetMap': e['target'][0], 'targetExit': e['target'][1]})
        check_arrivals(m, c['file'])
        R = reach.from_spawn_coordinates(m, starts=[exits[0]['spawn_world']])
        for e in exits:
            tiles = [(i % 100, i // 100) for i, c2 in enumerate(col) if c2 == boxes[e['warp']][2]]
            if not any((tx * 100 - 4950 + dx, 4950 - tz * 100 + dz) in R for tx, tz in tiles for dx in (-50, 0, 50) for dz in (-50, 0, 50)):
                sys.exit(f'{c["file"]}: no exit tile of warp {e["warp"]} is reachable from the first arrival')
        data = os.path.join(MOD, 'maps', c['name'] + '-data.json')
        json.dump({'camera': list(c['camera']), 'projection': c['projection'], 'collision': col, 'warps': m.warps}, open(data, 'w'))
        print(f'{c["file"]}: free tiles {col.count(0)}, exit tiles {sum(1 for v in col if 110 <= v < 120 or 51 <= v < 80)}, reach {len(R)}, '
              + ', '.join(f'warp {e["warp"]} spawn {tuple(round(v) for v in e["spawn_world"])} rot {m.warps[e["warp"]]["rotation"]}' for e in exits))
        os.makedirs(out, exist_ok=True)
        bg = np.array(Image.open(art).convert('RGB'))
        rp = np.zeros((H, W), np.uint8); ex = np.zeros((H, W), np.uint8)
        for x, z in R:
            p = cam.pixel(x, z)
            if p and 0 <= p[0] < W and 0 <= p[1] < H: rp[p[1], p[0]] = 1
        for tx, tz, u, v in cam.tiles():
            if u is not None and (110 <= col[tz * 100 + tx] < 120 or 51 <= col[tz * 100 + tx] < 80) and 0 <= u < W and 0 <= v < H: cv2.circle(ex, (u, v), 4, 1, -1)
        rp = cv2.dilate(rp, np.ones((3, 3), np.uint8)); ov = bg.copy(); ov[rp > 0] = (0, 200, 0); ov[ex > 0] = (0, 80, 255)
        img = (bg * 0.55 + ov * 0.45).astype(np.uint8)
        for e in exits: cv2.circle(img, cam.pixel(*e['spawn_world']), 4, (255, 255, 255), -1)
        Image.fromarray(img).resize((W * 2, H * 2), Image.NEAREST).save(os.path.join(out, c['file'] + '-zones.png'))

    def screen(self):
        c = self.cfg
        path = os.path.join(MOD, 'screens', f'{c["id"]}-{c["name"]}.json')
        json.dump({'id': c['id'], 'file': c['file'], 'tims8': c['tims8'], 'tims4': c['tims4'], 'sound_bank': c['sound_bank'],
                   'day_night': c.get('day_night', False), 'reads_digimon': True, 'doors': 0, 'toilet': 0, 'caption': c['caption'],
                   'concave': False, 'shop': c.get('shop', False), 'maphead': {'like': 240, 'script': 1}}, open(path, 'w'), indent=2)
        open(path, 'a').write('\n'); print(path)


if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    cmd, name = sys.argv[1], sys.argv[2]; s = Screen(name)
    if cmd == 'guide': s.guide(sys.argv[3])
    elif cmd == 'layout': s.layout(sys.argv[3])
    elif cmd == 'screen': s.screen()
    else: sys.exit(__doc__)
