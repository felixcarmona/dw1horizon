#!/usr/bin/env python3
"""Compile actual HARD helpers and old/new BTL/STD damage; verify save behavior separately.

Usage: hard_host.py HARD_TREE, or hard_host.py BASELINE_TREE HARD_TREE
"""
import json
from pathlib import Path
import struct
import subprocess
import shutil
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'tools'),str(Path(__file__).parent)]
import balance
from damage_functions_host import extract

def main():
    temporary=None
    if len(sys.argv)==2:
        after=Path(sys.argv[1]).resolve()
        temporary=tempfile.TemporaryDirectory(prefix='hard-baseline-')
        before=Path(temporary.name)
        for rel in ('btl/battle_main.c','std/std_main.c','vs/vs_main.c'):
            target=before/'src'/rel;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(after/'src'/rel,target)
        subprocess.run(['git','apply','-R','--include=src/btl/battle_main.c',
                        '--include=src/std/std_main.c','--include=src/vs/vs_main.c',
                        str(ROOT/'mods/patches/Add-HARD-single-player-difficulty.patch')],
                       cwd=before,check=True)
    else:
        before,after=[Path(v).resolve() for v in sys.argv[1:3]]
    setup=(after/'src/btl/battle_setup.c').read_text()
    assert setup.index('dst = (int16_t *)&INITIAL_COMBAT_STATS[i]') < setup.index('modHardEnemy(')
    assert setup.index('modHardEnemy(') < setup.index('BTL_addEnemyHPBars();')
    rules=json.loads((ROOT/'content/tables/battle-formulas.json').read_text())['battleFormulas']
    encoded=balance.encode_named('battleFormulas',rules,None)
    slots=struct.unpack('<'+'h'*(len(encoded)//2),encoded)
    with tempfile.TemporaryDirectory(prefix='hard-host-') as d:
        p=Path(d);(p/'dw').mkdir()
        (p/'dw/types.h').write_text('#include <stdint.h>\n')
        (p/'dw/entity.h').write_text('''#ifndef HOST_ENTITY_H
#define HOST_ENTITY_H
#include <stdint.h>
typedef struct {int type;} Entity;
typedef struct {struct {int16_t hp,mp,off,def,speed,brain;} base;struct {int16_t currentHP,currentMP;} current;} Stats;
typedef struct {Entity entity;Stats stats;} DigimonEntity;
#endif
''')
        options=(after/'include/dw/mod_options.h').read_text()
        (p/'dw/mod_options.h').write_text('#ifndef HOST_OPTIONS_H\n#define HOST_OPTIONS_H\n'+options[options.index('#define MOD_DIFF_NORMAL'):])
        stub='''#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <dw/mod_hard.h>
#define DAMAGE_CAP 30000
typedef struct {int16_t power;uint8_t special;} Move;
Move tech;
struct {uint8_t special[3];} para[2];
uint8_t TYPE_FACTORS[7][7];
Entity *ENTITY_TABLE[2];
struct {struct {int16_t finisherChargeup[2];} player;} combat;
#define COMBAT_DATA_PTR (&combat)
#define DIGI_PARA(id) para[id]
int32_t MOD_OPT_DIFFICULTY;
int rr;
int32_t BTL_HARD_ZERO_DAMAGE, STD_HARD_ZERO_DAMAGE;
static inline Move *modSpeciesMove(int id,int move){return &tech;}
static inline int randomLimit(int n){return rr%n;}
'''
        code=stub+'\nint16_t MOD_BATTLE[MOD_BT_SIZE]={'+','.join(map(str,slots))+'};\n'
        for rel,name in [('btl/battle_main.c','BTL_calculateDamage'),('std/std_main.c','STD_calculateDamage'),('vs/vs_main.c','VS_rollAttackOutcome')]:
            code+=extract(before/'src'/rel,name).replace(name,name+'_reference').replace('DAMAGE_CAP','2147483647')+'\n'
            code+=extract(after/'src'/rel,name)+'\n'
        code+='''
int main(void){
    DigimonEntity a={{0},{{10000,10000,800,750,700,600},{10000,10000}}};
    DigimonEntity b={{1},{{9999,9999,999,800,800,800},{9999,9999}}};
    Stats initial=b.stats;
    for(int mode=0;mode<2;mode++){
        MOD_OPT_DIFFICULTY=mode;b.stats=initial;modHardEnemy(&b.stats);
        assert(!memcmp(&b.stats,&initial,sizeof(initial)));
    }
    MOD_OPT_DIFFICULTY=MOD_DIFF_HARD;b.stats=initial;modHardEnemy(&b.stats);
    assert(b.stats.base.hp==10998&&b.stats.current.currentHP==10998);
    assert(b.stats.base.mp==9999&&b.stats.current.currentMP==9999);
    assert(b.stats.base.off==1498&&b.stats.base.def==840);
    assert(b.stats.base.speed==920&&b.stats.base.brain==1200);
    b.stats.base.hp=30000;b.stats.current.currentHP=7500;modHardEnemy(&b.stats);
    assert(b.stats.base.hp==30000&&b.stats.current.currentHP==7500);
    assert(modHardScale(30000,MOD_BT_HARD_HP,30000)==30000);
    assert(modHardScale(9999,MOD_BT_HARD_OFF,9999)==9999);
    int16_t factor=MOD_BATTLE[MOD_BT_HARD_HP];MOD_BATTLE[MOD_BT_HARD_HP]=-1;
    assert(modHardScale(1000,MOD_BT_HARD_HP,30000)==1000);MOD_BATTLE[MOD_BT_HARD_HP]=factor;
    int values[]={0,100,500,650,800,999,1500,4000,9999};
    int powers[]={1,255,586,32767},moves[]={8,45,58},charges[]={0,40,41,80};
    typedef int32_t (*Fn)(DigimonEntity*,DigimonEntity*,int16_t);
    Fn current[]={BTL_calculateDamage,STD_calculateDamage,VS_rollAttackOutcome};
    Fn reference[]={BTL_calculateDamage_reference,STD_calculateDamage_reference,VS_rollAttackOutcome_reference};
    long count=0;
    for(int field=0;field<3;field++)for(int mode=0;mode<3;mode++)
    for(int side=0;side<2;side++)for(int o=0;o<9;o++)for(int d=0;d<9;d++)
    for(int p=0;p<4;p++)for(int m=0;m<3;m++)for(int c=0;c<4;c++)for(int r=0;r<101;r++){
        if(field==2&&mode!=0)continue;
        a.stats.base.off=values[o];b.stats.base.def=values[d];
        for(int i=0;i<3;i++){para[0].special[i]=i;para[1].special[i]=i;TYPE_FACTORS[0][i]=i==0?2:i==1?10:20;}
        ENTITY_TABLE[1]=side?&b.entity:&a.entity;
        tech.power=powers[p];tech.special=0;rr=r;combat.player.finisherChargeup[0]=charges[c];
        MOD_OPT_DIFFICULTY=mode;
        int got=current[field](&a,&b,moves[m]);
        int rawDef=values[d], effective=rawDef, excess=0;
        if(moves[m]==45)effective=effective*MOD_BATTLE[MOD_BT_GUARD_PCT]/100;
        int knee=values[o]>999?values[o]:999;
        if(rawDef>999&&effective>knee){excess=effective-knee;effective=knee;}
        int delta=values[o]-effective,clamped=delta>500?500:delta < -500?-500:delta;
        int base=powers[p]+clamped*powers[p]/500;
        if(delta>500)base+=powers[p]*(delta-500)/((delta-500+500)*MOD_BATTLE[MOD_BT_TAIL_DIV]);
        if(excess)base=base*1000/(1000+excess);
        int roll=rr%21+90;
        int want=(base*32/30)*roll/100;
        if(mode==MOD_DIFF_HARD&&side){
            int zero=values[o]>500?500:values[o];
            int z=powers[p]+zero*powers[p]/500;
            if(values[o]>500)z+=powers[p]*(values[o]-500)/((values[o]-500+500)*MOD_BATTLE[MOD_BT_TAIL_DIV]);
            int floor=(z*32/30)*roll/100;
            if(floor>30000)floor=30000;
            if(moves[m]<58)assert(got*100>=floor*15);
            floor=(floor*15+99)/100;
            if(want<floor)want=floor;
        }
        if(moves[m]>=58){
            int pw=powers[p];
            if(mode==MOD_DIFF_HARD&&side)pw=pw*150/100>32767?32767:pw*150/100;
            want=(values[o]+pw)*32/30;
            if((!side||field==2)&&charges[c]>=41)want=want*charges[c]/40;
            if(side&&field!=2)want=want*(rr%101+100)/100;
            want=want*roll/100;
        }
        if(mode==MOD_DIFF_EASY)want=side?(want+1)/2:want*2;
        if(mode==MOD_DIFF_HARD&&!side)want=want*95/100;
        if(want<1)want=1;if(want>(field==2?9999:30000))want=field==2?9999:30000;
        if(mode!=MOD_DIFF_HARD&&rawDef<=999){
            int old=reference[field](&a,&b,moves[m]);
            if(old>(field==2?9999:30000))old=field==2?9999:30000;
            assert(old==got);
        }
        assert(got==want);count++;
    }
    MOD_OPT_DIFFICULTY=MOD_DIFF_HARD;
    long blocks=0;
    for(int zero=0;zero<=30000;zero++)for(int pct=10;pct<=30;pct++){
        int chip=modHardBlockedFloor(modHardMinimum(zero)*pct/100,zero,pct);
        if(chip<1)chip=1;
        int reference=zero*pct/100;if(reference<1)reference=1;
        assert(chip*100>=reference*15);blocks++;
    }
    printf("PASS %ld blocked-floor comparisons: final applied chip meets the minimum\\n",blocks);
    printf("PASS %ld actual BTL/STD/VS comparisons: EASY/NORMAL <=999 unchanged; reciprocal Defense and HARD floor/ordinary/counter/finishers, both sides, charge, variance and caps; UBSan clean\\n",count);
    return 0;
}
'''
        (p/'check.c').write_text(code)
        subprocess.run(['cc','-std=c99','-fsanitize=undefined','-fno-sanitize-recover=all','-I'+str(p),'-I'+str(after/'include'),str(p/'check.c'),'-o',str(p/'check')],check=True)
        subprocess.run([str(p/'check')],check=True)
    if temporary:temporary.cleanup()
if __name__=='__main__':main()
