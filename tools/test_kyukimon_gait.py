"""Check Kyukimon's idle, walk, tired walk and run (species 322) on the real import.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 322`; KYUKIMON_MODEL names another
path): the imported model, to which the overlay applies the chibi proportions and then these clips. The test runs
`kyukimon_gait.build` on it (about 3 s) and checks the result.

Kyukimon faces -z: body 1, hips 2, right leg 3-6 (thigh, shin, ankle, toe), left leg 12-15, tail 7-11, chest 22, head 23, strap 26,
right arm 16-18 (upper arm, forearm, hand with its blade), left arm 19-21. The model is the edit.py output with the species' slot
aliases applied (the overlay's own input).
"""
import copy
import json
import math
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animsheet
import mmd
from tools.models.field_animations import kyukimon_gait as gait
from tools.test_tortomon_gait import inside, DIRS

BONES = 27
TICKS = {2: 32, 3: 44, 4: 28}               # each clip is two different cycles of 16, 22 and 14 ticks
IDLE_TICKS = 74
SPEED = {2: 18, 3: 13, 4: 36}
TOES = {'LH': 15, 'RH': 6}
LEGS = {'LH': (12, 13, 14, 15), 'RH': (3, 4, 5, 6)}
G = dict(arm_r=[16, 17, 18], arm_l=[19, 20, 21], leg_r=[3, 4, 5, 6], leg_l=[12, 13, 14, 15], hips=[2], torso=[1, 22], tail=[7, 8, 9, 10, 11],
         strap=[26], head=[23])
# vertices and triangle centres inside another part, worst sampled tick, over the idle and the three gaits. The chibi model's own
# clips measured: legs in the hips 28 (idle) to 42, arms in the torso 6, the tail in the hips 5, the head in an arm 11 / 9, the strap
# in an arm 3 and in the torso 4; the new clips stay within that (the swinging arms touch the tail's root by 4).
PENETRATION = {('leg_r', 'hips'): 42, ('leg_l', 'hips'): 42, ('arm_r', 'torso'): 6, ('arm_l', 'torso'): 6, ('tail', 'hips'): 5,
               ('head', 'arm_r'): 11, ('head', 'arm_l'): 9, ('strap', 'arm_r'): 3, ('strap', 'arm_l'): 3, ('strap', 'torso'): 4,
               ('arm_r', 'tail'): 4, ('arm_l', 'tail'): 4,
               ('arm_r', 'leg_r'): 0, ('arm_r', 'leg_l'): 0, ('arm_l', 'leg_l'): 0, ('arm_l', 'leg_r'): 0, ('leg_r', 'leg_l'): 0,
               ('arm_r', 'hips'): 0, ('arm_l', 'hips'): 0, ('arm_r', 'arm_l'): 0}


class KyukimonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy
        except ImportError:
            raise unittest.SkipTest('needs numpy for the mesh checks')
        cls.np = numpy
        path = Path(os.environ.get('KYUKIMON_MODEL', 'build/imported-model-edit/edit/322-Kyukimon.MMD'))
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 322')
        cls.rig = json.loads(Path('content/species/322-kyukimon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[322] = cls.rig
        mmd.exe().bone_count[322] = BONES
        import species
        spec = json.loads(Path('content/species/322-kyukimon.json').read_text())
        cls.data, cls.report = gait.build(species.apply_slot_aliases(path.read_bytes(), spec), cls.rig)
        cls.new = mmd.MMD.parse(cls.data, BONES)
        cls.new.type = 322
        import animstudio
        cls.mesh = animstudio.FastMesh(SimpleNamespace(m=cls.new, skel=cls.rig))
        cls._pen = {}

    def frames(self, slot):
        return animsheet.slot_frames(self.new, BONES, slot)[0]

    def world(self, pose):
        p = copy.deepcopy(pose)
        p[0] = [4096] * 3 + [0] * 6
        return mmd.bone_matrices(self.new, p)

    def feet(self, slot):
        """Per tick (closing frame included): each toe point's world position (x, height, z with the root's travel)."""
        np = self.np
        rows = []
        for pose in self.frames(slot):
            mats = self.world(pose)
            row = {}
            for name, bone in TOES.items():
                x, y, z = (float(np.array(mats[bone], float)[i, 3]) for i in range(3))
                row[name] = (x, -y - pose[0][7], z + pose[0][8])
            rows.append(row)
        return rows

    def inside_count(self, pose, a, b):
        np, mesh = self.np, self.mesh
        world = mesh.world(self.world(pose)).astype(float)
        tri = world[mesh.tri[np.isin(mesh.bone, G[a])]]
        points = np.vstack([tri.reshape(-1, 3), tri.mean(1)])
        tris = world[mesh.tri[np.isin(mesh.bone, G[b])]]
        votes = sum(inside(np, points, tris, d).astype(int) for d in DIRS)
        return int((votes >= 3).sum())

    def test_chibi_proportions_and_the_record_patch_are_kept(self):
        self.assertEqual(self.report['factors']['leg_axial'], 0.878)
        self.assertIn('species_patch', self.report)
        self.assertEqual(self.report['gait']['changed_slots'], [2, 3, 4])    # the idle (0, 33) is the chibi build's

    def test_storage_fits_the_resident_buffer(self):
        from motionstorage import audit
        storage = audit(self.data, BONES)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)

    def test_the_idle_stands_still_and_closes(self):
        frames = self.frames(0)
        self.assertEqual(len(frames) - 1, IDLE_TICKS)
        self.assertEqual({f[0][8] for f in frames}, {0})
        for b in range(1, BONES):
            for i in range(3, 6):
                self.assertIn((frames[0][b][i] - frames[-1][b][i]) % 4096, (0, 1, 4095), (b, i))
        rows = self.feet(0)
        for name in TOES:
            for axis in (0, 2):
                values = [r[name][axis] for r in rows]
                self.assertLess(max(values) - min(values), 4, (name, axis))
            heights = [r[name][1] for r in rows]
            self.assertLess(max(heights) - min(heights), 4, name)

    def test_the_idle_moves_with_character_and_without_jumps(self):
        np, mesh = self.np, self.mesh
        frames = self.frames(0)
        for b, least in ((7, 20), (1, 5), (17, 15)):             # the tail root, the body, a forearm (the idle is the chibi build's)
            turns = [f[b][3:6] for f in frames]
            spread = max(max(t[i] for t in turns) - min(t[i] for t in turns) for i in range(3))
            self.assertGreater(min(spread, 4096 - spread), least, b)
        speeds, prev = [], None
        for pose in frames:
            world = mesh.world(self.world(pose)).astype(float).reshape(-1, 3)
            if prev is not None:
                speeds.append(float(np.linalg.norm(world - prev, axis=1).mean()))
            prev = world
        wide = [sum(speeds[(i + k) % len(speeds)] for k in range(-2, 3)) / 5 for i in range(len(speeds))]
        med = sorted(speeds)[len(speeds) // 2]
        self.assertLess(max(wide), 2.5 * med)

    def test_cycle_lengths_speeds_and_their_order(self):
        speeds = {}
        for slot, ticks in TICKS.items():
            frames = self.frames(slot)
            self.assertEqual(len(frames) - 1, ticks, slot)
            steps = {frames[i + 1][0][8] - frames[i][0][8] for i in range(ticks)}
            self.assertEqual(len(steps), 1, slot)                # the same step every tick (before: 7 to 10 different steps)
            speeds[slot] = -steps.pop()
            self.assertEqual(speeds[slot], SPEED[slot])
        self.assertLess(speeds[3], speeds[2])
        self.assertLess(speeds[2], speeds[4])
        self.assertTrue(15 <= speeds[2] <= 31 and 10 <= speeds[3] <= 20 and 35 <= speeds[4] <= 52)
        self.assertGreater(TICKS[3], TICKS[2])

    def test_loops_are_seamless(self):
        for slot in TICKS:
            frames = self.frames(slot)
            first, last = frames[0], frames[-1]
            for b in range(1, BONES):
                for i in range(3, 6):
                    self.assertIn((first[b][i] - last[b][i]) % 4096, (0, 1, 4095), (slot, b, i))
                for i in (6, 7, 8):
                    self.assertLessEqual(abs(first[b][i] - last[b][i]), 1, (slot, b, i))

    def test_the_feet_are_planted_in_stance(self):
        for slot in TICKS:
            rows = self.feet(slot)
            for name in TOES:
                stance = [i for i, r in enumerate(rows) if r[name][1] < 24]
                self.assertGreaterEqual(len(stance), 3, (slot, name))
                slips = [abs(rows[i + 1][name][2] - rows[i][name][2]) / SPEED[slot]
                         for i in range(len(rows) - 1) if i in stance and i + 1 in stance]
                self.assertTrue(slips, (slot, name))
                self.assertLess(sum(slips) / len(slips), 0.25, (slot, name))
                self.assertLess(max(slips), 0.45, (slot, name))

    def test_the_studio_measures_no_slide_in_stance(self):
        """The studio's measure: a foot in the lowest quarter of its lift moves over the ground by under 25 % of the
        body's speed on average and 45 % at worst (the chibi clips before: tired walk 172 % mean, 446 % worst)."""
        import animstudio
        for slot in TICKS:
            spec = f'{self._write()}:322:{self._write(tim=True)}'
            studio = animstudio.Model(spec, slot)
            _, results = animstudio.metrics(studio)
            for bone, _, _, mean, worst, lift in results:
                self.assertLess(mean, 25, (slot, bone))
                self.assertLess(worst, 45, (slot, bone))
                self.assertGreater(lift, 18, (slot, bone))

    def _write(self, tim=False):
        import tempfile
        if not hasattr(self, '_dir'):
            type(self)._dir = tempfile.mkdtemp()
            Path(self._dir, 'm.MMD').write_bytes(self.data)
            src = Path(os.environ.get('KYUKIMON_MODEL', 'build/imported-model-edit/edit/322-Kyukimon.MMD')).with_suffix('.TIM')
            Path(self._dir, 'm.TIM').write_bytes(src.read_bytes())
        return str(Path(self._dir, 'm.TIM' if tim else 'm.MMD'))

    def test_each_foot_strides_and_the_two_stay_on_their_sides(self):
        bounds = {2: 120, 3: 90, 4: 120}          # fore-aft travel of a claw point in the body frame (units)
        for slot in TICKS:
            rows = self.feet(slot)[:-1]
            speed = SPEED[slot]
            for name, side in (('LH', -1), ('RH', 1)):
                self.assertGreater(min(r[name][0] * side for r in rows), 20, (slot, name))
            self.assertGreater(min(abs(r['RH'][0] - r['LH'][0]) for r in rows), 60, slot)
            for name in TOES:
                body = [r[name][2] + speed * i for i, r in enumerate(rows)]
                self.assertGreater(max(body) - min(body), bounds[slot], (slot, name))

    def test_the_feet_clear_the_floor_in_swing_and_do_not_sink(self):
        for slot in TICKS:
            rows = self.feet(slot)
            for name in TOES:
                heights = [r[name][1] for r in rows]
                self.assertGreater(min(heights), -4, (slot, name))
                self.assertGreater(max(heights), 15, (slot, name))

    def test_the_gaits_differ_and_the_tired_walk_rides_lowest(self):
        mean = lambda slot, i: sum(f[1][i] for f in self.frames(slot)) / len(self.frames(slot))
        self.assertGreater(mean(3, 7), mean(2, 7))              # y grows downward
        self.assertGreater(mean(3, 3), mean(2, 3))
        self.assertGreater(mean(4, 3), mean(3, 3))
        for a, b in ((2, 3), (3, 4), (2, 4)):
            self.assertNotEqual(self.frames(a)[:3], self.frames(b)[:3])

    def test_the_body_sinks_and_rises_with_every_step_by_a_clear_amount(self):
        least = {2: 18, 3: 14, 4: 22}           # the pelvis' height, peak to peak (the chibi clips: 19 / 31 / 65 in uneven jumps)
        for slot, amount in least.items():
            height = [f[1][7] for f in self.frames(slot)[:-1]]
            self.assertGreaterEqual(max(height) - min(height), amount, slot)
            self.assertLessEqual(max(height) - min(height), 40, slot)
            n = len(height)
            smooth = [sum(height[(i + k) % n] for k in (-1, 0, 1)) / 3 for i in range(n)]
            peaks = [i for i in range(n) if smooth[i] > smooth[i - 1] and smooth[i] >= smooth[(i + 1) % n]]
            self.assertEqual(len(peaks), 4, (slot, peaks))       # one dip per step, two steps a cycle

    def test_the_two_cycles_and_the_two_legs_are_not_alike(self):
        """The metronome is broken: the second half of each clip differs from the first (the lifted foot's height, the
        pelvis' dip, the arms), and one leg lifts higher than the other."""
        for slot, ticks in TICKS.items():
            half = ticks // 2
            frames = self.frames(slot)
            for b, least in ((1, 4), (3, 6), (12, 6), (16, 4), (2, 3)):          # body, the two thighs, a shoulder, the hips
                gap = max(max(abs(frames[i][b][k] - frames[i + half][b][k]) for k in (3, 4, 5)) for i in range(half))
                self.assertGreater(gap, least, (slot, b))
            lifts = {name: max(r[name][1] for r in self.feet(slot)) for name in TOES}
            self.assertGreater(abs(lifts['LH'] - lifts['RH']), 0.5, slot)
            heights = {name: [r[name][1] for r in self.feet(slot)] for name in TOES}
            peaks = {n: [max(h[:half]), max(h[half:])] for n, h in heights.items()}
            self.assertGreater(abs(peaks['LH'][0] - peaks['LH'][1]) + abs(peaks['RH'][0] - peaks['RH'][1]), 1, slot)

    def test_the_whole_body_moves_with_the_stride(self):
        """The chibi clips played the idle's loop on every bone above the hips and left the head, hands, strap and wing spikes
        still. Now each moves, and on the stride's own cycle: the hips and the body turn against each other, the arms swing
        against the legs on their sides and the tail's segments follow one another."""
        np = self.np
        for slot, ticks in TICKS.items():
            half = ticks // 2
            frames = self.frames(slot)[:-1]
            for b, least in ((1, 5), (2, 5), (22, 3), (23, 3), (16, 8), (19, 8), (17, 6), (20, 6), (18, 3), (21, 3), (7, 3), (9, 3), (11, 3), (26, 2)):
                span = max(max(f[b][i] for f in frames) - min(f[b][i] for f in frames) for i in (3, 4, 5))
                self.assertGreater(min(span, 4096 - span) * 360 / 4096, least, (slot, b))
            # at the tick the left toe is furthest forward: the left hip leads, the left hand is behind its shoulder and the
            # right hand ahead of its own
            rows = [np.array([np.array(m, float)[:3, 3] for m in self.world(f)]) for f in frames]
            t = min(range(half), key=lambda i: rows[i][15][2])
            r = rows[t]
            self.assertLess(r[12][2], r[3][2] - 2, slot)
            self.assertGreater(r[21][2] - r[19][2], r[18][2] - r[16][2] + 10, slot)
            # one cycle: the arms' swing repeats at the stride (a half-clip shift of the cycle is the other leg and arm)
            hands = [rows[i][18][2] - rows[i][16][2] for i in range(len(rows))]
            self.assertGreater(max(hands) - min(hands), 25 if slot != 3 else 12, slot)

    def test_each_foot_points_along_the_way(self):
        """The toe stays within a few degrees of its own 30 degree outward splay round the whole loop (the chibi clips
        turned it 26 to 167 degrees in the walk and the whole way round in the run) and the shin never swings more than 45 degrees past
        vertical."""
        np = self.np
        for slot in (0, *TICKS):
            for tick, pose in enumerate(self.frames(slot)[:-1]):
                pts = [np.array(m, float)[:3, 3] for m in self.world(pose)]
                for leg, (hip, knee, heel, toe) in LEGS.items():
                    d = pts[toe] - pts[heel]
                    yaw = math.degrees(math.atan2(d[0], -d[2]))
                    side = 1 if leg == 'RH' else -1
                    self.assertLess(abs(yaw - 30 * side), 8, (slot, leg, tick))
                    shin = pts[heel] - pts[knee]
                    if slot != 4:              # the run kicks the heel high behind the body
                        self.assertLess(math.degrees(math.atan2(shin[2], shin[1])), 135, (slot, leg, tick))

    def test_no_tick_jumps(self):
        np, mesh = self.np, self.mesh
        for slot in TICKS:
            speeds, prev = [], None
            for pose in self.frames(slot):
                world = mesh.world(self.world(pose)).astype(float).reshape(-1, 3)
                if prev is not None:
                    speeds.append(float(np.linalg.norm(world - prev, axis=1).mean()))
                prev = world
            med = sorted(speeds)[len(speeds) // 2]
            self.assertLess(max(speeds), 2.5 * med, slot)

    def test_no_leg_is_ever_stretched_or_folded_to_its_limit(self):
        np = self.np
        norm = np.linalg.norm
        for slot in TICKS:
            for tick, pose in enumerate(self.frames(slot)[:-1]):
                pts = [np.array(m, float)[:3, 3] for m in self.world(pose)]
                for leg, (hip, knee, heel, _) in LEGS.items():
                    upper, lower, dist = norm(pts[knee] - pts[hip]), norm(pts[heel] - pts[knee]), norm(pts[heel] - pts[hip])
                    self.assertLess(dist, upper + lower - 1, (slot, leg, tick))
                    self.assertGreater(dist, abs(upper - lower) + 5, (slot, leg, tick))

    def test_parts_penetrate_no_more_than_in_the_chibi_clips(self):
        for (a, b), most in PENETRATION.items():
            for slot in (0, *TICKS):
                worst = max(self.inside_count(f, a, b) for f in self.frames(slot)[:-1])
                self.assertLessEqual(worst, most, (a, b, slot))


if __name__ == '__main__':
    unittest.main()
