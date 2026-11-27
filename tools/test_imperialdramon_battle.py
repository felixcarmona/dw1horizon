"""Imperialdramon's source tired idle with eased wing tips."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools'), str(ROOT / 'tools/models')]
import numpy as np
import animsheet
import mmd
import battle_qa as qa
import battle_qa_native as native
from tools.battle_retry_testcase import BattleRetryCase


class ImperialdramonBattle(BattleRetryCase):
    sid = 192
    changed_slots = (34,)

    def test_wing_motion_and_source_fidelity(self):
        review = os.environ.get('BATTLE_RETRY_REVIEW')
        if not review:
            self.skipTest('needs before/after provider fixtures')
        review = Path(review)
        sk = json.loads((review / 'main/192-species.json').read_text())['model']['skeleton']
        before, final, source = [(review / part / name).read_bytes() for part, name in
                                 [('main', '192.C.MMD'), ('final', '192.C.MMD'), ('main', '192.A.MMD')]]
        rows = qa.species_check(final, source, before, sk, [34], [34])
        self.assertEqual(rows[34]['flags'], [])
        self.assertLessEqual(rows[34]['final']['jump'], qa.JUMP_MAX[0])
        nb = len(sk)
        original, result = [mmd.MMD.parse(data, nb) for data in (before, final)]
        old, old_loop, old_events = animsheet.slot_frames(original, nb, 34)
        new, loop, events = animsheet.slot_frames(result, nb, 34)
        self.assertEqual((len(new), loop, events), (len(old), old_loop, old_events))
        for a, b in zip(old, new):
            for bone in range(nb):
                self.assertEqual(a[bone][:3] + a[bone][6:], b[bone][:3] + b[bone][6:])
                if bone not in (6, 7, 8, 9, 10):
                    self.assertLessEqual(max(abs((x-y+2048) % 4096-2048)
                                             for x, y in zip(a[bone][3:6], b[bone][3:6])), 1)
        F, A, M = [qa.Rig.from_mmd(data, sk) for data in (final, source, before)]
        src_model = mmd.MMD.parse(source, nb)
        blocks, fit = {}, {}
        for bone, (obj, _) in enumerate(sk):
            if obj < 0:
                continue
            vertices = np.asarray(src_model.tmd.obj_verts(obj), float)[:, :3]
            dest = F.local[bone]
            blocks[bone] = (bone, slice(0, len(vertices)))
            fit[bone] = (np.eye(3), float(((dest-dest.mean(0)) ** 2).sum())+1, dest, vertices)
        parents = [parent for _, parent in sk]
        hips = min(blocks, key=lambda bone: len(native._chain(parents, bone)))
        poses = F.frames(34)[0]
        expected = qa.retimed_baseline(A.frames(34)[0], 34, len(poses))
        fidelity = native.fidelity(native.body_world(poses, parents), native.body_world(expected, parents),
                                   fit, blocks, set(blocks), native.tips(sk), (hips, hips),
                                   (qa.reference(A)['h'], qa.reference(M)['h']))
        self.assertLessEqual(fidelity['rot_mean'], native.FID_MEAN)
        self.assertLessEqual(fidelity['rot_worst_piece'][0], native.FID_PIECE)
        self.assertLessEqual(fidelity['tip'], native.FID_TIP)
