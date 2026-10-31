"""Species-224 voice coverage and field-slot routing regressions."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import species


class MetalGreymonField(unittest.TestCase):
    def test_normal_gaits_can_follow_the_tamer_and_close_a_running_gap(self):
        from tools.models.field_animations.metal_greymon import FIELD_SPEEDS
        self.assertGreaterEqual(FIELD_SPEEDS[2], 20)
        self.assertGreater(FIELD_SPEEDS[4], 50)
        self.assertLess(FIELD_SPEEDS[3], FIELD_SPEEDS[2])

    def test_field_slots_cannot_be_redirected_by_technique_aliases(self):
        record = json.loads(Path('content/species/224-metalgreymonvaccine.json').read_text())
        for destination, source in record['model']['slot_aliases']:
            self.assertTrue(46 <= destination <= 61)
            self.assertTrue(46 <= source <= 61)

    def test_both_voice_tables_match_native_metalgreymon(self):
        record = json.loads(Path('content/species/224-metalgreymonvaccine.json').read_text())
        self.assertEqual(record['voice'], 12)
        self.assertEqual(record['partner']['voice'], 10)
        keys = species.vball_keys(record['voice'])
        if keys is None:
            self.skipTest('requires the player-extracted voice bank')
        # Happy, hit, faint and technique programs use these three voice notes;
        # footsteps use bank 1 and must not be mistaken for species voice notes.
        self.assertTrue({53, 54, 55} <= keys)


if __name__ == '__main__':
    unittest.main()
