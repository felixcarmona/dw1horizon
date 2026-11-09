"""Private-disc proof of the restored head and original console budgets."""
import os
from pathlib import Path
import sys
import unittest

sys.path[:0] = [str(Path(__file__).resolve().parent),str(Path(__file__).resolve().parents[1])]
import mmd
import motionstorage
from tools.derive.importers.vendor.dw3 import model as source_model
import dw3_extra


def triangles(model,oi):
    """Oriented triangles with corner attributes; pairing alone cannot change them."""
    norms = model.tmd.obj_norms(oi)
    out = set()
    for p in model.tmd.objects[oi].prims:
        d = p.decode()
        for corners in [(0,1,2)]+([(1,3,2)] if len(d['verts']) == 4 else []):
            verts = [(d['verts'][c],tuple(d['uv'][c]),tuple(norms[d['norms'][c]][:3])) for c in corners]
            out.add((min(tuple(verts[k:]+verts[:k]) for k in range(3)),d['cba'],d['tsb']))
    return out


class WarGrowlmonRepair(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path('build/mesh-evidence')
        paths = [Path(os.environ.get('WARGROWLMON_SOURCE','build/imported-model-edit/source-games/dw2003/disc/AAA/DAT/FIGHT/MODEL/M368MGRW.BIN')),
                 Path(os.environ.get('WARGROWLMON_BEFORE',str(root/'326-shipped.MMD'))),
                 Path(os.environ.get('WARGROWLMON_AFTER',str(root/'326-repaired.MMD')))]
        if not all(p.is_file() for p in paths):
            raise unittest.SkipTest('requires private source and reviewed before/after provider models')
        previous = source_model.sections_of
        try:
            source_model.sections_of = dw3_extra.sections_of
            cls.source = source_model.parse_model(paths[0].read_bytes())
        finally:
            source_model.sections_of = previous
        cls.before = mmd.MMD.parse(paths[1].read_bytes(),27)
        cls.data = paths[2].read_bytes()
        cls.after = mmd.MMD.parse(cls.data,27)

    def test_all_271_source_head_triangles_with_source_winding(self):
        expected = set()
        for p in self.source.bones[18].mesh.prims:
            v = list(p.verts)
            for c in [(0,1,2)]+([(1,3,2)] if len(v)==4 else []):
                t = [v[k] for k in c]
                expected.add(min(tuple(t[k:]+t[:k]) for k in range(3)))
        actual = {tuple(c[0] for c in triangle) for triangle,_,_ in triangles(self.after,18)}
        self.assertEqual(len(expected),271)
        self.assertEqual(actual,expected)
        self.assertEqual(sum(2 if len(p.decode()['verts']) == 4 else 1
                             for p in self.after.tmd.objects[18].prims),272)
        self.assertEqual(self.before.tmd.obj_verts(18),self.after.tmd.obj_verts(18))

    def test_every_other_part_except_torso_is_exact_after_pairing(self):
        for oi in range(26):
            if oi in (0,18):
                continue
            with self.subTest(object=oi):
                self.assertEqual(self.before.tmd.obj_verts(oi),self.after.tmd.obj_verts(oi))
                self.assertEqual(triangles(self.before,oi),triangles(self.after,oi))

    def test_acting_and_torso_extent_landmarks(self):
        self.assertEqual(self.before.anims.build(),self.after.anims.build())
        for k in range(3):
            def rendered(model):
                verts = model.tmd.obj_verts(0)
                return [verts[i][k] for p in model.tmd.objects[0].prims for i in p.decode()['verts']]
            old,new = rendered(self.before),rendered(self.after)
            self.assertEqual((min(old),max(old)),(min(new),max(new)))

    def test_original_console_storage_and_primitive_budget(self):
        report = motionstorage.require(self.data,27)
        old = motionstorage.require(self.before.build(),27)
        self.assertLessEqual(report['resident_bytes'],old['resident_bytes'])
        self.assertLessEqual(sum(len(o.prims) for o in self.after.tmd.objects),713)
        self.assertLessEqual(max(o.nvert for o in self.after.tmd.objects),172)
        self.assertTrue(all(r['sector_read_bytes'] <= 0x2000 for r in report['cold_reads']))


if __name__ == '__main__':
    unittest.main()
