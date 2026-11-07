"""Replay reviewed gaits and verify decoded storage, care clips and loop seams."""
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
from tools.models.field_animations import native_polish, gizamon_refine
from tools.models.resize import resize, resize_with_pace

ARTIFACTS = Path(os.environ.get('GAIT_REVIEW', ROOT / 'build/gait-review4'))


class RefinedGaits(unittest.TestCase):
    def test_recipes_match_provider_targets(self):
        records = {r['id']: r for r in json.loads((ROOT/'content/modeldelta/models.json').read_text())['models']}
        for path in (ROOT/'content/models/authoring/gait-refinement').glob('*.json'):
            cfg = json.loads(path.read_text())
            self.assertEqual(cfg['output_sha256'], records[cfg['species']]['mmd']['sha256'])
            preceding = cfg['preceding_delta']
            self.assertEqual(preceding['sha256'], cfg['source_sha256'])
            self.assertEqual(hashlib.sha256((ROOT/preceding['delta']).read_bytes()).hexdigest(), preceding['delta_sha256'])

    def test_replay_and_decoded_performance(self):
        if not (ARTIFACTS/'before/187-Stingmon.MMD').is_file():
            self.skipTest('Set GAIT_REVIEW to the before/after review artifacts')
        audit = []
        for path in sorted((ROOT/'content/models/authoring/gait-refinement').glob('*.json')):
            cfg = json.loads(path.read_text()); sid = cfg['species']; sk = cfg['skeleton']; nb = len(sk)
            with self.subTest(species=sid):
                before = next((ARTIFACTS/'before').glob(f'{sid}-*.MMD')).read_bytes()
                after = next((ARTIFACTS/'after').glob(f'{sid}-*.MMD')).read_bytes()
                self.assertEqual(hashlib.sha256(before).hexdigest(), cfg['source_sha256'])
                self.assertEqual(hashlib.sha256(after).hexdigest(), cfg['output_sha256'])
                if sid == 183:
                    self.assertEqual(resize_with_pace(before, sk, sid, cfg['factor']), after)
                    scaled = mmd.MMD.parse(resize(before, nb, cfg['factor']), nb)
                    actual = mmd.MMD.parse(after, nb); actual.type = sid
                    self.assertEqual(scaled.tmd.build(), actual.tmd.build())
                    self.assertEqual(changed_programs(scaled, actual), [2,3,4])
                    for slot, minimum in ((2,15),(3,9.5),(4,35)):
                        frames, loop, _ = animsheet.slot_frames(actual,nb,slot)
                        self.assertEqual(loop,0)
                        self.assertGreaterEqual(-(frames[-1][0][8]-frames[0][0][8])/(len(frames)-1),minimum)
                    continue
                replay, report = gizamon_refine.build(before, sk) if sid == 239 else native_polish.build(before, cfg)
                self.assertEqual(replay, after)
                mmd.exe().add_type(sid, sk)
                old = mmd.MMD.parse(before, nb); old.type = sid
                new = mmd.MMD.parse(after, nb); new.type = sid
                self.assertEqual(old.tmd.build(), new.tmd.build())
                changed = cfg.get('slots', [2,3,4]) if sid != 239 else [0,1,2,3,4,9,11]
                self.assertEqual(changed_programs(old,new), changed)
                self.assertTrue(motionstorage.require(after,nb)['fits'])
                for slot in changed:
                    frames, loop, events = animsheet.slot_frames(new,nb,slot)
                    if sid==239:
                        source = animsheet.slot_frames(old,nb,slot)[0]
                        self.assertEqual(len(source),len(frames))
                        for original,pose in zip(source,frames):
                            for bone in (10,11,12,13,14,15):
                                self.assertEqual(original[bone][:3]+original[bone][6:],pose[bone][:3]+pose[bone][6:])
                            world = mmd.bone_matrices(new,pose)
                            for bone in (12,15):self.assertLess(abs(abs(world[bone][0][3])-85),1)
                    if slot in (2,3,4):
                        self.assertEqual(loop,0)
                        for a,b in zip(frames[0][1:],frames[-1][1:]):
                            self.assertEqual(a[:3]+a[6:],b[:3]+b[6:])
                            self.assertLess(max(abs((x-y+2048)%4096-2048) for x,y in zip(a[3:6],b[3:6])),3)
                        player=mmd.AnimPlayer(new.anims.anims[new.anims.table[slot]],nb,slot)
                        poses=[]; period=len(frames)-1
                        for tick in range(period*4):
                            self.assertTrue(player.tick())
                            pose=[v[:3]+[x%4096 for x in v[3:6]]+v[6:] for v in player.pose[1:]]
                            if tick<period:poses.append(copy.deepcopy(pose))
                            else:self.assertEqual(pose,poses[tick%period])
                        if cfg.get('mirror_free_arm'):
                            arms = {187: ((13,16),(17,20)), 297: ((2,4),(5,7)), 306: ((2,4),(6,8))}[sid]
                            paths = [[],[]]
                            for pose in frames[:-1]:
                                world = mmd.bone_matrices(new,pose)
                                for path,(shoulder,wrist) in zip(paths,arms):path.append(world[wrist][2][3]-world[shoulder][2][3])
                            means = [sum(p)/len(p) for p in paths]
                            covariance = sum((a-means[0])*(b-means[1]) for a,b in zip(*paths))
                            self.assertLess(covariance,0,'opposite arms must swing in opposite phases')
                    feet=cfg.get('feet',[5,7,12,15]);floor=[]
                    for a,b in zip(frames,frames[1:]):
                        for alpha in (0,1365,2730):
                            pose=interpolate_pose(a,b,alpha);pose[0]=[4096]*3+[0]*6
                            world=mmd.bone_matrices(new,pose)
                            floor.append(max(sum(world[bone][1][j]*v[j] for j in range(3))+world[bone][1][3]
                                             for bone in feet for v in new.tmd.obj_verts(sk[bone][0])))
                    audit.append(dict(species=sid,slot=slot,worst_penetration=max(floor),largest_support_gap=-min(floor)))
                    self.assertLessEqual(max(floor),2.5)
                    if sid==289:self.assertLessEqual(-min(floor),20)
                    if sid==409 and slot==4:self.assertLessEqual(-min(floor),20)
                    if sid==460:self.assertLessEqual(-min(floor),12)
        (ARTIFACTS/'decoded-audit.json').write_text(json.dumps(audit,indent=2)+'\n')


if __name__=='__main__':unittest.main()
