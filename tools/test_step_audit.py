"""Footstep evidence must follow effect routing and the engine's max-key match."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tools.models.audit_steps import route, tones


class StepAudit(unittest.TestCase):
    def test_effect_ids_and_literal_voice_notes(self):
        self.assertEqual(route(1, 12), (0, 72))
        self.assertEqual(route(1, 17), (1, 61))
        self.assertEqual(route(1, 18), (1, 62))
        self.assertEqual(route(3, 52), (0, 52))
        self.assertEqual(route(4, 53), (0, 53))

    def test_tone_lookup_matches_max_instead_of_midi_range(self):
        class Vab:
            vags = [bytes(16)]
            progs = [dict(mvol=127)]
            def tones_of(self, program):
                return [dict(min=60, max=73, vag=1, center=90, shift=0,
                             vol=100, adsr1=0x80ff, adsr2=0x5fde)]
        self.assertEqual(tones(Vab(), 1, 12), [])
        found = tones(Vab(), 1, 13)
        self.assertEqual((found[0]['program'], found[0]['key'], found[0]['sample']), (0, 73, 1))
        self.assertEqual(found[0]['semitones'], -17)


if __name__ == '__main__':
    unittest.main()
