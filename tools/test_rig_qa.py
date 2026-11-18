"""Rig contracts and the post-binding reshape regression."""
import copy
import unittest
from unittest import mock

from tools.models import rig_qa, clip_rig
from tools.models.field_animations import native_battle as battle


def pose(x=0, y=0):
    return [4096, 4096, 4096, 0, 0, 0, x, y, 0]


class RigQA(unittest.TestCase):
    def setUp(self):
        self.rig = [[-1, -1], [0, 0], [1, 1], [2, 1]]
        self.rest = [pose(), pose(y=-200), pose(x=100), pose(x=-100)]

    def family(self):
        return dict(slots=[33, 46], skeleton=copy.deepcopy(self.rig), rest=copy.deepcopy(self.rest))

    def test_matches_and_order_hierarchy_count_and_rest_are_independent(self):
        family = self.family()
        self.assertEqual(rig_qa.compare(self.rig, self.rest, [family]), [])
        family['skeleton'][2] = [2, 0]
        family['skeleton'].append([3, 1])
        family['rest'][2][6] = 120
        family['rest'][3][3] = 1024
        row, = rig_qa.compare(self.rig, self.rest, [family])
        self.assertEqual(row['count'], [5, 4])
        self.assertEqual(row['slots'], [33, 46])
        bone, other = row['bones']
        self.assertEqual(bone, dict(bone=2, object=[2, 1], parent=[0, 1], offset=[[120, 0, 0], [100, 0, 0]]))
        self.assertEqual(other['rotation'], [[1024, 0, 0], [0, 0, 0]])

    def test_late_fit_uses_reshaped_offsets_and_keeps_mesh_rotation_basis(self):
        ctx = dict(rig=self.rig, rest=copy.deepcopy(self.rest), hips=(1, 1), source_height=200, k=1)
        # The orientation constants are tied to the fitted mesh, not the idle's
        # current arm rotation. The two are deliberately different here.
        ctx['pieces'] = {2: 'mesh basis'}
        ctx['rest_rot'] = ['binding rotations']
        final = copy.deepcopy(self.rest)
        final[1][7] = -180
        final[2][6] = 75
        final[2][3] = 400
        model = mock.Mock()
        model.tmd.obj_verts.return_value = [(0, 180, 0, 0)]
        with mock.patch.object(battle.animsheet, 'slot_frames', return_value=([final], None, [])):
            clip_rig.fit_context(model, ctx)
            once = copy.deepcopy(ctx)
            clip_rig.fit_context(model, ctx)
        self.assertEqual(ctx, once)
        self.assertEqual(ctx['rest'][1][7], -180)
        self.assertEqual(ctx['rest'][2][6], 75)
        self.assertEqual(ctx['rest'][2][3], 0)
        self.assertEqual(ctx['rest_rot'], ['binding rotations'])
        self.assertEqual(ctx['pieces'], {2: 'mesh basis'})
        self.assertAlmostEqual(ctx['k'], 0.9)

    def test_dimensions_already_matching_do_not_refit_the_mesh(self):
        ctx = dict(rig=self.rig, rest=copy.deepcopy(self.rest))
        model = mock.Mock()
        with mock.patch.object(battle.animsheet, 'slot_frames', return_value=([self.rest], None, [])):
            clip_rig.fit_context(model, ctx)
        self.assertEqual(ctx, dict(rig=self.rig, rest=self.rest))
        model.tmd.obj_verts.assert_not_called()

    def test_animated_idle_is_distinct_from_a_changed_joint_dimension(self):
        final = copy.deepcopy(self.rest)
        final[1][7] = -180
        final[2][3] = 400
        model = mock.Mock()
        model.anims.table = [0]
        model.anims.anims = [mock.Mock(pose=[[]]*3, instrs=[])]
        with mock.patch.object(rig_qa.mmd.MMD, 'parse', return_value=model), \
                mock.patch.object(rig_qa.animsheet, 'slot_frames', return_value=([final], None, [])):
            report = rig_qa.audit(b'model', self.rig, [self.family()])
            self.assertFalse(report['mismatches'])
            self.assertTrue(report['reference_pose_changes'])
            final[2][6] = 75
            report = rig_qa.audit(b'model', self.rig, [self.family()])
            self.assertEqual(report['mismatches'][0]['bones'],
                             [dict(bone=2, offset=[[100, 0, 0], [75, 0, 0]])])

class AuthoringGuards(unittest.TestCase):
    def test_clearance_keeps_source_motion_and_unrelated_placements(self):
        import json
        from pathlib import Path
        import tempfile
        from tools.models import native_recipe
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, fits, operations = (root / name for name in ('bindings.json', 'fits.json', 'ops.json'))
            source = {'310': {'battle_originals': {'slots': [36, 40]}}}
            manifest.write_text(json.dumps(source))
            fits.write_text(json.dumps({'310': {'40': []}, '314': {'52': []}}))
            turn = {'op': 'turn', 'bone': 5, 'axis': 'x', 'deg': 4}
            operations.write_text(json.dumps({'36': [turn]}))
            with mock.patch.object(native_recipe, 'MANIFEST', manifest), \
                    mock.patch.object(native_recipe, 'FITS', fits), \
                    mock.patch('sys.argv', ['native_recipe', '310', '36', '--clearance', str(operations),
                                            '--reason', 'Reviewed clearance']):
                native_recipe.main()
            self.assertEqual(json.loads(manifest.read_text()), source)
            self.assertEqual(json.loads(fits.read_text()),
                             {'310': {'36': [turn], '40': []}, '314': {'52': []}})

    def test_fit_refuses_different_bone_counts_before_copying_channels(self):
        from tools.models import clip_repair
        with self.assertRaisesRegex(ValueError, 'same ordered bones'):
            clip_repair.fit_rig([[pose(), pose()]], [pose(), pose()], [pose()])
        with self.assertRaisesRegex(ValueError, 'same ordered bones'):
            clip_repair.fit_rig([[pose()]], [pose(), pose()], [pose(), pose()])

    def test_withdrawal_removes_repairs_and_dependent_shares(self):
        from tools.models.native_recipe import keep_donor
        recipe = dict(battle_originals=dict(slots=[33, 49], repairs={'49': [dict(op='damp')]},
                                           ticks={'49': 20}, share={'50': 49, '51': 33}))
        keep_donor(recipe, [49])
        self.assertEqual(recipe['battle_originals'], dict(slots=[33], repairs={}, ticks={}, share={'51': 33}))
        with self.assertRaises(ValueError):
            keep_donor(recipe, [40])


if __name__ == '__main__':
    unittest.main()
