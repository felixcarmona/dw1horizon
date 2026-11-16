"""Rigid-pool sharing, complete clip preservation and located gun-arm clearance."""
import copy
from pathlib import Path
import sys
import unittest

import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'tools')]
import mmd
import motionstorage
from tools.models import mesh_raidenmon as R, meshcheck as MC
from tools.models.mesh_round4 import load, sparse_crossing
from tools.test_meshcheck import model, box_object


def corners(m):
    result = []
    for oi, ob in enumerate(m.tmd.objects):
        vv, nn = m.tmd.obj_verts(oi), m.tmd.obj_norms(oi)
        for p in ob.prims:
            d = p.decode()
            result.append((oi, [tuple(vv[i]) for i in d.pop('verts')],
                           [tuple(nn[i]) for i in d.pop('norms')], d))
    return result


class IdenticalPools(unittest.TestCase):
    def test_shared_coordinates_keep_independent_transforms_and_all_corners(self):
        m, bones = model(box_object(), box_object())
        before = corners(m)
        sizes = [(o.nvert, o.nnorm) for o in m.tmd.objects]
        source = MC.Model(m, bones)
        pose = source.rest()
        pose[2][3:6] = [400, -700, 1200]
        pose[2][6:9] = [50, 100, -40]
        world = source.world(pose)
        report = R.share_identical_pools(m)
        m.anims.anims = [mmd.encode_anim([pose, pose], len(bones), 0)]
        m.anims.table = [0]
        parsed = mmd.MMD.parse(m.build(), len(bones))
        self.assertEqual(corners(parsed), before)
        self.assertEqual(sizes, [(o.nvert, o.nnorm) for o in parsed.tmd.objects])
        self.assertGreater(sum(v['saved_bytes'] for v in report.values()), 0)
        for b, vv in MC.Model(parsed, bones).world(pose).items():
            np.testing.assert_array_equal(vv, world[b])

    def test_fourth_component_and_different_sets_prevent_sharing(self):
        m, _ = model(box_object(), box_object())
        oi = m.tmd.objects[1].vert_start
        v = m.tmd.verts[oi]
        m.tmd.verts[oi] = (*v[:3], 1)
        report = R.share_identical_pools(m)
        self.assertEqual(report['verts']['saved_bytes'], 0)


@unittest.skipUnless((ROOT/'build/raiden-before/336.MMD').exists(), 'private model fixture unavailable')
class CompleteRaidenmon(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before = load(ROOT/'build/raiden-before', 336)
        cls.after = copy.deepcopy(cls.before.m)
        cls.report = R.apply(cls.after, cls.before.bones)
        cls.raw = cls.after.build()
        cls.parsed = MC.Model(cls.raw, cls.before.bones)

    def test_every_clip_root_events_timing_aliases_and_unselected_channels(self):
        self.assertEqual(self.before.m.anims.table, self.after.anims.table)
        self.assertEqual(corners(self.before.m), corners(self.parsed.m))
        ticks = 0
        for slot in self.before.slots():
            left, info = mmd.simulate(self.before.m.anims.anims[self.before.m.anims.table[slot]], 24, slot=slot)
            right, got = mmd.simulate(self.parsed.m.anims.anims[self.parsed.m.anims.table[slot]], 24, slot=slot)
            self.assertEqual(info, got)
            self.assertEqual(len(left), len(right))
            expected = copy.deepcopy(left)
            if slot == 43:
                for t, p in enumerate(expected):
                    for a, degrees in enumerate(R.gun_arm_detour(t)):
                        p[2][3+a] += round(degrees*4096/360)
            for p in expected:
                for a, degrees in enumerate((-60, 0, -15) if slot == 61 else (-15, -15, -30)):
                    p[10][3+a] += round(degrees*4096/360)
            self.assertEqual(expected, right, slot)
            ticks += len(left)
        self.assertEqual(ticks, 1684)

    def test_slot43_forearm_clears_every_foreign_piece_every_frame(self):
        m = self.parsed
        ts = {b: np.array([t[3] for t in m.tris if t[0] == b], int) for b in m.local}
        for tick, p in enumerate(m.poses(43, 6000)):
            w = m.world(p)
            for b, indices in ts.items():
                if b not in (2, 3) and len(indices):
                    self.assertEqual(sparse_crossing(w[3][ts[3]], w[b][indices])[0], 0, (tick, b))

    def test_slot61_claw_and_fingers_clear_foreign_pieces(self):
        m = self.parsed
        ts = {b: np.array([t[3] for t in m.tris if t[0] == b], int) for b in m.local}
        for tick, p in enumerate(m.poses(61, 6000)):
            w = m.world(p)
            for a in (11, 12, 13, 14):
                for b, indices in ts.items():
                    if b not in (10, 11, 12, 13, 14) and len(indices):
                        self.assertEqual(sparse_crossing(w[a][ts[a]], w[b][indices])[0], 0, (tick, a, b))

    def test_same_model_funds_animation_and_cold_reads_fit(self):
        before = motionstorage.audit(self.before.m.build(), 24)
        after = motionstorage.audit(self.raw, 24)
        self.assertTrue(after['fits'], after)
        self.assertLessEqual(after['resident_bytes'], before['resident_bytes'])
        self.assertEqual(self.report['identical_pools']['verts']['saved_bytes'], 888)
        self.assertEqual(self.report['identical_pools']['norms']['saved_bytes'], 184)


class NativeReviewRasterizer(unittest.TestCase):
    def test_reference_rules_for_bent_quads_ties_transparency_and_blending(self):
        from tools.test_mesh_cleanup import Renderer as Fixture
        from tools.models import psx_blend
        from tools.models.mesh_raidenmon_review import Renderer
        fixture = Fixture('test_quad_second_half_uses_first_half_culling')
        for mode in (0x24, 0x26):
            for abr in range(4):
                triangle = fixture.face([4, 5, 6], 63).decode()
                triangle['mode'] = mode
                triangle['tsb'] = 5 | abr << 5
                quad = fixture.face([0, 1, 2, 3]).decode()
                quad['uv'] = [(0,0), (63,0), (63,0), (0,0)]
                mesh = fixture.paint(fixture.mesh(
                    [(0,0,2),(80,0,2),(0,80,2),(5,5,22),
                     (0,0,1),(80,0,1),(0,80,1)],
                    [mmd.Prim.encode(quad), mmd.Prim.encode(triangle)]))
                mesh.tex[1][0] = [0, 0x8000 | 31 << 5]
                native = Renderer(mesh)
                for phase in (0, 2, 2.5):
                    for yaw in (0, .7, 3.2):
                        result, frame = native.render(yaw, .1, size=100, depth_offset=phase)
                        expected, _ = psx_blend.render(mesh, yaw, .1, size=100, frame=frame, depth_offset=phase)
                        np.testing.assert_array_equal(result, expected)


if __name__ == '__main__':
    unittest.main()
