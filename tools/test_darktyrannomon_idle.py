"""Check DarkTyrannomon's authored idle on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 265`), or from the file named by
DARKTYRANNOMON_MODEL. Before the change it is `darktyrannomon_idle.SOURCE`: the generator is run on it and its bytes
are checked; afterwards it is the result itself and the checks that need the old clips are skipped.
"""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

try:
    import numpy as np
except ImportError:      # the repository's own array module has no FFT or point queries
    np = None

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import animstudio
import mmd
from motiondiscidentity import changed_programs
from test_starmon_gait import inside, DIRS
from tools.models.field_animations import darktyrannomon_idle as gait

EXPECTED = 'e0e7c12ccdfa3e61a97a7da4e95415abda882fb4842f8109ae4146aff8630c63'
GROUPS = {'feetR': (6, 7, 8), 'feetL': (9, 10, 11), 'armL': (12, 13, 14, 15), 'armR': (16, 17, 18, 19), 'body': (1, 2),
          'tail': (3, 4, 5), 'head': (20, 21)}
PAIRS = (('feetR', 'body'), ('feetL', 'body'), ('feetR', 'armR'), ('feetL', 'armL'), ('tail', 'body'), ('armL', 'body'),
         ('armR', 'body'), ('head', 'body'), ('feetR', 'tail'), ('feetL', 'tail'))
# (feet = bones 6-8 and 9-11, the short limbs at the centre; arms = bones 12-15 and 16-19, the big outer limbs;
# head = bones 20 (head) and 21 (lower jaw); tail = bones 3, 4, 5: base, middle and tip)
# the mesh pieces overlap at the joints by design: the points of one piece inside another in the rest pose (and the
# import's own idle, which the new one must not exceed by more than a few)
REST_OVERLAP = {('feetR', 'body'): 22, ('feetL', 'body'): 22, ('feetR', 'armR'): 0, ('feetL', 'armL'): 6, ('tail', 'body'): 18,
                ('armL', 'body'): 14, ('armR', 'body'): 20, ('head', 'body'): 40, ('feetR', 'tail'): 14, ('feetL', 'tail'): 15}
PLANTED = (8, 11)                   # the foot bones (6-8 and 9-11 are all still)


def step_degrees(a, b):
    r = np.array(mmd.rot_matrix(*a[3:6])).T @ np.array(mmd.rot_matrix(*b[3:6]))
    return math.degrees(math.acos(max(-1., min(1., (float(r[0, 0] + r[1, 1] + r[2, 2]) - 1)/2))))


def rotation_steps(frames, bone):
    return [step_degrees(frames[i][bone], frames[i + 1][bone]) for i in range(len(frames) - 1)]


class DarkTyrannomonIdle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if np is None:
            raise unittest.SkipTest('needs numpy')
        path = Path(os.environ.get('DARKTYRANNOMON_MODEL', 'build/imported-model-edit/edit/265-DarkTyrannomon.MMD'))
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 265')
        cls.rig = json.loads(Path('content/species/265-darktyrannomon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[265] = cls.rig
        mmd.exe().bone_count[265] = len(cls.rig)
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.old = None
        if digest == gait.SOURCE:
            cls.old = mmd.MMD.parse(data, gait.NB)
            cls.old.type = 265
            data, cls.report = gait.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        cls.data = data
        cls.new = mmd.MMD.parse(data, gait.NB)
        cls.new.type = 265
        cls.body = gait.Body(cls.new, cls.rig)

    def frames(self, slot, model=None):
        return animsheet.slot_frames(model or self.new, gait.NB, slot)[0]

    def need_old(self):
        if self.old is None:
            self.skipTest('needs the model before this change')

    def test_reviewed_output_is_exact(self):
        self.assertEqual(hashlib.sha256(self.data).hexdigest(), EXPECTED)

    def test_only_the_idle_changes(self):
        self.need_old()
        self.assertEqual(changed_programs(self.old, self.new), [0])
        self.assertEqual(self.old.tmd.build(), self.new.tmd.build())
        for slot, index in enumerate(self.old.anims.table):
            if slot != 0 and index is not None:
                self.assertEqual(self.frames(slot), self.frames(slot, self.old), slot)
        self.assertEqual(self.frames(33), self.frames(0, self.old))          # the battle idle keeps the old program
        for slot in (2, 3, 4):
            self.assertEqual(self.frames(slot), self.frames(slot, self.old), slot)

    def test_storage_fits_the_resident_buffer(self):
        from motionstorage import audit
        storage = audit(self.data, gait.NB)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)

    def test_loop_is_closed_and_slow(self):
        frames = self.frames(0)
        self.assertEqual(len(frames), gait.IDLE_TICKS + 1)
        self.assertEqual(frames[-1][1:], frames[0][1:])
        self.assertEqual(frames[0][0], [4096]*3 + [0]*6)           # no root motion
        self.assertTrue(all(p[0] == frames[0][0] for p in frames))

    def test_no_jerks(self):
        # the import's idle turned a bone up to 8.3 degrees a tick, changed a step by up to 6.3 degrees and moved the
        # pelvis 30 units; every bone of the new one turns under 2.5 degrees a tick and changes its step by under 1.2
        frames = self.frames(0)
        for bone in range(1, gait.NB):
            steps = rotation_steps(frames, bone)
            self.assertLess(max(steps), 2.5, bone)
            self.assertLess(max(abs(steps[(i + 1) % len(steps)] - steps[i]) for i in range(len(steps))), 1.2, bone)
            for k in (6, 7, 8):
                values = [p[bone][k] for p in frames]
                self.assertLessEqual(max(abs(values[i + 1] - values[i]) for i in range(len(values) - 1)), 3 if bone in (6, 9) else 1, (bone, k))   # shoulders glide up to 3 units a tick
        # no high-frequency content: every joint's path in the world is one slow breath (the head, the tail tip and the
        # jaw have a few harmonics); an eighth of the loop (12 ticks) or faster would be a tremor
        worlds = [self.body.world(p) for p in frames[:-1]]
        for bone in range(2, gait.NB):
            path = np.array([w[bone, :3, 3] for w in worlds], float)
            path -= path.mean(0)
            power = (np.abs(np.fft.rfft(path, axis=0))**2).sum(1)
            if power[1:].sum() > 2000:         # the planted hands and feet only carry rounding
                self.assertLess(power[13:].sum()/power[1:].sum(), .06 if bone == 2 else .02, bone)   # the chest rises in whole units

    def test_breathes_and_moves_slowly(self):
        frames = self.frames(0)
        spans = {bone: max(step_degrees(frames[0][bone], p[bone]) for p in frames) for bone in range(1, gait.NB)}
        self.assertEqual(spans[1], 0)               # the pelvis does not turn
        self.assertGreater(spans[2], 8)             # chest
        self.assertLess(spans[2], 14)
        self.assertGreater(spans[3], 20)            # tail base
        self.assertGreater(spans[4], 24)            # tail middle
        self.assertGreater(spans[5], 25)            # tail tip
        self.assertGreater(spans[20], 8)            # head
        self.assertGreater(spans[21], 20)            # lower jaw
        for bone in (6, 7, 8, 9, 10, 11):
            self.assertLess(spans[bone], 1e-3, bone)       # the feet do not turn
        for bone in (12, 16):
            self.assertGreater(spans[bone], 11, bone)       # arm shoulders
        for bone in (13, 17):
            self.assertGreater(spans[bone], 13, bone)       # arm elbows
        for bone in (14, 15, 18, 19):
            self.assertGreater(spans[bone], 14, bone)       # hands and claws
        # and never wildly: nothing turns more than 40 degrees from its first pose
        self.assertLess(max(spans.values()), 40)

    def test_mouth_opens_twice_and_shuts(self):
        # the lower jaw (bone 21) starts and ends shut, opens wide once (over 20 degrees) and a second, smaller time (over 12)
        frames = self.frames(0)[:-1]
        angle = [step_degrees(frames[0][21], p[21]) for p in frames]
        self.assertLess(angle[0], .5)
        peaks = [i for i in range(len(angle)) if angle[i] >= angle[i - 1] and angle[i] > angle[(i + 1) % len(angle)] and angle[i] > 10]
        self.assertEqual(len(peaks), 2, peaks)
        self.assertGreater(max(angle), 20)
        self.assertGreater(sorted(angle[i] for i in peaks)[0], 12)
        self.assertLess(min(angle[peaks[0]:peaks[1]]), 1)          # shut between the two openings

    def test_jaw_only_pitches_and_the_chin_goes_straight_down(self):
        # root cause of the sideways jaw: bones 20 and 21 are the head and its lower jaw (3-5 are the tail); the jaw must
        # only change its pitch channel, and the chin must move down in the head's own frame, never sideways
        frames = self.frames(0)
        for k in (4, 5):
            self.assertEqual({p[21][k] for p in frames}, {frames[0][21][k]}, k)
        worlds = [self.body.world(p) for p in frames]
        w0 = worlds[0]
        v0 = self.body.verts[21] @ w0[21, :3, :3].T + w0[21, :3, 3]
        chin = int(np.argmin(v0[:, 2]))
        rel = np.array([((self.body.verts[21] @ w[21, :3, :3].T + w[21, :3, 3])[chin] - w[20, :3, 3]) @ w[20, :3, :3] for w in worlds])
        self.assertLess(float(np.ptp(rel[:, 0])), 3)                  # no lateral movement
        self.assertGreater(float((rel[:, 1] - rel[0, 1]).max()), 30)  # and it drops over 30 units
        self.assertLess(float((rel[:, 1] - rel[0, 1]).min()), 3)      # never above the shut mouth

    def test_tail_tip_trails_its_base(self):
        frames = self.frames(0)
        base = [step_degrees(frames[0][3], p[3]) for p in frames]
        tip = [step_degrees(frames[0][5], p[5]) for p in frames]
        self.assertGreater(max(tip), 1.2*max(base))

    def test_feet_are_still_on_the_floor(self):
        # the pelvis and the feet (bones 6-11) are bit for bit the same in every tick, so nothing there moves at all
        frames = self.frames(0)
        for bone in (1,) + gait.FEET_BONES:
            self.assertTrue(all(p[bone] == frames[0][bone] for p in frames), bone)
        worlds = [self.body.world(p) for p in frames]
        for bone in gait.FEET_BONES:
            pts = np.array([self.body.verts[bone] @ w[bone, :3, :3].T + w[bone, :3, 3] for w in worlds])
            self.assertLess(float(abs(pts - pts[0]).max()), .5, bone)
        for bone in PLANTED:
            lowest = -float((self.body.verts[bone] @ worlds[0][bone, :3, :3].T + worlds[0][bone, :3, 3])[:, 1].max())
            self.assertGreater(lowest, -2.0, bone)              # on the floor, a unit or so above it
            self.assertLess(lowest, 3.0, bone)

    def test_arms_swing_free_and_never_through_the_floor(self):
        frames = self.frames(0)
        worlds = [self.body.world(p) for p in frames]
        for bone in (13, 14, 17, 18):
            pos = np.array([w[bone, :3, 3] for w in worlds])
            self.assertGreater(float(np.linalg.norm(pos - pos.mean(0), axis=1).max()), 10, bone)
        for bone in (14, 15, 18, 19):
            for w in worlds:
                lowest = -float((self.body.verts[bone] @ w[bone, :3, :3].T + w[bone, :3, 3])[:, 1].max())
                self.assertGreater(lowest, -2.0, bone)

    def test_pelvis_does_not_move(self):
        pel = np.array([self.body.world(p)[1, :3, 3] for p in self.frames(0)])
        self.assertEqual(float(np.ptp(pel, 0).max()), 0)

    def test_parts_do_not_pass_through_each_other(self):
        mesh = animstudio.FastMesh(SimpleNamespace(m=self.new, skel=self.rig))
        worst = {}
        for pose in self.frames(0)[:-1:4]:
            p = copy.deepcopy(pose)
            p[0] = [4096]*3 + [0]*6
            W = mesh.world(mmd.bone_matrices(self.new, p)).astype(float)
            for a, b in PAIRS:
                tri = W[mesh.tri[np.isin(mesh.bone, GROUPS[a])]]
                pts = np.vstack([tri.reshape(-1, 3), tri.mean(1)])
                tris = W[mesh.tri[np.isin(mesh.bone, GROUPS[b])]]
                votes = sum(inside(np, pts, tris, d).astype(int) for d in DIRS)
                worst[(a, b)] = max(worst.get((a, b), 0), int((votes >= 3).sum()))
        for pair, count in worst.items():
            self.assertLessEqual(count, REST_OVERLAP[pair] + 6, (pair, count))


if __name__ == '__main__':
    unittest.main()
