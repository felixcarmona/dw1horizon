#!/usr/bin/env python3
"""Build the offline player guide from an owned-data Git snapshot (stdlib only)."""
import argparse
import html
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from localize import translate
import recruits

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
INPUTS = ['content/techniques', 'content/species', 'content/tables/evolution-tree.json',
          'docs/reference/partner.md', 'docs/reference/combat.md',
          'story/base', 'story/mods/what-the-island-forgot', 'content/maps',
          'content/screens', 'content/tables/city-residents.json',
          'content/tables/fishing.json', 'text']
STATS = {'hp': 'HP', 'mp': 'MP', 'offense': 'Offense', 'defense': 'Defense',
         'speed': 'Speed', 'brain': 'Brains'}
LEVELS = ['fresh', 'in-training', 'rookie', 'champion', 'ultimate', 'mega']
RANGES = {0: 'Other', 1: 'Melee', 2: 'Ranged', 3: 'Area', 4: 'Self buff'}
STATUSES = {0: '—', 1: 'Poison', 2: 'Confusion', 3: 'Stun', 4: 'Flatten'}


def esc(value):
    return html.escape(str(value), quote=True)


def snapshot(ref='v0.0.7'):
    commit = subprocess.check_output(['git', 'rev-parse', '--verify', ref + '^{commit}'], cwd=ROOT, text=True).strip()
    raw = subprocess.check_output(['git', 'archive', commit, *INPUTS], cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        files = {m.name: archive.extractfile(m).read() for m in archive if m.isfile()}
    techniques = [json.loads(v) for k, v in sorted(files.items()) if k.startswith('content/techniques/') and k.endswith('.json')]
    species = [json.loads(v) for k, v in sorted(files.items()) if k.startswith('content/species/') and k.endswith('.json')]
    tree = json.loads(files['content/tables/evolution-tree.json'])
    return commit, techniques, species, tree, files


def resolve_move(name, techniques):
    match = re.search(r' \((\d+)\)$', name)
    if match:
        return next(t for t in techniques if t['id'] == int(match[1]))
    found = [t for t in techniques if t['name'] == name]
    if len(found) != 1:
        raise ValueError(f'Ambiguous or unknown technique: {name}')
    return found[0]


def chance(species, technique):
    slots = species['specialties']
    if 'learnChances' not in technique or technique['element'] not in slots:
        return None
    return technique['learnChances'][slots.index(technique['element'])]


def base_mp(technique):
    # BTL_setupMoveExecution skips MP charging for finisher IDs 58..112.
    return 0 if 58 <= technique['id'] <= 112 else technique['mpCost'] * 3


def requirements(s, partners, tree):
    r = dict(s.get('evolution', {}).get('requirements', {}))
    r.update(tree.get('requirement_overrides', {}).get(str(s['id']), {}))
    if s['level'] in ('fresh', 'in-training'):
        return 'Fixed growth; no requirement score.'
    if not r or all(r.get(k, -1) == -1 for k in STATS):
        return 'Special route; no ordinary stat requirement row.'
    if s['level'] == 'rookie':
        marked = [label for k, label in STATS.items() if r.get(k) == 1]
        stats = 'Highest stat: ' + ' / '.join(marked) + ' (HP and MP divided by 10)'
    else:
        stats = ', '.join(f'{label} ≥ {r[k] * (10 if k in ("hp", "mp") else 1)}'
                          for k, label in STATS.items() if r.get(k, -1) >= 0) or 'No stat thresholds'
    flags = r.get('flags', 0)
    care = f'Care mistakes {"≤" if flags & 16 else "≥"} {r["care"]}' if r.get('care', -1) >= 0 else 'Care: no threshold'
    weight = f'Weight {r["weight"] - 5}–{r["weight"] + 5}' if r.get('weight', -1) >= 0 else 'Weight: no threshold'
    bonus = []
    if r.get('digimon') in partners:
        bonus.append('from ' + partners[r['digimon']]['name'])
    for k, label in [('discipline', 'Discipline'), ('happiness', 'Happiness'), ('techs', 'Learned techniques')]:
        if r.get(k, -1) >= 0:
            value = (r[k] + 100) // 2 if k == 'happiness' else r[k]
            boundary = (f' (rounded boundary; {value + 1} guarantees it)'
                        if k == 'happiness' and r[k] % 2 else '')
            bonus.append(f'{label} ≥ {value}{boundary}')
    if r.get('battles', -1) >= 0:
        bonus.append(f'Wins {"≤" if flags & 1 else "≥"} {r["battles"]}')
    if s['level'] == 'rookie' and (r.get('battles') == -2 or r.get('techs') == 0):
        bonus = ['Automatic']
    parts = [stats, care, weight, 'Bonus (any one): ' + ('; '.join(bonus) or 'none')]
    if s['id'] == 17 and 17 in tree.get('routes', {}).get('16', {}).get('to', []):
        parts.append('Tsunomon route: weight 21–31 instead (Koromon: 10–20).')
    return '<br>'.join(esc(p) for p in parts)


def cell(value, sort=None):
    return f'<td data-value="{esc(sort if sort is not None else re.sub("<[^>]+>", " ", str(value)))}">{value}</td>'


def table(ident, title, intro, headers, rows):
    head = ''.join(f'<th scope="col" aria-sort="none"><button type="button">{esc(h)} <span aria-hidden="true">↕</span></button></th>' for h in headers)
    return f'''<section id="{ident}" class="data-section"><h2>{title}</h2>{intro}
<div class="controls"><label for="{ident}-search">Search {title.lower()}</label>
<input id="{ident}-search" type="search" placeholder="Name, specialty, or any detail…" aria-controls="{ident}-table">
<output aria-live="polite">{len(rows)} entries</output></div>
<div class="scroll" role="region" aria-label="{title} table" tabindex="0"><table id="{ident}-table"><thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p class="empty" hidden>No matching entries.</p></section>'''


def render(commit, techniques, all_species, tree, version):
    partners = {s['id']: s for s in all_species if 'partner' in s}
    ordered = sorted(partners.values(), key=lambda s: (LEVELS.index(s['level']), s['name'].casefold(), s['id']))
    to = {i: [t for t in tree.get('routes', {}).get(str(i), s.get('evolution', {})).get('to', []) if t in partners] for i, s in partners.items()}
    named = {s['name']: s['id'] for s in ordered}
    timed = set()
    for rule in tree['ultimate_rules']:
        a, b = named[rule['from']], named[rule['to']]
        if b not in to[a]:
            to[a].append(b)
        timed.add((a, b))
    frm = {i: [] for i in partners}
    for a, targets in to.items():
        for b in targets:
            frm[b].append(a)
    def links(ids):
        return ', '.join(f'<a translate="no" href="#species-{i}">{esc(partners[i]["name"])}</a>' for i in ids) or '—'
    rows = []
    for t in sorted(techniques, key=lambda t: t['id']):
        status = STATUSES[t['status']] + (f' ({t["statusChance"]}%)' if t['status'] else '')
        kind = 'Learnable' if t['id'] < 58 else 'Finisher' if t['id'] <= 112 else 'Intrinsic / other'
        values = [cell(f'<span translate="no">{esc(t["name"])}</span> <small>#{t["id"]} · {kind}</small>', t['name']), cell(esc(t['element']).title()), cell(t['power'], t['power']), cell(base_mp(t), base_mp(t)), cell(RANGES[t['range']]), cell(status)]
        values += [cell(f'{c}%', c) for c in t['learnChances']] if 'learnChances' in t else [cell('—', -1)] * 3
        rows.append('<tr>' + ''.join(values) + '</tr>')
    tech_table = table('techniques', 'Techniques', '''<p>Enemy execution of a normal technique records it for learning; it need not land a hit. At battle end, your partner must not already know it, must have it in its species list, and must have a matching specialty. The first matching slot selects the chance below. <strong>Brains does not affect this battle roll.</strong> If several techniques pass their rolls, one is learned at random. Repeated casts do not add extra rolls for the same technique.</p><p>Chances are per candidate roll, not a guaranteed final award. MP is the base battle cost (data cost ×3), before condition and Brains modifiers. Finishers cost no MP. Status percentages apply on a successful hit. Finishers and intrinsic moves have no battle learning chance. Shared names show their data IDs.</p>''', ['Technique', 'Specialty', 'Power', 'MP', 'Range type', 'Status', '1st', '2nd', '3rd'], rows)
    rows, evolutions = [], []
    for s in ordered:
        moves = [resolve_move(n, techniques) for n in s['techniques'] if n is not None]
        learn = []
        intrinsic = []
        for t in moves:
            if t['id'] < 58:
                c = chance(s, t)
                learn.append(f'<li><span translate="no">{esc(t["name"])}</span> <small>#{t["id"]}</small> — {str(c) + "%" if c is not None else "no matching specialty; no battle roll"}</li>')
            elif t['id'] > 112:
                intrinsic.append(esc(t['name']) + f' #{t["id"]}')
        finishers = [t for t in moves if 58 <= t['id'] <= 112]
        finisher = '—'
        if finishers:
            f = dict(finishers[-1], **s.get('finisher', {}))
            finisher = f'<span translate="no">{esc(f["name"])}</span> <small>#{f["id"]}</small><br>{esc(f["element"]).title()} · Power {f["power"]}'
        specialties = ' / '.join(f'{i + 1}: {esc(e).title() if e else "—"}' for i, e in enumerate(s['specialties']))
        detail = f'<details><summary>{len(learn)} normal techniques</summary><ul>{"".join(learn)}</ul></details>' if learn else 'No normal techniques'
        if intrinsic:
            detail += '<br>Intrinsic: ' + ', '.join(intrinsic)
        special = tree['special_routes'].get(s['name'], '')
        # Devimon has ordinary routes in the current table as well as its special.
        if s['name'] == 'Devimon':
            special = 'Also available through a special transformation.'
        rows.append(f'<tr id="species-{s["id"]}">' + cell('<span translate="no">' + esc(s['name']) + '</span>') + cell(esc(s['level']).title(), LEVELS.index(s['level'])) + cell(specialties) + cell(detail) + cell(finisher) + '</tr>')
        notes = esc(special)
        timed_from = [a for a in frm[s['id']] if (a, s['id']) in timed]
        if timed_from:
            notes += ('<br>' if notes else '') + 'Timed route from ' + links(timed_from) + ('; from 48 hours.' if s['name'] == 'Machinedramon' else '; from 120 hours.') + ' Target requirements still apply.'
        evolutions.append('<tr>' + cell(f'<a translate="no" href="#species-{s["id"]}">{esc(s["name"])}</a>') + cell(links(frm[s['id']])) + cell(links(to[s['id']])) + cell(requirements(s, partners, tree)) + cell(notes or '—') + '</tr>')
    species_table = table('species', 'Species', '<p>All partner-enabled forms, including special and laboratory forms. Specialties keep their original slot positions. Expand a move list for its effective battle roll. A listed move without a matching specialty cannot be learned in battle by that form. Finisher power includes species-specific overrides.</p>', ['Species', 'Level', 'Specialties in order', 'Normal techniques / battle chance', 'Finisher'], rows)
    evo_table = table('evolutions', 'Evolutions', '''<p>Routes use <strong>NEW DIGIMON on</strong>. Read a target’s row for its requirements. Ordinary evolution needs <strong>3 of 4 points</strong>: care mistakes, weight, stats, and bonus. All listed stats must meet their thresholds, except Rookie targets, which test the highest stat instead (ties: Brains, Speed, Defense, Offense, MP, HP). Any one listed bonus condition earns the bonus point. Happiness uses the status screen’s 0–100 scale; wins and care mistakes count in the current form.</p><p>Selection favors a target you have not raised yet. For Rookie→Champion and Champion→Ultimate candidates scoring 3, it then compares the average of required stats (HP/MP divided by 10). The documented picker carries its average accumulator after a qualifying loser, so list order can affect this comparison. In-Training→Rookie keeps the best score and the first listed target on a tie. Fresh growth is fixed. Special and timed routes have their own triggers; item routes are outside this table.</p>''', ['Target / species', 'From', 'To', 'Target requirements (3 of 4 groups)', 'Special routes'], evolutions)
    version_note = 'the next version' if version == 'next' else version.removeprefix('v')
    header = re.search(r'<header class="bar">.*?</header>', (ROOT / 'web/index.html').read_text(), re.S).group()
    header = header.replace('href="#top"', 'href="../"').replace('href="data/"', 'href="./"')
    header = '\n'.join(line.rstrip() for line in header.splitlines())
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Horizon technique learning, species, evolutions, and recruit data."><title>Digimon World: Horizon — Player data</title><meta name="theme-color" content="#cfd8f6"><link rel="icon" href="assets/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="assets/site.css"><link rel="stylesheet" href="assets/guide.css"><script type="module" src="assets/guide.js"></script></head><body><div class="wrap">
{header}<main id="top"><section class="hero data-hero"><h1>Player data</h1><p class="hero-lead">Data for Horizon {esc(version_note)}. Source snapshot: <code translate="no">{commit[:12]}</code>.</p><nav class="hero-actions" aria-label="Guide sections"><a class="button primary" href="#techniques">Techniques</a><a class="button soft" href="#species">Species</a><a class="button soft" href="#evolutions">Evolutions</a><a class="button soft" href="#recruits">Recruits</a></nav></section>
<p class="data-overview">{len(techniques)} techniques · {len(partners)} partner forms · Search each table or select a column heading to sort.</p><noscript><p>All data is available below. Search and sorting need JavaScript.</p></noscript>{tech_table}{species_table}{evo_table}</main><footer class="foot"><p data-i18n="footer.legal"></p></footer></div></body></html>\n'''


def render_recruits(rows, files, lang, strings):
    def t(key):
        return strings['data.recruit.' + key]
    rendered = []
    places = recruits.screen_names(files, lang)
    for row in sorted(rows, key=lambda r: recruits.species_name(files, r['name'], lang).casefold()):
        locations = '<br>'.join(f'{esc(places[screen])} <small>#{screen}</small>'
                               for screen in row['screens'])
        name = recruits.species_name(files, row['name'], lang)
        method = strings[recruits.text_key(row, 'method')]
        availability = strings[recruits.text_key(row, 'when')]
        hp_location = f' (#{row["battle"][0]})' if 'battle' in row else ''
        hp = '<br><small>' + esc(t('hp').replace('{n}', str(row['hp'])) + hp_location) + '</small>' if row['hp'] is not None else ''
        if 'rematch_hp' in row:
            hp += '<br><small>' + esc(t('rematchHp').replace('{n}', str(row['rematch_hp']))) + '</small>'
        rendered.append(f'<tr id="recruit-{row["id"]}">' + cell(esc(name)) + cell(locations) +
                        cell(esc(availability)) + cell(esc(method) + hp) +
                        cell(esc(t('service.' + row['service']))) + cell(row['points'], row['points']) + '</tr>')
    # Use the shared table mechanics, with all visible and accessible labels localized.
    section = table('recruits', esc(t('title')), '<p>' + esc(t('intro')) + '</p>',
                    [t(k) for k in ('digimon', 'where', 'when', 'how', 'adds', 'points')], rendered)
    section = section.replace('Search ' + esc(t('title')).lower(), esc(t('search')))
    section = section.replace('Name, specialty, or any detail…', esc(strings['data.searchHint']))
    section = section.replace(f'{len(rows)} entries', esc(strings['data.count'].replace('{n}', str(len(rows)))))
    section = section.replace('No matching entries.', esc(strings['data.noResults']))
    section = section.replace(esc(t('title')) + ' table', esc(t('table')))
    return section


def build(out, ref='v0.0.7', version=None):
    commit, techniques, species, tree, files = snapshot(ref)
    recruit_rows = recruits.load(files, species)
    if version is None:
        if not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+', ref):
            raise ValueError('Use --version when building a non-release ref')
        version = ref[1:]
    out.mkdir(parents=True, exist_ok=True)
    (out / 'assets').mkdir(exist_ok=True)
    (out / 'assets/style.css').unlink(missing_ok=True)
    english = json.loads((ROOT / 'web/i18n/en.json').read_text())
    page = render(commit, techniques, species, tree, version)
    for catalog in sorted((ROOT / 'web/i18n').glob('*.json')):
        lang = catalog.stem
        filename = 'index.html' if lang == 'en' else lang + '.html'
        strings = json.loads(catalog.read_text())
        localized = translate(page, english, strings)
        localized = localized.replace('</main>', render_recruits(recruit_rows, files, lang, strings) + '</main>')
        localized = localized.replace('<html lang="en">', f'<html lang="{lang}">')
        localized = localized.replace('placeholder="Name, specialty, or any detail…"',
                                      'placeholder="' + esc(strings['data.searchHint']) + '"')
        (out / filename).write_text(localized, encoding='utf-8')
    for name in ('guide.css', 'guide.js'):
        shutil.copyfile(HERE / 'assets' / name, out / 'assets' / name)
    shutil.copyfile(ROOT / 'web/style.css', out / 'assets/site.css')
    shutil.copyfile(ROOT / 'web/favicon.svg', out / 'assets/favicon.svg')
    shutil.copytree(HERE / 'assets/font', out / 'assets/font', dirs_exist_ok=True)
    for name in ('i18n.js', 'flags.js'):
        (out / 'assets/js').mkdir(exist_ok=True)
        shutil.copyfile(ROOT / 'web/js' / name, out / 'assets/js' / name)
    shutil.copytree(ROOT / 'web/i18n', out / 'assets/i18n', dirs_exist_ok=True)
    return commit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ref', default='v0.0.7', help='release data ref (default: v0.0.7; never reads working data)')
    parser.add_argument('--version', default=None, help='matching version (inferred from a vX.Y.Z ref); next for development data')
    parser.add_argument('--out', type=Path, default=HERE / 'out')
    args = parser.parse_args()
    commit = build(args.out, args.ref, args.version)
    size = sum(p.stat().st_size for p in args.out.rglob('*') if p.is_file())
    print(f'Built guide from {commit}: {size:,} bytes')


if __name__ == '__main__':
    main()
