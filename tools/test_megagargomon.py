"""Check the source surfaces and unchanged programs of the MegaGargomon repair."""
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mmd
import motionstorage
from tools.derive.importers.vendor.dw3.model import parse_model


class MegaGargomonSourceRepair(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path('build/models-review')
        paths = [Path(os.environ.get('MEGAGARGOMON_SOURCE', str(root/'source/M372SGRG.BIN'))),
                 Path(os.environ.get('MEGAGARGOMON_BEFORE', str(root/'before/335-MegaGargomon.MMD'))),
                 Path(os.environ.get('MEGAGARGOMON_AFTER', str(root/'mega-final.MMD')))]
        if not all(p.is_file() for p in paths):
            raise unittest.SkipTest('requires source disc model and before/after imported models')
        cls.source = parse_model(paths[0].read_bytes())
        cls.before = mmd.MMD.parse(paths[1].read_bytes(), 27)
        cls.data = paths[2].read_bytes()
        cls.after = mmd.MMD.parse(cls.data, 27)

    def test_complete_source_head_and_backpack_with_original_winding(self):
        def canonical(v):
            return min(tuple(v[i:]+v[:i]) for i in range(3))
        for obj, source_bone in [(0, 12), (16, 17)]:
            with self.subTest(object=obj):
                # These vertex pools are unchanged: source indices identify
                # every missing surface without an image similarity threshold.
                self.assertEqual(self.before.tmd.obj_verts(obj), self.after.tmd.obj_verts(obj))
                expected, actual = set(), set()
                for p in self.source.bones[source_bone-1].mesh.prims:
                    v = list(p.verts)
                    for t in [(0, 1, 2)] + ([(1, 3, 2)] if len(v)==4 else []):
                        expected.add(canonical([v[i] for i in t]))
                for p in self.after.tmd.objects[obj].prims:
                    v = p.decode()['verts']
                    for t in [(0, 1, 2)] + ([(1, 3, 2)] if len(v)==4 else []):
                        actual.add(canonical([v[i] for i in t]))
                self.assertEqual(expected, actual)

    def test_animation_programs_and_opaque_render_flags(self):
        self.assertEqual(self.before.anims.build(), self.after.anims.build())
        self.assertFalse(any(p.mode & 2 for o in self.after.tmd.objects for p in o.prims))
        self.assertEqual(len(self.before.tmd.objects), len(self.after.tmd.objects))
        self.assertLessEqual(max(o.nvert for o in self.after.tmd.objects), 172)

    def test_limb_meshes_remain_exact(self):
        for obj in range(26):
            if obj in (0, 16):
                continue
            with self.subTest(object=obj):
                self.assertEqual(self.before.tmd.obj_verts(obj), self.after.tmd.obj_verts(obj))
                self.assertEqual(self.before.tmd.obj_norms(obj)[:self.before.tmd.objects[obj].nnorm],
                                 self.after.tmd.obj_norms(obj)[:self.after.tmd.objects[obj].nnorm])
                self.assertEqual([p.decode() for p in self.before.tmd.objects[obj].prims],
                                 [p.decode() for p in self.after.tmd.objects[obj].prims])

    def test_original_2mb_resident_and_sector_read_limits(self):
        report = motionstorage.require(self.data, 27)
        self.assertLessEqual(report['resident_bytes'], 0x18800)
        self.assertTrue(all(r['sector_read_bytes'] <= 0x2000 for r in report['cold_reads']))
        self.assertLessEqual(report['resident_bytes'], 0x18800)


if __name__ == '__main__':
    unittest.main()
