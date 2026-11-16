"""Blade UV clipping, bounded normal funding, and complete decoded preservation."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'tools')]
import mmd
import motionstorage
from tools.models import mesh_omnimon as O, mesh_stability as S, meshcheck as MC, omnimon_render, psx_blend
from tools.models import mesh_omnimon_evidence as E
from tools.test_meshcheck import box_object, model


class SurfaceFits(unittest.TestCase):
    def test_render_checkpoints_cover_aliases_and_invalidate_changed_poses(self):
        from tools.test_audit_textures import tim, GREY
        from tools.models.mesh_cleanup import rotate_clip_bone
        m, bones = model(box_object())
        frames = [[[4096]*3+[0]*6 for _ in bones] for _ in range(2)]
        m.anims.anims = [mmd.encode_anim(frames, len(bones), 0, [])]
        m.anims.table = [0, 0]
        with tempfile.TemporaryDirectory() as temp:
            before, after, out = (Path(temp)/s for s in ('before', 'after', 'out'))
            for folder in (before, after):
                folder.mkdir()
                (folder/'461.MMD').write_bytes(m.build())
                (folder/'461.TIM').write_bytes(tim([GREY], lambda pixels: None))
                (folder/'index.json').write_text(json.dumps({'461':dict(name='fixture', bones=bones)}))
            result = E.render_all(before, after, out, jobs=1, size=64)
            self.assertTrue(result['complete'])
            self.assertEqual(result['frames'], 4)
            self.assertEqual(result['views'], 32)
            self.assertEqual(result['unique_clip_pose_sequences'], 1)
            self.assertEqual(result['rendered_unique_frames'], 1)
            with mock.patch.object(E, '_render_slot', side_effect=AssertionError('unexpected rerender')):
                replay = E.render_all(before, after, out, jobs=1, size=64)
            self.assertEqual(result['changed_pixels'], replay['changed_pixels'])
            old = replay['slots'][0]['inputs']
            rotate_clip_bone(m, 0, 1, (0, 10, 0))
            (after/'461.MMD').write_bytes(m.build())
            updated = E.render_all(before, after, out, jobs=1, size=64)
            self.assertNotEqual(old, updated['slots'][0]['inputs'])
            self.assertGreater(updated['changed_pixels'], 0)

    def test_two_phase_renderer_matches_reference_on_native_primitive_fixture(self):
        import numpy as np
        m, bones = model(box_object())
        scene = MC.Model(m, bones)
        for yaw, pitch in ((0, 0), (.7, .5), (2., -.2)):
            images, frame, _ = omnimon_render.phases(scene, yaw, pitch, size=96)
            for phase, image in zip((0, 2), images):
                expected, _ = psx_blend.render(scene, yaw, pitch, size=96, frame=frame, depth_offset=phase)
                np.testing.assert_array_equal(image, expected)

    def test_blade_keeps_tip_and_clips_rather_than_squeezes_the_inscription(self):
        m, _ = model(box_object())
        ob = copy.deepcopy(m.tmd.objects[0])
        ob.vert_start, ob.nvert = 0, 4
        m.tmd.objects = [mmd.TMDObject() for _ in range(6)]+[ob]
        m.tmd.verts = [(-7, 3, -14, 0), (-7, 3, 14, 0),
                       (-7, 214, -14, 0), (-7, 214, 14, 0)]
        ob.prims = [mmd.Prim.encode(dict(mode=0x3c, flag=0, verts=[0, 1, 2, 3], norms=[0]*4,
            uv=[(0, 0), (40, 0), (0, 211), (40, 211)], cba=31232, tsb=5, colors=[(128, 128, 128, 0x3c)]))]
        O.cut_blade(m)
        self.assertEqual([v[1] for v in m.tmd.verts], [150, 150, 214, 214])
        self.assertEqual(ob.prims[0].decode()['uv'], [(0, 147), (40, 147), (0, 211), (40, 211)])
        self.assertEqual(len(ob.prims), 1)

    def test_surface_transport_rejects_a_collapsed_triangle(self):
        m, _ = model(box_object())
        with self.assertRaisesRegex(ValueError, 'collapsed'):
            O.fit_surface(m, 0, lambda x, y, z: (0, 0, 0))

    def test_normal_funding_keeps_opposite_faces_and_bounds_lighting_error(self):
        m, _ = model(box_object())
        obj = m.tmd.objects[0]
        # Replace the first face's normal with a nearly identical entry.
        # Its opposing face must retain the opposite direction.
        n = m.tmd.norms[0]
        opposite = next(i for i, v in enumerate(m.tmd.norms)
                        if sum(a*b for a, b in zip(O._unit(n[:3]), O._unit(v[:3]))) < -.99)
        q = O._unit([n[0]+20, n[1]+20, n[2]+20])
        m.tmd.norms.append(tuple(round(v*4096) for v in q)+(0,))
        obj.nnorm += 1
        d = obj.prims[0].decode()
        d['norms'] = [len(m.tmd.norms)-1]*len(d['norms'])
        obj.prims[0] = mmd.Prim.encode(d)
        vertices, packets = list(m.tmd.verts), S.packet_bytes(m)
        report = O.merge_near_normals(m)
        self.assertGreater(report['merged_normals'], 0)
        self.assertLessEqual(report['max_normal_error_degrees'], 1)
        self.assertEqual(m.tmd.verts, vertices)
        self.assertEqual(S.packet_bytes(m), packets)
        self.assertIn(opposite, {i for p in obj.prims for i in p.decode()['norms']})
        self.assertEqual(set(obj.prims[0].decode()['norms']), {0})


@unittest.skipUnless((ROOT/'build/before/index.json').exists() and
                     (ROOT/'build/after/index.json').exists(), 'private Omnimon fixtures unavailable')
class CompleteModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bones = json.loads((ROOT/'build/before/index.json').read_text())['461']['bones']
        cls.models = [MC.Model((ROOT/f'build/{stage}/461.MMD').read_bytes(), cls.bones)
                      for stage in ('before', 'after')]

    def test_every_frame_retains_root_scales_timing_events_and_aliases(self):
        before, after = self.models
        self.assertEqual(before.m.anims.table, after.m.anims.table)
        allowed = {(3, 4), (3, 5), (9, 4), (9, 5), (10, 3), (10, 4),
                   (10, 5), (23, 3), (24, 3), (24, 8)}
        slots, ticks = 0, 0
        for slot in before.slots():
            ap, ai = mmd.simulate(before.m.anims.anims[before.m.anims.table[slot]], 25, slot=slot)
            bp, bi = mmd.simulate(after.m.anims.anims[after.m.anims.table[slot]], 25, slot=slot)
            self.assertEqual(ai, bi, slot)
            self.assertEqual(len(ap), len(bp), slot)
            slots += 1
            ticks += len(ap)
            for a, b in zip(ap, bp):
                for bone in range(25):
                    for channel in range(9):
                        if (bone, channel) not in allowed:
                            self.assertEqual(a[bone][channel], b[bone][channel], (slot, bone, channel))
                self.assertEqual(b[24][8], a[24][8]+30)
        self.assertEqual((slots, ticks), (52, 2116))

    def test_two_phase_renderer_matches_reference_on_animated_textured_cloth(self):
        import numpy as np
        for scene in self.models:
            scene.tim = mmd.Tim4((ROOT/'build/after/461.TIM').read_bytes())
            scene.tex = scene._texture()
            for slot, tick, yaw in ((0, 0, .7), (40, 3, 1.1), (47, 12, 2.5)):
                pose = scene.poses(slot, 6000)[tick]
                images, frame, _ = omnimon_render.phases(scene, yaw, .5, size=160, pose=pose)
                for phase, image in zip((0, 2), images):
                    expected, _ = psx_blend.render(scene, yaw, .5, size=160, frame=frame,
                                                   pose=pose, depth_offset=phase)
                    np.testing.assert_array_equal(image, expected)

    def test_geometry_packets_and_own_resident_budget(self):
        before, after = self.models
        self.assertEqual(S.packet_bytes(after.m)-S.packet_bytes(before.m), 336)
        self.assertEqual(len(before.tris), len(after.tris))
        # The repaired blade/cape are the only newly moved surface positions.
        for bone in before.local:
            if bone not in (7, 23, 24):
                self.assertEqual(sorted(map(tuple, before.local[bone])), sorted(map(tuple, after.local[bone])))
        for stage, m in zip(('before', 'after'), (before, after)):
            report = motionstorage.audit((ROOT/f'build/{stage}/461.MMD').read_bytes(), 25)
            self.assertTrue(report['fits'])
            if stage == 'before':
                budget = report['resident_bytes']
            else:
                self.assertLessEqual(report['resident_bytes'], budget)
            for tri in m.tris:
                O._normal(m.local[tri[0]], tri[3])


if __name__ == '__main__':
    unittest.main()
