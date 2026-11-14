"""The care clip QA (tools/models/care_qa.py) catches each defect it is for, and the condition idle generator
(tools/models/field_animations/care_idles.py) keeps what it must keep.

The synthetic tests build a small four-legged rig (a body box on four leg boxes, a head on a neck, a tail) with a field
idle, a walk and a tired walk, and give it condition idles with one defect each: the field idle itself, a clip too long
for the condition timer, a body sunk into the floor, a loop that does not close. CARE_QA_MODELS names a folder of real
models (ID.C.MMD the final model of this tree, ID.A.MMD its importer output, ID.main.MMD origin/main's final model);
with it every species there must have no failing slot, else it skips."""
import glob
import json
import os
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools'), str(ROOT / 'tools' / 'models')]
from tools.models import battle_qa as bq  # noqa: E402
from tools.models import care_qa as qa  # noqa: E402
from tools.models.field_animations import care_idles  # noqa: E402
from tools.test_battle_qa import box  # noqa: E402

TURN = 4096 / 360.0
LEGS = {2: (80, -100), 3: (-80, -100), 4: (80, 100), 5: (-80, 100)}
NECK, HEAD, TAIL = 6, 7, 8
PARENTS = [-1, 0, 1, 1, 1, 1, 1, 6, 1]
TICKS = 24


def rig_parts():
    pieces = [(1, box(-100, 100, -50, 50, -150, 150)), (NECK, box(-20, 20, -80, 0, -20, 20)),
              (HEAD, box(-40, 40, -60, 0, -90, 10)), (TAIL, box(-10, 10, -10, 10, 0, 160))]
    pieces += [(b, box(-15, 15, 0, 150, -15, 15)) for b in LEGS]
    local, tris = {}, []
    for bone, piece in pieces:
        local[bone] = piece[0]
        tris += [(bone, t) for t in piece[1]]
    return local, tris


def clip(swing=0.0, breath=2.0, head=0.0, drop=0.0, ticks=TICKS, open_end=False):
    """(frames, loop): the legs swing `swing` degrees, the neck breathes `breath` degrees, the head pitched `head`
    degrees, the body `drop` units down; `open_end` leaves the last tick off the first pose."""
    f = np.zeros((ticks + 1, len(PARENTS), 9))
    f[..., 0:3] = 4096
    f[:, 1, 6:9] = (0, -200 + drop, 0)
    f[:, NECK, 6:9] = (0, -50, -150)
    f[:, HEAD, 6:9] = (0, -80, 0)
    f[:, TAIL, 6:9] = (0, -20, 150)
    t = np.arange(ticks + 1) / ticks
    f[:, NECK, 3] = breath * TURN * np.sin(2 * np.pi * t)
    f[:, TAIL, 4] = 20 * TURN * np.sin(2 * np.pi * t)
    f[:, HEAD, 3] = head * TURN
    for b, (x, z) in LEGS.items():
        f[:, b, 6:9] = (x, 50, z)
        f[:, b, 3] = swing * TURN * np.sin(2 * np.pi * t + (0 if b in (2, 5) else np.pi))
    if open_end:
        f[-1, HEAD, 3] += 30 * TURN
    return np.round(f), 0


def rig(cond):
    local, tris = rig_parts()
    clips = {0: clip(), 2: clip(25), 3: clip(15)}
    clips.update(cond)
    return bq.Rig(PARENTS, local, tris, clips)


def run(final, main=None):
    main = main or {1: clip(breath=1.0, head=40)}
    return qa.check(rig(final), rig(final), rig(main), slots=tuple(final))


class SyntheticDefects(unittest.TestCase):
    def test_distinct_idle_passes(self):
        rows = run({1: clip(head=35, breath=4)})
        self.assertEqual(rows[1]['verdict'], 'pass', rows[1]['flags'])

    def test_field_idle_copy_flagged(self):
        rows = run({1: clip()})
        self.assertIn('distinct', rows[1]['keys'])
        self.assertEqual(rows[1]['verdict'], 'fail')

    def test_copy_on_main_is_reported_not_failed(self):
        rows = run({1: clip()}, main={1: clip()})
        self.assertEqual(rows[1]['verdict'], 'main')

    def test_timer_wrap_flagged(self):
        rows = run({18: clip(head=35, ticks=130)}, main={18: clip(head=40, ticks=40)})
        self.assertIn('length', rows[18]['keys'])

    def test_slot_1_longer_than_main_flagged(self):
        rows = run({1: clip(head=35, ticks=60)}, main={1: clip(head=40, ticks=TICKS)})
        self.assertIn('length', rows[1]['keys'])

    def test_sunk_body_flagged(self):
        rows = run({14: clip(head=35, drop=200)}, main={14: clip(head=40)})
        self.assertIn('sink', rows[14]['keys'])
        self.assertEqual(rows[14]['verdict'], 'fail')

    def test_open_loop_flagged(self):
        rows = run({17: clip(head=35, open_end=True)}, main={17: clip(head=40)})
        self.assertIn('seam', rows[17]['keys'])

    def test_close_pair_flagged(self):
        rows = run({14: clip(head=35), 15: clip(head=36)}, main={14: clip(head=40), 15: clip(head=50)})
        self.assertIn('pair', rows[14]['keys'])

    def test_importer_on_another_skeleton_is_not_compared(self):
        # a native binding's importer output has the source's skeleton: its body bones are not the final's, so its
        # posture explains nothing (the same clip on the same skeleton is the source's posture, noted)
        f, _ = clip(head=35)
        f[:, 1, 3] = 70 * TURN
        main = rig({14: clip(head=40)})
        same = qa.check(rig({14: (f, 0)}), rig({14: (f, 0)}), main, slots=(14,))
        self.assertEqual(same[14]['keys'], [])
        local, tris = rig_parts()
        extra = lambda g: np.concatenate([g, g[:, :1]], axis=1)  # noqa: E731
        other = bq.Rig(PARENTS + [1], local, tris, {0: (extra(clip()[0]), 0), 14: (extra(f), 0)})
        rows = qa.check(rig({14: (f, 0)}), other, main, slots=(14,))
        self.assertIn('body_off', rows[14]['keys'])


class Generator(unittest.TestCase):
    ROW = dict(body='quadruped', keep=[0, 1, 2, 3, 4, 5], lean=[NECK], head=[HEAD],
               droop={str(TAIL): [0.0, 0.0, 160.0]})

    def samples(self):
        f, _ = clip()
        return [[list(map(int, b)) for b in tick] for tick in f]

    def test_keeps_legs_scale_translation_and_closes(self):
        src = self.samples()
        for cond in care_idles.CONDITIONS:
            out = care_idles.condition_clip(src, PARENTS, self.ROW, cond)
            self.assertEqual(out[0], out[-1], cond)
            for t, (a, b) in enumerate(zip(src, out)):
                for bone in self.ROW['keep']:
                    self.assertEqual(a[bone], b[bone], (cond, t, bone))
                for bone in range(len(PARENTS)):
                    self.assertEqual(a[bone][0:3] + a[bone][6:9], b[bone][0:3] + b[bone][6:9], (cond, t, bone))

    def test_head_goes_down(self):
        local, tris = rig_parts()
        src = self.samples()
        for cond in ('tired', 'hungry', 'unhappy'):
            out = np.array(care_idles.condition_clip(src, PARENTS, self.ROW, cond), float)
            r = bq.Rig(PARENTS, local, tris, {0: (np.array(src, float), 0), 1: (out, 0)})
            y0 = bq.Clip(r, *r.frames(0)).V[HEAD][:, :, 1].mean()
            y1 = bq.Clip(r, *r.frames(1)).V[HEAD][:, :, 1].mean()
            self.assertGreater(y1, y0 + 10, cond)         # y is down

    def test_tame_narrows_only_the_named_bone(self):
        src = self.samples()
        out = care_idles.tame(src, {TAIL: 0.5})
        swing = lambda poses: max(p[TAIL][4] for p in poses) - min(p[TAIL][4] for p in poses)  # noqa: E731
        self.assertAlmostEqual(swing(out), swing(src) / 2, delta=2)
        self.assertEqual(out[0], out[-1])
        for a, b in zip(src, out):
            self.assertEqual([x for i, x in enumerate(a) if i != TAIL], [x for i, x in enumerate(b) if i != TAIL])

    def test_condition_idles_pass_qa(self):
        local, tris = rig_parts()
        src = self.samples()
        clips = {0: (np.array(src, float), 0), 2: clip(25), 3: clip(15)}
        for s, cond in care_idles.DEFAULT.items():
            clips[s] = (np.array(care_idles.condition_clip(src, PARENTS, self.ROW, cond, 1.7), float), 0)
        final = bq.Rig(PARENTS, local, tris, clips)
        main = rig({s: clip() for s in care_idles.DEFAULT})
        rows = qa.check(final, final, main, slots=tuple(care_idles.DEFAULT))
        bad = {s: r['flags'] for s, r in rows.items() if r['verdict'] == 'fail' and set(r['keys']) - {'pair'}}
        self.assertEqual(bad, {})


MODELS = os.environ.get('CARE_QA_MODELS')


@unittest.skipUnless(MODELS and os.path.isdir(MODELS), 'CARE_QA_MODELS names no folder of models')
class RealModels(unittest.TestCase):
    def test_no_failing_slot(self):
        for path in sorted(glob.glob(os.path.join(MODELS, '*.C.MMD'))):
            sid = os.path.basename(path).split('.')[0]
            species = glob.glob(str(ROOT / f'content/species/{sid}-*.json'))[0]
            bones = json.loads(Path(species).read_text())['model']['skeleton']
            rd = lambda p: Path(p).read_bytes() if os.path.exists(p) else None  # noqa: E731
            main = rd(os.path.join(MODELS, f'{sid}.main.MMD')) or rd(path)
            rows = qa.species_check(rd(path), rd(os.path.join(MODELS, f'{sid}.A.MMD')), main, bones)
            with self.subTest(species=sid):
                self.assertEqual(qa.failing(rows), [], {s: rows[s] for s in qa.failing(rows) if s != 'buffer'})

    def test_share_and_compact_rows(self):
        # a row's `share` points a slot at another slot's program, `compact` re-encodes the rest exactly
        import animsheet
        import mmd
        for path in sorted(glob.glob(os.path.join(MODELS, '*.C.MMD'))):
            sid = os.path.basename(path).split('.')[0]
            species = glob.glob(str(ROOT / f'content/species/{sid}-*.json'))[0]
            bones = json.loads(Path(species).read_text())['model']['skeleton']
            data = Path(path).read_bytes()
            row = {'slots': {}, 'share': {'1': 14}, 'compact': True}
            out, report = care_idles.apply(data, bones, row)
            before, after = mmd.MMD.parse(data, len(bones)), mmd.MMD.parse(out, len(bones))
            with self.subTest(species=sid):
                self.assertEqual(report[1], {'shares': 14})
                self.assertEqual(after.anims.table[1], after.anims.table[14])
                for slot, index in enumerate(before.anims.table):
                    if index is not None and slot != 1:
                        self.assertEqual(animsheet.slot_frames(before, len(bones), slot),
                                         animsheet.slot_frames(after, len(bones), slot))
            break


if __name__ == '__main__':
    unittest.main()
