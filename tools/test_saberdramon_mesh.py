"""Disc-backed regression for the native record's independently culled surfaces."""
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet
import coldsplit
import mmd
from tools import recordoriginals
from tools.models import meshcheck as MC, mesh_stability as S


def surfaces(model):
    """Ordered oriented GPU triangles, independent of pool/shading packing."""
    result = []
    for oi, ob in enumerate(model.tmd.objects):
        vv, nn = model.tmd.obj_verts(oi), model.tmd.obj_norms(oi)
        for prim in ob.prims:
            d = prim.decode()
            corners = []
            for k, vi in enumerate(d['verts']):
                corners.append((tuple(vv[vi]), tuple(nn[d['norms'][min(k, len(d['norms'])-1)]]),
                                tuple(d['uv'][k]),
                                tuple(d['colors'][min(k, len(d['colors'])-1)][:3]) if d['colors'] else ()))
            for ids in ((0, 1, 2), (1, 3, 2)) if len(corners) == 4 else ((0, 1, 2),):
                result.append((oi, d['mode'] & ~24, d['flag'], d['cba'], d['tsb'],
                               tuple(corners[i] for i in ids)))
    return result


class SaberdramonMesh(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (ROOT / 'extracted/CHDAT/MMD3/SABD.MMD').exists():
            raise unittest.SkipTest('needs the player disc extraction')
        cls.bones = mmd.exe().skeleton[106]
        cls.nb = len(cls.bones)
        row = next(r for r in recordoriginals.records() if r['id'] == 106)
        cls.data = recordoriginals.decode(row['mmd'])
        cls.final = mmd.MMD.parse(cls.data, cls.nb)
        cls.source = mmd.MMD.parse((ROOT / 'extracted/CHDAT/MMD3/SABD.MMD').read_bytes(), cls.nb)

    def test_all_disc_surfaces_keep_winding_uv_material_and_shading(self):
        self.assertEqual(surfaces(self.source), surfaces(self.final))
        self.assertEqual(len(surfaces(self.final)), 606)
        self.assertEqual(sum(len(o.prims) for o in self.final.tmd.objects), 444)
        self.assertFalse(S.bent_quads(self.final))
        self.assertLessEqual(S.packet_bytes(self.final)-S.packet_bytes(self.source), 1024)
        self.assertEqual(len(coldsplit.split(self.data, self.nb)[0]), 45738)

    def test_every_final_clip_tick_has_stable_surface_geometry(self):
        r = MC.flicker(MC.Model(self.data, self.bones))
        self.assertEqual(len(r['clips']), 46)
        self.assertEqual(sum(c['frames'] for c in r['clips'].values()), 1832)
        self.assertFalse(r['warped_quads'])
        self.assertFalse(r['degenerate_triangles'])
        self.assertFalse(r['tiny_triangles'])
        for slot, c in r['clips'].items():
            with self.subTest(slot=slot):
                self.assertFalse(c['quad_facing'])
                self.assertFalse(c['collapsed_triangles'])
                self.assertGreater(c['min_determinant'], 0)
        self.assertFalse(any(p.mode & 2 for o in self.final.tmd.objects for p in o.prims))

    def test_repair_preserves_all_decoded_motion_and_metadata(self):
        before = Path(os.environ.get('SABERDRAMON_BEFORE', ROOT / 'build/saber/before/106.MMD'))
        if not before.exists():
            self.skipTest('needs the pre-repair final record in SABERDRAMON_BEFORE')
        data = before.read_bytes()
        old = mmd.MMD.parse(data, self.nb)
        output, proof = S.apply(data, self.bones)
        self.assertEqual(output, self.data)
        self.assertEqual(proof['split'], 16)
        self.assertLessEqual(proof['resident_after'], proof['resident_before'])
        self.assertEqual([i is None for i in old.anims.table], [i is None for i in self.final.anims.table])
        for slot, index in enumerate(old.anims.table):
            if index is not None:
                with self.subTest(slot=slot):
                    self.assertEqual(animsheet.slot_frames(old, self.nb, slot, max_ticks=65536),
                                     animsheet.slot_frames(self.final, self.nb, slot, max_ticks=65536))


if __name__ == '__main__':
    unittest.main()
