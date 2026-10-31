#!/usr/bin/env python3
"""The site's Digimon list and evolution guide (web/js/digimon.js), written to web/content/digimon.json so the page
does not read content/species. Text only: names, levels, attributes, techniques, evolution links and requirements.

The list is the species of the in-game evolution chart (species.chart_tabs: partners, a level after the other) with
OPTIONS' NEW DIGIMON on, the default. "to" is what the game's pickers walk: a species' own list plus every species that
names it in "from" (the build links both into the same rows), plus the pairs of evolutionUltimate
(content/tables/evolution-rules.json, getModUltimateEvolutionTarget in evolution.c: routes with no "to" slot); "from" is
the inverse of all that, not the species' slot list. `new` is true for every species the original game does not raise
(no "vanilla" in its file).

A requirement says what chartCardBuild (game_menu.c, patch 0176) writes on the guide's card, from the same fields
evoRequirementsMet (evolution.c) scores; a number is [n] for "n or more" and [lo, hi] for a range:
  req "automatic"   a Baby II after its Fresh (care -1 and weight -1)
  req.mistakes      null: any; flags 0x10: [0, care]; otherwise [care]
  req.weight        [weight - tolerance, weight + tolerance]
  req.top           a Rookie: the stats that may be its highest (the ones marked 1)
  req.stats         the other levels: {stat: [n]} of the stats asked for (HP and MP times hpMpDiv); null: any
  req.bonus         null: any (one that always holds); otherwise {from, discipline, happiness, battles, techs}, one is enough
  req.after         a species reached only by evolutionUltimate: the hours its parent must have spent in its form first
                    (evolutionTiming.hours.ultimate); the requirements score as any other, the game's chart has no card
A species with no "from" has no card in the game and no req here.

The file is not tracked: it must describe the release the page builds, so the release workflow writes it from the
tag's content, and main may already hold the next release's species.

  tools/site_digimon.py [--out PATH]   write web/content/digimon.json, or PATH
"""
import json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import species as S

OUT = os.path.join(ROOT, 'web', 'content', 'digimon.json')
RULES = os.path.join(ROOT, 'content', 'tables', 'evolution-rules.json')
STATS = ('hp', 'mp', 'offense', 'defense', 'speed', 'brain')
FLAG_MAX_BATTLES, FLAG_MAX_MISTAKES = 0x01, 0x10


def links(allsp, ids, rules=()):
    """({id: its evolutions}, {id: what evolves into it}), both in the chart's order; rules: evolutionUltimate's pairs."""
    place = {t: k for k, t in enumerate(ids)}
    to = {t: set() for t in ids}
    for t in ids:
        e = allsp[t]['evolution']
        to[t].update(c for c in e.get('to') or [] if c in place)
        for p in e.get('from') or []:
            if p in place: to[p].add(t)
    for r in rules:
        if r['from'] in place and r['to'] in place: to[r['from']].add(r['to'])
    back = {t: [p for p in ids if t in to[p]] for t in ids}
    return {t: sorted(to[t], key=place.get) for t in ids}, back


def requirements(r, level, score):
    if r['care'] == -1 and r['weight'] == -1: return 'automatic'
    max_mistakes, max_battles = r['flags'] & FLAG_MAX_MISTAKES, r['flags'] & FLAG_MAX_BATTLES
    tol = score['weightTolerance']
    q = {'mistakes': [0, r['care']] if max_mistakes else None if r['care'] <= 0 else [r['care']],
         'weight': [r['weight'] - tol, r['weight'] + tol]}
    if level == 'rookie':
        q['top'] = [k for k in STATS if r[k] == 1]
    else:
        q['stats'] = {k: [r[k] * (score['hpMpDiv'] if k in ('hp', 'mp') else 1)] for k in STATS if r[k] >= 0} or None
    if (r['battles'] != -1 and not max_battles and r['battles'] <= 0) or (r['techs'] != -1 and r['techs'] <= 0) \
            or (r['discipline'] != -1 and r['discipline'] <= 0):
        q['bonus'] = None
    else:
        b = {}
        if r['digimon'] != -1: b['from'] = r['digimon']
        if r['discipline'] != -1: b['discipline'] = [r['discipline']]
        if r['happiness'] != -1: b['happiness'] = [r['happiness']]
        if r['battles'] != -1: b['battles'] = [0, r['battles']] if max_battles else [r['battles']]
        if r['techs'] != -1: b['techs'] = [r['techs']]
        q['bonus'] = b
    return q


def techniques(s):
    """The technique names as the game shows them: the files add " (id)" to a name several ids share."""
    return list(dict.fromkeys(re.sub(r' \(\d+\)$', '', m) for m in s['techniques'] or [] if isinstance(m, str)))


def guide(content=None):
    allsp = S.load_content(content)
    S.drop_absent_links(allsp)
    ids = [t for tab in S.chart_tabs(allsp, {t: s for t, s in allsp.items() if t >= S.NUM_ORIGINAL or S.is_record_original(s)})
           for t in tab]
    with open(RULES) as f: rules = json.load(f)
    score, ultimate = rules['evolutionFormula']['score'], rules['evolutionUltimate']
    to, back = links(allsp, ids, ultimate)
    only_ruled = {t for t in ids if back[t] and set(back[t]) <= {r['from'] for r in ultimate if r['to'] == t}}
    rows = []
    for t in ids:
        s = allsp[t]
        row = {'id': t, 'name': s['name'], 'level': s['level'], 'attribute': s['attribute'], 'new': not s.get('vanilla'),
               'from': back[t], 'to': to[t]}
        if back[t]: row['req'] = requirements(s['evolution']['requirements'], s['level'], score)
        if t in only_ruled: row['req']['after'] = rules['evolutionTiming']['hours']['ultimate']
        row['techniques'] = techniques(s)
        rows.append(row)
    return {'pass': score['passPoints'], 'digimon': rows}


def text(g=None):
    g = g or guide()
    dump = lambda x: json.dumps(x, ensure_ascii=False, separators=(',', ':'))
    return '{"pass":%d,"digimon":[\n%s\n]}\n' % (g['pass'], ',\n'.join(dump(x) for x in g['digimon']))


def main():
    if '-h' in sys.argv or '--help' in sys.argv: print(__doc__); return 0
    out = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else OUT
    new = text()
    with open(out, 'w', encoding='utf-8') as f: f.write(new)
    print(f'{os.path.relpath(out)}: {len(new.encode())} bytes')
    return 0


if __name__ == '__main__':
    sys.exit(main())
