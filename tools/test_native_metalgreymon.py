"""Disc-derived native movement, approved colours and save-slot compatibility."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
import motiondiscidentity
import motionstorage
import species
from tools.models import metalgreymon
from tools.derive.importers import Provider


@unittest.skipUnless(Path('extracted/CHDAT/MMD0/MTGR.MMD').exists(), 'needs the player extraction')
class NativeMetalGreymon(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.texture = metalgreymon.build('extracted')
        cls.model = mmd.MMD.parse(cls.data, 30)
        cls.native = mmd.MMD.load('extracted/CHDAT/MMD0/MTGR.MMD', 12)
        cls.record = json.loads(Path('content/species/224-metalgreymonvaccine.json').read_text())

    def test_field_slots_zero_through_four_have_identical_frames_and_events(self):
        for slot in range(5):
            with self.subTest(slot=slot):
                self.assertEqual(animsheet.slot_frames(self.model, 30, slot),
                                 animsheet.slot_frames(self.native, 30, slot))

    def test_care_and_battle_programs_are_native_without_retiming(self):
        def program(model, slot):
            return motiondiscidentity.program(model.anims.anims[model.anims.table[slot]])
        self.assertEqual(motiondiscidentity.changed_programs(self.native, self.model), list(range(0x2E, 0x3C)))
        for destination, source in enumerate(metalgreymon.TECHNIQUE_SLOTS, 0x2E):
            with self.subTest(slot=destination):
                self.assertEqual(program(self.model, destination), program(self.native, source))

    def test_approved_palette_and_polygon_selections(self):
        # Pins from the approved prototype's stripes output, before technique routing.
        self.assertEqual(hashlib.sha256(self.texture).hexdigest(),
                         '2c58ce10dde4e2088d73d6b40091af99806cf71a5ac198a6198e3df79763d68b')
        self.assertEqual(hashlib.sha256(self.model.tmd.build()).hexdigest(),
                         'e1bde9429cb4124d0a3b5737f325516e52d4acde91f3ff845621679a512e9953')
        native = mmd.load_tim('extracted/CHDAT/ALLTIM.TIM', 12)
        actual = mmd.Tim4(self.texture)
        self.assertEqual(actual.idx, native.idx)
        self.assertEqual(actual.pal[3], native.pal[3])
        self.assertEqual(actual.pal[8:], native.pal[8:])
        self.assertGreaterEqual(actual.ch, 8)

    def test_native_rig_dimensions_effects_and_visual_care_settings(self):
        native = json.loads(Path('content/species/12-metalgreymonvirus.json').read_text())
        self.assertEqual(self.record['model']['skeleton'], species.originals().rec[12]['bones'])
        for key in ('radius', 'height'):
            self.assertEqual(self.record['model'][key], native['model'][key])
        for key in ('voice', 'status_screen_position', 'item_distance'):
            self.assertEqual(self.record['partner'][key], native['partner'][key])
        training = self.record['partner']['training']
        self.assertEqual(training['hit_tick'], native['partner']['training']['hit_tick'])
        self.assertEqual(motiondiscidentity.program(self.model.anims.anims[self.model.anims.table[training['animation']]]),
                         motiondiscidentity.program(self.native.anims.anims[self.native.anims.table[native['partner']['training']['animation']]]))
        self.assertEqual(self.record['voice'], native['voice'])
        self.assertEqual(self.record['effects_like'], 12)
        self.assertFalse(self.record.get('effect_origins'))
        self.assertNotIn('sizing', self.record)
        self.assertEqual(self.record['condition_bubble'],
                         json.loads(Path('content/tables/effects.json').read_text())['conditionFxOffsets'][12])

    def test_existing_equipped_slots_keep_their_techniques_and_native_programs(self):
        moves = species.techniques_from_json(self.record['techniques'], '224')
        self.assertEqual(moves, [27, 28, 29, 25, 31, 24, 6, 1, 7, 4, 46, 45, 44, 79, 255, 255])
        for index in range(14):
            self.assertIsNotNone(self.model.anims.table[0x2E + index])
        report = motionstorage.require(self.data, 30)
        self.assertEqual(report['resident_bytes'], 78480)
        self.assertLessEqual(max(row['sector_read_bytes'] for row in report['cold_reads']), 8192)

    def test_imports_provider_uses_native_disc_builder_without_source_game_replay(self):
        with tempfile.TemporaryDirectory() as work:
            model, texture = Provider(Path(work) / 'no-source-games', work).model(224)
        self.assertEqual((model, texture), (self.data, self.texture))


if __name__ == '__main__':
    unittest.main()
