"""Guard reviewed wings, active stepping and the native larval binding."""
import copy
import json
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'tools')]
import animsheet
import mmd
import retarget as R
from motiondiscidentity import changed_programs
from motiontailspace import interpolate_pose
from tools.models.field_animations import followthrough as F, native_binding

ART = ROOT/'build/gait-review6'


class FollowThrough(unittest.TestCase):
    def test_recipes_pin_only_three_reviewed_species(self):
        recipes = json.loads(F.MANIFEST.read_text())
        self.assertEqual(set(recipes), {'187', '239'})
        rows = {r['id']: r for r in json.loads((ROOT/'content/modeldelta/models.json').read_text())['models']}
        for key, cfg in recipes.items():
            self.assertEqual(cfg['source_sha256'], rows[int(key)]['mmd']['sha256'])
        worm = json.loads(native_binding.MANIFEST.read_text())['183']
        self.assertEqual(worm['source_sha256'], rows[183]['mmd']['sha256'])
        self.assertEqual((worm['donor'], worm['scale']), (32, .65))
        self.assertNotIn('preserve_bind_pose', worm)

    def models(self, sid):
        if not (ART/'prior').is_dir():
            self.skipTest('review source/target models required')
        cfg = json.loads(F.MANIFEST.read_text())[str(sid)]
        sk = cfg['skeleton']; mmd.exe().add_type(sid, sk)
        data = next((ART/'prior').glob(f'{sid}-*.MMD')).read_bytes()
        output, proof = F.build(data, sk)
        self.assertEqual(output, next((ART/'after').glob(f'{sid}-*.MMD')).read_bytes())
        self.assertTrue(proof['storage']['fits'])
        old, new = mmd.MMD.parse(data, len(sk)), mmd.MMD.parse(output, len(sk))
        old.type = new.type = sid
        return sk, old, new

    def test_wings_preserve_every_other_bone_and_program(self):
        sk, old, new = self.models(187)
        self.assertEqual(old.tmd.build(), new.tmd.build())
        self.assertEqual(changed_programs(old, new), [2, 3, 4])
        idle = animsheet.slot_frames(old, len(sk), 0)[0][0]
        for slot in (2, 3, 4):
            before, loop, events = animsheet.slot_frames(old, len(sk), slot)
            after, new_loop, new_events = animsheet.slot_frames(new, len(sk), slot)
            self.assertEqual((len(before), loop, events), (len(after), new_loop, new_events))
            changed = set()
            for a, b in zip(before, after):
                for bone in range(len(sk)):
                    self.assertEqual(a[bone][:3]+a[bone][6:], b[bone][:3]+b[bone][6:])
                    angular = max(abs((x-y+2048)%4096-2048) for x, y in zip(a[bone][3:6], b[bone][3:6]))
                    if angular > 1: changed.add(bone)
                    if bone not in (9, 10, 11, 12): self.assertLessEqual(angular, 1)
                    else:
                        self.assertEqual(sk[bone][1], 1)
                        self.assertLess(max(abs((x-y+2048)%4096-2048) for x,y in zip(idle[bone][3:6],b[bone][3:6])),950)
            self.assertEqual(changed, {9, 10, 11, 12})

    def test_larval_binding_retains_mesh_dimensions_and_texture_faces(self):
        if not (ART/'prior/183-Wormmon.MMD').is_file():
            self.skipTest('review source required')
        cfg = json.loads(native_binding.MANIFEST.read_text())['183']
        source_sk = json.loads(next((ROOT/'content/species').glob('183-*.json')).read_text())['model']['skeleton']
        data = (ART/'prior/183-Wormmon.MMD').read_bytes()
        output, proof = native_binding.bind(data, source_sk, cfg)
        self.assertEqual(output, (ART/'after/183-Wormmon.MMD').read_bytes())
        old, new = mmd.MMD.parse(data, len(source_sk)), mmd.MMD.parse(output, 28)
        used = {}
        for sb, tb in cfg['map'].items():
            source = old.tmd.objects[source_sk[int(sb)][0]]
            target = new.tmd.objects[proof['generated_skeleton'][tb][0]]
            nv, np = used.get(tb, (0, 0))
            before = old.tmd.obj_verts(source_sk[int(sb)][0])
            after = new.tmd.obj_verts(proof['generated_skeleton'][tb][0])[nv:nv+len(before)]
            # Binding changes pivots and orientation, not the reduced surface
            # dimensions. A second resize would fail every edge comparison.
            for a, b in zip(before[1:], after[1:]):
                self.assertAlmostEqual(math.dist(a[:3], before[0][:3]), math.dist(b[:3], after[0][:3]), delta=2)
            for a, b in zip(source.prims, target.prims[np:np+len(source.prims)]):
                expected, actual = a.decode(), b.decode()
                for key in ('uv', 'cba', 'tsb', 'colors'):
                    self.assertEqual(expected.get(key), actual.get(key))
            used[tb] = nv+len(before), np+len(source.prims)
        old.type, new.type = 183, 32  # native parent order, with the bound mesh mapping below
        extents = []
        for model, rig in ((old, source_sk), (new, proof['generated_skeleton'])):
            pose = animsheet.slot_frames(model, len(rig), 0)[0][0]
            pose[0] = [4096]*3+[0]*6
            points = [v for triangle in animsheet.world_tris(model, pose, rig) for v in triangle[0]]
            extents.append([max(v[i] for v in points)-min(v[i] for v in points) for i in range(3)])
        for source, bound in zip(*extents):
            self.assertGreater(bound/source, .8)
            self.assertLess(bound/source, 1.15)

    def test_amphibian_steps_bobs_and_keeps_sleep_and_combat(self):
        sk, old, new = self.models(239)
        self.assertEqual(old.tmd.build(), new.tmd.build())
        self.assertEqual(changed_programs(old, new), [2, 3, 4])
        for slot, expected in [(2, 20), (3, 240/18), (4, 40)]:
            frames, loop, _ = animsheet.slot_frames(new, len(sk), slot)
            self.assertEqual(loop, 0)
            self.assertAlmostEqual(abs(frames[-1][0][8]-frames[0][0][8])/(len(frames)-1), expected, places=2)
            self.assertGreater(max(p[1][7] for p in frames)-min(p[1][7] for p in frames), 3 if slot == 3 else 6)
            poses = copy.deepcopy(frames)
            for p in poses: p[0] = [4096]*3+[0]*6
            positions = [R.world_pos(sk,p) for p in poses]
            for foot in (5,7,12,15):
                self.assertGreater(max(p[foot][2] for p in positions)-min(p[foot][2] for p in positions), 35)
                self.assertGreater(max(p[foot][1] for p in positions)-min(p[foot][1] for p in positions), 15)
                self.assertTrue(all(abs(p[foot][0]) > 35 for p in positions))
            for foot in (5,7,12,15):
                contacts = [F.A.floor(new,sk,p,[foot]) for p in frames[:-1]]
                self.assertGreaterEqual(sum(-3 <= value <= 1 for value in contacts), 2, 'stance paws must reach the floor')
            for bone in (2,3,8,9):
                self.assertGreater(len({tuple(p[bone][3:6]) for p in frames}), 3)
            grounds = [F.A.floor(new,sk,interpolate_pose(a,b,t),(5,7,12,15)) for a,b in zip(frames,frames[1:]) for t in (0,1365,2730)]
            self.assertLess(max(grounds), 6)


if __name__ == '__main__':
    unittest.main()
