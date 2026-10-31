#!/usr/bin/env python3
"""The evolution graph the game ends up with (docs/reference/partner.md), read from a built DIGI.DAT:
the disc's paths (types 1..62, with the engine layer) plus the links the archive applies at boot, and the records'
own paths. Prints per level: partners, reachable ones by natural evolution, free child slots.

  tools/evo_graph.py [DIGI.DAT]        (default build/full/DIGI.DAT)
  tools/evo_graph.py DIGI.DAT --json   the graph as JSON {id: {name, level, from, to}}
"""
import sys as _sys
if __name__ == '__main__' and _sys.argv[1:2] in (['-h'], ['--help']): print(__doc__); _sys.exit(0)
import collections, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import species as S

# species the game reaches without a "to" link (evolution.c handleSpecialEvolutions, the Rookie 96 h fallback,
# the virus bar, items.c handleEvoItems and its three special items, the mod's Machinedramon check); an item route
# gives no evolution gains (HAS_USED_EVOITEM)
SPECIAL = {7, 58, 47, 32, 49, 53, 28, 11, 0x27, 115}
ITEM = {0x05, 0x09, 0x15, 0x24, 0x2f, 0x26, 0x08, 0x06, 0x22, 0x30, 0x14, 0x25, 0x07, 0x32, 0x21, 0x13, 0x33, 0x19,
        0x3a, 0x0a, 0x18, 0x23, 0x31, 0x16, 0x17, 0x34, 0x35, 0x0c, 0x1a, 0x28, 0x36, 0x0d, 0x1b, 0x29, 0x37, 0x0e,
        0x1c, 0x2a, 0x38, 0x3b, 0x3c, 0x3d, 0x3e, 0x40, 0x3f, 0x41}
LEVELS = ['none', 'fresh', 'in-training', 'rookie', 'champion', 'ultimate', 'mega']


def graph(dat):
    d, count, recs = S.read_archive(dat)
    partners, _, links = S.read_index(d)
    eng = json.load(open(os.path.join(ROOT, 'content/balance/engine/tables.json')))['species']
    O = S.originals(); N = S.names('digimon') if 'digimon' in S.__dict__.get('_KINDS', ['digimon']) else None
    sp = S.load_content()
    g = {}
    for t, s in sp.items():
        if 'partner' not in s and t >= S.NUM_ORIGINAL: continue
        r = recs[t] if t < len(recs) and recs[t] else None
        if r is not None and (t >= S.NUM_ORIGINAL or t in S.record_originals(d)):
            p = r['evoPaths']
        elif t < S.NUM_ORIGINAL and O.rec[t].get('evoPaths'):
            p = {k: list(v) for k, v in O.rec[t]['evoPaths'].items()}
            for k, v in eng.get(str(t), {}).get('evoPaths', {}).items(): p[k] = list(v)
            # balance.py writes authored resident paths after the engine layer.
            # Archive links omit entries already present in those native rows.
            authored = s.get('evolution', {})
            if 'from' in authored:
                p = {k: list(authored.get(k, [])) for k in ('from', 'to')}
        else:
            p = {'from': [], 'to': []}
        g[t] = dict(name=s['name'], level=s['level'], partner='partner' in s,
                    frm=[x for x in p.get('from', []) if x > 0], to=[x for x in p.get('to', []) if x > 0],
                    nto=len(p.get('to', [])), nfrom=len(p.get('from', [])))
    for o, t, is_from in links:
        if o in g and t in g:
            if is_from:
                if o not in g[t]['to'] and False: pass
                if t not in g[o]['frm']: g[o]['frm'].append(t)
            else:
                if t not in g[o]['to']: g[o]['to'].append(t)
    # the "to" lists are what the game walks; make "from" consistent with them
    for o, x in g.items():
        for t in x['to']:
            if t in g and o not in g[t]['frm']: g[t]['frm'].append(o)
    return g


def main():
    dat = next((a for a in sys.argv[1:] if not a.startswith('--')), os.path.join(ROOT, 'build/full/DIGI.DAT'))
    g = graph(dat)
    if '--json' in sys.argv:
        print(json.dumps({str(k): v for k, v in sorted(g.items())}, indent=1)); return
    # reachable from the four Fresh by natural evolution ("to" lists)
    table = json.load(open(os.path.join(ROOT, 'content/tables/evolution-tree.json')))
    special = {t for t, x in g.items() if x['name'] in table['special_routes']} | SPECIAL
    seen = set(); st = [t for t, x in g.items() if x['level'] == 'fresh'] + [t for t in special if t in g]
    while st:
        t = st.pop()
        if t in seen: continue
        seen.add(t); st += [c for c in g.get(t, {}).get('to', []) if c in g]
    print("documented special/story roots:", ", ".join(sorted({g[t]["name"] for t in special if t in g})))
    for lv in LEVELS[1:]:
        ps = [t for t, x in g.items() if x['level'] == lv and x['partner']]
        if not ps: continue
        free = sum(max(0, 6 - len(g[t]['to'])) for t in ps)
        unreach = [g[t]['name'] for t in ps if t not in seen]
        print(f'{lv:12} partners {len(ps):3}  reachable {len(ps) - len(unreach):3}  child slots used '
              f'{sum(len(g[t]["to"]) for t in ps):3} free {free:3}  unreachable: {len(unreach)}')
    un = [t for t, x in g.items() if x['partner'] and t not in seen and x['level'] not in ('none',)]
    print('only by an item (no gains):', ', '.join(sorted(g[t]['name'] for t in un if t in ITEM)))
    for lv in LEVELS[3:]:
        names = sorted(g[t]['name'] + ('' if t >= S.NUM_ORIGINAL else f' ({t})') for t in un if t not in ITEM and g[t]['level'] == lv)
        if names: print(f'no route, {lv} ({len(names)}):', ', '.join(names))


if __name__ == '__main__':
    main()
