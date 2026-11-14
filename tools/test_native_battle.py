#!/usr/bin/env python3
"""The rotation helpers of the native battle retarget (tools/models/field_animations/native_battle.py)."""
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]

from tools.models.field_animations import native_battle  # noqa: E402


def _rz(a):
    c, s = math.cos(a), math.sin(a)
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]


def _rx(a):
    c, s = math.cos(a), math.sin(a)
    return [[1, 0, 0], [0, c, -s], [0, s, c]]


class NativeBattle(unittest.TestCase):
    def close(self, a, b, places=6):
        for ra, rb in zip(a, b):
            for x, y in zip(ra, rb):
                self.assertAlmostEqual(x, y, places=places)

    def test_polar_drops_the_stretch(self):
        r = _rz(0.7)
        stretched = [[v * k for v, k in zip(row, (2.0, 0.5, 1.3))] for row in r]
        self.close(native_battle.polar(stretched), r)

    def test_mean_of_one_rotation_is_itself(self):
        r = _rz(1.1)
        self.close(native_battle.mean_rotation([r], [1.0]), r)

    def test_mean_lies_between(self):
        self.close(native_battle.mean_rotation([_rz(0.2), _rz(0.6)], [1.0, 1.0]), _rz(0.4))

    def test_compaction_stays_within_half_a_degree(self):
        self.assertLess(native_battle.MAX_TOL * 360 / 4096, 0.5)
        with self.assertRaises(ValueError):
            native_battle.compact(b'', 1, {'tol': native_battle.MAX_TOL + 1})

    def test_mirrored_fit_follows_the_twins_bind_poses(self):
        # a mirrored piece's local vertex v is the twin's X.v; its fitted world shape is X.(Q_twin.W_twin.X.v), so the
        # fit from its own source world W_own.v is whatever maps one onto the other, also when the source poses the
        # twins unevenly (a guard stance)
        mul, apply = native_battle._mul, native_battle._apply
        X = native_battle.FLIP
        q_twin, w_twin, w_own = _rz(0.4), mul(_rx(0.3), _rz(-0.9)), mul(_rz(1.2), _rx(-0.5))
        fit = native_battle.mirrored_fit(q_twin, w_twin, w_own)
        for v in ([1., 0, 0], [0, 1., 0], [0.3, -0.2, 0.9]):
            want = apply(X, apply(q_twin, apply(w_twin, apply(X, v))))
            for a, b in zip(apply(fit, apply(w_own, v)), want):
                self.assertAlmostEqual(a, b, places=6)
        # twins posed as mirrors of each other: the plain reflection of the twin's fit
        self.close(native_battle.mirrored_fit(q_twin, mul(mul(X, w_own), X), w_own), mul(mul(X, q_twin), X))

    def test_pieces_set_in_a_reviewed_orientation_do_not_lead(self):
        skeleton = [(-1, -1), (0, 0), (1, 1), (2, 2), (3, 3)]   # 2 the chest, 3 an upper arm, 4 armour moved off it
        self.assertEqual(sorted(native_battle.lead_tops({2, 4}, skeleton)), [2, 4])
        self.assertEqual(native_battle.lead_tops({2, 4}, skeleton, {4}), [2])
        self.assertEqual(native_battle.lead_tops({4}, skeleton, {4}), [4])
        recipe = {"pieces": {"4": {"aim": {}}, "3": {"offset": [0, 0, 0]}}, "mirror": {"9": 4, "8": 3}}
        self.assertEqual(native_battle.fixed_pieces(recipe), {4, 9})
        # a battle_originals `ride` piece rides its bone without leading it
        recipe["battle_originals"] = {"slots": [33], "ride": [5]}
        self.assertEqual(native_battle.fixed_pieces(recipe), {4, 5, 9})
        self.assertEqual(native_battle.lead_tops({2, 5}, [(-1, -1), (0, 0), (1, 1), (2, 1), (3, 1), (4, 1)],
                                                 native_battle.fixed_pieces(recipe)), [2])

    def test_posture_skips_bones_that_hold_only_limbs(self):
        # the QA's body bones exclude a donor bone carrying only source limb bones (a hand holding an arm's head)
        sys.path[:0] = [str(ROOT / 'tools' / 'models')]
        import battle_qa_native
        # body 1, chest 2, an arm 3-4 and the head 5 on the chest, a leg 6-7 on the body
        skeleton = [(-1, -1), (0, 0), (1, 1), (2, 2), (3, 3), (4, 2), (5, 1), (6, 6)]
        limbs = battle_qa_native.limb_bones(skeleton)
        self.assertEqual(set(limbs), {3, 4, 5, 6, 7})
        # a donor rig: hand 3 (fingers 4, 5) holds the arm's two pieces, its finger 4 the arm's tip; pelvis 6 holds the
        # source head 5 and, on its leg 7, the source leg
        parents = [-1, 0, 1, 2, 3, 3, 1, 6]
        carried = {1: {1, 2}, 3: {3}, 4: {4}, 6: {5}, 7: {6, 7}}
        self.assertEqual(battle_qa_native.limb_carriers(carried, parents, limbs), {3, 4, 7})

    def test_order_puts_parents_first(self):
        skeleton = [(0, -1), (1, 2), (2, 0)]        # bone 1's parent comes after it
        order = native_battle.order(skeleton)
        self.assertLess(order.index(2), order.index(1))


if __name__ == '__main__':
    unittest.main()
