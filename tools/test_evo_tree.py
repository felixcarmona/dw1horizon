#!/usr/bin/env python3
"""Permanent evolution topology guard, from source or a built archive.

  tools/test_evo_tree.py [DIGI.DAT]
Special/story roots, wild-only recolours, canon Megas and specialty exceptions
are documented in content/tables/evolution-tree.json.
"""
import json
import sys

import evo_tree as T


def disc_routes():
    return {(p, c) for p, row in enumerate(T.S.originals().rec)
            for c in (row.get('evoPaths') or {}).get('to', []) if c > 0}


def ultimate_rules(sp, table):
    """The (from, to) ids of the documented Ultimate rules, or None when they differ from evolutionUltimate."""
    names = {s['name']: t for t, s in sorted(sp.items(), reverse=True) if 'partner' in s}
    rows = json.loads((T.ROOT / 'content/tables/evolution-rules.json').read_text())['evolutionUltimate']
    pairs = [(names[r['from']], names[r['to']]) for r in table.get('ultimate_rules', [])]
    if sorted(pairs) != sorted((r['from'], r['to']) for r in rows) or not all(r.get('reason') for r in table.get('ultimate_rules', [])):
        return None
    return pairs


def check(sp, kids, table):
    names = {s['name']: t for t, s in sorted(sp.items(), reverse=True) if 'partner' in s}
    natural = set()
    todo = [t for t, s in sp.items() if s['level'] == 'fresh']
    while todo:
        t = todo.pop()
        if t in natural:
            continue
        natural.add(t)
        todo.extend(kids.get(t, []))
    errors = []
    original_routes = disc_routes()
    allowed_specialties = {('Otamamon', 'Geremon')}
    for entry in table['specialty_exceptions']:
        if (entry['parent'], entry['child']) not in allowed_specialties or not entry.get('reason'):
            errors.append('specialty exception must be a documented permitted canon route')
    canon_links = table.get('canon_link_exceptions', [])
    if len(canon_links) != 1 or any(
            (e.get('parent'), e.get('child')) != ('Tsunomon', 'Gabumon') or not e.get('reason')
            for e in canon_links):
        errors.append('canon link allow-list must contain only documented Tsunomon -> Gabumon')
    # the level a vanilla species has with NEW DIGIMON off (Phoenixmon and HerculesKabuterimon are Ultimates there)
    off = {t: T.S.LEVELS[o] for t, _, o in T.S.level_swaps(sp)}
    for t, s in sp.items():
        if 'vanilla_as' in s:
            target = sp.get(s['vanilla_as'], {})
            level = 'ultimate' if s['level'] == 'mega' else s['level']
            if off.get(s['vanilla_as'], target.get('level')) != level or not target.get('vanilla'):
                errors.append(f'{s["name"]}: vanilla_as must name a vanilla {level}')
    # Disc and story species too (2026-11-03): NEW DIGIMON off gives them their disc level back at run time.
    for t in table.get('canon_ultimates', []):
        if sp[t]['level'] != 'ultimate':
            errors.append(f'{sp[t]["name"]}: canon Ultimate must be level 5')
    for t in table['sheet_megas']:
        if sp[t]['level'] != 'mega':
            errors.append(f'{sp[t]["name"]}: sheet Mega must be level 6')
    incoming = {}
    for p, children in kids.items():
        if sp[p]['level'] != 'in-training' and len(set(children)) > 6:
            errors.append(f'{sp[p]["name"]}: more than six children')
        for c in set(children):
            incoming.setdefault(c, set()).add(p)
    for c, parents in incoming.items():
        if len(parents) > 5:
            errors.append(f'{sp[c]["name"]}: more than five parents')
    accessible = set(natural)
    todo = [names[n] for n in table['special_routes']]
    while todo:
        t = todo.pop()
        if t in accessible:
            continue
        accessible.add(t)
        todo.extend(kids.get(t, []))
    # Numemon's fallback and other documented special raises are partners too.
    checked = accessible | {t for t, s in sp.items() if 'partner' in s and s['level'] in ('rookie', 'in-training')}
    for p in sorted(checked):
        level = sp[p]['level']
        target_level, count = {'champion': ('ultimate', 2), 'rookie': ('champion', 4),
                               'in-training': ('rookie', 1)}.get(level, ('', 0))
        actual = sum(sp[c]['level'] == target_level for c in set(kids.get(p, [])))
        if actual < count:
            errors.append(f'{sp[p]["name"]}: {actual} {target_level} targets; needs {count}')
    # Count distinct targets across ordinary paths and timed rules.
    rules = ultimate_rules(sp, table)
    if rules is None:
        errors.append('ultimate_rules must match evolution-rules.json evolutionUltimate')
        rules = []
    for p, c in rules:
        if sp[p]['level'] != 'ultimate' or sp[c]['level'] != 'mega':
            errors.append(f'{sp[p]["name"]} -> {sp[c]["name"]}: an Ultimate rule must lead an Ultimate to a Mega')
        if not (set(sp[p]['specialties']) - {None}) & (set(sp[c]['specialties']) - {None}):
            errors.append(f'{sp[p]["name"]} -> {sp[c]["name"]}: no shared specialty')
    for p in sorted(checked):
        if sp[p]['level'] == 'ultimate':
            targets = {c for c in kids.get(p, []) if sp[c]['level'] == 'mega'}
            targets.update(c for parent, c in rules if parent == p)
            if len(targets) < 2:
                errors.append(f'{sp[p]["name"]}: {len(targets)} Mega targets; needs 2')
    off_routes = {tuple(pair) for pair in table.get('off_routes', {}).get('pairs', [])}
    for p, c in off_routes:
        if not ((24 in (p, c) and sp[24]['level'] == 'ultimate') or
                ((p, c) in original_routes and c in (59, 60) and
                 sp[p]['level'] == 'champion' and sp[c]['level'] == 'mega')):
            errors.append('off_routes: only documented native tier changes are permitted')
        if c not in sp[p].get('off', {}).get('evolution', {}).get('to', []):
            errors.append(f'{sp[p]["name"]} -> {sp[c]["name"]}: missing explicit off route')
    for p, c in sorted(original_routes):
        if c not in kids.get(p, []) and (p, c) not in off_routes:
            errors.append(f'{sp[p]["name"]} -> {sp[c]["name"]}: original disc route removed')
    for t, s in sp.items():
        if 'partner' in s and s['level'] != 'none' and t not in accessible:
            errors.append(f'{s["name"]}: no natural or documented special route')
    for name, entry in table['children'].items():
        s = sp[names[name]]
        bonus = s['evolution']['requirements']['digimon']
        if not entry.get('disc') and bonus > 0 and bonus not in [names[p] for p in entry['parents']]:
            errors.append(f'{name}: parent bonus names a removed route')
        if entry.get('chain') and sp[names[name]]['evolution']['requirements']['digimon'] != names[entry['parents'][0]]:
            errors.append(f'{name}: Mega bonus must name its first listed parent')
    exceptions = {(e['parent'], e['child']) for e in table['specialty_exceptions']}
    exceptions |= {(e['parent'], e['child']) for e in canon_links
                   if (e.get('parent'), e.get('child')) == ('Tsunomon', 'Gabumon') and e.get('reason')}
    megas = set(table['canon_megas'])
    if table.get('disc_mega_routes'):
        errors.append('Champion-to-Mega exceptions are forbidden')
    for p, children in kids.items():
        for c in children:
            parent, child = sp[p], sp[c]
            pair = parent['name'], child['name']
            if T.LEVEL_NO.get(child['level'], 0) != T.LEVEL_NO.get(parent['level'], 0) + 1:
                errors.append(f'{pair[0]} -> {pair[1]}: evolution level step must be +1')
            if (p, c) not in original_routes and not (set(parent['specialties']) - {None}) & (set(child['specialties']) - {None}) and pair not in exceptions:
                errors.append(f'{pair[0]} -> {pair[1]}: no shared specialty')
            if child['name'] in megas and parent['level'] == 'champion':
                errors.append(f'{pair[0]} -> {pair[1]}: Champion parent of a canon Mega')
            if c in table['sheet_megas'] and c >= T.S.NUM_ORIGINAL and parent['level'] != 'ultimate':
                errors.append(f'{pair[0]} -> {pair[1]}: imported Mega parent must be Ultimate')
    for name in table['record_parents']:
        if not T.S.is_record_original(sp[names[name]]):
            errors.append(f'{name}: evolution parent requires a cached record row')
    for name in table['wild_only']:
        ids = {t for t, s in sp.items() if s['name'] == name}
        if any('partner' in sp[t] for t in ids) or any(ids & set(cs) for cs in kids.values()):
            errors.append(f'{name}: wild-only recolour became a partner or target')
    return errors


def practical_errors(sp, kids, table):
    errors = []
    _, reqs, levels = T.model(sp)
    names = {s['name']: t for t, s in sorted(sp.items(), reverse=True) if 'partner' in s}
    checked, chains = 0, 0
    for name, entry in table['children'].items():
        c = names[name]
        for parent in entry['parents']:
            p = names[parent]
            if levels[p] == 2:
                checked += 1
                if not T.rookie_witness(p, c, kids, reqs, levels, sp):
                    errors.append(f'{parent} -> {name}: no practical Rookie picker state')
            if levels[p] == 4:
                checked += 1
                if not T.practical(p, c, kids, reqs, levels, sp):
                    errors.append(f'{parent} -> {name}: no practical picker state')
                if not entry.get('disc'):
                    signature = {stat for stat in T.ALL if reqs[c][stat] != -1}
                    if any(signature == {stat for stat in T.ALL if reqs[k][stat] != -1}
                           for k in kids[p] if k != c and k in reqs):
                        errors.append(f'{parent} -> {name}: identical sibling picker average')
    preserved = {'Analogman', 'Jijimon'}
    for name in table.get('canon_megas', []):
        if name in preserved:
            continue
        c = names[name]
        parents = [p for p, cs in kids.items() if c in cs]
        if not parents:
            errors.append(f'{name}: no Mega chain parent')
        for p in parents:
            chains += 1
            if not T.chain_witness(p, c, kids, reqs, levels, sp):
                errors.append(f'{sp[p]["name"]} -> {name}: no practical chain')
    # An Ultimate rule into an imported Mega scores like a single path after the Mega hours.
    for p, c in ultimate_rules(sp, table) or []:
        if sp[c]['name'] in preserved:
            continue
        chains += 1
        arrival = T.arrival_witness(p, kids, reqs, levels, sp)
        targets = [child for parent, child in ultimate_rules(sp, table) if parent == p]
        if not arrival or not T.practical(p, c, {**kids, p: targets}, reqs, levels, sp,
                                         arrival['stats'], 60, kind='rule'):
            errors.append(f'{sp[p]["name"]} -> {sp[c]["name"]}: no practical Ultimate rule')
    return errors, checked, chains


def main():
    sp, _, table = T.load()
    archives = [a for a in sys.argv[1:] if not a.startswith('--')]
    if archives:
        import evo_graph
        graph = evo_graph.graph(archives[0])
        kids = {p: [c for c in g['to'] if c in sp] for p, g in graph.items()}
    else:
        kids, _, _ = T.model(sp)
    errors = check(sp, kids, table)
    if '--practical' in sys.argv:
        practical, checked, chains = practical_errors(sp, kids, table)
        errors.extend(practical)
        print(f'practical picker routes: {checked}; chain-parent routes: {chains}')
    for error in errors:
        print('ERROR:', error)
    print(f'evolution tree: {len(errors)} failures')
    return bool(errors)


if __name__ == '__main__':
    sys.exit(main())
