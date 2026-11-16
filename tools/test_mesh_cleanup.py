"""Surface identity, co-facing diagnostics and primitive PSX sorting rules."""
import copy
from pathlib import Path
import sys
import unittest

import numpy as np
sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
import mmd
from tools.test_meshcheck import model, box_object
from tools.test_audit_textures import tim, GREY
from tools.models import meshcheck as MC, mesh_cleanup as C, mesh_glitch as G, psx_blend as R


class Duplicates(unittest.TestCase):
    def pair(self, mode=None):
        ob, vv, nn = box_object()
        ob.prims = ob.prims[:1]*2
        if mode:
            d = ob.prims[1].decode(); d['mode'] = mode
            d['colors'][0] = (*d['colors'][0][:3], mode)
            ob.prims[1] = mmd.Prim.encode(d)
        return model((ob, vv, nn))

    def test_exact_opaque_duplicate_is_removed(self):
        m, _ = self.pair()
        self.assertEqual(C.duplicate_surfaces(m), 1)
        self.assertEqual(len(m.tmd.objects[0].prims), 1)

    def test_opposite_winding_and_distinct_colours_survive(self):
        for kind in ('winding', 'colour'):
            m, _ = self.pair(); d = m.tmd.objects[0].prims[1].decode()
            if kind == 'winding':
                d['verts'][1:3] = d['verts'][2:0:-1]
            else:
                d['colors'][0] = (100, 20, 40, d['mode'])
            m.tmd.objects[0].prims[1] = mmd.Prim.encode(d)
            self.assertEqual(C.duplicate_surfaces(m), 0)

    def test_translucent_duplicates_survive(self):
        m, _ = self.pair(0x2a)
        m.tmd.objects[0].prims[0] = copy.deepcopy(m.tmd.objects[0].prims[1])
        self.assertEqual(C.duplicate_surfaces(m), 0)

    def test_detector_finds_same_indices_same_uv_that_legacy_skips(self):
        m, bones = self.pair(); mc = MC.Model(m, bones)
        self.assertEqual(MC.zfight(mc, mc.world(mc.rest()), mc.height()[0]), [])
        self.assertGreater(G.coplanar_details(mc)['cofacing_pairs'], 0)
        C.duplicate_surfaces(m)
        self.assertEqual(G.coplanar_details(MC.Model(m, bones))['cofacing_pairs'], 0)

    def test_unreviewed_geometry_fails_closed(self):
        m, bones = self.pair()
        with self.assertRaisesRegex(ValueError, 'reviewed final TMD'):
            C.apply(m.build(), bones, 405)


class CrossingDepth(unittest.TestCase):
    def test_vectorized_depth_matches_scalar_and_symmetric_reversal(self):
        from tools.models.field_animations import meshclash as X
        rng = np.random.default_rng(9)
        a, b = rng.normal(size=(16, 3, 3))*30, rng.normal(size=(12, 3, 3))*30
        hit = np.zeros((len(a), len(b)), bool)
        for k in range(3):
            hit |= X._crossings(a[:, k], a[:, (k+1)%3], b)
            hit |= X._crossings(b[:, k], b[:, (k+1)%3], a).T
        expected = 0.
        for i, j in zip(*np.nonzero(hit)):
            n = np.cross(b[j, 1]-b[j, 0], b[j, 2]-b[j, 0])
            n = n/(np.linalg.norm(n)+1e-9)
            d = (a[i]-b[j, 0])@n
            expected = max(expected, min(max(d.max(), 0), max(-d.min(), 0)))
        count, depth = X.crossing(a, b)
        self.assertEqual(count, int(hit.sum()))
        self.assertAlmostEqual(depth, expected)
        reverse = X.crossing(b, a)[1]
        self.assertAlmostEqual(X.crossing(a, b, symmetric=True)[1], max(depth, reverse))
        self.assertAlmostEqual(X.crossing(a, b, symmetric=True)[1], X.crossing(b, a, symmetric=True)[1])
        X.crossing(a.astype(int), b.astype(int), symmetric=True)


class PieceRepairs(unittest.TestCase):
    def test_translation_and_uniform_fit_preserve_authored_normals(self):
        m, _ = model(box_object())
        old = list(m.tmd.norms)
        C.transform_piece(m, 0, offset=(0, 0, -8))
        self.assertEqual(m.tmd.norms, old)
        C.transform_piece(m, 0, scale=(.7, .7, .7))
        self.assertEqual(m.tmd.norms, old)

    def test_layer_offset_leaves_base_and_other_pools_fixed(self):
        ob, vv, nn = box_object()
        ob.prims = ob.prims[:1]*2
        m, _ = model((ob, vv, nn), box_object())
        base = m.tmd.objects[0].prims[1].decode()['verts']
        other = list(m.tmd.obj_verts(1))
        C.offset_layer(m, 0, [0], (0, 0, -6))
        overlay = m.tmd.objects[0].prims[0].decode()['verts']
        vertices = m.tmd.obj_verts(0)
        self.assertEqual(list(m.tmd.obj_verts(1)), other)
        for a, b in zip(base, overlay):
            self.assertNotEqual(a, b)
            self.assertEqual(vertices[b][:3], (vertices[a][0], vertices[a][1], vertices[a][2]-6))

    def test_joint_extension_preserves_momentum_events_and_every_decoded_tick(self):
        m, bones = model(box_object())
        pose = [[4096]*3+[0]*6 for _ in bones]
        frames = [copy.deepcopy(pose) for _ in range(8)]
        for i, p in enumerate(frames):
            p[1][6] = 10+i*3
        m.anims.anims = [mmd.encode_anim(frames, len(bones), 0, [])]
        m.anims.table = [0]
        before, info = mmd.simulate(m.anims.anims[0], len(bones))
        size = len(m.anims.anims[0].build())
        C.translate_bone(m, 1, 0, 40)
        after, result = mmd.simulate(m.anims.anims[0], len(bones))
        expected = copy.deepcopy(before)
        for p in expected:
            p[1][6] += 40
        self.assertEqual(after, expected)
        self.assertEqual(result, info)
        self.assertEqual(len(m.anims.anims[0].build()), size)


class Renderer(unittest.TestCase):
    def mesh(self, vertices, prims):
        ob = mmd.TMDObject(); ob.prims = prims
        m, bones = model((ob, [tuple(v)+(0,) for v in vertices], [(0,0,-4096,0)]))
        tex = tim([GREY], lambda idx: idx.__setitem__(slice(None), bytes([15])*len(idx)))
        return MC.Model(m, bones, tex)

    def face(self, ids, u=0):
        mode = 0x2c if len(ids) == 4 else 0x24
        return mmd.Prim.encode(dict(mode=mode, flag=0, verts=ids, norms=[0],
            uv=[(u,0)]*len(ids), cba=488<<6, tsb=5))

    def paint(self, mc):
        idx = np.zeros((128, 256), np.uint8); idx[:, 32:] = 1
        mc.tex = idx, np.array([[31, 31<<5]], np.uint16), None
        return mc

    def test_quad_second_half_uses_first_half_culling(self):
        face = self.face([0,1,2,3]).decode()
        face['uv'] = [(0,0),(0,0),(63,0),(63,0)]
        m = self.paint(self.mesh([(0,0,0),(80,0,0),(0,80,0),(5,5,20)], [mmd.Prim.encode(face)]))
        quad, frame = R.render(m, size=100)
        from tools.models.mesh_stability import split_quad
        m.m.tmd.objects[0].prims = split_quad(m.m.tmd.objects[0].prims[0])
        split = self.paint(MC.Model(m.m, m.bones, m.tim))
        tri, _ = R.render(split, size=100, frame=frame)
        self.assertGreater(np.count_nonzero(quad != tri), 100)
        # Reverse the first half: libgs must then reject BOTH halves.
        face['verts'] = [0,2,1,3]
        m.m.tmd.objects[0].prims = [mmd.Prim.encode(face)]
        culled = self.paint(MC.Model(m.m, m.bones, m.tim))
        img, _ = R.render(culled, size=100, frame=frame)
        self.assertFalse(np.any(np.all(img == [255,0,0], axis=-1)))

    def test_depth_tie_uses_reverse_insertion_not_sub_bin_depth(self):
        m = self.paint(self.mesh([(0,0,2),(80,0,2),(0,80,2),
                                 (0,0,1),(80,0,1),(0,80,1)],
                                [self.face([0,1,2], 63), self.face([3,4,5], 0)]))
        # Both depths fall in bin 0. The first packet draws last (green).
        image, frame = R.render(m, size=100)
        self.assertEqual(image[30,30].tolist(), [0,255,0])
        # Shift the bins across the pair: nearer red then draws last.
        image, _ = R.render(m, size=100, frame=frame, depth_offset=2.5)
        self.assertEqual(image[30,30].tolist(), [255,0,0])


if __name__ == '__main__':
    unittest.main()
