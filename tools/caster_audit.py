#!/usr/bin/env python3
"""Which wild Digimon really cast each technique in a fight that can be had again.

A placement of content/maps/<MAP>.json is only a fight when two things hold. Something puts a Digimon in its slot: the
screen's MAPHEAD section (`set_digimon`, story/base/maphead/screenNNN.dws) or the screen's script (`spawn`). And talking
to that slot fights: its `on_talk` is `recruitable(...)` (the game's wild encounter) or `fight()`. A slot nothing fills,
or one that only talks, never casts anything, whatever its move list says.

A fight can be had again when its Digimon is put there with no condition, by the hour or a roll, or for good once a
story step is done. One that stands only until a flag is set or a recruit joins is a single fight.

    tools/caster_audit.py            the techniques of the five new rows and who casts them
    tools/caster_audit.py --all      every learnable technique
"""
import ast
import collections
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEW_ROW_FIRST = 122
FIGHTS = ('recruitable', 'fight')
TIME_ONLY = re.compile(r'date_hour|random_roll\w*|clock\.hour|clock\.day|\broll\b|not:|\bnot\b|\band\b|\bor\b|[\d\s<>=!()&|]')


def _maphead():
    """screen -> scripts it runs, and (screen, slot) -> [conditions of each set_digimon]."""
    scripts, placed = collections.defaultdict(list), collections.defaultdict(list)
    for path in sorted(glob.glob(os.path.join(ROOT, 'story/base/maphead/screen*.dws'))):
        screen = int(re.search(r'screen(\d+)', path).group(1))
        stack, returned = [], []
        for line in open(path, encoding='utf-8'):
            s = line.strip()
            m = re.match(r'set_script\((\d+), *\d+\)', s)
            if m:
                scripts[screen].append(int(m.group(1)))
            if s.startswith('if'):
                stack.append(s[2:].strip(' {'))
            elif s.startswith('} else if'):
                stack[-1] = 'not:' + stack[-1] + ' ' + s[9:].strip(' {')
            elif s.startswith('} else'):
                stack[-1] = 'not:' + stack[-1]
            elif s == '}' and stack:
                stack.pop()
            elif s.startswith('return') and stack:
                returned.append('until:' + stack[-1])
            m = re.match(r'set_digimon\(species\([^)]*\), *(\d+)', s)
            if m:
                placed[(screen, int(m.group(1)))].append(stack + returned)
    return scripts, placed


class _Spawns(ast.NodeVisitor):
    def __init__(self, out):
        self.out, self.stack, self.returned = out, [], []

    def visit_If(self, node):
        test = ast.unparse(node.test)
        self.stack.append(test)
        for child in node.body:
            self.visit(child)
        if any(isinstance(child, ast.Return) for child in node.body):
            self.returned.append('until:' + test)
        self.stack[-1] = 'not:' + test
        for child in node.orelse:
            self.visit(child)
        self.stack.pop()

    def visit_Call(self, node):
        if getattr(node.func, 'id', '') == 'spawn':
            for kw in node.keywords:
                if kw.arg == 'slot' and isinstance(kw.value, ast.Constant):
                    self.out[kw.value.value].append(self.stack + self.returned)
        self.generic_visit(node)


def _scripts():
    """script -> {slot: what talking to it does}, and script -> {slot: [conditions of each spawn]}."""
    talks, spawns = collections.defaultdict(dict), collections.defaultdict(lambda: collections.defaultdict(list))
    for path in glob.glob(os.path.join(ROOT, 'story/base/zones/*/s*/*.py')):
        m = re.search(r'/s(\d+)(-\d+)?/', path)
        if not m:
            continue
        script = int(m.group(1))
        tree = ast.parse(open(path, encoding='utf-8').read())
        slots = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) \
                    and getattr(node.value.func, 'attr', '') == 'npc':
                for kw in node.value.keywords:
                    if kw.arg == 'slot' and isinstance(kw.value, ast.Constant):
                        slots[node.targets[0].id] = kw.value.value
            if not isinstance(node, ast.FunctionDef):
                continue
            _Spawns(spawns[script]).visit(node)
            for deco in node.decorator_list:
                if isinstance(deco, ast.Attribute) and deco.attr == 'on_talk' and getattr(deco.value, 'id', '') in slots:
                    top = [ast.unparse(stmt) for stmt in node.body]
                    if any(t.startswith('recruitable(') for t in top):
                        kind = 'recruitable'
                    elif any(t.startswith('fight(') for t in top):
                        kind = 'fight'
                    elif 'fight(' in ast.unparse(node) or 'recruitable(' in ast.unparse(node):
                        kind = 'story fight'
                    else:
                        kind = 'talk'
                    talks[script][slots[deco.value.id]] = kind
    return talks, spawns


def _comes_back(conditions):
    """True when a placement under these conditions is there again and again."""
    for cond in conditions:
        if cond.startswith('until:'):       # an early return that stops once the story moves on: there for good after it
            continue
        rest = TIME_ONLY.sub('', re.sub(r'is_recruited\(species\("[^"]*"\)\)', 'R', cond))
        if not rest:
            continue
        # a positive test of a recruit or of "no longer ..." holds for good; anything else is a story window
        if cond.startswith('not:(!') or re.fullmatch(r'\(?.*&& is_recruited\(.*\)\)?', cond):
            continue
        return False
    return True


def casters():
    """technique name -> {'again': [...], 'once': [...], 'never': [...]} of 'Species@MAP/slot'."""
    species = {}
    for path in glob.glob(os.path.join(ROOT, 'content/species/*.json')):
        doc = json.load(open(path, encoding='utf-8'))
        species[doc['name'] + str(doc['id'])] = doc
        if doc['name'] not in species or species[doc['name']]['id'] > doc['id']:
            species[doc['name']] = doc
    screens = {}
    for path in glob.glob(os.path.join(ROOT, 'content/screens/*.json')):
        number, name = os.path.basename(path)[:-5].split('-', 1)
        screens[name.upper()] = int(number)
    scripts, placed = _maphead()
    talks, spawns = _scripts()
    out = collections.defaultdict(lambda: collections.defaultdict(list))
    for path in sorted(glob.glob(os.path.join(ROOT, 'content/maps/*.json'))):
        name = os.path.basename(path)[:-5]
        screen = screens.get(name)
        for entry in json.load(open(path, encoding='utf-8')).get('digimon', []):
            slot = entry['slot']
            puts = list(placed.get((screen, slot), []))
            kinds = []
            for script in scripts.get(screen, []):
                puts += spawns[script].get(slot, [])
                kinds.append(talks[script].get(slot))
            if not puts or not any(k in FIGHTS for k in kinds):
                where = 'never'
            elif any(_comes_back(conditions) for conditions in puts):
                where = 'again'
            else:
                where = 'once'
            listed = (species.get(entry['species']) or {}).get('techniques') or []
            for move, prio in zip(entry['moves'], entry['prios']):
                index = move - 46
                if move != 255 and prio and 0 <= index < len(listed) and listed[index]:
                    out[listed[index]][where].append(f"{entry['species']}@{name}/{slot}")
    return out


def techniques():
    docs = [json.load(open(p, encoding='utf-8')) for p in glob.glob(os.path.join(ROOT, 'content/techniques/*.json'))]
    return sorted(docs, key=lambda d: d['id'])


def main(argv):
    found = casters()
    for tech in techniques():
        if tech['id'] < NEW_ROW_FIRST and '--all' not in argv:
            continue
        got = found.get(tech['name'], {})
        again = sorted({c.split('@')[0] for c in got.get('again', [])})
        print(f"{tech['id']:3} {tech['name']:<18} {len(got.get('again', [])):3} fights  {', '.join(again) or '-'}"
              f"   (once {len(got.get('once', []))}, never {len(got.get('never', []))})")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
