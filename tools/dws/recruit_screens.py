"""Keep ordinary wild encounters away from waiting extended-story recruits.

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
                result.setdefault(screen, set()).add(flag)
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
        if joins & recruitment.roster():
            continue
        if any(not c.args or not isinstance(c.args[0], ast.Name) or c.args[0].id != target for c in wild):
            continue
        slots.add(slot)
    return slots


def guard_wilds(comp, text, report):
    if not recruitment.ACTIVE.get():
        return text
    for screen, flags in sorted(waiting_recruits(comp).items()):
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
        count = 0
        def wrap(match):
            nonlocal count
            op, species, slot = match.group(1), int(match.group(2)), match.group(3)
            if (op == 'LOAD_DIGIMON' and species not in load_species or
                    op == 'SET_DIGIMON' and int(slot) not in slots):
                return match.group()
            label = f'recruit_screen_{screen}_{count}'
            count += 1
            condition = ', and '.join(f'trigger {flag}' for flag in sorted(flags))
            return f'    IF {condition}, else {label}\n{match.group()}\n{label}:'
        body = re.sub(r'^\s*(LOAD_DIGIMON|SET_DIGIMON)\s+(\d+)(?:,\s*(\d+),[^\n]*)?[^\S\n]*(?:;[^\n]*)?$', wrap, body, flags=re.M)
        text = text[:section.start()] + body + text[section.end():]
        report.append(f'recruit screen {screen}: wild slots {sorted(slots)}, require recruited triggers {sorted(flags)}')
    return text
