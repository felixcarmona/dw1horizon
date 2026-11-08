#!/usr/bin/env python3
"""Source-derived growth scenarios and landed-hit budgets; no game mutation.

Run: python3 tools/stat_softcap_audit.py --out build/stat-softcap
These controlled inputs are not player telemetry or emulator elapsed times.
"""
import argparse
import ast
import csv
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASELINE = '0cbdeb2ccef749de68abe2f6be9376fa2e97ed9d'
sys.path.insert(0, str(ROOT / 'tools'))
from battle_audit import damage, placements, table
from species import ELEMENTS

KEYS = ('hp', 'mp', 'offense', 'defense', 'speed', 'brains')
CAPS = (30000, 30000, 9999, 9999, 9999, 9999)

def read(path):
    return json.loads((ROOT / path).read_text())

# Cost coordinate: one point costs 1, 2, or 4 raw gain units.
# HP/MP use ten times the knees, retaining their original stat units.
def cost(value, scale=1):
    a, b = 999 * scale, 1999 * scale
    return min(value, a) + 2 * min(max(value-a, 0), b-a) + 4 * max(value-b, 0)

def invert(value, scale=1):
    a, b = 999 * scale, 1999 * scale
    if value <= a:
        return value
    if value <= a + 2*(b-a):
        return a + (value-a)//2
    return b + (value-a-2*(b-a))//4

class Stats:
    def __init__(self, values, soft):
        self.values = list(values)
        self.remainder = [0]*6
        self.soft = soft
    def add(self, gains):
        for i, gain in enumerate(gains):
            if gain <= 0:
                self.values[i] = max(0, self.values[i]+gain)
                continue
            if not self.soft:
                self.values[i] = min(CAPS[i], self.values[i]+gain)
                continue
            scale = 10 if i < 2 else 1
            budget = cost(self.values[i], scale) + self.remainder[i] + gain
            self.values[i] = min(CAPS[i], invert(budget, scale))
            self.remainder[i] = 0 if self.values[i] == CAPS[i] else budget-cost(self.values[i], scale)


def fin_off(value):
    return value if value <= 999 else 999 + 999*(value-999)//value


def simulate(species, soft, heavy=False, max_grind=False, variant=1):
    # Conservative Champion anchor from evo_tree.practical, then actual target blends.
    s = Stats((1500,1500,150,150,150,150), soft)
    logs=[]
    sessions = (84,60,60) if not heavy else (144,120,180)
    wins = (24,40,60) if not heavy else (80,120,200)
    gym = read('content/tables/training.json')['training']
    rows = read('content/tables/training-gains.json')['trainGain']
    # even training affinity, six gyms; normal slot (no jackpot).
    gyms=('hp','mp','off','def','spd','brain')
    rowkeys=('hp','mp','off','def','spd','brain')
    for stage,(level,target) in enumerate(((4,12),(5,373),(6,None))):
        ns = round(sessions[stage]*variant)
        nw = round(wins[stage]*variant)
        before=list(s.values)
        for j in range(ns):
            mode=j%6
            row=next(r for r in rows if r['gym']==gyms[mode] and r['slot'] in ('any',0))
            # Full recruitment/manual only for heavy scenario, without counter upgrade.
            num=gym['gainTenths'][1 if mode==5 else mode][0]*gym['levelTenths'][level]
            den=100
            if heavy:
                num*=6*12
                den*=5*10
            multiplier=num*10//den
            s.add([row.get(k,0)*multiplier//10 for k in rowkeys])
        logs.append(dict(stage=stage,source='gym',count=ns,before=before,after=list(s.values)))
        before=list(s.values)
        # Single-enemy conservative floor; small probabilistic +1 excluded.
        enemy=(3000,3000,400,300,250,250) if stage==0 else (5000,5000,700,500,400,400)
        for _ in range(nw):
            gain=[]
            for old,e in zip(s.values,enemy):
                legacy=math.ceil(e/max(old,1)) if e>=old else 0
                gain.append(max(legacy,e//100))
            s.add(gain)
        logs.append(dict(stage=stage,source='battle',count=nw,before=before,after=list(s.values)))
        # Six independent +50/+500 chips. No DV lifetime debit.
        chips=round((1 if not heavy else 8)*variant)
        before=list(s.values)
        for _ in range(chips):
            s.add((500,500,50,50,50,50))
        logs.append(dict(stage=stage,source='six chips',count=chips,before=before,after=list(s.values)))
        meals=round((4 if not heavy else 20)*variant)
        before=list(s.values)
        for _ in range(meals):
            s.add((70,70,7,7,7,7))
        logs.append(dict(stage=stage,source='best Digitamamon meal roll',count=meals,before=before,after=list(s.values)))
        if target:
            before=list(s.values)
            gains=species[target]['evolution']['gains']
            wanted=[v+g//10 if v>=g else (v+g)//2 for v,g in zip(s.values,[gains[k] for k in KEYS])]
            s.add([w-v for w,v in zip(wanted,s.values)])
            logs.append(dict(stage=stage,source='evolution '+str(target),count=1,before=before,after=list(s.values)))
    if max_grind:
        before=list(s.values)
        # Upper effort stress case: 200 further ordinary chips of each kind.
        for _ in range(200):
            s.add((500,500,50,50,50,50))
        logs.append(dict(stage=3,source='six chips',count=200,before=before,after=list(s.values)))
    return s.values,logs


def run(out):
    changed = subprocess.check_output(
        ['git', 'diff', BASELINE, '--', 'content', 'mods/patches', 'story/base',
         'story/mods/what-the-island-forgot'], cwd=ROOT, text=True)
    if changed:
        raise SystemExit('Source inputs differ from the pinned audit baseline; review and update BASELINE first.')
    allspecies, native = placements()
    sp={s['id']:s for s in allspecies}
    rules=read('content/tables/battle-formulas.json')['battleFormulas']['damage']
    types=read('content/tables/type-factors.json')['typeFactors']
    techniques={s['name']:s for s in (json.loads(p.read_text()) for p in (ROOT/'content/techniques').glob('*.json'))}
    def factors(element,species):
        return sum(10 if e is None else types[ELEMENTS.index(element)][ELEMENTS.index(e)] for e in species.get('specialties',[None]*3))
    scenarios=[]
    for name,heavy,grind in [('Normal',False,False),('Heavy',True,False),('Max grind',True,True)]:
        now,logs=simulate(sp,False,heavy,grind)
        new,newlogs=simulate(sp,True,heavy,grind)
        ranges={}
        for side,soft in [('today',False),('proposal',True)]:
            values=[simulate(sp,soft,heavy,grind,v)[0] for v in (.75,1.25)]
            ranges[side]=[[min(v[i] for v in values),max(v[i] for v in values)] for i in range(6)]
        scenarios.append(dict(name=name,today=now,proposal=new,ranges=ranges,today_events=logs,proposal_events=newlogs))
    bosses=[]
    for r in native:
        if (r['map']=='MGEN99' and r['slot'] in (0,1,3)) or (r['id']==115 and r['map'] in ('OGRE02','ICSA08','CHKA01')):
            bosses.append(dict(r,label=r['map']+':'+str(r['slot'])+' '+r['name'],source='content/maps/'+r['map']+'.json'))
    # Explicit story fights: resolve local NPC declarations and literal overrides.
    # Includes optional residents and branching ambushes. Imported base aliases are
    # listed as unresolved instead of fabricating a profile.
    unresolved=[]
    for path in sorted((ROOT/'story/mods/what-the-island-forgot/arcs').rglob('*.py')):
        tree=ast.parse(path.read_text())
        npcs={}
        for node in ast.walk(tree):
            if isinstance(node,ast.Assign) and isinstance(node.value,ast.Call):
                c=node.value
                if isinstance(c.func,ast.Attribute) and c.func.attr=='npc' and c.args and isinstance(c.args[0],ast.Attribute):
                    name=c.args[0].attr
                    candidates=[s for s in allspecies if (s['name']==name or ''.join(x for x in s['name'] if x.isalnum())==name or s['name']+str(s['id'])==name)]
                    if not candidates: continue
                    species=min(candidates,key=lambda s:abs(s['id']-int(''.join(filter(str.isdigit,name)) or s['id'])))
                    w=dict(species.get('wild',{}))
                    for kw in c.keywords:
                        if kw.arg in ('hp','mp','offense','defense','speed','brain') and isinstance(kw.value,ast.Constant):
                            w[{'offense':'off','defense':'def'}.get(kw.arg,kw.arg)]=kw.value.value
                    for lhs in node.targets:
                        if isinstance(lhs,ast.Name): npcs[lhs.id]=(species,w)
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='fight':
                for arg in node.args:
                    if not isinstance(arg,ast.Name): continue
                    if arg.id not in npcs:
                        unresolved.append(str(path.relative_to(ROOT))+':'+arg.id)
                        continue
                    species,w=npcs[arg.id]
                    if not all(k in w for k in ('hp','off','def')):
                        unresolved.append(str(path.relative_to(ROOT))+':'+arg.id)
                        continue
                    bosses.append(dict(w,id=species['id'],name=species['name'],label=path.parent.name+'/'+path.stem+':'+arg.id,source=str(path.relative_to(ROOT))))
    aliases={
        'airdramon/ambush:slot5':('TWNA02',5),
        'shore/beach-cave:ogremon':('OGRE11',0),
        'shore/beach-cave:slot3':('OGRE11',3),
        'summit/summit:slot0':('MGEN99',0),
    }
    for alias,(mapname,slot) in aliases.items():
        matches=[r for r in native if r['map']==mapname and r['slot']==slot]
        if matches:
            r=matches[0]
            bosses.append(dict(r,label=alias,source='content/maps/'+mapname+'.json'))
            unresolved=[u for u in unresolved if not (u.endswith(alias.split('/')[1].replace(':','.py:')) and '/'+alias.split('/')[0]+'/' in u)]
    # Initial Mega cup roll ranges; finals have no independent round multiplier.
    bases=read('content/tables/tournaments.json')['tournaments']['opponentBaseStats']
    for base in sorted(set(bases)-{0}):
        bosses.append(dict(label=f'Cup base {base}, Mega median (neutral)',hp=min(9999,base*35//10*10),off=min(999,base*35//10),**{'def':min(999,base*35//10)},id=None,source='content/tables/tournaments.json'))
    results=[]
    seen=set()
    for boss in bosses:
        if boss['label'] in seen:continue
        seen.add(boss['label'])
        target=sp[boss['id']] if boss['id'] is not None else {}
        tf=factors('air',target)
        ff=factors('battle',target)
        for scenario in scenarios:
            result=dict(boss=boss['label'],profile=scenario['name'],hp=boss['hp'],off=boss['off'],defense=boss['def'],source=boss['source'])
            for side in ('today','proposal'):
                vals=scenario[side]
                off,defense=vals[2:4]
                hit=damage(586,off,defense=boss['def'],factors=tf,rules=rules)
                hits=math.ceil(boss['hp']/hit)
                fo=off if side=='today' else fin_off(off)
                fin=min(30000,((fo+255)*ff//30)*2)
                # Standard threat probe, with MetalEtemon's actual Air susceptibility.
                incoming=damage(586,boss['off'],defense,40,rules)
                ef=target.get('finisher',{'power':255,'element':'battle'})
                eo=boss['off'] if side=='today' else fin_off(boss['off'])
                efbase=(eo+ef['power'])*factors(ef['element'],sp[65])//30
                # Max direct attack from the authored active move slots, no status DoT.
                if boss['id'] is None:
                    active=[]
                elif boss['source'].startswith('content/maps/'):
                    placement=next(r for r in read(boss['source'])['digimon'] if r['slot']==boss['slot'])
                    active=[target.get('techniques',[])[m-46] for m,w in zip(placement.get('moves',[]),placement.get('prios',[])) if w and 0<=m-46<len(target.get('techniques',[]))]
                else:
                    active=read('content/battle/enemy-movesets.json').get(str(boss['id']),{}).get('moves',target.get('techniques',[]))
                threats=[]
                for name in active or []:
                    t=techniques.get(name)
                    if t and t['id']<58 and t.get('power',0)>0 and t['id']!=45:
                        threats.append((damage(t['power'],boss['off'],defense,factors(t['element'],sp[65]),rules),name))
                strongest=max(threats,default=(0,'unknown'))
                result[side]=dict(incoming_active_max=strongest[0],incoming_active_technique=strongest[1],hit=hit,hits=hits,seconds=hits*3,finisher=fin,incoming_probe=incoming,
                    incoming_probe_total=incoming*hits,enemy_finisher_range=[efbase*90//100,efbase*2*110//100])
            results.append(result)
    buff_rows=[]
    for scenario in scenarios:
        for casts in (0,1,4,6):
            off,defense=999,800
            for _ in range(casts):
                off=min(9999,off+off*25//100);defense=min(9999,defense+defense*15//100)
            row=dict(profile=scenario['name'],casts=casts,off=off,defense=defense)
            for side in ('today','proposal'):
                v=scenario[side]
                row[side]=dict(incoming=damage(586,off,v[3],40,rules),outgoing=damage(586,v[2],defense,22,rules),
                    enemy_finisher_max=(((off if side=='today' else fin_off(off))+260)*50//30)*2*110//100)
            buff_rows.append(row)
    reqs=[]
    engine=read('content/balance/engine/tables.json')['species']
    for s in allspecies:
        if 'partner' not in s:continue
        req=dict(engine.get(str(s['id']),{}).get('evoReqs',{}))
        req.update(s.get('evolution',{}).get('requirements',{}))
        for mode,row in [('on',req),('off',dict(req,**s.get('off',{}).get('requirements',{})))]:
            for k in ('hp','mp','offense','defense','speed','brain'):
                v=row.get(k,-1)
                if v>999:reqs.append(dict(id=s['id'],name=s['name'],mode=mode,stat=k,normalized=v,actual=v*(10 if k in ('hp','mp') else 1)))
    for i in range(6):
        for start in (998,999,1000,1998,1999,2000):
            a=Stats([start]*6,True); b=Stats([start]*6,True)
            a.add([100]*6)
            for _ in range(100): b.add([1]*6)
            assert a.values==b.values and a.remainder==b.remainder
    assert fin_off(999)==999 and fin_off(9999)<1998
    data=dict(baseline=BASELINE,scenarios=scenarios,bosses=results,buffs=buff_rows,requirements_over_999=reqs,unresolved_story_aliases=sorted(set(unresolved)))
    out.mkdir(parents=True,exist_ok=True)
    (out/'audit.json').write_text(json.dumps(data,indent=2)+'\n')
    rows=[]
    for r in results:
        a,b=r['today'],r['proposal']
        rows.append([r['boss'],r['profile'],r['hp'],r['off'],r['defense'],a['hit'],b['hit'],a['seconds'],b['seconds'],a['incoming_active_technique'],a['incoming_active_max'],b['incoming_active_max'],a['incoming_probe'],b['incoming_probe'],a['finisher'],b['finisher'],str(a['enemy_finisher_range']),str(b['enemy_finisher_range'])])
    headers=['Encounter','Scenario','HP','O','D','Hit today','Hit proposed','TTK today s','TTK proposed s','Strongest active direct technique','Incoming active today','Incoming active proposed','Incoming probe today','Incoming probe proposed','Finisher today','Finisher proposed','Enemy finisher range today','Enemy finisher range proposed']
    (out/'boss-table.md').write_text(table(headers,rows)+'\n')
    with (out/'boss-table.csv').open('w') as f:
        writer=csv.writer(f,lineterminator="\n");writer.writerow(headers);writer.writerows(rows)
    print('Scenarios:',[(s['name'],s['today'],s['proposal']) for s in scenarios])
    print('Boss profiles:',len(seen),'requirements >999:',reqs,'unresolved:',data['unresolved_story_aliases'])

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=Path('build/stat-softcap'))
    run(parser.parse_args().out)
