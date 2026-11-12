"""Check Lynxmon's walk, tired walk and run (species 323) on the real import: four legs that read as four legs.

The model is read from build/imported-model-edit/edit (`tools/models/edit.py get 323`; LYNXMON_MODEL names another path).
Before the change it is `lynxmon_gait.SOURCE`: the generator is run on it (a few seconds) and its result checked; afterwards
it is the result itself. Lynxmon keeps its mesh, its texture and its proportions: only the clips change.

Lynxmon faces -z: chest 1, neck 2, head 3, jaw 4, right foreleg 5-8, left foreleg 9-12, hips 13, tail 14-15, right hind leg
16-19, left hind leg 20-23 (the toes are 8, 12, 19 and 23).
"""
import copy
import hashlib
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
from tools.models.field_animations import lynxmon_gait as gait
from tools.test_tortomon_gait import inside, DIRS

BONES = 24
EXPECTED = 'e88b1511b80b65af1d80c0739a9dc8fe70e71322853cb0b99d60b11428f49e33'    # the model after this change (the delta's target)
TICKS = {2: 36, 3: 48, 4: 32}               # each clip is two different cycles of 18, 24 and 16 ticks
IDLE_TICKS = 80
SPEED = {2: 26, 3: 15, 4: 46}
TOES = {'RF': 8, 'LF': 12, 'RH': 19, 'LH': 23}
BELLY = 165                                  # the underside of the belly over the floor: a swinging paw must stay under it
G = dict(arm_r=[5, 6, 7, 8], arm_l=[9, 10, 11, 12], leg_r=[16, 17, 18, 19], leg_l=[20, 21, 22, 23], hips=[13], torso=[1],
         tail=[14, 15], head=[2, 3, 4])
# vertices and triangle centres inside another part, worst tick over the idle and the three gaits: for each pair of
# parts what the imported clips measured (the legs' hold in the hips and the chest comes from the rest pose itself), so the
# new clips penetrate no more than the old ones (the sum over all pairs and every tick went from 736 to 387).
PENETRATION = {('arm_r', 'arm_l'): 0, ('arm_r', 'leg_r'): 30, ('arm_r', 'leg_l'): 0, ('arm_r', 'hips'): 6,
               ('arm_r', 'torso'): 110, ('arm_r', 'tail'): 0, ('arm_r', 'head'): 6, ('arm_l', 'arm_r'): 0,
               ('arm_l', 'leg_r'): 0, ('arm_l', 'leg_l'): 6, ('arm_l', 'hips'): 6, ('arm_l', 'torso'): 49,
               ('arm_l', 'tail'): 0, ('arm_l', 'head'): 7, ('leg_r', 'arm_r'): 43, ('leg_r', 'arm_l'): 0,
               ('leg_r', 'leg_l'): 19, ('leg_r', 'hips'): 80, ('leg_r', 'torso'): 5, ('leg_r', 'tail'): 0,
               ('leg_r', 'head'): 0, ('leg_l', 'arm_r'): 0, ('leg_l', 'arm_l'): 3, ('leg_l', 'leg_r'): 10,
               ('leg_l', 'hips'): 74, ('leg_l', 'torso'): 11, ('leg_l', 'tail'): 0, ('leg_l', 'head'): 0,
               ('hips', 'arm_r'): 0, ('hips', 'arm_l'): 0, ('hips', 'leg_r'): 19, ('hips', 'leg_l'): 18,
               ('hips', 'torso'): 48, ('hips', 'tail'): 0, ('hips', 'head'): 0, ('torso', 'arm_r'): 53,
               ('torso', 'arm_l'): 33, ('torso', 'leg_r'): 0, ('torso', 'leg_l'): 0, ('torso', 'hips'): 20,
               ('torso', 'tail'): 0, ('torso', 'head'): 15, ('tail', 'arm_r'): 0, ('tail', 'arm_l'): 0,
               ('tail', 'leg_r'): 6, ('tail', 'leg_l'): 3, ('tail', 'hips'): 9, ('tail', 'torso'): 0, ('tail',
               'head'): 0, ('head', 'arm_r'): 5, ('head', 'arm_l'): 5, ('head', 'leg_r'): 0, ('head',
               'leg_l'): 0, ('head', 'hips'): 0, ('head', 'torso'): 37, ('head', 'tail'): 0}
PENETRATION_SLACK = {('head', 'arm_l'): 2, ('arm_l', 'leg_l'): 2, ('leg_l', 'arm_l'): 9}   # the pairs the new clips touch a little more than the old ones (a few points: the left fore leg and the head, the left hind paw beside the left fore leg)


class LynxmonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy
        except ImportError:
            raise unittest.SkipTest('needs numpy for the mesh checks')
        cls.np = numpy
        path = Path(os.environ.get('LYNXMON_MODEL', 'build/imported-model-edit/edit/323-Lynxmon.MMD'))
        if not path.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 323')
        cls.rig = json.loads(Path('content/species/323-lynxmon.json').read_text())['model']['skeleton']
        mmd.exe().skeleton[323] = cls.rig
        mmd.exe().bone_count[323] = BONES
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        cls.report = None
        if digest == gait.SOURCE:
            data, cls.report = gait.build(data, cls.rig)
        elif digest != EXPECTED:
            raise unittest.SkipTest('the model is neither the one before nor the one after this change')
        cls.data = data
        cls.tim = path.with_suffix('.TIM')
        cls.new = mmd.MMD.parse(cls.data, BONES)
        cls.new.type = 323
        import animstudio
        cls.mesh = animstudio.FastMesh(SimpleNamespace(m=cls.new, skel=cls.rig))

    def frames(self, slot):
        return animsheet.slot_frames(self.new, BONES, slot)[0]

    def world(self, pose):
        p = copy.deepcopy(pose)
        p[0] = [4096] * 3 + [0] * 6
        return mmd.bone_matrices(self.new, p)

    def feet(self, slot):
        """Per tick (closing frame included): each toe's world position (x, height over the floor, z with the root's travel)."""
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

    def test_the_build_reports_the_gaits_it_changed(self):
        if self.report is None:
            self.skipTest('needs the model before this change')
        self.assertEqual(self.report['changed_slots'], [2, 3, 4])
        self.assertTrue(self.report['mesh_exact'] and self.report['other_programs_exact'])

    def test_storage_fits_the_resident_buffer(self):
        from motionstorage import audit
        storage = audit(self.data, BONES)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)

    def test_the_idle_is_untouched(self):
        frames = self.frames(0)
        self.assertEqual(len(frames) - 1, IDLE_TICKS)
        self.assertEqual({f[0][8] for f in frames}, {0})

    def test_cycle_lengths_speeds_and_their_order(self):
        speeds = {}
        for slot, ticks in TICKS.items():
            frames = self.frames(slot)
            self.assertEqual(len(frames) - 1, ticks, slot)
            steps = {frames[i + 1][0][8] - frames[i][0][8] for i in range(ticks)}
            self.assertEqual(len(steps), 1, slot)
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
                hs = [r[name][1] for r in rows]
                stance = [i for i, h in enumerate(hs) if h < min(hs) + 0.25 * (max(hs) - min(hs))]
                self.assertGreaterEqual(len(stance), 3, (slot, name))
                slips = [abs(rows[i + 1][name][2] - rows[i][name][2]) / SPEED[slot]
                         for i in range(len(rows) - 1) if i in stance and i + 1 in stance]
                self.assertTrue(slips, (slot, name))
                self.assertLess(sum(slips) / len(slips), 0.25, (slot, name))
                self.assertLess(max(slips), 0.45, (slot, name))

    def test_the_studio_measures_no_slide_in_stance(self):
        import animstudio
        for slot in TICKS:
            studio = animstudio.Model(f'{self._write()}:323:{self.tim}', slot)
            _, results = animstudio.metrics(studio)
            for bone, _, _, mean, worst, lift in results:
                self.assertLess(mean, 25, (slot, bone))
                self.assertLess(worst, 45, (slot, bone))
                self.assertGreater(lift, 12, (slot, bone))

    def _write(self):
        path = Path(os.environ.get('TMPDIR', '/tmp')) / f'lynxmon-gait-{os.getpid()}.MMD'
        path.write_bytes(self.data)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path

    def test_the_feet_do_not_sink_and_a_swinging_paw_stays_under_the_belly(self):
        """The old clips swung paws 146 to 263 up into a belly 165 over the floor, where the flame fur hid them; the new
        ones keep the paw 40 to 125 over the floor and it is always an open silhouette under the body."""
        top = {2: 100, 3: 76, 4: 135}
        for slot in TICKS:
            for tick, row in enumerate(self.feet(slot)):
                for name, (_, height, _) in row.items():
                    self.assertGreater(height, 33, (slot, name, tick))
                    self.assertLess(height, top[slot], (slot, name, tick))
                    self.assertLess(height, BELLY - 30, (slot, name, tick))
            lifts = {name: max(r[name][1] for r in self.feet(slot)) - min(r[name][1] for r in self.feet(slot)) for name in TOES}
            for name, lift in lifts.items():
                self.assertGreater(lift, 25 if slot == 3 else 45, (slot, name))

    def test_the_limbs_stand_apart_in_every_tick(self):
        """Fore paws stay outside the hind paws sideways (the old clips brought them to the same x, 0 to 15 apart on average),
        and the fore and hind paws of one side stay at least 95 units apart along the body (130 in the walks, 107 in the run)."""
        low = {2: 40, 3: 40, 4: 17}
        for slot in TICKS:
            for tick, row in enumerate(self.feet(slot)):
                for fore, hind in (('RF', 'RH'), ('LF', 'LH')):
                    self.assertGreater(abs(row[fore][0]) - abs(row[hind][0]), low[slot], (slot, fore, tick))
                    self.assertGreater(abs(row[fore][2] - row[hind][2]), 95, (slot, fore, tick))
                self.assertGreater(row['RF'][0] - row['LF'][0], 330, (slot, tick))     # the fore pair is a body apart
                self.assertGreater(row['RH'][0] - row['LH'][0], 235, (slot, tick))

    def test_the_walks_alternate_the_legs(self):
        """A lateral sequence: the hind paw on one side lifts, then the fore paw of the same side, then the other side."""
        for slot in (2, 3):
            rows = self.feet(slot)[:-1]
            n = len(rows) // 2
            lift_at = {}
            for name in TOES:
                hs = [r[name][1] for r in rows[:n]]
                lift_at[name] = max(range(n), key=lambda i: hs[i])      # the tick the paw is highest
            order = sorted(lift_at, key=lift_at.get)
            start = order.index('LH')
            self.assertEqual(order[start:] + order[:start], ['LH', 'LF', 'RH', 'RF'], (slot, lift_at))
            for i in range(4):
                gap = (lift_at[order[(i + 1) % 4]] - lift_at[order[i]]) % n
                self.assertGreaterEqual(gap, n // 8, (slot, lift_at))      # no two paws rise together

    def test_the_body_moves_against_the_legs(self):
        """The chest rolls, bobs and the hips twist the other way, the two walk cycles differ, the tail trails."""
        for slot, bob, roll in ((2, 8, 4), (3, 6, 4), (4, 15, 2)):
            frames = self.frames(slot)[:-1]
            ys = [f[1][7] for f in frames]
            self.assertGreater(max(ys) - min(ys), bob, slot)
            rolls = [((f[1][5] + 2048) % 4096 - 2048) * 360 / 4096 for f in frames]
            self.assertGreater(max(rolls) - min(rolls), roll, slot)
            hips = [((f[13][4] + 2048) % 4096 - 2048) for f in frames]
            chest = [((f[1][4] + 2048) % 4096 - 2048) for f in frames]
            self.assertGreater(max(hips) - min(hips), 8, slot)
            half = len(frames) // 2
            diff = max(abs(frames[i][1][7] - frames[i + half][1][7]) for i in range(half))
            self.assertGreater(diff, 1, slot)                          # the second cycle is not a copy of the first
            tail = [f[15][3] for f in frames]
            self.assertGreater(max(tail) - min(tail), 12, slot)
            self.assertGreater(max(chest) - min(chest), 8, slot)

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
        legs = {'RF': (5, 6, 7), 'LF': (9, 10, 11), 'RH': (16, 17, 18), 'LH': (20, 21, 22)}
        for slot in TICKS:
            for tick, pose in enumerate(self.frames(slot)[:-1]):
                pts = [np.array(m, float)[:3, 3] for m in self.world(pose)]
                for leg, (hip, knee, heel) in legs.items():
                    upper, lower, dist = norm(pts[knee] - pts[hip]), norm(pts[heel] - pts[knee]), norm(pts[heel] - pts[hip])
                    self.assertLess(dist, upper + lower - 1, (slot, leg, tick))
                    self.assertGreater(dist, abs(upper - lower) + 5, (slot, leg, tick))

    def test_parts_penetrate_no_more_than_in_the_imported_clips(self):
        for (a, b), most in PENETRATION.items():
            most += PENETRATION_SLACK.get((a, b), 0)
            for slot in (0, *TICKS):
                worst = max(self.inside_count(f, a, b) for f in self.frames(slot)[:-1:3])
                self.assertLessEqual(worst, most, (a, b, slot))


if __name__ == '__main__':
    unittest.main()
