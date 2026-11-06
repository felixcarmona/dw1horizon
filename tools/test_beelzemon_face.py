"""Geometry and acting regression checks for the Beelzemon face repair.

BEELZEMON_BEFORE and BEELZEMON_AFTER select MMD files reconstructed with
models/edit.py; textures use the same stems.
"""
from collections import Counter
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mmd


def triangles(model, obj_index):
    obj = model.tmd.objects[obj_index]
    verts = model.tmd.obj_verts(obj_index)
    out = Counter()
    for prim in obj.prims:
        face = prim.decode()
        if obj_index == 26 and (face['cba'] >> 6) - 488 == 2:
            continue  # replaced jaw
        for tri in [(0, 1, 2)] + ([(1, 3, 2)] if len(face['verts']) == 4 else []):
            # Compare actual geometry and winding, independent of vertex indices.
            points = tuple(verts[face['verts'][k]][:3] for k in tri)
            out[min(points[i:] + points[:i] for i in range(3))] += 1
    return out


class FaceRepair(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        before = os.environ.get('BEELZEMON_BEFORE')
        after = os.environ.get('BEELZEMON_AFTER')
        if not before or not after:
            raise unittest.SkipTest('set BEELZEMON_BEFORE and BEELZEMON_AFTER to reconstructed models')
        cls.before = mmd.MMD.parse(Path(before).read_bytes(), 31)
        cls.after = mmd.MMD.parse(Path(after).read_bytes(), 31)
        cls.tb = mmd.Tim4(Path(before).with_suffix('.TIM').read_bytes())
        cls.ta = mmd.Tim4(Path(after).with_suffix('.TIM').read_bytes())

    def test_acting_and_nonface_geometry(self):
        self.assertEqual(self.before.anims.build(), self.after.anims.build())
        for i in range(len(self.before.tmd.objects)):
            self.assertEqual(triangles(self.before, i), triangles(self.after, i), f'object {i}')

    def test_restored_jaw_and_polygon_budget(self):
        self.assertEqual(sum(len(o.prims) for o in self.after.tmd.objects), 713)
        jaw = [p.decode() for p in self.after.tmd.objects[26].prims if (p.decode()['cba'] >> 6) - 488 == 2]
        self.assertEqual(len(jaw), 8)
        self.assertTrue(all(0 <= u < 30 and 0 <= v < 24 for p in jaw for u, v in p['uv']))
        self.assertEqual(len(self.ta.to_bytes()), len(self.tb.to_bytes()))

    def test_eyes_have_isolated_red_palette(self):
        eyes = [p.decode() for p in self.after.tmd.objects[26].prims if (p.decode()['cba'] >> 6) - 488 == 11]
        self.assertEqual(len(eyes), 6)
        self.assertEqual(self.tb.pal[:11], self.ta.pal[:11])
        for index in [10, 11]:
            r, g, b, _ = mmd.c15_to_rgba(self.ta.pal[11][index])
            self.assertGreater(r, 2 * max(g, b))
        self.assertTrue(all(30 <= u < 78 and 0 <= v < 24 for p in eyes for u, v in p['uv']))


if __name__ == '__main__':
    unittest.main()
