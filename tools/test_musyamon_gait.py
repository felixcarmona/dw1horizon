"""Check Musyamon's posture (chest and head stood up in the walk, tired walk and run) and its hair kept off the cape and back (idle and those three),
on the real import (`tools/models/edit.py get 325`; skipped when it is absent)."""
import hashlib
import math
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
import motionstorage
from tools.models.field_animations import meshclash
from tools.models.field_animations import musyamon_hair as hair
from tools.models.field_animations import musyamon_posture as posture

LIMIT = 100352
OTHER_PROGRAMS = 'a5a79ab9ecb1caf71dd794253cb90341c044d64f28d24f68779185f4622e1bb1'      # every program but slots 0, 2, 3, 4 and their aliases, before this change
MESH = 'ffafa3cf7003'
TABLE = '9acb58fc842f'
# every channel of the walk, tired walk and run but the chest, pelvis, head, cape (bones 1, 2, 17, 23, 25-27) and the hair (24): the import's legs, arms and root, kept
LEGS_AND_ARMS = '9d128d223002'
STEPS = {2: [18, 19, 20, 25, 37, 34, 20, 21, 22, 18, 19, 20, 25, 35, 34, 20, 21, 22], 3: [29, 30, 15, 15, 15, 20, 21, 21, 21, 21, 28, 28, 28, 28, 15, 15, 15, 21, 21, 21, 21, 22, 26, 27], 4: [38, 39, 39, 88, 58, 58, 40, 40, 41, 40, 41, 40, 41, 87, 58, 58, 41, 42, 41, 42]}


def pairs(a, b):
    hit = np.zeros((len(a), len(b)), bool)
    for k in range(3):
        k2 = (k + 1) % 3
        hit |= meshclash._crossings(a[:, k], a[:, k2], b)
        hit |= meshclash._crossings(b[:, k], b[:, k2], a).T
    return int(hit.sum())


class MusyamonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('build/imported-model-edit/edit/325-Musyamon.MMD')
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 325')
        cls.data = path.read_bytes()
        cls.model = posture.parse(cls.data)

    def frames(self, s):
        return animsheet.slot_frames(self.model, posture.NB, s)[0]

    def test_only_the_four_programs_changed(self):
        table = self.model.anims.table
        moved = {table[s] for s in hair.SLOTS}
        rest = b''.join(self.model.anims.anims[table[s]].build() for s in range(len(table))
                        if table[s] not in moved and table[s] is not None)
        self.assertEqual(hashlib.sha256(rest).hexdigest(), OTHER_PROGRAMS)
        self.assertEqual(hashlib.sha256(self.model.tmd.build()).hexdigest()[:12], MESH)
        self.assertEqual(hashlib.sha256(repr(table).encode()).hexdigest()[:12], TABLE)

    def test_legs_arms_and_root_motion_are_the_imports(self):
        skip = {1, 2, 17, 23, 24, 25, 26, 27}
        rows = [[f[b][c] for b in range(posture.NB) if b not in skip for c in range(9)] for s in (2, 3, 4) for f in self.frames(s)]
        self.assertEqual(hashlib.sha256(repr(rows).encode()).hexdigest()[:12], LEGS_AND_ARMS)
        v = {}
        for s in (2, 3, 4):
            z = [f[0][8] for f in self.frames(s)]
            self.assertEqual([-d for d in np.diff(z)], STEPS[s], s)
            v[s] = abs(z[-1] - z[0]) / 16 if len(z) == 17 else abs(z[-1] - z[0]) / (len(z) - 1)
        self.assertLess(v[3], v[2])
        self.assertLess(v[2], v[4])
        self.assertTrue(15 <= v[2] <= 31 and 10 <= v[3] <= 22 and 35 <= v[4] <= 52, v)

    def test_the_body_is_upright(self):
        """The import leans the chest 22-40 degrees and the head 14-37 forward in the walks (spine 39-59); now at most 25 and 17 (spine 43)."""
        for s, (chest, head, spine) in {2: (25, 10, 44), 3: (24, 18, 42), 4: (26, 17, 44)}.items():
            for f in self.frames(s):
                w = posture.worlds(self.model, f)
                up = lambda b: math.degrees(math.atan2(-(w[b][:3, :3] @ [0, -1, 0])[2], -(w[b][:3, :3] @ [0, -1, 0])[1]))
                d = w[23][:3, 3] - w[2][:3, 3]
                self.assertLessEqual(up(1), chest, s)
                self.assertLessEqual(up(23), head, s)
                self.assertLessEqual(math.degrees(math.atan2(-d[2], -d[1])), spine, s)
                self.assertGreaterEqual(up(23), -3, s)               # and the head still looks ahead, not up

    def test_soles_at_the_floor(self):
        clash = meshclash.Clash(self.model, mmd.exe().skeleton[posture.SPECIES])
        for s in (2, 3, 4):
            low = [max(float(clash.tris(clash.world(f), [b]).reshape(-1, 3)[:, 1].max()) for b in range(5, 13)) for f in self.frames(s)]
            self.assertLess(max(low), 2.5, s)   # the import: 0.5-2.0
            self.assertGreater(max(low), -3, s)

    def test_the_hair_stays_off_the_cape_and_back(self):
        """Per tick, the mane's triangle pairs crossing the chest's back and shoulders (the import: 42-134), the arms and the legs (0), and the cape (66-152; what is
        left is the right spike beside the head, 27, which the mane rests against)."""
        clash = meshclash.Clash(self.model, mmd.exe().skeleton[posture.SPECIES])
        bound = {0: (0, 44), 2: (8, 76), 3: (0, 64), 4: (0, 64)}
        for s, (back, cape) in bound.items():
            for t, f in enumerate(self.frames(s)[:-1]):
                w = clash.world(f)
                h = clash.tris(w, [hair.HAIR])
                self.assertLessEqual(pairs(h, clash.tris(w, list(hair.BACK))), back, (s, t))
                self.assertEqual(pairs(h, clash.tris(w, list(hair.ARMS))), 0, (s, t))
                self.assertEqual(pairs(h, clash.tris(w, list(range(2, 13)))), 0, (s, t))
                self.assertLessEqual(pairs(h, clash.tris(w, list(hair.CAPE))), cape, (s, t))

    def test_the_hair_is_loose_and_the_loop_closes(self):
        for s in hair.SLOTS:
            fr = self.frames(s)
            for b in (23, 24, 25, 26, 27, 1, 2):
                a, z = np.array(fr[0][b], float), np.array(fr[-1][b], float)
                if b == 2 or b == 1:
                    a[6:9] = z[6:9] = 0
                self.assertLess(np.abs(a - z).max(), 3, (s, b))
            x = np.array([f[24] for f in fr], float)
            self.assertGreater(np.ptp(x[:, 3:6], axis=0).max() + np.ptp(x[:, 6:9], axis=0).max(), 8, s)   # still moves
            self.assertLess(np.abs(np.diff(x, axis=0)).max(), 60, s)        # no jump between ticks

    def test_buffer(self):
        self.assertLess(motionstorage.audit(self.data, posture.NB)['resident_bytes'], LIMIT)


if __name__ == '__main__':
    unittest.main()
