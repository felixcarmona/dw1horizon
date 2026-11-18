"""Corner fidelity and bounded fits for the four reviewed imports."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.test_meshcheck import model, box_object
from tools.models import mesh_gd as G
import mmd


class ReviewedFits(unittest.TestCase):
    def apply_rows(self, m, sid, fits=None, diagonals=None):
        rows = dict(fits={str(sid): fits or []}, diagonals={str(sid): diagonals or []})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'fits.json'
            path.write_text(json.dumps(rows))
            with patch.object(G, 'FITS', path):
                return G.apply(m, sid)

    def test_sheet_rotation_preserves_boundary_material_and_corner_attributes(self):
        m, _ = model(box_object())
        d = dict(mode=60, flag=0, olen=mmd.OLEN[60], uv=[(0,0),(8,0),(0,8),(8,8)],
                 norms=[0,1,2,3], colors=[], verts=[0,1,2,3], cba=1, tsb=5, pad=[], uvpad=[0,0])
        m.tmd.objects[0].prims = [mmd.Prim.encode(d)]
        before = copy.deepcopy(m)
        self.apply_rows(m, 307, diagonals=[[0,0,[0,1,2,3]]])
        after = m.tmd.objects[0].prims[0].decode()
        for attr in ('verts','uv','norms'):
            self.assertEqual(after[attr], [d[attr][k] for k in (1,3,0,2)])
        for attr in ('mode','flag','olen','cba','tsb'):
            self.assertEqual(after[attr], d[attr])
        # GPU boundary is 0,1,3,2; it rotates without reversing winding.
        old_boundary = [d['verts'][i] for i in (0,1,3,2)]
        new_boundary = [after['verts'][i] for i in (0,1,3,2)]
        self.assertEqual(new_boundary, old_boundary[1:]+old_boundary[:1])
        self.assertEqual(before.anims.build(), m.anims.build())
        self.assertEqual(before.tmd.verts, m.tmd.verts)

    def test_fit_moves_shared_vertex_only_and_rejects_unreviewed_or_large_edits(self):
        m, _ = model(box_object())
        old = list(m.tmd.verts[0][:3]); new = [old[0]+2, old[1]-1, old[2]]
        untouched = copy.deepcopy(m)
        self.apply_rows(m, 314, fits=[[0,0,old,new]])
        self.assertEqual(m.tmd.verts[0][:3], tuple(new))
        self.assertEqual(m.tmd.verts[1:], untouched.tmd.verts[1:])
        self.assertEqual([p.raw for p in m.tmd.objects[0].prims],
                         [p.raw for p in untouched.tmd.objects[0].prims])
        with self.assertRaisesRegex(ValueError, 'reviewed panel vertex'):
            self.apply_rows(m, 314, fits=[[0,0,old,new]])
        with self.assertRaisesRegex(ValueError, 'four-unit fit'):
            self.apply_rows(untouched, 314, fits=[[0,0,old,[old[0]+5,*old[1:]]]])

    def test_authored_scope_and_displacement_bound(self):
        rows = json.loads(G.FITS.read_text())
        self.assertEqual(set(rows['fits']), {'314','326'})
        self.assertEqual(set(rows['diagonals']), {'307','323'})
        for edits in rows['fits'].values():
            self.assertEqual(len(edits), len({(e[0],e[1]) for e in edits}))
            for _, _, a, b in edits:
                self.assertGreater(sum((x-y)**2 for x,y in zip(a,b)), 0)
                self.assertLessEqual(sum((x-y)**2 for x,y in zip(a,b)), 16)


if __name__ == '__main__':
    unittest.main()
