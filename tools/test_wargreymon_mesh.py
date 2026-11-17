"""Private final-provider regression; fixtures made by wargreymon_review.

WARGREYMON_MESH_FIXTURES may name another before/after fixture directory.
"""
import json
import os
from pathlib import Path
import unittest

from tools.models import meshcheck as C, mesh_cleanup, mesh_stability as S
from tools.models.wargreymon_review import shield_errors
import coldsplit


class WarGreymonMesh(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folder = Path(os.environ.get('WARGREYMON_MESH_FIXTURES', 'build/wargreymon'))
        if not (folder/'before/373.MMD').exists():
            raise unittest.SkipTest('private final provider fixture required')
        cls.before = (folder/'before/373.MMD').read_bytes()
        cls.after = (folder/'after/373.MMD').read_bytes()
        cls.bones = json.loads((folder/'before/index.json').read_text())['373']['bones']
        cls.tim = (folder/'before/373.TIM').read_bytes()

    def test_recipe_reproduces_final_output_within_existing_sector_read(self):
        actual, _ = mesh_cleanup.apply(self.before, self.bones, 373)
        self.assertEqual(actual, self.after)
        old = len(coldsplit.split(self.before, len(self.bones))[0])
        new = len(coldsplit.split(actual, len(self.bones))[0])
        self.assertLessEqual(new, (old+2047)//2048*2048)
        self.assertLessEqual(new, 49*2048)

    def test_every_animation_program_and_unrelated_piece_is_unchanged(self):
        a, b = [C.Model(d, self.bones, self.tim) for d in (self.before, self.after)]
        self.assertEqual(a.m.anims.table, b.m.anims.table)
        self.assertEqual([p.build() for p in a.m.anims.anims], [p.build() for p in b.m.anims.anims])
        for oi in range(20):
            if oi in (6, 8, 18, 19):
                continue
            self.assertEqual(list(a.m.tmd.obj_verts(oi)), list(b.m.tmd.obj_verts(oi)))
            self.assertEqual([p.raw for p in a.m.tmd.objects[oi].prims], [p.raw for p in b.m.tmd.objects[oi].prims])
        for oi in (6, 8):
            self.assertEqual(list(a.m.tmd.obj_verts(oi)), list(b.m.tmd.obj_verts(oi)))
        self.assertEqual(len(S.bent_quads(a.m))-len(S.bent_quads(b.m)), 4)

    def test_closed_shield_stops_torso_packets_winning_at_its_centre(self):
        import math
        a, b = [C.Model(d, self.bones, self.tim) for d in (self.before, self.after)]
        old, new = [], []
        for yaw in (160, 180, 200):
            for phase in range(4):
                old.append(shield_errors(a, a.poses(1)[8], math.radians(yaw), phase)[0])
                new.append(shield_errors(b, b.poses(1)[8], math.radians(yaw), phase)[0])
        self.assertGreater(sum(old), 0)
        self.assertLess(sum(new), sum(old)/4)


if __name__ == '__main__':
    unittest.main()
