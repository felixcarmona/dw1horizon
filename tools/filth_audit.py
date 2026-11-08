#!/usr/bin/env python3
"""Print Filth technique and specialty comparisons from owned JSON."""
import json
from pathlib import Path
from tools.battle_audit import damage, table

ROOT = Path(__file__).resolve().parents[1]
ELEMENTS = ['fire', 'battle', 'air', 'nature', 'ice', 'mech', 'filth']
BEFORE = {87: ['filth', None, None], 231: ['filth', 'battle', None],
          264: ['filth', 'battle', None], 307: ['filth', 'battle', None]}
ADDED = {87: ['Charm Perfume', 'Poison Powder'],
         231: ['Water Blit', 'Aqua Magic', 'Tear Drop', 'Counter'],
         264: ['Metal Sprinter', 'Power Crane'], 269: ['Metal Sprinter'],
         307: ['Water Blit', 'Aqua Magic', 'Tear Drop', 'Ice Needle', 'Winter Blast', 'Giga Freeze']}


def load(path):
    return json.loads((ROOT / path).read_text())


def report():
    rules = load('content/tables/battle-formulas.json')['battleFormulas']['damage']
    factors = load('content/tables/type-factors.json')['typeFactors']
    techniques = {s['id']: s for p in (ROOT/'content/techniques').glob('*.json') for s in [json.loads(p.read_text())]}
    species = {s['id']: s for p in (ROOT/'content/species').glob('*.json') for s in [json.loads(p.read_text())]}
    rows = []
    # Comparison specialty position; this does not change the learning table.
    for tid, position in [(36,1),(32,1),(20,1),(21,1),(23,1),(26,2),(24,2),(46,1),
                          (40,1),(42,1),(4,1),(3,1),(2,1),(0,1),(16,1),(17,1),(18,1),(19,1),(22,1),(8,1)]:
        t = techniques[tid]
        rows.append([t['name'],t['power'],t['mpCost']*3,t['accuracy'],
                     ('support' if t['power'] == 0 else '/'.join(str(damage(t['power'],o,d,30,rules)) for o,d in [(800,1300),(800,800),(1300,800)])),
                     f"{t['learnChances'][position]}% (slot {position+1})"])
    lines = ['### Technique numbers', '',
             'NORMAL; neutral element sum 30; 100% damage roll; no buffs or block. Damage columns are Offense minus Defense −500 / 0 / +500. Support effects are not direct damage: Aqua Magic and War Cry must not use the damage minimum as their effect value. MP is the runtime cost, three times stored `mpCost`. Learning rates require an unknown observed move, a matching specialty and inclusion in the current arsenal; they are per eligible roll, not guaranteed acquisition.', '',
             table(['Move','Power','MP/cast','Accuracy','Direct damage −500 / 0 / +500','Learn rate at proposed position'], rows), '',
             '### Incoming specialty sums', '',
             'Columns follow Fire / Battle / Air / Nature / Ice / Mech / Filth. Each sum enters damage with divisor 30. A null specialty contributes 10. Adding a specialty changes defense even without a new damaging move.', '',
             table(['Species','Before','Applied'], [[species[sid]['name'],
                 ' / '.join(map(str, [sum(10 if e is None else row[ELEMENTS.index(e)] for e in BEFORE[sid]) for row in factors])),
                 ' / '.join(map(str, [sum(10 if e is None else row[ELEMENTS.index(e)] for e in new) for row in factors]))]
                 for sid,new in [(87,['filth','nature',None]),(231,['filth','ice','battle']),(264,['filth','battle','mech']),(307,['filth','ice',None])]]), '',
             '### Current partner arsenals', '']
    for sid in [87,231,264,120,269,42,65,307,303]:
        s=species[sid]
        lines.append(f"- **{s['name']} ({sid})**: {' / '.join(e or '—' for e in s['specialties'])}; {', '.join(m for m in s['techniques'] if m)}.")
    byname = {t['name']: t for t in techniques.values()}
    lines += ['', '### Applied learning chances', '',
              'Unknown observed moves only; the runtime also checks the current arsenal. '
              'Buster Dive remains equipable at 500 power on BlackKingNumemon but must be learned '
              'before evolving (for example as Etemon): Filth/Ice has no Battle learning slot.', '']
    learning = []
    for sid, moves in ADDED.items():
        s = species[sid]
        for name in moves:
            t = byname[name]
            slot = s['specialties'].index(t['element'])
            assert name in s['techniques']
            learning.append([s['name'], name, slot + 1, f"{t['learnChances'][slot]}%",
                             hex(46 + s['techniques'].index(name))])
    lines += [table(['Species', 'Move', 'Specialty slot', 'Chance', 'Animation slot'], learning), '',
              '### Ordinary power ceilings', '']
    ceilings = []
    for sid, before in [(87,333),(231,211),(264,211),(269,722),(42,586),(65,586),(120,333),(307,500)]:
        ordinary = [t for name in species[sid]['techniques'] if name
                    for t in techniques.values() if t['name'] == name and t['id'] < 58 and name != 'Counter']
        ceilings.append([species[sid]['name'], before, max(t['power'] for t in ordinary)])
    lines += [table(['Species', 'Before', 'Applied (Counter excluded)'], ceilings)]
    return '\n'.join(lines)+'\n'


if __name__ == '__main__':
    print(report(), end='')
