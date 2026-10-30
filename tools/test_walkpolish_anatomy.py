"""Tests of tools/walkpolish.py: feet are picked by anatomy, not by the lowest vertices of a model.

    python3 tools/test_walkpolish_anatomy.py
"""
import unittest
from unittest.mock import patch

import walkpolish


class FakeModel:
    def __init__(self, *_args):
        self.lowest = [6, 15]  # Unreviewed low points, not Monmon's confirmed toes.


class FakeMMD:
    class Animations:
        table = [None, None, object()]

    anims = Animations()


class WalkpolishAnatomyTests(unittest.TestCase):
    def test_halsemon_hocks_are_not_mistaken_for_hind_knees(self):
        skel=walkpolish.mmd.exe().skeleton[196]
        self.assertEqual(walkpolish.FEET[196],[14,17,21,25])
        self.assertIn(196,walkpolish.ANATOMY_ABSTAIN)
        for paw,hock,knee,hip in [(21,20,19,18),(25,24,23,22)]:
            self.assertEqual([skel[paw][1],skel[hock][1],skel[knee][1]],
                             [hock,knee,hip])
        self.assertEqual([skel[14][1],skel[13][1]],[13,12])

    def test_monmon_uses_native_bare_toes_not_brown_gloves(self):
        skel = walkpolish.mmd.exe().skeleton[352]
        self.assertEqual(walkpolish.FEET[352], [11, 5])
        self.assertEqual([skel[b][1] for b in (11, 5)], [10, 4])
        self.assertEqual([skel[skel[b][1]][1] for b in (11, 5)], [9, 3])
        self.assertEqual([skel[14][1], skel[19][1]], [13, 18])
        # Knowing the toe IDs does not make the intervening heel a knee.
        self.assertIn(352, walkpolish.ANATOMY_ABSTAIN)

    def test_kyukimon_abstains_until_articulated_sole_dynamics_are_reviewed(self):
        skel = walkpolish.mmd.exe().skeleton[322]
        self.assertIn(322, walkpolish.ANATOMY_ABSTAIN)
        self.assertNotIn(322, walkpolish.FEET)
        self.assertEqual(walkpolish.ANATOMY_ABSTAIN[322],
                         'textured legs3-6/12-15 confirmed; four-bone sole dynamics and controller pending')
        # Textured isolation confirms pelvis legs and chest blade arms;
        # generic endpoint IK still lacks reviewed articulated sole dynamics.
        self.assertEqual(skel[3][1], 2)
        self.assertEqual(skel[12][1], 2)
        self.assertEqual(skel[16][1], 1)
        self.assertEqual(skel[19][1], 1)
        self.assertEqual(skel[6][1], 5)
        self.assertEqual(skel[15][1], 14)

    def test_explicit_monmon_feet_override_lowest_bone_metric(self):
        observed = []

        def metrics(model):
            observed.append(list(model.lowest))
            return 1.0, [(b, 1, 2, 10.0, 10.0, 1.0) for b in model.lowest]

        with patch.object(walkpolish.A, 'Model', FakeModel), \
                patch.object(walkpolish.A, 'metrics', metrics), \
                patch.object(walkpolish.mmd.MMD, 'load', return_value=FakeMMD()):
            slip, lift = walkpolish.stance_slip('ignored.MMD', 352, 'ignored.TIM', feet=walkpolish.FEET[352])

        self.assertEqual(observed, [[11, 5]])
        self.assertEqual(slip, 10.0)
        self.assertEqual(lift, 1.0)


if __name__ == '__main__':
    unittest.main()
