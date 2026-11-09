#!/usr/bin/env python3
"""Check evolution admission and random selection using the actual patched C picker.

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
    match = re.search(r'^(?:static (?:__attribute__\(\(noinline\)\) )?)?(?:void|int32_t|int16_t|int8_t|char \*) ?'
                      + name + r'\([^;]*?\)\s*\{', source, re.M)
    if not match:
        raise ValueError('Missing C function: ' + name)
    return source[match.start():source.index('\n}', match.end()) + 2] + '\n'



RANDOM_CHECKS = r"""
 PARTNER_ENTITY.digimonEntity.stats.base=(BaseStats){2000,1000,100,200,100,100};
 PARTNER_PARA.weight=10;PARTNER_PARA.evoTimer=72;
 for(int care=0;care<=4;care++){
  PARTNER_PARA.careMistakes=care;
  int met=evoRequirementsMet(221,234,1,0);
  assert(!!(met&EVO_MET_CARE)==(care<=1));
  assert(evoRequirementPoints(met)==(care<=1?4:3));
 }
 PARTNER_PARA.careMistakes=4;
 assert(calculateRequirementScore(221,234,1,0,-1)==3);
 assert(calculateRequirementScore(221,222,0,0,-1)==4);
 int hist[512]={0};
 for(int i=0;i<100000;i++){
  refresh=i/17;
  int t=getRookieEvolutionTarget(221,1);
  assert(t==234 || t==222);hist[t]++;
 }
 assert(hist[234]>49000 && hist[234]<51000);
 printf("PASS: Salamon 100000 rolls: Gatomon %d, BlackGatomon %d; no non-qualifier\n",hist[234],hist[222]);
 // Scores determine admission; stats do not rank admitted candidates.
 PARTNER_ENTITY.digimonEntity.stats.base.brain=300;
 for(int i=0;i<1000;i++){int t=getRookieEvolutionTarget(221,1);assert(t==234 || t==222);}
 PARTNER_ENTITY.digimonEntity.stats.base.brain=100;
 int before=draws;
 for(int i=0;i<1000;i++)assert(getRookieEvolutionTarget(221,0)==234);
 assert(draws==before);
 raised[222]=1;
 for(int i=0;i<100;i++)assert(getRookieEvolutionTarget(221,1)==234);
 assert(draws==before); // single candidate needs no roll
 raised[222]=0;raised[234]=1;
 memset(hist,0,sizeof(hist));
 for(int i=0;i<1000;i++)hist[getRookieEvolutionTarget(221,1)]++;
 assert(hist[234] && hist[222]); // earlier admitted raised target stays
 raised[234]=0;
 blocked_model[234]=1;assert(getRookieEvolutionTarget(221,1)==222);blocked_model[234]=0;
 blocked_option[222]=1;assert(getRookieEvolutionTarget(221,1)==234);blocked_option[222]=0;
 PARTNER_PARA.weight=16;
 assert(calculateRequirementScore(221,234,1,0,-1)==2);
 for(int i=0;i<100;i++)assert(getRookieEvolutionTarget(221,1)!=234);
 PARTNER_PARA.weight=10;
 // Zero through six qualifying targets exercise both ordinary stage wrappers.
 for(int t=400;t<406;t++){
  rows[t]=rows[234];para[t].level=5;gains[t].targetDigimon=t;
 }
 for(int count=0;count<=6;count++){
  for(int i=0;i<6;i++)path.to[i]=i<count?400+i:-1;
  memset(hist,0,sizeof(hist));
  for(int i=0;i<120000;i++){
   refresh=i/13;
   int t=getChampionEvolutionTarget(221,1);
   if(!count)assert(t==-1);
   else {assert(t>=400 && t<400+count);hist[t]++;}
  }
  if(count)for(int t=400;t<400+count;t++)assert(hist[t]>120000/count-1200 && hist[t]<120000/count+1200);
  printf("PASS: %d qualifiers:",count);
  for(int t=400;t<400+count;t++)printf(" %d",hist[t]);
  puts("");
 }
 // The first raw sample is in the rejected tail for a three-target draw.
 for(int i=0;i<6;i++)path.to[i]=i<3?400+i:-1;
 refresh=0;forced=32767;before=draws;
 assert(getChampionEvolutionTarget(221,1)>=400);assert(draws==before+2);
 // Same RNG state, different live refresh count: reload is not locked to a result.
 rng=7;refresh=0;int first=getChampionEvolutionTarget(221,1),changed=0;
 for(int i=1;i<30;i++){rng=7;refresh=i;changed|=getChampionEvolutionTarget(221,1)!=first;}
 assert(changed);
 // History exclusion is fixed before the roll, even with several preceding targets.
 raised[401]=1;raised[402]=1;
 for(int i=0;i<100;i++)assert(getChampionEvolutionTarget(221,1)==400);
 raised[400]=1;raised[401]=0;
 for(int i=0;i<100;i++){int t=getChampionEvolutionTarget(221,1);assert(t==400||t==401);}
 memset(raised,0,sizeof(raised));
 for(int i=0;i<6;i++)path.to[i]=-1;
 assert(getRookieEvolutionTarget(221,1)==-1);
 PARTNER_PARA.evoTimer=96;assert(getRookieEvolutionTarget(221,1)==11);
 // In-Training retains the score winner and earlier target on an exact tie.
 path.to[0]=400;path.to[1]=401;
 para[400].level=para[401].level=4;
 rows[400].care=1;rows[401].care=10;
 before=draws;
 assert(getInTrainingEvolutionTarget(221)==401);
 rows[400].care=10;assert(getInTrainingEvolutionTarget(221)==400);
 assert(draws==before);
 char label[64];chartRange(label,"Mistakes",0,rows[234].care);
 assert(strcmp(label,"Mistakes 0-1")==0);
 puts("PASS: preview no RNG, raised order, model/options filters, fallback, rejection, live timing, In-Training, care popup");
}
"""

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
int blocked_model[512], blocked_option[512];
int isPartnerModelFit(int t){return !blocked_model[t];}
int modSpeciesAllowed(int t){return !blocked_option[t];}
uint32_t rng=1; int refresh, draws, timer_reads, forced=-1;
int randomLimit(int n){
 assert(n==32768); draws++;
 if(forced>=0){int v=forced;forced=-1;return v;}
 rng=rng*1103515245u+12345u;return (rng>>16)&32767;
}
int VSync(int mode){assert(mode==-1);timer_reads++;return refresh;}
int getEvolutionExtraTargets(int cur,DigimonId **extra){return 0;}
int hasDigimonRaised(int t){return raised[t];}
int8_t getNumMasteredMoves(void){return 0;}
int32_t evoTargetWeight(int cur,DigimonId t){return rows[t].weight;}
'''
    source = (args.tree / 'src/main/evolution.c').read_text()
    randomized = 'chooseQualifiedEvolution' in source
    for name in ('evoAmt', 'evoPassPoints', 'evoPartnerTopStat', 'evoRequirementsMet',
                 'evoRequirementPoints', 'calculateRequirementScore'):
        code += function(source, name)
    names = (['chooseQualifiedEvolution'] if randomized else []) + ['getRookieEvolutionTarget', 'getChampionEvolutionTarget']
    if randomized:
        names += ['scoreInTrainingTarget', 'getInTrainingEvolutionTarget']
    for name in names:
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
    code += (RANDOM_CHECKS if randomized else r'''
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
''')
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
