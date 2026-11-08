"""One release-pinned model for wiki pages, trees and search (stdlib only)."""
import ast
import io
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/guide'))
_guide_spec = importlib.util.spec_from_file_location('wiki_guide_reader', ROOT / 'tools/guide/build.py')
guide = importlib.util.module_from_spec(_guide_spec)
_guide_spec.loader.exec_module(guide)
import recruits

LANGS = ('en', 'es', 'pt-br', 'fr', 'de', 'it', 'ja', 'ca', 'zh-hans')
INPUTS = ('content/species', 'content/techniques', 'content/tables', 'content/icons',
          'content/maps', 'content/screens', 'story/base', 'story/mods/what-the-island-forgot',
          'text', 'mods/patches', 'docs/reference/partner.md', 'docs/reference/combat.md',
          'docs/mods/options.md', 'docs/release/README-players.md')


def snapshot(ref):
    commit = subprocess.check_output(['git', 'rev-parse', '--verify', ref + '^{commit}'], cwd=ROOT, text=True).strip()
    raw = subprocess.check_output(['git', 'archive', commit, *INPUTS], cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        files = {m.name: archive.extractfile(m).read() for m in archive if m.isfile()}
    return commit, files


def read_json(files, name):
    return json.loads(files[name])


def patch_sources(files):
    """Active non-removed lines in series order; never read the working game tree."""
    series = files['mods/patches/series'].decode().splitlines()
    for name in series:
        if not name or name.startswith('#'):
            continue
        raw = files['mods/patches/' + name].decode()
        yield name, '\n'.join(line[1:] for line in raw.splitlines()
                             if line[:1] in ('+', ' ') and not line.startswith('+++'))


def save_blocks(files):
    # Resolve the actual card creation expression, including later single-block patches.
    # An unrecognized new layout fails the build rather than publishing stale advice.
    defines, expression = {}, None
    for _, source in patch_sources(files):
        for name, value in re.findall(r'^#define\s+(\w+)\s+(0x[\da-fA-F]+|\d+)\b', source, re.M):
            defines[name] = int(value, 0)
        calls = re.findall(r'status\s*=\s*MemCardCreateFile\(\s*MEMORY_CARD_ID\s*,\s*SAVE_FILE_NAME\s*,\s*([^;]+?)\);', source, re.S)
        if calls:
            expression = calls[0].strip()
    if expression is None:
        raise ValueError('No reviewed memory-card creation expression in release')
    def evaluate(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return node.value
        if isinstance(node, ast.Name):
            return defines[node.id]
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.FloorDiv)):
            return evaluate(node.left) // evaluate(node.right)
        raise ValueError('Review changed memory-card block expression: ' + expression)
    count = evaluate(ast.parse(expression, mode='eval').body)
    if count not in (1, 2):
        raise ValueError('Review changed memory-card block count')
    return count


def load(ref):
    commit, files = snapshot(ref)
    all_species = [json.loads(v) for k, v in sorted(files.items()) if k.startswith('content/species/') and k.endswith('.json')]
    techniques = [json.loads(v) for k, v in sorted(files.items()) if k.startswith('content/techniques/') and k.endswith('.json')]
    partners = {s['id']: s for s in all_species if 'partner' in s}
    tree = read_json(files, 'content/tables/evolution-tree.json')
    rules = read_json(files, 'content/tables/evolution-rules.json')
    to = {i: [t for t in tree.get('routes', {}).get(str(i), s.get('evolution', {})).get('to', []) if t in partners] for i, s in partners.items()}
    named = {s['name']: s['id'] for s in partners.values()}
    timed = {}
    for rule in tree['ultimate_rules']:
        a, b = named[rule['from']], named[rule['to']]
        if b not in to[a]:
            to[a].append(b)
        timed[(a, b)] = rules['evolutionTiming'].get('megaHours', 120) if partners[b]['level'] == 'mega' else rules['evolutionTiming']['hours']['ultimate']
    frm = {i: [] for i in partners}
    for a, targets in to.items():
        for b in targets:
            frm[b].append(a)
    rows = []
    for i, s in sorted(partners.items(), key=lambda pair: (guide.LEVELS.index(pair[1]['level']), pair[1]['name'].casefold(), pair[0])):
        moves = []
        for name in s['techniques']:
            if name is None:  # An empty move slot, not a technique named null.
                continue
            move = guide.resolve_move(name, techniques)
            moves.append(dict(id=move['id'], chance=guide.chance(s, move)))
        rows.append(dict(id=i, name=s['name'], level=s['level'], attribute=s['attribute'],
                         specialties=[x for x in s['specialties'] if x], slots=s['specialties'],
                         moves=moves, finisher=s.get('finisher', {}), partner=s['partner'],
                         to=to[i], parents=frm[i], requirements=guide.requirements(s, partners, tree),
                         special=tree['special_routes'].get(s['name'], '')))
    for move in techniques:
        move['baseMP'] = guide.base_mp(move)
    roster = recruits.load(files, all_species)
    # Never export the cemetery dialogue, questions, answer sequence or method.
    for row in roster:
        if row['name'] == 'Bakemon':
            row['method'] = ''
            row['when'] = ''
        row.pop('evidence', None)
    tables = {name: read_json(files, f'content/tables/{name}.json') for name in
              ('new-game', 'training-gains', 'care-rules', 'battle-formulas', 'clock')}
    facts = dict(save_blocks=save_blocks(files), timing=rules['evolutionTiming'],
                 score=rules['evolutionFormula']['score'], **tables)
    hard = tables['battle-formulas']['battleFormulas'].get('hard')
    facts['hard'] = hard
    # Bind shared article claims to release source, not just a version string.
    patches = dict(patch_sources(files))
    joined = '\n'.join(patches.values())
    for needle in ('MOD_TRAIN_BLOCK', 'modQuizResult', 'MOD_DIFF_EASY'):
        if needle not in joined:
            raise ValueError('Article behavior needs review: ' + needle)
    players = files['docs/release/README-players.md'].decode()
    if '250%' not in players or '20 Hz' not in players:
        raise ValueError('Review frame-rate guidance against selected release')
    return dict(tag=ref, commit=commit, species=rows, techniques=techniques, recruits=roster,
                timed=timed, facts=facts, files=files, rules=rules)


def slug(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
