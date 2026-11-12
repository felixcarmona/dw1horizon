"""Taomon's sleeves against its legs, aprons and tail, tick by tick, in the idle, walk, tired walk and run.

Needs `tools/models/edit.py get 315` (build/imported-model-edit/edit/315-Taomon.MMD); skipped when it is absent. The
final model is made as the build makes it: the importer's model through the equipment overlay and the chibi overlay.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet
import mmd
import motionstorage
from tools.models.field_animations import chibi
from tools.models.field_animations import okuwamon_limbs as ok
from tools.models.field_animations import taomon_arms as arms
from tools.models.field_animations.meshclash import Clash

SOURCE = ROOT / 'build/imported-model-edit/edit/315-Taomon.MMD'
SLEEVE = {'R': (20, 21, 22), 'L': (25, 26, 27)}
GROUPS = {'leg': arms.MUST_CLEAR['leg'], 'apron': arms.MUST_CLEAR['apron'], 'tail': arms.MUST_CLEAR['tail']}
SLOTS = (0, 2, 3, 4)
LIMIT = 100352
# Before this change (summed over a clip's ticks): the sleeves' triangle pairs against the legs.
BEFORE_LEG_PAIRS = {0: 142, 2: 1370, 3: 1037, 4: 486}   # incl. the thighs' tops
MAX_TURN_STEP = 8           # degrees from one tick to the next, outward or back


class TaomonArms(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SOURCE.exists():
            raise unittest.SkipTest('reconstruct with tools/models/edit.py get 315')
        cls.sk = json.loads(next((ROOT / 'content/species').glob('315-*.json')).read_text())['model']['skeleton']
        data = SOURCE.read_bytes()
        chibi._register(315, cls.sk)
        cls.final, cls.proof = chibi.build(data, cls.sk)
        rows = json.loads(chibi.MANIFEST.read_text())
        rows['315'].pop('post_generator')
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / 'chibi.json'
            manifest.write_text(json.dumps(rows))
            saved, chibi.MANIFEST = chibi.MANIFEST, manifest
            try:
                cls.before, _ = chibi.build(data, cls.sk)
            finally:
                chibi.MANIFEST = saved
        cls.model = arms.parse(cls.final, cls.sk)
        cls.old = arms.parse(cls.before, cls.sk)
        cls.clash = Clash(cls.model, cls.sk)
        cls.body = ok.Body(cls.model, cls.sk)
        oldclash = Clash(cls.old, cls.sk)
        cls.old_leg_depth = {slot: [{arm: oldclash.clash(p, parts, GROUPS['leg'], world=oldclash.world(p))[1] for arm, parts in SLEEVE.items()}
                                    for p in animsheet.slot_frames(cls.old, arms.NB, slot)[0][:-1]] for slot in SLOTS}
        cls.old_depth = {slot: [{arm: oldclash.clash(p, parts, arms.THIGH_TOP, world=oldclash.world(p))[1] for arm, parts in SLEEVE.items()}
                                for p in animsheet.slot_frames(cls.old, arms.NB, slot)[0][:-1]] for slot in SLOTS}

    def frames(self, model, slot):
        return animsheet.slot_frames(model, arms.NB, slot)[0]

    def test_pre_change_input_is_the_reviewed_one(self):
        self.assertEqual(hashlib.sha256(self.before).hexdigest(), arms.SOURCE)

    def test_no_sleeve_goes_through_a_leg_apron_or_tail_on_any_tick(self):
        for slot in SLOTS:
            for t, pose in enumerate(self.frames(self.model, slot)[:-1]):
                world = self.clash.world(pose)
                mats, vertices = self.body.world(pose)
                for arm, parts in SLEEVE.items():
                    top, _ = self.clash.clash(pose, parts, arms.THIGH_TOP, world=world)
                    for name, bones in GROUPS.items():
                        pairs, depth = self.clash.clash(pose, parts, bones, world=world)
                        if name == 'leg' and top:               # the shoulder is inside the thigh's top: no turn can clear the leg here
                            self.assertLessEqual(depth, self.old_leg_depth[slot][t][arm] + .5, f'slot {slot} tick {t} {arm}')
                            continue
                        self.assertEqual(pairs, 0, f'slot {slot} tick {t} {arm} sleeve into {name}: {pairs} pairs, {depth:.1f} deep')
                        self.assertEqual(self.body.count(mats, vertices, parts, bones), 0, f'slot {slot} tick {t} {arm} {name}')
                    pairs, depth = self.clash.clash(pose, parts, arms.THIGH_TOP, world=world)       # the thighs' tops
                    old = self.old_depth[slot][t][arm]
                    self.assertTrue(pairs == 0 or depth <= old + .5, f'slot {slot} tick {t} {arm} thigh top {depth:.1f} (was {old:.1f})')

    def test_it_was_a_real_problem_before(self):
        for slot, expected in BEFORE_LEG_PAIRS.items():
            total = 0
            clash = Clash(self.old, self.sk)
            for pose in self.frames(self.old, slot)[:-1]:
                world = clash.world(pose)
                total += sum(clash.clash(pose, parts, GROUPS['leg'] + arms.THIGH_TOP, world=world)[0] for parts in SLEEVE.values())
            self.assertEqual(total, expected, slot)

    def test_sleeves_only_brush_the_body(self):
        for slot in SLOTS:
            for t, (a, b) in enumerate(zip(self.frames(self.old, slot)[:-1], self.frames(self.model, slot)[:-1])):
                wa, wb = Clash(self.old, self.sk).world(a), self.clash.world(b)
                for arm, parts in SLEEVE.items():
                    for name, bones in (('body', arms.KEEP['body']),):
                        pa, da = Clash(self.old, self.sk).clash(a, parts, bones, world=wa)
                        pb, db = self.clash.clash(b, parts, bones, world=wb)
                        self.assertLessEqual(db, max(da, arms.BODY_DEPTH) + .01, f'slot {slot} tick {t} {arm} {name}')

    def test_only_the_two_sleeve_bones_rotation_changed(self):
        bones = {arms.ARMS[a]['bone'] for a in arms.ARMS}
        for slot in SLOTS:
            a = np.array(self.frames(self.old, slot), float)
            b = np.array(self.frames(self.model, slot), float)
            self.assertEqual(a.shape, b.shape)
            diff = np.abs(a - b)
            for bone in range(a.shape[1]):
                if bone in bones:
                    self.assertTrue(diff[:, bone, :3].max() == 0 and diff[:, bone, 6:].max() == 0, (slot, bone))
                else:
                    self.assertEqual(diff[:, bone].max(), 0, (slot, bone))
        for slot in range(len(self.old.anims.table)):
            if slot not in (0, 2, 3, 4, 33):
                ia, ib = self.old.anims.table[slot], self.model.anims.table[slot]
                self.assertEqual(ia, ib)
                if ia is not None:
                    self.assertEqual(self.old.anims.anims[ia].build(), self.model.anims.anims[ib].build(), slot)
        self.assertEqual(self.model.tmd.build(), self.old.tmd.build())
        self.assertEqual(self.model.anims.table[33], self.model.anims.table[0])

    def test_the_turns_are_smooth_and_the_loops_close(self):
        turns = json.loads(arms.TURNS.read_text())
        for slot, sides in turns.items():
            for arm, series in sides.items():
                for key in ('outward', 'back'):
                    v = series[key]
                    self.assertLessEqual(max(v), (arms.COMFORT if key == 'outward' else arms.REACH) + arms.MARGIN + 1e-9)
                    self.assertGreaterEqual(min(v), 0)
                    steps = [abs(v[(i + 1) % len(v)] - v[i]) for i in range(len(v))]
                    self.assertLessEqual(max(steps), MAX_TURN_STEP, (slot, arm, key))
        for slot in SLOTS:
            frames = self.frames(self.model, slot)
            self.assertEqual([p[arms.ARMS['R']['bone']][3:6] for p in frames[:1]], [frames[-1][arms.ARMS['R']['bone']][3:6]])
            self.assertEqual([p[arms.ARMS['L']['bone']][3:6] for p in frames[:1]], [frames[-1][arms.ARMS['L']['bone']][3:6]])

    def test_no_new_jump_in_the_motion(self):
        def worst(model, slot):
            frames = self.frames(model, slot)[:-1]
            worlds = [Clash(model, self.sk).world(f) for f in frames]
            d = [float(np.linalg.norm(worlds[(i + 1) % len(worlds)] - worlds[i], axis=1).mean()) for i in range(len(worlds))]
            return max(d) / np.median(d)
        for slot in (2, 3, 4):
            self.assertLessEqual(worst(self.model, slot), max(2.5, worst(self.old, slot) + .05), slot)

    def test_storage_budget(self):
        report = motionstorage.audit(self.final, arms.NB)
        self.assertTrue(report['fits'])
        self.assertLess(report['resident_bytes'], LIMIT)


if __name__ == '__main__':
    unittest.main()
