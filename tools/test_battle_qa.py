"""The battle clip QA (tools/models/battle_qa.py) catches each defect it is for and passes a sound clip.

The synthetic tests build a small four-legged rig (a body box on four leg boxes) with a field idle, a walk and a run, and
give it battle clips with one defect each: front legs left without a bone map, a leg piece off the body, a torso tipped
back. BATTLE_QA_MODELS names a folder of real models (ID.C.MMD the final model of this tree, ID.A.MMD its importer
output, ID.main.MMD origin/main's final model); with it every species there must have no failing slot, else it skips."""
import glob
import json
import os
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools'), str(ROOT / 'tools' / 'models')]
from tools.models import battle_qa as qa  # noqa: E402

TURN = 4096 / 360.0                      # angle units a degree
LEGS = {2: (80, -100), 3: (-80, -100), 4: (80, 100), 5: (-80, 100)}   # bone: (x, z) under the body; 2, 3 the front
PARENTS = [-1, 0, 1, 1, 1, 1]
TICKS = 16


def box(x0, x1, y0, y1, z0, z1):
    v = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return v, [t for a, b, c, d in faces for t in ((a, b, c), (a, c, d))]


def rig_parts():
    local, tris = {}, []
    for bone, piece in [(1, box(-100, 100, -50, 50, -150, 150))] + [(b, box(-15, 15, 0, 150, -15, 15)) for b in LEGS]:
        local[bone] = piece[0]
        tris += [(bone, t) for t in piece[1]]
    return local, tris


def clip(swing=0.0, still=(), body_pitch=0.0, push=None, ticks=TICKS):
    """(frames, loop): the legs swing `swing` degrees out of phase (bones in `still` do not), the body pitched by
    `body_pitch` degrees, `push` = (bone, x units) moves one leg out sideways at the middle ticks."""
    f = np.zeros((ticks + 1, len(PARENTS), 9))
    f[..., 0:3] = 4096
    f[:, 1, 6:9] = (0, -200, 0)
    f[:, 1, 3] = body_pitch * TURN
    for b, (x, z) in LEGS.items():
        f[:, b, 6:9] = (x, 50, z)
        if b not in still:
            phase = 0 if b in (2, 5) else np.pi
            f[:, b, 3] = swing * TURN * np.sin(2 * np.pi * np.arange(ticks + 1) / ticks + phase)
    if push:
        f[ticks // 4: 3 * ticks // 4, push[0], 6] += push[1]
    return np.round(f), 0


def rig(battle, field_swing=30.0):
    local, tris = rig_parts()
    clips = {0: clip(), 2: clip(field_swing), 4: clip(field_swing * 1.3, ticks=10)}
    clips.update(battle)
    return qa.Rig(PARENTS, local, tris, clips)


def sound():
    return {33: clip(4), 34: clip(6), 35: clip(25), 36: clip(35, ticks=12)}


def quiet(body_pitch=0.0):
    """Main's battle clips: barely moving, the movements as long as the sound ones (technique timing)."""
    return {s: clip(2, body_pitch=body_pitch, ticks=12 if s == 36 else TICKS) for s in qa.BATTLE}


def run(final, base=None, main=None):
    return qa.check(rig(final), rig(base or final), rig(main or quiet()))


class SyntheticDefects(unittest.TestCase):
    def test_sound_clips_pass(self):
        rows = run(sound())
        self.assertEqual({s: r['verdict'] for s, r in rows.items()}, {s: 'pass' for s in qa.BATTLE}, rows)

    def test_main_clip_is_main(self):
        rows = run(sound(), main=sound())
        self.assertTrue(all(r['source'] == 'main' for r in rows.values()))

    def test_front_legs_without_bone_map(self):
        # the source clip itself leaves the front legs still (no bone map for them): the field gait rule catches it
        bad = {**sound(), 35: clip(25, still=(2, 3)), 36: clip(35, still=(2, 3), ticks=12)}
        rows = run(bad)
        for s in (35, 36):
            self.assertIn('live_field', rows[s]['keys'], rows[s]['flags'])
            self.assertEqual(rows[s]['verdict'], 'fail')
        # against a baseline whose front legs move, the baseline rule catches it too
        rows = run(bad, base=sound())
        self.assertIn('live_base', rows[35]['keys'], rows[35]['flags'])

    def test_piece_leaves_the_body(self):
        rows = run({**sound(), 34: clip(6, push=(2, 80))}, base=sound())
        self.assertIn('tear', rows[34]['keys'], rows[34]['flags'])
        self.assertEqual((rows[34]['cause'], rows[34]['verdict']), ('rig', 'fail'))
        self.assertEqual(rows[33]['verdict'], 'pass')

    def test_torso_tipped_back(self):
        rows = run({**sound(), 34: clip(6, body_pitch=30)})
        self.assertIn('body_off', rows[34]['keys'], rows[34]['flags'])
        self.assertEqual((rows[34]['cause'], rows[34]['verdict']), ('source', 'fail'))
        # beyond any native clip it is flagged even when main is as tipped; no worse than main, it is kept
        rows = run({**sound(), 34: clip(6, body_pitch=65)}, main=quiet(65))
        self.assertIn('body_off', rows[34]['keys'], rows[34]['flags'])
        self.assertEqual(rows[34]['verdict'], 'kept')

    def test_fidelity(self):
        rows = run({**sound(), 33: clip(20)}, base=sound())
        self.assertIn('fidelity', rows[33]['keys'], rows[33]['flags'])


@unittest.skipUnless(os.environ.get('BATTLE_QA_MODELS'), 'BATTLE_QA_MODELS names no folder of real models')
class RealModels(unittest.TestCase):
    def test_no_failing_slot(self):
        folder = Path(os.environ['BATTLE_QA_MODELS'])
        ids = sorted(p.name.split('.')[0] for p in folder.glob('*.C.MMD'))
        self.assertTrue(ids)
        for sid in ids:
            with self.subTest(species=sid):
                bones = json.loads(Path(glob.glob(str(ROOT / f'content/species/{sid}-*.json'))[0]).read_text())
                rd = lambda kind: (folder / f'{sid}.{kind}.MMD').read_bytes()
                rows = qa.species_check(rd('C'), rd('A'), rd('main'), bones['model']['skeleton'],
                                        polished=qa.polished_slots(int(sid)))
                self.assertEqual([s for s, r in rows.items() if r['verdict'] == 'fail'], [],
                                 {s: r['flags'] for s, r in rows.items()})


if __name__ == '__main__':
    unittest.main()
