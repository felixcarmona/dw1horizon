#!/usr/bin/env python3
"""Does the evolution chart show every evolution route? A model of the chart's detail view (game_menu.c
chartBuildLists, the boxes of renderEvoChartDetail) and of the game's natural pickers (evolution.c
getNaturalEvolutionTarget), both from a built DIGI.DAT and the compiled executable, compared with each other and with
the topology the sources ask for (content/species, content/tables/evolution-tree.json, evolution-rules.json).

  tools/evo_chart.py DIGI.DAT EXE_DIR             lists every route the chart leaves out (exit 1 when any)
  tools/evo_chart.py DIGI.DAT EXE_DIR --old       the same for the chart before its lists (slot by slot, 6 "to" boxes)
  tools/evo_chart.py DIGI.DAT EXE_DIR --show NAME the chart's lists of one species

EXE_DIR holds SLUS_010.32 and SLUS_010.32.elf (build/<name>/exe). NEW DIGIMON on: every species is allowed.
Item, story and rule evolutions (Devimon, Numemon's fallback, Sukamon, Nanimon...) have no box, as in the original.
"""
import sys as _sys
if __name__ == '__main__' and _sys.argv[1:2] in (['-h'], ['--help']): print(__doc__); _sys.exit(0)
import json, os, struct, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import species as S
import balance as B

NUM_EVOLVING = 63                 # include/dw/ids.h NUM_EVOLVING_DIGIMON: EVOLUTION_PATHS covers types 1..62
EXTRA_PARENTS, EXTRA_TARGETS = S.EXTRA_PARENTS, S.EXTRA_TARGETS
PAIR_MAX = 8
CHART_TO_MAX, CHART_FROM_MAX = 24, 12   # game_menu.c CHART_TO_MAX, CHART_FROM_MAX
TO_PAGE, FROM_PAGE = 6, 5               # boxes a page of each side holds


def pairs(exe, table):
    raw = exe.raw(table)
    return [p for p in (struct.unpack_from('<hh', raw, 4 * i) for i in range(len(raw) // 4)) if p[0] >= 0 and p[1] >= 0]


def game(dat, exe_dir):
    """What the game holds after boot: {id: (from[5], to[6])} as getEvolutionPath returns it, the Baby II extra Rookie
    lists {parent: [ids]}, the MOD_EVO_FRESH and MOD_EVO_ULTIMATE pairs, and each species' level."""
    exe = B.Exe(exe_dir)
    raw = exe.raw('evoPaths')
    rows = {t + 1: struct.unpack_from('<11h', raw, 22 * t) for t in range(len(raw) // 22)}
    paths = {t: (list(v[:5]), list(v[5:])) for t, v in rows.items() if t < NUM_EVOLVING}
    d, count, recs = S.read_archive(dat)
    partners, _, links = S.read_index(d)
    levels = {}
    for t in range(count):
        if recs[t]: levels[t] = recs[t]['para']['level']
    O = S.originals()
    for t in range(1, S.NUM_ORIGINAL):
        if t not in levels and O.rec[t]: levels[t] = O.rec[t]['para']['level']
    extra = {}
    for o, t, is_from in links:                      # mod_species.c addEvolutionLink, in the archive's order
        if o < 1 or o >= NUM_EVOLVING: continue
        lst = paths[o][0 if is_from else 1]
        if t in lst: continue
        if -1 in lst: lst[lst.index(-1)] = t
        elif not is_from and levels.get(o) == 2:      # addExtraTarget
            if o not in extra and len(extra) >= EXTRA_PARENTS: continue
            ex = extra.setdefault(o, [])
            if t not in ex and len(ex) < EXTRA_TARGETS: ex.append(t)
    for t in partners:
        if t >= NUM_EVOLVING and recs[t] and recs[t]['flags'] & S.FLAG_PARTNER:
            p = recs[t]['evoPaths']
            paths[t] = (list(p['from']), list(p['to']))
    return dict(paths=paths, extra=extra, fresh=pairs(exe, 'evolutionFresh'), ultimate=pairs(exe, 'evolutionUltimate'),
                levels=levels, partners=set(partners) | set(range(1, NUM_EVOLVING)) | set(chart_ids(d)[0]), names=names(recs),
                block=chart_ids(d)[1])


def chart_ids(d):
    """The species of the chart's tabs (DIGI.DAT's chart block: every species the chart can open) and the block's
    {child, parent} pairs after them (the parents of the species without a path row; none in an older archive)."""
    sec = struct.unpack_from(S.HEADER, d, 0)[9]
    if not sec: return [], []
    base = sec * S.SECTOR
    counts = struct.unpack_from(f'<{len(S.CHART_TABS)}H', d, base)
    at = 2 * (len(counts) + sum(counts))
    n = struct.unpack_from('<H', d, base + at)[0]
    return (list(struct.unpack_from(f'<{sum(counts)}H', d, base + 2 * len(counts))),
            [struct.unpack_from('<HH', d, base + at + 2 + 4 * k) for k in range(n)])


def names(recs):
    out = {}
    for t, r in enumerate(recs):
        if r: out[t] = r['para']['name']
    O = S.originals()
    for t in range(S.NUM_ORIGINAL):
        if t not in out and O.rec[t]: out[t] = O.rec[t]['para']['name']
    return out


def path(g, t):
    return g['paths'].get(t, ([-1] * 5, [-1] * 6))


def natural_children(g, t):
    """The targets getNaturalEvolutionTarget can pick for a partner of type t (NEW DIGIMON on, every model fits)."""
    lv = g['levels'].get(t, 0)
    frm, to = path(g, t)
    to = [x for x in to if x > 0]
    if lv == 1: return [c for p, c in g['fresh'] if p == t]
    if lv == 2: return to + [x for x in g['extra'].get(t, []) if x not in to]
    if lv in (3, 4): return to
    if lv == 5: return [c for p, c in g['ultimate'] if p == t] + to     # getModUltimate..., then a Champion-style row
    return []


def chart_lists(g, t):
    """The new chart's boxes of species t (game_menu.c chartBuildLists): the "to" slots in order, the Baby II's extra
    Rookies, the Fresh and Ultimate pairs from t; the "from" slots, the pairs into t, the extra lists holding t."""
    frm, to = path(g, t)
    kids, parents = [], []
    def add(lst, x, cap):
        if x > 0 and x not in lst and len(lst) < cap: lst.append(x)
    for x in to: add(kids, x, CHART_TO_MAX)
    for x in g['extra'].get(t, []): add(kids, x, CHART_TO_MAX)
    for p, c in g['fresh'] + g['ultimate']:
        if p == t: add(kids, c, CHART_TO_MAX)
    for x in frm: add(parents, x, CHART_FROM_MAX)
    for p, c in g['fresh'] + g['ultimate']:
        if c == t: add(parents, p, CHART_FROM_MAX)
    for p, ex in g['extra'].items():
        if t in ex: add(parents, p, CHART_FROM_MAX)
    for c, p in g['block']:
        if c == t: add(parents, p, CHART_FROM_MAX)
    return parents, kids


def old_chart_lists(g, t):
    """The boxes the chart drew before its lists: renderEvoChartDetail walked to[0..5] with the 6-box layout for an even
    count of slots that are not -1 and the 5-box one for an odd count (so slot 5 was not drawn), from[0..4] with 4 boxes
    for an even count and 5 for an odd one; nothing else."""
    frm, to = path(g, t)
    nf = sum(x != -1 for x in frm); nt = sum(x != -1 for x in to)
    return ([x for x in frm[:4 if nf % 2 == 0 else 5] if x > 0], [x for x in to[:6 if nt % 2 == 0 else 5] if x > 0])


def source_routes():
    """(parent, child) routes the sources ask for: the species files' links (evo_tree.model), the evolutionFresh and
    evolutionUltimate rows of evolution-rules.json."""
    import evo_tree as T
    sp, _, _ = T.load()
    kids, _, _ = T.model(sp)
    out = {(p, c) for p, cs in kids.items() for c in cs if 'partner' in sp.get(p, {}) or p < NUM_EVOLVING}
    rules = json.load(open(os.path.join(ROOT, 'content/tables/evolution-rules.json')))
    nm = {s['name']: t for t, s in sorted(sp.items(), reverse=True) if 'partner' in s or t < NUM_EVOLVING}
    for key in ('evolutionFresh', 'evolutionUltimate'):
        for r in rules.get(key, []):
            f, t = r['from'], r['to']
            out.add((nm[f] if isinstance(f, str) else f, nm[t] if isinstance(t, str) else t))
    return out, sp


def audit(g, lists, sources=None):
    """[(kind, parent, child)] of the routes the chart does not show: kind 'child' (missing in the parent's "to" boxes)
    or 'parent' (missing in the child's "from" boxes)."""
    routes = {(p, c) for p in g['partners'] for c in natural_children(g, p)}
    if sources is not None:
        routes |= {(p, c) for p, c in sources if p in g['levels'] and c in g['levels']}
    out = []
    for p, c in sorted(routes):
        if c not in lists(g, p)[1]: out.append(('child', p, c))
        if p not in lists(g, c)[0]: out.append(('parent', p, c))
    return out, routes


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if len(args) < 2: print(__doc__); return 2
    g = game(args[0], args[1])
    lists = old_chart_lists if '--old' in sys.argv else chart_lists
    nm = lambda t: f'{g["names"].get(t, "?")} ({t})'
    if '--show' in sys.argv:
        want = sys.argv[sys.argv.index('--show') + 1]
        for t, n in sorted(g['names'].items()):
            if n == want or str(t) == want:
                f, k = lists(g, t)
                print(f'{nm(t)}: level {g["levels"].get(t)}\n  from: {", ".join(map(nm, f))}\n  to:   {", ".join(map(nm, k))}'
                      f'\n  picker: {", ".join(map(nm, natural_children(g, t)))}')
        return 0
    sources, _ = source_routes()
    missing, routes = audit(g, lists, sources)
    lost = sorted((p, c) for p, c in sources if c not in natural_children(g, p) and p in g['levels'] and c in g['levels']
                  and g['levels'].get(p) != 1)
    for p, c in lost:
        print(f'not in the game: {nm(p)} -> {nm(c)} (the sources ask for it; the built pickers never choose it)')
    for kind, p, c in missing:
        print(f'missing {kind}: {nm(p)} -> {nm(c)}')
    shown = sum(1 for p in g['partners'] for _ in lists(g, p)[1])
    print(f'evolution chart: {len(routes)} routes, {shown} "to" boxes, {len(missing)} omissions, {len(lost)} routes not in the game')
    return 1 if missing or lost else 0


if __name__ == '__main__':
    sys.exit(main())
