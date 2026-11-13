"""BomberNanimon (232) moves exactly like native Nanimon: its rig and field programs are Nanimon's own."""
import copy
import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
import motionstorage
from tools.models.field_animations import native_binding as binding

FIELD = [0, 1, 2, 3, 4]


class BomberNanimonNative(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(os.environ.get('BINDING_MODELS', 'build/imported-model-edit/edit'))
        files = list(source.glob('232-*.MMD'))
        native_path = Path(mmd.EXTRACTED) / 'CHDAT/MMD1/NANI.MMD'
        if not files or not native_path.exists():
            raise unittest.SkipTest('needs the imported 232 model (edit.py get 232) and the player DW1 extraction')
        cls.recipe = json.loads(binding.MANIFEST.read_text())['232']
        cls.record = json.loads(next(Path('content/species').glob('232-*.json')).read_text())
        cls.data, cls.proof = binding.bind(files[0].read_bytes(), cls.record['model']['skeleton'], cls.recipe)
        cls.rig = cls.proof['generated_skeleton']
        cls.model = mmd.MMD.parse(cls.data, len(cls.rig))
        cls.model.type = 232
        cls.native = mmd.MMD.load(str(native_path), 53)

    def test_rig_is_nanimons(self):
        self.assertEqual(self.rig and [p for _, p in self.rig], [p for _, p in mmd.exe().skeleton[53]])
        self.assertEqual(len(self.rig), 20)
        self.assertEqual(self.recipe['donor'], 53)
        self.assertEqual(self.recipe['scale'], 1.0)

    def test_field_slots_are_nanimons_unchanged(self):
        for slot in FIELD:
            with self.subTest(slot=slot):
                expected = copy.deepcopy(self.native.anims.anims[self.native.anims.table[slot]])
                expected.instrs = [i for i in expected.instrs if i['op'] != 'tex']
                expected.tail = b''
                self.assertEqual(self.model.anims.anims[self.model.anims.table[slot]].build(), expected.build())
                before, loop, _ = animsheet.slot_frames(self.native, 20, slot)
                after, new_loop, _ = animsheet.slot_frames(self.model, 20, slot)
                self.assertEqual((len(after), new_loop), (len(before), loop))
                for a, b in zip(after, before):
                    self.assertEqual(a, b)

    def test_training_clip_is_nanimons_training_clip(self):
        training = copy.deepcopy(self.native.anims.anims[self.native.anims.table[46]])
        training.instrs = [i for i in training.instrs if i['op'] != 'tex']
        training.tail = b''
        self.assertEqual(self.record['partner']['training'], {'animation': 57, 'hit_tick': 10})
        self.assertEqual(self.model.anims.anims[self.model.anims.table[57]].build(), training.build())

    def test_effect_points_stay_on_the_rig(self):
        patch = self.recipe['species_patch']
        for origin in patch['effect_origins']:
            self.assertLess(origin[4], 20)
        self.assertLess(patch['condition_bubble'][3], 20)

    def test_resident_animation_buffer(self):
        storage = motionstorage.require(self.data, len(self.rig))
        self.assertTrue(storage['fits'])
        self.assertLessEqual(storage['resident_bytes'], storage['resident_limit'])
        self.assertEqual(storage['resident_limit'], 100352)
        self.assertEqual(storage['resident_bytes'], 75080)

    def test_battle_originals(self):
        # the source game's own battle clips, retargeted onto the donor rig; all but the idles (which loop at their own
        # speed) as long as the donor's clip they replace, since technique effects are timed to it
        made = self.proof['battle_originals']
        self.assertEqual(sorted(int(s) for s in made), self.recipe['battle_originals']['slots'])
        for slot, row in made.items():
            if int(slot) not in (33, 34):
                self.assertEqual(row['frames'], row['donor_frames'])

    def test_every_piece_is_bound_once(self):
        objects = sorted(o for o, _ in self.rig if o >= 0)
        self.assertEqual(objects, list(range(len(self.model.tmd.objects))))
        self.assertEqual(set(map(int, self.recipe['map'])), set(range(1, 15)))


if __name__ == '__main__':
    unittest.main()
