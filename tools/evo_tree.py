#!/usr/bin/env python3
"""Apply the curated evolution tree without rewriting unrelated species.

Run without arguments to inspect the picker-resolved plan; --write applies it.
Topology and documented exceptions live in content/tables/evolution-tree.json.
"""
import collections
import functools
import hashlib
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import species as S
import evo_check as E

TABLE = ROOT / 'content/tables/evolution-tree.json'

ROLE_STATS = {'hp-defense': ('hp', 'defense', 'brain'), 'offense-speed': ('offense', 'speed', 'hp'),
              'mp-brains': ('mp', 'brain', 'speed'), 'even': None, 'all-low': ()}
ALL = ('hp', 'mp', 'offense', 'defense', 'speed', 'brain')
LEVEL_NO = {'fresh': 1, 'in-training': 2, 'rookie': 3, 'champion': 4, 'ultimate': 5, 'mega': 6}


def h(name, salt):
    return hashlib.sha256(f'evo-lines-2026-10-15/{salt}/{name}'.encode()).digest()[0]


def role_stats(s):
    tt = s['partner']['training_type']
    r = ROLE_STATS[tt]
    if r is None:                               # even: three of the six, by name
        order = sorted(ALL, key=lambda k: h(s['name'], k))
        r = tuple(order[:3])
    return r


def size_weight(s, top):
    """A weight by body size: the model's height in steps (10 .. top)."""
    hgt = int(s['model'].get('height', 300))
    steps = list(range(10, top + 1, 10))
    i = min(len(steps) - 1, max(0, (hgt - 150) // 150))
    return steps[i]


def care(s, level):
    att = s.get('attribute', 'free')
    if level == 'champion':
        return {'vaccine': (1, 16), 'data': (3, 16), 'free': (5, 16), 'virus': (3, 0)}.get(att, (5, 16))
    return {'vaccine': (5, 16), 'data': (10, 16), 'free': (15, 16), 'virus': (10, 0)}.get(att, (15, 16))


def candidates(s, req, lv):
    """Other requirement rows for a species whose first one a sibling shadows, or that takes a disc route's
    canonical state: other stat sets (its role's stats first), the other care mode, no parent bonus."""
    rs = list(role_stats(s)) or ['hp', 'mp', 'offense']
    rest = [k for k in ALL if k not in rs]
    sets = [tuple(rs[:2]), (rs[0],), tuple(rs[:3]), (rs[0], rs[2]), (rs[1], rs[2]), (rs[1],)]
    sets += [(rs[0], k) for k in rest] + [(rs[1], k) for k in rest] + [(k,) for k in rest]
    if lv == 'champion': base = [100, 100, 100]
    else:
        hi, lo = (500, 400) if req['techs'] == 40 else (400, 300)
        base = [hi, hi, lo]
    # digimon -1: no free bonus point from the parent (DW1's own pattern: the bonus then needs the techniques);
    # +100: thresholds a notch above a disc sibling's own
    for up, digimon, flags, st in itertools.product((0, 100), (req['digimon'], -1), (req['flags'], req['flags'] ^ 16), sets):
        r = dict(req, flags=flags, digimon=digimon)
        for k in ALL: r[k] = -1
        for i, k in enumerate(st): r[k] = base[i] + up
        yield r


def load():
    sp = S.load_content()
    by_name = {}
    for t, s in sorted(sp.items(), key=lambda kv: ('partner' not in kv[1], kv[0])):
        by_name.setdefault(s['name'], t)
    return sp, by_name, json.loads(TABLE.read_text())


def model(sp):
    """Record order and boot links, including the engine layer's original slots."""
    original = S.originals()
    engine = json.loads((ROOT / 'content/balance/engine/tables.json').read_text())['species']
    kids, reqs = {}, {}
    records = {t for t, s in sp.items() if t >= S.NUM_ORIGINAL or S.is_record_original(s)}
    for t, s in sp.items():
        if t in records:
            ev = s.get('evolution', {})
            kids[t] = [x for x in ev.get('to', []) if x > 0]
            if ev.get('requirements'): reqs[t] = dict(ev['requirements'])
        else:
            row = original.rec[t]
            paths = dict(row.get('evoPaths') or {})
            paths.update(engine.get(str(t), {}).get('evoPaths', {}))
            paths.update({k: s.get('evolution', {})[k] for k in ('from', 'to') if k in s.get('evolution', {})})
            kids[t] = [x for x in paths.get('to', []) if x > 0 and x in sp]
            req = dict(row.get('evoReqs') or {})
            req.update(engine.get(str(t), {}).get('evoReqs', {}))
            req.update(s.get('evolution', {}).get('requirements', {}))
            if req: reqs[t] = req
    for t in sorted(records):
        if 'partner' not in sp[t]: continue
        for p in sp[t].get('evolution', {}).get('from', []):
            if p in kids and t not in kids[p]: kids[p].append(t)
    levels = {t: LEVEL_NO.get(s['level'], 0) for t, s in sp.items()}
    return kids, reqs, levels



def training_rates(s):
    """Conservative unupgraded File City gains, in HP/MP tens and other stats.

    No manual, gym recruitment, slot prizes or ten-session counter bonus.
    Brains uses the MP affinity, as TRN_calculateTrainingMultiplier does.
    """
    return _training_rates(s['partner']['training_type'], LEVEL_NO[s['level']])


@functools.lru_cache(None)
def _training_rates(training_type, level):
    data = json.loads((ROOT / 'content/tables/training.json').read_text())['training']
    types = ('even', 'offense-speed', 'mp-brains', 'hp-defense', 'all-low')
    kind = types.index(training_type)
    return tuple(max(1, 8 * (data['gainTenths'][1 if i == 5 else i][kind]
                           * data['levelTenths'][level] // 10) // 10) for i in range(6))


_PRACTICAL = {}


def practical(cur, child, kids, reqs, levels, sp, base=None, budget=72):
    """A picker witness within a training budget; never assumes 999 stats or an imported target’s 40-move bonus.

    A Champion starts from 1500 HP/MP and 150 other stats; 72 sessions leave
    half its 144 hours for sleep, food, rest and 50 short battles. Chain callers supply
    the actual stats after the Perfect's gains and allow 48 more sessions.
    Secondary gym gains are omitted, making the session bound conservative.
    """
    base = tuple(base or (150,) * 6)
    cache_key = (cur, child, tuple(kids[cur]), tuple((t, tuple(reqs[t].items())) for t in kids[cur] if t in reqs), base, budget)
    if cache_key in _PRACTICAL:
        return _PRACTICAL[cache_key]
    rates = training_rates(sp[cur])
    row = reqs[child]
    options = []
    for i, stat in enumerate(ALL):
        threshold = max(base[i], row[stat])
        options.append(sorted({base[i], threshold, max(threshold, 450), max(threshold, 600)}))
    # Cheap states first. Repeated calls during resolve keep this finite.
    states = []
    for vals in itertools.product(*options):
        sessions = sum((max(0, v - b) + rate - 1) // rate for v, b, rate in zip(vals, base, rates))
        if sessions <= budget:
            states.append((sessions, vals))
    for sessions, vals in sorted(states):
        # Round each requested stat up to a whole attainable training gain.
        vals = tuple(b + ((max(0, v-b) + rate-1)//rate)*rate for v, b, rate in zip(vals, base, rates))
        st = {stat: vals[i] * (10 if i < 2 else 1) for i, stat in enumerate(ALL)}
        mistakes_allowed = (0, 1, 3, 5, max(0, row['care'])) if child < S.NUM_ORIGINAL and not S.is_record_original(sp[child]) else (0, 1, 3, 5)
        for mistakes in dict.fromkeys(mistakes_allowed):
            for weight in (row['weight'], row['weight'] - 5, row['weight'] + 5):
                # Disc routes retain their original late-raise requirements. Learned
                # moves survive rebirth, so 35 techniques is possible for Gigadramon.
                tech_counts = (20, 35) if child < S.NUM_ORIGINAL and not S.is_record_original(sp[child]) else (20,)
                for techs in tech_counts:
                    bonus = (0 if row['flags'] & 1 else 50, techs, 100, 100)
                    if E.pick(cur, kids[cur], reqs, levels, st, mistakes, weight, 'stats', bonus) == child:
                        result = dict(stats=vals, care=mistakes, weight=weight, sessions=sessions, bonus=bonus)
                        _PRACTICAL[cache_key] = result
                        return result
    _PRACTICAL[cache_key] = None
    return None


def after_evolution(s, stats):
    """Natural unscaled evolution's stat blend, in comparable stat units."""
    gains = s['evolution']['gains']
    formula = json.loads((ROOT / 'content/tables/evolution-rules.json').read_text())['evolutionFormula']['stat']
    result = []
    for i, key in enumerate(('hp', 'mp', 'offense', 'defense', 'speed', 'brains')):
        mul = 10 if i < 2 else 1
        value, gain = stats[i] * mul, gains[key]
        value = value + gain // formula['gainDiv'] if value >= gain else (value + gain) // formula['averageDiv']
        result.append(value // mul)
    return tuple(result)


def arrival_witness(target, kids, reqs, levels, sp, visited=()):
    """Find a real chain into an Ultimate, including existing Mega-to-Mega lines."""
    if target in visited:
        return None
    parents = [p for p, cs in kids.items() if target in cs]
    for p in parents:
        if levels[p] == 4:
            w = practical(p, target, kids, reqs, levels, sp)
            if w:
                return dict(stats=after_evolution(sp[target], w['stats']),
                            path=[p, target], witnesses=[w])
        elif levels[p] == 5:
            previous = arrival_witness(p, kids, reqs, levels, sp, visited + (target,))
            if not previous:
                continue
            w = practical(p, target, kids, reqs, levels, sp, previous['stats'], 48)
            if w:
                return dict(stats=after_evolution(sp[target], w['stats']),
                            path=previous['path'] + [target], witnesses=previous['witnesses'] + [w])
    return None


def chain_witness(parent, child, kids, reqs, levels, sp):
    previous = arrival_witness(parent, kids, reqs, levels, sp)
    if previous:
        w = practical(parent, child, kids, reqs, levels, sp, previous['stats'], 48)
        if w:
            return dict(path=previous['path'] + [child], witnesses=previous['witnesses'] + [w])
    return None


def resolve(sp, editable, primary, problems):
    """Find a winning row for every parent and preserve original canonical states."""
    kids, reqs, levels = model(sp)
    parents = collections.defaultdict(list)
    for p, cs in kids.items():
        for c in cs: parents[c].append(p)
    managed = {t for t, s in sp.items() if 'evolution' in s and
               (t >= S.NUM_ORIGINAL or S.is_record_original(s))}
    table = json.loads(TABLE.read_text())
    managed -= {t for t, s in sp.items() if s['name'] in table['record_parents']}
    def ok(c):
        for p in parents[c]:
            kind = 'in-training' if levels[p] == 2 else 'stats'
            if not E.reachable(p, c, kids[p], reqs, levels, kind): return False
            if levels[p] == 4 and not practical(p, c, kids, reqs, levels, sp): return False
            if c in primary and levels[p] == 5:
                if not chain_witness(p, c, kids, reqs, levels, sp): return False
            old = [k for k in kids[p] if k not in managed]
            if any(k in reqs and not E.keeps_canonical(p, k, old, kids[p], reqs, levels, kind) for k in old):
                return False
        return True
    for _ in range(10):
        changed = False
        for c in sorted(editable):
            if ok(c): continue
            first = reqs[c]
            siblings = {k for p in parents[c] for k in kids[p] if k != c and k in reqs}
            before = {k for k in siblings if ok(k)}
            for row in candidates(sp[c], first, sp[c]['level']):
                if c in primary and row['digimon'] != primary[c]: continue
                reqs[c] = row
                if ok(c) and all(ok(k) for k in before):
                    sp[c]['evolution']['requirements'] = row
                    changed = True
                    break
            else: reqs[c] = first
        if not changed: break
    for c in sorted(editable):
        if not ok(c): problems.append(f'{sp[c]["name"]}: no practical picker row from every parent with canonical routes kept')


def plan():
    sp, names, table = load()
    editable, primary, problems = set(), {}, []
    # Only listed children's reverse lists change. Disc children have no record
    # reverse list; their added routes belong in the record parents' to lists.
    for name, entry in table['children'].items():
        c = names[name]
        parents = [names[p] for p in entry['parents']]
        if entry.get('disc'):
            for p in parents:
                if p < S.NUM_ORIGINAL and not S.is_record_original(sp[p]): continue
                to = sp[p]['evolution']['to']
                if c not in to: to.append(c)
            continue
        ev = sp[c]['evolution']
        ev['from'] = parents
        editable.add(c)
        req = {k: -1 for k in ('digimon',) + ALL + ('care', 'weight', 'discipline', 'happiness', 'battles', 'techs')}
        req.update(digimon=parents[0], flags=0)
        chain = entry.get('chain', False)
        hi, lo = (500, 400) if chain else (400, 300)
        for i, stat in enumerate(role_stats(sp[c])[:3]): req[stat] = hi if i < 2 else lo
        req['care'], req['flags'] = care(sp[c], 'ultimate')
        req['weight'] = size_weight(sp[c], 60)
        req['techs'] = 40 if chain else 35
        ev['requirements'] = req
        if chain: primary[c] = parents[0]
    resolve(sp, editable, primary, problems)
    original, _, _ = load()
    for t, s in sp.items():
        before = original[t]
        if s == before:
            continue
        allowed = {'from', 'requirements'} if s['name'] in table['children'] and not table['children'][s['name']].get('disc') else set()
        # A forward list belongs to the record parent when a disc child has no reverse row.
        if any(e.get('disc') and s['name'] in e['parents'] for e in table['children'].values()):
            allowed.add('to')
        old_ev, new_ev = before.get('evolution', {}), s.get('evolution', {})
        if any(old_ev.get(k) != new_ev.get(k) for k in old_ev.keys() | new_ev.keys() if k not in allowed):
            problems.append(f'{s["name"]}: changed an unmanaged evolution field')
        if {k: v for k, v in before.items() if k != 'evolution'} != {k: v for k, v in s.items() if k != 'evolution'}:
            problems.append(f'{s["name"]}: changed an unmanaged species field')
    return sp, problems


def write(sp):
    count = 0
    for t, s in sp.items():
        path = Path(s['_path'])
        text = S.dumps(s)
        if text != path.read_text():
            path.write_text(text)
            count += 1
    return count


def main():
    sp, problems = plan()
    _, names, table = load()
    for name in table['children']:
        s = sp[names[name]]
        print(name, '<-', ', '.join(table['children'][name]['parents']), s.get('evolution', {}).get('requirements', {}))
    for problem in problems: print('ERROR:', problem)
    if problems: return 1
    if '--write' in sys.argv: print('wrote', write(sp), 'species')
    return 0


if __name__ == '__main__':
    sys.exit(main())
