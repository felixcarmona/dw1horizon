"""Toilet booths of the three long new areas: the Iron Hills (318), the Seam's CAMP 2 (326) and the Overdell Pass (331).

Each booth is our own RGBA piece (art/<screen>-toilet.png, an edit of the screen's own art, see art/README.md) laid over
the imported background with `dwmap.py bg --paste`, so its evening and night colours come from the screen's own
palettes. Its body is blocked, with the floor beside it where the tamer would be drawn over it, and the floor tiles in
front carry the toilet trigger (120): stepping on one while the partner needs to go runs MAPHEAD section 1250, which
walks the partner to the screen file's first toilet point, then into the booth (the second point), and back. The two
points are tile centres (`"toilet"` in screens/<id>-<name>.json); the booth is open at the front, as the originals are.
"""
import os

from mapbase import MOD, bg

TOILET = 120
WALL = 0x80

BOOTHS = {
    # The second Iron Hills screen: a rusty sheet-metal booth at the foot of the west slope, its open side towards the
    # track; the column east of it is blocked where the tamer's sprite would cross the booth's east wall.
    'IRON02': dict(png='iron-hills-2-toilet.png', at=(126, 121),
                   blocked=[(37, tz) for tz in range(32, 39)],
                   trigger=[(37, 39), (38, 39)] + [(tx, tz) for tz in (40, 41) for tx in (36, 37, 38)]),
    # CAMP 2: the camp's plank latrine against the north wall, east of the doorway to 327; the strip east of it, cut
    # off by the booth, is blocked too.
    'SEAM04': dict(png='seam-3-toilet.png', at=(487, 65),
                   blocked=[(tx, tz) for tz in (26, 27, 28) for tx in range(57, 65)],
                   trigger=[(tx, tz) for tz in (29, 30, 31) for tx in range(58, 64)]),
    # The dry riverbed: a plank latrine on the sand against the east rock pillar, the trigger on the floor at its west.
    'OVPS02': dict(png='descent-2-toilet.png', at=(452, 310),
                   blocked=[],
                   trigger=[(tx, tz) for tz in range(47, 52) for tx in (55, 56, 57)]),
}


def paste(m, name, out):
    """The booth over the screen's imported background (OUT/NAME.TFS); returns the map as bg leaves it."""
    b = BOOTHS[name]
    path = os.path.join(out, name + '.MAP')
    with open(path, 'wb') as f:
        f.write(m.build())
    tfs = os.path.join(out, name + '.TFS')
    return bg([path, tfs, tfs, '--paste', os.path.join(MOD, 'art', b['png']), b['at'][0], b['at'][1]])


def tiles(m, name):
    """Block the booth's surroundings and lay the trigger on free floor in front of it."""
    b = BOOTHS[name]
    for tx, tz in b['blocked']:
        m.collision[tz * 100 + tx] = WALL
    for tx, tz in b['trigger']:
        assert m.collision[tz * 100 + tx] == 0, (name, tx, tz, m.collision[tz * 100 + tx])
        m.collision[tz * 100 + tx] = TOILET
