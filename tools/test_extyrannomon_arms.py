"""Check ExTyrannomon's arms in the walk, tired walk and run (species 266) on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 266`). Before the change it is
`extyrannomon_arms.SOURCE`: the generator is run on it (about 90 s) and its bytes are checked; afterwards it is the result
itself and the checks that need the old clips use the numbers recorded here.
"""
import hashlib
import json
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
import motionstorage
import retarget as R
from tools.models.field_animations import extyrannomon_arms as arms

EXPECTED = '6aae86c7b16b64f6b740e7586c03152fa4d23f9e2375730cc97fa8fb399ce853'
NB = 9
# Every bone but the two arms (7, 8): the decoded poses of each clip, its loop sample and its events, as they were.
# For the idle (slot 0) the arms are included: it is not touched at all.
UNCHANGED = {
    0: '104363bdafa644b2f5ef07c6479c17105c6ce63c7a87814181334333cf335718',
    2: 'd375459aae49127c307e8f3c4cdba06b95041de8e90d5f53f95c66291846adfd',
    3: '4c43f159f3a92c0bba51e605b534b00d90cfe20b24a232b7b0db4f88fb9a0b22',
    4: 'da721f197df133a42876b15c1ef0083ec7e8bbd44692fb7deac4f4add55d24c7',
}
# The most vertices of an arm inside each other part, over the clip, before the change (`extyrannomon_arms.baseline`).
WORST_BEFORE = {
    2: {'back': 0, 'belly': 9, 'tail': 0, 'horn': 0, 'legs': 0, 'arm': 0},
    3: {'back': 0, 'belly': 128, 'tail': 0, 'horn': 0, 'legs': 71, 'arm': 0},
    4: {'back': 82, 'belly': 96, 'tail': 0, 'horn': 0, 'legs': 6, 'arm': 10},
}
# What the arms swing before: whole range of the turn about the body's x axis (degrees) over the clip.
SWING_BEFORE = {2: 4, 3: 0, 4: 20}
# Claws stay at least 30 units above the lowest foot vertex (before: 41 at the tiredest; now 48 or more).
# Smallest ranges now (degrees of turn about x, relative to the idle hang), and the claw tip's path in a clip (units).
MIN_SWING = {2: 22, 3: 12, 4: 35}
MIN_TRAVEL = {2: 350, 3: 80, 4: 200}
LEGS = {7: 3, 8: 4}
DEG = 4096 / 360


def digest(frames, loop, events, skip):
    body = [[p[b] for b in range(NB) if b not in skip] for p in frames]
    events = [(k, kind, sorted(c.items())) for k, kind, c in events]
    return hashlib.sha256(json.dumps([body, loop, events], sort_keys=True, default=str).encode()).hexdigest()


class ExTyrannomonArms(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy
        except ImportError:
            raise unittest.SkipTest('needs numpy for the mesh checks')
        cls.np = numpy
        path = Path('build/imported-model-edit/edit/266-ExTyrannomon.MMD')
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 266')
        cls.rig = json.loads(Path('content/species/266-extyrannomon.json').read_text())['model']['skeleton']
        data = path.read_bytes()
        digest_ = hashlib.sha256(data).hexdigest()
        if digest_ == arms.SOURCE:
            data, _ = arms.build(data, cls.rig)
        elif digest_ != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        cls.data = data
        cls.model = arms._parse(data, cls.rig)
        cls.clips = {s: arms.original(cls.model, s) for s in (0, 2, 3, 4)}
        cls.idle = cls.clips[0][0][0]

    def test_reviewed_output_is_exact(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)

    def test_only_the_arms_of_walk_tired_walk_and_run_changed(self):
        frames, loop, events = self.clips[0]
        self.assertEqual(digest(frames, loop, events, ()), UNCHANGED[0], 'idle (arms included)')
        for slot in (2, 3, 4):
            frames, loop, events = self.clips[slot]
            self.assertEqual(digest(frames, loop, events, (7, 8)), UNCHANGED[slot], slot)
            self.assertEqual(len(frames), (61, 25, 19)[slot - 2 if slot < 4 else 2])
        table = self.model.anims.table
        self.assertEqual(table[36], table[4], 'slot 36 shares the run')
        for slot in (2, 3, 4):
            self.assertEqual(sum(1 for v in table if v == table[slot]), 2 if slot == 4 else 1)

    def swing_series(self, slot, arm):
        """Turn about x (degrees) of the arm against the idle hang, per tick: the euler x of its relative rotation."""
        np = self.np
        ref = np.array(R.rot_of(self.idle[arm]))
        out = []
        for pose in self.clips[slot][0]:
            rel = np.array(R.rot_of(pose[arm])) @ ref.T
            out.append(mmd.matrix_euler(rel.tolist(), [0, 0, 0])[0] / DEG)
        return out

    def tip_path(self, slot, arm):
        np = self.np
        sk = self.rig
        verts = np.array(self.model.tmd.obj_verts(sk[arm][0]))[:, :3].astype(float)
        tip = verts[np.linalg.norm(verts, axis=1).argmax()]
        return np.array([np.array(R.rot_of(p[arm])) @ tip for p in self.clips[slot][0]])

    def test_arms_swing_in_every_gait(self):
        np = self.np
        for slot in (2, 3, 4):
            for arm in (7, 8):
                series = self.swing_series(slot, arm)
                self.assertGreaterEqual(max(series) - min(series), MIN_SWING[slot], (slot, arm))
                path = self.tip_path(slot, arm)
                travel = float(np.linalg.norm(np.diff(path, axis=0), axis=1).sum())
                self.assertGreaterEqual(travel, MIN_TRAVEL[slot], (slot, arm))
                self.assertGreater(max(series) - min(series), 3 * SWING_BEFORE[slot] if slot == 2 else SWING_BEFORE[slot])
            # the claws move in and out and the disc rolls too: not a single line
            for arm in (7, 8):
                path = self.tip_path(slot, arm)
                self.assertGreater(float(path[:, 0].max() - path[:, 0].min()), 12, (slot, arm, 'sweep'))

    def test_each_arm_opposes_the_leg_on_its_side_and_trails_it(self):
        np = self.np
        for slot in (2, 3, 4):
            frames = self.clips[slot][0]
            n = len(frames) - 1
            for arm, leg in LEGS.items():
                lift = -self.tip_path(slot, arm)[:n, 1]                      # y is down: the claws' height
                pitch = np.array([arms.pitch(frames[t], leg) for t in range(n)])     # the foot goes back with +
                lift, pitch = lift - lift.mean(), pitch - pitch.mean()
                corr = {lag: float(np.corrcoef(np.roll(lift, -lag), pitch)[0, 1]) for lag in range(-3, 6)}
                best = max(corr, key=corr.get)
                self.assertGreater(corr[best], 0.8, (slot, arm, corr))        # arm up as the same-side foot goes back
                self.assertTrue(0 <= best <= 3, (slot, arm, best))            # the arm arrives a tick or so after the leg

    def test_loops_close_and_the_arms_never_jump(self):
        np = self.np
        for slot in (2, 3, 4):
            frames = self.clips[slot][0]
            n = len(frames) - 1
            for arm in (7, 8):
                self.assertEqual(frames[0][arm], frames[n][arm], (slot, arm))
                rs = [np.array(R.rot_of(frames[t % n][arm])) for t in range(n + 1)]
                steps = [math.degrees(math.acos(max(-1, min(1, (np.trace(rs[t].T @ rs[t + 1]) - 1) / 2)))) for t in range(n)]
                self.assertLess(max(steps), 2.5 * float(np.median(steps)), (slot, arm))
                self.assertLess(max(steps), 20, (slot, arm))

    def test_arms_stay_out_of_the_body_and_the_legs_as_before(self):
        collider = arms.Collider(self.model, self.rig)
        for slot in (2, 3, 4):
            worst = {k: 0 for k in WORST_BEFORE[slot]}
            for pose in self.clips[slot][0]:
                for arm in (7, 8):
                    for k, v in collider.counts(pose, arm, collider.scene(pose, arm)).items():
                        worst[k] = max(worst[k], v)
            for k, v in worst.items():
                self.assertLessEqual(v, WORST_BEFORE[slot][k], (slot, k))

    def test_claws_stay_off_the_floor(self):
        np = self.np
        collider = arms.Collider(self.model, self.rig)
        for slot in (2, 3, 4):
            for pose in self.clips[slot][0]:
                p = [list(v) for v in pose]
                p[0] = [4096] * 3 + [0] * 6
                world = collider.mesh.world(mmd.bone_matrices(self.model, p)).astype(float)
                floor = max(world[a:a + k, 1].max() for b, a, k in collider.mesh.slices if b in (3, 4))
                for b, a, k in collider.mesh.slices:
                    if b in (7, 8):
                        self.assertLess(world[a:a + k, 1].max(), floor - 30, (slot, b))

    def test_resident_buffer_fits(self):
        self.assertLess(motionstorage.require(self.data, NB)['resident_bytes'], 100352)


if __name__ == '__main__':
    unittest.main()
