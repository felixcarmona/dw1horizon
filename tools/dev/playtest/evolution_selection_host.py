#!/usr/bin/env python3
"""Reproduce Salamon's four-mistake evolution with the actual patched C picker.

python3 tools/dev/playtest/evolution_selection_host.py build/decomp-int [--ref v0.0.7]
No disc required. The supplied tree must have that ref's patch series applied.
Model availability and raised flags are controlled fixtures; no evolution animation,
clock tick, archive loading or emulator execution is simulated.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
import evo_check as E


def function(source, name):
    match = re.search(r'^(?:static __attribute__\(\(noinline\)\) )?(?:int32_t|int16_t|int8_t|char \*) ?'
                      + name + r'\([^;]*?\)\s*\{', source, re.M)
    if not match:
        raise ValueError('Missing C function: ' + name)
    return source[match.start():source.index('\n}', match.end()) + 2] + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tree', type=Path)
    parser.add_argument('--ref', help='read species and rules from this Git ref')
    args = parser.parse_args()

    def read(path):
        return (subprocess.check_output(['git', 'show', f'{args.ref}:{path}'], cwd=ROOT).decode()
                if args.ref else (ROOT / path).read_text())

    parent = json.loads(read('content/species/221-salamon.json'))
    ids = parent['evolution']['to']
    # Filenames are only locators; the selected ref supplies every record's contents.
    species = {t: json.loads(read(str(next((ROOT / 'content/species').glob(f'{t}-*.json')).relative_to(ROOT))))
               for t in ids}
    reqs = {t: s['evolution']['requirements'] for t, s in species.items()}
    assert all(s['level'] == 'champion' for s in species.values())
    levels = {t: 4 for t in ids}
    score = json.loads(read('content/tables/evolution-rules.json'))['evolutionFormula']['score']
    assert score == dict(weightTolerance=5, pointCareMistakes=1, pointWeight=1, pointStats=1,
                         pointBonus=1, hpMpDiv=10, raisedBonus=1, passPoints=3)
    assert reqs[234]['care'] == 1 and reqs[234]['flags'] & 16
    stats = dict(zip(E.STATS, (2000, 1000, 100, 200, 100, 100)))
    assert [E.score(221, reqs[t], 4, stats, 4, 10, target=t) for t in ids] == [2, 2, 3, 4, 1]
    assert E.pick(221, ids, reqs, levels, stats, 4, 10, 'stats') == 234

    code = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef int16_t DigimonId;
typedef struct {int16_t digimon,hp,mp,offense,defense,speed,brain,care,weight,discipline,happiness,battles,techs; uint8_t flags;} EvoRequirements;
typedef struct {int16_t hp,mp,off,def,speed,brain;} BaseStats;
typedef struct {int16_t careMistakes,weight,discipline,happiness,battles,evoTimer;} PartnerPara;
struct {struct {struct {BaseStats base;} stats;} digimonEntity;} PARTNER_ENTITY;
PartnerPara PARTNER_PARA;
EvoRequirements rows[512];
struct {int level;} para[512];
struct {int targetDigimon;} gains[512];
struct {DigimonId to[6];} path;
#define EVO_REQ_ROW(t) rows[t]
#define DIGI_PARA(t) para[t]
#define EVO_GAINS_ROW(t) gains[t]
enum {EVO_MET_CARE=1,EVO_MET_WEIGHT=2,EVO_MET_STATS=4,EVO_MET_BONUS=8};
enum {MOD_EVF_SCORE_WEIGHT_TOL,MOD_EVF_SCORE_HPMP_DIV,MOD_EVF_SCORE_POINT_CARE,
 MOD_EVF_SCORE_POINT_WEIGHT,MOD_EVF_SCORE_POINT_STATS,MOD_EVF_SCORE_POINT_BONUS,
 MOD_EVF_SCORE_RAISED_BONUS,MOD_EVF_SCORE_PASS};
int16_t MOD_EVO_FORMULA[]={5,10,1,1,1,1,1,3};
enum {MOD_EVO_FALLBACK_HOURS,MOD_EVO_FALLBACK_TARGET};
int16_t MOD_EVO_TIMING[]={96,11};
int raised[512];
#define getEvolutionPath(t) (&path)
int isPartnerModelFit(int t){return 1;}
int modSpeciesAllowed(int t){return 1;}
int hasDigimonRaised(int t){return raised[t];}
int8_t getNumMasteredMoves(void){return 0;}
int32_t evoTargetWeight(int cur,DigimonId t){return rows[t].weight;}
'''
    source = (args.tree / 'src/main/evolution.c').read_text()
    for name in ('evoAmt', 'evoPassPoints', 'evoPartnerTopStat', 'evoRequirementsMet',
                 'evoRequirementPoints', 'calculateRequirementScore', 'getRookieEvolutionTarget'):
        code += function(source, name)
    # Exercise the actual popup range formatter as well as the shared scoring bits.
    menu = (args.tree / 'src/main/game_menu.c').read_text()
    code += 'char *chartNumber(char *p,int32_t n){return p+sprintf(p,"%d",n);}\n'
    code += function(menu, 'chartRange')
    code += 'int main(void){\n'
    for i, t in enumerate(ids + [-1]):
        code += f'path.to[{i}]={t};\n'
    for t, r in reqs.items():
        for key, value in r.items():
            code += f'rows[{t}].{key}={value};\n'
        code += f'para[{t}].level=4;gains[{t}].targetDigimon={t};\n'
    code += r'''
 PARTNER_ENTITY.digimonEntity.stats.base=(BaseStats){2000,1000,100,200,100,100};
 PARTNER_PARA.weight=10;PARTNER_PARA.evoTimer=72;
 // Inclusive care boundary: 0 and 1 pass; 2 and 4 lose only the care point.
 for(int care=0;care<=4;care++){
  PARTNER_PARA.careMistakes=care;
  int met=evoRequirementsMet(221,234,1,0);
  assert(!!(met&EVO_MET_CARE)==(care<=1));
  assert(evoRequirementPoints(met)==(care<=1?4:3));
 }
 PARTNER_PARA.careMistakes=4;
 assert(calculateRequirementScore(221,234,1,0,-1)==3);
 assert(calculateRequirementScore(221,222,0,0,-1)==4);
 assert(getRookieEvolutionTarget(221)==234); // avg 200 beats (200+200+100)/3
 puts("PASS: care 0/1 inclusive; four mistakes: Gatomon 3/4 beats BlackGatomon 4/4");
 PARTNER_ENTITY.digimonEntity.stats.base.brain=200;
 assert(getRookieEvolutionTarget(221)==234); // equal average keeps earlier Gatomon
 PARTNER_ENTITY.digimonEntity.stats.base.brain=300;
 assert(getRookieEvolutionTarget(221)==222); // BlackGatomon now has the larger average
 PARTNER_ENTITY.digimonEntity.stats.base.brain=100;
 PARTNER_PARA.weight=16;
 assert(calculateRequirementScore(221,234,1,0,-1)==2); // care + weight both fail
 assert(getRookieEvolutionTarget(221)!=234);
 PARTNER_PARA.weight=10;
 raised[222]=1;assert(getRookieEvolutionTarget(221)==234);
 raised[222]=0;raised[234]=1;
 // Later unraised gets +1 but must still beat the stat average.
 assert(calculateRequirementScore(221,222,0,0,234)==5);
 assert(getRookieEvolutionTarget(221)==234);
 PARTNER_ENTITY.digimonEntity.stats.base.brain=300;
 assert(getRookieEvolutionTarget(221)==222);
 raised[234]=0;raised[222]=1;
 assert(calculateRequirementScore(221,222,0,0,234)==0);
 assert(getRookieEvolutionTarget(221)==234);
 // Preserve the production accumulator: a qualifying loser affects its successor.
 for(int t=400;t<=402;t++){
  rows[t]=rows[234];rows[t].hp=rows[t].defense=-1;
  para[t].level=4;gains[t].targetDigimon=t;
 }
 rows[400].offense=0;rows[401].defense=0;rows[402].brain=0;
 for(int i=0;i<6;i++)path.to[i]=i<3?400+i:-1;
 PARTNER_ENTITY.digimonEntity.stats.base=(BaseStats){2000,1000,400,200,100,600};
 // 400 leads with 400; 401 loses with 200; 402 compares (200+600)/2=400.
 assert(getRookieEvolutionTarget(221)==400);
 puts("PASS: a qualifying loser's retained average affects the next candidate");
 char label[64];chartRange(label,"Mistakes",0,rows[234].care);
 assert(strcmp(label,"Mistakes 0-1")==0);
 puts("PASS: stat priority, exact tie, two failed groups, raised filtering, popup 0-1");
}
'''
    (ROOT / 'build').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / 'build', prefix='evo-selection-') as tmp:
        src, binary = Path(tmp) / 'check.c', Path(tmp) / 'check'
        src.write_text(code)
        subprocess.run(['cc', '-std=gnu99', '-Wall', '-Werror', '-fsanitize=undefined',
                        str(src), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
    print('Source/data:', args.ref or 'working tree')


if __name__ == '__main__':
    main()
