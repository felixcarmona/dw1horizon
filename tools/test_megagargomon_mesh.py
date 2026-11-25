"""MegaGargomon-only final repair and exhaustive evidence regressions."""
from pathlib import Path
import json
import unittest
import numpy as np
from tools.models import mesh_megagargomon_review as R
from tools.models.mesh_round4 import load
from tools.models.mesh_stability import bent_quads

ROOT=Path(__file__).resolve().parents[1]


class DeformationProof(unittest.TestCase):
    def test_strict_witness_has_positive_floor_and_rejects_an_oversized_cube(self):
        record=dict(edge_triangle=[[-2,0,-2],[2,0,2],[0,3,0]],
                    face_triangle=[[-4,-4,0],[4,-4,0],[0,4,0]],edge=0,
                    vertex_coordinate_radius=.01)
        self.assertGreater(R.verify_deformation_floor(record),0)
        record['vertex_coordinate_radius']=10
        with self.assertRaises(ValueError):R.verify_deformation_floor(record)


@unittest.skipUnless((ROOT/'build/after/index.json').exists(),'private final-model fixtures unavailable')
class FinalMesh(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before=load(ROOT/'build/before',335)
        cls.after=load(ROOT/'build/after',335)

    def test_storage_and_gpu_diagonals(self):
        import motionstorage
        before=motionstorage.require(self.before.m.build(),27)
        after=motionstorage.require(self.after.m.build(),27)
        # Full-size pods keep four more GPU-diagonal splits (80 B) than the
        # shrunken ones; the repair's own ceiling and the partner buffer still hold.
        self.assertLessEqual(after['resident_bytes'],before['resident_bytes']+80)
        self.assertLessEqual(after['resident_bytes'],97536)
        self.assertLessEqual(after['resident_bytes'],100256)
        self.assertFalse(bent_quads(self.after.m,.001))
        self.assertFalse(self.after.m.tmd.objects[19].prims)
        self.assertFalse(self.after.m.tmd.objects[20].prims)

    def test_every_visible_channel_root_event_loop_and_alias(self):
        import mmd
        a,b=self.before,self.after
        self.assertEqual(a.bones,b.bones)
        self.assertEqual(a.m.anims.table,b.m.anims.table)
        self.assertEqual(a.tim.to_bytes(),b.tim.to_bytes())
        from tools.models import mesh_megagargomon as G
        # channels this round re-times on purpose: tighter elbow arcs and a calmer head swing
        edited={}
        for slot in G.ELBOW_SLOTS:
            edited.setdefault(a.m.anims.table[slot],[]).extend([(15,3),(25,3)])
        for slot in G.HEAD_SWING:
            edited.setdefault(a.m.anims.table[slot],[]).extend([(17,3),(17,4),(17,5)])
        ticks=0
        for slot in a.slots():
            aa,info=mmd.simulate(a.m.anims.anims[a.m.anims.table[slot]],27,slot=slot)
            bb,got=mmd.simulate(b.m.anims.anims[b.m.anims.table[slot]],27,slot=slot)
            self.assertEqual(info,got)
            self.assertEqual(len(aa),len(bb))
            ticks+=len(aa)
            mask=np.ones((27,9),bool)
            mask[[20,21],:3]=False  # removed, permanently invisible objects
            for bone,channel in edited.get(a.m.anims.table[slot],()):
                mask[bone,channel]=False
            self.assertTrue(np.array_equal(np.asarray(aa)[:,mask],np.asarray(bb)[:,mask]),slot)
        self.assertEqual(ticks,2009)

    def test_exhaustive_target_pairs(self):
        path=ROOT/'build/collar-ledger/335.json'
        if not path.exists():self.skipTest('final exhaustive ledger unavailable')
        report=json.loads(path.read_text())
        self.assertEqual(report['ticks'],2009)
        self.assertEqual(len(report['slots']),52)
        # Full-size pods: the forearm meets its pod only where the clip raises the
        # guns over the shoulders (signature 11/42 and the two-gun attacks).
        raised={11,42,48,49,51,54,55,56,57,59,60}
        for pair in ('13/15','23/25'):
            slots={int(k) for k,row in report['slots'].items() if pair in row['pairs']}
            self.assertLessEqual(slots,raised,pair)
        # 23/24 (left upper arm against the back of its pod) stays in the walk and run.
        for slot in (0,1,2,3,4,14,15,16,17,18):
            for pair in ('13/15','23/25','13/16','23/26','13/17','17/23'):
                self.assertNotIn(pair,report['slots'][str(slot)]['pairs'],(slot,pair))
        # Full thighs: the top of the thigh shell meets the skirt hem (2/4, 2/9),
        # deepest in the walk and run; bounded, not cleared.
        for pair in ('2/4','2/9'):
            self.assertLess(report['pairs'][pair]['depth'],60,pair)

    def test_accelerator_matches_reference_sorting_and_rasterization(self):
        import math
        from tools.models import psx_blend
        library=R.compile_renderer(ROOT/'build/test-raster')
        for model in (self.before,self.after):
            renderer=R.Renderer(model,library)
            pose=model.poses(4,6000)[13]
            for phase in (0,2):
                expected,frame=psx_blend.render(model,math.pi/4,math.pi/6,size=96,
                                               pose=pose,depth_offset=phase)
                actual,_=renderer.render(pose,math.pi/4,frame=frame,phase=phase)
                self.assertTrue(np.array_equal(expected,actual))

    def test_each_retained_pair_has_a_verified_local_floor(self):
        path=ROOT/'build/floors/pair-floors.json'
        if not path.exists():self.skipTest('local deformation certificates unavailable')
        from tools.models.mesh_round4 import pair_at
        records=json.loads(path.read_text())
        self.assertFalse(records['unrestricted_floor_proven'])
        for pair,row in records['pairs'].items():
            proof=row['certificate']
            self.assertTrue(proof['proven'],pair)
            depth=R.verify_deformation_floor(proof)
            self.assertGreater(depth,0)
            self.assertAlmostEqual(depth,proof['depth_lower_bound'])
            entry=row['entry']
            aa,bb=pair_at(self.after,entry['bones'],entry['slot'],entry['tick'])
            def contains(group,triangle):
                return np.any(np.all(np.isclose(group,triangle,rtol=0,atol=1e-8),axis=(1,2)))
            edge,face=proof['edge_triangle'],proof['face_triangle']
            self.assertTrue((contains(aa,edge) and contains(bb,face)) or
                            (contains(bb,edge) and contains(aa,face)),pair)
