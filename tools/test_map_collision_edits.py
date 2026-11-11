"""Reviewed native-map collision edits preserve floor, triggers and arrivals."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import content


class CollisionEdits(unittest.TestCase):
    def setUp(self):
        self.map = SimpleNamespace(collision=[0] * 10000)
        self.edits = [dict(tile=[37, 74], before=0, after=128, reason='Solid rock foot.')]

    def test_only_reviewed_tile_changes(self):
        content.apply_map_collision(self.map, self.edits, 'fixture')
        self.assertEqual(self.map.collision[7437], 128)
        self.assertEqual(sum(bool(v) for v in self.map.collision), 1)
        content.apply_map_collision(self.map, self.edits, 'fixture')
        self.assertEqual(sum(bool(v) for v in self.map.collision), 1)

    def test_refuse_stale_inputs_without_partial_edits(self):
        self.map.collision[7438] = 51
        edits = self.edits + [dict(tile=[38, 74], before=0, after=128, reason='Rock.')]
        with self.assertRaisesRegex(ValueError, 'expected'):
            content.apply_map_collision(self.map, edits, 'fixture')
        self.assertEqual(self.map.collision[7437], 0)

    def test_refuse_invalid_or_duplicate_tiles(self):
        for tile in ([-1, 0], [100, 0], [0, 100], [0.5, 0]):
            with self.subTest(tile=tile), self.assertRaises(ValueError):
                content.apply_map_collision(self.map, [dict(self.edits[0], tile=tile)], 'fixture')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            content.apply_map_collision(self.map, self.edits * 2, 'fixture')

    @unittest.skipUnless((ROOT / 'extracted/MAP/MAP2/TROP06.MAP').exists(), 'needs USA extraction')
    def test_amida_arrivals_and_trial_routes(self):
        import json
        import dwmap
        from maps import reach
        original = dwmap.MapFile((ROOT / 'extracted/MAP/MAP2/TROP06.MAP').read_bytes())
        edited = dwmap.MapFile(original.build())
        edits = json.loads((ROOT / 'content/maps/TROP06.json').read_text())['collision']
        content.apply_map_collision(edited, edits, 'TROP06')
        self.assertEqual(original.warps, edited.warps)
        self.assertEqual(original.camera, edited.camera)
        self.assertEqual(original.instances, edited.instances)
        self.assertEqual(original.digimon, edited.digimon)
        self.assertEqual(set(original.collision), set(edited.collision))
        self.assertEqual(reach.check_arrivals(edited), [])
        w = edited.warps[0]
        area = reach.reach(edited, starts=[(w['x'], w['z'])])
        visited = {reach.model_tile(x, z) for x, z in area}
        # All three trial goal triggers and the southern exit remain reachable.
        for value in (110, 68, 69, 70):
            self.assertTrue(any(edited.collision[z*100+x] == value for x, z in visited), value)
        for x, z in (e['tile'] for e in edits):
            self.assertTrue(edited.collision[z*100+x] & 128)

    @unittest.skipUnless((ROOT / 'extracted/MAP/MAP11/FACT06.MAP').exists(), 'needs USA extraction')
    def test_andromon_room_exit_spans_the_whole_bottom_edge(self):
        import json
        import dwmap
        from maps import reach
        original = dwmap.MapFile((ROOT / 'extracted/MAP/MAP11/FACT06.MAP').read_bytes())
        edited = dwmap.MapFile(original.build())
        edits = json.loads((ROOT / 'content/maps/FACT06.json').read_text())['collision']
        content.apply_map_collision(edited, edits, 'FACT06')
        # Only wall bytes beside the existing exit become the same exit trigger.
        changed = [i for i, (a, b) in enumerate(zip(original.collision, edited.collision)) if a != b]
        self.assertEqual(len(changed), len(edits))
        self.assertTrue(all(original.collision[i] == 128 and edited.collision[i] == 51 for i in changed))
        self.assertEqual(original.warps, edited.warps)
        self.assertEqual(original.digimon, edited.digimon)
        self.assertEqual(reach.check_arrivals(edited), [])
        # Every floor tile on the bottom row of the room (tiles 47-57) now ends in the exit.
        floor_edge = 61
        for x in range(47, 58):
            self.assertEqual(edited.collision[floor_edge*100+x], 0)
            self.assertEqual(edited.collision[(floor_edge+1)*100+x], 51, x)
        # A tamer walking south from the arrival at any column reaches the trigger.
        area = reach.reach(edited, seed_policy='spawn_coordinates')
        trigger_tiles = {reach.model_tile(x, z) for x, z in area if edited.collision[reach.model_tile(x, z)[1]*100+reach.model_tile(x, z)[0]] == 51}
        self.assertTrue({(x, 62) for x in range(47, 58)} <= trigger_tiles)


if __name__ == '__main__':
    unittest.main()
