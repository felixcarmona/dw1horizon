#!/usr/bin/env python3
"""Trace all visible beach ground, blocking the wreck and its grounded spars.

Run from the repository root with OUT_DIR. The checked-in collision data is the
build input; this authoring recipe also writes the reachable-zone review image.
Whamon is included as a stationary body, and the unopened chest blocks its tiles.
"""
import json
from pathlib import Path
import sys

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'tools').is_dir())
sys.path[:0] = [str(ROOT), str(ROOT / 'tools'),
               str(ROOT / 'story/mods/what-the-island-forgot/maps')]
from mapbase import base_map, Cam, inside, check_arrivals, MOD
from maps import reach
from tools.image import Image, ImageDraw

CAMERA = (7200, 65)
PROJECTION = 900
# Pixel coordinates on the committed artwork. Both pale frost and dark pebbles
# are ground, up to the cliff feet and the ice/water edge.
GROUND = [(0,118),(75,126),(150,124),(230,134),(315,116),(390,123),
          (467,125),(552,116),(633,118),(710,112),(767,130),(767,268),
          (738,277),(709,293),(690,337),(670,367),(631,403),(592,435),
          (550,469),(488,510),(428,540),(359,571),(285,583),(208,572),
          (157,559),(98,582),(49,590),(0,604)]
HULL = [(108,357),(133,322),(191,289),(285,263),(356,217),(429,179),
        (504,168),(562,190),(559,219),(518,279),(450,326),(350,370),
        (250,396),(159,400)]
SPARS = [[(27,169),(34,162),(282,304),(274,315)],
         [(194,175),(204,181),(97,287),(88,281)],
         [(8,394),(12,405),(133,379),(131,369)]]
SPAWN_PX = (457,460)
WHAMON = (1560, -1720)
WHAMON_RADIUS = json.loads((ROOT / 'content/species/146-whamon.json').read_text())['model']['radius']


def layout():
    m = base_map('FRZL03', *CAMERA)
    m.projection = PROJECTION
    cam = Cam(m)
    for tx, tz, u, v in cam.tiles():
        if u is not None and inside(GROUND,u,v) and not any(
                inside(poly,u,v) for poly in [HULL, *SPARS]):
            m.collision[tz*100+tx] = 0
    x,z = cam.world(*SPAWN_PX)
    m.warps[0].update(x=x,z=z,rotation=0)
    # Tile rasterization can leave slivers next to a spar. Only remove floor
    # that the engine's body-box simulation cannot enter from the ferry arrival.
    visited = {(reach.col(x),reach.row(z)) for x,z in reach.from_spawn_coordinates(m)}
    for i,c in enumerate(m.collision):
        if c == 0 and (i%100,i//100) not in visited:
            m.collision[i] = 128
    # The compiler requires a floor tile beneath even a stationary water NPC.
    # This isolated tile is entirely inside the ferry's 500-unit body block;
    # neither the tamer nor the beach gains a route into the sea.
    tx, tz = reach.model_tile(*WHAMON)
    m.collision[tz*100+tx] = 0
    check_arrivals(m,'SHOR01')
    return m


def review(m, out):
    """Reach with the actual stationary ferry and the unopened chest present."""
    cam = Cam(m)
    whale = WHAMON
    chest = (-2036, -1152)
    tx, tz = reach.model_tile(*chest)
    grid = type('Grid', (), {'collision': list(m.collision), 'warps': m.warps})()
    for row in range(tz-2,tz+2):
        for col in range(tx-2,tx+2):
            grid.collision[row*100+col] = 128
    area = reach.reach(grid,seed_policy='spawn_coordinates',footprints=[(*whale,WHAMON_RADIUS)])
    assert any(reach.model_tile(x,z)==(tx+4,tz) for x,z in area), 'chest opening is unreachable'
    edge = WHAMON_RADIUS + 100
    assert any((edge < abs(x-whale[0]) <= edge+50 and abs(z-whale[1]) <= edge)
               or (edge < abs(z-whale[1]) <= edge+50 and abs(x-whale[0]) <= edge)
               for x,z in area), 'ferry talk boundary is unreachable'
    image = Image.open(Path(MOD,'art/drowned-shore.png')).convert('RGB')
    w,h = image.size
    mask = bytearray(w*h)
    for x,z in area:
        p = cam.pixel(x,z)
        if p is None: continue
        for dy in (-1,0,1):
            for dx in (-1,0,1):
                u,v = p[0]+dx,p[1]+dy
                if 0 <= u < w and 0 <= v < h: mask[v*w+u] = 1
    pixels = bytearray(image.tobytes())
    for i,value in enumerate(mask):
        if value:
            k=i*3
            for axis,green in enumerate((0,220,70)):
                pixels[k+axis] = (pixels[k+axis]*55+green*45)//100
    image = Image.frombytes('RGB',(w,h),bytes(pixels))
    draw = ImageDraw.Draw(image)
    # The engine uses an inclusive square for NPC/tamer collision, not a circle.
    corners = [cam.pixel(whale[0]+dx*edge,whale[1]+dz*edge)
               for dx,dz in [(-1,-1),(1,-1),(1,1),(-1,1),(-1,-1)]]
    draw.line(corners,fill='yellow',width=2)
    for label,point in [('arrival',(m.warps[0]['x'],m.warps[0]['z'])),
                        ('Whamon',whale),('chest',chest),('notebook',(363,-580))]:
        u,v = cam.pixel(*point)
        draw.ellipse((u-4,v-4,u+4,v+4),fill='white')
        draw.text((u+6,v),label,fill='white')
    image.resize((w*2,h*2),Image.NEAREST).save(out/'SHOR01-zones.png')
    result = dict(free_tiles=m.collision.count(0),reachable_positions=len(area),
                  whale=list(whale),whale_radius=WHAMON_RADIUS,tamer_exclusion=edge,chest=list(chest),chest_opening=[tx+4,tz],
                  camera=list(CAMERA),projection=PROJECTION)
    (out/'SHOR01-reach.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


def main(out):
    out.mkdir(parents=True,exist_ok=True)
    m=layout()
    data=dict(camera=CAMERA,projection=PROJECTION,collision=m.collision,warps=m.warps,
              ferry=dict(species=146,at=WHAMON,radius=WHAMON_RADIUS,facing=1024))
    Path(MOD,'maps/drowned-shore-data.json').write_text(json.dumps(data)+'\n')
    (out/'SHOR01.MAP').write_bytes(m.build())
    review(m,out)
    print(f'SHOR01: {m.collision.count(0)} free tiles; arrival {m.warps[0]}')


if __name__ == '__main__':
    if len(sys.argv) != 2:sys.exit(__doc__)
    main(Path(sys.argv[1]))
