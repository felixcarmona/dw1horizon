"""Decoded checks for the reviewed locomotion and sword-attack artifacts."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
import animsheet
import mmd
import motionstorage
from motiondiscidentity import changed_programs
from motiontailspace import interpolate_pose
from tools.models.field_animations.native_polish import proportions
from tools.models.resize import resize

ARTIFACTS = Path(os.environ.get('POLISH_MODELS', ROOT / 'build/polish'))


class NativePolish(unittest.TestCase):
    def test_reviewed_locomotion(self):
        if not (ARTIFACTS / 'effective/297.MMD').is_file():
            self.skipTest('Set POLISH_MODELS to the reviewed before/after artifact directory')
        for path in sorted((ROOT / 'content/models/authoring/native-polish').glob('*.json')):
            cfg = json.loads(path.read_text())
            sid, sk = cfg['species'], cfg['skeleton']
            with self.subTest(species=sid):
                mmd.exe().add_type(sid, sk)
                source = (ARTIFACTS / f'effective/{sid}.MMD').read_bytes()
                output = (ARTIFACTS / f'after/{sid}.MMD').read_bytes()
                self.assertEqual(hashlib.sha256(source).hexdigest(), cfg['source_sha256'])
                self.assertEqual(hashlib.sha256(output).hexdigest(), cfg['output_sha256'])
                expected = proportions(source, sk, cfg) if cfg.get('local_scales') else source
                if cfg.get('resize'):
                    expected = resize(expected, len(sk), cfg['resize'])
                old = mmd.MMD.parse(expected, len(sk)); old.type = sid
                new = mmd.MMD.parse(output, len(sk)); new.type = sid
                self.assertEqual(old.tmd.build(), new.tmd.build())
                self.assertEqual(changed_programs(old, new), cfg.get('slots', [2, 3, 4]))
                self.assertTrue(motionstorage.require(output, len(sk))['fits'])
                for slot in cfg.get('slots', [2, 3, 4]):
                    frames, loop, _ = animsheet.slot_frames(new, len(sk), slot)
                    self.assertEqual(loop, 0)
                    for a, b in zip(frames[0][1:], frames[-1][1:]):
                        self.assertEqual(a[:3]+a[6:], b[:3]+b[6:])
                        self.assertEqual([v % 4096 for v in a[3:6]], [v % 4096 for v in b[3:6]])
                    player = mmd.AnimPlayer(new.anims.anims[new.anims.table[slot]], len(sk), slot)
                    cycle = []
                    for tick in range((len(frames)-1)*9):
                        self.assertTrue(player.tick())
                        pose = [b[:3]+[v % 4096 for v in b[3:6]]+b[6:] for b in player.pose[1:]]
                        if tick < len(frames)-1:
                            cycle.append(copy.deepcopy(pose))
                        else:
                            self.assertEqual(pose, cycle[tick % (len(frames)-1)])
                    speed = -(frames[-1][0][8]-frames[0][0][8])/(len(frames)-1)
                    self.assertGreaterEqual(speed, 35 if slot == 4 else 9.5)
                    self.assertLessEqual(speed, 52)
                    worst = -float('inf')
                    for a, b in zip(frames, frames[1:]):
                        for blend in (0, 1365, 2730, 4096):
                            pose = interpolate_pose(a, b, blend)
                            pose[0] = [4096]*3+[0]*6
                            world = mmd.bone_matrices(new, pose)
                            for foot in cfg['feet']:
                                matrix = world[foot]
                                for vertex in new.tmd.obj_verts(sk[foot][0]):
                                    worst = max(worst, sum(matrix[1][j]*vertex[j] for j in range(3))+matrix[1][3])
                    self.assertLessEqual(worst, 1.5)

    def test_sword_attack_keeps_body_and_events(self):
        path = ARTIFACTS / 'effective/461.MMD'
        if not path.is_file():
            self.skipTest('Set POLISH_MODELS to the reviewed before/after artifact directory')
        from tools.models.repair_omnimon_attack import repair, SLOTS
        old = mmd.MMD.load(str(path), 461)
        output = repair(path.read_bytes(), mmd.exe().skeleton[461])
        self.assertEqual(output, (ARTIFACTS / 'after/461.MMD').read_bytes())
        new = mmd.MMD.parse(output, 25); new.type = 461
        self.assertEqual(changed_programs(old, new), list(SLOTS))
        for slot in SLOTS:
            before, loop, events = animsheet.slot_frames(old, 25, slot)
            after, new_loop, new_events = animsheet.slot_frames(new, 25, slot)
            self.assertEqual((len(before), loop, events), (len(after), new_loop, new_events))
            for a, b in zip(before, after):
                for bone in set(range(25))-{3, 4, 9, 10}:
                    self.assertEqual(a[bone], b[bone])
                self.assertEqual(b[9][3:6], before[0][9][3:6])
            self.assertGreater(len({tuple(p[3][3:6]) for p in after}), 5)


if __name__ == '__main__':
    unittest.main()
