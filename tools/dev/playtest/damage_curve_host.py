#!/usr/bin/env python3
"""Compile the actual shared C stat-power helper with exhaustive JSON powers.

UBSan checks signed arithmetic. Every difference in the game's complete stat
range is checked; the original ±500 range must retain C truncation bit for bit.
Usage: python3 tools/dev/playtest/damage_curve_host.py build/decomp-curve
"""
import re
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools.battle_audit import stat_power, load


def main():
    tree=Path(sys.argv[1]).resolve()
    rules=load('content/tables/battle-formulas.json')['battleFormulas']['damage']
    powers=sorted({0,1,32767} | {load(p.relative_to(ROOT))['power'] for p in (ROOT/'content/techniques').glob('*.json')})
    with tempfile.TemporaryDirectory(prefix='damage-curve-') as temp:
        folder=Path(temp); (folder/'dw').mkdir()
        (folder/'dw/types.h').write_text('#include <stdint.h>\n')
        c=r'''
#include <assert.h>
#include <stdio.h>
#include "mod_battle.h"
int16_t MOD_BATTLE[MOD_BT_SIZE];
int main(void) {
    int powers[] = {POWERS};
    MOD_BATTLE[MOD_BT_DIFF_CLAMP] = KNEE;
    MOD_BATTLE[MOD_BT_DIFF_DIV] = DIVISOR;
    MOD_BATTLE[MOD_BT_TAIL_HALF] = HALF;
    MOD_BATTLE[MOD_BT_TAIL_DIV] = TAILDIV;
    for (unsigned i=0;i<sizeof(powers)/sizeof(*powers);i++) {
        int p=powers[i], previous=-1;
        for(int d=-9999;d<=9999;d++) {
            int limited=d < -KNEE ? -KNEE : d > KNEE ? KNEE : d;
            int original=p+limited*p/DIVISOR;
            int got=modBtStatPower(p,d);
            if(d<=KNEE) assert(got==original);
            assert(got>=previous); previous=got;
            assert(got<=3*p);
            printf("%d %d %d\n",p,d,got);
        }
    }
    /* Largest supported denominator and a non-unit amplitude divisor. */
    MOD_BATTLE[MOD_BT_TAIL_HALF]=1234; MOD_BATTLE[MOD_BT_TAIL_DIV]=3;
    assert(modBtStatPower(722,9999)==1444+(722*9499/10733)/3);
    MOD_BATTLE[MOD_BT_DIFF_CLAMP]=0;
    MOD_BATTLE[MOD_BT_TAIL_HALF]=32767; MOD_BATTLE[MOD_BT_TAIL_DIV]=32767;
    assert(modBtStatPower(32767,32767)==32767);
    MOD_BATTLE[MOD_BT_DIFF_CLAMP]=KNEE;
    MOD_BATTLE[MOD_BT_TAIL_HALF]=HALF; MOD_BATTLE[MOD_BT_TAIL_DIV]=TAILDIV;
    /* Missing/wiped rules retain the bounded old path and never divide by 0. */
    MOD_BATTLE[MOD_BT_TAIL_HALF]=-1;
    assert(modBtStatPower(586,9999)==1172);
    MOD_BATTLE[MOD_BT_TAIL_HALF]=500; MOD_BATTLE[MOD_BT_TAIL_DIV]=0;
    assert(modBtStatPower(586,9999)==1172);
    for (unsigned i=0;i<MOD_BT_SIZE;i++) MOD_BATTLE[i]=-1;
    assert(modBtStatPower(586,9999)==586);
}
'''
        for name,value in dict(POWERS=','.join(map(str,powers)),KNEE=rules['statDifferenceClamp'],
                               DIVISOR=rules['statDifferenceDivisor'],HALF=rules['tailHalfDifference'],
                               TAILDIV=rules['tailPowerDivisor']).items(): c=re.sub(r'\b'+name+r'\b',str(value),c)
        (folder/'test.c').write_text(c)
        subprocess.run(['cc','-std=c99','-Wall','-Werror','-fsanitize=undefined','-fno-sanitize-recover=all',
                        '-I'+str(folder),'-I'+str(tree/'include/dw'),str(folder/'test.c'),'-o',str(folder/'test')],check=True)
        proc=subprocess.Popen([str(folder/'test')],stdout=subprocess.PIPE,text=True)
        count=0
        for line in proc.stdout:
            power,diff,got=map(int,line.split()); want=stat_power(power,diff,rules)
            assert got==want,(power,diff,got,want);count+=1
        assert proc.wait()==0
        print(f'PASS {count:,} C/Python comparisons; {len(powers)} powers; all differences −9999..9999; original range identical; monotonic; UBSan clean')
    # Ensure all three real functions actually call the tested helper.
    for path in ('btl/battle_main.c','std/std_main.c','vs/vs_main.c'):
        source=(tree/'src'/path).read_text()
        assert 'modBtStatPower(modSpeciesMove(attacker->entity.type, move)->power, diff)' in source,path
        assert 'if (diff > BM(DIFF_CLAMP))' not in source,path
    print('PASS field/story, tournament and VS all use the tested helper')


if __name__=='__main__': main()
