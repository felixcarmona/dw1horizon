#!/usr/bin/env python3
"""Render the growth audit review sheet (requires matplotlib and numpy)."""
import argparse
import json
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out',type=Path,default=Path('build/stat-softcap'))
OUT=parser.parse_args().out
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
x=json.load(open(OUT/'audit.json'))
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
blue='#2773a5';gold='#b96215';bg='#f5f8fb'
fig=plt.figure(figsize=(11.7,16.5),facecolor='white')
fig.text(.06,.963,'HORIZON  |  STAT GROWTH REVIEW',fontsize=23,weight='bold',color='#153550')
fig.text(.06,.94,'Source model • 7 Nov 2026 • baseline 0cbdeb2 • PROPOSAL ONLY',fontsize=11)
fig.text(.06,.914,'Gains: ×1 to 999, ×½ to 1999, ×¼ thereafter. HP/MP knees: 9990 / 19990.\nFinisher effective O: O through 999; then 999 + floor[999 × (O−999) / O].',fontsize=11,linespacing=1.6)
ax=fig.add_axes([.09,.72,.38,.145])
pos=np.arange(3)
ax.bar(pos-.18,[s['today'][2] for s in x['scenarios']],.36,label='Today',color=blue)
ax.bar(pos+.18,[s['proposal'][2] for s in x['scenarios']],.36,label='Proposal',color=gold)
for i,s in enumerate(x['scenarios']):
 for dx,side in [(-.18,'today'),(.18,'proposal')]:
  v=s[side][2];ax.text(i+dx,v+180,str(v),ha='center',fontsize=9)
ax.set_xticks(pos,['Normal budget','Heavy budget','Max grind'])
ax.set_ylim(0,11500);ax.set_ylabel('Offense');ax.set_title('Equal inputs: permanent Offense',loc='left',weight='bold')
ax.legend(frameon=False,fontsize=9)
ax=fig.add_axes([.59,.72,.34,.145])
o=np.arange(0,10000)
e=np.where(o<=999,o,999+999*np.maximum(0,o-999)//np.maximum(o,1))
ax.plot(o,2*(o+255),color=blue,label='Today')
ax.plot(o,2*(e+255),color=gold,label='Finisher curve only')
ax.set_xlabel('Offense before growth changes');ax.set_ylabel('Neutral full finisher damage')
ax.set_title('Finishers: power 255, charge 80',loc='left',weight='bold');ax.legend(frameon=False,fontsize=8)
fig.text(.06,.673,'BOSS BUDGETS  |  seconds, today → proposal',fontsize=14,weight='bold',color='#153550')
fig.text(.06,.651,'Thunder Justice • MetalEtemon fixture • NORMAL • 100% roll • no buffs or guard\nTTK = landed hits × assumed 3 s; no finisher included. These are not live timings.',fontsize=10,linespacing=1.5)
select=[('Mt. Infinity Machinedramon','MGEN99:0 Machinedramon'),('Repeat Machinedramon (3 sites)','CHKA01:1 Machinedramon'),('Digitamamon post-game','MGEN99:3 Digitamamon'),('Cup base 350, Mega median','Cup base 350, Mega median (neutral)'),('Knightmon challenge','residents/knightmon:knightmon'),('WaruSeadramon ambush','shore/sea-ambush:waruseadramon'),('Datamon challenge','factory/remodelling:datamon'),('Mist hunter (plus escort)','hunters/ambush-mist:hunter'),('Airdramon city ambush','airdramon/ambush:slot5')]
rows=[]
for label,name in select:
 rr=[r for r in x['bosses'] if r['boss']==name]
 rows.append([label]+[f"{r['today']['seconds']} → {r['proposal']['seconds']}" for r in rr])
ax=fig.add_axes([.06,.399,.88,.23]);ax.axis('off')
t=ax.table(cellText=rows,colLabels=['Encounter','Normal','Heavy','Max grind'],colWidths=[.55,.15,.15,.15],loc='center',cellLoc='center')
t.auto_set_font_size(False);t.set_fontsize(10);t.scale(1,1.8)
for (r,c),cell in t.get_celld().items():
 cell.set_edgecolor('#d7e1e8')
 if r==0:cell.set_facecolor('#153550');cell.set_text_props(color='white',weight='bold')
 elif r%2:cell.set_facecolor(bg)
 if c==0 and r>0:cell.set_text_props(ha='left')
fig.text(.06,.355,'WHAT CHANGES — AND WHAT REMAINS',fontsize=14,weight='bold',color='#153550')
fig.text(.06,.327,'Full neutral finishers (normal / heavy / max grind):\n4102 → 3076   /   12450 → 3776   /   20508 → 4124',fontsize=11,linespacing=1.7)
fig.text(.06,.271,'Growth slows, but most unbuffed attacks still deal 1 to heavy / max partners.\nNormal vs repeat Machinedramon, strongest active direct hit: 1 → 455.\nFull Potential can restore danger; its casts are not assumed in the TTK table.\nNo O / D / Speed / Brains evolution requirement exceeds 999 (maximum: 600).',fontsize=11,linespacing=1.65)
fig.text(.06,.181,'REVIEW LIMITS',fontsize=13,weight='bold',color='#9a4e12')
fig.text(.06,.158,'“Normal / heavy” are explicit budgets, not observed player distributions.\nChampion seed: 1500 HP/MP, 150 other stats. Fixed evolution checkpoints.\nHeavy needs lifetime extensions; max grind assumes stockpiled chips and money.\nNo complete raise, fresh boss replay, AI TTK, or hardware test was run.\nAnalogman is a scene actor; the summit fight is Machinedramon.',fontsize=10,linespacing=1.6,va='top')
fig.text(.06,.055,'STOP FOR REVIEW  •  No gameplay code or balance data changed.\nSee STAT-SOFTCAP.md, the event ledger and 126-row boss CSV for assumptions and sources.',fontsize=11,weight='bold',linespacing=1.6)
fig.savefig(OUT/'summary.png',dpi=150)
fig.savefig(OUT/'summary.pdf')
# Every resolved encounter, separate printable table.
fig2=plt.figure(figsize=(16.5,23.4),facecolor='white')
fig2.text(.035,.97,'HORIZON  |  COMPLETE BOSS SCENARIO TABLE',fontsize=24,weight='bold',color='#153550')
fig2.text(.035,.947,'Per target; multi-enemy participants shown separately. Today → proposal. 42 encounter/fixture rows × 3 partner budgets.',fontsize=11)
fig2.text(.035,.927,'TTK = landed hits × assumed 3 s, Thunder Justice; no finisher. Incoming = strongest authored active direct hit, 100% roll, no buffs.\nRows marked p use power 586 / type sum 40 probe; active moves unknown. Final opponents, RNG, status and AI timings are not measured.',fontsize=11,linespacing=1.5)
rows=[]
for name in dict.fromkeys(r['boss'] for r in x['bosses']):
 rr=[r for r in x['bosses'] if r['boss']==name]
 a=rr[0]
 cells=[name,f"{a['hp']}/{a['off']}/{a['defense']}"]
 cells += [f"{r['today']['seconds']}→{r['proposal']['seconds']}" for r in rr]
 for r in rr:
  k='incoming_probe' if r['today']['incoming_active_technique']=='unknown' else 'incoming_active_max'
  cells.append(f"{r['today'][k]}→{r['proposal'][k]}"+('p' if k=='incoming_probe' else ''))
 rows.append(cells)
ax=fig2.add_axes([.035,.10,.93,.80]);ax.axis('off')
t=ax.table(cellText=rows,colLabels=['Encounter / fixture','HP/O/D','TTK N','TTK H','TTK G','Taken N','Taken H','Taken G'],colWidths=[.37,.13,.08,.08,.08,.09,.085,.085],loc='center',cellLoc='center')
t.auto_set_font_size(False);t.set_fontsize(9.1);t.scale(1,2.05)
for (r,c),cell in t.get_celld().items():
 cell.set_edgecolor('#d7e1e8')
 if r==0:cell.set_facecolor('#153550');cell.set_text_props(color='white',weight='bold')
 elif r%2:cell.set_facecolor(bg)
 if c==0 and r>0:cell.set_text_props(ha='left')
fig2.text(.035,.055,'Analogman rows are hypothetical hits on a scene actor, not boss fights. Repeated branch rows share their authored profiles.\nN = normal budget, H = heavy budget, G = max grind. No player percentile, whole-fight damage total, or real elapsed TTK is claimed.\nSource: tools/stat_softcap_audit.py; baseline 0cbdeb2; see STAT-SOFTCAP.md and docs/data/stat-softcap/bosses.csv.',fontsize=11,linespacing=1.7)
fig2.savefig(OUT/'boss-table.png',dpi=120)
fig2.savefig(OUT/'boss-table.pdf')
with PdfPages(OUT/'review.pdf') as pdf:
 pdf.savefig(fig);pdf.savefig(fig2)
print('Wrote summary, full boss table and two-page review PDF')
