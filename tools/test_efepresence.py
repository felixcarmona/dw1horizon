"""Every own finisher effect reads at least as big as vanilla's lower quartile and no bigger than vanilla's
biggest, measured in the emulator after its last change (tools/efepresence.py)."""
import unittest

from tools import efepresence as P


class Presence(unittest.TestCase):
    def test_every_entry_measured_fresh_and_within_bounds(self):
        self.assertEqual(P.check(P.load(P.SPEC), P.load(P.TABLE)), [])

    def test_a_changed_entry_is_stale(self):
        spec = {'1': {'name': 'A', 'scale': 0.2}}
        table = {'1': dict(area=0.05, height=0.4, seconds=4, entry=P.entry_hash(spec['1']))}
        self.assertEqual(P.check(spec, table), [])
        spec['1']['scale'] = 0.3
        self.assertIn('changed', P.check(spec, table)[0])

    def test_pins_and_sounds_do_not_make_an_entry_stale(self):
        e = {'name': 'A', 'dw3': {'model': 'M', 'pin': 'a'}}
        f = {'name': 'A', 'dw3': {'model': 'M', 'pin': 'b', 'pins': {'dw3-us': 'c'}}, 'sounds': [[0, 2]], 'hit_sound': 4}
        self.assertEqual(P.entry_hash(e), P.entry_hash(f))
        self.assertEqual(P.entry_hash({'name': 'B', 'dcb': {'attack': 1, 'pin': 'a'}}),
                         P.entry_hash({'name': 'B', 'dcb': {'attack': 1, 'pin': 'b'}}))

    def test_small_and_huge_fail(self):
        spec = {'1': {'name': 'A'}, '2': {'name': 'B'}}
        h = P.entry_hash({'name': 'A'}), P.entry_hash({'name': 'B'})
        table = {'1': dict(area=P.FLOOR / 2, entry=h[0]), '2': dict(area=P.CEILING * 2, entry=h[1])}
        self.assertEqual(len(P.check(spec, table)), 2)


if __name__ == '__main__':
    unittest.main()
