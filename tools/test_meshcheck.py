#!/usr/bin/env python3
"""tools/models/meshcheck.py: see-through views, winding, detached parts and tears on synthetic boxes, and the
closed Cherrymon (121) against the open JURE.MMD it is made from (needs extracted/)."""
import math
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, ROOT)

try:
    import numpy  # noqa: F401
except ImportError:            # the player's build has no numpy; this developer check needs it
    numpy = None

import mmd  # noqa: E402

FACES = {                       # outward normal: the four corners of the face (a quad's 0 1 2 3, Z order)
    (0, 0, -1): [(-1, -1, -1), (1, -1, -1), (-1, 1, -1), (1, 1, -1)],
    (0, 0, 1): [(-1, -1, 1), (1, -1, 1), (-1, 1, 1), (1, 1, 1)],
    (-1, 0, 0): [(-1, -1, -1), (-1, -1, 1), (-1, 1, -1), (-1, 1, 1)],
    (1, 0, 0): [(1, -1, -1), (1, -1, 1), (1, 1, -1), (1, 1, 1)],
    (0, -1, 0): [(-1, -1, -1), (1, -1, -1), (-1, -1, 1), (1, -1, 1)],
    (0, 1, 0): [(-1, 1, -1), (1, 1, -1), (-1, 1, 1), (1, 1, 1)],
}


def _cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def box_object(size=100, skip=(), flip=(), offset=(0, 0, 0)):
    """A TMD object: a box of untextured lit quads, wound and lit like DW1's (seen from outside), less the faces
    in `skip`; the faces in `flip` are wound inside out (their normals still point out)."""
    ob = mmd.TMDObject()
    verts, norms = [], []
    for n, corners in FACES.items():
        if n in skip:
            continue
        P = [tuple(c * size + o for c, o in zip(p, offset)) for p in corners]
        a, b, c = P[0], P[1], P[2]
        x = _cross(tuple(q - p for p, q in zip(a, b)), tuple(q - p for p, q in zip(a, c)))
        outward_wound = sum(x[i] * n[i] for i in range(3)) < 0       # DW1: the normal is opposite to cross(b-a, c-a)
        if outward_wound == (n in flip):
            P = [P[0], P[2], P[1], P[3]]
        ids = []
        for p in P:
            if p + (0,) not in verts:
                verts.append(p + (0,))
            ids.append(verts.index(p + (0,)))
        norms.append(tuple(c * 4096 for c in n) + (0,))
        ob.prims.append(mmd.Prim.encode(dict(mode=0x28, flag=0, colors=[(200, 200, 200, 0x28)],
                                             norms=[len(norms) - 1], verts=ids)))
    return ob, verts, norms


def model(*objects):
    """An MMD with one bone per object (all children of the entity) and no animation."""
    m = mmd.MMD()
    m.tmd = mmd.TMD()
    for ob, verts, norms in objects:
        ob.vert_start, ob.nvert = len(m.tmd.verts), len(verts)
        ob.norm_start, ob.nnorm = len(m.tmd.norms), len(norms)
        m.tmd.verts += verts
        m.tmd.norms += norms
        m.tmd.objects.append(ob)
    m.anims = mmd.AnimSection()
    return m, [(-1, -1)] + [(k, 0) for k in range(len(objects))]


@unittest.skipIf(numpy is None, 'numpy is needed for the mesh check')
class Synthetic(unittest.TestCase):
    def analyse(self, *objects):
        from tools.models import meshcheck
        m, bones = model(*objects)
        return meshcheck.analyse(meshcheck.Model(m, bones), anims=False)[0]

    def test_closed_box_is_clean(self):
        r = self.analyse(box_object())
        self.assertEqual(r['flags'], [])
        self.assertTrue(all(v['holes'] == 0 for v in r['views'].values()), r['views'])
        self.assertEqual(r['open'], 0)

    def test_missing_back_is_see_through(self):
        r = self.analyse(box_object(skip=[(0, 0, 1)]))
        self.assertGreater(r['views']['back']['holes'], 0.5)
        self.assertLess(r['views']['front']['holes'], 0.01)
        self.assertEqual(r['open'], 4)
        self.assertTrue(any(f.startswith('see-through') for f in r['flags']), r['flags'])

    def test_inside_out_face(self):
        r = self.analyse(box_object(flip=[(1, 0, 0)]))
        self.assertTrue(any(f.startswith('see-through') for f in r['flags']), r['flags'])
        self.assertIn(1, r['inverted'])

    def test_detached_part(self):
        r = self.analyse(box_object(), box_object(size=10, offset=(0, -400, 0)))
        self.assertTrue(any(f.startswith('detached') for f in r['flags']), r['flags'])
        self.assertFalse(self.analyse(box_object(), box_object(size=10, offset=(0, -105, 0)))['flags'])

    def test_back_faces_are_culled_even_when_double_sided(self):
        """libgs' GsTMDfast routines ignore the TMD double-sided flag: the check must not trust it."""
        from tools.models import meshcheck
        ob, verts, norms = box_object(skip=[(0, 0, 1)])
        ob.prims = [mmd.Prim(p.raw[:2] + bytes([p.flag | 2]) + p.raw[3:]) for p in ob.prims]
        m, bones = model((ob, verts, norms))
        r = meshcheck.analyse(meshcheck.Model(m, bones), anims=False)[0]
        self.assertGreater(r['views']['back']['holes'], 0.5)


@unittest.skipIf(numpy is None, 'numpy is needed for the mesh check')
@unittest.skipUnless(os.path.exists(os.path.join(ROOT, 'extracted/CHDAT/MMD4/JURE.MMD')), 'needs extracted/')
class Cherrymon(unittest.TestCase):
    """The partner model is closed (content/models/cherrymon/back.py); the NPC's disc model is not."""

    def model(self, data):
        from tools.models import meshcheck
        import species
        bones = species.originals().rec[121]['bones']
        tim = mmd.alltim_entry(open(os.path.join(ROOT, 'extracted/CHDAT/ALLTIM.TIM'), 'rb').read(), 121)
        return meshcheck.Model(data, bones, tim)

    def check(self, data):
        from tools.models import meshcheck
        return meshcheck.analyse(self.model(data), anims=False)[0]

    def partner(self):
        from tools import recordoriginals
        row = [r for r in recordoriginals.records() if r['id'] == 121][0]
        return recordoriginals.decode(row['mmd'])

    def test_partner_is_closed(self):
        r = self.check(self.partner())
        self.assertEqual(r['flags'], [])
        worst = max(v['holes'] for v in r['views'].values())
        self.assertLess(worst, 0.01, r['views'])

    def test_partner_keeps_together_walking(self):
        """The added faces ride their own bones: idle, walk and run leave no piece behind."""
        from tools.models import meshcheck
        m = self.model(self.partner())
        height = m.height()[0]
        worst = meshcheck.tears(m, height, slots=[0, 1, 2])
        self.assertTrue(worst and worst[0][0] < meshcheck.STRETCH_MAX, worst[:3])

    def test_disc_model_is_open_at_the_back(self):
        r = self.check(open(os.path.join(ROOT, 'extracted/CHDAT/MMD4/JURE.MMD'), 'rb').read())
        self.assertGreater(r['views']['back']['holes'], 0.3)


if __name__ == '__main__':
    unittest.main()
