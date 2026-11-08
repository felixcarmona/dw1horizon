#!/usr/bin/env python3
"""Reproduce EASY/NORMAL/HARD landed-hit budgets from owned numeric inputs.

TTK seconds assume 3 seconds per landed ordinary hit; not live AI timings.
"""
import argparse
import csv
import json
import math
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from battle_audit import damage, placements, table
from species import ELEMENTS

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,default=Path('build/hard-audit'))
    ap.add_argument('--rules',type=Path,default=ROOT/'content/tables/battle-formulas.json')
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    allsp,places=placements();sp={s['id']:s for s in allsp}
    formulas=json.loads(a.rules.read_text())['battleFormulas']
    rules=formulas['damage'];hard=formulas['hard']
    factors=json.loads((ROOT/'content/tables/type-factors.json').read_text())['typeFactors']
    def elem(el,s):return sum(10 if e is None else factors[ELEMENTS.index(el)][ELEMENTS.index(e)] for e in s.get('specialties',[None]*3))
    def scale(v,key,cap):return min(cap,v*hard[key]//100)
    selected=[r for r in places if (r['map']=='MGEN99' and r['slot'] in (0,3)) or (r['map']=='ICSA08' and r['slot']==0) or (r['map']=='FACT02' and r['slot']==0) or (r['map']=='MAYO00' and r['slot']==0)]
    # Include the actual controlled wild proof map's authored enemy.
    for r in places:
        if r['map']=='FACT03' and r['slot']==0 and r not in selected:selected.append(r)
    for name,hp,off,defense in [('Knightmon',4500,720,380),('Datamon',3000,640,340),('WaruSeadramon',4500,560,280),('Gururumon',3200,540,300)]:
        species=next(s for s in allsp if s['name']==name and 'partner' in s)
        selected.append(dict(map='Horizon '+name,slot=0,id=species['id'],hp=hp,off=off,**{'def':defense}))
    profiles=[('Original late',800,800,8005),('Reported low',650,650,8005),('Reported high',820,820,8005),('Strong late',1500,1500,15000),('Heavy grind',4000,4000,20000),('Ceiling',9999,9999,30000)]
    rows=[];data=[]
    for enemy in selected:
        target=sp[enemy['id']];label=enemy['map']+':'+str(enemy['slot'])+' '+target['name']
        for name,off,defense,hp in profiles:
            for mode in ('EASY','NORMAL','HARD'):
                h=mode=='HARD';ehp=scale(enemy['hp'],'hpPercent',30000) if h else enemy['hp']
                ed=scale(enemy['def'],'defensePercent',9999) if h else enemy['def']
                eo=scale(enemy['off'],'offensePercent',9999) if h else enemy['off']
                dealt=damage(586,off,ed,elem('air',target),rules,easy=1 if mode=='EASY' else 0)
                if h:dealt=max(1,dealt*hard['partnerDamagePercent']//100)
                taken=damage(586,eo,defense,elem('air',sp[65]),rules,easy=-1 if mode=='EASY' else 0)
                if h:taken=max(taken,(damage(586,eo,0,elem('air',sp[65]),rules)*hard['minimumDamagePercent']+99)//100)
                # Actual enemy finisher power and element; no finisher readiness assumed.
                fin=target.get('finisher')
                enemy_fin=None
                if fin:
                    p=scale(fin['power'],'finisherPowerPercent',32767) if h else fin['power']
                    base=(eo+p)*elem(fin['element'],sp[65])//30
                    lo=max(1,base*90//100);hi=min(30000,base*2*110//100)
                    enemy_fin=[(lo+1)//2,(hi+1)//2] if mode=='EASY' else [lo,hi]
                partner_fin=(off+255)*elem('battle',target)//30*2
                partner_fin=partner_fin*2 if mode=='EASY' else partner_fin*hard['partnerDamagePercent']//100 if h else partner_fin
                partner_fin=min(30000,max(1,partner_fin))
                hits=math.ceil(ehp/dealt)
                beforeRules={k:v for k,v in rules.items() if k not in ('defenseKnee','defenseTailHalf')}
                beforeTaken=damage(586,enemy['off'],defense,elem('air',sp[65]),beforeRules,easy=-1 if mode=='EASY' else 0)
                if mode in ('NORMAL','EASY') and defense<=999:assert taken==beforeTaken
                row=dict(incomingBefore=beforeTaken,encounter=label,profile=name,mode=mode,partnerO=off,partnerD=defense,partnerHP=hp,enemyHP=ehp,enemyO=eo,enemyD=ed,ordinary=dealt,hits=hits,ttkSeconds=hits*3,incomingProbe=taken,enemyFinisher=enemy_fin,partnerFinisher=partner_fin)
                data.append(row);rows.append([label,name,mode,ehp,eo,ed,dealt,hits,hits*3,taken,enemy_fin,partner_fin])
    beforeRules={k:v for k,v in rules.items() if k not in ('defenseKnee','defenseTailHalf')}
    with (a.out/'normal-before-after.csv').open('w',newline='') as stream:
        writer=csv.writer(stream,lineterminator='\n')
        writer.writerow(['Defense','EASY before','EASY now','NORMAL before','NORMAL now','HARD now','NORMAL zero Defense','HARD zero Defense'])
        for defense in (800,1500,9999):
            hardOff=999*hard['offensePercent']//100
            zero=damage(586,hardOff,0,30,rules)
            hardHit=max(damage(586,hardOff,defense,30,rules),(zero*hard['minimumDamagePercent']+99)//100)
            writer.writerow([defense,damage(586,999,defense,30,beforeRules,easy=-1),damage(586,999,defense,30,rules,easy=-1),
                             damage(586,999,defense,30,beforeRules),damage(586,999,defense,30,rules),hardHit,damage(586,999,0,30,rules),zero])
    original=[]
    for e in selected:
        d=damage(586,800,e['def'],elem('air',sp[e['id']]),rules,old=True)
        original.append([e['map']+':'+str(e['slot'])+' '+sp[e['id']]['name'],e['hp'],d,math.ceil(e['hp']/d)*3])
    headers=['Encounter','Profile','Mode','Enemy HP','Enemy O','Enemy D','Ordinary hit','Hits','Assumed TTK s','Incoming P586 probe','Enemy finisher range','Full partner finisher']
    with (a.out/'comparison.csv').open('w',newline='') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(headers);w.writerows(rows)
    (a.out/'comparison.md').write_text(table(headers,rows)+'\n')
    pukumon=sp[401]
    pre=[4740,4890,500,500,500,500]
    keys=('hp','mp','offense','defense','speed','brains')
    evo=[v+g//10 if v>=g else (v+g)//2 for v,g in zip(pre,[pukumon['evolution']['gains'][k] for k in keys])]
    training=json.loads((ROOT/'content/tables/training.json').read_text())['training']
    gainrows=json.loads((ROOT/'content/tables/training-gains.json').read_text())['trainGain']
    final=list(evo);witness=[]
    for gym,mode,count in [('hp',0,12),('mp',1,32),('spd',4,5),('brain',1,5)]:
        row=next(r for r in gainrows if r['gym']==gym and r['slot'] in ('any',0))
        multiplier=training['gainTenths'][mode][1]*training['levelTenths'][6]//10
        gains=[row.get(k,0)*multiplier//10 for k in ('hp','mp','off','def','spd','brain')]
        final=[v+g*count for v,g in zip(final,gains)]
        witness.append(dict(gym=gym,sessions=count,multiplierTenths=multiplier,gainsPerSession=gains))
    hpmp=dict(preMega=pre,afterEvolution=evo,sessions=witness,final=final,scope='Constructed arithmetic witness; no chip, gym bonuses, food or battle gains. Not a replay of the reported save.')
    assert final==[8005,9520,674,714,675,655]
    (a.out/'hpmp-witness.json').write_text(json.dumps(hpmp,indent=2)+'\n')
    print('HP/MP arithmetic witness:',hpmp)
    (a.out/'comparison.json').write_text(json.dumps(dict(factors=hard,rows=data,originalLate=original),indent=2)+'\n')
    print('Original capped late profile O=D=800:',original)
    for r in data:
        if r['profile'] in ('Strong late','Reported high') and r['encounter'].startswith(('MGEN99','ICSA08')):print(r)
if __name__=='__main__':main()
