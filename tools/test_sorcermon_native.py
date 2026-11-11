"""Sorcermon (242) moves like native Angemon, as Wizardmon does: every case of test_wizardmon_native runs on it, and
its crystal staff, held out to the side by the staff hand, stays clear of the hat, the body and the legs."""
import json
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
import test_wizardmon_native as wizard
from tools.models.field_animations import native_binding as binding
from tools.models.field_animations import sorcermon_native


class SorcermonNative(wizard.WizardmonNative):
    SPECIES = 242
    BUILDER = sorcermon_native

    def test_rig_is_angemons(self):
        super().test_rig_is_angemons()
        self.assertEqual(self.recipe['species'], 242)

    def test_staff_clear_of_hat_body_and_legs(self):
        """In every field clip and tick the staff keeps at least 8 units from the head and hat, the chest and the legs
        (the glove and the arm hold it: those are left out)."""
        import numpy as np
        points = {b: self.surface(b) for b in (2, 3, 9, 18, 19, 20, 21, 22, 23, 24)}

        def gap(a, c):
            return min(np.sqrt(((a[i:i+400, None]-c[None])**2).sum(-1)).min() for i in range(0, len(a), 400))
        for slot in (0, 2, 3, 4):
            frames, _, _ = animsheet.slot_frames(self.model, 26, slot)
            for tick, pose in enumerate(frames):
                world = np.array(mmd.bone_matrices(self.model, [list(v) for v in pose]))
                at = {b: p @ world[b, :3, :3].T + world[b, :3, 3] for b, p in points.items()}
                for name, bones in (('head', (3,)), ('chest', (2,)), ('legs', (18, 19, 20, 21, 22, 23, 24))):
                    self.assertGreater(gap(at[9], np.concatenate([at[b] for b in bones])), 8, (slot, tick, name))

    def test_endless_loops_close_on_their_first_pose(self):
        """The cape and hair followers end each endless loop on the pose it began from, so repeated passes do not
        creep: the last tick equals the first on those bones (Angemon's own bones keep their own programs) and ten passes of
        the engine's player end where they began."""
        import numpy as np
        for slot, index in enumerate(self.model.anims.table):
            if index is None:
                continue
            frames, loop, _ = animsheet.slot_frames(self.model, 26, slot)
            if loop is None:
                continue
            with self.subTest(slot=slot):
                self.assertEqual([frames[-1][b] for b in sorted(self.BUILDER.FOLLOWERS)],
                                 [frames[loop][b] for b in sorted(self.BUILDER.FOLLOWERS)])
                player = mmd.AnimPlayer(self.model.anims.anims[index], 26, slot)
                poses = []
                for _ in range((len(frames) - 1 - loop) * 10 + loop + 1):
                    player.tick()
                    poses.append(np.array([list(v) for v in player.pose], float))
                follow = sorted(self.BUILDER.FOLLOWERS)
                self.assertLessEqual(np.abs(poses[-1][follow, 3:6] - poses[loop][follow, 3:6]).max(), 2)

    def test_techniques_play_angemons_clips_of_their_kind(self):
        """A technique Wizardmon also has uses the same Angemon clip; the rest are cast clips of the kind (the ice shots
        and the buff share them, as in the source), and the finisher is Angemon's finisher."""
        wizard = json.loads(binding.MANIFEST.read_text())['241']['technique_slots']
        wizard_moves = json.loads(next(Path('content/species').glob('241-*.json')).read_text())['techniques']
        for index, move in enumerate(self.record['techniques']):
            if move in wizard_moves:
                self.assertEqual(self.recipe['technique_slots'][index], wizard[wizard_moves.index(move)], move)
        self.assertEqual(self.recipe['technique_slots'][-1], 56)
        self.assertEqual(len(self.recipe['technique_slots']), len(self.record['techniques']))

    def test_condition_bubble_matches_wizardmons_over_the_same_hat(self):
        self.assertEqual(self.recipe['species_patch']['condition_bubble'], [153, 71, -31, 3])


if __name__ == '__main__':
    unittest.main()
