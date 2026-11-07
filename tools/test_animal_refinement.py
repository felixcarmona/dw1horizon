"""Replay anatomical animal gaits and guard the approved model boundaries."""
import copy
import hashlib
import json
import statistics
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
import animsheet
import mmd
import retarget as R
from motiondiscidentity import changed_programs
from motiontailspace import interpolate_pose
from tools.models.field_animations import animal_refine

ART=ROOT/'build/gait-review5'


class AnimalRefinement(unittest.TestCase):
    def test_provenance_and_targets(self):
        rows={r['id']:r for r in json.loads((ROOT/'content/modeldelta/models.json').read_text())['models']}
        for path in (ROOT/'content/models/authoring/animal-refinement').glob('*.json'):
            cfg=json.loads(path.read_text());sid=cfg['species']
            self.assertEqual(cfg['output_sha256'],rows[sid]['mmd']['sha256'])
            if 'preceding_delta' in cfg:
                pin=cfg['preceding_delta']
                self.assertEqual(pin['sha256'],cfg['source_sha256'])
                self.assertEqual(hashlib.sha256((ROOT/pin['delta']).read_bytes()).hexdigest(),pin['delta_sha256'])
            else:self.assertEqual(cfg['importer_source']['sha256'],cfg['source_sha256'])

    def test_replay_mesh_events_and_unaffected_clips(self):
        if not (ART/'prior/187-Stingmon.MMD').is_file():self.skipTest('before/after review artifacts required')
        for path in (ROOT/'content/models/authoring/animal-refinement').glob('*.json'):
            cfg=json.loads(path.read_text());sid=cfg['species'];sk=cfg['skeleton'];nb=len(sk)
            with self.subTest(species=sid):
                source=(ART/'raw/build/batch5/Gizamon.MMD') if sid==239 else next((ART/'prior').glob(f'{sid}-*.MMD'))
                data=source.read_bytes();target=next((ART/'after').glob(f'{sid}-*.MMD')).read_bytes()
                self.assertEqual(animal_refine.digest(data),cfg['source_sha256'])
                replay,_=animal_refine.build(data,cfg);self.assertEqual(replay,target)
                old=mmd.MMD.parse((ART/'prior/239-Gizamon.MMD').read_bytes() if sid==239 else data,nb);new=mmd.MMD.parse(target,nb)
                self.assertEqual(old.tmd.build(),new.tmd.build())
                self.assertEqual(changed_programs(old,new),[0,1,2,3,4,9,11] if sid==239 else [2,3,4])
                for slot in ([9,11] if sid==239 else [2,3,4] if sid==187 else []):
                    before=animsheet.slot_frames(old,nb,slot);after=animsheet.slot_frames(new,nb,slot)
                    self.assertEqual(before[2],after[2])

    def test_stingmon_other_limbs_and_shoe_frame(self):
        if not (ART/'after/187-Stingmon.MMD').is_file():self.skipTest('review artifacts required')
        cfg=json.loads((ROOT/'content/models/authoring/animal-refinement/187.json').read_text());sk=cfg['skeleton'];nb=len(sk);mmd.exe().add_type(187,sk)
        before=mmd.MMD.load(str(ART/'prior/187-Stingmon.MMD'),187);after=mmd.MMD.load(str(ART/'after/187-Stingmon.MMD'),187)
        right=before.tmd.obj_verts(sk[24][0]);left=before.tmd.obj_verts(sk[27][0])
        rc=[sum(v[i] for v in right)/len(right) for i in range(3)]
        lc=[sum(v[i] for v in left)/len(left) for i in range(3)]
        mirrored=[[-(v[0]-lc[0]),v[1]-lc[1],v[2]-lc[2]] for v in left]
        centered=[[v[i]-rc[i] for i in range(3)] for v in right]
        rms=(sum(min(sum((a[i]-b[i])**2 for i in range(3)) for b in mirrored) for a in centered)/len(centered))**.5
        self.assertLess(rms,2,'shoe shapes differ by width reflection and origin, with matching sole orientation')
        for slot in (2,3,4):
            old=animsheet.slot_frames(before,nb,slot)[0];new=animsheet.slot_frames(after,nb,slot)[0];period=len(old)-1
            self.assertEqual(len(old),len(new))
            for tick,(a,b) in enumerate(zip(old,new)):
                for bone in range(nb):
                    self.assertEqual(a[bone][:3]+a[bone][6:],b[bone][:3]+b[bone][6:])
                    if bone not in (25,26,27):
                        self.assertLess(max(abs((x-y+2048)%4096-2048) for x,y in zip(a[bone][3:6],b[bone][3:6])),1.1)
                expected=R.world_rots(sk,old[(tick+period//2)%period])[24]
                actual=R.world_rots(sk,b)[27]
                for axis in (1,2):
                    self.assertGreater(sum(expected[i][axis]*actual[i][axis] for i in range(3)),.999,'sole and toe directions must agree through the cycle')

    def test_no_hop_support_and_four_cycle_playback(self):
        if not (ART/'after/409-Kyubimon.MMD').is_file():self.skipTest('review artifacts required')
        audit=[]
        for sid,feet in [(409,[5,8,15,18]),(183,[11,12,14,15,17,18]),(239,[5,7,12,15])]:
            cfg=json.loads((ROOT/f'content/models/authoring/animal-refinement/{sid}.json').read_text());sk=cfg['skeleton'];nb=len(sk);mmd.exe().add_type(sid,sk)
            model=mmd.MMD.load(str(next((ART/'after').glob(f'{sid}-*.MMD'))),sid)
            for slot in (2,3,4):
                fs,loop,_=animsheet.slot_frames(model,nb,slot);self.assertEqual(loop,0)
                if sid==409:
                    self.assertEqual(len({p[1][7] for p in fs}),1,'canine trunk must never bounce')
                    self.assertEqual(cfg['donor'],22);self.assertEqual(cfg['donor_slots'][str(slot)],2)
                    if slot==2:
                        slip=[]
                        for a,b in zip(fs,fs[1:]):
                            ap,bp=R.world_pos(sk,a),R.world_pos(sk,b)
                            for foot in feet:
                                if animal_refine.floor(model,sk,a,[foot])>=-4 and animal_refine.floor(model,sk,b,[foot])>=-4:
                                    slip.append(abs(bp[foot][2]-ap[foot][2]))
                        self.assertGreaterEqual(len(slip),8)
                        self.assertLessEqual(statistics.median(slip),6)

                if sid==183:self.assertEqual(cfg['donor'],32)
                ground=[animal_refine.floor(model,sk,interpolate_pose(a,b,t),feet) for a,b in zip(fs,fs[1:]) for t in (0,1365,2730)]
                self.assertLessEqual(max(ground),6)
                self.assertGreaterEqual(min(ground),-8)
                player=mmd.AnimPlayer(model.anims.anims[model.anims.table[slot]],nb,slot);period=len(fs)-1;first=[]
                for tick in range(period*4):
                    self.assertTrue(player.tick());pose=[v[:3]+[x%4096 for x in v[3:6]]+v[6:] for v in player.pose[1:]]
                    if tick<period:first.append(copy.deepcopy(pose))
                    else:self.assertEqual(pose,first[tick%period])
                audit.append(dict(species=sid,slot=slot,penetration=max(ground),support_gap=-min(ground)))
        (ART/'decoded-audit.json').write_text(json.dumps(audit,indent=2)+'\n')

    def test_gizamon_sleep_keeps_full_source_limbs(self):
        if not (ART/'after/239-Gizamon.MMD').is_file():self.skipTest('review artifacts required')
        cfg=json.loads((ROOT/'content/models/authoring/animal-refinement/239.json').read_text());sk=cfg['skeleton'];nb=len(sk);mmd.exe().add_type(239,sk)
        self.assertEqual(cfg['donor'],4)
        original=mmd.MMD.load(str(ART/'raw/build/batch5/Gizamon.MMD'),239);model=mmd.MMD.load(str(ART/'after/239-Gizamon.MMD'),239)
        for slot in (9,11):
            a=animsheet.slot_frames(original,nb,slot)[0];b=animsheet.slot_frames(model,nb,slot)[0]
            self.assertEqual(len(a),len(b))
            for before,after in zip(a,b):
                for bone in (4,5,6,7,10,11,12,13,14,15):
                    self.assertEqual(before[bone][:3]+before[bone][6:],after[bone][:3]+after[bone][6:])
                world=R.world_pos(sk,after)
                for foot in (12,15):self.assertGreater(abs(world[foot][0]),50)
