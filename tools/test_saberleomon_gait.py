"""SaberLeomon's carriage and sway (field_animations/saberleomon_gait.py): no paw or forearm reaches through the mane or the
jaw on any tick of the idles, walk, condition walk and run; every loop closes on its first pose; the root's travel, the mesh,
the skeleton and the other programs stay exact; the resident motion buffer stays under its limit. Needs the delta model
and the DW1 extraction:

    python3 tools/models/edit.py get 258      (writes build/imported-model-edit/edit/258-SaberLeomon.MMD)"""
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / 'models'))
import numpy as np
import animsheet
import mmd
import motionstorage
import retarget
from tools.models.field_animations import meshclash, pace, saberleomon_gait as gen

SOURCE = Path(os.environ.get('SABERLEOMON_MODEL', 'build/imported-model-edit/edit/258-SaberLeomon.MMD'))
SPECIES_JSON = Path(__file__).resolve().parent.parent / 'content/species/258-saberleomon.json'
SPEEDS = {2: 22.5, 3: 15, 4: 40}
FORELEGS = (5, 6, 7, 8, 9, 10)
MOVED = {gen.CHEST, gen.NECK, gen.HEAD, gen.HIPS, *gen.TAIL, *gen.LEG_BONES}


def _clips(data, skeleton):
    model = mmd.MMD.parse(data, len(skeleton))
    model.type = 258
    return model, {s: animsheet.slot_frames(model, len(skeleton), s)[0] for s in range(5)}


def _degrees(a, b):
    ra, rb = np.array(mmd.rot_matrix(*a[3:6])), np.array(mmd.rot_matrix(*b[3:6]))
    return math.degrees(math.acos(max(-1.0, min(1.0, (np.trace(ra.T @ rb) - 1) / 2))))


class SaberLeomonGait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SOURCE.exists() or not Path(mmd.EXTRACTED).exists():
            raise unittest.SkipTest('needs the SaberLeomon delta model and the player DW1 extraction')
        cls.skeleton = [tuple(b) for b in json.loads(SPECIES_JSON.read_text())['model']['skeleton']]
        cls.nb = len(cls.skeleton)
        data = SOURCE.read_bytes()
        mmd.exe().skeleton[258] = cls.skeleton
        mmd.exe().bone_count[258] = cls.nb
        cls.final_bytes, cls.report = pace.build(data, cls.skeleton)
        profiles = json.loads(pace.MANIFEST.read_text())
        profiles['258'].pop('after_generator')
        with tempfile.TemporaryDirectory() as tmp:
            plain = Path(tmp) / 'pace.json'
            plain.write_text(json.dumps(profiles))
            keep, pace.MANIFEST = pace.MANIFEST, plain
            try:
                before_bytes, _ = pace.build(data, cls.skeleton)
            finally:
                pace.MANIFEST = keep
        cls.model, cls.new = _clips(cls.final_bytes, cls.skeleton)
        cls.old_model, cls.old = _clips(before_bytes, cls.skeleton)

    def test_the_manifest_runs_the_layer(self):
        self.assertEqual(json.loads(pace.MANIFEST.read_text())['258']['after_generator'], gen.__name__)

    def test_nothing_reaches_through_the_mane(self):
        clash = meshclash.Clash(self.model, self.skeleton)
        for slot, frames in self.new.items():
            for t, pose in enumerate(frames[:-1]):
                world = clash.world(pose)
                pairs, depth = clash.clash(pose, FORELEGS, (gen.HEAD, gen.JAW), world=world)
                self.assertEqual((pairs, depth), (0, 0.0), (slot, t))

    def test_the_old_clips_did_reach_through(self):
        # the measurement sees the fault it is there to catch
        clash = meshclash.Clash(self.old_model, self.skeleton)
        worst = max(clash.clash(p, FORELEGS, (gen.HEAD, gen.JAW))[0] for p in self.old[2][:-1])
        self.assertGreater(worst, 20)

    def test_the_forelegs_stay_clear_of_each_other(self):
        clash = meshclash.Clash(self.model, self.skeleton)
        for slot, frames in self.new.items():
            for t, pose in enumerate(frames[:-1]):
                self.assertEqual(clash.clash(pose, (5, 6, 7), (8, 9, 10))[0], 0, (slot, t))

    def test_loops_close_and_travel_is_unchanged(self):
        for slot, speed in SPEEDS.items():
            frames = self.new[slot]
            ticks = len(frames) - 1
            self.assertAlmostEqual((frames[0][0][8] - frames[-1][0][8]) / ticks, speed, delta=0.1, msg=slot)
        for slot in range(5):
            self.assertEqual([f[0] for f in self.new[slot]], [f[0] for f in self.old[slot]], slot)
            frames = self.new[slot]
            self.assertEqual(len(frames), len(self.old[slot]))
            for bone in range(self.nb):
                for c in range(3, 9):
                    gap = abs(frames[-1][bone][c] - frames[0][bone][c]) % 4096
                    old_gap = abs(self.old[slot][-1][bone][c] - self.old[slot][0][bone][c]) % 4096
                    if slot in gen.SLOTS:
                        self.assertLessEqual(min(gap, 4096 - gap), max(1, min(old_gap, 4096 - old_gap)), (slot, bone, c))

    def test_only_the_swaying_bones_change(self):
        for slot in range(5):
            a, b = self.old[slot], self.new[slot]
            for t in range(len(a)):
                for bone in range(self.nb):
                    if bone in MOVED and slot in gen.SLOTS:
                        continue
                    self.assertEqual(a[t][bone], b[t][bone], (slot, t, bone))
            if slot not in gen.SLOTS:
                self.assertEqual(self.old_model.anims.table[slot] is None, self.model.anims.table[slot] is None)
        self.assertEqual(self.old_model.tmd.build(), self.model.tmd.build())

    def test_no_jump_between_two_ticks(self):
        for slot in gen.SLOTS:
            frames = self.new[slot]
            for t in range(len(frames) - 1):
                for bone in MOVED:
                    step = _degrees(frames[t][bone], frames[t + 1][bone])
                    self.assertLess(step, 90 if bone in gen.LEG_BONES else 16, (slot, t, bone))

    def test_the_stride_no_longer_repeats_exactly_at_half_a_loop(self):
        # the imported walk replayed one 16-tick stride twice (80 degrees apart on the chest, tail and head)
        for slot in (2, 3, 4):
            frames = self.new[slot]
            ticks = len(frames) - 1
            apart = max(_degrees(frames[t][bone], frames[(t + ticks // 2) % ticks][bone])
                        for t in range(ticks) for bone in (gen.CHEST, gen.HEAD, 12, 13, 14))
            self.assertGreater(apart, 8, slot)

    def _positions(self, frames, bone):
        out = []
        for pose in frames[:-1]:
            q = [list(x) for x in pose]
            q[0] = [4096] * 3 + [0] * 6
            out.append(retarget.world_pos(self.skeleton, q)[bone])
        return out

    def test_the_spine_flexes_and_the_body_bounces(self):
        # per clip: the chest's pitch range (degrees) and the chest's height range (units), at least
        least = {2: (8, 8), 3: (4, 4), 4: (14, 24)}
        for slot, (flex, bounce) in least.items():
            frames = self.new[slot]
            pitch = [math.degrees(math.asin(-retarget.world_rots(self.skeleton, [list(x) for x in f])[gen.CHEST][1][2]))
                     for f in frames[:-1]]
            self.assertGreater(max(pitch) - min(pitch), flex, slot)
            heights = [-p[1] for p in self._positions(frames, gen.CHEST)]
            self.assertGreater(max(heights) - min(heights), bounce, slot)

    def test_the_run_is_a_bound_with_a_suspension(self):
        frames = self.new[4]
        paws = {b: self._positions(frames, b) for b in (7, 10, 18, 22)}
        ground = {b: max(p[1] for p in paws[b]) for b in paws}
        airborne = [t for t in range(len(paws[7])) if all(ground[b] - paws[b][t][1] > 8 for b in paws)]
        self.assertGreaterEqual(len(airborne), 9)                      # three ticks of every 14
        # the walks never leave the ground
        for slot in (2, 3):
            paws = {b: self._positions(self.new[slot], b) for b in (7, 10, 18, 22)}
            ground = {b: max(p[1] for p in paws[b]) for b in paws}
            for t in range(len(paws[7])):
                self.assertGreaterEqual(sum(ground[b] - paws[b][t][1] < 12 for b in paws), 1, (slot, t))

    def test_the_feet_do_not_slide_more_than_the_clips_did(self):
        for slot, speed in SPEEDS.items():
            worst = {}
            for name, frames in (('old', self.old[slot]), ('new', self.new[slot])):
                top = 0
                for b in (7, 10, 18, 22):
                    paw = self._positions(frames, b)
                    ground = max(p[1] for p in paw)
                    for t in range(len(paw)):
                        a, c = paw[t], paw[(t + 1) % len(paw)]
                        if a[1] > ground - 6 and c[1] > ground - 6:
                            top = max(top, abs(math.hypot(c[0] - a[0], c[2] - a[2]) - speed))
                worst[name] = top
            self.assertLessEqual(worst['new'], worst['old'] + 1, slot)

    def test_inside_the_resident_buffer(self):
        report = motionstorage.require(self.final_bytes, self.nb)
        self.assertLess(report['resident_bytes'], 100352)


if __name__ == '__main__':
    unittest.main()
