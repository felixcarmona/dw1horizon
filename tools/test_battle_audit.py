#!/usr/bin/env python3
"""Owned damage curve contracts and audit inputs; no disc or emulator required."""
import copy
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools import battle_audit as B
from tools import balance


class CurveTests(unittest.TestCase):
    def setUp(self):
        self.rules=B.load('content/tables/battle-formulas.json')['battleFormulas']['damage']

    def test_original_range_signed_rounding(self):
        for power in (0,1,65,586,722,32767):
            for diff in range(-500,501):
                old=power+B.trunc(diff*power,500)
                self.assertEqual(B.stat_power(power,diff,self.rules),old)
        self.assertEqual(B.stat_power(1,-499,self.rules),1)

    def test_high_stat_targets_and_floor(self):
        for diff,want in ((500,1172),(750,1367),(1000,1465),(5000,1699),(9999,1728)):
            self.assertEqual(B.stat_power(586,diff,self.rules),want)
        self.assertEqual(B.damage(586,0,9999,60,self.rules),1)
        self.assertEqual(B.damage(586,9999,0,30,self.rules,easy=1),3456)
        self.assertEqual(B.damage(586,9999,0,30,self.rules,block=10),172)

    def test_owned_encoding_and_older_table_prefix(self):
        obj=B.load('content/tables/battle-formulas.json')['battleFormulas']
        raw=balance.encode_named('battleFormulas',obj,None)
        self.assertEqual(struct.unpack('<2h',raw[-4:]),(500,1))
        class Old:
            def where(self,key):return ('SLUS_010.32',0,len(raw)-4)
        self.assertEqual(balance.encode_named('battleFormulas',obj,Old()),raw[:-4])
        obj=copy.deepcopy(obj)
        del obj['damage']['tailHalfDifference']
        del obj['damage']['tailPowerDivisor']
        self.assertEqual(balance.encode_named('battleFormulas',obj,None)[:-4],raw[:-4])
        self.assertEqual(balance.encode_named('battleFormulas',obj,None)[-4:],b'\xff'*4)

    def test_missing_tail_is_old_rule(self):
        for key in ('tailHalfDifference','tailPowerDivisor'):
            for value in (0,-1):
                rules=dict(self.rules,**{key:value})
                self.assertEqual(B.stat_power(586,9999,rules),1172)

    def test_canonical_elements_and_reported_hit(self):
        self.assertEqual(B.ELEMENTS,balance.ELEMENTS)
        matrix=B.load('content/tables/type-factors.json')['typeFactors']
        air=B.ELEMENTS.index('air')
        total=matrix[air][B.ELEMENTS.index('nature')]+matrix[air][B.ELEMENTS.index('battle')]+10
        self.assertEqual(total,22)
        self.assertEqual(B.damage(586,4430,600,total,self.rules,old=True,roll=93),798)
        self.assertEqual(B.damage(586,4430,600,total,self.rules,roll=93),1145)
        machine=next(s for s in B.placements()[0] if s['id']==115)
        self.assertEqual(sum(matrix[air][B.ELEMENTS.index(e)] for e in machine['specialties']),22)

    def test_actual_boss_and_noncombat_rows(self):
        _,rows=B.placements()
        boss=next(r for r in rows if r['map']=='MGEN99' and r['slot']==0)
        self.assertEqual((boss['hp'],boss['off'],boss['def']),(9400,999,650))
        market=next(r for r in rows if r['off']==9100)
        self.assertEqual(market['level'],'none')


if __name__=='__main__':unittest.main()
