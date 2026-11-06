"""Source preservation and storage gates for the reviewed player model repairs."""
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
import motionstorage
from motiondiscidentity import changed_programs
from motiontailspace import interpolate_pose


class PlayerModelReports(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(os.environ.get('MODEL_REPORT_DIR', 'build/reports'))
        if not (cls.root/'starmon-final.MMD').exists():
            raise unittest.SkipTest('needs the pre-edit and reviewed models in MODEL_REPORT_DIR')

    def load(self, path, sid):
        return mmd.MMD.load(str(self.root/path), sid)

    def test_walk_edits_preserve_mesh_rig_and_all_other_programs(self):
        for sid, before, after in (
            (243, 'before/243-Starmon.MMD', 'starmon-final.MMD'),
            (226, 'after-small-models/226-silphymon-field.MMD', 'silphymon-final.MMD'),
        ):
            with self.subTest(species=sid):
                old, new = self.load(before, sid), self.load(after, sid)
                self.assertEqual(old.tmd.build(), new.tmd.build())
                self.assertEqual(changed_programs(old, new), [2, 3, 4])
                self.assertTrue(motionstorage.require((self.root/after).read_bytes(), mmd.exe().bone_count[sid])['fits'])
                for slot in (2, 3, 4):
                    poses, loop, _ = animsheet.slot_frames(new, mmd.exe().bone_count[sid], slot)
                    self.assertEqual(loop, 0)
                    self.assertLess(len(poses), 40)
                    self.assertLess(poses[-1][0][8], poses[0][0][8])
                    self.assertGreater(len({tuple(p[1][3:9]) for p in poses}), 3)

    def test_complete_boots_clear_the_floor_at_ticks_and_blends(self):
        for sid, name, boots in ((243, 'starmon', (10, 11, 14, 15)),
                                 (226, 'silphymon', (14, 15, 18, 19))):
            model = self.load(name+'-final.MMD', sid)
            rig = mmd.exe().skeleton[sid]
            for slot in (2, 3, 4):
                frames, _, _ = animsheet.slot_frames(model, len(rig), slot)
                worst = -float('inf')
                for tick in range(len(frames)-1):
                    for alpha in (0, 1365, 2730, 4096):
                        pose = interpolate_pose(frames[tick], frames[tick+1], alpha)
                        pose[0][6:9] = [0, 0, 0]
                        matrices = mmd.bone_matrices(model, pose)
                        for bone in boots:
                            transform = matrices[bone]
                            worst = max(worst, max(sum(transform[1][k]*v[k] for k in range(3)) + transform[1][3]
                                                   for v in model.tmd.obj_verts(rig[bone][0])))
                self.assertLessEqual(worst, 1.5, (sid, slot, worst))

    def test_both_ears_keep_the_source_head_proportions(self):
        source = self.load('before/226-Silphymon.MMD', 226)
        final = self.load('silphymon-final.MMD', 226)
        pairs = []
        for obj in (2, 3, 4):
            a, b = source.tmd.obj_verts(obj), final.tmd.obj_verts(obj)
            self.assertEqual(len(a), len(b))
            pairs.extend((x, y) for p, q in zip(a, b) for x, y in zip(p[:3], q[:3]))
        scale = sum(x*y for x, y in pairs)/sum(x*x for x, _ in pairs)
        self.assertLess(max(abs(y-x*scale) for x, y in pairs), 1.5)

    def test_saberdramon_mesh_remains_the_untouched_disc_mesh(self):
        source = mmd.MMD.load('extracted/CHDAT/MMD3/SABD.MMD', 106)
        before = self.load('before/106-Saberdramon.MMD', 106)
        self.assertEqual(source.tmd.build(), before.tmd.build())
        source_texture = mmd.alltim_entry(Path('extracted/CHDAT/ALLTIM.TIM').read_bytes(), 106)
        before_texture = (self.root/'before/106-Saberdramon.TIM').read_bytes()
        self.assertEqual(source_texture, before_texture)


if __name__ == '__main__':
    unittest.main()
