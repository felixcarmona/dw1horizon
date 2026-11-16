"""KingEtemon's intact cape must survive native fitting as one continuous sheet."""
import copy
import json
from pathlib import Path
import sys
import unittest

import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import mmd
from tools.models.field_animations import native_binding as binding


class KingEtemonCape(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path('build/edit/303-KingEtemon.MMD')
        if not path.exists() or not (Path(mmd.EXTRACTED)/'CHDAT/MMD1/ETEM.MMD').exists():
            raise unittest.SkipTest('requires the private imported model and native extraction')
        cls.data = path.read_bytes()
        cls.skeleton = json.loads(next(Path('content/species').glob('303-*.json')).read_text())['model']['skeleton']
        cls.recipe = json.loads(binding.MANIFEST.read_text())['303']

    def test_all_panels_share_the_attachment_fit_and_carrier(self):
        recipe = copy.deepcopy(self.recipe)
        # Isolate geometry fitting; these later stages only author motion.
        for stage in ('pace','hands','battle_originals'):
            recipe.pop(stage,None)
        placements = {}
        data,proof = binding.bind(self.data,self.skeleton,recipe,placements,final=False)
        source = mmd.MMD.parse(self.data,len(self.skeleton))
        target = mmd.MMD.parse(data,len(proof['generated_skeleton']))
        self.assertEqual(sum(len(o.prims) for o in source.tmd.objects),
                         sum(len(o.prims) for o in target.tmd.objects))
        for bone in (19,20,21,22):
            self.assertEqual(recipe['map'][str(bone)],recipe['map']['1'])
            for before,after in zip(placements[1],placements[bone]):
                np.testing.assert_array_equal(before,after)
        source.type = 303
        pose = binding.bind_pose(source,self.skeleton,recipe)
        pose[0] = [4096]*3+[0]*6
        world = np.array(mmd.bone_matrices(source,pose))
        pools = {}
        for bone in (1,19,20,21,22):
            vertices = np.array(source.tmd.obj_verts(self.skeleton[bone][0]))[:,:3]
            pools[bone] = vertices@world[bone,:3,:3].T+world[bone,:3,3]
        anchor,transform,destination = placements[1]
        seams = 0
        for a,b in ((1,19),(19,20),(20,21),(21,22)):
            distance = np.linalg.norm(pools[a][:,None]-pools[b][None,:],axis=2)
            pairs = np.argwhere(distance <= 8.)
            for i,j in pairs:
                gap = np.linalg.norm((pools[a][i]-pools[b][j])@transform.T)
                self.assertLessEqual(gap,1.5*distance[i,j]+1e-6)
                seams += 1
        self.assertGreater(seams,10)

    def test_follow_piece_refuses_a_different_carrier(self):
        recipe = copy.deepcopy(self.recipe)
        recipe['map']['19'] = 14
        for stage in ('pace','hands','battle_originals'):
            recipe.pop(stage,None)
        with self.assertRaisesRegex(ValueError,'same carrier'):
            binding.bind(self.data,self.skeleton,recipe,final=False)
