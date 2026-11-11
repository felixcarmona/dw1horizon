"""Blossomon's idle, walk, condition walk and run: different from each other, seamless, roots planted, nothing sunk into
the floor or cutting into the body more than before, inside the resident animation buffer.

Needs the field model the clips were authored from (see field_animations/blossomon_gait.py) and the DW1 extraction:

    python3 tools/models/edit.py get 274 DIR     (at the commit before the clips) and BLOSSOMON_MODEL=DIR/274-Blossomon.MMD

The checks that compare with the old model skip when only the new model is at hand."""
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import animsheet
import mmd
import motionstorage
from tools.models.field_animations import blossomon_gait as gait
from tools.models.field_animations import okuwamon_limbs as limbs

SOURCE = Path(os.environ.get('BLOSSOMON_MODEL', 'build/imported-model-edit/edit/274-Blossomon.MMD'))
NB = 24
FEET = gait.FEET
VINES = tuple(range(10, 22))
BODY = (1, 2)
HEAD = (8, 9)
PAIRS = {'feet-trunk': (FEET, (2,)), 'vines-body': (VINES, BODY + HEAD), 'leaves-body': ((22, 23), BODY + HEAD), 'head-trunk': (HEAD, BODY)}
# the most vertices of one part inside another in any tick of the four clips of the model before this change
OLD_MOST = None


def feet_report(model, body, frames):
    """Per root: stance ticks (the centre near its lowest), slip over the ground in stance as a percentage of the root's speed,
    the lowest vertex below the floor (positive y is down) and the lift."""
    n = len(frames) - 1
    speed = -(frames[1][0][8] - frames[0][0][8])
    worlds = [body.world(f)[1] for f in frames[:n]]
    out = []
    for k in FEET:
        pts = [body.points(w, (k,)) for w in worlds]
        ys = np.array([p[:, 1].mean() for p in pts])
        zs = np.array([p[:, 2].mean() + f[0][8] for p, f in zip(pts, frames)])
        lo, hi = ys.max(), ys.min()
        stance = [t for t in range(n - 1) if ys[t] > lo - .25 * (lo - hi)]
        slip = np.array([abs(zs[t + 1] - zs[t]) for t in stance]) / speed * 100 if speed else np.zeros(1)
        out.append(dict(stance=len(stance), mean=float(slip.mean()), max=float(slip.max()), sunk=float(max(p[:, 1].max() for p in pts)),
                        lift=float(lo - hi)))
    return out


def penetration(body, frames, every=1):
    most = {k: 0 for k in PAIRS}
    most['feet-feet'] = 0
    for f in frames[:-1:every]:
        mats, w = body.world(f)
        for key, (a, b) in PAIRS.items():
            most[key] = max(most[key], body.count(mats, w, a, b))
        most['feet-feet'] = max(most['feet-feet'], sum(body.count(mats, w, (a,), (c,)) for a in FEET for c in FEET if a < c))
    return most


class BlossomonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SOURCE.exists() or not Path(mmd.EXTRACTED).exists():
            raise unittest.SkipTest('needs the Blossomon field model (tools/models/edit.py get 274) and the player DW1 extraction')
        cls.skeleton = [tuple(b) for b in json.loads(Path('content/species/274-blossomon.json').read_text())['model']['skeleton']]
        data = SOURCE.read_bytes()
        cls.old = None
        if hashlib.sha256(data).hexdigest() == gait.SOURCE_SHA256:
            mmd.exe().add_type(274, cls.skeleton)
            cls.old = mmd.MMD.parse(data, NB)
            cls.old.type = 274
            data, cls.proof = gait.build(data, cls.skeleton)
        else:
            cls.proof = None
        cls.data = data
        mmd.exe().add_type(274, cls.skeleton)
        cls.model = mmd.MMD.parse(data, NB)
        cls.model.type = 274
        cls.body = limbs.Body(cls.model, cls.skeleton)
        cls.clips = {s: animsheet.slot_frames(cls.model, NB, s)[0] for s in gait.SLOTS}
        cls.events = {s: animsheet.slot_frames(cls.model, NB, s)[2] for s in gait.SLOTS}

    def test_clips_loop_and_the_root_goes_at_one_speed(self):
        for slot in gait.SLOTS:
            f = self.clips[slot]
            self.assertEqual(f[0][1:], f[-1][1:], slot)
        for slot, (ticks, low, high) in {2: (48, 15, 31), 3: (60, 10, 20), 4: (33, 35, 52)}.items():
            f = self.clips[slot]
            self.assertEqual(len(f) - 1, ticks)
            speeds = {f[i][0][8] - f[i + 1][0][8] for i in range(len(f) - 1)}
            self.assertEqual(len(speeds), 1, slot)
            self.assertTrue(low <= speeds.pop() <= high, slot)
        self.assertEqual(len(self.clips[0]) - 1, gait.IDLE_TICKS)

    def test_tired_is_slower_than_the_walk_and_the_run_faster(self):
        v = {s: self.clips[s][0][0][8] - self.clips[s][1][0][8] for s in (2, 3, 4)}
        self.assertLess(v[3], v[2])
        self.assertLess(v[2], v[4])

    def test_the_four_clips_differ_in_posture_and_motion(self):
        mean = {s: np.mean([f[1][3:9] for f in self.clips[s][:-1]], axis=0) for s in gait.SLOTS}
        swing = {s: {b: np.ptp([f[b][3:6] for f in self.clips[s][:-1]], axis=0).max() / 4096 * 360 for b in (8, 10, 12, 14, 22)}
                 for s in gait.SLOTS}
        for a in gait.SLOTS:
            for b in gait.SLOTS:
                if a < b:
                    self.assertGreater(float(np.abs(mean[a] - mean[b]).max()) + max(abs(swing[a][k] - swing[b][k]) for k in swing[a]), 3, (a, b))
                    self.assertNotEqual([f[1:] for f in self.clips[a][:8]], [f[1:] for f in self.clips[b][:8]])
        lean = {s: np.mean([f[1][3] for f in self.clips[s][:-1]]) / 4096 * 360 for s in (2, 3, 4)}
        self.assertGreater(lean[4], lean[2] + 1)               # the run leans further forward
        sink = {s: np.mean([f[1][7] for f in self.clips[s][:-1]]) for s in (2, 3)}
        self.assertGreater(sink[3], sink[2] + 3)               # the tired walk is lower (y is down)
        for slot in (2, 3, 4):                                  # every vine and the head move
            for b in (8, 11, 12, 14, 15, 17, 18, 20, 21, 22, 23):
                self.assertGreater(swing[slot][b] if b in swing[slot] else np.ptp([f[b][3:6] for f in self.clips[slot][:-1]]) / 4096 * 360, 3, (slot, b))

    def test_the_trunk_moves_with_the_gait_and_nothing_is_hurried(self):
        for slot in (2, 3, 4):
            f = np.array(self.clips[slot], float)[:-1]
            r = f[:, 2, 3:6]
            ptp = [float(np.ptp((r[:, i] - r[0, i] + 2048) % 4096 - 2048)) / 4096 * 360 for i in range(3)]
            self.assertGreater(ptp[0], 4, slot)               # pitch
            self.assertGreater(ptp[1], 6, slot)               # twist against the pelvis
            self.assertGreater(float(np.ptp(f[:, 1, 7])), 5, slot)       # bob of the pelvis
            for b in (10, 12, 15, 8):                         # vines and head turn slowly: under 6 degrees a tick, as a true rotation
                m = [np.array(mmd.rot_matrix(*a[b][3:6])) for a in np.array(self.clips[slot], float)]
                peak = max(np.degrees(np.arccos(np.clip((np.trace(m[i].T @ m[i + 1]) - 1) / 2, -1, 1))) for i in range(len(m) - 1))
                self.assertLess(peak, 6, (slot, b))
            for k in FEET:                                    # a root's peak speed over the ground stays under the old run's 80
                zs = [self.body.points(self.body.world(a)[1], (k,)).mean(0) + np.array([0, 0, a[0][8]]) for a in self.clips[slot][:-1]]
                self.assertLess(float(np.linalg.norm(np.diff(zs, axis=0), axis=1).max()), 90, (slot, k))
        self.assertGreater(gait.GAITS[2]['n'] / gait.GAITS[2]['cycles'], 15)       # a step lasts 16 ticks or more in the walk

    def test_roots_are_planted_and_the_idle_stands_still(self):
        for slot in gait.SLOTS:
            for k, r in zip(FEET, feet_report(self.model, self.body, self.clips[slot])):
                self.assertLess(r['sunk'], 2.0, (slot, k))               # no sole under the floor
                if slot == 0:
                    self.assertLess(r['mean'] + r['max'], 1, (slot, k))
                else:
                    self.assertGreaterEqual(r['stance'], 5, (slot, k))
                    self.assertLess(r['mean'], 25, (slot, k))
                    self.assertLess(r['max'], 45, (slot, k))
                    self.assertGreater(r['lift'], 15, (slot, k))

    def test_no_tick_jumps(self):
        for slot in gait.SLOTS:
            a = np.array(self.clips[slot], float)
            step = np.abs(np.diff(a[:, 1:, 3:], axis=0)).max(axis=2).max(axis=1)
            self.assertLess(step.max(), 2.5 * np.median(step), slot)

    def test_nothing_sinks_into_the_floor_but_the_roots_stand_on_it(self):
        for slot in gait.SLOTS:
            for f in self.clips[slot][:-1:2]:
                w = self.body.world(f)[1]
                pieces = self.body.points(w, tuple(range(1, 3)) + tuple(range(8, 24)))
                self.assertLess(float(pieces[:, 1].max()), -4, slot)     # vines, leaves, head and stalk clear of the floor

    def test_the_body_is_not_cut_more_than_before(self):
        global OLD_MOST
        now = {s: penetration(self.body, self.clips[s]) for s in gait.SLOTS}
        if self.old is not None:
            old_body = limbs.Body(self.old, self.skeleton)
            OLD_MOST = {}
            for s in gait.SLOTS:
                for k, v in penetration(old_body, animsheet.slot_frames(self.old, NB, s)[0]).items():
                    OLD_MOST[k] = max(OLD_MOST.get(k, 0), v)
        else:
            OLD_MOST = {'feet-trunk': 59, 'feet-feet': 16, 'vines-body': 60, 'leaves-body': 16, 'head-trunk': 6}
        for s in gait.SLOTS:
            for k, v in now[s].items():
                self.assertLessEqual(v, OLD_MOST[k], (s, k))

    def test_resident_buffer_and_the_slots_changed(self):
        storage = motionstorage.audit(self.data, NB)
        self.assertTrue(storage['fits'])
        self.assertLess(storage['resident_bytes'], 100352)
        if self.proof is not None:
            self.assertLessEqual(set(self.proof['changed_slots']), {0, 1, 2, 3, 4, 18, 33})
            self.assertEqual(self.old.tmd.build(), self.model.tmd.build())

    def test_the_blink_and_footsteps_are_kept(self):
        for slot in gait.SLOTS:
            ev = self.events[slot]
            tex = [e for e in ev if e[1] == 'tex']
            self.assertEqual(tex[0][0], 0, slot)
            self.assertGreaterEqual(len(tex), 5, slot)
            sounds = [e for e in ev if e[1] == 'sound']
            self.assertEqual(len(sounds), 0 if slot == 0 else gait.GAITS[slot]['cycles'], slot)


if __name__ == '__main__':
    unittest.main()
