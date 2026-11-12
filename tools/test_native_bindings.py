"""Replay native bindings against the actual source and native disc programs."""
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
import species
from tools.models.field_animations import native_binding as binding


class NativeBindings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = []
        source = Path(os.environ.get('BINDING_MODELS', 'build/angels/source'))
        binding.BASE_MODELS = str(source)      # an imported donor (`donor_species`) is read from the same folder
        for sid, recipe in json.loads(binding.MANIFEST.read_text()).items():
            files = list(source.glob(f'{sid}-*.MMD')) or list(source.glob(f'{sid}.MMD'))
            donor_files = list(source.glob(f"{recipe['donor_species']}-*.MMD")) if recipe.get('donor_species') else None
            if not files or not (donor_files if recipe.get('donor_species') else (Path(mmd.EXTRACTED)/recipe['model']).exists()):
                raise unittest.SkipTest('needs imported models and the player DW1 extraction')
            record = json.loads(next(Path('content/species').glob(f'{sid}-*.json')).read_text())
            data, proof = binding.bind(files[0].read_bytes(), record['model']['skeleton'], recipe)
            model = mmd.MMD.parse(data, len(proof['generated_skeleton']))
            if recipe.get('donor_species'):
                native = mmd.MMD.parse(binding.donor_model(recipe), mmd.exe().bone_count[recipe['donor']])
                native.type = recipe['donor']
            else:
                native = mmd.MMD.load(str(Path(mmd.EXTRACTED)/recipe['model']), recipe['donor'])
            cls.cases.append((recipe, record, data, proof, model, native))

    def test_full_native_hierarchy_and_mesh_coverage(self):
        for recipe, _, _, proof, model, native in self.cases:
            with self.subTest(species=recipe['species']):
                rig = proof['generated_skeleton']
                self.assertEqual([p for _, p in rig], [p for _, p in mmd.exe().skeleton[native.type]])
                self.assertEqual(sorted(o for o, _ in rig if o >= 0), list(range(len(model.tmd.objects))))
                self.assertTrue(all(p < len(rig) for _, p in rig))
                self.assertEqual(set(map(int, recipe['map'])), set(range(1, len(json.loads(next(Path('content/species').glob(f"{recipe['species']}-*.json")).read_text())['model']['skeleton']))))

    def test_programs_keep_native_rotations_scales_controls_and_timing(self):
        for recipe, _, _, proof, model, native in self.cases:
            for slot, index in enumerate(native.anims.table[:46]):
                if index is None:
                    continue
                with self.subTest(species=recipe['species'], slot=slot):
                    expected = copy.deepcopy(native.anims.anims[index])
                    for pose in expected.pose:
                        pose[-3:] = [round(v*recipe['scale']) for v in pose[-3:]]
                    for instruction in expected.instrs:
                        if instruction['op'] == 'key':
                            for group in instruction['bones']:
                                for channel in group['vals']:
                                    if channel in ('tx', 'ty', 'tz'):
                                        group['vals'][channel] = round(group['vals'][channel]*recipe['scale'])
                    for bone, offset in binding.spread_offsets(recipe, native).items():
                        pose = expected.pose[bone - 1]
                        pose[-3:] = [v + o for v, o in zip(pose[-3:], offset)]
                    expected.instrs = [i for i in expected.instrs if i['op'] != 'tex']
                    expected.tail = b''
                    if slot not in recipe.get('arm_pump', {}).get('slots', ()):  # re-posed arms: test_<species>_native
                        self.assertEqual(model.anims.anims[model.anims.table[slot]].build(), expected.build())
                    before, loop, _ = animsheet.slot_frames(native, len(proof['generated_skeleton']), slot)
                    after, new_loop, _ = animsheet.slot_frames(model, len(proof['generated_skeleton']), slot)
                    self.assertEqual((len(after), new_loop), (len(before), loop))

    def test_partner_actions_techniques_voice_and_2mb_storage(self):
        required = [0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 19, 21, 22, 24, 25, 27, 33, 34, 35, 36, 37, 40, 41, 42, 43, 44]
        for recipe, record, data, proof, model, _ in self.cases:
            with self.subTest(species=recipe['species']):
                for slot in required + list(range(46, 46+len(record['techniques']))):
                    self.assertIsNotNone(model.anims.table[slot], slot)
                notes = {i['note'] for a in model.anims.anims for i in a.instrs if i['op']=='sound' and i['bank']==4}
                self.assertFalse(notes - species.vball_keys(record['voice']))
                self.assertFalse(any(i['op']=='tex' for a in model.anims.anims for i in a.instrs))
                self.assertTrue(motionstorage.require(data, len(proof['generated_skeleton']))['fits'])

    def test_changed_sources_are_rejected(self):
        for recipe, record, _, _, _, _ in self.cases:
            with self.assertRaises(ValueError):
                binding.bind(b'changed', record['model']['skeleton'], recipe)


if __name__ == '__main__':
    unittest.main()
