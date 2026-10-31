#!/usr/bin/env python3
"""Compile the real BTL target scorer/selector on the host with authored data.

Run: python3 tools/test_target_score.py [build/decomp-int]
"""
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def function(source, name):
    match = re.search(r'^\w+ ' + name + r'\([^;]*?\)\n\{', source, re.M)
    assert match, name
    return source[match.start():source.index('\n}', match.end()) + 2]


def main():
    work = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'build/decomp-int'
    source = (work / 'src/btl/battle_main.c').read_text()
    formula = json.loads((ROOT / 'content/tables/battle-formulas.json').read_text())['battleFormulas']['ai']['targetScore']
    factors = json.loads((ROOT / 'content/tables/type-factors.json').read_text())['typeFactors']
    constants = dict(zip(('TSCORE_INV0', 'TSCORE_INV1', 'TSCORE_INV2', 'TSCORE_INV3'), formula['invertedFactor']))
    constants.update(TSCORE_DEF=formula['defenseMax'], TSCORE_DIV=formula['divisor'])
    code = '#include <stdint.h>\n#include <assert.h>\n#include <stdio.h>\n'
    code += (work / 'include/dw/caps.h').read_text()
    code += '\n'.join(f'#define {k} {v}' for k, v in constants.items()) + '\n'
    code += '#define BM(k) (k)\n#define BMD(v,k) ((k) ? (v)/(k) : 0)\n'
    code += 'uint8_t TYPE_FACTORS[7][7] = ' + str(factors).replace('[', '{').replace(']', '}') + ';\n'
    code += r'''
typedef struct { struct { int16_t hp, def; } base; struct { int16_t currentHP; } current; } Stats;
typedef struct { int type; } Entity;
typedef struct { Entity entity; Stats stats; } DigimonEntity;
typedef struct { uint8_t targetId; } FighterData;
struct { uint8_t special[1]; } para[4];
#define DIGI_PARA(t) para[t]
struct { FighterData fighter[4]; struct { int entityIds[4]; } player; } combat;
#define COMBAT_DATA_PTR (&combat)
Entity *ENTITY_TABLE[4];
int ENEMY_COUNT = 3, dead[4];
int BTL_isFighterDefeated(int i) { return dead[i]; }
int16_t BTL_calculateTargetScore(DigimonEntity *, DigimonEntity *);
'''
    code += function(source, 'BTL_calculateTargetScore') + '\n'
    code += function(source, 'BTL_getWeakestEnemy') + '\n'
    code += r'''
int main(void) {
    DigimonEntity d[4] = {0};
    for (int i=0; i<4; i++) {
        d[i].entity.type=i; ENTITY_TABLE[i]=&d[i].entity;
        combat.player.entityIds[i]=i;
    }
    d[0].stats.base.hp=100;
    para[0].special[0]=1; para[1].special[0]=2;
    para[2].special[0]=2; para[3].special[0]=2;
    d[0].stats.base.def=9999; d[0].stats.current.currentHP=100;
    combat.fighter[0].targetId=0xff;
    int16_t score=-1, choice=-1;
    BTL_getWeakestEnemy(&d[0].entity,combat.fighter,&score,&choice);
    printf("Defense 9999, full HP, inverse 20: score=%d target=%d\n",score,choice);
    fflush(stdout);
    assert(choice==1);
    /* All legal positive int16 stats, every first-specialty matchup, every HP percent.
       Also proves exact old-range results, including the intermediate integer divisions. */
    for (int a=0; a<7; a++) for (int b=0; b<7; b++) {
        para[0].special[0]=a; para[1].special[0]=b;
        int factor=TYPE_FACTORS[a][b], inv=factor;
        if (factor==20) inv=TSCORE_INV0;
        if (factor==15) inv=TSCORE_INV1;
        if (factor==5) inv=TSCORE_INV2;
        if (factor==2) inv=TSCORE_INV3;
        for (int def=0; def<=32767; def++) for (int hp=0; hp<=100; hp++) {
            d[0].stats.base.def=def; d[0].stats.current.currentHP=hp;
            int expected=hp+BMD(inv*BMD((def>OLD_STAT_CAP?OLD_STAT_CAP:def)*100,TSCORE_DEF),TSCORE_DIV);
            int score=BTL_calculateTargetScore(d,d+1);
            assert(score==expected && score<1000);
            if (def<=999) assert(score==hp+BMD(inv*BMD(def*100,TSCORE_DEF),TSCORE_DIV));
        }
    }
    /* Real selector: extreme Defense must yield a live target; preserve ties,
       current-target exclusion, defeated opponents and the no-candidate sentinel. */
    para[0].special[0]=1; para[1].special[0]=2; para[2].special[0]=2; para[3].special[0]=2;
    d[0].stats.base.def=32767; d[0].stats.current.currentHP=100;
    combat.fighter[0].targetId=0xff;
    BTL_getWeakestEnemy(&d[0].entity,combat.fighter,&score,&choice); assert(choice==1);
    dead[1]=1;
    BTL_getWeakestEnemy(&d[0].entity,combat.fighter,&score,&choice); assert(choice==2);
    combat.fighter[0].targetId=2;
    BTL_getWeakestEnemy(&d[0].entity,combat.fighter,&score,&choice); assert(choice==3);
    dead[3]=1;
    BTL_getWeakestEnemy(&d[0].entity,combat.fighter,&score,&choice); assert(choice==0xff);
    puts("PASS: 162168832 scores; exact old-range decisions, int16 cheat bounds, selector ties/exclusions");
}
'''
    with tempfile.TemporaryDirectory() as tmp:
        c = Path(tmp) / 'target_score.c'
        exe = Path(tmp) / 'target_score'
        c.write_text(code)
        subprocess.run(['cc', '-std=c99', '-O2', '-Wall', '-Wextra', '-Wno-unused-but-set-variable',
                        '-fsanitize=undefined', '-fno-sanitize-recover=undefined',
                        '-o', str(exe), str(c)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    main()
