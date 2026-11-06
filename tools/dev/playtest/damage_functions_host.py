#!/usr/bin/env python3
"""Compile verbatim old/new BTL, STD and VS damage functions with minimal stubs.

Compare the complete element/variance/finisher/difficulty/cap pipeline in native
C with UBSan. Arguments: original prepared decomp tree, patched decomp tree.
"""
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
import balance


def extract(path,name):
    source=path.read_text(); start=source.index('int32_t '+name+'(DigimonEntity *attacker, DigimonEntity *defender, int16_t move)\n{')
    end=source.index('\n}\n',start)+3
    return source[start:end]


def main():
    old,new=map(lambda p:Path(p).resolve(),sys.argv[1:3])
    rules=json.loads((ROOT/'content/tables/battle-formulas.json').read_text())['battleFormulas']
    encoded=balance.encode_named('battleFormulas',rules,None)
    import struct
    slots=struct.unpack('<'+'h'*(len(encoded)//2),encoded)
    header=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include "mod_battle.h"
#define DAMAGE_CAP 30000
#define MOD_DIFF_EASY 1
extern int MOD_OPT_DIFFICULTY, rr;
typedef struct {int type;} Entity;
typedef struct {Entity entity;struct {struct {int16_t off,def;} base;} stats;} DigimonEntity;
typedef struct {int16_t power;uint8_t special;} Move;
extern Move tech;
extern struct Para {uint8_t special[3];} para[2];
extern uint8_t TYPE_FACTORS[7][7];
extern Entity *ENTITY_TABLE[2];
extern struct Combat {struct {int16_t finisherChargeup[2];} player;} combat;
#define COMBAT_DATA_PTR (&combat)
#define DIGI_PARA(id) para[id]
#define MOD_DIFF_DAMAGE(attacker,defender,partner,dmg) \
 (MOD_OPT_DIFFICULTY != MOD_DIFF_EASY ? (dmg) : (Entity*)(attacker)==(partner) ? (dmg)*2 : (Entity*)(defender)==(partner) ? ((dmg)+1)/2 : (dmg))
static inline Move *modSpeciesMove(int id,int move) {(void)id;(void)move;return &tech;}
static inline int randomLimit(int n) {return rr%n;}
'''
    funcs=[('btl/battle_main.c','BTL_calculateDamage'),('std/std_main.c','STD_calculateDamage'),('vs/vs_main.c','VS_rollAttackOutcome')]
    with tempfile.TemporaryDirectory(prefix='damage-functions-') as temp:
        folder=Path(temp);(folder/'dw').mkdir();(folder/'dw/types.h').write_text('#include <stdint.h>\n')
        (folder/'stub.h').write_text(header)
        files=[]
        for label,tree in [('old',old),('new',new)]:
            src='#include "stub.h"\n'
            for path,name in funcs: src+=extract(tree/'src'/path,name).replace(name,name+'_'+label)+'\n'
            p=folder/(label+'.c');p.write_text(src);files.append(str(p))
        main='#include "stub.h"\n'
        for _,name in funcs:
            for label in ('old','new'):main+=f'int32_t {name}_{label}(DigimonEntity*,DigimonEntity*,int16_t);\n'
        main+='int16_t MOD_BATTLE[MOD_BT_SIZE]={'+','.join(map(str,slots))+'};\n'
        main+=r'''
int MOD_OPT_DIFFICULTY,rr;
Move tech;
struct Para para[2];
uint8_t TYPE_FACTORS[7][7];
Entity *ENTITY_TABLE[2];
struct Combat combat;
int main(void) {
    typedef int32_t (*Fn)(DigimonEntity*,DigimonEntity*,int16_t);
    Fn before[]={BTL_calculateDamage_old,STD_calculateDamage_old,VS_rollAttackOutcome_old};
    Fn after[]={BTL_calculateDamage_new,STD_calculateDamage_new,VS_rollAttackOutcome_new};
    int powers[]={0,1,586,722,32767}, factors[][3]={{2,2,2},{10,10,10},{20,20,20},{2,10,10},{20,10,20}}, moves[]={8,45,58};
    long count=0;
    DigimonEntity a={{0},{{0,0}}},b={{1},{{0,0}}};
    for(int f=0;f<3;f++) for(int p=0;p<5;p++) for(int e=0;e<5;e++)
    for(int side=0;side<2;side++) for(int easy=0;easy<2;easy++) for(int m=0;m<3;m++) {
        tech.power=powers[p]; tech.special=0;
        for(int i=0;i<3;i++) {para[0].special[i]=i;para[1].special[i]=i;TYPE_FACTORS[0][i]=factors[e][i];}
        ENTITY_TABLE[1]=side ? &b.entity : &a.entity;
        MOD_OPT_DIFFICULTY=easy;
        for(int d=-9999;d<=9999;d+=1) {
            a.stats.base.off=d>=0?d:0;b.stats.base.def=d<0?-d:0;
            rr=(d+9999)%101; combat.player.finisherChargeup[0]=d%3==0?40:d%3==1?41:80;
            int x=before[f](&a,&b,moves[m]),y=after[f](&a,&b,moves[m]);
            int effective=a.stats.base.off-(m==1?b.stats.base.def*30/100:b.stats.base.def);
            if(effective<=500 || m==2) assert(x==y);
            else {assert(y>=x);assert(y<= (f==2?9999:30000));}
            count++;
        }
    }
    /* Original reported example: mixed Air factors, no difficulty bonus. */
    tech.power=586;tech.special=0;MOD_OPT_DIFFICULTY=0;rr=3;
    a.stats.base.off=4430;b.stats.base.def=600;ENTITY_TABLE[1]=&a.entity;
    TYPE_FACTORS[0][0]=2;TYPE_FACTORS[0][1]=10;TYPE_FACTORS[0][2]=10;
    for(int f=0;f<3;f++) {
        assert(before[f](&a,&b,8)==798);
        assert(after[f](&a,&b,8)==1145);
    }
    printf("PASS %ld complete old/new damage comparisons: BTL/STD/VS, all stat differences, elements, both sides, EASY, counter, finisher charge and caps; UBSan clean\n",count);
}
'''
        (folder/'main.c').write_text(main)
        subprocess.run(['cc','-std=c99','-O2','-Wall','-Werror','-fsanitize=undefined','-fno-sanitize-recover=all',
                        '-I'+str(folder),'-I'+str(new/'include/dw'),*files,str(folder/'main.c'),'-o',str(folder/'test')],check=True)
        subprocess.run([str(folder/'test')],check=True)


if __name__=='__main__':main()
