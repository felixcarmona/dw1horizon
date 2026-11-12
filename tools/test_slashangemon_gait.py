"""Check SlashAngemon's walk (slot 2) on the real import (`tools/models/edit.py get 300`; skipped when it is absent)."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
import motionstorage
from tools.models.field_animations import slashangemon_gait as gait

LIMIT = 100352
# the import's other programs (every slot but the walk), its mesh and its slot table, before this change
OTHER_PROGRAMS = '955e66e2c4673b1ce8f865db66e04846c6f95526b38eceff40b549a728bba85b'
MESH = 'a6f0ce05bb54'
TABLE = '754b91322429'
BASE_PENETRATION = 2332         # the import's walk, summed over its ticks (limbs against the parts they must not cut)


class SlashAngemonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('build/imported-model-edit/edit/300-SlashAngemon.MMD')
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 300')
        cls.rig = json.loads(Path('content/species/300-slashangemon.json').read_text())['model']['skeleton']
        cls.data = path.read_bytes()
        cls.model = gait.parse(cls.data, cls.rig)
        cls.m = {s: gait.measure(cls.model, cls.rig, s) for s in (2, 3, 4)}

    def test_only_the_walk_changed(self):
        table = self.model.anims.table
        rest = b''.join(self.model.anims.anims[table[s]].build() for s in range(len(table)) if s != 2 and table[s] is not None)
        self.assertEqual(hashlib.sha256(rest).hexdigest(), OTHER_PROGRAMS)
        self.assertEqual(hashlib.sha256(self.model.tmd.build()).hexdigest()[:12], MESH)
        self.assertEqual(hashlib.sha256(repr(table).encode()).hexdigest()[:12], TABLE)

    def test_loop_closes_and_cycle_is_sixteen_ticks(self):
        frames = animsheet.slot_frames(self.model, gait.NB, 2)[0]
        self.assertEqual(len(frames), 17)
        a, b = np.array(frames[0], float), np.array(frames[-1], float)
        a[0][8] = b[0][8] = 0
        self.assertLess(np.abs(a - b).max(), 3)

    def test_speed_order_and_constant_root_speed(self):
        v = {s: self.m[s]['speed'] for s in (2, 3, 4)}
        self.assertLess(v[3], v[2])
        self.assertLess(v[2], v[4])
        self.assertTrue(15 <= v[2] <= 31, v)
        z = [f[0][8] for f in animsheet.slot_frames(self.model, gait.NB, 2)[0]]
        self.assertLess(np.ptp(np.diff(z)), 1.01)

    def test_planted_soles_do_not_slip(self):
        for foot, v in self.m[2]['feet'].items():
            self.assertGreaterEqual(v['stance'], 5, foot)
            self.assertLess(v['slip_sole'][0], 25, foot)
            self.assertLess(v['slip_sole'][1], 45, foot)

    def test_feet_alternate_by_half_a_cycle(self):
        frames = animsheet.slot_frames(self.model, gait.NB, 2)[0][:-1]
        n = len(frames)
        zs = {}
        for bone in (23, 30):
            z = []
            for f in frames:
                g = [list(b) for b in f]
                g[0] = [4096] * 3 + [0] * 6
                z.append(mmd.bone_matrices(self.model, g)[bone][2][3])
            zs[bone] = z
        # in the body's frame the left foot is the right one half a cycle later
        left = [zs[30][(t + n // 2) % n] for t in range(n)]
        self.assertLess(max(abs(a - b) for a, b in zip(left, zs[23])), 6)

    def test_floor_and_jumps(self):
        self.assertLess(self.m[2]['foot_floor'], 4)
        ratio, _ = gait.jumps(self.model, self.rig, 2)
        self.assertLess(ratio, 2.5)

    def test_penetration_not_worse_than_the_import(self):
        worst, total = gait.penetration_report(self.model, self.rig, 2)
        self.assertLessEqual(total, BASE_PENETRATION * 1.01, worst)
        for key, limit in dict(armL=10, armR=10, legL=37, legR=39, wingL=26, wingR=22, skirt=36).items():
            self.assertLessEqual(worst[key], limit, key)

    def test_upper_body_has_grace_and_is_smooth(self):
        up = gait.upper_motion(self.model, self.rig, 2)
        self.assertGreaterEqual(up['chest_turn'], 10, 'the chest turns on a clear S-curve')
        self.assertLess(up['against'], -0.5, 'the chest turns against the hips')
        for arm in ('armL', 'armR'):
            self.assertGreaterEqual(up['travel'][arm][2], 12, arm + ' swings')
        for wing in ('wingL', 'wingR'):
            self.assertGreaterEqual(max(up['travel'][wing]), 15, wing + ' breathes')
        self.assertGreaterEqual(up['travel']['head'][0], 8, 'the head follows')
        self.assertLessEqual(up['travel']['head'][2], 8, 'the head stays level')
        for key, rough in up['rough'].items():
            self.assertLess(rough, 0.6, key + ' has no flutter')

    def test_buffer(self):
        self.assertLess(motionstorage.audit(self.data, gait.NB)['resident_bytes'], LIMIT)


if __name__ == '__main__':
    unittest.main()
