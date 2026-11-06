"""Source coverage, retained geometry and 2 MB storage checks for Beelzemon.

Set BEELZEMON_BEFORE, BEELZEMON_AFTER, BEELZEMON_SOURCE and BEELZEMON_IMPORT.
MMD textures use the same stems. Source/import select the untouched DW3 file
and its pinned raw converter output; AFTER may be reconstructed from DIGI.DAT.
"""
from collections import Counter
import os
from pathlib import Path
import sys
import unittest

sys.path[:0] = [str(Path(__file__).resolve().parent.parent), str(Path(__file__).resolve().parent)]
import mmd
import mmdport
import motionstorage
from tools.models.repair_beelzemon import RESTORED, BODY_PANELS, source_mesh


def triangles(model, obj_index):
    obj = model.tmd.objects[obj_index]
    verts, norms = model.tmd.obj_verts(obj_index), model.tmd.obj_norms(obj_index)
    out = Counter()
    for prim in obj.prims:
        face = prim.decode()
        material = (face['mode'] & ~8, face['flag'], face['cba'], face['tsb'])
        for tri in [(0, 1, 2)] + ([(1, 3, 2)] if len(face['verts']) == 4 else []):
            corners = tuple((tuple(verts[face['verts'][k]][:3]), tuple(norms[face['norms'][k]][:3]),
                             tuple(face['uv'][k])) for k in tri)
            out[material, min(corners[i:] + corners[:i] for i in range(3))] += 1
    return out


class FaceRepair(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        paths = [os.environ.get('BEELZEMON_' + name) for name in ('BEFORE', 'AFTER', 'SOURCE', 'IMPORT')]
        if not all(paths):
            raise unittest.SkipTest('set BEELZEMON_BEFORE, AFTER, SOURCE and IMPORT')
        before, after, source, imported = map(Path, paths)
        cls.after_data = after.read_bytes()
        cls.before = mmd.MMD.parse(before.read_bytes(), 31)
        cls.after = mmd.MMD.parse(cls.after_data, 31)
        cls.tb = mmd.Tim4(before.with_suffix('.TIM').read_bytes())
        cls.ta = mmd.Tim4(after.with_suffix('.TIM').read_bytes())
        bones, texture = source_mesh(source.read_bytes(), imported.read_bytes(), cls.tb.to_bytes())
        cls.source = mmd.MMD.parse(before.read_bytes(), 31)
        cls.source.tmd = mmdport.build_tmd(mmdport.Model('source', bones, texture.idx, texture.pal, {}))

    def test_acting_and_protected_geometry_are_exact(self):
        self.assertEqual(self.before.anims.build(), self.after.anims.build())
        for i in range(len(self.before.tmd.objects)):
            if i not in RESTORED | BODY_PANELS:
                self.assertEqual(triangles(self.before, i), triangles(self.after, i), f'object {i}')

    def test_body_panel_extents_stay_exact(self):
        for i in BODY_PANELS:
            a = self.before.tmd.obj_verts(i)
            b = self.after.tmd.obj_verts(i)
            for axis in range(3):
                self.assertEqual(min(v[axis] for v in a), min(v[axis] for v in b), (i, axis))
                self.assertEqual(max(v[axis] for v in a), max(v[axis] for v in b), (i, axis))

    def test_every_restored_source_triangle_is_present(self):
        for i in RESTORED:
            self.assertEqual(triangles(self.source, i), triangles(self.after, i), f'source object {i}')
        self.assertEqual(sum(triangles(self.after, 26).values()), 130)

    def test_storage_and_jaw(self):
        self.assertLessEqual(sum(len(o.prims) for o in self.after.tmd.objects), 713)
        self.assertLessEqual(max(o.nvert for o in self.after.tmd.objects), 172)
        self.assertEqual(len(self.after.tmd.objects), 29)
        self.assertTrue(motionstorage.audit(self.after_data, 31)['fits'])
        jaw = [p.decode() for p in self.after.tmd.objects[26].prims if (p.decode()['cba'] >> 6) - 488 == 2]
        self.assertEqual(len(jaw), 8)
        self.assertTrue(all(0 <= u < 30 and 0 <= v < 24 for p in jaw for u, v in p['uv']))
        self.assertEqual(len(self.ta.to_bytes()), len(self.tb.to_bytes()))

    def test_green_irises_and_texture_isolation(self):
        eyes = [p.decode() for p in self.after.tmd.objects[26].prims if (p.decode()['cba'] >> 6) - 488 == 11]
        self.assertEqual(len(eyes), 7)
        self.assertEqual(self.tb.pal[:11], self.ta.pal[:11])
        for index in (0, 1):
            r, g, b, _ = mmd.c15_to_rgba(self.ta.pal[11][index])
            self.assertGreater(g, 2 * max(r, b))
            source = self.tb.pal[5][index]
            expected = (source & 0xFC00) | ((source & 31) << 5) | ((source >> 5) & 31)
            self.assertEqual(self.ta.pal[11][index], expected)
        self.assertEqual(self.ta.pal[11][2:], self.tb.pal[5][2:])
        for i, (old, new) in enumerate(zip(self.tb.idx, self.ta.idx)):
            u, v = i % 256, i // 256
            if v >= 24 or not (0 <= u < 78 or 86 <= u < 102):
                self.assertEqual(old, new, f'non-face texel {u},{v}')
        self.assertTrue(all((30 <= u < 78 or 86 <= u < 102) and 0 <= v < 24 for p in eyes for u, v in p['uv']))


if __name__ == '__main__':
    unittest.main()
