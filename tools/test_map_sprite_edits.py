"""Reviewed native-map sprite depth edits refuse stale inputs; the restaurant counter sits between the order tiles and the cooks."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import content


class SpriteEdits(unittest.TestCase):
    def setUp(self):
        self.map = SimpleNamespace(sprites=[dict(x=1, y=2, z=3)])
        self.edit = dict(sprite=0, field='z', before=3, after=9, reason='Depth.')

    def test_edit_applies_and_is_idempotent(self):
        content.apply_map_sprites(self.map, [self.edit], 'fixture')
        content.apply_map_sprites(self.map, [self.edit], 'fixture')
        self.assertEqual(self.map.sprites[0], dict(x=1, y=2, z=9))

    def test_refuse_stale_or_invalid(self):
        self.map.sprites[0]['z'] = 4
        with self.assertRaisesRegex(ValueError, 'expected'):
            content.apply_map_sprites(self.map, [self.edit], 'fixture')
        for bad in (dict(self.edit, sprite=5), dict(self.edit, field='w'), dict(self.edit, reason='')):
            with self.assertRaises(ValueError):
                content.apply_map_sprites(self.map, [bad], 'fixture')
        self.assertEqual(self.map.sprites[0]['z'], 4)

    @unittest.skipUnless((ROOT / 'extracted/MAP/MAP15/ROOM05A.MAP').exists(), 'needs USA extraction')
    def test_restaurant_counter_depth(self):
        import dwmap
        for name in ('ROOM05A', 'ROOM05B'):
            m = dwmap.MapFile(content.build_map(name, (ROOT / f'extracted/MAP/MAP15/{name}.MAP').read_bytes()))
            vp, _, _, fw = dwmap.camera_basis(m)
            s = m.sprites[0]
            depth = sum((p - vp[i]) * fw[i] for i, p in enumerate((s['x'], s['y'], s['z'])))
            order = max(sum((p - vp[i]) * fw[i] for i, p in enumerate(((t % 100 - 50) * 100 + 50, 0, (49 - t // 100) * 100 + 50)))
                        for t, v in enumerate(m.collision) if v == 0x51)
            self.assertGreater(depth, order)          # every order tile is nearer than the counter: no tamer there is behind it
            self.assertLess(depth, 11000)             # the cooks (about 11070) stay behind it


if __name__ == '__main__':
    unittest.main()
