#!/usr/bin/env python3
"""Compile actual field, tournament and versus buff functions with the shared clamp.

Run: python3 tools/dev/playtest/buff_caps_host.py build/decomp-dev
Includes every configured buff, repeated casts, cap boundaries and unchanged
stats. Native game rendering is stubbed; emulator proofs remain separate.
"""
import argparse
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
import balance


def extract(path, name, result='void'):
    source = path.read_text()
    match = re.search(result + r' ' + name + r'\([^)]*\)\n[^{}]*?\{', source)
    if not match:
        raise ValueError(f'{path}: cannot extract {name}')
    return source[match.start():source.index('\n}', match.end()) + 2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tree', type=Path)
    args = parser.parse_args()
    tree = args.tree.resolve()
    rules = json.loads((ROOT / 'content/tables/battle-formulas.json').read_text())['battleFormulas']
    encoded = balance.encode_named('battleFormulas', rules, None)
    values = struct.unpack('<' + 'h' * (len(encoded) // 2), encoded)
    source = r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#include "mod_battle.h"
#include "caps.h"
typedef struct { struct { int16_t off, def, speed; } base; } Stats;
typedef struct { int type; } Entity;
typedef struct { Entity entity; Stats stats; } DigimonEntity;
static void addEntityText(Entity *e,int slot,int color,int value,int flag) {
    (void)e;(void)slot;(void)color;(void)value;(void)flag;
}
'''
    source += '\nint16_t MOD_BATTLE[MOD_BT_SIZE]={' + ','.join(map(str, values)) + '};\n'
    source += extract(tree / 'src/main/item.c', 'addWithLimit') + '\n'
    for folder, file, tag in (('btl', 'battle_main', 'BTL'), ('std', 'std_main', 'STD'), ('vs', 'vs_main', 'VS')):
        path = tree / f'src/{folder}/{file}.c'
        source += extract(path, tag + '_buffStats') + '\n'
        source += extract(path, tag + '_applyBuffMove', 'int32_t') + '\n'
    source += r'''
int main(void) {
    int32_t (*apply[])(DigimonEntity*,int32_t,int16_t)={BTL_applyBuffMove,STD_applyBuffMove,VS_applyBuffMove};
    int bases[]={1,998,999,1000,1500,9000,9998,9999},cases=0,failed=0;
    for(int arena=0;arena<3;arena++)for(int row=0;row<5;row++)for(int b=0;b<8;b++) {
        DigimonEntity d={0};
        d.stats.base.off=d.stats.base.def=d.stats.base.speed=bases[b];
        for(int cast=0;cast<12;cast++) {
            int16_t expected[3]={d.stats.base.off,d.stats.base.def,d.stats.base.speed};
            int percent[3]={BM(BUFF_OFF0+row),BM(BUFF_DEF0+row),BM(BUFF_SPD0+row)};
            for(int stat=0;stat<3;stat++) {
                int sum=expected[stat]+expected[stat]*percent[stat]/100;
                expected[stat]=sum>STAT_CAP?STAT_CAP:sum;
            }
            assert(apply[arena](&d,0,BMV(BUFF_MOVE0+row))==1);
            int16_t got[3]={d.stats.base.off,d.stats.base.def,d.stats.base.speed};
            for(int stat=0;stat<3;stat++) {
                cases++;
                if(got[stat]!=expected[stat]) {
                    if(failed++<8) printf("FAIL arena=%d move=%d base=%d cast=%d stat=%d got=%d expected=%d\n",
                       arena,BMV(BUFF_MOVE0+row),bases[b],cast,stat,got[stat],expected[stat]);
                }
            }
        }
        Stats before=d.stats;
        assert(apply[arena](&d,0,255)==0);
        assert(d.stats.base.off==before.base.off && d.stats.base.def==before.base.def && d.stats.base.speed==before.base.speed);
    }
    printf("%d buff stat checks, %d failures; all three arenas, all five moves, repeated casts and 9999 cap\n",cases,failed);
    return failed!=0;
}
'''
    with tempfile.TemporaryDirectory(prefix='buff-caps-') as tmp:
        directory = Path(tmp)
        (directory / 'dw').mkdir()
        (directory / 'dw/types.h').write_text('#include <stdint.h>\n')
        (directory / 'test.c').write_text(source)
        subprocess.run(['cc', '-std=gnu99', '-O2', '-Wno-deprecated-non-prototype',
                        '-fsanitize=undefined', '-fno-sanitize-recover=all',
                        '-I'+str(directory), '-I'+str(tree / 'include/dw'),
                        str(directory / 'test.c'), '-o', str(directory / 'test')], check=True)
        return subprocess.run([str(directory / 'test')]).returncode


if __name__ == '__main__':
    sys.exit(main())
