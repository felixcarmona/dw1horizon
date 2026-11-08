#!/usr/bin/env python3
"""Build four local proposal screens using the existing release snapshot reader."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/guide'))
import build as guide
import recruits


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ref', default='v0.0.7')
    parser.add_argument('--out', type=Path, default=ROOT / 'build/wiki-mockups')
    args = parser.parse_args()
    commit, moves, species, tree, files = guide.snapshot(args.ref)
    partners = {s['id']: s for s in species if 'partner' in s}
    routes = {i: [n for n in tree.get('routes', {}).get(str(i), s.get('evolution', {})).get('to', []) if n in partners] for i, s in partners.items()}
    names = {s['name']: i for i, s in partners.items()}
    for rule in tree['ultimate_rules']:
        a, b = names[rule['from']], names[rule['to']]
        if b not in routes[a]:
            routes[a].append(b)
    agumon = partners[3]
    move_rows = []
    for name in agumon['techniques']:
        move = guide.resolve_move(name, moves)
        move_rows.append(dict(id=move['id'], name=move['name'], element=move['element'], power=move['power'], mp=guide.base_mp(move), chance=guide.chance(agumon, move)))
    recruit = next(r for r in recruits.load(files, species) if r['id'] == 3)
    recruit['place'] = recruits.screen_name(files, recruit['screens'][0], 'en')
    data = dict(version=args.ref, commit=commit, counts=dict(species=len(partners), techniques=len(moves), recruits=len(recruits.load(files, species))),
                digimon=dict(name='Agumon', id=3, level=agumon['level'], attribute=agumon['attribute'], specialties=agumon['specialties'], partner=agumon['partner'],
                             parents=[partners[i]['name'] for i in partners if 3 in routes[i]],
                             targets=[dict(name=partners[i]['name'], requirements=guide.requirements(partners[i], partners, tree).replace('<br>', '; ')) for i in routes[3]], moves=move_rows, recruit=recruit))
    args.out.mkdir(parents=True, exist_ok=True)
    here = Path(__file__).resolve().parent
    for name in ('mockup.css', 'mockup.js'):
        shutil.copyfile(here / name, args.out / name)
    shutil.copyfile(ROOT / 'web/style.css', args.out / 'site.css')
    shutil.copytree(ROOT / 'tools/guide/assets/font', args.out / 'font', dirs_exist_ok=True)
    (args.out / 'snapshot.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    for page, title in [('index', 'Wiki'), ('digimon', 'Agumon'), ('article', 'DuckStation on Android'), ('search', 'Search')]:
        (args.out / f'{page}.html').write_text(f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#cfd8f6"><title>{title} · Horizon wiki proposal</title><link rel="stylesheet" href="site.css"><link rel="stylesheet" href="mockup.css"><script type="module" src="mockup.js"></script></head><body data-page="{page}"><a class="skip" href="#main">Skip to content</a><div class="wrap"><header class="bar"><a class="brand" href="index.html">Digimon World: Horizon</a><nav class="pill" aria-label="Main"><a href="index.html" class="active">Wiki</a><span class="language-label">English</span></nav></header><div id="app"></div><footer class="wiki-foot">Digimon World: Horizon · Wiki design proposal<br>Maintained in the project repository · No community editing</footer></div></body></html>\n''')
    print(f'{args.ref} {commit}: {args.out}')


if __name__ == '__main__':
    main()
