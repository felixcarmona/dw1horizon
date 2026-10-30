"""Texture placement order and UV footprint boundary regressions."""
import random
import json
from pathlib import Path
import unittest

from tools.derive.arraymath import array, uint8
from tools.derive.texel import footprint, place, window_pair


class Texels(unittest.TestCase):
    def test_palette_merges_match_numpy_oracle_bytes_and_choices(self):
        from tools import dw2mmd
        data = json.loads(Path(__file__).with_name('testdata').joinpath('dw2-palettes.json').read_text())
        pixels = array(data['pixels'], uint8)
        ids = data['ids'][:]
        pals = {int(k): v[:] for k, v in data['pals'].items()}
        report = dw2mmd.merge_palettes(pixels, data['uvs'], ids, pals, data['limit'], lambda *a: None)
        expected = data['expected']
        self.assertEqual(pixels.tobytes().hex(), expected['pixels'])
        self.assertEqual(ids, expected['ids'])
        self.assertEqual(pals, {int(k): v for k, v in expected['pals'].items()})
        self.assertEqual([list(row) for row in report], expected['report'])

    def test_windows_match_exhaustive_cost_and_first_tie(self):
        self.assertEqual(window_pair([(64, 192, 100)]), (0, 64))
        self.assertEqual(window_pair([(0, 128, 1), (128, 256, 1)]), (0, 128))
        rng = random.Random(182)
        for _ in range(100):
            size = rng.randrange(2, 12)
            intervals = [(rng.randrange(-2, 2 * size), rng.randrange(2 * size + 3),
                          rng.choice((0, 1, 17, 1000000))) for _ in range(rng.randrange(25))]
            expected = min((sum(float(w) for lo, hi, w in intervals
                                if not (a <= lo and hi <= a + size or b <= lo and hi <= b + size)) +
                            .01 * (abs(a) + abs(b - size)), a, b)
                           for a in range(size + 1) for b in range(a, size + 1))
            self.assertEqual(window_pair(intervals, size), expected[1:])

    def test_placement_matches_exact_search(self):
        rng = random.Random(219)
        for _ in range(100):
            height, width = rng.randrange(2, 15), rng.randrange(2, 18)
            h, w = rng.randrange(1, height+2), rng.randrange(1, width+2)
            occ = [[rng.random() < .25 for _ in range(width)] for _ in range(height)]
            mask = [[rng.random() < .6 for _ in range(w)] for _ in range(h)]
            for align in (None, (4, 0), (4, 3)):
                expected = None
                for y in range(height-h, -1, -1):
                    for x in range(width-w+1):
                        if align and x % align[0] != align[1]: continue
                        if not any(occ[y+j][x+i] and mask[j][i] for j in range(h) for i in range(w)):
                            expected = (x,y); break
                    if expected is not None: break
                self.assertEqual(place(array(occ), array(mask), align), expected)

    def test_integer_triangle_includes_edge_texels(self):
        x, y, mask = footprint([(0, 0), (2, 0), (0, 2)])
        self.assertEqual((x,y), (0,0))
        self.assertEqual(mask.tolist(), [[1,1,1],[1,1,0],[1,0,0]])
        mask[:] = False
        self.assertEqual(footprint([(0, 0), (2, 0), (0, 2)])[2].sum(), 6)


if __name__ == '__main__': unittest.main()
