"""Whole-quad NCLIP regression and the stored Omnimon repair's geometry/storage proof."""
import collections
import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import mmd
from tools.models import meshcheck as qa
from tools.models import repair_omnimon_mesh as fix
from tools.test_meshcheck import box_object, model


def animated(m, vals):
    a = mmd.Anim()
    a.frame_count, a.has_scale = 8, True
    a.pose = [[4096, 4096, 4096, 0, 0, 0, 0, 0, 0]]
    a.instrs = [dict(op='key', frame=1, bones=[dict(bone=1, div=1, vals=vals)]), dict(op='end')]
    m.anims.anims, m.anims.table = [a], [0]
    return m


def corners(tmd):
    """Multiset of oriented GPU triangles and their texture/normal attributes."""
    result = collections.Counter()
    for oi, ob in enumerate(tmd.objects):
        for prim in ob.prims:
            p = prim.decode()
            for tri in ((0, 1, 2), (1, 3, 2)) if len(p['verts']) == 4 else ((0, 1, 2),):
                c = tuple((p['verts'][k], p['norms'][k if len(p['norms']) > 1 else 0] if p['norms'] else None,
                           tuple(p['uv'][k]) if p['uv'] else None,
                           tuple(p['colors'][k if len(p['colors']) > 1 else 0][:3]) if p['colors'] else None)
                          for k in tri)
                result[oi, c, p['mode'] & ~8, p['flag'], p['cba'], p['tsb']] += 1
    return result


class Detector(unittest.TestCase):
    def test_ordinary_facing_changes_are_not_bent_quads(self):
        m, bones = model(box_object())
        r = qa.flicker(qa.Model(animated(m, {'ry': 256}), bones))
        self.assertEqual(r['warped_quads'], [])
        self.assertGreater(r['clips'][0]['facing_changes'], 0)
        self.assertEqual(r['clips'][0]['collapsed_triangles'], [])

    def test_scale_collapse_is_detected(self):
        m, bones = model(box_object())
        r = qa.flicker(qa.Model(animated(m, {'sx': -1024}), bones))
        self.assertTrue(r['clips'][0]['collapsed_triangles'])

    def test_bent_quad_and_primitive_culling(self):
        import numpy as np
        ob, verts, norms = box_object()
        # A bow-tie projection: the first triangle is back facing while the
        # second is front facing. Both belong to one primitive.
        verts = [(0, 0, 0, 0), (100, 0, 0, 0), (0, -100, 0, 0), (100, 100, 100, 0)]
        ob.prims = [mmd.Prim.encode(dict(mode=0x28, flag=0, colors=[(200, 200, 200, 0x28)],
                                       norms=[0], verts=[0, 1, 2, 3]))]
        m, bones = model((ob, verts, norms))
        mc = qa.Model(m, bones)
        self.assertEqual(len(qa.warped_quads(mc)), 1)
        T = mc.tri_array(mc.world(mc.rest()))
        actual = qa.render(mc, T, 0)[3]
        old = qa.render(mc, T, 0, primitive_cull=False)[3]
        self.assertEqual(int(actual.sum()), 0)
        self.assertGreater(int(old.sum()), 0)
        r = qa.flicker(qa.Model(animated(m, {'rx': 256}), bones))
        self.assertTrue(r['clips'][0]['quad_facing'])
        self.assertFalse(np.isnan(r['clips'][0]['min_area']))

    def test_split_keeps_attributes_for_each_primitive_family(self):
        for mode, flag in ((0x28, 0), (0x2c, 0), (0x3c, 0), (0x2d, 1), (0x3d, 1), (0x38, 4)):
            nv, nuv, ncol, nn = mmd.prim_shape(mode, flag)
            p = mmd.Prim.encode(dict(mode=mode, flag=flag, verts=list(range(nv)), norms=list(range(nn)),
                uv=[(k * 7, k * 11) for k in range(nuv)], colors=[(k, 42, 84, mode) for k in range(ncol)],
                cba=31232, tsb=5))
            ob = mmd.TMDObject(); ob.prims = [p]
            tmd = mmd.TMD(); tmd.objects = [ob]
            before = corners(tmd)
            ob.prims = fix.split_quad(p)
            self.assertEqual(before, corners(tmd), (mode, flag))
            self.assertTrue(all(q.olen == mmd.OLEN[q.mode] for q in ob.prims))


class Omnimon(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(os.environ.get('OMNIMON_MESH_MODEL', 'build/imported-model-edit/edit/461-Omnimon.MMD'))
        if not path.is_file():
            raise unittest.SkipTest('needs edit.py get 461 or OMNIMON_MESH_MODEL')
        cls.data = path.read_bytes()
        cls.bones = json.loads((ROOT / 'content/species/461-omnimon.json').read_text())['model']['skeleton']

    def test_repair_preserves_surface_animation_and_budgets(self):
        data, proof = fix.repair(self.data, self.bones)
        before, after = (mmd.MMD.parse(d, len(self.bones)) for d in (self.data, data))
        self.assertEqual(corners(before.tmd), corners(after.tmd))
        self.assertEqual(before.tmd.verts, after.tmd.verts)
        self.assertEqual(before.tmd.norms, after.tmd.norms)
        self.assertEqual(before.anims.build(), after.anims.build())
        self.assertLessEqual(proof['primitives'], 713)
        self.assertTrue(proof['storage']['fits'])
        self.assertEqual(qa.warped_quads(qa.Model(data, self.bones)), [])
        self.assertEqual(fix.repair(data, self.bones)[0], data)


if __name__ == '__main__':
    unittest.main()
