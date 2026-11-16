"""Decoded-motion and fixed-allocation regression on private real model fixtures.

PARTNER_HEADROOM_FIXTURES=build/heap-proof python3 -m unittest tools.test_partner_headroom
The directory contains ID-before.MMD and ID-safe.MMD for each reviewed species.
"""
import os
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
import mmd
import coldsplit
import animsheet
from tools.models import partner_headroom as H


@unittest.skipUnless(os.environ.get('PARTNER_HEADROOM_FIXTURES'), 'private model fixtures required')
class PartnerHeadroom(unittest.TestCase):
    def test_actual_models_preserve_mesh_events_timing_and_channel_bound(self):
        import json
        folder=Path(os.environ['PARTNER_HEADROOM_FIXTURES'])
        metadata=json.loads((folder/'fixture-bones.json').read_text())
        for sid in sorted(H.SPECIES):
            with self.subTest(species=sid):
                nb=metadata[str(sid)]
                before=(folder/f'{sid}-before.MMD').read_bytes()
                after,proof=H.apply(before,[None]*nb,sid,cold=sid>=180)
                self.assertEqual(after,(folder/f'{sid}-safe.MMD').read_bytes())
                a,b=mmd.MMD.parse(before,nb),mmd.MMD.parse(after,nb)
                self.assertEqual(a.tmd.build(),b.tmd.build())
                self.assertEqual(len(a.anims.table),len(b.anims.table))
                for slot,(ai,bi) in enumerate(zip(a.anims.table,b.anims.table)):
                    self.assertEqual(ai is None,bi is None)
                    if ai is None:continue
                    if a.anims.anims[ai].build()==b.anims.anims[bi].build():continue
                    if sid>=180:self.assertIn(slot,H.SLOTS)
                    frames,loop,events=animsheet.slot_frames(a,nb,slot)
                    again,loop2,events2=animsheet.slot_frames(b,nb,slot)
                    self.assertEqual((len(frames),loop,list(events)),(len(again),loop2,list(events2)))
                    error=max(abs(int(x)-int(y)) for pa,pb in zip(frames,again)
                              for ba,bb in zip(pa,pb) for x,y in zip(ba,bb))
                    self.assertLessEqual(error,proof['tolerance'])
                resident,cold=coldsplit.split(after,nb) if sid>=180 else (after,b'')
                self.assertLessEqual((len(resident)+2047)//2048*2048,0x18000)
                self.assertEqual(H.apply(after,[None]*nb,sid,cold=sid>=180)[0],after)


if __name__=='__main__':unittest.main()
