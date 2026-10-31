"""The Coela Point cliff must not cover the added staircase with its donor pixels."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'tools'))
MAPS = ROOT / 'story/mods/what-the-island-forgot/maps'
sys.path.insert(0, str(MAPS))
import dwmap


@unittest.skipUnless(list((ROOT / 'extracted/MAP').glob('*/MAYO05.MAP')),
                     'needs the player disc extraction')
class CoelaForeground(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('mayo05_recipe', MAPS / 'mayo05-path.py')
        cls.recipe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.recipe)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.recipe.main(cls.tmp.name)
        src = next((ROOT / 'extracted/MAP').glob('*/MAYO05.MAP'))
        cls.before = dwmap.MapFile(src.read_bytes())
        cls.original = dwmap.TfsFile(src.with_suffix('.TFS').read_bytes())
        cls.after = dwmap.MapFile((Path(cls.tmp.name) / 'MAYO05.MAP').read_bytes())
        cls.tfs = dwmap.TfsFile((Path(cls.tmp.name) / 'MAYO05.TFS').read_bytes())

    def test_staircase_survives_the_foreground_at_every_time_of_day(self):
        _, _, old = self.original.image_indices(self.before)
        _, _, new = self.tfs.image_indices(self.after)
        inst = self.after.instances[0]
        sp = self.after.sprites[inst['frames'][0]]
        tim = dwmap.TIM(self.after.tims[0])
        for k, label in enumerate(('day', 'evening', 'night')):
            wrong = []
            for y in range(sp['height']):
                for x in range(sp['width']):
                    bx, by = inst['x'] + x, inst['y'] + y
                    if old[by][bx] == new[by][bx]:
                        continue
                    v = tim.pixels[y * tim.w * 2 + x]
                    # Colour zero lets the already-composited TFS show through.
                    if self.tfs.cluts[k][v] and ((self.tfs.cluts[k][v] ^
                                                self.tfs.cluts[k][new[by][bx]]) & 0x7fff):
                        wrong.append((bx, by))
            self.assertEqual(len(wrong), 0, f'{label}: foreground hides {len(wrong)} stair pixels')

    def test_only_the_painted_cliff_texels_change(self):
        self.assertEqual(self.after.sprites, self.before.sprites)
        self.assertEqual(self.after.instances, self.before.instances)
        self.assertEqual(self.after.tims[1:], self.before.tims[1:])
        self.assertEqual(self.tfs.cluts, self.original.cluts)
        a = dwmap.TIM(self.before.tims[0])
        b = dwmap.TIM(self.after.tims[0])
        self.assertEqual((a.x, a.y, a.w, a.h, a.size), (b.x, b.y, b.w, b.h, b.size))
        _, _, old = self.original.image_indices(self.before)
        _, _, new = self.tfs.image_indices(self.after)
        count = 0
        for p, (v, w) in enumerate(zip(a.pixels, b.pixels)):
            if v == w:
                continue
            count += 1
            x, y = p % (a.w * 2), p // (a.w * 2)
            self.assertLess(x, self.before.sprites[0]['width'])
            self.assertLess(y, self.before.sprites[0]['height'])
            self.assertNotEqual(old[y][128 + x], new[y][128 + x])
            self.assertTrue(any(c[v] != 0 for c in self.original.cluts))
        self.assertGreater(count, 0)
        expected = bytearray(self.before.collision)
        for tx, tz in self.recipe.EXIT_TILES:
            expected[tz * 100 + tx] = 111
        self.assertEqual(self.after.collision, expected)
        self.assertEqual((self.after.warps[1]['targetMap'], self.after.warps[1]['targetExit']), (314, 1))


if __name__ == '__main__':
    unittest.main()
