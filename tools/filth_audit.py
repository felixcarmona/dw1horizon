#!/usr/bin/env python3
"""Print proposal-only Filth technique and specialty comparisons from owned JSON."""
import json
from pathlib import Path
from tools.battle_audit import damage, table

ROOT = Path(__file__).resolve().parents[1]
ELEMENTS = ['fire', 'battle', 'air', 'nature', 'ice', 'mech', 'filth']


def load(path):
    return json.loads((ROOT / path).read_text())


def report():
    rules = load('content/tables/battle-formulas.json')['battleFormulas']['damage']
    factors = load('content/tables/type-factors.json')['typeFactors']
    techniques = {s['id']: s for p in (ROOT/'content/techniques').glob('*.json') for s in [json.loads(p.read_text())]}
    species = {s['id']: s for p in (ROOT/'content/species').glob('*.json') for s in [json.loads(p.read_text())]}
    rows = []
    # Intended specialty position; it is not a new learning table.
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
             table(['Species','Current','Recommended'], [[species[sid]['name'],
                 ' / '.join(map(str, [sum(10 if e is None else row[ELEMENTS.index(e)] for e in species[sid]['specialties']) for row in factors])),
                 ' / '.join(map(str, [sum(10 if e is None else row[ELEMENTS.index(e)] for e in new) for row in factors]))]
                 for sid,new in [(87,['filth','nature',None]),(231,['filth','ice','battle']),(264,['filth','battle','mech']),(307,['filth','ice',None])]]), '',
             '### Current partner arsenals', '']
    for sid in [87,231,264,120,269,42,65,307,303]:
        s=species[sid]
        lines.append(f"- **{s['name']} ({sid})**: {' / '.join(e or '—' for e in s['specialties'])}; {', '.join(s['techniques'])}.")
    return '\n'.join(lines)+'\n'


if __name__ == '__main__':
    print(report(), end='')
