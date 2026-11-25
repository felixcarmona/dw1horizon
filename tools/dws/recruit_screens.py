"""Keep ordinary wild encounters away from waiting extended-story recruits, and from an NPC placed with `alone=` while
its condition holds (a resident challenger: the meeting is one against one).

Only base talk handlers using recruitable() are ordinary wild encounters. Direct
fight() scenes, services and NPCs referenced by story events keep their setup.
"""
import ast
from functools import cache
from pathlib import Path
import re

from . import recruitment


def requires_unrecruited(condition, trigger):
    if condition == ('not', ('trig', trigger)):
        return True
    return condition[0] == 'and' and any(requires_unrecruited(c, trigger) for c in condition[1])


def waiting_recruits(comp):
    roster = recruitment.roster()
    placements = {(screen, slot, species) for screen, slot, species, *_ in comp.placements}
    result = {}
    for screen, data in ((comp.city or {}).get('presence') or {}).items():
        for slot, species, _, condition in data.get('npcs', []):
            if (screen, slot, species) not in placements or species < 112 or species not in roster:
                continue
            flag = recruitment.recruit_trigger(species)
            if requires_unrecruited(condition, flag):
                result.setdefault(screen, []).append((slot, condition))
    return result


@cache
def ordinary_slots(screen):
    from .py import naming
    _, screens = naming.disc_screens()
    script = next((sid for sid, ids in screens.items() if screen in ids), None)
    if script is None:
        return set()
    source = next((p for p in (Path(naming.BASE) / 'zones').rglob('script.py')
                   if p.parent.name.startswith(f's{script:03}-')), None)
    if source is None:
        return set()
    tree = ast.parse(source.read_text())
    members = {name: sid for sid, name in naming.enum_members('species').items()}
    npcs = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        call = node.value
        if (isinstance(call.func, ast.Name) and call.func.id == 'entity' and len(call.args) == 1
                and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, int) and call.args[0].value >= 5):
            npcs[node.targets[0].id] = (call.args[0].value - 5, None)     # `entity(6)`: slot 1, its species is the .MAP's
            continue
        if not isinstance(call.func, ast.Attribute) or call.func.attr != 'npc':
            continue
        slot = next((k.value.value for k in call.keywords if k.arg == 'slot' and isinstance(k.value, ast.Constant)), None)
        species = members.get(call.args[0].attr) if call.args and isinstance(call.args[0], ast.Attribute) else None
        if slot is not None and species is not None:
            npcs[node.targets[0].id] = (slot, species)
    slots = set()
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        targets = [d.value.id for d in node.decorator_list if isinstance(d, ast.Attribute)
                   and d.attr == 'on_talk' and isinstance(d.value, ast.Name)]
        if len(targets) != 1 or targets[0] not in npcs:
            continue
        target = targets[0]
        slot, species = npcs[target]
        calls = [n for stmt in node.body for n in ast.walk(stmt) if isinstance(n, ast.Call)]
        wild = [c for c in calls if isinstance(c.func, ast.Name) and c.func.id == 'recruitable']
        if not wild:
            continue
        # Calls with state changes, shared scene helpers or direct battles require
        # an authored review; do not hide their entities automatically.
        if any(not isinstance(c.func, ast.Name) or c.func.id not in ('recruitable', 'say') for c in calls):
            continue
        joins = {members.get(k.value.attr) for c in wild for k in c.keywords
                 if k.arg == 'joins' and isinstance(k.value, ast.Attribute)} or {species}
        if None in joins or joins & recruitment.roster():               # (an entity with no `joins`: species unknown)
            continue
        if any(not c.args or not isinstance(c.args[0], ast.Name) or c.args[0].id != target for c in wild):
            continue
        slots.add(slot)
    return slots


def absent(condition):
    """Negate the complete placement guard, retaining time and story requirements."""
    kind = condition[0]
    if kind == 'not':
        return condition[1]
    if kind in ('and', 'or'):
        return ('or' if kind == 'and' else 'and', [absent(c) for c in condition[1]])
    return ('not', condition)


def alone_npcs(comp):
    """`alone slot K when C;` rules: {screen: [(slot, C)]}, C the condition under which the wilds stay away."""
    return {screen: list(data['alone']) for screen, data in ((comp.city or {}).get('presence') or {}).items() if data.get('alone')}


def guard_wilds(comp, text, report):
    from .backend import CLOCK_PSTAT, P_SETUP_DATE, presence_if
    guards = alone_npcs(comp)
    if recruitment.ACTIVE.get():
        for screen, recruits in waiting_recruits(comp).items():
            guards.setdefault(screen, []).extend(recruits)
    for screen, recruits in sorted(guards.items()):
        slots = ordinary_slots(screen)
        if not slots:
            report.append(f'recruit screen {screen}: no ordinary wild handlers; story encounters retained')
            continue
        section = re.search(rf'^sec{screen}:.*?(?=^sec\d+:|\Z)', text, re.S | re.M)
        if section is None:
            raise ValueError(f'recruit screen {screen}: missing setup section')
        body = section.group()
        sets = re.findall(r'^\s*SET_DIGIMON\s+(\d+),\s*(\d+),[^\n]*', body, re.M)
        guarded_species = {int(sp) for sp, slot in sets if int(slot) in slots}
        load_species = {sp for sp in guarded_species
                        if all(int(slot) in slots for species, slot in sets if int(species) == sp)}
        conditions = [presence_if(absent(condition), screen, slot) for slot, condition in recruits]
        date = (f'    STORE_DATE p{P_SETUP_DATE}\n'
                if any(p in condition.split() for condition in conditions for p in CLOCK_PSTAT.values()) else '')
        count = 0
        def wild(line):
            m = re.fullmatch(r'\s*(LOAD_DIGIMON|SET_DIGIMON)\s+(\d+)(?:,\s*(\d+),[^\n]*)?[^\S\n]*(?:;[^\n]*)?', line)
            if not m: return False
            op, species, slot = m.group(1), int(m.group(2)), m.group(3)
            return op == 'LOAD_DIGIMON' and species in load_species or op == 'SET_DIGIMON' and int(slot) in slots
        def wrap(match):                    # one guard for each run of wild lines next to each other (MAPHEAD has little room)
            nonlocal count
            label = f'recruit_screen_{screen}_{count}'
            count += 1
            guards = ''.join(f'    IF {condition}, else {label}\n' for condition in conditions)
            return f'{date}{guards}{match.group().rstrip(chr(10))}\n{label}:\n'
        lines = body.splitlines(keepends=True); out = []; run = []
        for line in lines + ['']:
            if line and wild(line.rstrip('\n')): run.append(line); continue
            if run: out.append(wrap(re.match(r'(?s).*', ''.join(run)))); run = []
            out.append(line)
        body = ''.join(out)
        text = text[:section.start()] + body + text[section.end():]
        report.append(f'recruit screen {screen}: wild slots {sorted(slots)}, require waiting recruits absent (slots {sorted(slot for slot, _ in recruits)})')
    return text
