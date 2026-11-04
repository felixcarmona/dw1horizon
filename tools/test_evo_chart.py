#!/usr/bin/env python3
"""The evolution chart's lists (tools/evo_chart.py) on a small made-up tree: no disc, no build.
tools/evo_chart.py DIGI.DAT EXE_DIR checks a built disc the same way (the self-test's evolution-chart)."""
import os, struct, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evo_chart as E
import species as S


def tree():
    # Koromon-like Baby II 2 with six slots full and five more Rookies in its extra list; Ultimate 64 without a path
    # row, reached from Champion 10's row, evolving into Mega 115 by an Ultimate pair; Fresh 1 -> 2 by a Fresh pair
    paths = {1: ([-1] * 5, [-1, -1, 2, -1, -1, -1]), 2: ([-1, -1, 1, -1, -1], [3, 17, 80, 84, 180, 233]),
             10: ([-1] * 5, [-1, -1, 54, 64, -1, -1]), 54: ([10, -1, -1, -1, -1], [-1] * 6)}
    for t in (3, 17, 80, 84, 180, 233, 235, 251, 351, 354, 433):
        paths.setdefault(t, ([2, -1, -1, -1, -1], [-1] * 6))
    levels = {1: 1, 2: 2, 10: 4, 54: 5, 64: 5, 115: 6}
    levels.update({t: 3 for t in (3, 17, 80, 84, 180, 233, 235, 251, 351, 354, 433)})
    return dict(paths=paths, extra={2: [235, 251, 351, 354, 433]}, fresh=[(1, 2)], ultimate=[(64, 115), (54, 115)],
                levels=levels, partners=set(levels), names={t: str(t) for t in levels}, block=[(64, 10)])


class ChartLists(unittest.TestCase):
    def test_every_route_has_its_boxes(self):
        g = tree()
        missing, routes = E.audit(g, E.chart_lists)
        self.assertEqual(missing, [])
        self.assertIn((2, 433), routes)
        self.assertIn((64, 115), routes)

    def test_the_old_chart_missed_them(self):
        missing, _ = E.audit(tree(), E.old_chart_lists)
        self.assertIn(('child', 2, 235), missing)          # past the six slots
        self.assertIn(('parent', 10, 64), missing)         # no path row
        self.assertIn(('child', 64, 115), missing)         # an Ultimate pair
        self.assertIn(('parent', 54, 115), missing)

    def test_order_slots_then_extra_then_pairs(self):
        parents, kids = E.chart_lists(tree(), 2)
        self.assertEqual(kids, [3, 17, 80, 84, 180, 233, 235, 251, 351, 354, 433])
        self.assertEqual(parents, [1])
        self.assertEqual(E.chart_lists(tree(), 115)[0], [64, 54])

    def test_block_roundtrip(self):
        """species.py chart_parents writes what evo_chart.chart_ids reads."""
        tabs = [[1, 2], [3], [10], [54, 64], [115]]
        block = S.chart_block(tabs, {}, None)
        paths = {10: {'from': [-1] * 5, 'to': [-1, -1, 54, 64, -1, -1]}}
        block = S.chart_parents(block, tabs, paths, {}, [None] * 120, [])
        d = bytearray(S.SECTOR) + block
        struct.pack_into(S.HEADER, d, 0, b'DIGI', S.VERSION, S.RECORD_SIZE, 120, 0, 0, 0, 0, 0, 1)
        self.assertEqual(E.chart_ids(bytes(d)), ([1, 2, 3, 10, 54, 64, 115], [(64, 10)]))


if __name__ == '__main__':
    unittest.main()
