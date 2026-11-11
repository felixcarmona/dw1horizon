"""The arrival from the elevator side of the Ogre Fortress room stands outside Machinedramon's body box."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'story/mods/what-the-island-forgot/maps')]
import dwmap
from tools.maps import reach

spec = importlib.util.spec_from_file_location('ogre02_arrival', ROOT / 'story/mods/what-the-island-forgot/maps/ogre02-arrival.py')
recipe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recipe)


def inside_box(x, z):
    mx, mz = recipe.MACHINEDRAMON
    return abs(x - mx) < recipe.BODY and abs(z - mz) < recipe.BODY


class OgreArrival(unittest.TestCase):
    def test_arrival_leaves_the_body_box(self):
        path = ROOT / 'extracted/MAP/MAP4/OGRE02.MAP'
        if not path.is_file():
            self.skipTest('requires the original disc extraction')
        old = dwmap.MapFile(path.read_bytes())
        new = dwmap.MapFile(recipe.repair(path.read_bytes()))
        d = old.digimon[3]
        self.assertEqual((d['posX'], d['posZ']), recipe.MACHINEDRAMON)
        ow, nw = old.warps[recipe.WARP], new.warps[recipe.WARP]
        self.assertTrue(inside_box(ow['x'], ow['z']))
        self.assertFalse(inside_box(nw['x'], nw['z']))
        # Only that spawn changes; the arrival is free floor that the body can stand on and leave.
        self.assertEqual(new.collision, old.collision)
        self.assertEqual(new.digimon, old.digimon)
        for i, (a, b) in enumerate(zip(old.warps, new.warps)):
            if i != recipe.WARP:
                self.assertEqual(a, b)
        for k in ('y', 'rotation', 'targetMap', 'targetExit'):
            self.assertEqual(ow[k], nw[k])
        self.assertTrue(reach.can_x(new, nw['x'], nw['z'], 1, 100) and reach.can_z(new, nw['x'], nw['z'], 1, 100))
        # From the new arrival the room is connected to the south door (exit 0) and the arrival from the first door.
        R = reach.from_spawn_coordinates(new, starts=[(nw['x'], nw['z'])])
        self.assertIn((nw['x'], nw['z']), R)
        south = new.warps[0]
        tiles = {(reach.col(x), reach.row(z)) for x, z in R}
        self.assertIn((reach.col(south['x']), reach.row(south['z'])), tiles)
        for door in (110, 111):
            self.assertTrue(any(new.collision[tz * 100 + tx] == door for tx, tz in tiles))


if __name__ == '__main__':
    unittest.main()
