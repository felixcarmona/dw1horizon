"""Attack timing changes one slot while retaining the imported pose vocabulary."""
import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mmd
from tools.models.technique_timing import apply, program


class TechniqueTiming(unittest.TestCase):
    def fixture(self):
        model = mmd.MMD()
        model.nbones = 2
        model.tmd = mmd.TMD()
        poses = [[[4096] * 3 + [0] * 6,
                  [4096] * 3 + [0, i * 12, 0, i * 20, -100, -i * 10]]
                 for i in range(20)]
        source = mmd.encode_anim(poses, 2, events=[(16, 'sound', dict(bank=4, note=17))])
        model.anims = mmd.AnimSection()
        model.anims.anims = [source]
        model.anims.table = [0] * 64
        spec = dict(techniques=['Megaton Punch', 'Power Crane'], model=dict(skeleton=[[-1, -1], [0, 0]]))
        recipe = dict(source='Power Crane', source_sha256=hashlib.sha256(source.build()).hexdigest(),
                      samples=[[0, 0], [11, 14], [14, 17], [19, 19]])
        return model, spec, recipe

    def test_contact_phase_and_recovery_preserve_source_poses(self):
        old, spec, recipe = self.fixture()
        data, proof = apply(old.build(), spec, {'Megaton Punch': recipe})
        new = mmd.MMD.parse(data, 2)
        source, _ = mmd.simulate(old.anims.anims[0], 2)
        actual, info = mmd.simulate(new.anims.anims[new.anims.table[46]], 2, slot=46)
        self.assertEqual(len(actual), len(source))
        for dst, src in ((0, 0), (11, 14), (14, 17), (19, 19)):
            self.assertEqual(actual[dst], source[src])
        self.assertIsNone(info['loop'])
        self.assertEqual(proof['changed_slots'], [46])
        self.assertTrue(proof['storage']['fits'])
        self.assertEqual(new.tmd.build(), old.tmd.build())
        for slot in range(64):
            if slot != 46:
                self.assertEqual(new.anims.anims[new.anims.table[slot]].build(), old.anims.anims[0].build())
        self.assertEqual([(bank, note) for _, bank, note in info['sounds']], [(4, 17)])
        self.assertLess(info['sounds'][0][0], 16)

    def test_changed_source_requires_review(self):
        old, _, recipe = self.fixture()
        recipe['source_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'source program changed'):
            program(old.anims.anims[0], 2, 47, recipe)

    def test_shortened_recovery_keeps_contact_endpoints_and_sound(self):
        old, _, recipe = self.fixture()
        recipe.update(ticks=12, samples=[[0, 0], [8, 16], [12, 19]])
        source, _ = mmd.simulate(old.anims.anims[0], 2)
        animation = program(old.anims.anims[0], 2, 47, recipe)
        actual, info = mmd.simulate(animation, 2, slot=47)
        self.assertEqual(len(actual), 13)
        self.assertEqual(actual[0], source[0])
        self.assertEqual(actual[8], source[16])
        self.assertEqual(actual[-1], source[-1])
        self.assertEqual(info['sounds'], [(8, 4, 17)])
        self.assertIsNone(info['loop'])

    def test_invalid_phase_order_is_rejected(self):
        old, _, recipe = self.fixture()
        recipe['samples'] = [[0, 0], [11, 17], [14, 14], [19, 19]]
        with self.assertRaisesRegex(ValueError, 'must increase'):
            program(old.anims.anims[0], 2, 47, recipe)


if __name__ == '__main__':
    unittest.main()
