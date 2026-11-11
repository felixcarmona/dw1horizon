"""Datamon's idle, walk, tired walk and run: four clearly different loops that hold two or three strides (so no pose repeats
every third of a second), seamless, constant speed in the native ranges, boots that stay put in stance, flat on the
floor, smooth, nothing cut into more than before, the resident animation buffer intact. Needs the field model
(field_animations/datamon_gait.py):

    python3 tools/models/edit.py get 294 DIR     and DATAMON_MODEL=DIR/294-Datamon.MMD

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
from tools.models.field_animations import datamon_gait as gait
from tools.models.field_animations import okuwamon_limbs as limbs

SOURCE = Path(os.environ.get('DATAMON_MODEL', 'build/imported-model-edit/edit/294-Datamon.MMD'))
NB = 28
SLOTS = gait.PROGRAMS
CLIPS = {0: (gait.IDLE_TICKS, 0), 2: (36, 15), 3: (28, 11), 4: (21, 36)}
NATIVE = {2: (15, 31), 3: (10, 20), 4: (35, 52)}
BOOTS = (5, 9, 13, 17)
GROUPS = {'legFR': (2, 3, 4, 5), 'legFL': (6, 7, 8, 9), 'legRR': (10, 11, 12, 13), 'legRL': (14, 15, 16, 17),
          'armR': (19, 20, 21, 22), 'armL': (24, 25, 26, 27)}
# vertices of a limb inside the torso and the parts around it, in the clips of the model before this one (mean over the
# loop): a clip may not cut in deeper than the larger of the two numbers plus two
BEFORE = {0: dict(legFR=0, legFL=0, legRR=0, legRL=0, armR=22.1, armL=22.4),
          2: dict(legFR=33.6, legFL=33.9, legRR=27.1, legRL=26.4, armR=22.2, armL=22.3),
          3: dict(legFR=25.6, legFL=24.5, legRR=21.4, legRL=21.2, armR=22.1, armL=22.3),
          4: dict(legFR=45.2, legFL=47.6, legRR=45.5, legRL=45.2, armR=22.0, armL=22.4)}


class DatamonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SOURCE.exists():
            raise unittest.SkipTest('needs the Datamon field model (tools/models/edit.py get 294)')
        data = SOURCE.read_bytes()
        cls.skeleton = [tuple(b) for b in json.loads(Path('content/species/294-datamon.json').read_text())['model']['skeleton']]
        cls.proof = None
        cls.old = None
        if hashlib.sha256(data).hexdigest() == gait.SOURCE:
            cls.old = data
            data, cls.proof = gait.build(data)
        mmd.exe().skeleton[294] = cls.skeleton
        mmd.exe().bone_count[294] = NB
        cls.data = data
        cls.model = mmd.MMD.parse(data, NB)
        cls.model.type = 294
        cls.clips = {s: animsheet.slot_frames(cls.model, NB, s)[0] for s in SLOTS}
        cls.events = {s: animsheet.slot_frames(cls.model, NB, s)[2] for s in SLOTS}

    def local(self, slot, tick):
        return [[4096] * 3 + [0] * 6] + [list(b) for b in self.clips[slot][tick][1:]]

    def world(self, slot, tick):
        return [np.array(m) for m in mmd.bone_matrices(self.model, self.local(slot, tick))]

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

    def test_the_loops_hold_whole_strides_and_are_long_enough_not_to_repeat_quickly(self):
        for slot in (2, 3, 4):
            cfg = gait.GAITS[slot]
            self.assertEqual(CLIPS[slot][0], cfg['T'] * cfg['cycles'])
            self.assertGreaterEqual(cfg['cycles'], 2)
        self.assertGreaterEqual(min(CLIPS[s][0] for s in (2, 3, 4)), 21)

    def test_the_second_stride_is_not_a_copy_of_the_first(self):
        for slot in (2, 3):
            ticks, T = CLIPS[slot][0], gait.GAITS[slot]['T']
            a = np.array([self.vertices(slot, t) for t in range(T)])
            b = np.array([self.vertices(slot, t + T) for t in range(T)])
            self.assertGreater(np.sqrt(((a - b) ** 2).sum(-1).mean()), 2.0, slot)

    def test_the_build_changes_only_the_field_slots_and_fits(self):
        if self.proof is None:
            self.skipTest('the stored model is not regenerated')
        self.assertEqual(self.proof['changed_slots'], sorted(gait.SLOTS))
        self.assertTrue(self.proof['storage']['fits'])
        self.assertLessEqual(self.proof['storage']['resident_bytes'], gait.RESIDENT_LIMIT)

    def test_the_resident_buffer_fits(self):
        import motionstorage
        self.assertLess(motionstorage.audit(self.data, NB)['resident_bytes'], gait.RESIDENT_LIMIT)

    def test_the_four_clips_look_different(self):
        poses = {s: np.array([self.vertices(s, t) for t in range(0, CLIPS[s][0], 3 if s == 0 else 1)]) for s in SLOTS}
        for a, b in itertools.combinations(SLOTS, 2):
            mean = np.sqrt(((poses[a].mean(0) - poses[b].mean(0)) ** 2).sum(-1).mean())
            self.assertGreater(mean, 4, (a, b, 'average pose'))
            n = 32
            ia = [int(i * len(poses[a]) / n) for i in range(n)]
            ib = [int(i * len(poses[b]) / n) for i in range(n)]
            phase = np.sqrt(((poses[a][ia] - poses[b][ib]) ** 2).sum(-1).mean())
            self.assertGreater(phase, 6, (a, b, 'phase by phase'))

    def test_the_tired_walk_is_a_slumped_shuffle(self):
        lift = {s: np.mean([np.ptp(self.boot_track(s, b)[0]) for b in BOOTS]) for s in (2, 3)}
        self.assertLess(lift[3], 0.8 * lift[2])                      # the boots barely leave the floor
        lean = {s: np.mean([self.clips[s][t][1][3] for t in range(CLIPS[s][0])]) for s in (2, 3)}
        self.assertGreater(abs(lean[3] - lean[2]), 20)                # and the torso leans more (1/4096 of a turn)

    def boot_track(self, slot, bone):
        ys, zs = [], []
        for t in range(CLIPS[slot][0] + 1):
            m = self.world(slot, t)[bone]
            ys.append(m[1, 3])
            zs.append(m[2, 3] + self.clips[slot][t][0][8])
        return np.array(ys), np.array(zs)

    def test_boots_stay_put_in_stance(self):
        for slot in (2, 3, 4):
            speed = CLIPS[slot][1]
            for bone in BOOTS:
                ys, zs = self.boot_track(slot, bone)
                lo, hi = ys.max(), ys.min()
                stance = [t for t in range(len(ys) - 1) if ys[t] > lo - 0.25 * (lo - hi)]   # as animstudio's metrics count it
                slip = [abs(zs[t + 1] - zs[t]) / speed * 100 for t in stance]
                self.assertGreaterEqual(len(stance), 2, (slot, bone))
                self.assertLess(np.mean(slip), 25, (slot, bone, slip))
                self.assertLess(max(slip), 45, (slot, bone, slip))

    def test_idle_keeps_its_boots_planted(self):
        for bone in BOOTS:
            ys, zs = self.boot_track(0, bone)
            self.assertLess(np.ptp(zs), 7.0)
            self.assertLess(np.ptp(ys), 7.0)

    def test_the_boots_swing_calmly(self):
        # the world speed of a boot between two ticks: a swinging boot must cover a stride in the air, so its speed is bounded
        # below by the root's; these caps keep the step slow and heavy (the clips before slid instead of stepping)
        caps = {2: 40, 3: 33, 4: 75}
        for slot, cap in caps.items():
            for bone in BOOTS:
                pts = np.array([self.world(slot, t)[bone][:3, 3] + [0, 0, self.clips[slot][t][0][8]] for t in range(CLIPS[slot][0] + 1)])
                speed = np.linalg.norm(np.diff(pts, axis=0), axis=1)
                self.assertLess(speed.max(), cap, (slot, bone))
                self.assertLess(speed.max(), 3.0 * CLIPS[slot][1], (slot, bone))

    def test_the_hands_hang_by_the_body_not_out_in_front(self):
        # the hands were held 31-44 units in front of the torso (the model's rest pose is 35 and 42); forward is -z
        for slot in SLOTS:
            for hand in (22, 27):
                ahead = [self.world(slot, t)[1][2, 3] - self.world(slot, t)[hand][2, 3] for t in range(CLIPS[slot][0])]
                self.assertLess(np.mean(ahead), 12, (slot, hand))
                self.assertLess(max(ahead), 25, (slot, hand))

    def test_every_boot_leaves_the_floor_in_the_walks(self):
        for slot in (2, 3, 4):
            for bone in BOOTS:
                ys, _ = self.boot_track(slot, bone)
                self.assertGreater(np.ptp(ys), 6, (slot, bone))

    def test_nothing_sinks_under_the_ground(self):
        for slot in SLOTS:
            ticks = CLIPS[slot][0]
            low = [self.vertices(slot, t)[:, 1].max() for t in range(0, ticks, 2 if slot == 0 else 1)]
            self.assertLessEqual(max(low), gait.FLOOR + 4, (slot, max(low)))
            if slot in (2, 3):
                self.assertGreaterEqual(max(low), gait.FLOOR - 4, slot)      # a boot is always down in the walks

    def test_clips_change_smoothly_and_without_flicker(self):
        for slot in SLOTS:
            v = [self.vertices(slot, t) for t in range(len(self.clips[slot]))]
            speeds = np.array([np.linalg.norm(b - a, axis=1).mean() for a, b in zip(v, v[1:])])
            self.assertLessEqual(speeds.max(), 2.5 * np.median(speeds) + (1.5 if slot == 0 else 0.5), (slot, speeds.max(), np.median(speeds)))
            angles = np.array([[b[3:6] for b in f[1:]] for f in self.clips[slot]])
            self.assertLess(np.abs(np.diff(angles, axis=0)).max(), 1024, slot)     # no joint spins across an angle branch
        # the idle is slow: most of its energy lies below a quarter of the loop's own rate band
        idle = np.array([self.vertices(0, t) for t in range(CLIPS[0][0])])[:, ::7]
        spec = np.abs(np.fft.rfft(idle - idle.mean(0), axis=0)) ** 2
        energy = spec.sum((1, 2))
        self.assertGreater(energy[:13].sum() / energy[1:].sum(), 0.9)        # up to 12 cycles per loop (a breath is 4)

    def test_limbs_cut_in_no_deeper_than_the_old_clips(self):
        if not BEFORE:
            self.skipTest('no recorded baseline')
        body = limbs.Body(self.model, self.skeleton)
        for slot in SLOTS:
            ticks = CLIPS[slot][0]
            stride = 1 if ticks < 40 else 6
            mean = {g: [] for g in GROUPS}
            for t in range(0, ticks, stride):
                mats, w = body.world(self.local(slot, t))
                for g, bones in GROUPS.items():
                    others = (1, 18, 23) + tuple(b for g2, c in GROUPS.items() if g2 != g for b in c)
                    mean[g].append(body.count(mats, w, bones[1:] if g.startswith('leg') else bones, others))
            for g, values in mean.items():
                self.assertLessEqual(np.mean(values), BEFORE[slot][g] + 2, (slot, g, np.mean(values)))

    def test_the_footfalls_sound_and_the_eyes_keep_their_events(self):
        for slot in (2, 3, 4):
            kinds = [e[1] for e in self.events[slot]]
            self.assertEqual(kinds.count('sound'), 2 * gait.GAITS[slot]['cycles'], slot)
        for slot in SLOTS:
            self.assertGreaterEqual([e for e in self.events[slot] if e[1] == 'tex'].__len__(), 1, slot)
        self.assertEqual([e[0] for e in self.events[0] if e[1] == 'tex'], [0] + [k for k, _ in gait.BLINKS])


if __name__ == '__main__':
    unittest.main()
