#!/usr/bin/env python3
"""Can every evolution target be reached? A model of the game's pickers (evolution.c calculateRequirementScore,
getInTrainingEvolutionTarget, getRookie/ChampionEvolutionTarget), run on the graph and requirements of a built
DIGI.DAT: for each parent and each of its targets, a search over partner states (each stat 0, the target's
threshold or 999; care mistakes 0, the target's or 30; the target's weight; battles, techniques, discipline and
happiness none, the target's or all) for one where the picker chooses it.
The "raised" adjustment is left out (no species raised yet).

  tools/evo_check.py [DIGI.DAT]      lists the targets no state reaches, per parent
"""
import sys as _sys
if __name__ == '__main__' and _sys.argv[1:2] in (['-h'], ['--help']): print(__doc__); _sys.exit(0)
import collections, itertools, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import species as S
import evo_graph

STATS = ('hp', 'mp', 'offense', 'defense', 'speed', 'brain')


def reqs_table(dat):
    """evoReqs per species id: the records (DIGI.DAT), the engine layer, the disc."""
    d, count, recs = S.read_archive(dat)
    eng = json.load(open(os.path.join(ROOT, 'content/balance/engine/tables.json')))['species']
    O = S.originals(); out = {}; source = S.load_content()
    for t in range(count):
        if recs[t] and recs[t]['flags'] & S.FLAG_PARTNER and (t >= S.NUM_ORIGINAL or t in S.record_originals(d)):
            out[t] = recs[t]['evoReqs']
        elif t < S.NUM_ORIGINAL:
            r = dict(O.rec[t]['evoReqs']) if O.rec[t].get('evoReqs') else None
            if str(t) in eng and 'evoReqs' in eng[str(t)]:          # the engine layer: differences from the disc
                r = dict(r or {k: -1 for k in STATS + ('digimon', 'care', 'weight', 'discipline', 'happiness',
                                                       'battles', 'techs')}, flags=(r or {}).get('flags', 0))
                r.update(eng[str(t)]['evoReqs'])
            r = dict(r or {})
            r.update(source.get(t, {}).get('evolution', {}).get('requirements', {}))
            if r: out[t] = r
    return out


def score(cur, req, level, st, care, weight, bonus=(0, 0, 0, 0)):
    battles, techs, discipline, happiness = bonus
    pts = 0
    if req.get('flags', 0) & 0x10:
        pts += care <= req['care']
    else:
        pts += care >= req['care']
    pts += req['weight'] - 5 <= weight <= req['weight'] + 5
    vals = [st['hp'] // 10, st['mp'] // 10, st['offense'], st['defense'], st['speed'], st['brain']]
    if level == 3:
        hi = max(i for i in range(6) if all(vals[i] >= v for v in vals))
        pts += req[STATS[hi]] == 1
    else:
        pts += all(vals[i] >= req[k] for i, k in enumerate(STATS))
    if req['battles'] == -1: b = False
    elif req.get('flags', 0) & 1: b = battles <= req['battles']
    else: b = battles >= req['battles']
    ok = (req['digimon'] != -1 and cur == req['digimon']) or (req['discipline'] != -1 and discipline >= req['discipline']) \
        or (req['happiness'] != -1 and happiness >= req['happiness']) or b \
        or (req['techs'] != -1 and techs >= req['techs'])
    return pts + bool(ok)


def pick(cur, targets, R, levels, st, care, weight, kind, bonus=(0, 0, 0, 0)):
    best, best_score = -1, 0
    for t in targets:
        if t not in R: continue
        sc = score(cur, R[t], levels[t], st, care, weight, bonus)
        if kind == 'in-training':
            if best_score < sc and sc >= 3: best, best_score = t, sc
        elif sc >= 3:
            req = R[t]; vals = [st['hp'] // 10, st['mp'] // 10, st['offense'], st['defense'], st['speed'], st['brain']]
            used = [vals[i] for i, k in enumerate(STATS) if req[k] != -1]
            avg = sum(used) // len(used) if used else 0
            if best_score < avg: best, best_score = t, avg
    return best


def states(cur, t, targets, R, levels, kind):
    """Every searched partner state in which the picker chooses t."""
    req = R[t]
    own = lambda k, hi: max(req[k], 0) if req[k] != -1 else hi
    bonuses = [(0, 0, 0, 0), (own('battles', 0), own('techs', 0), own('discipline', 0), own('happiness', 0)),
               (999, 99, 100, 100)]
    choices = []
    for k in STATS:
        base = req[k] if req[k] not in (-1, 1) else 50
        mul = 10 if k in ('hp', 'mp') else 1
        choices.append(sorted({0, base * mul, 999 * mul}))
    for vals in itertools.product(*choices):
        st = dict(zip(STATS, vals))
        for care in sorted({0, max(req['care'], 0), 30}):
            for bonus in bonuses:
                if pick(cur, targets, R, levels, st, care, req['weight'], kind, bonus) == t:
                    yield st, care, req['weight'], bonus


def canonical(cur, t, R, levels):
    """The partner state that meets t's own requirements exactly (required stats at their thresholds, the rest 0,
    its weight, its care mode, battles/techniques/discipline/happiness at its values)."""
    req = R[t]; mul = lambda k: 10 if k in ('hp', 'mp') else 1
    if levels[t] == 3: st = {k: (200 if req[k] == 1 else 10) * mul(k) for k in STATS}
    else: st = {k: max(req[k], 0) * mul(k) for k in STATS}
    care = 0 if req.get('flags', 0) & 0x10 else max(req['care'], 0)
    own = lambda k: max(req[k], 0)
    return st, care, req['weight'], (own('battles'), own('techs'), own('discipline'), own('happiness'))


def keeps_canonical(cur, t, old, targets, R, levels, kind):
    """A disc route that its canonical state chose among the disc's targets is still chosen with the new ones."""
    st, care, w, b = canonical(cur, t, R, levels)
    if pick(cur, old, R, levels, st, care, w, kind, b) != t: return True
    return pick(cur, targets, R, levels, st, care, w, kind, b) == t


def reachable(cur, t, targets, R, levels, kind):
    req = R[t]
    own = lambda k, hi: max(req[k], 0) if req[k] != -1 else hi
    # partner battles, techniques, discipline, happiness: none, exactly the target's, all
    bonuses = [(0, 0, 0, 0), (own('battles', 0), own('techs', 0), own('discipline', 0), own('happiness', 0)),
               (999, 99, 100, 100)]
    choices = []
    for k in STATS:
        base = req[k] if req[k] not in (-1, 1) else 50
        mul = 10 if k in ('hp', 'mp') else 1
        choices.append(sorted({0, base * mul, 999 * mul}))
    for vals in itertools.product(*choices):
        st = dict(zip(STATS, vals))
        for care in sorted({0, max(req['care'], 0), 30}):
            for bonus in bonuses:
                if pick(cur, targets, R, levels, st, care, req['weight'], kind, bonus) == t:
                    return True
    return False


def main():
    dat = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'build/full/DIGI.DAT')
    g = evo_graph.graph(dat); R = reqs_table(dat)
    LV = {'fresh': 1, 'in-training': 2, 'rookie': 3, 'champion': 4, 'ultimate': 5, 'mega': 6}
    levels = {t: LV.get(x['level'], 0) for t, x in g.items()}
    bad = []; n = 0
    for p, x in sorted(g.items()):
        kind = x['level']
        if kind not in ('in-training', 'rookie', 'champion', 'ultimate'): continue
        targets = [t for t in x['to'] if t in g]
        for t in targets:
            if t not in R: continue
            n += 1
            if not reachable(p, t, targets, R, levels, 'in-training' if kind == 'in-training' else 'stats'):
                bad.append((x['name'], g[t]['name']))
    print(f'{n} links checked; unreachable by the picker: {len(bad)}')
    for p, t in bad: print(f'  {p} -> {t}')
    # the disc's own routes (docs/reference/partner.md): of the states that chose a disc
    # child before the new species were added to its parent's list, how many still choose it
    sp = S.load_content()
    managed = {t for t, s in sp.items() if 'evolution' in s and (t >= S.NUM_ORIGINAL or S.is_record_original(s))}
    table = json.load(open(os.path.join(ROOT, 'content/tables/evolution-tree.json')))
    managed -= {t for t, s in sp.items() if s['name'] in table['record_parents']}
    lost = []; m = 0
    for p, x in sorted(g.items()):
        if p in managed or x['level'] not in ('in-training', 'rookie', 'champion', 'ultimate'): continue
        targets = [t for t in x['to'] if t in g]
        old = [t for t in targets if t not in managed]
        if len(old) == len(targets): continue
        kind = 'in-training' if x['level'] == 'in-training' else 'stats'
        for t in old:
            if t not in R: continue
            before = list(states(p, t, old, R, levels, kind))
            if not before: continue
            m += 1
            kept = sum(1 for st, care, w, b in before if pick(p, targets, R, levels, st, care, w, kind, b) == t)
            if kept < len(before):
                lost.append((x['name'], g[t]['name'], kept, len(before),
                             collections.Counter(g[pick(p, targets, R, levels, st, care, w, kind, b)]['name']
                                                 for st, care, w, b in before
                                                 if pick(p, targets, R, levels, st, care, w, kind, b) != t).most_common(2)))
    print(f'{m} disc routes with new siblings; routes that lose some states to a new species: {len(lost)}'
          f' (kept {sum(k for _, _, k, _, _ in lost)} of {sum(n for _, _, _, n, _ in lost)})')
    if '-v' in sys.argv:
        for p, t, k, n, who in lost: print(f'  {p} -> {t}: {k}/{n} states kept; taken by {who}')
    # the canonical state of a disc route must still win
    broken = []
    for p, x in sorted(g.items()):
        if p in managed or x['level'] not in ('in-training', 'rookie', 'champion', 'ultimate'): continue
        targets = [t for t in x['to'] if t in g]; old = [t for t in targets if t not in managed]
        if len(old) == len(targets): continue
        kind = 'in-training' if x['level'] == 'in-training' else 'stats'
        for t in old:
            if t in R and not keeps_canonical(p, t, old, targets, R, levels, kind):
                st, care, w, b = canonical(p, t, R, levels)
                got = pick(p, targets, R, levels, st, care, w, kind, b)
                broken.append((x['name'], g[t]['name'], g[got]['name'] if got in g else got))
    print(f'disc routes whose canonical state now picks a new species: {len(broken)}')
    for p, t, w in broken: print(f'  {p} -> {t}: now {w}')
    import test_evo_tree
    table = json.load(open(os.path.join(ROOT, 'content/tables/evolution-tree.json')))
    topology = test_evo_tree.check(sp, {p: [c for c in x['to'] if c in sp] for p, x in g.items()}, table)
    for error in topology: print('ERROR:', error)
    print(f'evolution topology failures: {len(topology)}')
    return bool(bad or broken or topology)


if __name__ == '__main__':
    sys.exit(main())
