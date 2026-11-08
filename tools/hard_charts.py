#!/usr/bin/env python3
"""Render a one-page HARD summary from the live fight and build evidence."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=Path('build/hard-review'))
    parser.add_argument('--fights',type=Path,default=Path('build/hard-primary/results.json'))
    parser.add_argument('--before',type=Path,default=Path('build/hard-primary-before/results.json'))
    parser.add_argument('--postgame',type=Path,default=Path('build/hard-postgame-proof/results.json'))
    parser.add_argument('--postgame-before',type=Path,default=Path('build/hard-before-proof/results.json'))
    parser.add_argument('--verification',type=Path,default=Path('build/hard-verification.json'))
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    fights=json.loads(args.fights.read_text())
    before=json.loads(args.before.read_text())
    verification=json.loads(args.verification.read_text())
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9})
    fig=plt.figure(figsize=(11.7,16.5),facecolor='white')
    navy='#14364f'
    def text(y,value,size=11,bold=False):
        fig.text(.06,y,value,fontsize=size,weight='bold' if bold else 'normal',color=navy if bold else '#202e38',va='top',linespacing=1.45)
    def table(y,height,headers,rows,widths,size=10):
        ax=fig.add_axes([.06,y,.88,height]);ax.axis('off')
        t=ax.table(cellText=rows,colLabels=headers,colWidths=widths,cellLoc='center',loc='center')
        t.auto_set_font_size(False);t.set_fontsize(size);t.scale(1,2.1)
        for (r,c),cell in t.get_celld().items():
            cell.set_edgecolor('#d6e2e9')
            if r==0:cell.set_facecolor(navy);cell.set_text_props(color='white',weight='bold')
            elif c>=3:cell.set_facecolor('#f9eadb')
    text(.966,'HORIZON  |  HARD + DEFENSE CURVE',24,True)
    text(.936,'Fixed encounter factors. Permanent growth and rewards unchanged.',12)
    text(.909,'HARD: HP ×1.10; Offense / Brains / finisher power ×1.50; Defense ×1.05; Speed ×1.15.\nPartner direct damage ×0.95; empty-slot idle weight ×0.25. Enemy hits have a 15%\nzero-Defense floor. Finishers already ignore Defense.',11)
    text(.839,'DEFENSE ABOVE 999, ALL DIFFICULTIES',14,True)
    text(.817,'Beyond max(999, Offense): boundary power × 1000 / (1000 + excess Defense).\nAt 999 or below: existing arithmetic and rounding preserved.',11)
    table(.692,.085,['Partner Defense','NORMAL before','NORMAL now','HARD'],
          [['800','819','819','1338'],['1500','1','390','584'],['9999','1','58','235']], [.28,.24,.24,.24])
    text(.687,'Neutral P586 probe, initial enemy Offense 999 (HARD 1498), 100% variance.\nNORMAL max Defense takes 3.96% of zero-Defense damage. Probes are not live timings.',9)
    text(.639,'REAL 2 MB FIGHTS',14,True)
    rows=[]
    for kind in ('wild','boss'):
        for profile in ('late','strong','max'):
            pair=[]
            for data,mode in ((before,'NORMAL'),(fights,'NORMAL'),(fights,'HARD')):
                r=next(r for r in data if r['kind']==kind and r['profile']==profile and r['mode']==mode)
                frames={h['frame'] for h in r['hits'] if not h['partner']}
                damage=[h['damage'] for h in r['appliedHits'] if h['partnerTarget'] and h['frame'] in frames]
                span=f'{min(damage)}–{max(damage)} ({len(damage)})' if damage else 'no landed hit'
                used=r.get('recoveriesCarried',0)-r.get('recoveriesRemaining',0)
                pair.extend([f"{r['combatSeconds']:.1f} s"+(' LOSS' if r['partnerKnockedOut'] else '')+(f' /{used}R' if kind=='boss' else ''),span])
            rows.append([('Guardromon' if kind=='wild' else 'Story Machinedramon')+' / '+profile,*pair])
    post=json.loads(args.postgame.read_text()) if args.postgame.exists() else []
    if len(post)==2:
        prior=json.loads(args.postgame_before.read_text())
        pair=[]
        for data,mode in ((prior,'NORMAL'),(post,'NORMAL'),(post,'HARD')):
            r=next(r for r in data if r['kind']=='boss' and r['profile']=='max' and r['mode']==mode)
            frames={h['frame'] for h in r['hits'] if not h['partner']}
            damage=[h['damage'] for h in r['appliedHits'] if h['partnerTarget'] and h['frame'] in frames]
            span=f'{min(damage)}–{max(damage)} ({len(damage)})' if damage else 'no landed hit'
            pair.extend([f"{r['combatSeconds']:.1f} s"+(' LOSS' if r['partnerKnockedOut'] else ''),span])
        rows.append(['Repeat Machinedramon / max',*pair])
    table(.405,.19,['Encounter / partner','N before','damage (hits)','N now','damage (hits)','HARD','damage (hits)'],rows,[.23,.115,.14,.115,.14,.115,.145],size=9)
    text(.403,'Seconds from actual 20 Hz ticks; natural AI/rolls, pairs are not RNG lockstep. Damage includes finishers.\nWild: partner Auto, Megaton Punch / Muscle Charge / War Cry; no recovery or finisher input.\nStory boss: real ending scene, early Muscle Charge orders then Buster Dive; R = large recoveries consumed.\nLate: stats800 HP/MP8005/9520; strong1500/15000; max9999/30000. Native finisher equipped.\nRepeat boss extra row uses Auto, no items. Its stronger move set can one-shot the 8005-HP partner.\nHARD incoming hits are checked against the actual C zero-Defense comparator and block roll.',9)
    text(.308,'VALIDATION AND BUDGET',14,True)
    text(.285,'\n'.join(verification['summaryLines']),10)
    text(.206,'SAVE, OPTIONS AND GROWTH',14,True)
    text(.183,'Existing save byte 10: NORMAL=0, EASY=1, HARD=2; missing/invalid → NORMAL.\nNine owned translations; eight 2 MB languages checked in all three font styles.\nHP/MP growth unchanged: 8005 HP / 9520 MP normalize to 800.5 / 952.\nA constructed no-chip Pukumon example reaches these values in 54 ordinary sessions.',10)
    text(.105,'Limits: controlled fixtures, one trial per cell; no full raise or physical console proof.\nChinese keeps its existing 8 MB and dedicated-font requirement.',9)
    text(.062,'HARD-DIFFICULTY.md  •  STAT-SOFTCAP.md  •  reproducible owned rules and playtests',10,True)
    for suffix in ('png','pdf'):fig.savefig(args.out/('summary.'+suffix),dpi=150)
    plt.close(fig)


if __name__=='__main__':main()
