#!/usr/bin/env python3
"""Cold-read capacity includes the stream's position within its first sector."""
import unittest
import copy
from unittest.mock import patch
import motionstorage as S


class ColdCapacity(unittest.TestCase):
    def test_target_capacities_come_from_the_linked_engine(self):
        text=' .bss.COLD_ANIM_BUFFER\n 0x80100000 0x2000 file.o\n .bss.PARTNER_MODEL_BUFFER\n 0x80102000 0x18800 other.o\n'
        self.assertEqual(S.linker_limits(text),dict(cold_limit=8192,resident_limit=100352))
        with self.assertRaisesRegex(ValueError,'PARTNER_MODEL_BUFFER'):S.linker_limits(text.split(' .bss.PARTNER_MODEL_BUFFER')[0])

    def test_split_aligns_large_stream_and_join_preserves_every_animation(self):
        m=S.M.mmd.MMD();m.tmd=S.M.mmd.TMD();m.anims=S.M.mmd.AnimSection()
        pose=[[4096,4096,4096,0,0,0,0,0,0],[4096,4096,4096,0,0,0,0,-20,0]]
        a=S.M.mmd.encode_anim([pose,copy.deepcopy(pose)],2,loop_sample=None,tol=0,repeats=False)
        a.tail+=b'\0'*(-len(a.build())%4)
        streams=[copy.deepcopy(a) for _ in range(3)]
        for stream,size in zip(streams[1:],[5472,7880]):stream.tail+=b'\0'*(size-len(stream.build()))
        m.anims.table=[None]*14;m.anims.table[0]=0;m.anims.table[5]=1;m.anims.table[7]=2;m.anims.anims=streams
        data=m.build();resident,cold=S.C.split(data,2);rows=S.cold_reads(resident)
        self.assertEqual(rows[1]['offset'],6144);self.assertTrue(all(r['fits'] for r in rows))
        joined=S.M.mmd.MMD.parse(S.C.join(resident,cold,2,14),2)
        for slot in [0,5,7]:self.assertEqual(joined.anims.anims[joined.anims.table[slot]].build(),streams[m.anims.table[slot]].build())
        streams[2].tail+=b'\0'*400
        with self.assertRaisesRegex(ValueError,'exceeds buffer'):S.C.split(m.build(),2)

    def test_alignment_can_push_an_individually_small_stream_over_capacity(self):
        def entry(offset,length):return 0x80000000|((length//4)<<16)|(offset//4)
        with patch.object(S.C,'entries',return_value={7:entry(0,8192),8:entry(4,8192),9:entry(2044,6148),10:entry(2044,6152)}):
            rows=S.cold_reads(b'')
        self.assertEqual([r['sector_read_bytes'] for r in rows],[8192,10240,8192,10240])
        self.assertEqual([r['fits'] for r in rows],[True,False,True,False])


if __name__=='__main__':unittest.main()
