"""Clockmon's idle, walk, condition walk and run: four clearly different loops, seamless, constant speed in the native
ranges, feet that stay put in stance, flat feet on the floor, smooth, nothing cut into more than the rest pose, the
resident animation buffer and the celebration overlay intact. Needs the field model (field_animations/clockmon_gait.py):

    python3 tools/models/edit.py get 290 DIR     and CLOCKMON_MODEL=DIR/290-Clockmon.MMD

The file may be the stored model or the one before the clips (then the generator makes them)."""
import hashlib
import itertools
import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import animsheet
import mmd
from tools.models.field_animations import clockmon_gait as gait
from tools.models.field_animations import okuwamon_limbs as limbs

SOURCE = Path(os.environ.get('CLOCKMON_MODEL', 'build/imported-model-edit/edit/290-Clockmon.MMD'))
NB = 21
SLOTS = gait.SLOTS
CLIPS = {0: (gait.IDLE_TICKS, 0), 2: (gait.GAITS[2]['T'], 15), 3: (gait.GAITS[3]['T'], 10), 4: (gait.GAITS[4]['T'], 38)}
NATIVE = {2: (15, 31), 3: (10, 20), 4: (35, 52)}
GROUPS = {'legR': (3, 4, 5), 'legL': (6, 7, 8), 'armR': (9, 10), 'armL': (11, 12), 'hammer': (14, 15, 16, 17, 18, 19)}
TOES = (5, 8)
# vertices of a limb inside the chassis and the parts around it, in the rest pose (the model's own overlap) and in the
# clips of the model before this one (mean over the loop): a clip may not cut in deeper than the larger of the two
REST = {'legR': 0, 'legL': 0, 'armR': 23, 'armL': 18, 'hammer': 40}
BEFORE = {0: dict(legR=0, legL=0, armR=23, armL=18, hammer=36), 2: dict(legR=0, legL=0, armR=19.2, armL=20.5, hammer=41.8),
          3: dict(legR=0, legL=1.5, armR=19.2, armL=16.8, hammer=0), 4: dict(legR=12.2, legL=8.6, armR=17.2, armL=15.1, hammer=14.1)}


class ClockmonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SOURCE.exists():
            raise unittest.SkipTest('needs the Clockmon field model (tools/models/edit.py get 290)')
        data = SOURCE.read_bytes()
        cls.skeleton = [tuple(b) for b in json.loads(Path('content/species/290-clockmon.json').read_text())['model']['skeleton']]
        cls.proof = None
        cls.old = None
        if hashlib.sha256(data).hexdigest() == gait.SOURCE:
            cls.old = data
            data, cls.proof = gait.build(data)
        mmd.exe().skeleton[290] = cls.skeleton
        mmd.exe().bone_count[290] = NB
        cls.data = data
        cls.model = mmd.MMD.parse(data, NB)
        cls.model.type = 290
        cls.clips = {s: animsheet.slot_frames(cls.model, NB, s)[0] for s in SLOTS}
        cls.events = {s: animsheet.slot_frames(cls.model, NB, s)[2] for s in SLOTS}

    def local(self, slot, tick):
        return [[4096] * 3 + [0] * 6] + [list(b) for b in self.clips[slot][tick][1:]]

    def world(self, slot, tick):
        mats = mmd.bone_matrices(self.model, self.local(slot, tick))
        return [np.array(m) for m in mats]

    def vertices(self, slot, tick):
        mats = self.world(slot, tick)
        return np.concatenate([np.array(self.model.tmd.obj_verts(o), float)[:, :3] @ mats[b][:3, :3].T + mats[b][:3, 3]
                               for b, (o, _) in enumerate(self.skeleton) if o >= 0])

    def test_loops_keep_their_length_and_speed(self):
        for slot, (ticks, speed) in CLIPS.items():
            f = self.clips[slot]
            self.assertEqual(len(f) - 1, ticks, slot)
            self.assertEqual(f[0][1:], f[-1][1:], slot)
            self.assertAlmostEqual((f[0][0][8] - f[-1][0][8]) / ticks, speed, delta=0.01, msg=slot)
            if speed:
                self.assertEqual({round(f[i][0][8] - f[i + 1][0][8], 3) for i in range(ticks)}, {float(speed)})

    def test_speeds_are_native_and_ordered(self):
        for slot, (lo, hi) in NATIVE.items():
            self.assertTrue(lo <= CLIPS[slot][1] <= hi, slot)
        self.assertLess(CLIPS[3][1], CLIPS[2][1])
        self.assertLess(CLIPS[2][1], CLIPS[4][1])
        self.assertEqual(len({CLIPS[s][0] for s in SLOTS}), 4)
        self.assertLess(CLIPS[4][0], CLIPS[2][0])      # the run cycle is the quicker one

    def test_the_build_changes_only_the_four_field_slots_and_fits(self):
        if self.proof is None:
            self.skipTest('the stored model is not regenerated')
        self.assertEqual(self.proof['changed_slots'], list(SLOTS))
        self.assertTrue(self.proof['storage']['fits'])
        self.assertLessEqual(self.proof['storage']['resident_bytes'], gait.RESIDENT_LIMIT)

    def test_the_resident_buffer_fits(self):
        import motionstorage
        self.assertLess(motionstorage.audit(self.data, NB)['resident_bytes'], gait.RESIDENT_LIMIT)

    def test_the_four_clips_look_different(self):
        poses = {s: np.array([self.vertices(s, t) for t in range(CLIPS[s][0])]) for s in SLOTS}
        for a, b in itertools.combinations(SLOTS, 2):
            mean = np.sqrt(((poses[a].mean(0) - poses[b].mean(0)) ** 2).sum(-1).mean())
            self.assertGreater(mean, 5, (a, b, 'average pose'))
            n = 48
            ia = [int(i * len(poses[a]) / n) for i in range(n)]
            ib = [int(i * len(poses[b]) / n) for i in range(n)]
            phase = np.sqrt(((poses[a][ia] - poses[b][ib]) ** 2).sum(-1).mean())
            self.assertGreater(phase, 10, (a, b, 'phase by phase'))

    def test_the_tired_walk_is_lower_than_the_walk(self):
        chassis = {s: np.mean([self.world(s, t)[2][1, 3] for t in range(CLIPS[s][0])]) for s in (2, 3, 4)}
        self.assertGreater(chassis[3], chassis[2] + 2)        # y is down: a larger value is a lower body

    def toe_track(self, slot, bone):
        ticks = CLIPS[slot][0]
        ys, zs = [], []
        for t in range(ticks + 1):
            m = self.world(slot, t)[bone]
            ys.append(m[1, 3])
            zs.append(m[2, 3] + self.clips[slot][t][0][8])
        return np.array(ys), np.array(zs)

    def test_feet_stay_put_in_stance(self):
        for slot in (2, 3, 4):
            speed = CLIPS[slot][1]
            for bone in TOES:
                ys, zs = self.toe_track(slot, bone)
                lo, hi = ys.max(), ys.min()
                stance = [t for t in range(len(ys) - 1) if ys[t] > lo - 0.25 * (lo - hi)]
                slip = [abs(zs[t + 1] - zs[t]) / speed * 100 for t in stance]
                self.assertGreaterEqual(len(stance), 2, (slot, bone))
                self.assertLess(np.mean(slip), 25, (slot, bone, slip))
                self.assertLess(max(slip), 45, (slot, bone, slip))

    def test_idle_keeps_its_feet_planted(self):
        for bone in TOES:
            ys, zs = self.toe_track(0, bone)
            self.assertLess(np.ptp(zs), 4.0)      # whole-turn angle steps of 0.09 degrees show as a few units at the toe
            self.assertLess(np.ptp(ys), 4.0)

    def test_nothing_sinks_under_the_ground_and_soles_are_flat_on_it(self):
        for slot in SLOTS:
            low = [max(self.vertices(slot, t)[:, 1].max(), -1e9) for t in range(CLIPS[slot][0])]
            self.assertLessEqual(max(low), gait.FLOOR + 3, (slot, max(low)))
            self.assertGreaterEqual(max(low), gait.FLOOR - 3, slot)      # a foot is always down in the walk; the run has flight but never floats high
        # the foot block's sole in stance is flat on the floor: the pitch of its block stays small
        for slot in (2, 3):
            for t in range(CLIPS[slot][0]):
                w = self.world(slot, t)
                for foot in (4, 7):
                    down = w[foot][:3, :3] @ np.array([0.0, 1.0, 0.0])
                    pitch = np.degrees(np.arcsin(abs(down[2])))
                    self.assertLess(pitch, 20, (slot, t, foot))

    def test_clips_change_smoothly(self):
        for slot in SLOTS:
            v = [self.vertices(slot, t) for t in range(len(self.clips[slot]))]
            speeds = np.array([np.linalg.norm(b - a, axis=1).mean() for a, b in zip(v, v[1:])])
            self.assertLessEqual(speeds.max(), 2.5 * np.median(speeds) + (1.5 if slot == 0 else 0.5), (slot, speeds.max(), np.median(speeds)))
            angles = np.array([[b[3:6] for b in f[1:]] for f in self.clips[slot]])
            self.assertLess(np.abs(np.diff(angles, axis=0)).max(), 1024, slot)     # no joint spins across an angle branch (a flip is 2048 or more)

    def test_limbs_cut_in_no_deeper_than_the_rest_pose_or_the_old_clips(self):
        body = limbs.Body(self.model, self.skeleton)
        for slot in SLOTS:
            ticks = CLIPS[slot][0]
            stride = 1 if ticks < 20 else 6
            mean = {g: [] for g in GROUPS}
            for t in range(0, ticks, stride):
                mats, w = body.world(self.local(slot, t))
                for g, bones in GROUPS.items():
                    others = (2,) if g == 'hammer' else (2, 1, 13) + tuple(b for g2, c in GROUPS.items() if g2 not in (g, 'hammer') for b in c)
                    mean[g].append(body.count(mats, w, bones[1:] if g.startswith('leg') else bones, others))
            for g, values in mean.items():
                self.assertLessEqual(np.mean(values), max(REST[g], BEFORE[slot][g]) + 2, (slot, g, np.mean(values)))

    def test_the_celebration_overlay_is_untouched(self):
        if self.old is None:
            self.skipTest('needs the model before the clips to compare the overlays')
        import tempfile
        from motiondiscidentity import changed_programs
        from tools.models.field_animations import celebrations
        rows = json.loads(celebrations.MANIFEST.read_text())
        new_overlay, _ = celebrations.build(self.data, self.skeleton)
        rows['290']['source_sha256'] = hashlib.sha256(self.old).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'celebrations.json'
            path.write_text(json.dumps(rows))
            was, celebrations.MANIFEST = celebrations.MANIFEST, path
            try:
                old_overlay, _ = celebrations.build(self.old, self.skeleton)
            finally:
                celebrations.MANIFEST = was
        a, b = mmd.MMD.parse(old_overlay, NB), mmd.MMD.parse(new_overlay, NB)
        a.type = b.type = 290
        self.assertEqual(changed_programs(a, b), list(SLOTS))
        self.assertEqual(a.tmd.build(), b.tmd.build())

    def test_the_footfalls_sound_and_the_eyes_keep_their_events(self):
        for slot in (2, 3, 4):
            kinds = [e[1] for e in self.events[slot]]
            self.assertEqual(kinds.count('sound'), 2, slot)
        for slot in SLOTS:
            self.assertEqual([e for e in self.events[slot] if e[1] == 'tex'].__len__(), 2, slot)


if __name__ == '__main__':
    unittest.main()
