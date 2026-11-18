"""Old Gallery (screen 315): the dead-end strip between the plank and the fallen beam must not hold a big partner.

A player's partner jammed in the 2-tile strip south of the beam's west end (tiles 42-44, rows 64-68): a tamer fits,
a partner with a radius of 150 or more has no legal step there. The strip's tail is solid in the screen's data."""
import json
from collections import deque
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from maps import reach

DATA = json.loads((ROOT / 'story/mods/what-the-island-forgot/maps/old-gallery-data.json').read_text())
MOVES = [(a, b) for a in (-10, 0, 10) for b in (-10, 0, 10) if a or b]


def closed_pockets(m, radius):
    """Tamer-walkable points where an actor of this radius can never get back to the arrivals."""
    starts = [(round(w['x'] / 10) * 10, round(w['z'] / 10) * 10) for w in m.warps if w['targetMap'] != -1]
    main, queue = set(starts), deque(starts)
    while queue:
        x, z = queue.popleft()
        for dx, dz in MOVES:
            n = (x + dx, z + dz)
            if n not in main and reach._step_ok(m, n[0], n[1], dx, dz, radius):
                main.add(n); queue.append(n)
    out, done = set(), set()
    for p in reach.reach(m):
        if p in main or p in done:
            continue
        comp, queue, escapes = {p}, deque([p]), False
        while queue:
            x, z = queue.popleft()
            for dx, dz in MOVES:
                n = (x + dx, z + dz)
                if n in comp or not reach._step_ok(m, n[0], n[1], dx, dz, radius):
                    continue
                if n in main:
                    escapes = True
                    continue
                comp.add(n); queue.append(n)
        done |= comp
        if not escapes:
            out |= {(reach.col(x), reach.row(z)) for x, z in comp}
    return out


class OldGalleryNeck(unittest.TestCase):
    def setUp(self):
        self.m = SimpleNamespace(collision=list(DATA['collision']), warps=DATA['warps'])

    def test_strip_tail_is_solid(self):
        for tx, tz in ((42, 66), (43, 66), (44, 66), (43, 67), (44, 67), (44, 68)):
            self.assertEqual(self.m.collision[tz * 100 + tx], 128, (tx, tz))

    def test_big_partners_have_no_closed_pocket_in_the_strip(self):
        for radius in (150, 190):
            pockets = {t for t in closed_pockets(self.m, radius) if t[0] >= 40 and t[1] >= 62}
            self.assertEqual(pockets, set(), radius)

    def test_no_trap_tile_and_arrivals_still_connect(self):
        self.assertEqual(reach.trap_tiles(self.m), [])
        walked = {(reach.col(x), reach.row(z)) for x, z in reach.reach(self.m)}
        self.assertIn((43, 65), walked)       # the strip's mouth stays walkable
        self.assertIn((45, 58), walked)       # the way to the mouth exit
        self.assertIn((33, 41), walked)       # the way to the stair exit


if __name__ == '__main__':
    unittest.main()
