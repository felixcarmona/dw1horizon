"""Movement sound edits preserve shared pose programs and texture events."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mmd
from tools.models import movement_sounds
from motiondiscidentity import changed_programs


class MovementSounds(unittest.TestCase):
    def model(self, with_sound):
        model = mmd.MMD()
        model.tmd = mmd.TMD()
        model.tmd.objects = [mmd.TMDObject(), mmd.TMDObject()]
        model.tmd.verts = [(0,0,0,0), (1,2,3,0)]
        model.tmd.norms = [(0,4096,0,0)]
        for i, obj in enumerate(model.tmd.objects):
            obj.vert_start = i
            obj.nvert = obj.nnorm = 1
        samples = []
        for t in range(21):
            samples.append([[4096,4096,4096,0,0,0,0,0,-20*t],
                            [4096,4096,4096,0,t*2,0,0,-50,0],
                            [4096,4096,4096,0,0,t,0,-10,30]])
        events = [(0,'tex',dict(src=(0,0),size=(1,1),dst=(0,1)))]
        if with_sound:
            events.append((6,'sound',dict(bank=1,note=13)))
        animation = mmd.encode_anim(samples,3,loop_sample=0,events=events,tol=0,repeats=False)
        model.anims = mmd.AnimSection()
        model.anims.anims = [animation]
        model.anims.table = [0]*46
        return model.build()

    def test_add_and_replace_sounds_without_changing_shared_motion(self):
        for with_sound in (False,True):
            with self.subTest(existing_sound=with_sound):
                source = self.model(with_sound)
                result, proof = movement_sounds.apply(source,[[-1,-1],[0,0],[1,1]],307,24)
                old = mmd.MMD.parse(source,3)
                new = mmd.MMD.parse(result,3)
                self.assertEqual(changed_programs(old,new),[2,3,4,27,35,36])
                self.assertEqual(old.tmd.build(),new.tmd.build())
                for slot in (2,3,4,27,35,36):
                    before = mmd.AnimPlayer(old.anims.anims[old.anims.table[slot]],3,slot)
                    after = mmd.AnimPlayer(new.anims.anims[new.anims.table[slot]],3,slot)
                    for _ in range(181):
                        self.assertEqual(before.tick(),after.tick())
                        self.assertEqual(before.pose,after.pose)
                        self.assertEqual(before.root,after.root)
                        self.assertEqual(before.base,after.base)
                    self.assertEqual([e for e in before.events if e[1]=='tex'],
                                     [e for e in after.events if e[1]=='tex'])
                    self.assertTrue(any(k=='sound' for _,k,_ in after.events))
                    self.assertTrue(all((e['bank'],e['note'])==(1,24)
                                        for _,kind,e in after.events if kind=='sound'))
                self.assertTrue(proof['storage']['fits'])


if __name__ == '__main__':
    unittest.main()
