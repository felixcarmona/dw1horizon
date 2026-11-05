#!/usr/bin/env python3
"""Compile the actual evolution-item handler and native-item refusal branch."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]


def body(source, signature):
    start = source.index(signature)
    at = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[at] == '{') - (source[at] == '}')
        at += 1
    return source[start:at]


def check(tree):
    target = json.loads((ROOT / 'content/items/92-north-star.json').read_text())['evolution_target']
    assert target == 238
    partner = (tree / 'src/main/partner_impl.c').read_text()
    macro = re.search(r'^#define ITEM_EVOLUTION_TARGET\(item\).*$', partner, re.M)[0]
    refusal = body(partner, 'if (((item >= 0x47)')
    handler = body((tree / 'src/main/item.c').read_text(), 'void handleEvoItems(int16_t item)')
    code = r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#include <stddef.h>
#define LEVEL_MEGA 6
#define LEVEL_ULTIMATE 5
struct Para { int level; } data[512];
#define DIGI_PARA(t) data[t]
struct Entity { int type; } entity, *ENTITY_TABLE[2]={0,&entity};
struct Partner { struct { struct { int type; } entity; } digimonEntity; } PARTNER_ENTITY;
typedef struct { int target, level; } ModEvoItem;
uint8_t EVOLUTION_ITEM_TARGET[44];
int EVOLUTION_TARGET=-1, enabled=1, consumed, closed, tamerState, partnerState;
int modOriginalLevel(int type) { return data[type].level; }
int modSpeciesAllowed(int type) { return enabled || type<66; }
ModEvoItem *getModEvoItem(int item) { return NULL; }
void removeTamerItem(void) { consumed++; }
void closeInventoryBoxes(void) { closed++; }
void tamerSetState(int n) { tamerState=n; }
void partnerSetState(int n) { partnerState=n; }
'''
    code += '\n' + macro + '\nint refuses(int item) {\n' + refusal + '\nreturn 0;\n}\n' + handler
    code += f'\nint main(void) {{ EVOLUTION_ITEM_TARGET[92-71]={target};\n'
    code += r'''
 data[238].level=4; entity.type=PARTNER_ENTITY.digimonEntity.entity.type=4; data[4].level=3;
 assert(!refuses(92)); handleEvoItems(92);
 assert(EVOLUTION_TARGET==238 && consumed==1 && closed==1 && tamerState==6 && partnerState==13);
 EVOLUTION_TARGET=-1; consumed=closed=0;
 for(int stage=1;stage<=6;stage++) {
  data[4].level=stage;
  if(stage==3) { assert(!refuses(92)); continue; }
  assert(refuses(92)); handleEvoItems(92); assert(EVOLUTION_TARGET==-1 && !consumed && !closed);
 }
 data[4].level=3; enabled=0;
 assert(refuses(92)); handleEvoItems(92); assert(EVOLUTION_TARGET==-1 && !consumed && !closed);
 puts("PASS actual item handler/refusal branch: Rookie accepts North Star -> Dolphmon 238; all five non-Rookie stages rejected; imported target unavailable with NEW DIGIMON off and item not consumed");
}
'''
    with tempfile.TemporaryDirectory() as folder:
        src = Path(folder) / 'north.c'; exe = Path(folder) / 'north'
        src.write_text(code)
        subprocess.run(['cc', '-std=c99', '-Wall', '-Werror', str(src), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)
    for lang in ('ours', 'es', 'pt-br', 'fr', 'de', 'it', 'ja', 'ca'):
        desc = json.loads((ROOT / 'text' / lang / 'names.json').read_text())['main.ITEM_DESCS.92']
        assert ('ルカモン' if lang == 'ja' else 'Dolphmon') in desc, (lang, desc)
        assert 'Whamon' not in desc and 'ホエーモン' not in desc
    print('PASS North Star description targets Dolphmon in all eight languages')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tree', type=Path, default=ROOT / 'build/decomp-dev')
    check(p.parse_args().tree)
