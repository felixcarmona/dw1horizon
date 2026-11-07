"""The jungle exit accepts the tamer's full body along the grass edge."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'story/mods/what-the-island-forgot/maps')]
import dwmap
from tools.maps import reach

spec = importlib.util.spec_from_file_location('jungle_exit', ROOT / 'story/mods/what-the-island-forgot/maps/trop02-exit.py')
recipe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recipe)


class JungleExit(unittest.TestCase):
    def test_original_snag_and_widened_body_box_route(self):
        path = ROOT / 'extracted/MAP/MAP1/TROP02.MAP'
        if not path.is_file():
            self.skipTest('requires the original disc extraction')
        old = dwmap.MapFile(path.read_bytes())
        new = dwmap.MapFile(recipe.repair(path.read_bytes()))
        # Walk south beside the west boundary, through both inward corners.
        route = [(-2550, z) for z in range(-2600, -3751, -10)]
        self.assertTrue(any(not reach.can_z(old, x, z, -1, 100) for x, z in route))
        self.assertTrue(all(reach.can_z(new, x, z, -1, 100) for x, z in route))
        self.assertEqual(new.collision[reach.row(route[-1][1]) * 100 + reach.col(-2550)], 111)
        self.assertEqual(old.warps, new.warps)
        self.assertEqual(old.digimon, new.digimon)
        changed = [i for i, (a, b) in enumerate(zip(old.collision, new.collision)) if a != b]
        self.assertEqual(len(changed), 32)
        self.assertTrue(all(old.collision[i] == 128 and new.collision[i] in (0, 111) for i in changed))
        # Object collision and every original exit tile remain unchanged.
        for i, value in enumerate(old.collision):
            if 110 <= value < 120:
                self.assertEqual(new.collision[i], value)
        for z, lo, hi, _ in recipe.GRASS + recipe.EXIT:
            for x in range(lo, hi + 1):
                new.collision[z * 100 + x] = 128
        self.assertEqual(new.build(), old.build())


if __name__ == '__main__':
    unittest.main()
