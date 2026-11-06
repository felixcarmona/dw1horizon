#!/usr/bin/env python3
"""Compile actual native/custom evolution-item eligibility and handler code."""
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
    item = json.loads((ROOT / 'content/items/124-dolph-fin.json').read_text())
    assert item['id'] == 124 and item['value'] == 5000 and item['droppable'] == 1
    assert json.loads((ROOT / 'content/items/92-north-star.json').read_text())['evolution_target'] == 24
    rules = json.loads((ROOT / 'content/tables/evolution-rules.json').read_text())['evolutionItemRules']
    assert len(rules) == 4 and dict(item=124, target=238, partnerLevel=3).items() <= rules[-1].items()
    partner = (tree / 'src/main/partner_impl.c').read_text()
    macro = re.search(r'^#define ITEM_EVOLUTION_TARGET\(item\).*$', partner, re.M)[0]
    refusal = body(partner, 'if (((item >= 0x47)')
    quest = partner[partner.index('if ((item >= 0x73)'):partner.index('if ((item >= 0x21)')]
    item_c = (tree / 'src/main/item.c').read_text()
    functions = re.findall(r'\(ItemFunction\)\w+|\bNULL\b', item_c.split('ItemFunction ITEM_FUNCTIONS[NUM_ITEMS] = {')[1].split('};')[0])
    assert len(functions) == 128 and functions[124] == '(ItemFunction)handleEvoItems'
    handler = body(item_c, 'void handleEvoItems(int16_t item)')
    lookup = body((tree / 'src/main/evolution.c').read_text(), 'ModEvoItem *getModEvoItem(int32_t item)')
    stage = body((tree / 'src/main/mod_species.c').read_text(), 'int32_t modNativeItemTargetLevel(int32_t type)')
    code = r'''
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
#include <stddef.h>
#define LEVEL_MEGA 6
#define LEVEL_ULTIMATE 5
#define MOD_EVO_ITEM_MAX 4
struct Para { int level; } data[512];
#define DIGI_PARA(t) data[t]
struct Entity { int type; } entity, *ENTITY_TABLE[2]={0,&entity};
struct Partner { struct { struct { int type; } entity; } digimonEntity; } PARTNER_ENTITY;
typedef struct { int16_t item, target, level; } ModEvoItem;
uint8_t EVOLUTION_ITEM_TARGET[44];
int EVOLUTION_TARGET=-1, enabled=1, consumed, closed, tamerState, partnerState;
int modSpeciesAllowed(int type) { return enabled || type<66; }
void removeTamerItem(void) { consumed++; }
void closeInventoryBoxes(void) { closed++; }
void tamerSetState(int n) { tamerState=n; }
void partnerSetState(int n) { partnerState=n; }
'''
    code += 'ModEvoItem MOD_EVO_ITEMS[4]={' + ','.join('{%d,%d,%d}' % (r['item'],r['target'],r['partnerLevel']) for r in rules) + '};\n'
    code += stage + '\n' + lookup + '\n' + macro + '\nint refuses(int item) {\n' + quest + refusal + '\nreturn 0;\n}\n' + handler
    code += r'''
int main(void) {
 data[238].level=4; entity.type=PARTNER_ENTITY.digimonEntity.entity.type=4;
 EVOLUTION_ITEM_TARGET[92-71]=24; data[24].level=5;
 for(int level=1;level<=6;level++) {
  data[4].level=level;
  assert(refuses(124)==(level!=3)); assert(refuses(92)==(level!=4));
 }
 assert(refuses(123)); /* The real fridge key remains inedible. */
 data[4].level=3; assert(!refuses(124)); handleEvoItems(124);
 assert(EVOLUTION_TARGET==238 && consumed==1 && closed==1 && tamerState==6 && partnerState==13);
 EVOLUTION_TARGET=-1; consumed=closed=0; enabled=0;
 assert(refuses(124)); handleEvoItems(124); assert(EVOLUTION_TARGET==-1 && !consumed && !closed);
 data[24].level=4; assert(!refuses(92)); handleEvoItems(92); assert(EVOLUTION_TARGET==24);
 enabled=1; data[24].level=5; data[4].level=4; consumed=0; handleEvoItems(92);
 assert(EVOLUTION_TARGET==24 && consumed==1);
 EVOLUTION_ITEM_TARGET[111-71]=59; data[59].level=6;
 for (int target=59;target<=60;target++) {
  int item=target==59?111:112;
  EVOLUTION_ITEM_TARGET[item-71]=target; data[target].level=6;
  for(int level=1;level<=6;level++) {
   data[4].level=level; EVOLUTION_TARGET=-1; consumed=0;
   assert(refuses(item)==(level!=5)); handleEvoItems(item);
   assert(consumed==(level==5)); assert(EVOLUTION_TARGET==(level==5?target:-1));
  }
  /* Explicit off levels preserve the original Champion item stage. */
  data[target].level=5;
  for(int level=1;level<=6;level++) {
   data[4].level=level; assert(refuses(item)==(level!=4));
  }
 }
 data[65].level=6;
 for(int level=1;level<=6;level++) {
  data[4].level=level; EVOLUTION_TARGET=-1; consumed=0;
  assert(refuses(127)==(level!=5)); handleEvoItems(127);
  assert(consumed==(level==5)); assert(EVOLUTION_TARGET==(level==5?65:-1));
 }
 data[63].level=5;
 for(int level=1;level<=6;level++) {
  data[4].level=level; EVOLUTION_TARGET=-1; consumed=0;
  assert(refuses(126)==(level!=4)); handleEvoItems(126);
  assert(consumed==(level==4)); assert(EVOLUTION_TARGET==(level==4?63:-1));
 }
 puts("PASS actual item code: Dolph Fin Rookie -> Dolphmon, all wrong stages refused; NEW DIGIMON off refuses without consumption; North Star -> Ultimate Whamon from Champion (Rookie with off); all three Mega items require Ultimate and reject every wrong stage; fridge key inedible; 128 items and four custom rules");
}
'''
    with tempfile.TemporaryDirectory() as folder:
        src = Path(folder) / 'items.c'; exe = Path(folder) / 'items'
        src.write_text(code)
        subprocess.run(['cc', '-std=c99', '-Wall', '-Werror', str(src), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)
    for lang in ('ours', 'es', 'pt-br', 'fr', 'de', 'it', 'ja', 'ca'):
        names = json.loads((ROOT / 'text' / lang / 'names.json').read_text())
        assert len(names['main.ITEM_NAMES.124']) <= 11
        assert ('ルカモン' if lang == 'ja' else 'Dolphmon') in names['main.ITEM_DESCS.124']
        assert ('ホエーモン' if lang == 'ja' else 'Whamon') in names['main.ITEM_DESCS.92']
    print('PASS all eight item-name lengths, Dolph Fin descriptions and restored North Star descriptions')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tree', type=Path, default=ROOT / 'build/decomp-dev')
    check(p.parse_args().tree)
