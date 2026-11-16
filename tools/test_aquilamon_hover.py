"""A low mesh envelope must preserve the flap, care/battle acting and model heap."""
import json
import os
from pathlib import Path
import unittest

from tools.models import edit, audit_field
from tools.models.battle_qa import Rig
from tools.models.field_animations import aquilamon
import animsheet
import mmd
import motionstorage
from motiontailspace import interpolate_pose
from tools.models.hover import MeshHover


@unittest.skipUnless(os.environ.get('AQUILAMON_MODEL'), 'set AQUILAMON_MODEL to the reviewed pre-fix model')
class AquilamonHover(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(os.environ['AQUILAMON_MODEL']).read_bytes()
        cls.sk = json.loads((aquilamon.ROOT / 'content/species/188-aquilamon.json').read_text())['model']['skeleton']
        cls.output = aquilamon.lower_current(cls.source, cls.sk)

    def test_only_carrier_height_changes_and_other_slots_stay_exact(self):
        old, new = [mmd.MMD.parse(d, len(self.sk)) for d in (self.source, self.output)]
        self.assertEqual(old.tmd.build(), new.tmd.build())
        for slot, index in enumerate(old.anims.table):
            if index is None:
                continue
            a, la, ea = animsheet.slot_frames(old, len(self.sk), slot)
            b, lb, eb = animsheet.slot_frames(new, len(self.sk), slot)
            self.assertEqual((len(a), la, ea), (len(b), lb, eb))
            if slot not in (0, 1, 2, 3, 4, 18):
                self.assertEqual(old.anims.anims[index].build(), new.anims.anims[new.anims.table[slot]].build())
                continue
            for fa, fb in zip(a, b):
                for bone, (pa, pb) in enumerate(zip(fa, fb)):
                    for channel, (va, vb) in enumerate(zip(pa, pb)):
                        if (bone, channel) != (1, 7):
                            self.assertLessEqual(abs(va - vb), 1, (slot, bone, channel))

    def test_final_provider_and_condition_overlay_fit_and_keep_heap(self):
        tim = Path(os.environ['AQUILAMON_MODEL']).with_suffix('.TIM').read_bytes()
        final, _, record = edit.provider_output(188, self.output, tim)
        rig = Rig.from_mmd(final, record['model']['skeleton'], 188)
        for slot, (low, high) in {0: (30, 50), 1: (30, 50), 2: (80, 140),
                                  3: (30, 70), 4: (80, 140), 18: (30, 50)}.items():
            r = audit_field.hover_heights(rig, slot)
            self.assertGreaterEqual(r['lowest_min'], low - 2)
            self.assertLessEqual(r['lowest_peak'], high + 2)
            self.assertFalse(r['high_hover'])
        self.assertTrue(motionstorage.require(final, len(self.sk))['fits'])
        model = mmd.MMD.parse(final, len(self.sk))
        mesh = MeshHover(model, self.sk)
        for slot in (0, 1, 2, 3, 4, 18):
            frames, _, _ = animsheet.slot_frames(model, len(self.sk), slot)
            for a, b in zip(frames, frames[1:]):
                for alpha in (1365, 2730):
                    self.assertGreater(-mesh.floor(interpolate_pose(a, b, alpha)), 25)
        old = mmd.MMD.parse(self.source, len(self.sk))
        new = mmd.MMD.parse(final, len(self.sk))
        for slot in (5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 19, 33, 34, 35, 36):
            self.assertEqual(animsheet.slot_frames(old, len(self.sk), slot),
                             animsheet.slot_frames(new, len(self.sk), slot), slot)
