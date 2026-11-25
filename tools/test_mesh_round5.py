"""Eased joint edits, fan provenance, and optional complete model fixtures."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'tools')]
import mmd
from tools.models import mesh_fan as F, mesh_pose as P
from tools.test_meshcheck import model, box_object


class EasedEdits(unittest.TestCase):
    def test_elbow_keeps_the_ordinary_arc_and_never_exceeds_90_degrees(self):
        for x in range(-2048, 2049):
            y = P.elbow_pitch(x)
            self.assertLessEqual(abs(y), 1024)
            if abs(x)*360/4096 <= 70:
                self.assertEqual(y, x)
            self.assertEqual(y, P.elbow_pitch(x+4096))

    def test_full_turn_and_limit_transitions_have_no_clamp_snap(self):
        samples = [P.elbow_pitch(x) for x in range(-4096, 4097)]
        self.assertLessEqual(max(abs(b-a) for a, b in zip(samples, samples[1:])), 2)
        self.assertEqual(P.elbow_pitch(-2048), P.elbow_pitch(2048))
        self.assertEqual(P.smoothstep(-1), 0)
        self.assertEqual(P.smoothstep(2), 1)
        self.assertAlmostEqual(P.smoothstep(.5), .5)

    def test_edit_keeps_root_other_bones_events_loops_and_aliases(self):
        m, bones = model(box_object())
        frames = [[[4096]*3+[0]*6 for _ in bones] for _ in range(16)]
        for t, p in enumerate(frames):
            p[0][6] = t*3
            p[1][3] = -600-t*25
            p[1][7] = t
        m.anims.anims = [mmd.encode_anim(frames, len(bones), 0, []),
                         mmd.encode_anim(frames, len(bones), 0, [])]
        m.anims.table = [0, 0, 1]
        before, info = mmd.simulate(m.anims.anims[0], len(bones), slot=0)
        other = m.anims.anims[1].build()
        table = list(m.anims.table)
        changed = P.edit(m, bones, lambda slot, t, poses: {(1, 0): P.elbow_pitch(poses[t][1][3])}, {0, 1})
        after, result = mmd.simulate(m.anims.anims[0], len(bones), slot=0)
        expected = copy.deepcopy(before)
        for pose in expected:
            pose[1][3] = P.elbow_pitch(pose[1][3])
        self.assertEqual(changed, [0])
        self.assertEqual(after, expected)
        self.assertEqual(result, info)
        self.assertEqual(m.anims.table, table)
        self.assertEqual(m.anims.anims[1].build(), other)


class FanProvenance(unittest.TestCase):
    def test_tail_groups_cover_every_packet_once(self):
        groups = F.packet_groups()
        packets = [p for g in groups for p in g]
        self.assertEqual(len(groups), 9)
        self.assertEqual(sorted(packets), list(range(224)))
        self.assertEqual(len(set(packets)), len(packets))

    def test_rotation_keeps_lengths(self):
        a, b = F.unit([1, 2, 3]), F.unit([-2, 1, 4])
        self.assertTrue(np.allclose(F.align(a, b, a), b))
        v = [3, 2, 5]
        self.assertAlmostEqual(F.dot(F.align(a, b, v), F.align(a, b, v)), F.dot(v, v))


@unittest.skipUnless((ROOT/'build/before/index.json').exists(), 'private model fixtures unavailable')
class CompleteFixtures(unittest.TestCase):
    def test_preservation_heap_packets_and_surface_checks(self):
        report = json.loads((ROOT/'build/preservation.json').read_text())
        self.assertEqual(set(report['changed_pins']), {409, 406, 335, 461, 336})
        self.assertEqual(sum(r['ticks'] for r in report['models'].values()), 8984)
        for sid, row in report['models'].items():
            for stage in ('before', 'after'):
                raw = (ROOT/f'build/{stage}/{sid}.MMD').read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), row['hashes'][stage])
            self.assertTrue(row['storage']['after']['fits'])
            self.assertLessEqual(row['storage']['after']['resident_bytes'], 100256)
            self.assertEqual(*row['packet_bytes_before_after'])
            self.assertEqual(*row['zero_triangles_before_after'])

    def test_rebound_fan_does_not_hide_cross_tail_geometry(self):
        from tools.models.mesh_round4 import load, sparse_crossing
        m = load(ROOT/'build/after', 409)
        groups = F.packet_groups()
        tris = [np.array([t[3] for t in m.tris if t[0] == 15 and t[2] in group]) for group in groups]
        depths = [sparse_crossing(m.local[15][tris[a]], m.local[15][tris[b]])[1]
                  for a in range(9) for b in range(a+1, 9)]
        self.assertLess(max(depths), 5.2)
        self.assertGreater(max(depths), 0)  # retain the shallow root contacts in the report
        # Also audit each original base/end join, which now shares a complete
        # tail group and therefore would be omitted by a cross-tail-only probe.
        for tail, (proximal, _, _) in enumerate(F.JOINS):
            left, right = [np.array([t[3] for t in m.tris if t[0] == 15 and t[2] in pis])
                           for pis in (proximal, range(84+20*tail, 104+20*tail))]
            self.assertLess(sparse_crossing(m.local[15][left], m.local[15][right])[1], 8.4)


if __name__ == '__main__':
    unittest.main()
