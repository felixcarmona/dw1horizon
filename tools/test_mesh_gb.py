"""Scoped final-fit preservation checks; private meshes are optional fixtures."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import animsheet
import mmd
import motionstorage
from tools.models import mesh_cleanup as C, mesh_stability as S


class FinalFits(unittest.TestCase):
    def check_fit(self, sid):
        source = ROOT / f'build/review-provider/{sid}.MMD'
        index = ROOT / 'build/before/index.json'
        if not source.exists() or not index.exists():
            self.skipTest('reviewed private provider mesh unavailable')
        # Native binding can replace the authored skeleton before the final
        # pass. Decode its reviewed provider binding, never the source rig.
        bones = json.loads(index.read_text())[str(sid)]['bones']
        before = mmd.MMD.parse(source.read_bytes(), len(bones))
        data, report = C.apply(source.read_bytes(), bones, sid)
        after = mmd.MMD.parse(data, len(bones))
        self.assertTrue(report['applied'])
        self.assertEqual(before.anims.table, after.anims.table)
        for slot, index in enumerate(before.anims.table):
            if index is not None and index >= 0:
                self.assertEqual(animsheet.slot_frames(before, len(bones), slot),
                                 animsheet.slot_frames(after, len(bones), slot))
        self.assertEqual(S.packet_bytes(before), S.packet_bytes(after))
        self.assertTrue(motionstorage.audit(data, len(bones))['fits'])
        self.assertLessEqual(motionstorage.audit(data, len(bones))['resident_bytes'], 100256)
        for oi, (a, b) in enumerate(zip(before.tmd.objects, after.tmd.objects)):
            av, bv = before.tmd.obj_verts(oi), after.tmd.obj_verts(oi)
            self.assertEqual(len(a.prims), len(b.prims))
            for pi, (ap, bp) in enumerate(zip(a.prims, b.prims)):
                ad, bd = ap.decode(), bp.decode()
                for key in ('mode', 'flag', 'uv', 'cba', 'tsb', 'colors'):
                    self.assertEqual(ad[key], bd[key])
                for ai, bi in zip(ad['verts'], bd['verts']):
                    x, y = av[ai], bv[bi]
                    if sid == 238 and oi in (5, 6, 7, 8):
                        self.assertEqual(y, (x[0], x[1], round(x[2]*.78+8.8), x[3]))
                        self.assertLessEqual(abs(y[2]-x[2]), 15)
                    elif sid == 220 and oi in (17, 18):
                        self.assertEqual(y, (x[0], x[1], x[2]+8, x[3]))
                    elif sid == 220 and oi == 2:
                        self.assertEqual(y[:2], x[:2])
                        self.assertIn(y[2]-x[2], (0, -4))
                    elif sid == 236 and oi in (3, 6) and pi in (2, 3):
                        self.assertEqual(y, (x[0], x[1]+2, x[2], x[3]))
                    elif sid == 270 and oi == 6 and pi in (177, 178, 179, 183, 184, 185, 187):
                        self.assertEqual(y, (x[0], x[1]+3, x[2], x[3]))
                    else:
                        self.assertEqual(y, x)

    def test_vikemon_fit_preserves_motion_material_and_packet_budget(self):
        self.check_fit(220)

    def test_dolphmon_fit_preserves_motion_material_and_packet_budget(self):
        self.check_fit(238)

    def test_demidevimon_layers_preserve_motion_material_and_packet_budget(self):
        self.check_fit(236)

    def test_princemamemon_layers_preserve_motion_material_and_packet_budget(self):
        self.check_fit(270)


if __name__ == '__main__':
    unittest.main()
